"""通用工具：时间、分页、文本清洗、安全片段高亮。"""

from __future__ import annotations

import hashlib
import math
import re
import secrets
import unicodedata
from datetime import date, datetime, time, timezone
from typing import Any, Iterable
from urllib.parse import quote

from .config import settings

TAG_RE = re.compile(r"<[^>]+>")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SLUG_RE = re.compile(r"[^\w\u4e00-\u9fff-]+", re.UNICODE)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat().replace("+00:00", "Z")
    return value.isoformat()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def day_bounds(from_day: date | None, to_day: date | None) -> tuple[datetime, datetime]:
    start_day = from_day or (utcnow().date().replace(day=1))
    end_day = to_day or utcnow().date()
    start = datetime.combine(start_day, time.min)
    end = datetime.combine(end_day, time.max)
    return start, end


def clean_text(value: str | None, *, max_len: int | None = None, keep_newlines: bool = True) -> str:
    """去掉控制字符与 HTML 标签；展示层继续依赖 Vue 自动转义，双层防护。"""
    if value is None:
        return ""
    text = CONTROL_RE.sub("", str(value))
    text = TAG_RE.sub("", text)
    text = text.strip()
    if not keep_newlines:
        text = re.sub(r"\s+", " ", text)
    if max_len is not None:
        text = text[:max_len]
    return text


def slugify(value: str, fallback: str = "item") -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    normalized = normalized.replace("_", "-").replace(" ", "-")
    normalized = SLUG_RE.sub("-", normalized).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized[:80] or fallback


def unique_slug(db, model, value: str, fallback: str = "item") -> str:
    base = slugify(value, fallback)
    candidate = base
    for _ in range(20):
        exists = db.query(model).filter(model.slug == candidate).first()
        if not exists:
            return candidate
        candidate = f"{base}-{secrets.token_hex(2)}"
    return f"{base}-{secrets.token_hex(4)}"


def mask_ip(ip: str | None) -> str:
    if not ip:
        return "未知"
    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:4]) + ":••••"
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3]) + ".***"
    return ip[: max(1, len(ip) - 3)] + "***"


def mask_phone(phone: str | None) -> str:
    if not phone:
        return ""
    return phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else "****"


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    name, domain = email.split("@", 1)
    return f"{name[:2]}***@{domain}"


def page_params(page: int | None, page_size: int | None, *, max_size: int = 50) -> tuple[int, int]:
    page = max(1, int(page or 1))
    page_size = min(max(1, int(page_size or 12)), max_size)
    return page, page_size


def paginate(query, page: int, page_size: int) -> tuple[list, dict]:
    total = query.order_by(None).count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = max(1, math.ceil(total / page_size))
    return rows, {
        "page": page,
        "pageSize": page_size,
        "total": total,
        "pages": pages,
        "hasNext": page < pages,
    }


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def highlight_snippet(text: str | None, keyword: str, radius: int = 60) -> str:
    """返回已 HTML 转义的 60 字上下文，命中词用 <mark> 包裹，前端用 v-html 输出。"""
    import html

    if not text:
        return ""
    plain = clean_text(text, max_len=10000)
    term = clean_text(keyword, max_len=50, keep_newlines=False)
    idx = plain.lower().find(term.lower()) if term else -1
    if idx < 0:
        snippet = plain[: radius * 2]
        return html.escape(snippet) + ("…" if len(plain) > len(snippet) else "")
    start = max(0, idx - radius)
    end = min(len(plain), idx + len(term) + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(plain) else ""
    segment = plain[start:end]
    if term:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        pieces = []
        cursor = 0
        for match in pattern.finditer(segment):
            pieces.append(html.escape(segment[cursor : match.start()]))
            pieces.append(f"<mark>{html.escape(match.group(0))}</mark>")
            cursor = match.end()
        pieces.append(html.escape(segment[cursor:]))
        highlighted = "".join(pieces)
    else:
        highlighted = html.escape(segment)
    return f"{prefix}{highlighted}{suffix}"


def short_code(length: int = 10) -> str:
    alphabet = "23456789abcdefghjkmnpqrstuvwxyz"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def numeric_code(length: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_user_id(user_id: int) -> str:
    import hmac

    return hmac.new(settings.jwt_secret.encode(), str(user_id).encode(), hashlib.sha256).hexdigest()


def domain_of(url: str | None) -> str:
    if not url:
        return ""
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "").lower()


def safe_link(url: str | None) -> str | None:
    """运营位跳转白名单：只允许站内路径与自身/前端域名。"""
    if not url:
        return None
    value = url.strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    from urllib.parse import urlparse

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None
    allowed_hosts = {domain_of(settings.public_base_url), domain_of(settings.frontend_origin.split(",")[0])}
    if parsed.hostname and parsed.hostname.lower() in allowed_hosts:
        return value
    return None


def public_media_url(path: str | None) -> str | None:
    """本地媒体路径经过 quote，兼容空格与中文文件名。"""
    if not path:
        return None
    return "/" + quote(path.lstrip("/"), safe="/")


def chunked(items: Iterable[Any], size: int):
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
