"""幂等种子数据：账号、曲库、分类标签、演示内容、工单、埋点与运营位。

执行：
    python -m app.seed          # 需要在 backend 目录下，或使用 scripts/seed.py
重复执行不会生成重复数据，也不会重置已修改的账号密码。
"""

from __future__ import annotations

import json
import logging
import random
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import Integer, cast, func
from sqlalchemy.orm import Session

from .config import settings
from .database import init_db, session_scope
from .models import (
    Banner,
    Category,
    Event,
    EventDef,
    FavoriteTrack,
    Feedback,
    Funnel,
    InviteCode,
    Item,
    Notification,
    PostTag,
    PushChannel,
    PushTask,
    Role,
    SearchLog,
    ShareLink,
    Tag,
    Track,
    User,
    UserPushSetting,
    UserRole,
    utcnow,
)
from .security import hash_password
from .services.audio import analyze_audio, mood_scores_from_features
from .services.emotion import demos as load_demos
from .utils import hash_user_id, slugify, unique_slug

logger = logging.getLogger("moodwave.seed")

ROLE_DEFS = {
    "admin": (["*", "admin:access", "users:manage", "content:manage", "feedback:manage", "analytics:manage", "reports:view"], "系统管理员"),
    "editor": (["admin:access", "content:manage", "categories:manage", "feedback:manage", "reports:view"], "内容编辑"),
    "user": (["content:read", "content:write", "profile:write", "feedback:write"], "普通用户"),
}


def _upsert_role(db: Session, code: str) -> Role:
    permissions, name = ROLE_DEFS[code]
    role = db.query(Role).filter(Role.code == code).first()
    if not role:
        role = Role(name=name, code=code, permissions=permissions, description=name)
        db.add(role)
        db.flush()
    else:
        role.name = name
        role.permissions = permissions
    return role


def _ensure_user(
    db: Session,
    *,
    email: str,
    nickname: str,
    password: str | None,
    role_code: str,
    status: str = "active",
    bio: str = "",
    locale: str = "zh-CN",
    avatar_url: str | None = None,
) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            password_hash=hash_password(password) if password else None,
            nickname=nickname,
            role=role_code,
            status=status,
            bio=bio,
            locale=locale,
            email_verified=True,
            avatar_url=avatar_url,
        )
        db.add(user)
        db.flush()
        logger.info("seed_user_created email=%s role=%s", email, role_code)
    else:
        if user.nickname != nickname and not db.query(User).filter(User.nickname == nickname, User.id != user.id).first():
            user.nickname = nickname
        user.role = role_code
        if user.status not in {"pending", "disabled"}:
            user.status = status
    role = db.query(Role).filter(Role.code == role_code).first()
    if role:
        link = db.query(UserRole).filter(UserRole.user_id == user.id, UserRole.role_id == role.id).first()
        if not link:
            db.add(UserRole(user_id=user.id, role_id=role.id, granted_at=utcnow()))
    return user


def seed_users(db: Session) -> tuple[User, User]:
    for code in ROLE_DEFS:
        _upsert_role(db, code)
    admin = _ensure_user(
        db,
        email=settings.seed_admin_email.lower(),
        nickname="Moodwave 管理员",
        password=settings.seed_admin_password,
        role_code="admin",
        bio="维护心绪声场的曲库、内容与社区秩序。",
        avatar_url="/media/banners/avatar-admin.svg",
    )
    demo = _ensure_user(
        db,
        email=settings.seed_user_email.lower(),
        nickname="林间听风",
        password=settings.seed_user_password,
        role_code="user",
        bio="在通勤和深夜之间收集情绪切片。喜欢钢琴、环境声与低保真。",
        avatar_url="/media/banners/avatar-demo.svg",
    )
    if not demo.phone:
        demo.phone = "+8613800138000"
        demo.phone_verified = True
    extras = [
        ("nora@moodwave.app", "Nora 的夜航", "user", "active", "夜晚比白天诚实。"),
        ("chen@moodwave.app", "陈屿", "user", "active", "把城市噪音混进歌里。"),
        ("mika@moodwave.app", "米卡", "user", "pending", "正在等待审核。"),
        ("jun@moodwave.app", "阿骏", "editor", "active", "编辑，偶尔写乐评。"),
    ]
    for email, nickname, role, status, bio in extras:
        _ensure_user(db, email=email, nickname=nickname, password="Member@12345", role_code=role, status=status, bio=bio)
    # 未通过审核的演示账号每次 seed 保持 pending 以便后台演示
    pending = db.query(User).filter(User.email == "mika@moodwave.app").first()
    if pending and pending.status == "active":
        pending.status = "pending"
    return admin, demo


