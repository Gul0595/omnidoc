"""
tools/notifications.py — Email via Resend (3,000/month free)

# ── CREDENTIAL REQUIRED ──────────────────────────────────────────────────────
# RESEND_API_KEY — Get free at: https://resend.com
# FROM_EMAIL     — your verified sender email
# ─────────────────────────────────────────────────────────────────────────────
# If RESEND_API_KEY not set, emails are silently skipped (no crash).
"""
import os

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
FROM         = os.getenv("FROM_EMAIL", "OmniDoc <noreply@yourdomain.com>")


def _send(to: str, subject: str, html: str):
    key = os.getenv("RESEND_API_KEY")
    if not key:
        print(f"[Email skipped — RESEND_API_KEY not set] To: {to}, Subject: {subject}")
        return
    try:
        import resend
        resend.api_key = key
        resend.Emails.send({"from": FROM, "to": [to],
                            "subject": subject, "html": html})
    except Exception as e:
        print(f"Email failed: {e}")


def send_upload_complete(to: str, name: str, filename: str,
                         ws_name: str, chunks: int, pages: int):
    _send(to, f"OmniDoc: '{filename}' is ready",
          f"<h2>{ws_name}</h2>"
          f"<p>Hi {name}, <b>{filename}</b> has been processed:</p>"
          f"<ul><li>Pages: {pages}</li><li>Searchable chunks: {chunks}</li></ul>"
          f"<p><a href='{FRONTEND_URL}'>Open OmniDoc →</a></p>")


def send_invite(to: str, inviter: str, ws_name: str, ws_id: str):
    _send(to, f"OmniDoc: {inviter} invited you",
          f"<p><b>{inviter}</b> invited you to workspace <b>{ws_name}</b>.</p>"
          f"<p><a href='{FRONTEND_URL}'>Accept invite →</a></p>")
