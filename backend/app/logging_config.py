"""结构化 JSON 日志与请求上下文。"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from .config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname.lower(),
            "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "logger": record.name,
            "message": record.getMessage(),
            "requestId": getattr(record, "requestId", None),
            "userId": getattr(record, "userId", None),
            "context": getattr(record, "context", None) or {},
        }
        for key in ("path", "method", "status", "durationMs", "detail", "errors", "ip"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["context"]["exception"] = self.formatException(record.exc_info)[-4000:]
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("uvicorn.error").propagate = True


def access_log(
    *,
    level: str,
    message: str,
    request_id: str | None,
    user_id: int | None,
    method: str,
    path: str,
    status: int,
    duration_ms: float,
    ip: str,
    detail: str | None = None,
) -> None:
    logger = logging.getLogger("moodwave.access")
    log = getattr(logger, level, logger.info)
    log(
        message,
        extra={
            "requestId": request_id,
            "userId": user_id,
            "method": method,
            "path": path,
            "status": status,
            "durationMs": round(duration_ms, 2),
            "ip": ip,
            "detail": detail,
        },
    )
