"""统计报表：按天预聚合并从 daily_metrics 读取，支持 CSV 导出。"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..errors import APIError, success
from ..models import AuditLog, DailyMetric, EmotionLog, Event, Feedback, Item, Track, User, utcnow
from ..security import require_permission
from ..services.ratelimit import get_client_ip
from ..utils import iso, parse_date

router = APIRouter(prefix="/api/v1", tags=["reports"])

REPORT_TYPES = {"overview", "emotions", "users", "content", "music", "feedback"}
METRIC_DEFINITIONS = {
    "users_new": ("新增用户", "人"),
    "items_new": ("新增内容", "篇"),
    "feedback_new": ("新增工单", "单"),
    "emotion_count": ("情绪识别", "次"),
    "play_count": ("曲目播放", "次"),
}
REPORT_TITLES = {
    "overview": "运营总览",
    "emotions": "情绪分布",
    "users": "用户增长",
    "content": "内容产出",
    "music": "音乐播放",
    "feedback": "工单状态",
}


def _upsert_metric(db: Session, day: date, metric: str, dimension: str, value: int) -> None:
    row = (
        db.query(DailyMetric)
        .filter(DailyMetric.day == day, DailyMetric.metric == metric, DailyMetric.dimension == dimension)
        .first()
    )
    if row:
        row.value = value
    else:
        db.add(DailyMetric(day=day, metric=metric, dimension=dimension, value=value))


def refresh_daily_metrics(db: Session, start: date, end: date) -> None:
    """可重复执行的按天预聚合；报表只读该表，避免每次全量扫描。"""
    day = start
    while day <= end:
        next_day = day + timedelta(days=1)
        start_dt = datetime.combine(day, datetime.min.time())
        end_dt = datetime.combine(next_day, datetime.min.time())
        _upsert_metric(db, day, "users_new", "all", db.query(User).filter(User.created_at >= start_dt, User.created_at < end_dt).count())
        _upsert_metric(db, day, "items_new", "all", db.query(Item).filter(Item.created_at >= start_dt, Item.created_at < end_dt).count())
        _upsert_metric(db, day, "feedback_new", "all", db.query(Feedback).filter(Feedback.created_at >= start_dt, Feedback.created_at < end_dt).count())
        _upsert_metric(
            db,
            day,
            "play_count",
            "all",
            db.query(Event).filter(Event.event_key == "music_play", Event.occurred_at >= start_dt, Event.occurred_at < end_dt).count(),
        )
        for emotion, count in (
            db.query(EmotionLog.emotion, func.count(EmotionLog.id))
            .filter(EmotionLog.created_at >= start_dt, EmotionLog.created_at < end_dt)
            .group_by(EmotionLog.emotion)
            .all()
        ):
            _upsert_metric(db, day, "emotion_count", emotion, int(count))
        day = next_day
    db.commit()


def _bucket(day: date, group_by: str) -> str:
    if group_by == "week":
        monday = day - timedelta(days=day.weekday())
        return monday.isoformat()
    if group_by == "month":
        return day.replace(day=1).isoformat()
    return day.isoformat()


def _rows_to_series(rows: list[DailyMetric], group_by: str) -> list[dict]:
    bucket_map: dict[str, dict[str, int | float]] = {}
    for row in rows:
        bucket = _bucket(row.day, group_by)
        bucket_map.setdefault(bucket, {})
        bucket_map[bucket][row.metric] = bucket_map[bucket].get(row.metric, 0) + row.value
    series = []
    for bucket in sorted(bucket_map.keys()):
        item = {"date": bucket}
        item.update(bucket_map[bucket])
        series.append(item)
    return series


def _csv_response(meta: dict, series: list[dict], emotion_breakdown: list[dict]) -> StreamingResponse:
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow([f"Moodwave 报表 · {REPORT_TITLES.get(meta['type'], meta['type'])}"])
    writer.writerow(["区间", meta["from"], "至", meta["to"], "分组", meta["groupBy"]])
    writer.writerow([])
    if series:
        writer.writerow(["时间"] + list(series[0].keys())[1:])
        for row in series:
            writer.writerow([row.get("date")] + [row.get(key, 0) for key in list(row.keys())[1:]])
    if emotion_breakdown:
        writer.writerow([])
        writer.writerow(["情绪", "次数", "占比(%)"])
        for row in emotion_breakdown:
            writer.writerow([row["label"], row["count"], row["percentage"]])
    if meta.get("summary"):
        writer.writerow([])
        writer.writerow(["汇总指标", "值"])
        for key, value in meta["summary"].items():
            writer.writerow([key, value])
    data = buffer.getvalue().encode("utf-8")
    filename = f"moodwave-{meta['type']}-{meta['from']}-{meta['to']}.csv"
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/{report_type}")
def get_report(
    report_type: str,
    request: Request,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    groupBy: Literal["day", "week", "month"] = "day",
    format: Literal["json", "csv"] = "json",
    admin: User = Depends(require_permission("reports:view")),
    db: Session = Depends(get_db),
):
    if report_type not in REPORT_TYPES:
        raise APIError(404, "不支持的报表类型")
    end_day = parse_date(to) or utcnow().date()
    start_day = parse_date(from_) or (end_day - timedelta(days=29))
    if start_day > end_day:
        raise APIError(422, "开始日期不能晚于结束日期")
    if (end_day - start_day).days > 366:
        raise APIError(422, "单次报表区间不能超过 366 天")
    refresh_daily_metrics(db, start_day, end_day)
    range_rows = (
        db.query(DailyMetric)
        .filter(DailyMetric.day >= start_day, DailyMetric.day <= end_day)
        .order_by(DailyMetric.day.asc())
        .all()
    )
    series: list[dict] = []
    emotion_breakdown: list[dict] = []
    summary: dict = {}
    labels = {}

    if report_type == "overview":
        series = _rows_to_series(range_rows, groupBy)
        summary = {
            "新增用户": sum(row.value for row in range_rows if row.metric == "users_new"),
            "新增内容": sum(row.value for row in range_rows if row.metric == "items_new"),
            "新增工单": sum(row.value for row in range_rows if row.metric == "feedback_new"),
            "情绪识别": sum(row.value for row in range_rows if row.metric == "emotion_count"),
            "曲目播放": sum(row.value for row in range_rows if row.metric == "play_count"),
        }
        labels = {key: value[0] for key, value in METRIC_DEFINITIONS.items()}
    elif report_type == "emotions":
        for row in range_rows:
            if row.metric != "emotion_count":
                continue
            emotion_breakdown.append({"emotion": row.dimension, "label": row.dimension, "count": row.value})
        # 合并分组后的情绪
        merged: dict[str, int] = {}
        for item in emotion_breakdown:
            merged[item["emotion"]] = merged.get(item["emotion"], 0) + item["count"]
        total = sum(merged.values())
        emotion_breakdown = [
            {
                "emotion": key,
                "label": {
                    "happy": "愉悦",
                    "sad": "低落",
                    "angry": "愤怒",
                    "fear": "不安",
                    "surprised": "惊喜",
                    "neutral": "平静",
                }.get(key, key),
                "count": count,
                "percentage": round(count / total * 100, 1) if total else 0.0,
            }
            for key, count in sorted(merged.items(), key=lambda item: item[1], reverse=True)
        ]
        series = [{"date": item["label"], "emotion_count": item["count"]} for item in emotion_breakdown]
        summary = {"总识别次数": total, "情绪类别数": len(emotion_breakdown)}
    elif report_type == "users":
        rows = [row for row in range_rows if row.metric == "users_new"]
        series = _rows_to_series(rows, groupBy)
        summary = {
            "新增用户": sum(row.value for row in rows),
            "累计用户": db.query(User).count(),
            "待审核": db.query(User).filter(User.status == "pending").count(),
        }
    elif report_type == "content":
        rows = [row for row in range_rows if row.metric == "items_new"]
        series = _rows_to_series(rows, groupBy)
        summary = {
            "新增内容": sum(row.value for row in rows),
            "已发布": db.query(Item).filter(Item.deleted_at.is_(None), Item.status == "published").count(),
            "草稿": db.query(Item).filter(Item.deleted_at.is_(None), Item.status == "draft").count(),
            "曲库": db.query(Track).count(),
        }
    elif report_type == "music":
        rows = [row for row in range_rows if row.metric == "play_count"]
        series = _rows_to_series(rows, groupBy)
        summary = {
            "播放次数": sum(row.value for row in rows),
            "本地曲目": db.query(Track).filter(Track.source == "local").count(),
            "在线曲目元数据": db.query(Track).filter(Track.source != "local").count(),
        }
    else:
        rows = [row for row in range_rows if row.metric == "feedback_new"]
        series = _rows_to_series(rows, groupBy)
        summary = {
            "新增工单": sum(row.value for row in rows),
            "待处理": db.query(Feedback).filter(Feedback.status == "open").count(),
            "处理中": db.query(Feedback).filter(Feedback.status == "processing").count(),
            "已解决": db.query(Feedback).filter(Feedback.status == "resolved").count(),
        }
    meta = {
        "type": report_type,
        "title": REPORT_TITLES[report_type],
        "from": start_day.isoformat(),
        "to": end_day.isoformat(),
        "groupBy": groupBy,
        "summary": summary,
        "labels": labels,
        "precision": {"percent": 1, "moneyUnit": "分"},
        "generatedAt": iso(utcnow()),
    }
    if format == "csv":
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="report.export",
                target_type="report",
                target_id=report_type,
                detail={"from": start_day.isoformat(), "to": end_day.isoformat(), "groupBy": groupBy},
                ip=get_client_ip(request)[:64],
            )
        )
        db.commit()
        return _csv_response(meta, series, emotion_breakdown)
    return success(
        {
            "meta": meta,
            "series": series,
            "breakdown": emotion_breakdown,
            "metricDefinition": METRIC_DEFINITIONS,
        }
    )
