"""统一响应、业务异常与全局异常处理。"""

from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("moodwave.errors")


class APIError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        code: int | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.code = code if code is not None else status_code
        self.data = data
        self.headers = headers or {}
        super().__init__(message)


def success(data: Any = None, message: str = "ok", status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": 0, "message": message, "data": data},
    )


def error_response(
    status_code: int,
    message: str,
    *,
    code: int | None = None,
    data: Any = None,
    headers: dict[str, str] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "code": code if code is not None else status_code,
        "message": message,
        "data": data,
    }
    if request_id:
        payload["requestId"] = request_id
    response_headers = dict(headers or {})
    if request_id:
        response_headers.setdefault("X-Request-ID", request_id)
    return JSONResponse(status_code=status_code, content=payload, headers=response_headers)


def get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):  # noqa: ANN001
        rid = get_request_id(request)
        if exc.status_code >= 500:
            logger.error(exc.message, extra={"requestId": rid, "path": str(request.url.path)})
        else:
            logger.warning(
                "business_error",
                extra={
                    "requestId": rid,
                    "path": str(request.url.path),
                    "status": exc.status_code,
                    "detail": exc.message,
                },
            )
        return error_response(
            exc.status_code,
            exc.message,
            code=exc.code,
            data=exc.data,
            headers=exc.headers,
            request_id=rid,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errors = []
        for item in exc.errors():
            field = ".".join(str(part) for part in item.get("loc", []) if part not in ("body", "query", "path"))
            errors.append(
                {
                    "field": field or "request",
                    "message": item.get("msg", "参数不合法"),
                    "type": item.get("type", "value_error"),
                }
            )
        rid = get_request_id(request)
        logger.warning(
            "validation_error",
            extra={"requestId": rid, "path": str(request.url.path), "errors": errors},
        )
        return error_response(
            422,
            "请检查填写内容",
            data={"errors": errors},
            request_id=rid,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        rid = get_request_id(request)
        message = exc.detail if isinstance(exc.detail, str) else "请求无法完成"
        if exc.status_code == 404:
            message = "请求的资源不存在"
        return error_response(
            exc.status_code,
            message,
            headers=dict(getattr(exc, "headers", None) or {}),
            request_id=rid,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        rid = get_request_id(request)
        logger.exception(
            "unhandled_exception",
            extra={
                "requestId": rid,
                "path": str(request.url.path),
                "userId": getattr(request.state, "user_id", None),
                "context": {"trace": traceback.format_exc(limit=8)},
            },
        )
        # 5xx 通知可观测通道；失败不影响响应
        try:
            from .services.alerting import notify_server_error

            notify_server_error(rid or "-", str(request.url.path), repr(exc))
        except Exception:
            pass
        return error_response(
            500,
            "服务器开小差了，请稍后重试",
            request_id=rid,
        )
