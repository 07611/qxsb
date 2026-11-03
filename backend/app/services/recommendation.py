"""推荐算法：情绪向量匹配 + 音频特征距离 + 用户反馈 + 多样性重排。"""

from __future__ import annotations

import math
from collections import Counter

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import FavoriteTrack, RecommendationLog, Track, TrackFeedback, User
from ..services.audio import EMOTION_TARGETS
from ..services.cache import cache
from ..serializers import track_public

MOOD_QUERY = {
    "happy": "happy upbeat pop",
    "sad": "sad acoustic ballad",
    "angry": "angry rock energetic",
    "fear": "dark ambient tense",
    "surprised": "feel good dance",
    "neutral": "lofi chill instrumental",
}

REASON_TEMPLATES = {
    "happy": "明亮的调式与轻快节拍，会把愉悦感继续推高。",
    "sad": "较慢的速度与低唤醒度，给低落情绪留出被理解的空间。",
    "angry": "高能量、强节奏与短促和声，为愤怒提供安全的出口。",
    "fear": "低明亮度与不稳定和声，陪你穿过不安而不放大它。",
    "surprised": "跳跃的节奏和明亮音色，与惊喜的高唤醒度同频。",
    "neutral": "均衡的动态与克制编排，适合把注意力慢慢收回来。",
}


def _affinity(features: dict, emotion: str) -> float:
    target = EMOTION_TARGETS[emotion]
    v = float(features.get("valence", 0.5))
    a = float(features.get("arousal", 0.45))
    distance = math.hypot(v - target["valence"], a - target["arousal"])
    return max(0.0, 1 - distance / math.sqrt(2))


def _user_taste(db: Session, user: User | None) -> tuple[dict[str, float], set[int], set[int]]:
    if not user:
        return {}, set(), set()
    favorites = db.query(FavoriteTrack).filter(FavoriteTrack.user_id == user.id).all()
    feedback = db.query(TrackFeedback).filter(TrackFeedback.user_id == user.id).all()
    track_ids = {row.track_id for row in favorites} | {row.track_id for row in feedback}
    if not track_ids:
        return {}, set(), set()
    tracks = db.query(Track).filter(Track.id.in_(track_ids)).all()
    vectors = {track.id: track.audio_features or {} for track in tracks}
    liked, disliked = set(), set()
    v_sum = a_sum = weight_sum = 0.0
    for row in favorites:
        vec = vectors.get(row.track_id, {})
        v_sum += float(vec.get("valence", 0.5)) * 1.3
        a_sum += float(vec.get("arousal", 0.45)) * 1.3
        weight_sum += 1.3
        liked.add(row.track_id)
    for row in feedback:
        if row.rating > 0:
            vec = vectors.get(row.track_id, {})
            v_sum += float(vec.get("valence", 0.5)) * 1.8
            a_sum += float(vec.get("arousal", 0.45)) * 1.8
            weight_sum += 1.8
            liked.add(row.track_id)
        elif row.rating < 0:
            disliked.add(row.track_id)
    if weight_sum == 0:
        return {}, liked, disliked
    return {"valence": v_sum / weight_sum, "arousal": a_sum / weight_sum}, liked, disliked


def recommend_local(db: Session, user: User | None, emotion: str, limit: int = 8) -> list[dict]:
    target = EMOTION_TARGETS.get(emotion, EMOTION_TARGETS["neutral"])
    tracks = db.query(Track).filter(Track.is_public.is_(True), Track.source == "local").all()
    if not tracks:
        return []
    taste, liked, disliked = _user_taste(db, user)
    max_popularity = max(1, max(track.play_count + track.like_count for track in tracks))
    scored: list[tuple[float, Track, dict]] = []
    for track in tracks:
        if track.id in disliked:
            continue
        features = track.audio_features or {}
        mood_scores = track.mood_scores or {}
        affinity = _affinity(features, emotion)
        mood_prob = float(mood_scores.get(emotion, 0.0))
        pref = 0.0
        if taste:
            pref = 1 - math.hypot(
                float(features.get("valence", 0.5)) - taste.get("valence", 0.5),
                float(features.get("arousal", 0.45)) - taste.get("arousal", 0.45),
            ) / math.sqrt(2)
        novelty = 0.4 if track.id in liked else 1.0
        popularity = min(1.0, (track.play_count + track.like_count) / max_popularity)
        score = 0.42 * mood_prob + 0.28 * affinity + 0.12 * pref + 0.10 * novelty + 0.08 * popularity
        reason = _reason(track, features, emotion)
        scored.append((score, track, {"score": round(score, 4), "affinity": round(affinity, 3), "moodProbability": round(mood_prob, 3), "reason": reason}))
    scored.sort(key=lambda item: item[0], reverse=True)
    # 先保留明确同频的曲目，避免把明显不匹配的曲目塞进列表；不足 4 首时用最接近的补位
    relevant = [item for item in scored if item[2].get("moodProbability", 0) >= 0.12 or item[1].mood == emotion]
    if len(relevant) < 4:
        used_ids = {item[1].id for item in relevant}
        for item in scored:
            if item[1].id not in used_ids:
                relevant.append(item)
                used_ids.add(item[1].id)
            if len(relevant) >= 4:
                break
    candidates = relevant or scored

    # MMR 多样性重排：同一艺人最多 2 首，避免推荐列表同质化
    selected: list[tuple[float, Track, dict]] = []
    artist_counts: Counter[str] = Counter()
    for candidate in candidates:
        if artist_counts[candidate[1].artist] >= 2:
            continue
        selected.append(candidate)
        artist_counts[candidate[1].artist] += 1
        if len(selected) >= limit:
            break
    results = []
    for score, track, meta in selected:
        payload = track_public(track)
        payload.update(meta)
        results.append(payload)
        if user:
            db.add(
                RecommendationLog(
                    user_id=user.id,
                    emotion=emotion,
                    track_id=track.id,
                    score=score,
                    reason=meta["reason"],
                )
            )
    if user:
        db.commit()
    return results


