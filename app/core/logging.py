import logging, structlog
from app.core.config import get_settings

SENSITIVE_KEYS = {"token", "access_token", "page_access_token", "secret", "password", "authorization", "api_key"}


def _scrub(logger, method, event_dict):
    for k in list(event_dict.keys()):
        if any(s in k.lower() for s in SENSITIVE_KEYS):
            event_dict[k] = "***"
    return event_dict


def configure_logging():
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _scrub,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "app") -> structlog.BoundLogger:
    return structlog.get_logger(name)
