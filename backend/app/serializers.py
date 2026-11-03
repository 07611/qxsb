"""统一序列化：前端只拿到公开字段，敏感字段绝不外泄。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import (
    Attachment,
    Banner,
    Category,
    Feedback,
    Item,
    Notification,
    PostTag,
    Tag,
    Track,
    User,
)
from .utils import iso, mask_ip, mask_phone, public_media_url

MOOD_LABELS = {
    "happy": "愉悦",
    "sad": "低落",
    "angry": "愤怒",
    "fear": "不安",
    "surprised": "惊喜",
    "neutral": "平静",
}

ROLE_LABELS = {"admin": "管理员", "editor": "内容编辑", "user": "普通用户"}


def user_public(user: User, *, self_view: bool = False) -> dict:
    data = {
        "id": user.id,
        "nickname": user.nickname,
        "avatarUrl": user.avatar_url,
        "bio": user.bio or "",
        "role": user.role,
        "roleLabel": ROLE_LABELS.get(user.role, user.role),
        "status": user.status,
        "gender": user.gender,
        "locale": user.locale,
        "location": user.location,
        "createdAt": iso(user.created_at),
    }
    if self_view:
        data.update(
            {
                "email": user.email,
                "phone": mask_phone(user.phone),
                "phoneRaw": user.phone or "",
                "emailVerified": user.email_verified,
                "phoneVerified": user.phone_verified,
                "birthday": user.birthday.isoformat() if user.birthday else None,
                "unreadCount": user.unread_count,
                "lastLoginAt": iso(user.last_login_at),
            }
        )
    return data


def user_admin(user: User) -> dict:
    data = user_public(user, self_view=True)
    data.update(
        {
            "failedLoginAttempts": user.failed_login_attempts,
            "lockedUntil": iso(user.locked_until),
            "disabledReason": user.disabled_reason,
        }
    )
    return data


def category_public(category: Category) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "parentId": category.parent_id,
        "sort": category.sort,
        "postCount": category.post_count,
        "description": category.description or "",
    }


def tag_public(tag: Tag) -> dict:
    return {
        "id": tag.id,
        "name": tag.name,
        "slug": tag.slug,
        "postCount": tag.post_count,
    }


def item_tags(db: Session, item_id: int) -> list[dict]:
    tags = (
        db.query(Tag)
        .join(PostTag, PostTag.tag_id == Tag.id)
        .filter(PostTag.post_id == str(item_id))
        .order_by(Tag.post_count.desc())
        .all()
    )
    return [tag_public(tag) for tag in tags]


def item_public(db: Session, item: Item, *, detail: bool = False) -> dict:
    data = {
        "id": item.id,
        "title": item.title,
        "excerpt": (item.content or "")[:160],
        "status": item.status,
        "coverUrl": item.cover_url,
        "coverThumbUrl": item.cover_thumb_url,
        "category": category_public(item.category) if item.category else None,
        "tags": item_tags(db, item.id),
        "owner": {
            "id": item.owner_id,
            "nickname": item.owner.nickname if item.owner else "已注销用户",
            "avatarUrl": item.owner.avatar_url if item.owner else None,
        },
        "createdAt": iso(item.created_at),
        "updatedAt": iso(item.updated_at),
    }
    if detail:
        data["content"] = item.content
        data["canEdit"] = False
    return data


def track_public(track: Track, *, detail: bool = False) -> dict:
    audio_url = track.preview_url
    if not audio_url and track.local_path:
        audio_url = "/" + track.local_path.lstrip("/")
    data = {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album or "",
        "mood": track.mood,
        "moodLabel": MOOD_LABELS.get(track.mood, track.mood),
        "coverUrl": track.cover_url,
        "duration": round(track.duration_seconds or 0),
        "source": track.source,
        "audioUrl": public_media_url(audio_url) if audio_url and audio_url.startswith("/") else audio_url,
        "previewUrl": track.preview_url,
        "likeCount": track.like_count,
        "playCount": track.play_count,
        "licenseNote": track.license_note or "",
        "audioFeatures": track.audio_features if detail else {
            "tempo": (track.audio_features or {}).get("tempo"),
            "valence": (track.audio_features or {}).get("valence"),
            "arousal": (track.audio_features or {}).get("arousal"),
            "mode": (track.audio_features or {}).get("mode"),
        },
    }
    if detail:
        data["moodScores"] = track.mood_scores
    return data


def notification_public(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "type": notification.type,
        "title": notification.title,
        "message": notification.message,
        "targetType": notification.target_type,
        "targetId": notification.target_id,
        "read": notification.read_at is not None,
        "readAt": iso(notification.read_at),
        "createdAt": iso(notification.created_at),
    }


def feedback_public(feedback: Feedback, *, admin: bool = False) -> dict:
    data = {
        "id": feedback.id,
        "ticketNo": feedback.ticket_no,
        "type": feedback.type,
        "content": feedback.content,
        "images": feedback.images or [],
        "contact": feedback.contact or "",
        "status": feedback.status,
        "reply": feedback.reply or "",
        "supplementary": feedback.supplementary or [],
        "createdAt": iso(feedback.created_at),
        "updatedAt": iso(feedback.updated_at),
    }
    if admin:
        data["userId"] = feedback.user_id
        data["handlerId"] = feedback.handler_id
    return data


def banner_public(banner: Banner) -> dict:
    return {
        "id": banner.id,
        "position": banner.position_code,
        "title": banner.title,
        "subtitle": banner.subtitle or "",
        "imageUrl": banner.image_url,
        "linkUrl": banner.link_url,
        "sort": banner.sort,
        "aspectRatio": banner.aspect_ratio,
        "startAt": iso(banner.start_at),
        "endAt": iso(banner.end_at),
        "status": banner.status,
    }


def attachment_public(attachment: Attachment) -> dict:
    return {
        "id": attachment.id,
        "url": attachment.url,
        "thumbUrl": attachment.thumb_url,
        "detailUrl": attachment.detail_url,
        "mime": attachment.mime,
        "size": attachment.size_bytes,
        "width": attachment.width,
        "height": attachment.height,
        "bizType": attachment.biz_type,
        "createdAt": iso(attachment.created_at),
    }
