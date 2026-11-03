"""FastAPI 应用入口：中间件、路由、静态资源与启动种子。"""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db, session_scope
from .errors import APIError, register_exception_handlers
from .logging_config import access_log, configure_logging
from .middleware import IdempotencyMiddleware
from .routers import admin, analytics, auth, content, music, reports, social, uploads, users
from .services.notify import archive_old_notifications
from .services.analytics import archive_old_events
from .utils import iso, utcnow

configure_logging()
logger = logging.getLogger("moodwave.app")

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime()
    init_db()
    if settings.auto_seed:
        from .seed import run_seed

        run_seed()
    try:
        with session_scope() as db:
            archive_old_notifications(db)
            archive_old_events(db)
    except Exception as exc:
        logger.warning("notification_archive_startup_failed error=%s", exc)
    if settings.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.08, environment=settings.app_env)
            logger.info("sentry_initialized")
        except Exception as exc:
            logger.warning("sentry_init_failed error=%s", exc)
    logger.info(
        "startup_complete env=%s online_music=%s",
        settings.app_env,
        settings.enable_online_music,
    )
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Moodwave API",
    version="1.0.0",
    description="基于本地人脸情绪识别的歌曲推荐系统 API。统一响应 { code, message, data }。",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Idempotency-Key", "X-Tracking-Source"],
    expose_headers=["X-Request-ID", "Retry-After", "Content-Disposition", "X-Idempotent-Replay"],
    max_age=600,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(IdempotencyMiddleware)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "")
    if not REQUEST_ID_RE.match(request_id):
        request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > (settings.max_video_mb + 15) * 1024 * 1024:
        return JSONResponse(
            {"code": 413, "message": "请求体过大", "data": None},
            status_code=413,
            headers={"X-Request-ID": request_id},
        )
    try:
        response = await call_next(request)
    except Exception:
        # 异常处理器会再生成响应；这里记录耗时并继续抛出
        logger.exception("request_failed", extra={"requestId": request_id, "path": request.url.path})
        raise
    elapsed = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: blob: https:; media-src 'self' blob: https:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; font-src 'self' data:; "
        "connect-src 'self' https:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if settings.is_production or request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    level = "error" if response.status_code >= 500 else ("warning" if response.status_code >= 400 else "info")
    access_log(
        level=level,
        message="request_completed",
        request_id=request_id,
        user_id=getattr(request.state, "user_id", None),
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=elapsed,
        ip=request.client.host if request.client else "unknown",
    )
    return response


register_exception_handlers(app)

# API 路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(content.router)
app.include_router(uploads.router)
app.include_router(music.router)
app.include_router(social.router)
app.include_router(admin.router)
app.include_router(analytics.router)
app.include_router(reports.router)
app.include_router(social.share_router)
app.include_router(social.health_router)

# 本地媒体静态服务
media_path = Path(settings.media_root)
if media_path.exists():
    app.mount("/media", StaticFiles(directory=str(media_path)), name="media")

# 构建产物静态资源（生产）
dist_path = Path(settings.frontend_dist)
assets_path = dist_path / "assets"
if assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")


@app.get("/", include_in_schema=False)
def root():
    index = dist_path / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        {
            "code": 0,
            "message": "Moodwave API is running. 前端开发服务器：http://localhost:5173",
            "data": {"health": "/healthz", "docs": "/api/docs"},
        }
    )


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    if full_path.startswith(("api/", "media/", "assets/")):
        raise APIError(404, "接口不存在")
    if dist_path.exists():
        candidate = (dist_path / full_path).resolve()
        if dist_path.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        index = dist_path / "index.html"
        if index.exists():
            return FileResponse(index)
    raise APIError(
        404,
        "前端尚未构建。开发模式请访问 Vite 的 5173 端口，或执行 npm run build。",
    )
