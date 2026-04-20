import pytest
from app.tasks.insights import refresh_page_insights_impl, refresh_page_revenue_impl


@pytest.mark.integration
def test_refresh_page_insights_writes_rows(db_cursor):
    db_cursor.execute("SELECT id FROM pages LIMIT 1")
    row = db_cursor.fetchone()
    if not row:
        pytest.skip("No pages in DB")
    page_id = row["id"]
    refresh_page_insights_impl(str(page_id), days=7)
    db_cursor.execute("SELECT COUNT(*) AS c FROM page_insights WHERE page_id=%s", (page_id,))
    assert db_cursor.fetchone()["c"] >= 7


@pytest.mark.integration
def test_refresh_revenue_writes_rows(db_cursor):
    db_cursor.execute("SELECT id FROM pages LIMIT 1")
    row = db_cursor.fetchone()
    if not row:
        pytest.skip("No pages in DB")
    page_id = row["id"]
    refresh_page_revenue_impl(str(page_id), days=7)
    db_cursor.execute("SELECT COUNT(*) AS c FROM revenue_records WHERE page_id=%s", (page_id,))
    assert db_cursor.fetchone()["c"] >= 7
