"""认证：注册、登录锁定、刷新令牌轮换、验证码、找回密码、OAuth、会话管理。"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx
import jwt
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..errors import APIError, success
from ..models import (
    InviteCode,
    OAuthAccount,
    OAuthState,
    PasswordReset,
    RefreshToken,
    Role,
    SmsLog,
    User,
    UserRole,
    VerifyCode,
    utcnow,
)
from ..security import (
    REFRESH_COOKIE,
    clear_refresh_cookie,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    find_valid_refresh_token,
    get_current_user,
    get_optional_user,
    hash_password,
    password_strength_error,
    revoke_all_sessions,
    set_refresh_cookie,
    verify_password,
)
from ..serializers import user_public
from ..services.mailer import enqueue_email
from ..services.ratelimit import enforce, enforce_for_user, get_client_ip
from ..services.notify import create_notification
from ..utils import hash_token, iso, mask_ip, numeric_code, short_code, utcnow as now_utc

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger("moodwave.auth")

PHONE_RE = r"^\+?[0-9]{6,20}$"
ALLOWED_SCENES = {"register", "login", "reset", "change_contact", "verify_email"}


# ── Schemas ─────────────────────────────────────────────────────────────
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    nickname: str = Field(min_length=2, max_length=20)
    locale: str = "zh-CN"
    inviteCode: str | None = None
    verificationToken: str | None = None

    @field_validator("nickname")
    @classmethod
    def nickname_clean(cls, value: str) -> str:
        value = value.strip()
        if value.startswith("<") or ">" in value:
            raise ValueError("昵称不能包含 HTML 标签")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str | None = None


class LogoutIn(BaseModel):
    refresh_token: str | None = None


class CodeSendIn(BaseModel):
    target: str = Field(min_length=3, max_length=255)
    scene: Literal["register", "login", "reset", "change_contact", "verify_email"]
    channel: Literal["email", "sms"] = "email"


class CodeVerifyIn(BaseModel):
    target: str
    scene: Literal["register", "login", "reset", "change_contact", "verify_email"]
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=20)
    newPassword: str = Field(min_length=8, max_length=64)


# ── Helpers ─────────────────────────────────────────────────────────────
def _default_role(db: Session) -> Role:
    role = db.query(Role).filter(Role.code == "user").first()
    if not role:
        role = Role(name="普通用户", code="user", permissions=["content:read", "content:write"], description="默认角色")
        db.add(role)
        db.flush()
    return role


def _ensure_nickname(db: Session, nickname: str) -> str:
    candidate = nickname
    if db.query(User).filter(User.nickname == candidate).first():
        candidate = f"{nickname[:14]}-{secrets.token_hex(2)}"
    return candidate[:20]


def _issue_session(db: Session, user: User, request: Request | None = None) -> dict:
    access_token, expires_in = create_access_token(user)
    raw_refresh, _row = create_refresh_token(db, user, request)
    db.commit()
    return {
        "accessToken": access_token,
        "refreshToken": raw_refresh,
        "tokenType": "Bearer",
        "expiresIn": expires_in,
        "refreshExpiresIn": settings.refresh_token_expire_days * 86400,
        "user": user_public(user, self_view=True),
    }


def _auth_response(payload: dict) -> JSONResponse:
    response = JSONResponse({"code": 0, "message": "ok", "data": payload})
    set_refresh_cookie(response, payload["refreshToken"])
    return response


def _normalize_target(target: str, channel: str) -> str:
    if channel == "email":
        normalized = target.strip().lower()
        if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
            raise APIError(422, "请输入有效邮箱")
        return normalized
    import re

    normalized = target.strip()
    if not re.match(PHONE_RE, normalized):
        raise APIError(422, "请输入有效手机号")
    return normalized


def _code_digest(target: str, scene: str, code: str) -> str:
    # 6 位数字空间小，必须用服务端密钥做 HMAC，禁止裸 SHA256 落库
    return hmac.new(settings.jwt_secret.encode(), f"{target}:{scene}:{code}".encode(), hashlib.sha256).hexdigest()


def _create_verification_token(target: str, scene: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": target,
        "scene": scene,
        "type": "verification",
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "iat": int(now.timestamp()),
        "iss": "moodwave",
        "aud": "moodwave-web",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _validate_registration_token(token: str | None, email: str) -> None:
    if not token:
        return
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience="moodwave-web",
            issuer="moodwave",
        )
    except jwt.InvalidTokenError as exc:
        raise APIError(422, "邮箱验证凭证无效或已过期") from exc
    if payload.get("type") != "verification" or payload.get("sub") != email.lower():
        raise APIError(422, "邮箱验证凭证与注册邮箱不一致")


# ── Register / Login ────────────────────────────────────────────────────
@router.post("/register")
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    enforce(request, "auth:register", limit=8, window_seconds=3600)
    error = password_strength_error(payload.password)
    if error:
        raise APIError(422, "密码不符合要求", data={"errors": [{"field": "password", "message": error}]})
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise APIError(409, "该邮箱已注册，请直接登录")
    if db.query(User).filter(User.nickname == payload.nickname).first():
        raise APIError(409, "该昵称已被使用，请换一个")
    _validate_registration_token(payload.verificationToken, email)

    invite: InviteCode | None = None
    if settings.registration_require_invite:
        if not payload.inviteCode:
            raise APIError(422, "当前为邀请制注册，请填写邀请码")
        invite = db.query(InviteCode).filter(InviteCode.code == payload.inviteCode.strip()).first()
        if not invite or invite.consumed_at is not None:
            raise APIError(422, "邀请码无效或已被使用")
        if invite.expires_at and invite.expires_at < utcnow():
            raise APIError(422, "邀请码已过期")

    status = "pending" if (settings.registration_require_approval or settings.registration_require_invite) else "active"
    role = _default_role(db)
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname,
        role="user",
        status=status,
        locale=payload.locale if payload.locale in {"zh-CN", "en-US"} else "zh-CN",
        email_verified=bool(payload.verificationToken),
        avatar_url=None,
    )
    db.add(user)
    try:
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id, granted_at=utcnow()))
        if invite:
            invite.used_by = user.id
            invite.consumed_at = utcnow()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIError(409, "该邮箱或昵称已被占用") from exc
    db.refresh(user)
    enqueue_email(
        db,
        to_email=user.email,
        template="welcome.html",
        subject="欢迎来到 Moodwave 心绪声场",
        context={"nickname": user.nickname, "appUrl": settings.frontend_origin.split(",")[0], "sentAt": iso(utcnow())},
        user=user,
        force=True,
    )
    session = _issue_session(db, user, request)
    session["requiresApproval"] = status == "pending"
    return _auth_response(session)


@router.post("/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    enforce(request, "auth:login:ip", limit=30, window_seconds=60)
    email = payload.email.lower()
    enforce(request, "auth:login:account", limit=20, window_seconds=300, discriminator=email)

    user = db.query(User).filter(User.email == email).first()
    if user and user.locked_until and user.locked_until > utcnow():
        retry = max(1, int((user.locked_until - utcnow()).total_seconds()))
        raise APIError(
            429,
            "登录失败次数过多，请稍后再试",
            data={"retryAfter": retry},
            headers={"Retry-After": str(retry)},
        )
    if not user:
        # 固定时间比较，避免通过响应时间枚举账号
        verify_password(payload.password, "$2b$12$C6UzMDM.H6dfI/f/IKcEe.5S9XkY7.Rn7hW7VQKxYhF6gR0yqf3nO")
        raise APIError(401, "邮箱或密码错误")
    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = utcnow() + timedelta(minutes=15)
            user.failed_login_attempts = 0
            db.commit()
            retry = 15 * 60
            raise APIError(
                429,
                "连续登录失败 5 次，账号已锁定 15 分钟",
                data={"retryAfter": retry},
                headers={"Retry-After": str(retry)},
            )
        db.commit()
        raise APIError(401, "邮箱或密码错误")

    if user.status == "disabled":
        raise APIError(403, "账号已停用，请联系管理员")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    session = _issue_session(db, user, request)
    create_notification(
        db,
        user_id=user.id,
        type="security",
        title="新设备登录",
        message=f"你的账号刚刚在 {mask_ip(get_client_ip(request))} 的设备上登录。如非本人操作，请立即前往账号安全下线该设备。",
        target_type="login",
        target_id=f"{user.id}-{int(utcnow().timestamp())}",
    )
    db.commit()
    session["requiresApproval"] = user.status == "pending"
    return _auth_response(session)


@router.post("/refresh")
def refresh(payload: RefreshIn | None = None, request: Request = None, db: Session = Depends(get_db)):  # type: ignore[assignment]
    enforce(request, "auth:refresh", limit=120, window_seconds=3600)
    raw = (payload.refresh_token if payload else None) or request.cookies.get(REFRESH_COOKIE)
    row = find_valid_refresh_token(db, raw)
    if not row or not row.user:
        response = JSONResponse(
            {"code": 401, "message": "刷新令牌无效或已撤销，请重新登录", "data": None},
            status_code=401,
        )
        clear_refresh_cookie(response)
        return response
    user = row.user
    if user.status == "disabled":
        raise APIError(403, "账号已停用，请联系管理员")
    # 刷新令牌轮换：旧的立即撤销，降低泄露风险
    row.revoked_at = utcnow()
    row.last_used_at = utcnow()
    db.flush()
    session = _issue_session(db, user, request)
    session["requiresApproval"] = user.status == "pending"
    return _auth_response(session)


@router.post("/logout")
def logout(
    payload: LogoutIn | None = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
):
    raw = (payload.refresh_token if payload else None) or (request.cookies.get(REFRESH_COOKIE) if request else None)
    if raw:
        row = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(raw)).first()
        if row and row.revoked_at is None:
            row.revoked_at = utcnow()
            db.commit()
    response = JSONResponse({"code": 0, "message": "已退出登录", "data": {"loggedOut": True}})
    clear_refresh_cookie(response)
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success({"user": user_public(user, self_view=True)})


# ── 验证码 ─────────────────────────────────────────────────────────────
@router.post("/code/send")
def send_code(payload: CodeSendIn, request: Request, db: Session = Depends(get_db)):
    enforce(request, "auth:code:ip", limit=20, window_seconds=86400)
    target = _normalize_target(payload.target, payload.channel)
    enforce(request, "auth:code:resend", limit=1, window_seconds=60, discriminator=f"{payload.channel}:{target}")
    if payload.channel == "sms":
        phone_count = (
            db.query(SmsLog)
            .filter(SmsLog.phone == target, SmsLog.created_at >= utcnow() - timedelta(days=1))
            .count()
        )
        if phone_count >= 10:
            raise APIError(429, "该手机号今日短信条数已达上限", headers={"Retry-After": "86400"})
    code = numeric_code()
    row = VerifyCode(
        target=target,
        scene=payload.scene,
        code_hash=_code_digest(target, payload.scene, code),
        expires_at=utcnow() + timedelta(minutes=5),
        ip=get_client_ip(request)[:64],
    )
    db.add(row)
    user = db.query(User).filter(User.email == target).first() if payload.channel == "email" else None
    if payload.channel == "sms":
        db.add(
            SmsLog(
                phone=target,
                scene=payload.scene,
                template_id="verify_code",
                status="sent",
                sent_at=utcnow(),
                ip=get_client_ip(request)[:64],
            )
        )
        logger.info("sms_verify_code_simulated target=%s scene=%s", target, payload.scene)
    db.commit()
    if payload.channel == "email":
        enqueue_email(
            db,
            to_email=target,
            template="verify_code.html",
            subject="Moodwave 验证码",
            context={"nickname": user.nickname if user else "你好", "code": code, "sentAt": iso(utcnow())},
            user=user,
            force=True,
        )
    data = {
        "sent": True,
        "channel": payload.channel,
        "expiresIn": 300,
        "resendAfter": 60,
        "message": "若信息有效，验证码已发送",
    }
    if settings.debug:
        data["devCode"] = code
    return success(data)


@router.post("/code/verify")
def verify_code(payload: CodeVerifyIn, request: Request, db: Session = Depends(get_db)):
    enforce(request, "auth:code:verify", limit=20, window_seconds=600)
    target = payload.target.strip().lower()
    row = (
        db.query(VerifyCode)
        .filter(
            VerifyCode.target == target,
            VerifyCode.scene == payload.scene,
            VerifyCode.used_at.is_(None),
        )
        .order_by(VerifyCode.id.desc())
        .first()
    )
    if not row or row.expires_at < utcnow():
        raise APIError(400, "验证码已过期，请重新获取")
    if not hmac.compare_digest(row.code_hash, _code_digest(target, payload.scene, payload.code)):
        raise APIError(400, "验证码错误")
    row.used_at = utcnow()
    db.commit()
    return success(
        {
            "verified": True,
            "verificationToken": _create_verification_token(target, payload.scene),
            "expiresIn": 600,
        }
    )


# ── 找回密码 ───────────────────────────────────────────────────────────
@router.post("/password/forgot")
def forgot_password(payload: ForgotIn, request: Request, db: Session = Depends(get_db)):
    enforce(request, "auth:forgot:ip", limit=10, window_seconds=3600)
    email = payload.email.lower()
    enforce(request, "auth:forgot:email", limit=3, window_seconds=3600, discriminator=email)
    user = db.query(User).filter(User.email == email).first()
    dev_url = None
    if user:
        raw = secrets.token_urlsafe(40)
        db.add(
            PasswordReset(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=utcnow() + timedelta(minutes=15),
            )
        )
        db.commit()
        url = f"{settings.frontend_origin.split(',')[0].rstrip('/')}/forgot-password?token={raw}"
        enqueue_email(
            db,
            to_email=email,
            template="password_reset.html",
            subject="Moodwave 密码重置",
            context={"nickname": user.nickname, "resetUrl": url, "sentAt": iso(utcnow())},
            user=user,
            force=True,
        )
        if settings.debug and settings.expose_dev_reset_link:
            dev_url = url
    return success(
        {
            "message": "如果该邮箱已注册，我们会发送重置链接",
            "devResetUrl": dev_url,
        }
    )


@router.post("/password/reset")
def reset_password(payload: ResetIn, db: Session = Depends(get_db)):
    error = password_strength_error(payload.newPassword)
    if error:
        raise APIError(422, "密码不符合要求", data={"errors": [{"field": "newPassword", "message": error}]})
    row = db.query(PasswordReset).filter(PasswordReset.token_hash == hash_token(payload.token)).first()
    if not row or row.used_at is not None or row.expires_at < utcnow():
        raise APIError(400, "重置链接无效或已过期")
    user = db.get(User, row.user_id)
    if not user:
        raise APIError(400, "账号不存在")
    user.password_hash = hash_password(payload.newPassword)
    row.used_at = utcnow()
    db.query(PasswordReset).filter(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None)).update(
        {PasswordReset.used_at: utcnow()}
    )
    revoked = revoke_all_sessions(db, user.id)
    create_notification(
        db,
        user_id=user.id,
        type="security",
        title="密码已重置",
        message="你的密码刚刚被重置，所有设备已强制下线。如非本人操作，请立即联系管理员。",
        target_type="password_reset",
        target_id=str(int(utcnow().timestamp())),
    )
    db.commit()
    response = JSONResponse(
        {
            "code": 0,
            "message": "密码已重置，所有设备已下线",
            "data": {"revokedSessions": revoked},
        }
    )
    clear_refresh_cookie(response)
    return response


# ── 会话管理 ───────────────────────────────────────────────────────────
@router.get("/sessions")
def sessions(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_hash = hash_token(request.cookies.get(REFRESH_COOKIE, "")) if request.cookies.get(REFRESH_COOKIE) else ""
    rows = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > utcnow(),
        )
        .order_by(RefreshToken.created_at.desc())
        .all()
    )
    data = []
    for row in rows:
        agent = row.user_agent or "未知设备"
        platform = "移动端" if any(token in agent.lower() for token in ("mobile", "android", "iphone")) else "桌面端"
        data.append(
            {
                "id": row.id,
                "device": agent[:120],
                "platform": platform,
                "ip": mask_ip(row.ip),
                "createdAt": iso(row.created_at),
                "lastActiveAt": iso(row.last_used_at or row.created_at),
                "expiresAt": iso(row.expires_at),
                "current": bool(current_hash) and row.token_hash == current_hash,
            }
        )
    return success({"items": data})


@router.delete("/sessions/{session_id}")
def revoke_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(RefreshToken, session_id)
    if not row:
        raise APIError(404, "会话不存在")
    if row.user_id != user.id:
        raise APIError(403, "无权下线他人的会话")
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        db.commit()
    return success({"revoked": True, "id": session_id})


# ── OAuth ──────────────────────────────────────────────────────────────
PROVIDERS = {
    "github": {
        "authorize": "https://github.com/login/oauth/authorize",
        "token": "https://github.com/login/oauth/access_token",
        "profile": "https://api.github.com/user",
        "email": "https://api.github.com/user/emails",
        "scope": "read:user user:email",
        "client_id": lambda: settings.github_client_id,
        "client_secret": lambda: settings.github_client_secret,
    },
    "google": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "profile": "https://openidconnect.googleapis.com/v1/userinfo",
        "email": None,
        "scope": "openid email profile",
        "client_id": lambda: settings.google_client_id,
        "client_secret": lambda: settings.google_client_secret,
    },
    "wechat": {
        "authorize": "https://open.weixin.qq.com/connect/qrconnect",
        "token": "https://api.weixin.qq.com/sns/oauth2/access_token",
        "profile": "https://api.weixin.qq.com/sns/userinfo",
        "email": None,
        "scope": "snsapi_login",
        "client_id": lambda: settings.wechat_app_id,
        "client_secret": lambda: settings.wechat_app_secret,
    },
}


def _provider_redirect_uri(provider: str) -> str:
    return f"{settings.oauth_redirect_base.rstrip('/')}/api/v1/auth/oauth/{provider}/callback"


@router.get("/oauth/{provider}")
def oauth_start(provider: str, request: Request, db: Session = Depends(get_db)):
    config = PROVIDERS.get(provider)
    if not config:
        raise APIError(404, "不支持的第三方登录渠道")
    if not config["client_id"]():
        raise APIError(503, f"{provider} 登录尚未配置，请使用邮箱密码登录")
    enforce(request, f"auth:oauth:{provider}", limit=30, window_seconds=3600)
    state = secrets.token_urlsafe(32)
    db.add(
        OAuthState(
            state=state,
            provider=provider,
            expires_at=utcnow() + timedelta(minutes=10),
        )
    )
    db.commit()
    redirect_uri = _provider_redirect_uri(provider)
    params = {
        "client_id": config["client_id"](),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": config["scope"],
        "state": state,
    }
    if provider == "wechat":
        url = f"{config['authorize']}?" + urllib.parse.urlencode(params) + "#wechat_redirect"
    else:
        url = config["authorize"] + "?" + urllib.parse.urlencode(params)
    return RedirectResponse(url, status_code=302)


@router.get("/oauth/{provider}/callback")
def oauth_callback(provider: str, code: str, state: str, request: Request, db: Session = Depends(get_db)):
    config = PROVIDERS.get(provider)
    if not config or not config["client_id"]():
        raise APIError(503, "第三方登录渠道未配置")
    if request.query_params.get("error"):
        return _oauth_error_redirect(provider, "授权被取消或失败")
    state_row = db.query(OAuthState).filter(OAuthState.state == state, OAuthState.provider == provider).first()
    if not state_row or state_row.used_at is not None or state_row.expires_at < utcnow():
        return _oauth_error_redirect(provider, "state 校验失败，请重新发起登录")
    state_row.used_at = utcnow()
    db.commit()
    try:
        profile, uid, email, avatar = _fetch_oauth_profile(provider, code, config)
    except Exception as exc:
        logger.warning("oauth_exchange_failed provider=%s error=%s", provider, str(exc)[:200])
        return _oauth_error_redirect(provider, "第三方账号验证失败")
    account = (
        db.query(OAuthAccount)
        .filter(OAuthAccount.provider == provider, OAuthAccount.provider_uid == str(uid))
        .first()
    )
    if account:
        user = db.get(User, account.user_id)
        if not user or user.status == "disabled":
            return _oauth_error_redirect(provider, "关联账号不可用")
    else:
        # 绝不按邮箱静默合并：始终为新 openid 创建独立账号
        base_nickname = profile.get("name") or profile.get("login") or f"{provider}-用户"
        nickname = _ensure_nickname(db, str(base_nickname)[:18])
        provider_email = email if email and not db.query(User).filter(User.email == email).first() else None
        placeholder_email = f"{provider}_{uid}@oauth.local"
        user = User(
            email=provider_email or placeholder_email,
            password_hash=None,
            nickname=nickname,
            role="user",
            status="active",
            avatar_url=avatar,
            locale="zh-CN",
            email_verified=bool(provider_email),
        )
        db.add(user)
        db.flush()
        role = _default_role(db)
        db.add(UserRole(user_id=user.id, role_id=role.id, granted_at=utcnow()))
        account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_uid=str(uid),
            provider_email=email,
            avatar_url=avatar,
        )
        db.add(account)
        db.commit()
    session = _issue_session(db, user, request)
    response = RedirectResponse(f"{settings.frontend_origin.split(',')[0].rstrip('/')}/?oauth=success", status_code=302)
    set_refresh_cookie(response, session["refreshToken"])
    return response


def _oauth_error_redirect(provider: str, message: str) -> RedirectResponse:
    target = f"{settings.frontend_origin.split(',')[0].rstrip('/')}/login?oauth_error={urllib.parse.quote(message)}"
    return RedirectResponse(target, status_code=302)


def _fetch_oauth_profile(provider: str, code: str, config: dict) -> tuple[dict, str, str | None, str | None]:
    redirect_uri = _provider_redirect_uri(provider)
    with httpx.Client(timeout=12, follow_redirects=True) as client:
        if provider == "wechat":
            token_resp = client.get(
                config["token"],
                params={
                    "appid": config["client_id"](),
                    "secret": config["client_secret"](),
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )
        else:
            token_resp = client.post(
                config["token"],
                data={
                    "client_id": config["client_id"](),
                    "client_secret": config["client_secret"](),
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access = token_data.get("access_token")
        if not access:
            raise ValueError("missing access token")
        headers = {"Authorization": f"Bearer {access}", "Accept": "application/json"}
        profile_resp = client.get(config["profile"], headers=headers)
        profile_resp.raise_for_status()
        profile = profile_resp.json()
        if provider == "wechat":
            uid = profile.get("unionid") or profile.get("openid")
            email = None
            avatar = profile.get("headimgurl")
        elif provider == "google":
            uid = profile.get("sub")
            email = profile.get("email")
            avatar = profile.get("picture")
        else:
            uid = profile.get("id")
            email = profile.get("email")
            avatar = profile.get("avatar_url")
            if not email and config.get("email"):
                email_resp = client.get(config["email"], headers=headers)
                if email_resp.status_code == 200:
                    for item in email_resp.json():
                        if item.get("primary") and item.get("verified"):
                            email = item.get("email")
                            break
        if not uid:
            raise ValueError("missing provider uid")
        return profile, str(uid), email, avatar
