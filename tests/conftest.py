import os
import pytest
import fakeredis
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _env_for_tests():
    os.environ["META_MODE"] = "mock"
    os.environ["REDIS_URL"] = "redis://localhost:6379/15"
    os.environ["CLERK_SECRET_KEY"] = "sk_test_fake"
    os.environ["LOG_LEVEL"] = "warning"
    yield


@pytest.fixture
def redis_client():
    r = fakeredis.FakeRedis(decode_responses=True)
    with patch("app.core.redis.get_redis", return_value=r):
        yield r


@pytest.fixture
def celery_eager(monkeypatch):
    from app.celery_app import celery_app
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)
    yield celery_app


@pytest.fixture
def api_client():
    from main import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer fake-jwt", "X-Org-Id": "org_test"}
