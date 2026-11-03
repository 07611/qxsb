"""事件滚动归档。SQLite 无原生分区，使用独立归档表保持主表可查询。"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from ..models import Event, EventArchive, utcnow

logger = logging.getLogger("moodwave.analytics")


def archive_old_events(db: Session, days: int = 365, batch_size: int = 5000) -> int:
    cutoff = utcnow() - timedelta(days=days)
    rows = db.query(Event).filter(Event.occurred_at < cutoff).limit(batch_size).all()
    if not rows:
        return 0
    for row in rows:
        db.add(
            EventArchive(
                original_id=row.id,
                event_key=row.event_key,
                user_hash=row.user_hash,
                session_id=row.session_id,
                props=row.props,
                occurred_at=row.occurred_at,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )
        db.delete(row)
    db.commit()
    logger.info("events_archived count=%s cutoff=%s", len(rows), cutoff.isoformat())
    return len(rows)
