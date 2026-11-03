"""幂等写入中间件：所有 JSON 写请求 10 秒窗口内去重。"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from datetime import timedelta
from typing import Awaitable, Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .database import SessionLocal
from .models import IdempotencyKey, utcnow
from .services.ratelimit import get_client_ip

SKIP_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/track",
    "/api/v1/upload/put/",
)
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
MAX_BODY = 512 * 1024
WINDOW_SECONDS = 10


def _decode_headers(scope: Scope) -> dict[str, str]:
    return {key.decode("latin1").lower(): value.decode("latin1") for key, value in scope.get("headers", [])}


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")
        headers = _decode_headers(scope)
        content_type = headers.get("content-type", "")
        if (
            method not in WRITE_METHODS
            or not path.startswith("/api/v1/")
            or path.startswith(SKIP_PREFIXES)
            or ("application/json" not in content_type and "application/x-www-form-urlencoded" not in content_type)
        ):
            await self.app(scope, receive, send)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break
        if len(body) > MAX_BODY:
            await self._json(send, 413, "请求体过大")
            return

        scope_identity = hashlib.sha256(
            (headers.get("authorization", "") + "|" + get_client_ip_from_scope(scope)).encode()
        ).hexdigest()[:24]
        explicit_key = headers.get("x-idempotency-key", "").strip()
        request_hash = hashlib.sha256(bytes(body)).hexdigest()
        if explicit_key:
            key = hashlib.sha256(f"{scope_identity}:idem:{explicit_key}".encode()).hexdigest()
        else:
            key = hashlib.sha256(f"{scope_identity}:{method}:{path}:{request_hash}".encode()).hexdigest()
        now = utcnow()
        db = SessionLocal()
        try:
            row = db.get(IdempotencyKey, key)
            if row:
                if row.request_hash != request_hash:
                    await self._json(send, 409, "同一幂等键不能用于不同请求体")
                    return
                if row.status == "processing" and row.expires_at > now:
                    await self._json(send, 409, "相同请求正在处理中，请稍后重试", headers={"Retry-After": "1"})
                    return
                if row.status == "completed" and row.response_status and row.response_body and row.expires_at > now:
                    payload = base64.b64decode(row.response_body)
                    stored_headers = [
                        (key.encode("latin1"), value.encode("latin1"))
                        for key, value in (row.response_headers or [])
                        if key.lower() not in {"content-length", "date", "transfer-encoding"}
                    ]
                    stored_headers.append((b"x-idempotent-replay", b"true"))
                    stored_headers.append((b"content-length", str(len(payload)).encode()))
                    await send({"type": "http.response.start", "status": row.response_status, "headers": stored_headers})
                    await send({"type": "http.response.body", "body": payload, "more_body": False})
                    return
                db.delete(row)
                db.commit()
            pending = IdempotencyKey(
                key=key,
                request_hash=request_hash,
                status="processing",
                expires_at=now + timedelta(seconds=WINDOW_SECONDS),
            )
            db.add(pending)
            db.commit()
        finally:
            db.close()

        sent_body = bytearray()
        captured = {"status": 0, "headers": []}

        async def replay_receive() -> Message:
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        async def capture_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
                captured["headers"] = [
                    (key.decode("latin1"), value.decode("latin1")) for key, value in message.get("headers", [])
                ]
            elif message["type"] == "http.response.body" and len(sent_body) < MAX_BODY:
                sent_body.extend(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, replay_receive, capture_send)
        except Exception:
            self._delete(key)
            raise
        status = int(captured["status"])
        if 200 <= status < 300 and sent_body and len(sent_body) < MAX_BODY:
            db = SessionLocal()
            try:
                row = db.get(IdempotencyKey, key)
                if row:
                    row.status = "completed"
                    row.response_status = status
                    row.response_body = base64.b64encode(bytes(sent_body)).decode()
                    row.response_headers = captured["headers"]
                    row.expires_at = utcnow() + timedelta(seconds=WINDOW_SECONDS)
                    db.commit()
            finally:
                db.close()
        else:
            self._delete(key)

    def _delete(self, key: str) -> None:
        db = SessionLocal()
        try:
            row = db.get(IdempotencyKey, key)
            if row:
                db.delete(row)
                db.commit()
        finally:
            db.close()

    async def _json(self, send: Send, status: int, message: str, headers: dict[str, str] | None = None) -> None:
        payload = json.dumps({"code": status, "message": message, "data": None}, ensure_ascii=False).encode()
        response_headers = [(b"content-type", b"application/json; charset=utf-8"), (b"content-length", str(len(payload)).encode())]
        for key, value in (headers or {}).items():
            response_headers.append((key.encode(), value.encode()))
        await send({"type": "http.response.start", "status": status, "headers": response_headers})
        await send({"type": "http.response.body", "body": payload, "more_body": False})


def get_client_ip_from_scope(scope: Scope) -> str:
    client = scope.get("client")
    return client[0] if client else "unknown"