def seed_taxonomy(db: Session) -> tuple[list[Category], list[Tag]]:
    categories_data = [
        ("场景", "scenes", None, 10),
        ("情绪", "moods", None, 20),
        ("编辑手记", "editorial", None, 30),
    ]
    root_map = {}
    for name, slug, parent, sort in categories_data:
        row = db.query(Category).filter(Category.slug == slug).first()
        if not row:
            row = Category(name=name, slug=slug, parent_id=None, sort=sort, description=f"{name}相关歌单")
            db.add(row)
            db.flush()
        root_map[slug] = row
    children = [
        ("通勤路上", "commute", "scenes", 11, "地铁、步行与城市移动的声音。"),
        ("深夜房间", "late-night", "scenes", 12, "把灯关掉之后的歌单。"),
        ("专注工作", "focus", "scenes", 13, "低干扰的背景纹理。"),
        ("明亮时刻", "bright", "moods", 21, "值得被放大的好心情。"),
        ("低落补给", "low", "moods", 22, "不急着振作，先被理解。"),
        ("高能释放", "release", "moods", 23, "把压力交给节奏。"),
        ("创作札记", "notes", "editorial", 31, "关于曲调与情绪的写作。"),
    ]
    for name, slug, parent_slug, sort, desc in children:
        row = db.query(Category).filter(Category.slug == slug).first()
        if not row:
            row = Category(name=name, slug=slug, parent_id=root_map[parent_slug].id, sort=sort, description=desc)
            db.add(row)
            db.flush()
    tag_names = ["钢琴", "环境声", "城市夜景", "低保真", "纯音乐", "女声", "通勤", "治愈", "合成器", "雨声"]
    tags = []
    for name in tag_names:
        tag = db.query(Tag).filter(Tag.name == name).first()
        if not tag:
            tag = Tag(name=name, slug=unique_slug(db, Tag, name, "tag"), post_count=0)
            db.add(tag)
            db.flush()
        tags.append(tag)
    db.commit()
    all_categories = db.query(Category).all()
    return all_categories, tags


def seed_tracks(db: Session) -> list[Track]:
    manifest_path = settings.audio_dir.parent / "tracks.json"
    if not manifest_path.exists():
        logger.warning("tracks_manifest_missing path=%s", manifest_path)
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tracks: list[Track] = []
    for entry in manifest:
        audio_path = Path(settings.media_root) / entry["audio"]
        features: dict = {}
        if audio_path.exists():
            try:
                features = analyze_audio(audio_path)
            except Exception as exc:
                logger.warning("audio_analysis_failed file=%s error=%s", audio_path, str(exc)[:120])
        track = db.query(Track).filter(Track.source == "local", Track.external_id == entry["slug"]).first()
        if not track:
            track = Track(
                title=entry["title"],
                artist=entry["artist"],
                album=entry["album"],
                mood=entry["mood"],
                source="local",
                external_id=entry["slug"],
                local_path=f"media/{entry['audio']}",
                cover_url=f"/media/{entry['cover']}",
                is_public=True,
                license_note=entry["licenseNote"],
            )
            db.add(track)
        track.title = entry["title"]
        track.artist = entry["artist"]
        track.album = entry["album"]
        # 人工试听标签作为先验，音频分析决定连续情绪坐标；两者混合为概率分布。
        if features:
            derived = mood_scores_from_features(features)
            curated = {mood: 0.0 for mood in derived}
            curated[entry["mood"]] = 1.0
            blended = {mood: round(0.55 * derived[mood] + 0.45 * curated[mood], 4) for mood in derived}
            total = sum(blended.values()) or 1
            track.mood_scores = {key: round(value / total, 4) for key, value in blended.items()}
            track.audio_features = {
                **features,
                "analyzedMood": features.get("mood"),
                "curatedMood": entry["mood"],
                "curationWeight": 0.45,
            }
            track.duration_seconds = features.get("duration", 0)
            if not track.mood:
                track.mood = features.get("mood", entry["mood"])
        track.local_path = f"media/{entry['audio']}"
        track.cover_url = f"/media/{entry['cover']}"
        track.license_note = entry["licenseNote"]
        tracks.append(track)
    db.flush()
    return tracks


