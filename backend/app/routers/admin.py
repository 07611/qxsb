"""管理后台：用户/角色、审核、邀请码、工单、邮件、推送、运营位、审计。"""

from __future__ import annotations

import logging
import secrets
import time as time_module
from datetime import datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..errors import APIError, success
from ..models import (
    AuditLog,
    Banner,
    Category,
    ClientLog,
    EmailLog,
    Event,
    Feedback,
    Item,
    InviteCode,
    PushChannel,
    PushTask,
    Role,
    Tag,
    Track,
    User,
    UserPushSetting,
    UserRole,
    utcnow,
)
from ..security import get_current_user, has_permission, require_permission
from ..serializers import banner_public, feedback_public, user_admin
from ..services.cache import cache
from ..services.mailer import enqueue_email, send_test_email
from ..services.notify import create_notification
from ..services.ratelimit import enforce, get_client_ip
from ..utils import clean_text, iso, page_params, paginate, parse_datetime, safe_link, short_code

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
logger = logging.getLogger("moodwave.admin")

ROLE_PERMISSIONS = {
    "admin": ["*", "admin:access"],
    "editor": ["admin:access", "content:manage", "categories:manage", "reports:view"],
    "user": ["content:read", "content:write", "profile:write", "feedback:write"],
}


def write_audit(
    db: Session,
    actor: User,
    action: str,
    target_type: str,
    target_id: str | int,
    detail: dict | None = None,
    request: Request | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor.id,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            detail=detail or {},
            ip=get_client_ip(request)[:64] if request else "",
        )
    )


# ── 概览 ────────────────────────────────────────────────────────────────
@router.get("/stats")
def admin_stats(admin: User = Depends(require_permission("admin:access")), db: Session = Depends(get_db)):
    cached = cache.get("admin:stats:v1")
    if cached is not None:
        return success(cached)
    now = utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.status == "active").count()
    pending_users = db.query(User).filter(User.status == "pending").count()
    total_items = db.query(Item).filter(Item.deleted_at.is_(None)).count()
    published_items = db.query(Item).filter(Item.deleted_at.is_(None), Item.status == "published").count()
    total_tracks = db.query(Track).count()
    open_feedback = db.query(Feedback).filter(Feedback.status.in_(["open", "processing"])).count()
    emotion_rows = (
        db.query(Event.event_key, func.count(Event.id))
        .filter(Event.event_key.like("emotion_%"))
        .group_by(Event.event_key)
        .all()
    )
    recent_feedback = db.query(Feedback).order_by(Feedback.created_at.desc()).limit(4).all()
    recent_errors = db.query(ClientLog).filter(ClientLog.level == "error").order_by(ClientLog.created_at.desc()).limit(3).all()
    signup_series = []
    for offset in range(6, -1, -1):
        day = today_start - timedelta(days=offset)
        count = db.query(User).filter(User.created_at >= day, User.created_at < day + timedelta(days=1)).count()
        signup_series.append({"date": day.date().isoformat(), "users": count})
    payload = {
        "users": {"total": total_users, "active": active_users, "pending": pending_users},
        "content": {"items": total_items, "published": published_items, "tracks": total_tracks},
        "feedback": {"open": open_feedback},
        "emotions": [{"key": key.replace("emotion_", ""), "count": count} for key, count in emotion_rows],
        "signupSeries": signup_series,
        "recentFeedback": [feedback_public(row, admin=True) for row in recent_feedback],
        "recentErrors": [
            {"id": row.id, "message": row.message, "route": row.route, "level": row.level, "createdAt": iso(row.created_at)}
            for row in recent_errors
        ],
        "cache": cache.stats(),
        "generatedAt": iso(now),
    }
    cache.set("admin:stats:v1", payload, 20)
    return success(payload)


# ── 用户与角色 ──────────────────────────────────────────────────────────
@router.get("/users")
def admin_users(
    q: str | None = Query(default=None, max_length=50),
    role: str | None = None,
    status: str | None = None,
    page: int = 1,
    pageSize: int = 20,
    sort: str = Query(default="newest", pattern="^(newest|oldest|email)$"),
    admin: User = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    query = db.query(User)
    if q:
        like = f"%{clean_text(q, max_len=50, keep_newlines=False)}%"
        query = query.filter(or_(User.email.like(like), User.nickname.like(like)))
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)
    if sort == "oldest":
        query = query.order_by(User.created_at.asc())
    elif sort == "email":
        query = query.order_by(User.email.asc())
    else:
        query = query.order_by(User.created_at.desc())
    rows, meta = paginate(query, page, size)
    return success({"items": [user_admin(row) for row in rows], "pagination": meta})


