"""Email tool — read and send emails via IMAP and SMTP.

Supports reading inbox, searching, sending, and replying
using standard IMAP/SMTP protocols.
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
from typing import Any

from tools.base import BaseTool
from core.config import get_config

logger = logging.getLogger(__name__)


class EmailTool(BaseTool):
    name = "email"
    description = (
        "Manage email: read inbox, read individual messages, search, "
        "send new emails, and reply to existing threads via IMAP/SMTP."
    )
    requires_confirmation = True
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "read_inbox",
                    "read_email",
                    "search_email",
                    "send_email",
                    "reply_email",
                ],
                "description": "The email action to perform",
            },
            "email_id": {
                "type": "string",
                "description": "ID of the email (for 'read_email', 'reply_email')",
            },
            "query": {
                "type": "string",
                "description": "Search query string (for 'search_email')",
            },
            "to": {
                "type": "string",
                "description": "Recipient address (for 'send_email')",
            },
            "subject": {
                "type": "string",
                "description": "Email subject (for 'send_email')",
            },
            "body": {
                "type": "string",
                "description": "Email body content (for 'send_email', 'reply_email')",
            },
            "limit": {
                "type": "integer",
                "description": "Max number of results to return (for 'read_inbox', 'search_email')",
            },
            "attachments": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file paths to attach (for 'send_email', 'reply_email')",
            },
        },
        "required": ["action"],
    }

    def _get_email_config(self) -> dict:
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

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")
        email_cfg = self._get_email_config()

        if not email_cfg.get("username") or not email_cfg.get("password"):
            return (
                "Error: Email not configured. Add email settings to config.yaml:\n"
                "  email:\n"
                "    imap_host: imap.gmail.com\n"
                "    smtp_host: smtp.gmail.com\n"
                "    username: you@gmail.com\n"
                "    password: your-app-password"
            )

        try:
            if action == "read_inbox":
                return self._read_inbox(email_cfg, kwargs.get("limit", 10))
            elif action == "read_email":
                return self._read_email(email_cfg, kwargs.get("email_id", ""))
            elif action == "search_email":
                return self._search_email(
                    email_cfg, kwargs.get("query", ""), kwargs.get("limit", 10)
                )
            elif action == "send_email":
                return self._send_email(
                    email_cfg,
                    kwargs.get("to", ""),
                    kwargs.get("subject", ""),
                    kwargs.get("body", ""),
                    kwargs.get("attachments", []),
                )
            elif action == "reply_email":
                return self._reply_email(
                    email_cfg,
                    kwargs.get("email_id", ""),
                    kwargs.get("body", ""),
                    kwargs.get("attachments", []),
                )
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            logger.exception("Email error: %s", action)
            return f"Email error: {e}"

    def _connect_imap(self, cfg: dict) -> imaplib.IMAP4_SSL:
        host = cfg.get("imap_host", "imap.gmail.com")
        port = cfg.get("imap_port", 993)
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(cfg["username"], cfg["password"])
        return conn

    def _decode_header_value(self, value: str) -> str:
        decoded_parts = decode_header(value)
        parts = []
        for content, charset in decoded_parts:
            if isinstance(content, bytes):
                parts.append(content.decode(charset or "utf-8", errors="replace"))
            else:
                parts.append(content)
        return " ".join(parts)

    def _get_body(self, msg: email.message.Message) -> str:
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

    def _read_inbox(self, cfg: dict, limit: int) -> str:
        conn = self._connect_imap(cfg)
        conn.select("INBOX")
        _, msg_ids = conn.search(None, "ALL")
        ids = msg_ids[0].split()

        if not ids:
            conn.logout()
            return "Inbox is empty."

        # Get latest N
        recent = ids[-limit:]
        recent.reverse()

        lines = [f"Inbox ({len(ids)} total, showing {len(recent)}):\n"]
        for mid in recent:
            _, data = conn.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if data[0] is None:
                continue
            header = email.message_from_bytes(data[0][1])
            from_addr = self._decode_header_value(header.get("From", ""))
            subject = self._decode_header_value(header.get("Subject", "(no subject)"))
            date = header.get("Date", "")
            lines.append(f"  [{mid.decode()}] {date[:20]}  From: {from_addr[:40]}  Subject: {subject[:60]}")

        conn.logout()
        return "\n".join(lines)

    def _read_email(self, cfg: dict, email_id: str) -> str:
        if not email_id:
            return "Error: email_id is required."

        conn = self._connect_imap(cfg)
        conn.select("INBOX")
        _, data = conn.fetch(email_id.encode(), "(RFC822)")

        if data[0] is None:
            conn.logout()
            return f"Email {email_id} not found."

        msg = email.message_from_bytes(data[0][1])
        from_addr = self._decode_header_value(msg.get("From", ""))
        to_addr = self._decode_header_value(msg.get("To", ""))
        subject = self._decode_header_value(msg.get("Subject", ""))
        date = msg.get("Date", "")
        body = self._get_body(msg)

        if len(body) > 5000:
            body = body[:5000] + "\n... [truncated]"

        conn.logout()
        return (
            f"From: {from_addr}\n"
            f"To: {to_addr}\n"
            f"Date: {date}\n"
            f"Subject: {subject}\n\n"
            f"{body}"
        )

    def _search_email(self, cfg: dict, query: str, limit: int) -> str:
        if not query:
            return "Error: query is required for search_email."

        conn = self._connect_imap(cfg)
        conn.select("INBOX")

        # IMAP search
        criteria = f'(OR SUBJECT "{query}" FROM "{query}")'
        _, msg_ids = conn.search(None, criteria)
        ids = msg_ids[0].split()

        if not ids:
            conn.logout()
            return f"No emails matching '{query}'."

        recent = ids[-limit:]
        recent.reverse()

        lines = [f"Search results for '{query}' ({len(ids)} matches, showing {len(recent)}):\n"]
        for mid in recent:
            _, data = conn.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if data[0] is None:
                continue
            header = email.message_from_bytes(data[0][1])
            from_addr = self._decode_header_value(header.get("From", ""))
            subject = self._decode_header_value(header.get("Subject", "(no subject)"))
            date = header.get("Date", "")
            lines.append(f"  [{mid.decode()}] {date[:20]}  From: {from_addr[:40]}  Subject: {subject[:60]}")

        conn.logout()
        return "\n".join(lines)

    def _attach_files(self, msg: email.mime.multipart.MIMEMultipart, attachments: list) -> list[str]:
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

    def _send_email(self, cfg: dict, to: str, subject: str, body: str, attachments: list | None = None) -> str:
        if not to:
            return "Error: 'to' address is required."
        if not subject:
            return "Error: 'subject' is required."
        if not body:
            return "Error: 'body' is required."

        msg = email.mime.multipart.MIMEMultipart()
        msg["From"] = cfg["username"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(email.mime.text.MIMEText(body, "plain"))

        # Attach files if provided
        attached = []
        if attachments:
            attached = self._attach_files(msg, attachments)

        host = cfg.get("smtp_host", "smtp.gmail.com")
        port = cfg.get("smtp_port", 587)

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(cfg["username"], cfg["password"])
            server.send_message(msg)

        result = f"Email sent to {to}\nSubject: {subject}"
        if attached:
            result += f"\nAttachments: {', '.join(attached)}"
        return result

    def _reply_email(self, cfg: dict, email_id: str, body: str, attachments: list | None = None) -> str:
        if not email_id:
            return "Error: email_id is required."
        if not body:
            return "Error: body is required."

        conn = self._connect_imap(cfg)
        conn.select("INBOX")
        _, data = conn.fetch(email_id.encode(), "(RFC822)")

        if data[0] is None:
            conn.logout()
            return f"Email {email_id} not found."

        original = email.message_from_bytes(data[0][1])
        from_addr = original.get("From", "")
        subject = original.get("Subject", "")
        message_id = original.get("Message-ID", "")
        conn.logout()

        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        reply = email.mime.multipart.MIMEMultipart()
        reply["From"] = cfg["username"]
        reply["To"] = from_addr
        reply["Subject"] = subject
        if message_id:
            reply["In-Reply-To"] = message_id
            reply["References"] = message_id
        reply.attach(email.mime.text.MIMEText(body, "plain"))

        # Attach files if provided
        attached = []
        if attachments:
            attached = self._attach_files(reply, attachments)

        host = cfg.get("smtp_host", "smtp.gmail.com")
        port = cfg.get("smtp_port", 587)

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(cfg["username"], cfg["password"])
            server.send_message(reply)

        result = f"Reply sent to {from_addr}\nSubject: {subject}"
        if attached:
            result += f"\nAttachments: {', '.join(attached)}"
        return result