def seed_items(db: Session, admin: User, demo: User, users: list[User], categories: list[Category], tags: list[Tag], tracks: list[Track]) -> list[Item]:
    category_by_slug = {row.slug: row for row in categories}
    tag_by_name = {row.name: row for row in tags}
    items_data = [
        {
            "owner": demo,
            "title": "把晚高峰调成静音的五首歌",
            "content": "从地铁换乘通道出来，城市的低频还在耳膜里振动。我把这五首放进同一条队列：先让合成器铺开空间，再用钢琴把呼吸收回来。听的时候不必急着放松，先承认疲惫。\n\n推荐顺序：静海 → 白噪咖啡馆 → 雨窗独白 → 未寄出的信 → 悬停。\n\n如果你刚好在情绪识别里得到「低落」，这套顺序会比直接播放高 BPM 的歌更友好。",
            "status": "published",
            "category": "commute",
            "tags": ["通勤", "城市夜景", "纯音乐"],
            "cover": tracks[0].cover_url if tracks else "/media/covers/morning-drift.svg",
        },
        {
            "owner": demo,
            "title": "给愉悦留一点余震",
            "content": "开心的时候不一定需要更吵的歌。真正舒服的是让明亮的旋律在房间里多停留一会儿，让情绪有余震。这份歌单从柠檬气泡开始，最后落在微光惊起。",
            "status": "published",
            "category": "bright",
            "tags": ["合成器", "女声", "治愈"],
            "cover": tracks[1].cover_url if len(tracks) > 1 else "/media/covers/lemon-static.svg",
        },
        {
            "owner": admin,
            "title": "当愤怒需要出口：高能量歌单的编排笔记",
            "content": "愤怒不是需要被立刻消除的状态。我们让节奏先承接它，再逐步把速度降下来。红移与暗涌放在前两首，中段加入低频环境声，最后落到静海。\n\n这是编辑部的「高能释放」分类，也是一次关于推荐边界的设计：不鼓励宣泄伤害，只提供安全的生理出口。",
            "status": "published",
            "category": "release",
            "tags": ["合成器", "城市夜景", "纯音乐"],
            "cover": tracks[4].cover_url if len(tracks) > 4 else "/media/covers/red-shift.svg",
        },
        {
            "owner": demo,
            "title": "深夜房间：三首不需要歌词的歌",
            "content": "晚上十一点之后，语言会变得多余。选三首没有歌词的曲子，让旋律替你把房间的灯调暗。",
            "status": "published",
            "category": "late-night",
            "tags": ["雨声", "环境声", "低保真"],
            "cover": tracks[2].cover_url if len(tracks) > 2 else "/media/covers/rain-window.svg",
        },
        {
            "owner": demo,
            "title": "未完成的专注歌单（草稿）",
            "content": "这个歌单还在整理中。目标是 60 分钟不打断工作流，目前只完成了前 20 分钟。",
            "status": "draft",
            "category": "focus",
            "tags": ["低保真", "纯音乐"],
            "cover": tracks[-1].cover_url if tracks else None,
        },
        {
            "owner": admin,
            "title": "旧版本：关于情绪推荐的五个假设",
            "content": "这是一篇已经被软删除的旧稿，仅用于演示后台与内容生命周期。",
            "status": "deleted",
            "category": "notes",
            "tags": ["治愈"],
            "cover": None,
        },
    ]
    items = []
    for item_data in items_data:
        item = db.query(Item).filter(Item.owner_id == item_data["owner"].id, Item.title == item_data["title"]).first()
        if not item:
            item = Item(
                owner_id=item_data["owner"].id,
                title=item_data["title"],
                content=item_data["content"],
                status=item_data["status"],
                category_id=category_by_slug[item_data["category"]].id if item_data["category"] in category_by_slug else None,
                cover_url=item_data["cover"],
                cover_thumb_url=item_data["cover"],
                deleted_at=utcnow() if item_data["status"] == "deleted" else None,
            )
            db.add(item)
            db.flush()
        else:
            item.content = item_data["content"]
            item.status = item_data["status"]
            item.cover_url = item_data["cover"]
            item.cover_thumb_url = item_data["cover"]
            item.deleted_at = utcnow() if item_data["status"] == "deleted" else None
        for tag_name in item_data["tags"]:
            tag = tag_by_name.get(tag_name)
            if not tag:
                continue
            exists = db.query(PostTag).filter(PostTag.post_id == str(item.id), PostTag.tag_id == tag.id).first()
            if not exists:
                db.add(PostTag(post_id=str(item.id), tag_id=tag.id))
        items.append(item)
    db.flush()
    db.commit()
    # 冗余计数一次性校准
    for category in db.query(Category).all():
        category.post_count = (
            db.query(Item)
            .filter(Item.category_id == category.id, Item.deleted_at.is_(None), Item.status == "published")
            .count()
        )
    for tag in db.query(Tag).all():
        tag.post_count = (
            db.query(PostTag)
            .join(Item, Item.id == cast(PostTag.post_id, Integer))
            .filter(PostTag.tag_id == tag.id, Item.deleted_at.is_(None), Item.status == "published")
            .count()
        )
    db.commit()
    return items