class RolePatch(BaseModel):
    role: Literal["admin", "editor", "user"]


@router.patch("/users/{user_id}/role")
def change_role(
    user_id: int,
    payload: RolePatch,
    request: Request,
    admin: User = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise APIError(404, "用户不存在")
    if user.id == admin.id and payload.role != "admin":
        raise APIError(400, "不能移除自己的管理员角色")
    if user.role == "admin" and payload.role != "admin":
        admin_count = (
            db.query(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .filter(Role.code == "admin")
            .count()
        )
        if admin_count <= 1:
            raise APIError(409, "系统必须保留至少一名管理员")
    role = db.query(Role).filter(Role.code == payload.role).first()
    if not role:
        role = Role(
            name={"admin": "管理员", "editor": "内容编辑", "user": "普通用户"}[payload.role],
            code=payload.role,
            permissions=ROLE_PERMISSIONS[payload.role],
        )
        db.add(role)
        db.flush()
    db.query(UserRole).filter(UserRole.user_id == user.id).delete(synchronize_session=False)
    db.add(UserRole(user_id=user.id, role_id=role.id, granted_at=utcnow()))
    user.role = payload.role
    write_audit(db, admin, "user.role.change", "user", user.id, {"from": user.role, "to": payload.role}, request)
    create_notification(
        db,
        user_id=user.id,
        type="system",
        title="账号角色已变更",
        message=f"你的账号角色已被管理员调整为「{role.name}」，新权限立即生效。",
        target_type="role",
        target_id=str(int(utcnow().timestamp())),
    )
    db.commit()
    cache.delete_prefix("admin:stats")
    return success({"user": user_admin(user)})


class ApproveIn(BaseModel):
    approved: bool = True
    reason: str | None = Field(default=None, max_length=200)


@router.patch("/users/{user_id}/approve")
def approve_user(
    user_id: int,
    payload: ApproveIn,
    request: Request,
    admin: User = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise APIError(404, "用户不存在")
    if user.status != "pending":
        raise APIError(409, "该用户不处于待审核状态")
    if payload.approved:
        user.status = "active"
        user.disabled_reason = None
        create_notification(
            db,
            user_id=user.id,
            type="approval",
            title="账号审核通过",
            message="你的账号已通过审核，现在可以创建内容并获得完整推荐体验。",
            target_type="approval",
            target_id=str(int(utcnow().timestamp())),
        )
    else:
        user.status = "disabled"
        user.disabled_reason = clean_text(payload.reason, max_len=200) or "审核未通过"
    write_audit(db, admin, "user.approve" if payload.approved else "user.reject", "user", user.id, {"approved": payload.approved, "reason": user.disabled_reason}, request)
    db.commit()
    cache.delete_prefix("admin:stats")
    return success({"user": user_admin(user)})


# ── 邀请码 ──────────────────────────────────────────────────────────────
class InviteIn(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    expiresInDays: int = Field(default=7, ge=1, le=90)
    count: int = Field(default=1, ge=1, le=20)


@router.get("/invite-codes")
def invite_codes(admin: User = Depends(require_permission("users:manage")), db: Session = Depends(get_db)):
    rows = db.query(InviteCode).order_by(InviteCode.created_at.desc()).limit(100).all()
    return success(
        {
            "items": [
                {
                    "id": row.id,
                    "code": row.code,
                    "usedBy": row.used_by,
                    "consumed": row.consumed_at is not None,
                    "consumedAt": iso(row.consumed_at),
                    "expiresAt": iso(row.expires_at),
                    "createdAt": iso(row.created_at),
                }
                for row in rows
            ]
        }
    )


@router.post("/invite-codes")
def create_invite_codes(
    payload: InviteIn,
    request: Request,
    admin: User = Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
):
    created = []
    for index in range(payload.count):
        code = (payload.code if payload.count == 1 and payload.code else f"MW-{short_code(8).upper()}")
        if db.query(InviteCode).filter(InviteCode.code == code).first():
            raise APIError(409, f"邀请码 {code} 已存在")
        row = InviteCode(
            code=code,
            created_by=admin.id,
            expires_at=utcnow() + timedelta(days=payload.expiresInDays),
        )
        db.add(row)
        created.append(code)
    write_audit(db, admin, "invite.create", "invite", ",".join(created), {"count": payload.count}, request)
    db.commit()
    return success({"codes": created}, status_code=201)


# ── 工单 ────────────────────────────────────────────────────────────────
@router.get("/feedback")
def admin_feedback(
    status: str | None = None,
    q: str | None = Query(default=None, max_length=50),
    page: int = 1,
    pageSize: int = 20,
    admin: User = Depends(require_permission("feedback:manage")),
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    query = db.query(Feedback)
    if status:
        query = query.filter(Feedback.status == status)
    if q:
        like = f"%{clean_text(q, max_len=50, keep_newlines=False)}%"
        query = query.filter(or_(Feedback.ticket_no.like(like), Feedback.content.like(like)))
    rows, meta = paginate(query.order_by(Feedback.created_at.desc()), page, size)
    return success(
        {
            "items": [feedback_public(row, admin=True) for row in rows],
            "pagination": meta,
            "summary": {
                "open": db.query(Feedback).filter(Feedback.status == "open").count(),
                "processing": db.query(Feedback).filter(Feedback.status == "processing").count(),
                "resolved": db.query(Feedback).filter(Feedback.status == "resolved").count(),
                "closed": db.query(Feedback).filter(Feedback.status == "closed").count(),
            },
        }
    )


class FeedbackReplyIn(BaseModel):
    status: Literal["processing", "resolved", "closed"] | None = None
    reply: str | None = Field(default=None, max_length=3000)


@router.patch("/feedback/{feedback_id}")
def reply_feedback(
    feedback_id: int,
    payload: FeedbackReplyIn,
    request: Request,
    admin: User = Depends(require_permission("feedback:manage")),
    db: Session = Depends(get_db),
):
    row = db.get(Feedback, feedback_id)
    if not row:
        raise APIError(404, "工单不存在")
    allowed = {"open": {"processing", "resolved", "closed"}, "processing": {"resolved", "closed"}, "resolved": {"closed"}, "closed": set()}
    if payload.status and payload.status != row.status:
        if payload.status not in allowed.get(row.status, set()):
            raise APIError(409, f"工单状态不能从 {row.status} 变为 {payload.status}")
        row.status = payload.status
    if payload.reply is not None:
        row.reply = clean_text(payload.reply, max_len=3000)
        row.handler_id = admin.id
    row.handler_id = admin.id
    user = db.get(User, row.user_id)
    if payload.reply and user:
        create_notification(
            db,
            user_id=user.id,
            type="feedback",
            title=f"工单 {row.ticket_no} 有新回复",
            message=row.reply[:180],
            target_type="feedback",
            target_id=str(row.id),
        )
        if user.email:
            enqueue_email(
                db,
                to_email=user.email,
                template="feedback_reply.html",
                subject=f"工单 {row.ticket_no} 有新回复",
                context={"nickname": user.nickname, "ticketNo": row.ticket_no, "reply": row.reply, "sentAt": iso(utcnow())},
                user=user,
            )
    write_audit(db, admin, "feedback.reply", "feedback", row.id, {"status": row.status}, request)
    db.commit()
    return success({"feedback": feedback_public(row, admin=True)})


# ── 邮件 ────────────────────────────────────────────────────────────────
class EmailTestIn(BaseModel):
    to: str = Field(min_length=3, max_length=255)


@router.post("/emails/test")
def email_test(
    payload: EmailTestIn,
    request: Request,
    admin: User = Depends(require_permission("admin:access")),
    db: Session = Depends(get_db),
):
    enforce(request, "admin:email:test", limit=10, window_seconds=3600, discriminator=str(admin.id))
    import re

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", payload.to):
        raise APIError(422, "请输入有效邮箱")
    log = send_test_email(db, admin, payload.to)
    write_audit(db, admin, "email.test", "email", log.id if log else "throttled", {"to": payload.to}, request)
    db.commit()
    return success({"queued": bool(log), "logId": log.id if log else None, "smtpConfigured": bool(settings.smtp_host)})


@router.get("/emails")
def email_logs(
    page: int = 1,
    pageSize: int = 20,
    admin: User = Depends(require_permission("admin:access")),
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    rows, meta = paginate(db.query(EmailLog).order_by(EmailLog.created_at.desc()), page, size)
    return success(
        {
            "items": [
                {
                    "id": row.id,
                    "toEmail": row.to_email,
                    "template": row.template,
                    "subject": row.subject,
                    "status": row.status,
                    "retryCount": row.retry_count,
                    "sentAt": iso(row.sent_at),
                    "error": row.error_message,
                    "createdAt": iso(row.created_at),
                }
                for row in rows
            ],
            "pagination": meta,
            "smtpConfigured": bool(settings.smtp_host),
        }
    )


@router.get("/emails/{email_id}/outbox", response_class=HTMLResponse)
def email_outbox(
    email_id: int,
    admin: User = Depends(require_permission("admin:access")),
    db: Session = Depends(get_db),
):
    row = db.get(EmailLog, email_id)
    if not row:
        raise APIError(404, "邮件记录不存在")
    path = settings.logs_dir / "email-outbox" / f"{email_id:06d}.html"
    if path.exists():
        return HTMLResponse(path.read_text(encoding="utf-8"))
    if not settings.smtp_host:
        return HTMLResponse("<p>outbox 尚未生成，请确认后台邮件线程已经执行。</p>")
    return HTMLResponse("<p>该邮件已通过 SMTP 发送，不保留网页副本。</p>")


# ── 推送 ────────────────────────────────────────────────────────────────
PUSH_TEMPLATES = {
    "system_notice": {"title": "系统公告", "body": "{{content}}", "marketing": False},
    "feature_update": {"title": "新功能上线", "body": "{{content}}", "marketing": False},
    "weekly_pick": {"title": "本周情绪歌单", "body": "{{content}}", "marketing": True},
}
PUSH_CHANNELS = {"inapp", "email", "sms", "push"}


class PushIn(BaseModel):
    templateCode: Literal["system_notice", "feature_update", "weekly_pick"]
    content: str = Field(min_length=2, max_length=500)
    userIds: list[int] = Field(default_factory=list, max_length=200)
    channels: list[str] = Field(default_factory=lambda: ["inapp"], max_length=4)
    marketing: bool = False


def _webhook_with_retry(url: str, payload: dict) -> tuple[bool, str]:
    """外部推送/短信通道：最多 3 次指数退避，失败后标记放弃并返回错误。"""
    last_error = ""
    for attempt in range(1, 4):
        try:
            response = httpx.post(url, json=payload, timeout=6)
            response.raise_for_status()
            return True, ""
        except Exception as exc:  # pragma: no cover - 外部通道
            last_error = str(exc)[:300]
            logger.warning("push_delivery_failed url=%s attempt=%s error=%s", url, attempt, last_error)
            if attempt < 3:
                time_module.sleep(0.25 * attempt)
    return False, last_error


@router.post("/push/send")
def send_push(
    payload: PushIn,
    request: Request,
    admin: User = Depends(require_permission("admin:access")),
    db: Session = Depends(get_db),
):
    enforce(request, "admin:push", limit=20, window_seconds=3600, discriminator=str(admin.id))
    template = PUSH_TEMPLATES[payload.templateCode]
    content = clean_text(payload.content, max_len=500)
    if not content:
        raise APIError(422, "推送内容不能为空")
    channels = [channel for channel in payload.channels if channel in PUSH_CHANNELS]
    if not channels:
        raise APIError(422, "请选择至少一个推送渠道")
    is_marketing = payload.marketing or template["marketing"]
    local_now = datetime.now(ZoneInfo("Asia/Shanghai")).time()
    if is_marketing and (local_now < time(8, 0) or local_now >= time(22, 0)):
        raise APIError(422, "营销类消息在 22:00–08:00 不推送，请调整发送时间")
    if payload.userIds:
        users = db.query(User).filter(User.id.in_(payload.userIds), User.status == "active").all()
    else:
        users = db.query(User).filter(User.status == "active").limit(200).all()
    if not users:
        raise APIError(404, "没有可触达的用户")
    day_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    settings_map = {
        (row.user_id, row.channel_code): row
        for row in db.query(UserPushSetting).filter(UserPushSetting.user_id.in_([user.id for user in users])).all()
    }
    created = 0
    skipped = 0
    delivered = 0
    for user in users:
        sent_today = (
            db.query(PushTask)
            .filter(
                PushTask.user_id == user.id,
                PushTask.template_code == payload.templateCode,
                PushTask.created_at >= day_start,
            )
            .count()
        )
        if sent_today >= 5:
            skipped += len(channels)
            continue
        for channel in channels:
            pref = settings_map.get((user.id, channel))
            enabled = pref.enabled if pref else channel in {"inapp", "email"}
            if not enabled:
                skipped += 1
                continue
            if channel == "inapp":
                create_notification(
                    db,
                    user_id=user.id,
                    type="push",
                    title=template["title"],
                    message=content,
                    target_type="push",
                    target_id=f"{payload.templateCode}-{int(utcnow().timestamp())}-{user.id}",
                )
            elif channel == "email" and user.email:
                enqueue_email(
                    db,
                    to_email=user.email,
                    template="push_notice.html",
                    subject=template["title"],
                    context={
                        "nickname": user.nickname,
                        "title": template["title"],
                        "content": content,
                        "appUrl": settings.frontend_origin.split(",")[0],
                    },
                    user=user,
                    force=True,
                )
            task_status = "sent"
            error_message = None
            if channel == "sms":
                if settings.sms_webhook_url:
                    ok, error_message = _webhook_with_retry(settings.sms_webhook_url, {"phone": user.phone, "content": content})
                    task_status = "sent" if ok else "failed"
                else:
                    db.add(
                        SmsLog(
                            phone=(user.phone or "unbound"),
                            scene="admin_push",
                            template_id=payload.templateCode,
                            status="simulated",
                            error_message=None,
                            sent_at=utcnow(),
                            ip=get_client_ip(request)[:64],
                        )
                    )
            elif channel == "push":
                if settings.push_webhook_url:
                    ok, error_message = _webhook_with_retry(
                        settings.push_webhook_url,
                        {"userId": user.id, "title": template["title"], "body": content, "template": payload.templateCode},
                    )
                    task_status = "sent" if ok else "failed"
                else:
                    task_status = "simulated"
            elif channel == "email":
                task_status = "queued"
            ok = task_status not in {"failed", "skipped"}
            task = PushTask(
                user_id=user.id,
                channel_code=channel,
                template_code=payload.templateCode,
                payload={"content": content, "title": template["title"]},
                status=task_status,
                sent_at=utcnow() if ok else None,
                error_message=error_message,
                is_marketing=is_marketing,
            )
            db.add(task)
            created += 1
            if ok:
                delivered += 1
    write_audit(db, admin, "push.send", "push", payload.templateCode, {"users": len(users), "channels": channels, "delivered": delivered, "skipped": skipped}, request)
    db.commit()
    return success({"targetUsers": len(users), "tasksCreated": created, "delivered": delivered, "skipped": skipped, "channels": channels})


@router.get("/push/channels")
def push_channels(admin: User = Depends(require_permission("admin:access")), db: Session = Depends(get_db)):
    rows = db.query(PushChannel).all()
    return success(
        {
            "items": [
                {
                    "code": row.code,
                    "name": row.name,
                    "provider": row.provider,
                    "status": row.status,
                    "configured": row.provider in {"internal", "smtp"} or bool(settings.smtp_host),
                }
                for row in rows
            ]
        }
    )


# ── 运营位 ──────────────────────────────────────────────────────────────
POSITION_MAP = {"home": 0, "discover": 1, "settings": 2}


class BannerIn(BaseModel):
    position: Literal["home", "discover", "settings"] = "home"
    title: str = Field(min_length=2, max_length=80)
    subtitle: str | None = Field(default=None, max_length=160)
    imageUrl: str = Field(min_length=5, max_length=500)
    linkUrl: str | None = Field(default=None, max_length=500)
    sort: int = 0
    startAt: datetime | None = None
    endAt: datetime | None = None
    status: Literal["active", "inactive"] = "active"
    aspectRatio: str = "16/5"


def _banner_validate(payload: BannerIn) -> tuple[str, str | None]:
    image = payload.imageUrl.strip()
    if not (image.startswith("/media/") or image.startswith("https://")):
        raise APIError(422, "运营图必须来自本站媒体或 HTTPS 资源")
    link = safe_link(payload.linkUrl)
    if payload.linkUrl and not link:
        raise APIError(422, "跳转链接不在白名单内")
    if payload.startAt and payload.endAt and payload.startAt >= payload.endAt:
        raise APIError(422, "结束时间必须晚于开始时间")
    return image, link


@router.get("/banners")
def all_banners(admin: User = Depends(require_permission("admin:access")), db: Session = Depends(get_db)):
    rows = db.query(Banner).order_by(Banner.position.asc(), Banner.sort.asc()).all()
    return success({"items": [banner_public(row) for row in rows], "maxPerPosition": {"home": 3, "discover": 2, "settings": 1}})


@router.post("/banners")
def create_banner(
    payload: BannerIn,
    request: Request,
    admin: User = Depends(require_permission("admin:access")),
    db: Session = Depends(get_db),
):
    image, link = _banner_validate(payload)
    row = Banner(
        position=POSITION_MAP[payload.position],
        position_code=payload.position,
        title=clean_text(payload.title, max_len=80, keep_newlines=False),
        subtitle=clean_text(payload.subtitle, max_len=160),
        image_url=image,
        link_url=link,
        sort=payload.sort,
        start_at=payload.startAt.replace(tzinfo=None) if payload.startAt and payload.startAt.tzinfo else payload.startAt,
        end_at=payload.endAt.replace(tzinfo=None) if payload.endAt and payload.endAt.tzinfo else payload.endAt,
        status=payload.status,
        aspect_ratio=payload.aspectRatio,
    )
    db.add(row)
    db.flush()
    write_audit(db, admin, "banner.create", "banner", row.id, {"title": row.title}, request)
    db.commit()
    cache.delete_prefix("banners:")
    return success({"banner": banner_public(row)}, status_code=201)


@router.patch("/banners/{banner_id}")
def update_banner(
    banner_id: int,
    payload: BannerIn,
    request: Request,
    admin: User = Depends(require_permission("admin:access")),
    db: Session = Depends(get_db),
):
    row = db.get(Banner, banner_id)
    if not row:
        raise APIError(404, "运营位不存在")
    image, link = _banner_validate(payload)
    row.position = POSITION_MAP[payload.position]
    row.position_code = payload.position
    row.title = clean_text(payload.title, max_len=80, keep_newlines=False)
    row.subtitle = clean_text(payload.subtitle, max_len=160)
    row.image_url = image
    row.link_url = link
    row.sort = payload.sort
    row.start_at = payload.startAt
    row.end_at = payload.endAt
    row.status = payload.status
    row.aspect_ratio = payload.aspectRatio
    write_audit(db, admin, "banner.update", "banner", row.id, {"title": row.title}, request)
    db.commit()
    cache.delete_prefix("banners:")
    return success({"banner": banner_public(row)})


@router.delete("/banners/{banner_id}")
def delete_banner(
    banner_id: int,
    request: Request,
    admin: User = Depends(require_permission("admin:access")),
    db: Session = Depends(get_db),
):
    row = db.get(Banner, banner_id)
    if not row:
        raise APIError(404, "运营位不存在")
    write_audit(db, admin, "banner.delete", "banner", row.id, {"title": row.title}, request)
    db.delete(row)
    db.commit()
    cache.delete_prefix("banners:")
    return success({"deleted": True})


# ── 可观测与审计 ────────────────────────────────────────────────────────
@router.get("/audit-logs")
def audit_logs(
    page: int = 1,
    pageSize: int = 20,
    admin: User = Depends(require_permission("admin:access")),
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    rows, meta = paginate(db.query(AuditLog).order_by(AuditLog.created_at.desc()), page, size)
    return success(
        {
            "items": [
                {
                    "id": row.id,
                    "actorId": row.actor_id,
                    "action": row.action,
                    "targetType": row.target_type,
                    "targetId": row.target_id,
                    "detail": row.detail,
                    "ip": row.ip[:8] + "***" if row.ip else "",
                    "createdAt": iso(row.created_at),
                }
                for row in rows
            ],
            "pagination": meta,
        }
    )


@router.get("/client-errors")
def client_errors(
    page: int = 1,
    pageSize: int = 20,
    admin: User = Depends(require_permission("admin:access")),
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    rows, meta = paginate(
        db.query(ClientLog).filter(ClientLog.level == "error").order_by(ClientLog.created_at.desc()),
        page,
        size,
    )
    return success(
        {
            "items": [
                {
                    "id": row.id,
                    "message": row.message,
                    "route": row.route,
                    "stack": row.stack,
                    "requestId": row.request_id,
                    "createdAt": iso(row.created_at),
                }
                for row in rows
            ],
            "pagination": meta,
        }
    )
