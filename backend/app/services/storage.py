"""本地签名直传、文件头嗅探、缩略图流水线。

存储驱动采用任务书锁定的「本地磁盘 + 静态服务」；上传链路仍是
申请签名 URL → 浏览器直传 → 服务端校验 → 登记附件，应用层不解析业务请求体。
如需切换 R2/S3，只需实现同一 StorageDriver 协议。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import mimetypes
import os
import secrets
import time
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from ..config import settings
from ..errors import APIError

ALLOWED_IMAGE_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
ALLOWED_VIDEO_MIME = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}
ALLOWED_DOC_MIME = {
    "application/pdf": ".pdf",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/ogg": ".ogg",
}
ALLOWED_MIME = {**ALLOWED_IMAGE_MIME, **ALLOWED_VIDEO_MIME, **ALLOWED_DOC_MIME}


def sniff_mime(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"qt  ",):
            return "video/quicktime"
        if brand in (b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V "):
            return "video/mp4"
        return "video/mp4"
    if head.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    return None


def extension_for(mime: str) -> str:
    return ALLOWED_MIME.get(mime) or mimetypes.guess_extension(mime) or ".bin"


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(payload: bytes) -> str:
    return hmac.new(settings.jwt_secret.encode(), payload, hashlib.sha256).hexdigest()


def create_upload_token(user_id: int, mime: str, size: int, key: str, max_size: int) -> str:
    payload = {
        "uid": user_id,
        "mime": mime,
        "size": int(size),
        "max": int(max_size),
        "key": key,
        "exp": int(time.time()) + min(settings.presign_expire_seconds, 600),
        "nonce": secrets.token_urlsafe(6),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return _b64encode(raw) + "." + _sign(raw)


def parse_upload_token(token: str, expected_user_id: int | None = None) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        raw = _b64decode(encoded)
        if not hmac.compare_digest(_sign(raw), signature):
            raise ValueError("bad signature")
        payload = json.loads(raw)
    except Exception as exc:
        raise APIError(400, "上传凭证无效，请重新获取") from exc
    if int(payload.get("exp", 0)) < int(time.time()):
        raise APIError(410, "上传地址已过期，请重新获取")
    if expected_user_id is not None and int(payload.get("uid", 0)) != expected_user_id:
        raise APIError(403, "上传凭证不属于当前用户")
    return payload


def validate_declared_file(filename: str, mime: str, size: int) -> int:
    if not filename:
        raise APIError(422, "缺少文件名")
    if size <= 0:
        raise APIError(422, "文件为空")
    if mime not in ALLOWED_MIME:
        raise APIError(422, "不支持的文件类型")
    if mime in ALLOWED_IMAGE_MIME:
        limit = settings.max_image_mb * 1024 * 1024
    elif mime in ALLOWED_VIDEO_MIME:
        limit = settings.max_video_mb * 1024 * 1024
    else:
        limit = 20 * 1024 * 1024
    if size > limit:
        raise APIError(413, f"文件超过 {limit // (1024 * 1024)}MB 限制")
    return limit


def presign(user_id: int, filename: str, mime: str, size: int) -> dict:
    limit = validate_declared_file(filename, mime, size)
    ext = ALLOWED_MIME[mime]
    key = f"uploads/{user_id}/{time.strftime('%Y%m')}/{secrets.token_hex(16)}{ext}"
    token = create_upload_token(user_id, mime, size, key, limit)
    return {
        "driver": "local-signed",
        "key": key,
        "uploadToken": token,
        "uploadUrl": f"/api/v1/upload/put/{token}",
        "method": "PUT",
        "headers": {"Content-Type": mime},
        "expiresIn": min(settings.presign_expire_seconds, 600),
        "maxSize": limit,
        "mime": mime,
    }


def _safe_path(key: str) -> Path:
    media_root = Path(settings.media_root).resolve()
    target = (media_root / key).resolve()
    if media_root not in target.parents and target != media_root:
        raise APIError(400, "非法文件路径")
    return target


def save_direct_upload(token: str, content_type: str | None, stream: BinaryIO, user_id: int) -> dict:
    payload = parse_upload_token(token, user_id)
    expected_mime = payload["mime"]
    actual_type = (content_type or "").split(";")[0].strip()
    if actual_type and actual_type != expected_mime:
        raise APIError(422, f"Content-Type 与申请不一致，应为 {expected_mime}")
    target = _safe_path(payload["key"])
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".part")
    written = 0
    head = b""
    try:
        with temp.open("wb") as handle:
            while True:
                chunk = stream.read(1024 * 256)
                if not chunk:
                    break
                if not head:
                    head = chunk[:64]
                written += len(chunk)
                if written > payload["max"]:
                    raise APIError(413, "文件超过大小限制")
                handle.write(chunk)
        if written == 0:
            raise APIError(422, "上传内容为空")
        detected = sniff_mime(head)
        if detected != expected_mime:
            raise APIError(422, f"文件头校验失败：声明 {expected_mime}，实际 {detected or '未知'}")
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)
    metadata = process_uploaded_file(target, payload["key"], expected_mime, user_id)
    metadata["uploadToken"] = token
    metadata["size"] = written
    return metadata


def process_uploaded_file(target: Path, key: str, mime: str, user_id: int) -> dict:
    url = f"/media/{key}"
    result = {
        "key": key,
        "url": url,
        "thumbUrl": url,
        "detailUrl": url,
        "mime": mime,
        "width": 0,
        "height": 0,
    }
    if mime not in ALLOWED_IMAGE_MIME:
        return result
    try:
        with Image.open(target) as image:
            image = ImageOps.exif_transpose(image)
            width, height = image.size
            result["width"], result["height"] = width, height
            if image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, "#FBFAF7")
                converted = image.convert("RGBA")
                background.paste(converted, mask=converted.split()[-1])
                image = background
            else:
                image = image.convert("RGB")
            stem = key.rsplit(".", 1)[0]
            thumb_paths = {}
            for size in (400, 1200):
                thumb_key = f"thumbs/{user_id}/{Path(stem).name}_{size}.webp"
                thumb_target = _safe_path(thumb_key)
                thumb_target.parent.mkdir(parents=True, exist_ok=True)
                rendered = image.copy()
                rendered.thumbnail((size, size), Image.Resampling.LANCZOS)
                rendered.save(thumb_target, "WEBP", quality=84, method=4)
                thumb_paths[size] = f"/media/{thumb_key}"
            result["thumbUrl"] = thumb_paths[400]
            result["detailUrl"] = thumb_paths[1200]
    except (UnidentifiedImageError, OSError) as exc:
        target.unlink(missing_ok=True)
        raise APIError(422, "图片损坏或无法解析") from exc
    return result


def verify_registered_upload(token: str, user_id: int) -> dict:
    payload = parse_upload_token(token, user_id)
    target = _safe_path(payload["key"])
    if not target.exists() or not target.is_file():
        raise APIError(409, "文件尚未上传完成，无法登记")
    size = target.stat().st_size
    if size <= 0 or size > payload["max"]:
        raise APIError(422, "文件大小校验失败")
    mime = payload["mime"]
    with target.open("rb") as handle:
        head = handle.read(64)
    if sniff_mime(head) != mime:
        raise APIError(422, "文件头校验失败")
    metadata = process_uploaded_file(target, payload["key"], mime, user_id)
    metadata["size"] = size
    return metadata


def delete_file(relative_url: str | None) -> None:
    if not relative_url or not relative_url.startswith("/media/"):
        return
    key = relative_url.removeprefix("/media/")
    try:
        _safe_path(key).unlink(missing_ok=True)
    except Exception:
        pass


async def save_avatar(upload: UploadFile, user_id: int) -> dict:
    raw = await upload.read(settings.max_image_mb * 1024 * 1024 + 1)
    if len(raw) > settings.max_image_mb * 1024 * 1024:
        raise APIError(413, f"头像不能超过 {settings.max_image_mb}MB")
    mime = sniff_mime(raw[:64])
    if mime not in ALLOWED_IMAGE_MIME:
        raise APIError(422, "头像仅支持 JPG / PNG / WebP / GIF")
    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image = ImageOps.fit(image.convert("RGB"), (512, 512), method=Image.Resampling.LANCZOS)
    except Exception as exc:
        raise APIError(422, "头像图片无法解析") from exc
    key = f"avatars/{user_id}/{secrets.token_hex(12)}.webp"
    target = _safe_path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "WEBP", quality=88, method=4)
    return {"url": f"/media/{key}", "width": 512, "height": 512, "mime": "image/webp", "size": len(raw)}


def public_url_for_key(key: str) -> str:
    return f"/media/{key}"
