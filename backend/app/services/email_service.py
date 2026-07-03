"""Shared email delivery helper (SMTP with local-outbox fallback).

Extracted so multiple routers (sales invoices, Super Admin service invoices, …)
can email a PDF without duplicating SMTP logic. If SMTP is not configured (or the
send fails), the message + attachment is written to static/mail_outbox so nothing
is lost and the action still succeeds in dev.
"""
from __future__ import annotations

import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from app.config import settings

_OUTBOX_DIR = Path(__file__).resolve().parents[1].parent / "static" / "mail_outbox"


def mail_config_looks_configured() -> bool:
    placeholders = {
        "your@gmail.com",
        "your-gmail-app-password",
        "noreply@yourcompany.com",
        "smtp.gmail.com",
    }
    username = (settings.mail_username or "").strip()
    password = (settings.mail_password or "").strip()
    sender = (settings.mail_from or "").strip()
    server = (settings.mail_server or "").strip()
    return (
        bool(username and password and sender and server)
        and username not in placeholders
        and password not in placeholders
    )


def write_email_outbox_copy(*, recipient: str, subject: str, body: str, pdf_filename: str, pdf_bytes: bytes) -> str:
    _OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    token = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    pdf_path = _OUTBOX_DIR / f"{token}_{pdf_filename.replace(' ', '_')}"
    meta_path = _OUTBOX_DIR / f"{token}.txt"
    pdf_path.write_bytes(pdf_bytes)
    meta_path.write_text(
        "\n".join([f"to={recipient}", f"subject={subject}", "body=", body, "", f"attachment={pdf_path.name}"]),
        encoding="utf-8",
    )
    return pdf_path.name


def send_pdf_email(*, recipient: str, subject: str, body: str, pdf_filename: str, pdf_bytes: bytes) -> dict:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = (settings.mail_from or "").strip()
    msg["To"] = recipient
    msg.set_content(body)
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename)

    if mail_config_looks_configured():
        try:
            if settings.mail_ssl_tls:
                with smtplib.SMTP_SSL(settings.mail_server, settings.mail_port, timeout=20) as smtp:
                    smtp.login(settings.mail_username, settings.mail_password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(settings.mail_server, settings.mail_port, timeout=20) as smtp:
                    smtp.ehlo()
                    if settings.mail_starttls:
                        smtp.starttls(context=ssl.create_default_context())
                        smtp.ehlo()
                    smtp.login(settings.mail_username, settings.mail_password)
                    smtp.send_message(msg)
            return {"delivery": "smtp", "message": "Email sent successfully"}
        except Exception:
            outbox = write_email_outbox_copy(
                recipient=recipient, subject=subject, body=body,
                pdf_filename=pdf_filename, pdf_bytes=pdf_bytes,
            )
            return {"delivery": "outbox", "message": "SMTP send failed; saved email copy to local outbox", "outbox_file": outbox}

    outbox = write_email_outbox_copy(
        recipient=recipient, subject=subject, body=body,
        pdf_filename=pdf_filename, pdf_bytes=pdf_bytes,
    )
    return {"delivery": "outbox", "message": "SMTP not configured; saved email copy to local outbox", "outbox_file": outbox}
