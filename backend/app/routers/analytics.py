"""埋点上报、漏斗与留存分析。"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..errors import APIError, success
from ..models import Event, EventArchive, EventDef, Funnel, User, utcnow
from ..security import get_optional_user, require_permission
from ..services.ratelimit import enforce, get_client_ip
from ..utils import hash_user_id, iso, parse_datetime

router = APIRouter(prefix="/api/v1", tags=["analytics"])
logger = logging.getLogger("moodwave.analytics")
SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
SENSITIVE_KEYS = {"password", "passwd", "token", "access_token", "refresh_token", "authorization", "cookie", "secret", "email", "phone"}


class EventIn(BaseModel):
    eventKey: str = Field(min_length=2, max_length=100)
    sessionId: str = Field(min_length=8, max_length=64)
    props: dict[str, Any] | None = None
    occurredAt: str | None = None
    page: int = 0


class TrackIn(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=100)


def _sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return None
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                continue
            clean[str(key)[:64]] = _sanitize(item, depth + 1)
        return clean
    if isinstance(value, list):
        return [_sanitize(item, depth + 1) for item in value[:30]]
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:200]


@router.post("/track")
def track_events(
    payload: TrackIn,
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    origin = request.headers.get("origin")
    if origin:
        allowed_origins = set(settings.cors_origins)
        allowed_origins.add(settings.public_base_url.rstrip("/"))
        allowed_origins.add(f"{request.url.scheme}://{request.url.netloc}")
        if origin.rstrip("/") not in allowed_origins:
            raise APIError(403, "事件来源不被允许")
    enforce(request, "analytics:track:ip", limit=120, window_seconds=60)
    if user:
        enforce(request, "analytics:track:user", limit=600, window_seconds=60, discriminator=str(user.id))
    definitions = {row.key for row in db.query(EventDef).filter(EventDef.status == "active").all()}
    if not definitions:
        raise APIError(503, "事件定义尚未初始化")
    accepted = 0
    rejected = []
    for item in payload.events:
        if item.eventKey not in definitions:
            rejected.append({"eventKey": item.eventKey, "reason": "未注册的事件"})
            continue
        if not SESSION_RE.match(item.sessionId):
            rejected.append({"eventKey": item.eventKey, "reason": "sessionId 格式错误"})
            continue
        props = _sanitize(item.props or {})
        if len(json.dumps(props, ensure_ascii=False)) > 4096:
            rejected.append({"eventKey": item.eventKey, "reason": "props 过大"})
            continue
        occurred = parse_datetime(item.occurredAt) or utcnow()
        if occurred > utcnow() + timedelta(minutes=5):
            occurred = utcnow()
        db.add(
            Event(
                event_key=item.eventKey,
                user_id=None,  # 隐私：不直接落用户主键，只保存 HMAC 标识
                user_hash=hash_user_id(user.id) if user else None,
                session_id=item.sessionId,
                page=item.page,
                props=props,
                occurred_at=occurred,
            )
        )
        accepted += 1
    db.commit()
    return success({"accepted": accepted, "rejected": rejected[:20], "receivedAt": iso(utcnow())})


@router.get("/admin/analytics/definitions")
def definitions(
    admin: User = Depends(require_permission("analytics:manage")),
    db: Session = Depends(get_db),
):
    rows = db.query(EventDef).order_by(EventDef.category.asc(), EventDef.key.asc()).all()
    return success(
        {
            "items": [
                {"key": row.key, "name": row.name, "category": row.category, "status": row.status, "schema": row.props_schema}
                for row in rows
            ]
        }
    )


@router.get("/admin/analytics/summary")
def analytics_summary(
    days: int = Query(default=30, ge=1, le=180),
    admin: User = Depends(require_permission("analytics:manage")),
    db: Session = Depends(get_db),
):
    since = utcnow() - timedelta(days=days)
    rows = (
        db.query(Event.event_key, func.count(Event.id))
        .filter(Event.occurred_at >= since)
        .group_by(Event.event_key)
        .order_by(func.count(Event.id).desc())
        .all()
    )
    sessions = db.query(Event.session_id).filter(Event.occurred_at >= since).distinct().count()
    users = db.query(Event.user_hash).filter(Event.occurred_at >= since, Event.user_hash.isnot(None)).distinct().count()
    return success(
        {
            "periodDays": days,
            "events": [{"key": key, "count": count} for key, count in rows],
            "sessions": sessions,
            "identifiedUsers": users,
            "totalEvents": sum(count for _, count in rows),
        }
    )


@router.get("/admin/analytics/funnels")
def list_funnels(
    admin: User = Depends(require_permission("analytics:manage")),
    db: Session = Depends(get_db),
):
    rows = db.query(Funnel).order_by(Funnel.created_at.desc()).all()
    return success(
        {
            "items": [
                {
                    "id": row.id,
                    "name": row.name,
                    "steps": row.steps,
                    "createdAt": iso(row.created_at),
                }
                for row in rows
            ]
        }
    )


class FunnelStep(BaseModel):
    eventKey: str = Field(min_length=2, max_length=100)
    label: str = Field(min_length=1, max_length=50)


class FunnelIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    steps: list[FunnelStep] = Field(min_length=2, max_length=8)


@router.post("/admin/analytics/funnels")
def create_funnel(
    payload: FunnelIn,
    admin: User = Depends(require_permission("analytics:manage")),
    db: Session = Depends(get_db),
):
    defs = {row.key for row in db.query(EventDef).all()}
    for step in payload.steps:
        if step.eventKey not in defs:
            raise APIError(422, f"未注册事件：{step.eventKey}")
    row = Funnel(name=payload.name, steps=[step.model_dump() for step in payload.steps], created_by=admin.id)
    db.add(row)
    db.commit()
    return success({"funnel": {"id": row.id, "name": row.name, "steps": row.steps}}, status_code=201)


@router.get("/admin/analytics/funnel")
def funnel_analysis(
    funnelId: int | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    admin: User = Depends(require_permission("analytics:manage")),
    db: Session = Depends(get_db),
):
    funnel = db.get(Funnel, funnelId) if funnelId else db.query(Funnel).order_by(Funnel.id.asc()).first()
    if not funnel:
        raise APIError(404, "漏斗不存在")
    start = parse_datetime(from_) or (utcnow() - timedelta(days=30))
    end = parse_datetime(to) or utcnow()
    if start >= end:
        raise APIError(422, "开始时间必须早于结束时间")
    keys = [step["eventKey"] for step in funnel.steps]
    rows = (
        db.query(Event)
        .filter(Event.event_key.in_(keys), Event.occurred_at >= start, Event.occurred_at <= end)
        .order_by(Event.session_id.asc(), Event.occurred_at.asc())
        .all()
    )
    by_session: dict[str, list[str]] = {}
    for row in rows:
        by_session.setdefault(row.session_id, []).append(row.event_key)
    reach = [0] * len(keys)
    completed = 0
    for sequence in by_session.values():
        cursor = 0
        for key in sequence:
            if cursor < len(keys) and key == keys[cursor]:
                reach[cursor] += 1
                cursor += 1
        if cursor == len(keys):
            completed += 1
    base = reach[0] if reach else 0
    steps = []
    for index, step in enumerate(funnel.steps):
        count = reach[index]
        steps.append(
            {
                **step,
                "count": count,
                "conversionFromStart": round((count / base * 100) if base else 0, 1),
                "dropFromPrevious": round(((reach[index - 1] - count) / reach[index - 1] * 100) if index and reach[index - 1] else 0, 1),
            }
        )
    return success(
        {
            "funnel": {"id": funnel.id, "name": funnel.name},
            "range": {"from": iso(start), "to": iso(end)},
            "sessions": len(by_session),
            "completed": completed,
            "overallConversion": round((completed / base * 100) if base else 0, 1),
            "steps": steps,
        }
    )


@router.get("/admin/analytics/retention")
def retention_analysis(
    weeks: int = Query(default=6, ge=2, le=16),
    admin: User = Depends(require_permission("analytics:manage")),
    db: Session = Depends(get_db),
):
    """周留存：以 user_hash 关联跨会话，周一对齐 cohort。"""
    end = utcnow()
    start = end - timedelta(weeks=weeks)
    rows = (
        db.query(Event.user_hash, Event.occurred_at)
        .filter(Event.user_hash.isnot(None), Event.occurred_at >= start)
        .order_by(Event.occurred_at.asc())
        .all()
    )
    first_seen: dict[str, datetime] = {}
    activity: dict[str, set[tuple[int, int]]] = {}
    for user_hash, occurred in rows:
        first_seen[user_hash] = min(first_seen.get(user_hash, occurred), occurred)
        year, week, _ = occurred.isocalendar()
        activity.setdefault(user_hash, set()).add((year, week))

    def week_start(value: datetime) -> datetime:
        return (value - timedelta(days=value.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

    cohorts: dict[str, list[str]] = {}
    for user_hash, first in first_seen.items():
        cohorts.setdefault(week_start(first).date().isoformat(), []).append(user_hash)
    result = []
    for cohort_key in sorted(cohorts.keys(), reverse=True)[:weeks]:
        members = cohorts[cohort_key]
        cohort_start = datetime.fromisoformat(cohort_key)
        cells = []
        for offset in range(0, min(5, weeks)):
            target_start = cohort_start + timedelta(weeks=offset)
            target_end = target_start + timedelta(weeks=1)
            active = 0
            target_week = target_start.date().isocalendar()[:2]
            for user_hash in members:
                if target_week in activity.get(user_hash, set()):
                    active += 1
            cells.append(round(active / len(members) * 100, 1) if members else 0.0)
        result.append(
            {
                "cohort": cohort_key,
                "size": len(members),
                "retention": cells,
            }
        )
    return success(
        {
            "range": {"from": iso(start), "to": iso(end)},
            "weeks": weeks,
            "cohorts": result,
            "note": "留存按 user_hash 计算，不暴露可逆用户标识；0 周为注册当周。",
        }
    )


@router.get("/admin/analytics/events")
def recent_events(    page: int = 1,
    pageSize: int = 30,
    admin: User = Depends(require_permission("analytics:manage")),
    db: Session = Depends(get_db),
):
    from ..utils import page_params, paginate

    page, size = page_params(page, pageSize)
    rows, meta = paginate(db.query(Event).order_by(Event.occurred_at.desc()), page, size)
    return success(
        {
            "items": [
                {
                    "id": row.id,
                    "eventKey": row.event_key,
                    "sessionId": row.session_id[:8] + "…",
                    "props": row.props,
                    "occurredAt": iso(row.occurred_at),
                }
                for row in rows
            ],
            "pagination": meta,
        }
    )
