from celery import shared_task
from app.services.email.templates import render_email
from app.services.email.resend_client import send_email


@shared_task(name="app.tasks.email.send_transactional_email", acks_late=True, max_retries=3, retry_backoff=True)
def send_transactional_email(to: str, template: str, data: dict):
    html, subject = render_email(template, data)
    return send_email(to, subject, html)
