from app.celery_app import celery_app


def test_celery_app_configured():
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_max_tasks_per_child == 1000
    assert celery_app.conf.task_default_queue == "default"
