from celery.schedules import crontab

BEAT_SCHEDULE = {
    "refresh_all_page_insights_6h": {
        "task": "app.tasks.insights.refresh_all_page_insights",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "refresh_all_revenue_24h": {
        "task": "app.tasks.insights.refresh_all_revenue",
        "schedule": crontab(minute=0, hour=2),
    },
    "check_all_tokens_15m": {
        "task": "app.tasks.health.check_all_tokens",
        "schedule": crontab(minute="*/15"),
    },
    "reclaim_orphans_2m": {
        "task": "app.tasks.publishing.reclaim_orphans",
        "schedule": crontab(minute="*/2"),
    },
}
