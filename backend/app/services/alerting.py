"""可选告警钩子：仅配置 ALERT_WEBHOOK_URL 时发送，失败静默降级。"""

from __future__ import annotations

import logging
import threading

import httpx

from ..config import settings

logger = logging.getLogger("moodwave.alerting")


def _post(payload: dict) -> None:
    try:
        httpx.post(settings.alert_webhook_url, json=payload, timeout=4)
    except Exception as exc:  # pragma: no cover - 外部依赖
        logger.warning("alert_webhook_failed error=%s", exc)


def notify_server_error(request_id: str, path: str, error: str) -> None:
    if not settings.alert_webhook_url:
        return
    payload = {
        "text": f"[Moodwave][5xx] requestId={request_id} path={path}",
        "requestId": request_id,
        "path": path,
        "error": error[:800],
    }
    threading.Thread(target=_post, args=(payload,), daemon=True).start()