def _reason(track: Track, features: dict, emotion: str) -> str:
    tempo = round(float(features.get("tempo", 0)))
    mode = "大调" if features.get("mode") == "major" else "小调"
    valence = float(features.get("valence", 0.5))
    arousal = float(features.get("arousal", 0.45))
    if emotion == "happy" and valence > 0.7:
        detail = f"{tempo} BPM · {mode}，明亮度较高"
    elif emotion == "sad" and valence < 0.4:
        detail = f"{tempo} BPM · {mode}，低唤醒的留白编排"
    elif emotion == "angry" and arousal > 0.65:
        detail = f"{tempo} BPM · 高能量，强拍推动"
    elif emotion == "fear" and arousal > 0.5:
        detail = f"{tempo} BPM · 不稳定和声与低频张力"
    elif emotion == "surprised":
        detail = f"{tempo} BPM · 明亮音色与跳跃节奏"
    else:
        detail = f"{tempo} BPM · {mode}，动态均衡"
    return f"{detail}。{REASON_TEMPLATES.get(emotion, '')}"


async def search_online(mood: str, limit: int = 6) -> tuple[list[dict], str | None]:
    if not settings.enable_online_music:
        return [], "在线曲库已关闭"
    mood = mood if mood in MOOD_QUERY else "neutral"
    cache_key = f"music:online:{mood}:{limit}:v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, None
    params = {
        "term": MOOD_QUERY[mood],
        "media": "music",
        "entity": "song",
        "limit": min(limit, 12),
        # 中国区 Apple Music 搜索经常不返回 previewUrl；预览资源使用美国区目录
        "country": "us",
    }
    tracks: list[dict] = []
    error = None
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            response = await client.get("https://itunes.apple.com/search", params=params)
            response.raise_for_status()
            payload = response.json()
        for item in payload.get("results", []):
            preview = item.get("previewUrl")
            if not preview:
                continue
            artwork = item.get("artworkUrl100", "").replace("100x100bb", "400x400bb")
            tracks.append(
                {
                    "id": f"itunes-{item.get('trackId')}",
                    "title": item.get("trackName", "未知曲目"),
                    "artist": item.get("artistName", "未知艺人"),
                    "album": item.get("collectionName", ""),
                    "mood": mood,
                    "moodLabel": {"happy": "愉悦", "sad": "低落", "angry": "愤怒", "fear": "不安", "surprised": "惊喜", "neutral": "平静"}[mood],
                    "coverUrl": artwork,
                    "duration": round((item.get("trackTimeMillis") or 30000) / 1000),
                    "source": "itunes",
                    "audioUrl": preview,
                    "previewUrl": preview,
                    "externalId": str(item.get("trackId")),
                    "licenseNote": "iTunes Search API · 30 秒试听；版权归原权利人",
                    "reason": "在线元数据匹配：曲风标签与该情绪的唤醒度/效价一致；播放的是官方预览片段。",
                    "score": 0.62,
                }
            )
        tracks = tracks[:limit]
    except Exception as exc:  # 外部服务不可用时降级，本地推荐不受影响
        error = "在线曲库暂时不可用，已继续展示本地曲目"
        try:
            from ..logging_config import access_log

            # 仅记录简短错误，避免把外部响应写入日志
            import logging

            logging.getLogger("moodwave.music").warning("itunes_search_failed error=%s", str(exc)[:200])
        except Exception:
            pass
    cache.set(cache_key, tracks, 300) if tracks else None
    return tracks, error


def algorithm_spec() -> dict:
    return {
        "face": {
            "name": "FER+ CNN + Haar 几何校准",
            "steps": [
                "Haar Cascade 多尺度检测人脸，筛选面积最大的人脸作为主目标",
                "裁切并转灰度，输入 FER+ 8 类表情 ONNX 卷积网络",
                "Haar 微笑/眼睛级联与嘴线曲率、眼裂开合、眉间明暗构成几何先验",
                "CNN 置信度不足时按权重融合几何先验，映射为 6 类情绪并归一化",
            ],
            "labels": ["happy", "sad", "angry", "surprised", "fear", "neutral"],
            "privacy": "图片只在本机服务进程内处理，不写入磁盘、不上传第三方。",
        },
        "music": {
            "name": "Krumhansl 调性 + Thayer 二维情绪模型",
            "steps": [
                "短时能量包络自相关估计 BPM",
                "FFT 谱质心与谱通量衡量明亮度/能量",
                "chroma 与 Krumhansl 大调/小调模板相关，判断调式",
                "valence = f(调式, 明亮度, 过零率)，arousal = f(BPM, 能量, 明亮度)",
                "将曲目映射到六类情绪概率分布，离线曲目真实分析音频，在线曲目使用元数据回退",
            ],
            "offline": "本地 WAV 曲目由真实音频特征计算；在线 iTunes 曲目仅做元数据匹配。",
        },
        "recommendation": {
            "name": "加权混合 + MMR 多样性重排",
            "formula": "score = 0.42×情绪概率 + 0.28×二维情绪距离 + 0.12×个人偏好 + 0.10×新鲜度 + 0.08×热度",
            "strategy": "先按当前情绪召回，再加入收藏/喜欢反馈；去除点过不喜欢的曲目；同一艺人最多 2 首；本地曲目优先，在线曲目补位。",
        },
    }