def seed_feedback(db: Session, demo: User, admin: User, items: list[Item]) -> None:
    feedbacks = [
        ("MW-20251101-100001", "bug", "在实时摄像头模式下，连续识别十几次后页面偶发卡顿。希望能限制历史帧的保留数量。", "processing", None),
        ("MW-20251102-100002", "feature", "希望可以为每首歌单帖添加一个可分享的短链，好友打开后能看到 OG 预览。", "resolved", "分享短链已经上线：发布歌单帖后，在详情页点击「分享」即可复制 7 天有效的链接。"),
        ("MW-20251103-100003", "experience", "深色模式下，播放器底部的进度条对比度有点低，夜里不太容易看清。", "open", None),
        ("MW-20251103-100004", "other", "谢谢你们的本地识别，不想把脸传到云端。", "closed", "谢谢你的反馈，这正是我们坚持本地推理的原因。"),
    ]
    for ticket, type_, content, status, reply in feedbacks:
        row = db.query(Feedback).filter(Feedback.ticket_no == ticket).first()
        if not row:
            row = Feedback(
                ticket_no=ticket,
                user_id=demo.id,
                type=type_,
                content=content,
                images=[],
                contact=demo.email,
                status=status,
                handler_id=admin.id if status != "open" else None,
                reply=reply,
                supplementary=[],
            )
            db.add(row)
    db.commit()


def seed_notifications(db: Session, users: list[User], items: list[Item]) -> None:
    for user in users:
        existing = db.query(Notification).filter(Notification.user_id == user.id).first()
        if existing:
            continue
        notes = [
            ("system", "欢迎来到心绪声场", "六种情绪的演示照片已经准备好，打开摄像头或上传照片即可开始。", "system", "welcome"),
            ("security", "登录提醒", "你的账号刚刚在 127.0.0.*** 的设备上登录。如非本人操作，请前往账号安全下线该设备。", "security", "seed"),
            ("approval", "账号权限说明", "角色变更会立即生效；前端隐藏按钮只是体验优化，真正的权限校验发生在服务端。", "approval", "seed"),
        ]
        if items:
            notes.append(("comment", "你的歌单收到一条新回复", f"有人喜欢你的歌单《{items[0].title}》。", "item", str(items[0].id)))
        for type_, title, message, target_type, target_id in notes:
            exists = (
                db.query(Notification)
                .filter(
                    Notification.user_id == user.id,
                    Notification.target_type == target_type,
                    Notification.target_id == target_id,
                )
                .first()
            )
            if not exists:
                db.add(
                    Notification(
                        user_id=user.id,
                        type=type_,
                        title=title,
                        message=message,
                        target_type=target_type,
                        target_id=target_id,
                        payload={},
                    )
                )
    db.flush()
    for user in users:
        user.unread_count = db.query(Notification).filter(Notification.user_id == user.id, Notification.read_at.is_(None)).count()
    db.commit()


