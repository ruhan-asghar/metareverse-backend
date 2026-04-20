import pytest
from app.tasks.health import ping_page_token_impl


@pytest.mark.integration
def test_ping_valid_token_keeps_status(db_cursor):
    db_cursor.execute("SELECT id, status FROM pages WHERE status='ready' LIMIT 1")
    page = db_cursor.fetchone()
    if not page:
        pytest.skip("No ready pages")
    ping_page_token_impl(str(page["id"]))
    db_cursor.execute("SELECT status FROM pages WHERE id=%s", (page["id"],))
    assert db_cursor.fetchone()["status"] == "ready"
