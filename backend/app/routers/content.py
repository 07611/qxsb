"""歌单帖 CRUD、分类标签、全文搜索。"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import Integer, cast, func, or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db, session_scope
from ..errors import APIError, success
from ..models import Attachment, Category, Item, PostTag, SearchLog, Tag, Track, User, utcnow
from ..security import get_current_user, get_optional_user, has_permission, require_permission
from ..serializers import category_public, item_public, tag_public, track_public
from ..services.cache import cache
from ..services.ratelimit import enforce
from ..utils import (
    clean_text,
    escape_like,
    highlight_snippet,
    page_params,
    paginate,
    parse_datetime,
    slugify,
    unique_slug,
)

router = APIRouter(prefix="/api/v1", tags=["content"])
logger = logging.getLogger("moodwave.content")


class ItemCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=1, max_length=20000)
    categoryId: int | None = None
    tags: list[str] = Field(default_factory=list, max_length=8)
    coverUrl: str | None = None
    coverThumbUrl: str | None = None
    status: str = "published"

    def normalized(self) -> "ItemCreate":
        self.title = clean_text(self.title, max_len=120, keep_newlines=False)
        self.content = clean_text(self.content, max_len=20000)
        self.tags = [clean_text(tag, max_len=20, keep_newlines=False) for tag in self.tags if clean_text(tag)]
        if len(self.title) < 2:
            raise APIError(422, "标题至少 2 个字符")
        if not self.content:
            raise APIError(422, "正文不能为空")
        if self.status not in {"published", "draft"}:
            raise APIError(422, "状态只能是 published 或 draft")
        return self


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    slug: str | None = Field(default=None, max_length=60)
    parentId: int | None = None
    sort: int = 0
    description: str | None = Field(default=None, max_length=200)


def _category_depth(db: Session, category: Category) -> int:
    depth = 1
    seen = {category.id}
    parent_id = category.parent_id
    while parent_id:
        if parent_id in seen:
            raise APIError(409, "分类层级存在循环")
        parent = db.get(Category, parent_id)
        if not parent:
            break
        seen.add(parent.id)
        depth += 1
        parent_id = parent.parent_id
        if depth > 3:
            break
    return depth


def _recount_category(category_id: int) -> None:
    with session_scope() as db:
        category = db.get(Category, category_id)
        if not category:
            return
        count = db.query(Item).filter(Item.category_id == category_id, Item.deleted_at.is_(None), Item.status == "published").count()
        category.post_count = count


def _recount_tags(tag_ids: list[int]) -> None:
    with session_scope() as db:
        for tag_id in tag_ids:
            tag = db.get(Tag, tag_id)
            if not tag:
                continue
            count = (
                db.query(PostTag)
                .join(Item, Item.id == cast(PostTag.post_id, Integer))
                .filter(PostTag.tag_id == tag_id, Item.deleted_at.is_(None), Item.status == "published")
                .count()
            )
            tag.post_count = count


def _resolve_tags(db: Session, names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    for name in names[:8]:
        clean_name = clean_text(name, max_len=20, keep_newlines=False)
        if not clean_name:
            continue
        tag = db.query(Tag).filter(Tag.name == clean_name).first()
        if not tag:
            tag = Tag(name=clean_name, slug=unique_slug(db, Tag, clean_name, "tag"), post_count=0)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


def _sync_post_tags(db: Session, item_id: int, tags: list[Tag]) -> list[int]:
    previous = db.query(PostTag).filter(PostTag.post_id == str(item_id)).all()
    previous_ids = [row.tag_id for row in previous]
    for row in previous:
        db.delete(row)
    db.flush()
    for tag in tags:
        db.add(PostTag(post_id=str(item_id), tag_id=tag.id))
    db.flush()
    affected = list(set(previous_ids + [tag.id for tag in tags]))
    return affected


def _validate_cover(db: Session, user: User, url: str | None, thumb: str | None) -> tuple[str | None, str | None]:
    if not url:
        return None, None
    if url.startswith("/media/"):
        attachment = db.query(Attachment).filter(Attachment.owner_id == user.id, Attachment.url == url).first()
        if not attachment:
            raise APIError(422, "封面附件不属于当前用户或尚未登记")
        return attachment.detail_url or attachment.url, attachment.thumb_url or thumb or attachment.url
    if url.startswith("https://") and url == thumb:
        # 兼容演示种子数据中的稳定外链占位图，仅允许 https 且不带脚本
        return url, thumb
    raise APIError(422, "封面地址不合法，请通过附件上传获取")


@router.get("/items")
def list_items(
    request: Request,
    q: str | None = Query(default=None, max_length=50),
    category: str | None = None,
    tag: str | None = None,
    mine: bool = False,
    status: str | None = None,
    page: int = 1,
    pageSize: int = 12,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    query = (
        db.query(Item)
        .options(joinedload(Item.owner), joinedload(Item.category))
        .filter(Item.deleted_at.is_(None))
    )
    if mine:
        if not user:
            raise APIError(401, "请先登录")
        query = query.filter(Item.owner_id == user.id)
    else:
        query = query.filter(Item.status == "published")
    if status:
        can_see_all = bool(user and (mine or has_permission(db, user, "content:manage")))
        if status not in {"published", "draft"} or not can_see_all:
            status = "published"
        query = query.filter(Item.status == status)
    if category:
        category_row = db.query(Category).filter(Category.slug == category).first()
        if not category_row:
            return success({"items": [], "pagination": {"page": page, "pageSize": size, "total": 0, "pages": 1, "hasNext": False}})
        query = query.filter(Item.category_id == category_row.id)
    if tag:
        tag_row = db.query(Tag).filter(Tag.slug == tag).first()
        if not tag_row:
            return success({"items": [], "pagination": {"page": page, "pageSize": size, "total": 0, "pages": 1, "hasNext": False}})
        query = query.join(PostTag, cast(PostTag.post_id, Integer) == Item.id).filter(PostTag.tag_id == tag_row.id)
    if q:
        keyword = clean_text(q, max_len=50, keep_newlines=False)
        like = f"%{escape_like(keyword)}%"
        query = query.filter(or_(Item.title.like(like, escape="\\"), Item.content.like(like, escape="\\")))
    query = query.order_by(Item.created_at.desc())
    rows, meta = paginate(query, page, size)
    return success(
        {
            "items": [item_public(db, item) for item in rows],
            "pagination": meta,
        }
    )


@router.get("/items/{item_id}")
def get_item(item_id: int, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    item = (
        db.query(Item)
        .options(joinedload(Item.owner), joinedload(Item.category))
        .filter(Item.id == item_id, Item.deleted_at.is_(None))
        .first()
    )
    if not item:
        raise APIError(404, "内容不存在")
    if item.status != "published":
        if not user:
            raise APIError(401, "请先登录")
        if item.owner_id != user.id and not has_permission(db, user, "content:manage"):
            raise APIError(403, "无权查看该草稿")
    data = item_public(db, item, detail=True)
    data["canEdit"] = bool(user and (item.owner_id == user.id or has_permission(db, user, "content:manage")))
    return success({"item": data})


@router.post("/items")
def create_item(
    payload: ItemCreate,
    request: Request,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce(request, "content:item:create", limit=10, window_seconds=600, discriminator=str(user.id))
    payload = payload.normalized()
    category = None
    if payload.categoryId:
        category = db.get(Category, payload.categoryId)
        if not category:
            raise APIError(422, "分类不存在")
        if _category_depth(db, category) > 2:
            raise APIError(422, "分类最多支持两级")
    cover, thumb = _validate_cover(db, user, payload.coverUrl, payload.coverThumbUrl)
    item = Item(
        owner_id=user.id,
        title=payload.title,
        content=payload.content,
        status=payload.status,
        category_id=category.id if category else None,
        cover_url=cover,
        cover_thumb_url=thumb,
    )
    db.add(item)
    db.flush()
    tags = _resolve_tags(db, payload.tags)
    affected = _sync_post_tags(db, item.id, tags)
    db.commit()
    db.refresh(item)
    if category:
        background.add_task(_recount_category, category.id)
    background.add_task(_recount_tags, affected)
    return success({"item": item_public(db, item, detail=True)}, status_code=201)


@router.put("/items/{item_id}")
def update_item(
    item_id: int,
    payload: ItemCreate,
    background: BackgroundTasks,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce(request, "content:item:update", limit=30, window_seconds=600, discriminator=str(user.id))
    item = db.query(Item).filter(Item.id == item_id, Item.deleted_at.is_(None)).first()
    if not item:
        raise APIError(404, "内容不存在")
    if item.owner_id != user.id and not has_permission(db, user, "content:manage"):
        raise APIError(403, "无权修改他人的内容")
    payload = payload.normalized()
    category = None
    if payload.categoryId:
        category = db.get(Category, payload.categoryId)
        if not category:
            raise APIError(422, "分类不存在")
        if _category_depth(db, category) > 2:
            raise APIError(422, "分类最多支持两级")
    cover, thumb = _validate_cover(db, user, payload.coverUrl, payload.coverThumbUrl)
    old_category = item.category_id
    item.title = payload.title
    item.content = payload.content
    item.status = payload.status
    item.category_id = category.id if category else None
    item.cover_url = cover
    item.cover_thumb_url = thumb
    tags = _resolve_tags(db, payload.tags)
    affected = _sync_post_tags(db, item.id, tags)
    db.commit()
    db.refresh(item)
    for cat_id in {old_category, item.category_id}:
        if cat_id:
            background.add_task(_recount_category, cat_id)
    background.add_task(_recount_tags, affected)
    return success({"item": item_public(db, item, detail=True)})


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    background: BackgroundTasks,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(Item).filter(Item.id == item_id, Item.deleted_at.is_(None)).first()
    if not item:
        raise APIError(404, "内容不存在")
    if item.owner_id != user.id and not has_permission(db, user, "content:manage"):
        raise APIError(403, "无权删除他人的内容")
    category_id = item.category_id
    affected = [row.tag_id for row in db.query(PostTag).filter(PostTag.post_id == str(item.id)).all()]
    item.deleted_at = utcnow()
    item.status = "deleted"
    if has_permission(db, user, "content:manage"):
        from ..models import AuditLog
        from ..services.ratelimit import get_client_ip

        db.add(
            AuditLog(
                actor_id=user.id,
                action="item.delete",
                target_type="item",
                target_id=str(item.id),
                detail={"title": item.title, "ownerId": item.owner_id},
                ip=get_client_ip(request)[:64],
            )
        )
    db.commit()
    if category_id:
        background.add_task(_recount_category, category_id)
    background.add_task(_recount_tags, affected)
    return success({"deleted": True, "id": item_id})


# ── 分类与标签 ──────────────────────────────────────────────────────────
@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    cached = cache.get("taxonomy:categories:v2")
    if cached is not None:
        return success(cached)
    rows = db.query(Category).order_by(Category.sort.asc(), Category.id.asc()).all()
    nodes = {row.id: {**category_public(row), "children": []} for row in rows}
    tree = []
    for row in rows:
        node = nodes[row.id]
        if row.parent_id and row.parent_id in nodes:
            nodes[row.parent_id]["children"].append(node)
        else:
            tree.append(node)
    payload = {"categories": tree, "flat": [category_public(row) for row in rows]}
    cache.set("taxonomy:categories:v2", payload, 120)
    return success(payload)


@router.get("/categories/{slug}")
def get_category(slug: str, db: Session = Depends(get_db)):
    row = db.query(Category).filter(Category.slug == slug).first()
    if not row:
        raise APIError(404, "分类不存在")
    data = category_public(row)
    data["children"] = [category_public(child) for child in db.query(Category).filter(Category.parent_id == row.id).all()]
    return success({"category": data})


@router.post("/admin/categories")
def create_category(
    payload: CategoryIn,
    admin: User = Depends(require_permission("categories:manage")),
    db: Session = Depends(get_db),
):
    name = clean_text(payload.name, max_len=40, keep_newlines=False)
    if len(name) < 2:
        raise APIError(422, "分类名称至少 2 个字符")
    parent = None
    if payload.parentId:
        parent = db.get(Category, payload.parentId)
        if not parent:
            raise APIError(422, "父分类不存在")
        if parent.parent_id:
            raise APIError(422, "最多支持两级分类，不能在子分类下继续创建")
    slug_value = payload.slug or slugify(name, "category")
    if db.query(Category).filter(Category.slug == slug_value).first():
        raise APIError(409, "分类 slug 已存在")
    row = Category(
        name=name,
        slug=slug_value,
        parent_id=parent.id if parent else None,
        sort=payload.sort,
        description=clean_text(payload.description, max_len=200),
    )
    db.add(row)
    db.commit()
    cache.delete_prefix("taxonomy:categories")
    return success({"category": category_public(row)}, status_code=201)


@router.patch("/admin/categories/{category_id}")
def update_category(
    category_id: int,
    payload: CategoryIn,
    admin: User = Depends(require_permission("categories:manage")),
    db: Session = Depends(get_db),
):
    row = db.get(Category, category_id)
    if not row:
        raise APIError(404, "分类不存在")
    if payload.parentId == category_id:
        raise APIError(422, "不能将分类设为自己的子分类")
    parent = None
    if payload.parentId:
        parent = db.get(Category, payload.parentId)
        if not parent:
            raise APIError(422, "父分类不存在")
        if parent.parent_id:
            raise APIError(422, "最多支持两级分类")
    row.name = clean_text(payload.name, max_len=40, keep_newlines=False)
    row.parent_id = parent.id if parent else None
    row.sort = payload.sort
    row.description = clean_text(payload.description, max_len=200)
    if payload.slug and payload.slug != row.slug:
        if db.query(Category).filter(Category.slug == payload.slug, Category.id != row.id).first():
            raise APIError(409, "分类 slug 已存在")
        row.slug = payload.slug
    db.commit()
    cache.delete_prefix("taxonomy:categories")
    return success({"category": category_public(row)})


@router.delete("/admin/categories/{category_id}")
def delete_category(
    category_id: int,
    admin: User = Depends(require_permission("categories:manage")),
    db: Session = Depends(get_db),
):
    row = db.get(Category, category_id)
    if not row:
        raise APIError(404, "分类不存在")
    children = db.query(Category).filter(Category.parent_id == row.id).count()
    posts = db.query(Item).filter(Item.category_id == row.id, Item.deleted_at.is_(None)).count()
    if children or posts:
        raise APIError(409, "该分类下仍有子分类或内容，请先迁移后再删除")
    db.delete(row)
    db.commit()
    cache.delete_prefix("taxonomy:categories")
    return success({"deleted": True})


@router.get("/tags")
def list_tags(
    sort: str = Query(default="hot", pattern="^(hot|name)$"),
    page: int = 1,
    pageSize: int = 30,
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize, max_size=100)
    cache_key = f"taxonomy:tags:{sort}:{page}:{size}:v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return success(cached)
    query = db.query(Tag)
    query = query.order_by(Tag.post_count.desc(), Tag.id.asc()) if sort == "hot" else query.order_by(Tag.name.asc())
    rows, meta = paginate(query, page, size)
    payload = {"tags": [tag_public(tag) for tag in rows], "pagination": meta}
    cache.set(cache_key, payload, 60)
    return success(payload)


@router.get("/tags/{slug}")
def get_tag(slug: str, db: Session = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.slug == slug).first()
    if not tag:
        raise APIError(404, "标签不存在")
    return success({"tag": tag_public(tag)})


# ── 搜索 ────────────────────────────────────────────────────────────────
@router.get("/search")
def search(
    request: Request,
    q: str = Query(min_length=1, max_length=50),
    type: str = Query(default="all", pattern="^(all|items|tracks)$"),
    page: int = 1,
    pageSize: int = 10,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    page, size = page_params(page, pageSize)
    keyword = clean_text(q, max_len=50, keep_newlines=False)
    if not keyword:
        raise APIError(422, "请输入搜索关键词")
    like = f"%{escape_like(keyword)}%"
    item_rows: list[Item] = []
    tag_rows: list[Track] = []
    item_total = track_total = 0
    if type in {"all", "items"}:
        item_query = (
            db.query(Item)
            .options(joinedload(Item.owner), joinedload(Item.category))
            .filter(
                Item.deleted_at.is_(None),
                Item.status == "published",
                or_(Item.title.like(like, escape="\\"), Item.content.like(like, escape="\\")),
            )
            .order_by(Item.created_at.desc())
        )
        item_total = item_query.count()
        item_rows = item_query.offset((page - 1) * size).limit(size).all()
    if type in {"all", "tracks"}:
        track_query = db.query(Track).filter(
            Track.is_public.is_(True),
            or_(Track.title.like(like, escape="\\"), Track.artist.like(like, escape="\\"), Track.mood.like(like, escape="\\")),
        )
        track_total = track_query.count()
        tag_rows = track_query.order_by(Track.play_count.desc()).offset((page - 1) * size).limit(size).all()
    total = item_total + track_total
    log = SearchLog(user_id=user.id if user else None, keyword=keyword, result_count=total)
    db.add(log)
    db.commit()
    cache.delete("search:hot:v1")
    return success(
        {
            "keyword": keyword,
            "type": type,
            "results": {
                "items": [
                    {
                        **item_public(db, item),
                        "highlight": highlight_snippet(f"{item.title} {item.content}", keyword),
                    }
                    for item in item_rows
                ],
                "tracks": [
                    {
                        **track_public(track),
                        "highlight": highlight_snippet(f"{track.title} {track.artist} {track.mood}", keyword),
                    }
                    for track in tag_rows
                ],
            },
            "pagination": {
                "page": page,
                "pageSize": size,
                "total": total,
                "pages": max(1, (total + size - 1) // size),
                "hasNext": page * size < total,
                "itemTotal": item_total,
                "trackTotal": track_total,
            },
        }
    )


@router.get("/search/hot")
def hot_searches(db: Session = Depends(get_db)):
    cached = cache.get("search:hot:v1")
    if cached is not None:
        return success(cached)
    since = utcnow() - timedelta(days=30)
    rows = (
        db.query(SearchLog.keyword, func.count(SearchLog.id).label("count"))
        .filter(SearchLog.created_at >= since)
        .group_by(SearchLog.keyword)
        .order_by(func.count(SearchLog.id).desc())
        .limit(10)
        .all()
    )
    fallback = ["愉悦", "雨夜", "lofi", "通勤", "钢琴", "sad", "惊喜"]
    keywords = [{"keyword": keyword, "count": count} for keyword, count in rows]
    if len(keywords) < 5:
        existing = {item["keyword"] for item in keywords}
        for word in fallback:
            if word not in existing:
                keywords.append({"keyword": word, "count": 0})
    payload = {"keywords": keywords[:10]}
    cache.set("search:hot:v1", payload, 60)
    return success(payload)
