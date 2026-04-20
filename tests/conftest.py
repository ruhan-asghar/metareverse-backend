import os
import pytest
import fakeredis
import psycopg2
from psycopg2.extras import RealDictCursor
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


@pytest.fixture
def db_conn():
    from app.core.config import get_settings
    s = get_settings()
    conn = psycopg2.connect(s.database_url)
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture
def db_cursor(db_conn):
    cur = db_conn.cursor(cursor_factory=RealDictCursor)
    yield cur
    cur.close()
