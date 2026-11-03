"""接口限流：优先 Redis（多实例），未配置时使用 SQLite 原子计数。"""

from __future__ import annotations

import hashlib
import time
import logging
from typing import Any

from fastapi import Request
from sqlalchemy import text

from ..config import settings
from ..database import SessionLocal
from ..errors import APIError
from ..utils import utcnow

logger = logging.getLogger("moodwave.ratelimit")
_redis_client: Any = None
_redis_checked = False


def _get_redis():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    if not settings.redis_url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=1.5)
        client.ping()
        _redis_client = client
        logger.info("rate_limit_backend_redis")
    except Exception as exc:  # pragma: no cover - 环境依赖
        logger.warning("redis_unavailable_fallback_sqlite error=%s", exc)
        _redis_client = None
    return _redis_client


def get_client_ip(request: Request | None) -> str:
    if request is None:
        return "unknown"
    forwarded = request.headers.get("x-forwarded-for") if settings.trust_proxy else None
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip") if settings.trust_proxy else None
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _hash_key(value: str) -> str:
    return hashlib.sha256(f"{settings.jwt_secret}:{value}".encode()).hexdigest()[:40]


def _increment_sqlite(key: str, window_seconds: int) -> tuple[int, int]:
    now = int(time.time())
    window_start = now - (now % window_seconds)
    retry_after = max(1, window_start + window_seconds - now)
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO rate_limit_counters (key, window_start, count)
                VALUES (:key, :window_start, 1)
                ON CONFLICT(key, window_start) DO UPDATE SET count = count + 1
                """
            ),
            {"key": key, "window_start": window_start},
        )
        count = db.execute(
            text("SELECT count FROM rate_limit_counters WHERE key=:key AND window_start=:ws"),
            {"key": key, "ws": window_start},
        ).scalar_one()
        db.commit()
        # 周期性清理，避免表无限增长
        if int(now) % 3600 < 2:
            db.execute(text("DELETE FROM rate_limit_counters WHERE window_start < :old"), {"old": now - 86400 * 2})
            db.commit()
        return int(count), retry_after
    finally:
        db.close()


def hit(key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
    """返回 (allowed, current, retry_after)。"""
    redis_client = _get_redis()
    if redis_client is not None:
        bucket = int(time.time()) // window_seconds
        redis_key = f"ratelimit:{key}:{bucket}"
        try:
            pipe = redis_client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds + 1)
            count = int(pipe.execute()[0])
            ttl = redis_client.ttl(redis_key)
            return count <= limit, count, max(1, int(ttl) if ttl and ttl > 0 else window_seconds)
        except Exception:
            logger.warning("redis_rate_limit_failed_fallback_sqlite")
    count, retry_after = _increment_sqlite(key, window_seconds)
    return count <= limit, count, retry_after


def enforce(
    request: Request | None,
    scope: str,
    *,
    limit: int,
    window_seconds: int,
    discriminator: str = "",
) -> None:
    ip = get_client_ip(request)
    suffix = _hash_key(discriminator) if discriminator else ""
    key = f"{scope}:{ip}:{suffix}"
    allowed, _count, retry_after = hit(key, limit, window_seconds)
    if not allowed:
        raise APIError(
            429,
            "操作过于频繁，请稍后再试",
            data={"retryAfter": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


def enforce_for_user(user_id: int, scope: str, *, limit: int, window_seconds: int) -> None:
    key = f"{scope}:user:{user_id}"
    allowed, _count, retry_after = hit(key, limit, window_seconds)
    if not allowed:
        raise APIError(
            429,
            "操作过于频繁，请稍后再试",
            data={"retryAfter": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


def remaining(key: str, limit: int, window_seconds: int) -> int:
    redis_client = _get_redis()
    if redis_client is not None:
        bucket = int(time.time()) // window_seconds
        current = int(redis_client.get(f"ratelimit:{key}:{bucket}") or 0)
        return max(0, limit - current)
    now = utcnow()
    return limit
