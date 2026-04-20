import resend
from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("email")


def send_email(to: str, subject: str, html: str) -> str | None:
    s = get_settings()
    if not s.resend_api_key:
        log.info("email_skipped_no_api_key", to=to, subject=subject)
        return None
    resend.api_key = s.resend_api_key
    r = resend.Emails.send({"from": s.resend_from_email, "to": to, "subject": subject, "html": html})
    log.info("email_sent", to=to, subject=subject, email_id=r.get("id"))
    return r.get("id")
