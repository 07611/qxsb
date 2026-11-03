"""情绪识别、曲库、在线搜索、推荐与反馈接口。"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..errors import APIError, success
from ..models import EmotionLog, FavoriteTrack, RecommendationLog, Track, TrackFeedback, User, utcnow
from ..security import get_current_user, get_optional_user
from ..serializers import MOOD_LABELS, track_public
from ..services.audio import EMOTION_TARGETS
from ..services.emotion import EMOTION_COLORS, EMOTION_LABELS, engine, demos
from ..services.ratelimit import enforce, enforce_for_user, get_client_ip
from ..services.recommendation import algorithm_spec, recommend_local, search_online
from ..utils import iso, page_params, paginate

router = APIRouter(prefix="/api/v1", tags=["music"])
logger = logging.getLogger("moodwave.music")

EMOTION_META = [
    {
        "code": "happy",
        "label": EMOTION_LABELS["happy"],
        "color": EMOTION_COLORS["happy"],
        "target": EMOTION_TARGETS["happy"],
        "description": "嘴角上扬、眼睑微收，适合明亮而富有弹性的旋律。",
    },
    {
        "code": "sad",
        "label": EMOTION_LABELS["sad"],
        "color": EMOTION_COLORS["sad"],
        "target": EMOTION_TARGETS["sad"],
        "description": "眉眼低垂、嘴角下沉，先用低唤醒音乐承接，再缓慢提亮。",
    },
    {
        "code": "angry",
        "label": EMOTION_LABELS["angry"],
        "color": EMOTION_COLORS["angry"],
        "target": EMOTION_TARGETS["angry"],
        "description": "眉间收紧、下颌用力，用高能量节奏提供安全释放。",
    },
    {
        "code": "surprised",
        "label": EMOTION_LABELS["surprised"],
        "color": EMOTION_COLORS["surprised"],
        "target": EMOTION_TARGETS["surprised"],
        "description": "眼睛睁大、嘴巴张开，跳跃和明亮的音色会更合拍。",
    },
    {
        "code": "fear",
        "label": EMOTION_LABELS["fear"],
        "color": EMOTION_COLORS["fear"],
        "target": EMOTION_TARGETS["fear"],
        "description": "眉眼紧张、呼吸变浅，避免突然的高动态与刺耳瞬态。",
    },
    {
        "code": "neutral",
        "label": EMOTION_LABELS["neutral"],
        "color": EMOTION_COLORS["neutral"],
        "target": EMOTION_TARGETS["neutral"],
        "description": "表情舒展、肌肉放松，适合克制而均衡的编排。",
    },
]


@router.get("/emotion/demos")
def emotion_demos():
    items = demos()
    return success(
        {
            "items": items,
            "engine": engine.status(),
            "privacy": "所有演示照片与上传图片只在本地推理进程内使用，识别后不保存原图。",
        }
    )


@router.post("/emotion/analyze")
async def analyze_emotion(
    request: Request,
    file: UploadFile | None = File(default=None),
    demoId: str | None = Form(default=None),
    source: str = Form(default="upload"),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    enforce(request, "emotion:analyze", limit=40, window_seconds=60, discriminator=str(user.id) if user else "")
    if demoId:
        demo = next((item for item in demos() if item["id"] == demoId), None)
        if not demo:
            raise APIError(404, "演示照片不存在")
        path = Path(settings.demo_dir) / demo["file"]
        result = engine.analyze_path(path, source="demo")
    elif file is not None:
        raw = await file.read(settings.max_image_mb * 1024 * 1024 + 1)
        if len(raw) > settings.max_image_mb * 1024 * 1024:
            raise APIError(413, f"图片不能超过 {settings.max_image_mb}MB")
        result = engine.analyze_bytes(raw, source=source if source in {"upload", "camera", "video"} else "upload")
    else:
        raise APIError(422, "请上传图片或选择演示照片")
    log = EmotionLog(
        user_id=user.id if user else None,
        emotion=result["emotion"],
        confidence=result["confidence"],
        scores=result["scores"],
        source=result.get("source", source),
        inference_ms=result.get("inferenceMs", 0),
    )
    db.add(log)
    db.commit()
    result["logId"] = log.id
    result["emotionMeta"] = next((item for item in EMOTION_META if item["code"] == result["emotion"]), None)
    return success(result)


@router.get("/emotion/history")
def emotion_history(
    page: int = 1,
    pageSize: int = 12,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    rows, meta = paginate(
        db.query(EmotionLog).filter(EmotionLog.user_id == user.id).order_by(EmotionLog.created_at.desc()),
        page,
        size,
    )
    return success(
        {
            "items": [
                {
                    "id": row.id,
                    "emotion": row.emotion,
                    "label": EMOTION_LABELS.get(row.emotion, row.emotion),
                    "confidence": row.confidence,
                    "source": row.source,
                    "scores": row.scores,
                    "createdAt": iso(row.created_at),
                }
                for row in rows
            ],
            "pagination": meta,
        }
    )


@router.get("/music/emotions")
def emotion_catalog():
    return success({"items": EMOTION_META, "algorithm": algorithm_spec()})


@router.get("/music/algorithm")
def music_algorithm():
    return success(algorithm_spec())


@router.get("/music/local")
def local_tracks(
    mood: str | None = Query(default=None, max_length=20),
    page: int = 1,
    pageSize: int = 12,
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    query = db.query(Track).filter(Track.is_public.is_(True), Track.source == "local")
    if mood:
        query = query.filter(Track.mood == mood)
    rows, meta = paginate(query.order_by(Track.created_at.asc()), page, size)
    return success({"items": [track_public(track) for track in rows], "pagination": meta})


@router.get("/music/online")
async def online_tracks(mood: str = Query(default="neutral", max_length=20), limit: int = Query(default=6, ge=1, le=12)):
    tracks, error = await search_online(mood, limit)
    return success({"items": tracks, "onlineAvailable": error is None, "notice": error})


@router.get("/music/recommendations")
async def recommendations(
    emotion: str = Query(default="neutral", pattern="^(happy|sad|angry|surprised|fear|neutral)$"),
    limit: int = Query(default=8, ge=1, le=20),
    includeOnline: bool = True,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    local = recommend_local(db, user, emotion, min(limit, 12))
    online: list[dict] = []
    online_error = None
    if includeOnline and settings.enable_online_music:
        online, online_error = await search_online(emotion, min(4, limit))
    return success(
        {
            "emotion": emotion,
            "emotionLabel": EMOTION_LABELS.get(emotion, emotion),
            "local": local,
            "online": online,
            "onlineAvailable": online_error is None,
            "onlineNotice": online_error,
            "algorithm": algorithm_spec()["recommendation"],
            "generatedAt": iso(utcnow()),
        }
    )


@router.get("/music/favorites")
def favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Track)
        .join(FavoriteTrack, FavoriteTrack.track_id == Track.id)
        .filter(FavoriteTrack.user_id == user.id)
        .order_by(FavoriteTrack.created_at.desc())
        .all()
    )
    return success({"items": [track_public(track) for track in rows]})


@router.post("/music/{track_id}/favorite")
def add_favorite(
    track_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    track = db.get(Track, track_id)
    if not track:
        raise APIError(404, "曲目不存在")
    row = db.query(FavoriteTrack).filter(FavoriteTrack.user_id == user.id, FavoriteTrack.track_id == track_id).first()
    if not row:
        db.add(FavoriteTrack(user_id=user.id, track_id=track_id))
        track.like_count += 1
        db.commit()
    return success({"favorited": True, "trackId": track_id, "likeCount": track.like_count})


@router.delete("/music/{track_id}/favorite")
def remove_favorite(
    track_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(FavoriteTrack).filter(FavoriteTrack.user_id == user.id, FavoriteTrack.track_id == track_id).first()
    if row:
        track = db.get(Track, track_id)
        db.delete(row)
        if track and track.like_count > 0:
            track.like_count -= 1
        db.commit()
    return success({"favorited": False, "trackId": track_id})


class FeedbackIn(BaseModel):
    rating: int = Field(ge=-1, le=1)


@router.post("/music/{track_id}/feedback")
def track_feedback(
    track_id: int,
    payload: FeedbackIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.rating == 0:
        raise APIError(422, "rating 只能为 1（喜欢）或 -1（不喜欢）")
    track = db.get(Track, track_id)
    if not track:
        raise APIError(404, "曲目不存在")
    enforce_for_user(user.id, "music:feedback", limit=60, window_seconds=3600)
    row = db.query(TrackFeedback).filter(TrackFeedback.user_id == user.id, TrackFeedback.track_id == track_id).first()
    if row:
        row.rating = payload.rating
    else:
        db.add(TrackFeedback(user_id=user.id, track_id=track_id, rating=payload.rating))
    db.commit()
    return success({"trackId": track_id, "rating": payload.rating, "message": "偏好已记录，将影响后续推荐"})


@router.post("/music/{track_id}/play")
def record_play(
    track_id: int,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    track = db.get(Track, track_id)
    if not track:
        raise APIError(404, "曲目不存在")
    track.play_count += 1
    db.commit()
    return success({"trackId": track_id, "playCount": track.play_count})


@router.get("/music/history")
def recommendation_history(
    page: int = 1,
    pageSize: int = 10,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    query = (
        db.query(RecommendationLog, Track)
        .join(Track, Track.id == RecommendationLog.track_id)
        .filter(RecommendationLog.user_id == user.id)
        .order_by(RecommendationLog.created_at.desc())
    )
    total = query.count()
    rows = query.offset((page - 1) * size).limit(size).all()
    items = []
    for log, track in rows:
        item = track_public(track)
        item.update({"reason": log.reason, "score": log.score, "recommendedAt": iso(log.created_at), "recommendedFor": log.emotion})
        items.append(item)
    return success(
        {
            "items": items,
            "pagination": {
                "page": page,
                "pageSize": size,
                "total": total,
                "pages": max(1, (total + size - 1) // size),
                "hasNext": page * size < total,
            },
        }
    )


@router.get("/music/{track_id}")
def track_detail(track_id: int, db: Session = Depends(get_db)):
    track = db.get(Track, track_id)
    if not track or not track.is_public:
        raise APIError(404, "曲目不存在")
    data = track_public(track, detail=True)
    data["moodLabel"] = MOOD_LABELS.get(track.mood, track.mood)
    return success({"track": data})
