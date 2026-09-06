"""Sends the daily digest email via Resend's HTTP API, with the full
dashboard.html attached. Failures here are logged distinctly and never affect
whether the dashboard file itself was written."""
from __future__ import annotations

import base64
import logging

import requests

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"


class EmailSendError(Exception):
    pass


def send_digest(api_key: str, sender: str, recipient: str, subject: str,
                 html_body: str, dashboard_html: str, dashboard_filename: str = "dashboard.html") -> None:
    if not api_key:
        raise EmailSendError("RESEND_API_KEY must be set")

    attachment_b64 = base64.b64encode(dashboard_html.encode("utf-8")).decode("ascii")

    payload = {
        "from": sender,
        "to": [recipient],
        "subject": subject,
        "html": html_body,
        "attachments": [
            {"filename": dashboard_filename, "content": attachment_b64}
        ],
    }

    resp = requests.post(
        _RESEND_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=20,
    )

    if resp.status_code >= 300:
        raise EmailSendError(f"Resend send failed: {resp.status_code} {resp.text[:300]}")

    logger.info("Digest email sent to %s", recipient)
