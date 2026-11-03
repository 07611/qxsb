"""签名直传、附件登记与删除。"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..errors import APIError, success
from ..models import Attachment, User
from ..security import get_current_user
from ..serializers import attachment_public
from ..services.ratelimit import enforce
from ..services.storage import (
    ALLOWED_IMAGE_MIME,
    ALLOWED_MIME,
    _safe_path,
    delete_file,
    parse_upload_token,
    presign,
    process_uploaded_file,
    sniff_mime,
    verify_registered_upload,
)

router = APIRouter(prefix="/api/v1", tags=["uploads"])
logger = logging.getLogger("moodwave.uploads")


class PresignIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime: str = Field(min_length=3, max_length=100)
    size: int = Field(gt=0)
    bizType: str = Field(default="item_cover", max_length=50)


class AttachmentIn(BaseModel):
    uploadToken: str = Field(min_length=20)
    bizType: str = Field(default="general", max_length=50)
    bizId: str | None = Field(default=None, max_length=64)


@router.post("/upload/presign")
def presign_upload(
    payload: PresignIn,
    request: Request,
    user: User = Depends(get_current_user),
):
    enforce(request, "upload:presign", limit=60, window_seconds=3600, discriminator=str(user.id))
    # 单次批量上传最多 9 张：以 10 秒窗口的突发限流兜底
    enforce(request, "upload:presign:burst", limit=9, window_seconds=10, discriminator=str(user.id))
    if payload.mime not in ALLOWED_MIME:
        raise APIError(422, "不支持的文件类型")
    data = presign(user.id, payload.filename, payload.mime, payload.size)
    data["bizType"] = payload.bizType
    return success(data)


@router.put("/upload/put/{token}")
async def direct_upload(token: str, request: Request):
    """浏览器直传入口。凭证里冻结了用户、MIME、大小上限与对象键。"""
    payload = parse_upload_token(token)
    target = _safe_path(payload["key"])
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".part")
    written = 0
    head = b""
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    if content_type and content_type != payload["mime"]:
        raise APIError(422, f"Content-Type 与申请不一致，应为 {payload['mime']}")
    try:
        with temp.open("wb") as handle:
            async for chunk in request.stream():
                if not chunk:
                    continue
                if not head:
                    head = chunk[:64]
                written += len(chunk)
                if written > payload["max"]:
                    raise APIError(413, "文件超过大小限制")
                handle.write(chunk)
        if written == 0:
            raise APIError(422, "上传内容为空")
        detected = sniff_mime(head)
        if detected != payload["mime"]:
            raise APIError(422, f"文件头校验失败：声明 {payload['mime']}，实际 {detected or '未知'}")
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)
    metadata = process_uploaded_file(target, payload["key"], payload["mime"], payload["uid"])
    metadata.update({"uploadToken": token, "size": written})
    return success(metadata)


@router.post("/attachments")
def create_attachment(
    payload: AttachmentIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enforce(request, "attachments:create", limit=120, window_seconds=3600, discriminator=str(user.id))
    metadata = verify_registered_upload(payload.uploadToken, user.id)
    existing = db.query(Attachment).filter(Attachment.storage_key == metadata["key"], Attachment.owner_id == user.id).first()
    if existing:
        return success({"attachment": attachment_public(existing)})
    attachment = Attachment(
        owner_id=user.id,
        biz_type=payload.bizType,
        biz_id=payload.bizId,
        url=metadata["url"],
        thumb_url=metadata["thumbUrl"],
        detail_url=metadata["detailUrl"],
        storage_key=metadata["key"],
        mime=metadata["mime"],
        size_bytes=int(metadata.get("size") or 0),
        width=metadata["width"],
        height=metadata["height"],
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return success({"attachment": attachment_public(attachment)}, status_code=201)


@router.delete("/attachments/{attachment_id}")
def delete_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(Attachment, attachment_id)
    if not row:
        raise APIError(404, "附件不存在")
    if row.owner_id != user.id and user.role != "admin":
        raise APIError(403, "无权删除他人的附件")
    delete_file(row.url)
    delete_file(row.thumb_url)
    delete_file(row.detail_url)
    db.delete(row)
    db.commit()
    return success({"deleted": True, "id": attachment_id})
