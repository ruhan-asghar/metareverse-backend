import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from app.core.config import get_settings


def _scrub_event(event, hint):
    if "request" in event and "data" in event["request"]:
        event["request"]["data"] = "[scrubbed]"
    return event


def init_sentry_api():
    s = get_settings()
    if not s.sentry_dsn_api:
        return
    sentry_sdk.init(
        dsn=s.sentry_dsn_api,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        before_send=_scrub_event,
        send_default_pii=False,
    )


def init_sentry_worker():
    s = get_settings()
    if not s.sentry_dsn_worker:
        return
    sentry_sdk.init(
        dsn=s.sentry_dsn_worker,
        integrations=[CeleryIntegration()],
        traces_sample_rate=0.1,
        before_send=_scrub_event,
        send_default_pii=False,
    )
