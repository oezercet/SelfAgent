"""Email tool — read and send emails via IMAP and SMTP.

Supports reading inbox, searching, sending, and replying
using standard IMAP/SMTP protocols.
"""

import email
import email.mime.multipart
import email.mime.text
import logging
import re
from typing import Any

from tools.base import BaseTool
from tools.email_helpers import (
    attach_files,
    connect_imap,
    decode_header_value,
    fetch_header_summaries,
    get_body,
    get_email_config,
    send_via_smtp,
)

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

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")
        email_cfg = get_email_config()

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

    def _read_inbox(self, cfg: dict, limit: int) -> str:
        conn = connect_imap(cfg)
        conn.select("INBOX")
        _, msg_ids = conn.search(None, "ALL")
        ids = msg_ids[0].split()

        if not ids:
            conn.logout()
            return "Inbox is empty."

        recent = ids[-limit:]
        recent.reverse()

        lines = [f"Inbox ({len(ids)} total, showing {len(recent)}):\n"]
        lines.extend(fetch_header_summaries(conn, recent))
        conn.logout()
        return "\n".join(lines)

    def _read_email(self, cfg: dict, email_id: str) -> str:
        if not email_id:
            return "Error: email_id is required."

        conn = connect_imap(cfg)
        conn.select("INBOX")
        _, data = conn.fetch(email_id.encode(), "(RFC822)")

        if data[0] is None:
            conn.logout()
            return f"Email {email_id} not found."

        msg = email.message_from_bytes(data[0][1])
        from_addr = decode_header_value(msg.get("From", ""))
        to_addr = decode_header_value(msg.get("To", ""))
        subject = decode_header_value(msg.get("Subject", ""))
        date = msg.get("Date", "")
        body = get_body(msg)

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

        conn = connect_imap(cfg)
        conn.select("INBOX")

        criteria = f'(OR SUBJECT "{query}" FROM "{query}")'
        _, msg_ids = conn.search(None, criteria)
        ids = msg_ids[0].split()

        if not ids:
            conn.logout()
            return f"No emails matching '{query}'."

        recent = ids[-limit:]
        recent.reverse()

        lines = [f"Search results for '{query}' ({len(ids)} matches, showing {len(recent)}):\n"]
        lines.extend(fetch_header_summaries(conn, recent))
        conn.logout()
        return "\n".join(lines)

    @staticmethod
    def _md_to_html(text: str) -> str:
        """Convert basic markdown to HTML for email bodies."""
        h = text
        # Escape HTML entities
        h = h.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Code blocks
        h = re.sub(r"```\w*\n([\s\S]*?)```", r"<pre>\1</pre>", h)
        # Inline code
        h = re.sub(r"`([^`]+)`", r"<code>\1</code>", h)
        # Bold
        h = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", h)
        # Italic
        h = re.sub(r"\*(.+?)\*", r"<em>\1</em>", h)
        # Headings
        h = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", h, flags=re.MULTILINE)
        h = re.sub(r"^### (.+)$", r"<h3>\1</h3>", h, flags=re.MULTILINE)
        h = re.sub(r"^## (.+)$", r"<h2>\1</h2>", h, flags=re.MULTILINE)
        h = re.sub(r"^# (.+)$", r"<h1>\1</h1>", h, flags=re.MULTILINE)
        # Horizontal rule
        h = re.sub(r"^---+$", r"<hr>", h, flags=re.MULTILINE)
        # Links
        h = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', h)
        # Unordered lists
        h = re.sub(r"^[-*] (.+)$", r"<li>\1</li>", h, flags=re.MULTILINE)
        h = re.sub(r"((?:<li>.*</li>\n?)+)", r"<ul>\1</ul>", h)
        # Ordered lists
        h = re.sub(r"^\d+\. (.+)$", r"<li>\1</li>", h, flags=re.MULTILINE)
        # Paragraphs
        h = re.sub(r"\n\n+", "</p><p>", h)
        h = "<p>" + h + "</p>"
        # Line breaks
        h = h.replace("\n", "<br>")
        # Clean empty paragraphs
        h = h.replace("<p></p>", "")
        return h

    def _send_email(self, cfg: dict, to: str, subject: str, body: str,
                    attachments: list | None = None) -> str:
        if not to:
            return "Error: 'to' address is required."
        if not subject:
            return "Error: 'subject' is required."
        if not body:
            return "Error: 'body' is required."

        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg["From"] = cfg["username"]
        msg["To"] = to
        msg["Subject"] = subject
        # Plain text version (strip markdown symbols)
        plain = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
        plain = re.sub(r"\*(.+?)\*", r"\1", plain)
        plain = re.sub(r"^#{1,4} ", "", plain, flags=re.MULTILINE)
        plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
        msg.attach(email.mime.text.MIMEText(plain, "plain"))
        # HTML version
        html_body = self._md_to_html(body)
        html_full = (
            '<html><body style="font-family:sans-serif;line-height:1.6;">'
            + html_body + "</body></html>"
        )
        msg.attach(email.mime.text.MIMEText(html_full, "html"))

        attached = []
        if attachments:
            attached = attach_files(msg, attachments)

        send_via_smtp(cfg, msg)

        result = f"Email sent to {to}\nSubject: {subject}"
        if attached:
            result += f"\nAttachments: {', '.join(attached)}"
        return result

    def _reply_email(self, cfg: dict, email_id: str, body: str,
                     attachments: list | None = None) -> str:
        if not email_id:
            return "Error: email_id is required."
        if not body:
            return "Error: body is required."

        conn = connect_imap(cfg)
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

        reply = email.mime.multipart.MIMEMultipart("alternative")
        reply["From"] = cfg["username"]
        reply["To"] = from_addr
        reply["Subject"] = subject
        if message_id:
            reply["In-Reply-To"] = message_id
            reply["References"] = message_id
        # Plain text version
        plain = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
        plain = re.sub(r"\*(.+?)\*", r"\1", plain)
        plain = re.sub(r"^#{1,4} ", "", plain, flags=re.MULTILINE)
        plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
        reply.attach(email.mime.text.MIMEText(plain, "plain"))
        # HTML version
        html_body = self._md_to_html(body)
        html_full = (
            '<html><body style="font-family:sans-serif;line-height:1.6;">'
            + html_body + "</body></html>"
        )
        reply.attach(email.mime.text.MIMEText(html_full, "html"))

        attached = []
        if attachments:
            attached = attach_files(reply, attachments)

        send_via_smtp(cfg, reply)

        result = f"Reply sent to {from_addr}\nSubject: {subject}"
        if attached:
            result += f"\nAttachments: {', '.join(attached)}"
        return result
