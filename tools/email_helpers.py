"""Email helper utilities — IMAP connection, header decoding, body extraction,
SMTP sending, config loading, and file attachment logic used by EmailTool.
"""

import email
import email.encoders
import email.mime.base
import email.mime.multipart
import email.mime.text
import imaplib
import logging
import mimetypes
import smtplib
from email.header import decode_header
from pathlib import Path

from core.config import get_config

logger = logging.getLogger(__name__)


def get_email_config() -> dict:
    """Get email settings from config."""
    config = get_config()
    raw = getattr(config, "email", None)
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    # Map EmailConfig dataclass fields to what the tool expects
    return {
        "imap_host": getattr(raw, "imap_server", "") or getattr(raw, "imap_host", ""),
        "imap_port": getattr(raw, "imap_port", 993),
        "smtp_host": getattr(raw, "smtp_server", "") or getattr(raw, "smtp_host", ""),
        "smtp_port": getattr(raw, "smtp_port", 587),
        "username": getattr(raw, "email", "") or getattr(raw, "username", ""),
        "password": getattr(raw, "password", ""),
    }


def connect_imap(cfg: dict) -> imaplib.IMAP4_SSL:
    """Open an authenticated IMAP connection."""
    host = cfg.get("imap_host", "imap.gmail.com")
    port = cfg.get("imap_port", 993)
    conn = imaplib.IMAP4_SSL(host, port)
    conn.login(cfg["username"], cfg["password"])
    return conn


def decode_header_value(value: str) -> str:
    """Decode an RFC-2047 encoded header value into a plain string."""
    decoded_parts = decode_header(value)
    parts = []
    for content, charset in decoded_parts:
        if isinstance(content, bytes):
            parts.append(content.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(content)
    return " ".join(parts)


def get_body(msg: email.message.Message) -> str:
    """Extract the plain-text (or HTML fallback) body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback to HTML
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return f"[HTML]\n{payload.decode(charset, errors='replace')}"
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return "(no body)"


def attach_files(
    msg: email.mime.multipart.MIMEMultipart, attachments: list
) -> list[str]:
    """Attach files to an email message. Returns list of attached filenames."""
    attached = []
    for file_path in attachments:
        p = Path(file_path).expanduser()
        if not p.exists():
            logger.warning("Attachment not found: %s", p)
            continue
        if p.stat().st_size > 25 * 1024 * 1024:  # 25MB Gmail limit
            logger.warning("Attachment too large (>25MB): %s", p)
            continue

        mime_type, _ = mimetypes.guess_type(str(p))
        if mime_type is None:
            mime_type = "application/octet-stream"
        main_type, sub_type = mime_type.split("/", 1)

        with open(p, "rb") as f:
            part = email.mime.base.MIMEBase(main_type, sub_type)
            part.set_payload(f.read())
        email.encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=p.name)
        msg.attach(part)
        attached.append(p.name)
    return attached


def send_via_smtp(cfg: dict, msg: email.mime.multipart.MIMEMultipart) -> None:
    """Send an already-composed MIME message through SMTP."""
    host = cfg.get("smtp_host", "smtp.gmail.com")
    port = cfg.get("smtp_port", 587)
    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(cfg["username"], cfg["password"])
        server.send_message(msg)


def fetch_header_summaries(
    conn: imaplib.IMAP4_SSL, message_ids: list[bytes]
) -> list[str]:
    """Fetch FROM / SUBJECT / DATE headers for a list of message IDs
    and return one summary line per message."""
    lines: list[str] = []
    for mid in message_ids:
        _, data = conn.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if data[0] is None:
            continue
        header = email.message_from_bytes(data[0][1])
        from_addr = decode_header_value(header.get("From", ""))
        subject = decode_header_value(header.get("Subject", "(no subject)"))
        date = header.get("Date", "")
        lines.append(
            f"  [{mid.decode()}] {date[:20]}  From: {from_addr[:40]}  Subject: {subject[:60]}"
        )
    return lines
