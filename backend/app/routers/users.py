"""个人资料、头像、联系方式二次验证、权限集合与推送偏好。"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..errors import APIError, success
from ..models import PushChannel, SmsLog, User, UserPushSetting, VerifyCode, utcnow
from ..security import (
    get_current_user,
    get_user_permissions,
    hash_password,
    password_strength_error,
    revoke_all_sessions,
    verify_password,
)
from ..serializers import user_public
from ..services.mailer import enqueue_email
from ..services.notify import create_notification
from ..services.ratelimit import enforce, get_client_ip
from ..services.storage import save_avatar
from ..utils import clean_text, iso, mask_ip

router = APIRouter(prefix="/api/v1", tags=["users"])
logger = logging.getLogger("moodwave.users")


class ProfilePatch(BaseModel):
    nickname: str | None = Field(default=None, min_length=2, max_length=20)
    bio: str | None = Field(default=None, max_length=300)
    gender: Literal["", "female", "male", "nonbinary", "secret"] | None = None
    birthday: date | None = None
    location: str | None = Field(default=None, max_length=80)
    locale: Literal["zh-CN", "en-US"] | None = None
    # 邮箱/手机号显式出现时给出可读的安全流程提示，不允许静默忽略
    email: str | None = None
    phone: str | None = None


class ContactRequestIn(BaseModel):
    type: Literal["email", "phone"]
    value: str = Field(min_length=3, max_length=255)


class ContactConfirmIn(BaseModel):
    type: Literal["email", "phone"]
    value: str
    code: str = Field(min_length=6, max_length=6)


class PasswordChangeIn(BaseModel):
    currentPassword: str
    newPassword: str = Field(min_length=8, max_length=64)


class PushSettingItem(BaseModel):
    channelCode: str
    enabled: bool
    quietHours: bool = True


class PushSettingsPatch(BaseModel):
    settings: list[PushSettingItem]


@router.get("/users/me")
def get_profile(user: User = Depends(get_current_user)):
    return success({"user": user_public(user, self_view=True)})


@router.patch("/users/me")
def update_profile(payload: ProfilePatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.email is not None or payload.phone is not None:
        raise APIError(
            422,
            "修改邮箱或手机号需要先完成新联系方式验证",
            data={
                "code": "CONTACT_REQUIRES_VERIFICATION",
                "requestEndpoint": "/api/v1/users/me/contact/request",
                "confirmEndpoint": "/api/v1/users/me/contact/confirm",
            },
        )
    changed = False
    if payload.nickname is not None:
        nickname = clean_text(payload.nickname, max_len=20, keep_newlines=False)
        if len(nickname) < 2:
            raise APIError(422, "昵称至少 2 个字符", data={"errors": [{"field": "nickname", "message": "昵称至少 2 个字符"}]})
        exists = db.query(User).filter(User.nickname == nickname, User.id != user.id).first()
        if exists:
            raise APIError(409, "该昵称已被使用")
        user.nickname = nickname
        changed = True
    if payload.bio is not None:
        user.bio = clean_text(payload.bio, max_len=300)
        changed = True
    if payload.gender is not None:
        user.gender = payload.gender
        changed = True
    if "birthday" in payload.model_fields_set:
        user.birthday = payload.birthday
        changed = True
    if payload.location is not None:
        user.location = clean_text(payload.location, max_len=80, keep_newlines=False)
        changed = True
    if payload.locale is not None:
        user.locale = payload.locale
        changed = True
    if not changed:
        raise APIError(422, "没有需要更新的字段")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIError(409, "昵称已被占用") from exc
    db.refresh(user)
    return success({"user": user_public(user, self_view=True)})


@router.post("/users/me/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce(request, "users:avatar", limit=10, window_seconds=3600, discriminator=str(user.id))
    result = await save_avatar(file, user.id)
    old = user.avatar_url
    user.avatar_url = result["url"]
    db.commit()
    if old and old != result["url"]:
        from ..services.storage import delete_file

        delete_file(old)
    return success({"avatarUrl": result["url"], "width": result["width"], "height": result["height"]})


# ── 联系方式二次验证 ────────────────────────────────────────────────────
def _code_digest(target: str, scene: str, code: str) -> str:
    import hashlib
    import hmac

    return hmac.new(settings.jwt_secret.encode(), f"{target}:{scene}:{code}".encode(), hashlib.sha256).hexdigest()


@router.post("/users/me/contact/request")
def request_contact_change(
    payload: ContactRequestIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce(request, "users:contact:send", limit=5, window_seconds=3600, discriminator=str(user.id))
    value = payload.value.strip().lower()
    if payload.type == "email":
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            raise APIError(422, "请输入有效邮箱")
        if db.query(User).filter(User.email == value, User.id != user.id).first():
            raise APIError(409, "该邮箱已被其他账号使用")
    else:
        if not re.match(r"^\+?[0-9]{6,20}$", value):
            raise APIError(422, "请输入有效手机号")
        if db.query(User).filter(User.phone == value, User.id != user.id).first():
            raise APIError(409, "该手机号已被其他账号使用")
    if value == (user.email if payload.type == "email" else user.phone):
        raise APIError(422, "新联系方式与当前一致")
    enforce(request, "users:contact:resend", limit=1, window_seconds=60, discriminator=f"{user.id}:{value}")
    from ..utils import numeric_code

    code = numeric_code()
    db.add(
        VerifyCode(
            target=value,
            scene="change_contact",
            code_hash=_code_digest(value, "change_contact", code),
            expires_at=utcnow() + timedelta(minutes=5),
            ip=get_client_ip(request)[:64],
        )
    )
    if payload.type == "phone":
        db.add(
            SmsLog(
                phone=value,
                scene="change_contact",
                template_id="verify_code",
                status="sent",
                sent_at=utcnow(),
                ip=get_client_ip(request)[:64],
            )
        )
    db.commit()
    if payload.type == "email":
        enqueue_email(
            db,
            to_email=value,
            template="verify_code.html",
            subject="Moodwave 联系方式验证",
            context={"nickname": user.nickname, "code": code, "sentAt": iso(utcnow())},
            user=user,
            force=True,
        )
    data = {"sent": True, "channel": payload.type, "expiresIn": 300}
    if settings.debug:
        data["devCode"] = code
    return success(data)


@router.post("/users/me/contact/confirm")
def confirm_contact_change(
    payload: ContactConfirmIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    value = payload.value.strip().lower()
    row = (
        db.query(VerifyCode)
        .filter(
            VerifyCode.target == value,
            VerifyCode.scene == "change_contact",
            VerifyCode.used_at.is_(None),
        )
        .order_by(VerifyCode.id.desc())
        .first()
    )
    if not row or row.expires_at < utcnow():
        raise APIError(400, "验证码已过期，请重新获取")
    import hmac

    if not hmac.compare_digest(row.code_hash, _code_digest(value, "change_contact", payload.code)):
        raise APIError(400, "验证码错误")
    row.used_at = utcnow()
    if payload.type == "email":
        user.email = value
        user.email_verified = True
        revoked = revoke_all_sessions(db, user.id)
    else:
        user.phone = value
        user.phone_verified = True
        revoked = 0
    create_notification(
        db,
        user_id=user.id,
        type="security",
        title="联系方式已更新",
        message=f"你的{'邮箱' if payload.type == 'email' else '手机号'}已更新为 {value}。如非本人操作，请立即修改密码。",
        target_type="contact",
        target_id=f"{payload.type}-{int(utcnow().timestamp())}",
    )
    db.commit()
    return success({"updated": True, "type": payload.type, "value": value, "revokedSessions": revoked})


@router.post("/users/me/password")
def change_password(
    payload: PasswordChangeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.password_hash and not verify_password(payload.currentPassword, user.password_hash):
        raise APIError(400, "当前密码不正确")
    error = password_strength_error(payload.newPassword)
    if error:
        raise APIError(422, error)
    user.password_hash = hash_password(payload.newPassword)
    revoked = revoke_all_sessions(db, user.id)
    db.commit()
    return success({"changed": True, "revokedSessions": revoked})


# ── 权限 ────────────────────────────────────────────────────────────────
@router.get("/permissions")
def my_permissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    permissions = sorted(get_user_permissions(db, user))
    return success({"permissions": permissions, "role": user.role, "status": user.status})


# ── 推送设置 ─────────────────────────────────────────────────────────────
@router.get("/users/me/push-settings")
def get_push_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    channels = db.query(PushChannel).filter(PushChannel.status == "active").all()
    if not channels:
        defaults = [
            ("inapp", "站内通知", "internal"),
            ("email", "邮件", "smtp"),
            ("sms", "短信", "sms"),
            ("push", "App 推送", "webpush"),
        ]
        channels = []
        for code, name, provider in defaults:
            channel = PushChannel(code=code, name=name, provider=provider, status="active", config={})
            db.add(channel)
            channels.append(channel)
        db.commit()
    settings_rows = {
        row.channel_code: row for row in db.query(UserPushSetting).filter(UserPushSetting.user_id == user.id).all()
    }
    items = []
    for channel in channels:
        row = settings_rows.get(channel.code)
        items.append(
            {
                "channelCode": channel.code,
                "name": channel.name,
                "provider": channel.provider,
                "enabled": row.enabled if row else channel.code in {"inapp", "email"},
                "quietHours": row.quiet_hours if row else True,
            }
        )
    return success({"items": items})


@router.patch("/users/me/push-settings")
def update_push_settings(
    payload: PushSettingsPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    valid = {channel.code for channel in db.query(PushChannel).all()}
    if not valid:
        valid = {"inapp", "email", "sms", "push"}
    for item in payload.settings:
        if item.channelCode not in valid:
            raise APIError(422, f"未知推送渠道：{item.channelCode}")
        row = (
            db.query(UserPushSetting)
            .filter(UserPushSetting.user_id == user.id, UserPushSetting.channel_code == item.channelCode)
            .first()
        )
        if row:
            row.enabled = item.enabled
            row.quiet_hours = item.quietHours
        else:
            db.add(
                UserPushSetting(
                    user_id=user.id,
                    channel_code=item.channelCode,
                    enabled=item.enabled,
                    quiet_hours=item.quietHours,
                )
            )
    db.commit()
    return get_push_settings(user, db)
