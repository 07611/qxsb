"""站内通知：服务端组装文案、冗余未读数、90 天归档。"""

from __future__ import annotations

import logging

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..models import Notification, NotificationArchive, User, utcnow
from .cache import cache

logger = logging.getLogger("moodwave.notifications")


def create_notification(
    db: Session,
    *,
    user_id: int,
    type: str,
    title: str,
    message: str,
    target_type: str = "",
    target_id: str = "",
    payload: dict | None = None,
) -> Notification | None:
    exists = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.target_type == target_type,
            Notification.target_id == target_id,
        )
        .first()
    )
    if exists:
        return exists
    note = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        target_type=target_type,
        target_id=target_id,
        payload=payload or {},
    )
    db.add(note)
    db.execute(update(User).where(User.id == user_id).values(unread_count=User.unread_count + 1))
    cache.delete(f"notifications:unread:{user_id}:v1")
    db.flush()
    return note


def archive_old_notifications(db: Session, days: int = 90) -> int:
    cutoff = utcnow().replace(microsecond=0) - __import__("datetime").timedelta(days=days)
    rows = db.query(Notification).filter(Notification.created_at < cutoff).limit(5000).all()
    if not rows:
        return 0
    affected_users = set()
    for row in rows:
        if row.read_at is None:
            affected_users.add(row.user_id)
        db.add(
            NotificationArchive(
                original_id=row.id,
                user_id=row.user_id,
                type=row.type,
                title=row.title,
                message=row.message,
                read_at=row.read_at,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )
        db.delete(row)
    db.flush()
    for user_id in affected_users:
        user = db.get(User, user_id)
        if user:
            user.unread_count = (
                db.query(Notification)
                .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
                .count()
            )
            cache.delete(f"notifications:unread:{user_id}:v1")
    db.commit()
    logger.info("notifications_archived count=%s", len(rows))
    return len(rows)


def unread_count(db: Session, user_id: int) -> int:
    user = db.get(User, user_id)
    return int(user.unread_count) if user else 0
