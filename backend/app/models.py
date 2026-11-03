"""ORM 模型。基础结构来自任务书建表脚本，扩展字段均有注释并在 docs 中说明。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    """统一存储无时区 UTC，输出时由序列化层补 Z。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False, index=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    bio: Mapped[Optional[str]] = mapped_column(Text)
    phone: Mapped[Optional[str]] = mapped_column(String(32), unique=True)
    gender: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    birthday: Mapped[Optional[date]] = mapped_column(Date)
    location: Mapped[Optional[str]] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(50), default="zh-CN", nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 冗余未读数：写通知时原子 +1，避免每次 count 全表
    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 登录失败锁定策略字段
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    disabled_reason: Mapped[Optional[str]] = mapped_column(Text)

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    items: Mapped[list["Item"]] = relationship(back_populates="owner")


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[Optional[str]] = mapped_column(Text)


class UserRole(TimestampMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="ux_user_roles_user_role"),
        Index("ix_user_roles_user_id", "user_id"),
        Index("ix_user_roles_role_id", "role_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship()


class RefreshToken(TimestampMixin, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_hash", "token_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    ip: Mapped[str] = mapped_column(String(255), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped[User] = relationship()


class Item(TimestampMixin, Base):
    __tablename__ = "items"
    __table_args__ = (Index("ix_items_owner_id", "owner_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="published", nullable=False, index=True)
    # 任务书分类功能所需，原 items 表缺少归属字段
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    cover_url: Mapped[Optional[str]] = mapped_column(Text)
    cover_thumb_url: Mapped[Optional[str]] = mapped_column(Text)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)

    owner: Mapped[User] = relationship(back_populates="items")
    category: Mapped[Optional["Category"]] = relationship()


class Attachment(TimestampMixin, Base):
    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_owner_id", "owner_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    biz_type: Mapped[str] = mapped_column(String(50), default="")
    biz_id: Mapped[Optional[str]] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    thumb_url: Mapped[Optional[str]] = mapped_column(Text)
    detail_url: Mapped[Optional[str]] = mapped_column(Text)
    storage_key: Mapped[Optional[str]] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(String(100), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("slug", name="ux_categories_slug"), Index("ix_categories_parent_id", "parent_id"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    post_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    parent: Mapped[Optional["Category"]] = relationship(remote_side="Category.id")


class Tag(TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("slug", name="ux_tags_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    post_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)


class PostTag(TimestampMixin, Base):
    __tablename__ = "post_tags"
    __table_args__ = (
        UniqueConstraint("post_id", "tag_id", name="ux_post_tags_post_tag"),
        Index("ix_post_tags_tag_id", "tag_id"),
        Index("ix_post_tags_post_id", "post_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)


class SearchLog(TimestampMixin, Base):
    __tablename__ = "search_logs"
    __table_args__ = (Index("ix_search_logs_user_id", "user_id"), Index("ix_search_logs_keyword", "keyword"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", name="ux_notifications_dedup"),
        Index("ix_notifications_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="system", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    target_type: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class NotificationArchive(TimestampMixin, Base):
    __tablename__ = "notification_archive"
    __table_args__ = (Index("ix_notification_archive_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    archived_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class VerifyCode(TimestampMixin, Base):
    __tablename__ = "verify_codes"
    __table_args__ = (Index("ix_verify_codes_target_scene", "target", "scene"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    scene: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ip: Mapped[str] = mapped_column(String(64), default="")


class OAuthAccount(TimestampMixin, Base):
    __tablename__ = "o_auth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_uid", name="ux_oauth_provider_uid"),
        Index("ix_o_auth_accounts_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    # 原脚本 provider_user_id 为 BIGINT，无法存 openid 字符串；保留原字段并新增字符串字段
    provider_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    provider_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[Optional[str]] = mapped_column(String(255))
    access_token: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)


class OAuthState(TimestampMixin, Base):
    __tablename__ = "oauth_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    bind_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class PasswordReset(TimestampMixin, Base):
    __tablename__ = "password_resets"
    __table_args__ = (Index("ix_password_resets_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class ShareLink(TimestampMixin, Base):
    __tablename__ = "share_links"
    __table_args__ = (UniqueConstraint("code", name="ux_share_links_code"), Index("ix_share_links_created_by", "created_by"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class EmailLog(TimestampMixin, Base):
    __tablename__ = "email_logs"
    __table_args__ = (Index("ix_email_logs_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    template: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 模板变量与服务端渲染上下文；避免把用户输入直接拼进邮件
    context: Mapped[Optional[dict]] = mapped_column(JSON)


class Feedback(TimestampMixin, Base):
    __tablename__ = "feedbacks"
    __table_args__ = (Index("ix_feedbacks_user_id", "user_id"), Index("ix_feedbacks_handler_id", "handler_id"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="other", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    images: Mapped[Optional[list]] = mapped_column(JSON)
    contact: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False, index=True)
    handler_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reply: Mapped[Optional[str]] = mapped_column(Text)
    supplementary: Mapped[Optional[list]] = mapped_column(JSON)


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_user_id", "user_id"),
        Index("ix_events_event_key", "event_key"),
        Index("ix_events_occurred_at", "occurred_at"),
        Index("ix_events_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    user_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    page: Mapped[int] = mapped_column(Integer, default=0)
    props: Mapped[Optional[dict]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class EventDef(TimestampMixin, Base):
    __tablename__ = "event_defs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    props_schema: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)


class EventArchive(TimestampMixin, Base):
    """事件滚动归档表：SQLite 不支持原生分区，用独立归档表控制主表体积。"""

    __tablename__ = "event_archive"
    __table_args__ = (Index("ix_event_archive_occurred_at", "occurred_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    user_hash: Mapped[Optional[str]] = mapped_column(String(64))
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    props: Mapped[Optional[dict]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Funnel(TimestampMixin, Base):
    __tablename__ = "funnels"
    __table_args__ = (Index("ix_funnels_created_by", "created_by"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


class PushChannel(TimestampMixin, Base):
    __tablename__ = "push_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="internal")
    config: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), default="active")


class UserPushSetting(TimestampMixin, Base):
    __tablename__ = "user_push_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_code", name="ux_user_push_channel"),
        Index("ix_user_push_settings_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel_code: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quiet_hours: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PushTask(TimestampMixin, Base):
    __tablename__ = "push_tasks"
    __table_args__ = (Index("ix_push_tasks_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel_code: Mapped[str] = mapped_column(String(50), nullable=False)
    template_code: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    is_marketing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class InviteCode(TimestampMixin, Base):
    __tablename__ = "invite_codes"
    __table_args__ = (Index("ix_invite_codes_created_by", "created_by"), Index("ix_invite_codes_used_by", "used_by"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    used_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class SmsLog(TimestampMixin, Base):
    __tablename__ = "sms_logs"
    # 原脚本 phone UNIQUE 会阻止同号码多条记录；这里改为普通索引（见 docs/architecture.md）
    __table_args__ = (Index("ix_sms_logs_phone", "phone"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    scene: Mapped[str] = mapped_column(String(50), default="")
    template_id: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(50), default="sent")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ip: Mapped[str] = mapped_column(String(64), default="")


class Banner(TimestampMixin, Base):
    __tablename__ = "banners"
    __table_args__ = (Index("ix_banners_position_sort", "position", "sort"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    position_code: Mapped[str] = mapped_column(String(50), default="home", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[Optional[str]] = mapped_column(Text)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="16/5")


class Track(TimestampMixin, Base):
    """推荐曲库。本地曲目保存完整音频特征；在线曲目仅存元数据。"""

    __tablename__ = "tracks"
    __table_args__ = (Index("ix_tracks_source", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    artist: Mapped[str] = mapped_column(String(255), default="Moodwave Studio")
    album: Mapped[Optional[str]] = mapped_column(String(255))
    mood: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    mood_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    audio_features: Mapped[dict] = mapped_column(JSON, default=dict)
    local_path: Mapped[Optional[str]] = mapped_column(Text)
    preview_url: Mapped[Optional[str]] = mapped_column(Text)
    cover_url: Mapped[Optional[str]] = mapped_column(Text)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(50), default="local")
    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    play_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    license_note: Mapped[Optional[str]] = mapped_column(Text)


class EmotionLog(TimestampMixin, Base):
    __tablename__ = "emotion_logs"
    __table_args__ = (Index("ix_emotion_logs_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    emotion: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(50), default="upload")
    inference_ms: Mapped[int] = mapped_column(Integer, default=0)
    image_attachment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("attachments.id", ondelete="SET NULL"))


class TrackFeedback(TimestampMixin, Base):
    __tablename__ = "track_feedback"
    __table_args__ = (UniqueConstraint("user_id", "track_id", name="ux_track_feedback_user_track"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class FavoriteTrack(TimestampMixin, Base):
    __tablename__ = "favorite_tracks"
    __table_args__ = (UniqueConstraint("user_id", "track_id", name="ux_favorite_user_track"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)


class RecommendationLog(TimestampMixin, Base):
    __tablename__ = "recommendation_logs"
    __table_args__ = (Index("ix_recommendation_logs_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    emotion: Mapped[str] = mapped_column(String(50), nullable=False)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"
    __table_args__ = (Index("ix_rate_limit_window", "window_start"),)

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    window_start: Mapped[int] = mapped_column(Integer, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (Index("ix_idempotency_expires", "expires_at"),)

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="processing")
    response_status: Mapped[int] = mapped_column(Integer, default=0)
    response_body: Mapped[Optional[str]] = mapped_column(Text)
    response_headers: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ClientLog(TimestampMixin, Base):
    __tablename__ = "client_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    level: Mapped[str] = mapped_column(String(20), default="error")
    message: Mapped[str] = mapped_column(Text, default="")
    stack: Mapped[Optional[str]] = mapped_column(Text)
    route: Mapped[Optional[str]] = mapped_column(String(255))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    request_id: Mapped[Optional[str]] = mapped_column(String(64))
    context: Mapped[Optional[dict]] = mapped_column(JSON)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_actor_id", "actor_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), default="")
    target_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[Optional[dict]] = mapped_column(JSON)
    ip: Mapped[str] = mapped_column(String(64), default="")


class DailyMetric(Base):
    __tablename__ = "daily_metrics"
    __table_args__ = (UniqueConstraint("day", "metric", "dimension", name="ux_daily_metric"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[str] = mapped_column(String(100), default="all", nullable=False)
    value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
