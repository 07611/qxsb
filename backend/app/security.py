"""密码哈希、JWT、刷新令牌、RBAC 依赖与 Cookie 工具。"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable

import bcrypt
import jwt
from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .errors import APIError
from .models import RefreshToken, Role, User, UserRole, utcnow
from .services.ratelimit import get_client_ip
from .utils import hash_token

bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"
ISSUER = "moodwave"
AUDIENCE = "moodwave-web"
REFRESH_COOKIE = "mw_refresh"


# ── 密码 ──────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise APIError(422, "密码过长，请控制在 72 字节以内")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode())
    except ValueError:
        return False


DUMMY_HASH = hash_password("Moodwave-dummy-password-for-timing")


def password_strength_error(password: str) -> str | None:
    if len(password) < 8:
        return "密码至少 8 个字符"
    if len(password) > 64:
        return "密码不能超过 64 个字符"
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        return "密码需同时包含字母和数字"
    return None


# ── JWT ──────────────────────────────────────────────────────────────
def create_access_token(user: User) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "type": "access",
        "jti": secrets.token_urlsafe(16),
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "iss": ISSUER,
        "aud": AUDIENCE,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, settings.access_token_expire_minutes * 60


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise APIError(401, "登录状态已过期，请刷新或重新登录", headers={"WWW-Authenticate": "Bearer"}) from exc
    except jwt.InvalidTokenError as exc:
        raise APIError(401, "登录凭证无效", headers={"WWW-Authenticate": "Bearer"}) from exc


def create_refresh_token(
    db: Session,
    user: User,
    request: Request | None = None,
) -> tuple[str, RefreshToken]:
    raw = secrets.token_urlsafe(48)
    row = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        user_agent=(request.headers.get("user-agent", "")[:250] if request else ""),
        ip=(get_client_ip(request) if request else ""),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(row)
    db.flush()
    return raw, row


def find_valid_refresh_token(db: Session, raw: str | None) -> RefreshToken | None:
    if not raw:
        return None
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(raw)).first()
    if not row:
        return None
    if row.revoked_at is not None or row.expires_at <= utcnow():
        return None
    return row


def revoke_all_sessions(db: Session, user_id: int) -> int:
    now = utcnow()
    count = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: now})
    )
    return int(count)


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth", httponly=True, secure=settings.cookie_secure, samesite="lax")


# ── 身份依赖 ───────────────────────────────────────────────────────────
def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise APIError(401, "请先登录", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_access_token(credentials.credentials)
    if payload.get("type") != "access":
        raise APIError(401, "登录凭证类型错误", headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id = int(payload.get("sub", "0"))
    except ValueError as exc:
        raise APIError(401, "登录凭证无效") from exc
    # 每次都回源数据库：角色变更、封禁、审核状态即时生效
    user = db.get(User, user_id)
    if not user:
        raise APIError(401, "账号不存在或已注销")
    if user.status == "disabled":
        raise APIError(403, "账号已停用，请联系管理员")
    request.state.user_id = user.id
    return user


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user = db.get(User, int(payload.get("sub", "0")))
    except Exception:
        return None
    if user and user.status != "disabled":
        request.state.user_id = user.id
        return user
    return None


def get_user_permissions(db: Session, user: User) -> set[str]:
    permissions: set[str] = set()
    role_codes = [user.role]
    rows = (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user.id)
        .all()
    )
    for role in rows:
        role_codes.append(role.code)
        for permission in role.permissions or []:
            permissions.add(str(permission))
    if "admin" in role_codes:
        permissions.update({"*", "admin:access"})
    if "user" in role_codes:
        permissions.update({"content:read", "content:write", "profile:write", "feedback:write"})
    return permissions


def has_permission(db: Session, user: User, permission: str) -> bool:
    perms = get_user_permissions(db, user)
    if "*" in perms or permission in perms:
        return True
    # support prefix wildcard like content:*
    prefix = permission.split(":", 1)[0] + ":*"
    return prefix in perms


def require_permission(permission: str) -> Callable:
    def dependency(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not has_permission(db, user, permission):
            raise APIError(403, "你没有执行此操作的权限")
        return user

    return dependency


def require_admin(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if not has_permission(db, user, "admin:access"):
        raise APIError(403, "需要管理员权限")
    return user


def require_active_user(user: User = Depends(get_current_user)) -> User:
    if user.status != "active":
        raise APIError(403, "账号尚未通过审核", data={"status": user.status, "redirect": "/pending"})
    return user


def is_admin(db: Session, user: User | None) -> bool:
    return bool(user and has_permission(db, user, "admin:access"))