def seed_banners(db: Session) -> None:
    banners = [
        {
            "position": "home",
            "position_code": 0,
            "title": "让旋律回应此刻的表情",
            "subtitle": "本地识别，不上传人脸；音乐情绪由曲调特征计算。",
            "image_url": "/media/banners/banner-hero.svg",
            "link_url": "/algorithms",
            "aspect_ratio": "16/5",
            "sort": 1,
        },
        {
            "position": "home",
            "position_code": 0,
            "title": "六种情绪，六条声场路径",
            "subtitle": "从一张照片开始，找到适配当前唤醒度的歌单。",
            "image_url": "/media/banners/banner-arch.svg",
            "link_url": "/#scanner",
            "aspect_ratio": "16/5",
            "sort": 2,
        },
        {
            "position": "discover",
            "position_code": 1,
            "title": "夜晚的更慢一些",
            "subtitle": "低唤醒歌单与夜间模式已经上线。",
            "image_url": "/media/banners/banner-night.svg",
            "link_url": "/categories/late-night",
            "aspect_ratio": "16/5",
            "sort": 1,
        },
    ]
    for entry in banners:
        row = db.query(Banner).filter(Banner.title == entry["title"], Banner.position_code == entry["position"]).first()
        if not row:
            row = Banner(
                position=entry["position_code"],
                position_code=entry["position"],
                title=entry["title"],
                subtitle=entry["subtitle"],
                image_url=entry["image_url"],
                link_url=entry["link_url"],
                sort=entry["sort"],
                status="active",
                aspect_ratio=entry["aspect_ratio"],
                start_at=utcnow() - timedelta(days=2),
                end_at=utcnow() + timedelta(days=90),
            )
            db.add(row)
    db.commit()


def seed_channels(db: Session) -> None:
    channels = [
        ("inapp", "站内通知", "internal"),
        ("email", "邮件", "smtp"),
        ("sms", "短信", "sms"),
        ("push", "App 推送", "webpush"),
    ]
    for code, name, provider in channels:
        row = db.query(PushChannel).filter(PushChannel.code == code).first()
        if not row:
            db.add(PushChannel(code=code, name=name, provider=provider, config={}, status="active"))
    db.commit()


def seed_push_settings(db: Session, demo: User) -> None:
    for code, enabled in [("inapp", True), ("email", True), ("sms", False), ("push", False)]:
        row = db.query(UserPushSetting).filter(UserPushSetting.user_id == demo.id, UserPushSetting.channel_code == code).first()
        if not row:
            db.add(UserPushSetting(user_id=demo.id, channel_code=code, enabled=enabled, quiet_hours=True))
    db.commit()


def seed_events(db: Session, users: list[User]) -> None:
    defs = [
        ("page_view", "页面浏览", "navigation"),
        ("emotion_scan_started", "开始情绪识别", "emotion"),
        ("emotion_detected", "完成情绪识别", "emotion"),
        ("recommendation_viewed", "查看推荐结果", "recommendation"),
        ("music_play", "播放曲目", "music"),
        ("favorite_added", "收藏曲目", "music"),
        ("login_success", "登录成功", "auth"),
        ("signup_success", "注册成功", "auth"),
        ("search", "搜索", "search"),
        ("feedback_submit", "提交反馈", "feedback"),
        ("share_created", "创建分享", "share"),
    ]
    for key, name, category in defs:
        if not db.query(EventDef).filter(EventDef.key == key).first():
            db.add(EventDef(key=key, name=name, category=category, status="active", props_schema={}))
    db.flush()
    if db.query(Event).count() > 0:
        db.commit()
        return
    rng = random.Random(20251103)
    now = utcnow()
    session_counter = 0
    for user in users:
        for age_days in range(0, 22, 3):
            base = now - timedelta(days=age_days)
            session_counter += 1
            session_id = f"seed{user.id:02d}{age_days:02d}{session_counter:03d}"
            sequence = ["page_view", "emotion_scan_started", "emotion_detected", "recommendation_viewed", "music_play", "favorite_added"]
            stop = rng.choice([2, 3, 3, 4, 5, 6])
            for index, event_key in enumerate(sequence[:stop]):
                db.add(
                    Event(
                        event_key=event_key,
                        user_id=None,
                        user_hash=hash_user_id(user.id),
                        session_id=session_id,
                        page=0,
                        props={"route": "/", "seed": True, "emotion": rng.choice(["happy", "sad", "neutral", "angry", "fear", "surprised"]) if event_key == "emotion_detected" else None},
                        occurred_at=base - timedelta(minutes=(len(sequence) - index) * 9),
                    )
                )
    db.commit()


