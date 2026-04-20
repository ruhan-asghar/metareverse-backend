import pytest
from unittest.mock import MagicMock
from app.tasks.publishing import publish_post_impl
from app.services.meta.errors import TokenExpired


@pytest.fixture
def db_fixtures(db_cursor):
    db_cursor.execute("SELECT id FROM posts WHERE status='queued' LIMIT 1")
    row = db_cursor.fetchone()
    if not row:
        pytest.skip("No queued post seed row available")
    return {"post_id": row["id"]}


@pytest.mark.integration
def test_publish_post_happy_path(db_cursor, db_fixtures):
    publish_post_impl(db_fixtures["post_id"])
    db_cursor.execute("SELECT status, platform_post_id FROM posts WHERE id=%s", (db_fixtures["post_id"],))
    row = db_cursor.fetchone()
    assert row["status"] == "published"
    assert row["platform_post_id"].startswith("fb_")


@pytest.mark.integration
def test_publish_post_token_expired_marks_reconnect(db_cursor, db_fixtures, monkeypatch):
    client = MagicMock()
    client.publish_fb.side_effect = TokenExpired("expired", code=190)
    monkeypatch.setattr("app.tasks.publishing.get_meta_client", lambda: client)
    publish_post_impl(db_fixtures["post_id"])
    db_cursor.execute("SELECT status FROM posts WHERE id=%s", (db_fixtures["post_id"],))
    assert db_cursor.fetchone()["status"] == "reconnect_required"


@pytest.mark.integration
def test_publish_post_idempotent_when_already_published(db_cursor, db_fixtures):
    db_cursor.execute("UPDATE posts SET status='published', platform_post_id='fb_existing' WHERE id=%s",
                      (db_fixtures["post_id"],))
    db_cursor.connection.commit()
    publish_post_impl(db_fixtures["post_id"])
    db_cursor.execute("SELECT platform_post_id FROM posts WHERE id=%s", (db_fixtures["post_id"],))
    assert db_cursor.fetchone()["platform_post_id"] == "fb_existing"
