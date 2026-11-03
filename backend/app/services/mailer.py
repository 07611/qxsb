"""异步邮件投递：后台线程 + 最多 3 次退避重试 + 本地 outbox 降级。"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from ..config import settings
from ..database import session_scope
from ..models import EmailLog, User, utcnow
from ..utils import iso

logger = logging.getLogger("moodwave.email")
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="mail")
_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parents[1] / "templates" / "email")),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_template(template: str, context: dict) -> str:
    return _env.get_template(template).render(**context)


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(f"{settings.jwt_secret}|email-context".encode()).digest())
    return Fernet(key)


def seal_context(context: dict) -> dict:
    """验证码、重置链接不能以明文落库；异步线程取用时解密。"""
    payload = json.dumps(context, ensure_ascii=False, separators=(",", ":")).encode()
    return {"_sealed": _fernet().encrypt(payload).decode()}


def open_context(context: dict | None) -> dict:
    if not context:
        return {}
    token = context.get("_sealed") if isinstance(context, dict) else None
    if not token:
        return context
    try:
        return json.loads(_fernet().decrypt(token.encode()).decode())
    except (InvalidToken, ValueError, json.JSONDecodeError):
        logger.error("email_context_decrypt_failed")
        return {}


def _smtp_send(to_email: str, subject: str, html_body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content("此邮件包含 HTML 内容，请使用支持 HTML 的邮件客户端查看。")
    message.add_alternative(html_body, subtype="html")
    if settings.smtp_tls:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=12) as server:
            server.ehlo()
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=12) as server:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)


def _write_outbox(log_id: int, to_email: str, subject: str, html_body: str) -> str:
    if settings.is_production:
        raise RuntimeError("SMTP 未配置：生产环境禁止把邮件正文写成本地明文文件")
    outbox = Path(settings.logs_dir) / "email-outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    path = outbox / f"{log_id:06d}.html"
    path.write_text(
        f"<!-- to: {html.escape(to_email)} -->\n<!-- subject: {html.escape(subject)} -->\n{html_body}",
        encoding="utf-8",
    )
    return str(path)


def _deliver(log_id: int) -> None:
    """独立会话执行，失败重试 3 次；最终失败落库并写 error 日志。"""
    last_error = ""
    for attempt in range(1, 5):
        with session_scope() as db:
            row = db.get(EmailLog, log_id)
            if not row or row.status == "sent":
                return
            row.retry_count = attempt - 1
            try:
                context = open_context(row.context or {})
                if settings.smtp_host:
                    _smtp_send(row.to_email, row.subject, render_template(row.template, context))
                else:
                    outbox_file = _write_outbox(row.id, row.to_email, row.subject, render_template(row.template, context))
                    logger.info("email_outbox_written id=%s file=%s", row.id, outbox_file)
                row.status = "sent"
                row.sent_at = utcnow()
                row.error_message = None
                return
            except Exception as exc:  # pragma: no cover - SMTP 环境相关
                last_error = str(exc)[:1000]
                row.status = "retrying" if attempt < 4 else "failed"
                row.error_message = last_error
                logger.warning("email_send_failed id=%s attempt=%s error=%s", row.id, attempt, last_error)
        if attempt < 4:
            time.sleep(min(8, 2**attempt))
    logger.error("email_given_up id=%s error=%s", log_id, last_error)
    try:
        from .alerting import notify_server_error

        notify_server_error(f"email-{log_id}", "mailer", f"email {log_id} failed after retries: {last_error}")
    except Exception:
        pass


def enqueue_email(
    db: Session,
    *,
    to_email: str,
    template: str,
    subject: str,
    context: dict,
    user: User | None = None,
    force: bool = False,
    min_interval_seconds: int = 60,
) -> EmailLog | None:
    """同一用户同模板做频率限制，避免验证码邮件轰炸。"""
    if user and not force:
        recent = (
            db.query(EmailLog)
            .filter(
                EmailLog.user_id == user.id,
                EmailLog.template == template,
                EmailLog.created_at > utcnow() - timedelta(seconds=min_interval_seconds),
            )
            .order_by(EmailLog.id.desc())
            .first()
        )
        if recent and (utcnow() - recent.created_at).total_seconds() < min_interval_seconds:
            logger.info("email_throttled user=%s template=%s", user.id, template)
            return None
    row = EmailLog(
        user_id=user.id if user else None,
        to_email=to_email,
        template=template,
        subject=subject,
        status="pending",
        context=seal_context(context),
    )
    db.add(row)
    db.commit()
    _executor.submit(_deliver, row.id)
    return row


def send_test_email(db: Session, user: User, to_email: str) -> EmailLog | None:
    return enqueue_email(
        db,
        to_email=to_email,
        template="test.html",
        subject="Moodwave 邮件通道测试",
        context={
            "nickname": user.nickname,
            "sentAt": iso(utcnow()),
            "smtpEnabled": bool(settings.smtp_host),
        },
        user=user,
        force=True,
    )