def seed_funnels(db: Session, admin: User) -> None:
    definition = db.query(Funnel).filter(Funnel.name == "情绪识别到播放").first()
    if not definition:
        definition = Funnel(
            name="情绪识别到播放",
            steps=[
                {"eventKey": "page_view", "label": "进入首页"},
                {"eventKey": "emotion_scan_started", "label": "开始识别"},
                {"eventKey": "emotion_detected", "label": "识别成功"},
                {"eventKey": "recommendation_viewed", "label": "看到推荐"},
                {"eventKey": "music_play", "label": "播放曲目"},
                {"eventKey": "favorite_added", "label": "收藏"},
            ],
            created_by=admin.id,
        )
        db.add(definition)
    if not db.query(Funnel).filter(Funnel.name == "注册转化").first():
        db.add(
            Funnel(
                name="注册转化",
                steps=[
                    {"eventKey": "page_view", "label": "访问"},
                    {"eventKey": "signup_success", "label": "注册成功"},
                    {"eventKey": "emotion_detected", "label": "首次识别"},
                ],
                created_by=admin.id,
            )
        )
    db.commit()


def seed_misc(db: Session, demo: User, admin: User, tracks: list[Track]) -> None:
    for keyword, count in [("愉悦", 12), ("雨夜", 9), ("lofi", 7), ("通勤", 6), ("钢琴", 5)]:
        if not db.query(SearchLog).filter(SearchLog.keyword == keyword, SearchLog.user_id == demo.id).first():
            db.add(SearchLog(user_id=demo.id, keyword=keyword, result_count=count))
    if tracks and not db.query(FavoriteTrack).filter(FavoriteTrack.user_id == demo.id).first():
        for track in tracks[:2]:
            db.add(FavoriteTrack(user_id=demo.id, track_id=track.id))
            track.like_count += 1
    if not db.query(InviteCode).filter(InviteCode.code == "MOODWAVE-DEMO").first():
        db.add(
            InviteCode(
                code="MOODWAVE-DEMO",
                created_by=admin.id,
                expires_at=utcnow() + timedelta(days=365),
            )
        )
    rows = db.query(Item).filter(Item.status == "published", Item.deleted_at.is_(None)).limit(1).all()
    if rows:
        exists = db.query(ShareLink).filter(ShareLink.code == "demo2026").first()
        if not exists:
            db.add(
                ShareLink(
                    code="demo2026",
                    target_type="item",
                    target_id=str(rows[0].id),
                    created_by=demo.id,
                    expires_at=utcnow() + timedelta(days=30),
                )
            )
    db.commit()


def run_seed() -> None:
    init_db()
    with session_scope() as db:
        admin, demo = seed_users(db)
        db.commit()
        categories, tags = seed_taxonomy(db)
        tracks = seed_tracks(db)
        db.commit()
        users = db.query(User).filter(User.status.in_(["active", "pending"])).all()
        items = seed_items(db, admin, demo, users, categories, tags, tracks)
        seed_feedback(db, demo, admin, items)
        seed_notifications(db, users, items)
        seed_banners(db)
        seed_channels(db)
        seed_push_settings(db, demo)
        seed_events(db, [user for user in users if user.status == "active"])
        seed_funnels(db, admin)
        seed_misc(db, demo, admin, tracks)
        logger.info("seed_completed users=%s tracks=%s items=%s", len(users), len(tracks), len(items))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run_seed()
    print("Seed completed. Demo accounts:")
    print(f"  admin: {settings.seed_admin_email} / (password from SEED_ADMIN_PASSWORD)")
    print(f"  user : {settings.seed_user_email} / (password from SEED_USER_PASSWORD)")


if __name__ == "__main__":
    main()
