"""站内通知、反馈工单、分享、运营位、客户端日志、i18n 与健康检查。"""

from __future__ import annotations

import html
import logging
import random
from datetime import timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db, healthcheck_database
from ..errors import APIError, success
from ..logging_config import access_log
from ..models import Attachment, Banner, ClientLog, Feedback, Item, Notification, ShareLink, User, utcnow
from ..security import get_current_user, get_optional_user
from ..serializers import banner_public, feedback_public, notification_public
from ..services.cache import cache
from ..services.ratelimit import enforce, get_client_ip
from ..utils import clean_text, iso, page_params, paginate, public_media_url, safe_link, short_code

router = APIRouter(prefix="/api/v1", tags=["social"])
share_router = APIRouter(tags=["share"])
logger = logging.getLogger("moodwave.social")

POSITION_MAP = {"home": 0, "discover": 1, "settings": 2}
MAX_BANNERS = {"home": 3, "discover": 2, "settings": 1}


# ── 通知 ────────────────────────────────────────────────────────────────
@router.get("/notifications")
def list_notifications(
    type: str | None = Query(default=None, max_length=50),
    unreadOnly: bool = False,
    page: int = 1,
    pageSize: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    query = db.query(Notification).filter(Notification.user_id == user.id)
    if type:
        query = query.filter(Notification.type == type)
    if unreadOnly:
        query = query.filter(Notification.read_at.is_(None))
    query = query.order_by(Notification.created_at.desc())
    rows, meta = paginate(query, page, size)
    types = [
        {"value": value, "count": count}
        for value, count in db.query(Notification.type, __import__("sqlalchemy").func.count(Notification.id))
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .group_by(Notification.type)
        .all()
    ]
    return success({"items": [notification_public(row) for row in rows], "pagination": meta, "unreadByType": types})


@router.get("/notifications/unread-count")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.refresh(user)
    return success({"count": user.unread_count})


@router.patch("/notifications/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = utcnow()
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .update({Notification.read_at: now}, synchronize_session=False)
    )
    db.execute(update(User).where(User.id == user.id).values(unread_count=0))
    db.commit()
    cache.delete(f"notifications:unread:{user.id}:v1")
    return success({"updated": int(count)})


@router.patch("/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = db.get(Notification, notification_id)
    if not note:
        raise APIError(404, "通知不存在")
    if note.user_id != user.id:
        raise APIError(403, "无权操作他人的通知")
    if note.read_at is None:
        note.read_at = utcnow()
        db.execute(
            update(User)
            .where(User.id == user.id)
            .values(unread_count=__import__("sqlalchemy").case((User.unread_count > 0, User.unread_count - 1), else_=0))
        )
        db.commit()
        cache.delete(f"notifications:unread:{user.id}:v1")
    return success({"notification": notification_public(note)})


# ── 反馈工单 ─────────────────────────────────────────────────────────────
class FeedbackIn(BaseModel):
    type: Literal["bug", "feature", "experience", "other"] = "other"
    content: str = Field(min_length=5, max_length=3000)
    images: list[str] = Field(default_factory=list, max_length=3)
    contact: str | None = Field(default=None, max_length=255)


class SupplementIn(BaseModel):
    content: str = Field(min_length=2, max_length=1000)


def _ticket_no() -> str:
    return f"MW-{utcnow():%Y%m%d}-{random.randint(100000, 999999)}"


@router.post("/feedback")
def create_feedback(
    payload: FeedbackIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce(request, "feedback:create", limit=5, window_seconds=3600, discriminator=str(user.id))
    content = clean_text(payload.content, max_len=3000)
    if len(content) < 5:
        raise APIError(422, "请把问题描述得更具体一些")
    images = []
    for url in payload.images[:3]:
        if not url.startswith("/media/"):
            raise APIError(422, "截图地址必须来自本站附件")
        attachment = db.query(Attachment).filter(Attachment.owner_id == user.id, Attachment.url == url).first()
        if not attachment:
            raise APIError(422, "截图附件不存在或不属于当前用户")
        images.append({"url": url, "thumbUrl": attachment.thumb_url or url, "width": attachment.width, "height": attachment.height})
    ticket = _ticket_no()
    for _ in range(5):
        if not db.query(Feedback).filter(Feedback.ticket_no == ticket).first():
            break
        ticket = _ticket_no()
    row = Feedback(
        ticket_no=ticket,
        user_id=user.id,
        type=payload.type,
        content=content,
        images=images,
        contact=clean_text(payload.contact, max_len=255, keep_newlines=False),
        status="open",
        supplementary=[],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return success({"feedback": feedback_public(row)}, status_code=201)


@router.get("/users/me/feedback")
def my_feedback(
    page: int = 1,
    pageSize: int = 10,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    rows, meta = paginate(
        db.query(Feedback).filter(Feedback.user_id == user.id).order_by(Feedback.created_at.desc()),
        page,
        size,
    )
    return success({"items": [feedback_public(row) for row in rows], "pagination": meta})


@router.post("/feedback/{feedback_id}/supplement")
def supplement_feedback(
    feedback_id: int,
    payload: SupplementIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(Feedback).filter(Feedback.id == feedback_id, Feedback.user_id == user.id).first()
    if not row:
        found = db.get(Feedback, feedback_id)
        if found:
            raise APIError(403, "无权修改他人的反馈")
        raise APIError(404, "反馈不存在")
    if row.status == "closed":
        raise APIError(409, "工单已关闭，无法继续补充")
    items = list(row.supplementary or [])
    items.append({"content": clean_text(payload.content, max_len=1000), "createdAt": iso(utcnow())})
    row.supplementary = items
    db.commit()
    return success({"feedback": feedback_public(row)})


# ── 分享 ────────────────────────────────────────────────────────────────
class ShareIn(BaseModel):
    targetType: Literal["item"] = "item"
    targetId: int
    expiresInDays: int | None = Field(default=7, ge=1, le=30)


@router.post("/shares")
def create_share(
    payload: ShareIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce(request, "share:create", limit=30, window_seconds=3600, discriminator=str(user.id))
    item = db.query(Item).filter(Item.id == payload.targetId, Item.deleted_at.is_(None)).first()
    if not item:
        raise APIError(404, "分享目标不存在")
    if item.status != "published":
        raise APIError(409, "未发布或敏感内容不允许生成分享链接")
    code = short_code(10)
    while db.query(ShareLink).filter(ShareLink.code == code).first():
        code = short_code(10)
    row = ShareLink(
        code=code,
        target_type="item",
        target_id=str(item.id),
        created_by=user.id,
        expires_at=utcnow() + timedelta(days=payload.expiresInDays or 7) if payload.expiresInDays else None,
    )
    db.add(row)
    db.commit()
    url = f"{settings.public_base_url.rstrip('/')}/s/{code}"
    return success(
        {
            "code": code,
            "url": url,
            "expiresAt": iso(row.expires_at),
            "title": item.title,
        },
        status_code=201,
    )


def _resolve_share(db: Session, code: str) -> tuple[ShareLink, Item]:
    row = db.query(ShareLink).filter(ShareLink.code == code).first()
    if not row:
        raise APIError(404, "分享链接不存在")
    if row.expires_at and row.expires_at < utcnow():
        raise APIError(410, "分享链接已过期")
    item = db.query(Item).filter(Item.id == int(row.target_id), Item.deleted_at.is_(None)).first()
    if not item or item.status != "published":
        raise APIError(410, "分享内容已下线")
    db.execute(update(ShareLink).where(ShareLink.id == row.id).values(view_count=ShareLink.view_count + 1))
    db.commit()
    db.refresh(row)
    return row, item


@router.get("/shares/{code}")
def get_share(code: str, db: Session = Depends(get_db)):
    row, item = _resolve_share(db, code)
    return success(
        {
            "code": row.code,
            "title": item.title,
            "excerpt": (item.content or "")[:160],
            "coverUrl": item.cover_url,
            "itemId": item.id,
            "owner": {"nickname": item.owner.nickname if item.owner else "Moodwave 用户"},
            "expiresAt": iso(row.expires_at),
            "viewCount": row.view_count,
        }
    )


@share_router.get("/s/{code}", response_class=HTMLResponse)
def share_landing(code: str, db: Session = Depends(get_db)):
    try:
        row, item = _resolve_share(db, code)
    except APIError as exc:
        return HTMLResponse(
            f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>分享不可用 · Moodwave</title>"
            f"<body style='font-family:sans-serif;background:#FBFAF7;color:#1A1A1C;padding:12vh 8vw'>"
            f"<h1 style='font-size:32px'>分享不可用</h1><p style='color:#6B6B72'>{html.escape(exc.message)}</p></body></html>",
            status_code=exc.status_code,
        )
    image = item.cover_url or f"{settings.public_base_url.rstrip('/')}/media/banners/share-default.svg"
    if image.startswith("/"):
        image = settings.public_base_url.rstrip("/") + image
    target = f"{settings.frontend_origin.split(',')[0].rstrip('/')}/items/{item.id}"
    title = html.escape(item.title)
    description = html.escape((item.content or "让旋律回应此刻的表情")[:150])
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title} · Moodwave</title>
<meta name="description" content="{description}" />
<meta property="og:type" content="article" />
<meta property="og:site_name" content="Moodwave 心绪声场" />
<meta property="og:title" content="{title}" />
<meta property="og:description" content="{description}" />
<meta property="og:image" content="{html.escape(image)}" />
<meta property="og:url" content="{settings.public_base_url.rstrip('/')}/s/{row.code}" />
<meta name="twitter:card" content="summary_large_image" />
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0;background:#FBFAF7;color:#1A1A1C;font-family:Manrope,'PingFang SC','Microsoft YaHei',sans-serif; }}
  .glow {{ position:fixed;inset:-20% 30% 50% -20%;background:radial-gradient(circle,#5B5BD625,transparent 65%);pointer-events:none; }}
  main {{ max-width:760px;margin:0 auto;padding:9vh 24px;position:relative; }}
  .eyebrow {{ font:600 12px/1 'Space Grotesk',monospace;letter-spacing:.18em;color:#6B6B72;text-transform:uppercase; }}
  .card {{ background:#fff;border:1px solid #E7E4DC;border-radius:10px;overflow:hidden;margin-top:24px; }}
  .cover {{ width:100%;aspect-ratio:16/8;object-fit:cover;background:#EFEDE6;display:block; }}
  .body {{ padding:32px; }}
  h1 {{ font-size:clamp(28px,5vw,42px);line-height:1.2;margin:0 0 16px;font-family:'Space Grotesk','PingFang SC',sans-serif; }}
  p {{ color:#6B6B72;font-size:16px;line-height:1.7;margin:0 0 24px; }}
  a.btn {{ display:inline-block;background:#5B5BD6;color:#fff;text-decoration:none;padding:13px 20px;border-radius:10px;font-size:15px; }}
  footer {{ color:#9A9890;font-size:12px;margin-top:28px; }}
</style>
</head>
<body><div class="glow"></div><main>
  <div class="eyebrow">Moodwave · 心绪声场</div>
  <article class="card">
    <img class="cover" src="{html.escape(image)}" alt="{title}" width="1200" height="600" />
    <div class="body"><h1>{title}</h1><p>{description}</p><a class="btn" href="{target}">在 Moodwave 中打开</a></div>
  </article>
  <footer>分享码 {row.code} · 浏览 {row.view_count} 次 · 由 {html.escape(item.owner.nickname if item.owner else 'Moodwave 用户')} 分享</footer>
</main></body></html>"""
    return HTMLResponse(page)


# ── 运营位 ──────────────────────────────────────────────────────────────
@router.get("/banners")
def get_banners(
    position: str = Query(default="home", pattern="^(home|discover|settings)$"),
    db: Session = Depends(get_db),
):
    cache_key = f"banners:{position}:v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return success({"items": cached})
    now = utcnow()
    rows = (
        db.query(Banner)
        .filter(
            Banner.position_code == position,
            Banner.status == "active",
            (Banner.start_at.is_(None) | (Banner.start_at <= now)),
            (Banner.end_at.is_(None) | (Banner.end_at >= now)),
        )
        .order_by(Banner.sort.asc(), Banner.id.desc())
        .limit(MAX_BANNERS[position])
        .all()
    )
    items = [banner_public(row) for row in rows]
    cache.set(cache_key, items, 60)
    return success({"items": items})


# ── 客户端错误上报 ──────────────────────────────────────────────────────
class ClientLogIn(BaseModel):
    level: Literal["info", "warn", "error"] = "error"
    message: str = Field(min_length=1, max_length=1000)
    stack: str | None = Field(default=None, max_length=8000)
    route: str | None = Field(default=None, max_length=255)
    requestId: str | None = Field(default=None, max_length=64)
    context: dict | None = None


@router.post("/logs/client")
def client_log(
    payload: ClientLogIn,
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    enforce(request, "logs:client", limit=60, window_seconds=60)
    row = ClientLog(
        user_id=user.id if user else None,
        level=payload.level,
        message=clean_text(payload.message, max_len=1000),
        stack=payload.stack[-8000:] if payload.stack else None,
        route=payload.route,
        user_agent=request.headers.get("user-agent", "")[:500],
        request_id=payload.requestId or getattr(request.state, "request_id", None),
        context=payload.context or {},
    )
    db.add(row)
    db.commit()
    level = "error" if payload.level == "error" else "warning"
    getattr(logger, level)(
        "client_error",
        extra={
            "requestId": row.request_id,
            "userId": row.user_id,
            "context": {"route": row.route, "message": row.message, "stack": (row.stack or "")[:1500]},
        },
    )
    return success({"accepted": True})


# ── i18n / 元信息 ───────────────────────────────────────────────────────
@router.get("/i18n/{locale}")
def get_i18n(locale: str):
    safe_locale = locale if locale in {"zh-CN", "en-US"} else "zh-CN"
    path = Path(__file__).resolve().parents[1] / "locales" / f"{safe_locale}.json"
    if not path.exists():
        raise APIError(404, "语言包不存在")
    import json

    return success({"locale": safe_locale, "messages": json.loads(path.read_text(encoding="utf-8"))})


@router.get("/meta")
def meta():
    return success(
        {
            "appName": settings.app_name,
            "environment": settings.app_env,
            "registrationRequireInvite": settings.registration_require_invite,
            "registrationRequireApproval": settings.registration_require_approval,
            "oauthProviders": [
                {"code": "github", "name": "GitHub", "enabled": bool(settings.github_client_id)},
                {"code": "google", "name": "Google", "enabled": bool(settings.google_client_id)},
                {"code": "wechat", "name": "微信", "enabled": bool(settings.wechat_app_id)},
            ],
            "onlineMusic": settings.enable_online_music,
            "locales": ["zh-CN", "en-US"],
            "maxImageMb": settings.max_image_mb,
            "debug": settings.debug,
        }
    )


# ── 健康检查 ────────────────────────────────────────────────────────────
health_router = APIRouter(tags=["health"])


@health_router.get("/healthz")
def healthz():
    db_ok = healthcheck_database()
    try:
        from ..services.emotion import engine

        emotion_status = engine.status()
    except Exception as exc:
        emotion_status = {"engine": "unavailable", "error": str(exc)[:120]}
    return success(
        {
            "status": "ok" if db_ok else "degraded",
            "database": "ok" if db_ok else "down",
            "emotion": emotion_status,
            "cache": cache.stats(),
            "time": iso(utcnow()),
            "version": "1.0.0",
        }
    )
