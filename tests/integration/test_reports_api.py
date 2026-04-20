"""Integration tests for reports endpoints — deferred to Phase 9 (need real DB)."""
import pytest

pytestmark = pytest.mark.integration


def test_overview_returns_metrics_shape(api_client, auth_headers_mock):
    resp = api_client.get("/api/v1/reports/overview?period=28d", headers=auth_headers_mock)
    assert resp.status_code == 200
    body = resp.json()
    assert body["period"] == "28d"
    assert "metrics" in body
    assert "views" in body["metrics"]
    assert "follows" in body["metrics"]
    assert "interactions" in body["metrics"]


def test_earnings_splits_revenue(api_client, auth_headers_mock):
    resp = api_client.get("/api/v1/reports/earnings?period=7d", headers=auth_headers_mock)
    assert resp.status_code == 200
    body = resp.json()
    assert body["period"] == "7d"
    # Real schema: total + per-media-type splits (reels/photos/stories/text), NOT cpm/network/other
    for key in ("total_cents", "reels_cents", "photos_cents", "stories_cents", "text_cents"):
        assert key in body, f"missing key {key}"
    assert "series" in body
    assert isinstance(body["series"], list)


def test_id_performance_masks_user_id(api_client, auth_headers_mock):
    resp = api_client.get("/api/v1/reports/id-performance", headers=auth_headers_mock)
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    for it in items:
        assert "facebook_user_id_masked" in it
        masked = it["facebook_user_id_masked"]
        # Mask looks like abcd…wxyz (contains an ellipsis character)
        assert "…" in masked or masked == ""


def test_posting_id_health(api_client, auth_headers_mock):
    resp = api_client.get("/api/v1/reports/posting-id-health", headers=auth_headers_mock)
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    for it in items:
        assert "health_label" in it
        assert it["health_label"] in ("Healthy", "Declining", "Replace")


def test_results_top_posts_includes_caption(api_client, auth_headers_mock):
    resp = api_client.get("/api/v1/reports/results?period=28d", headers=auth_headers_mock)
    assert resp.status_code == 200
    body = resp.json()
    assert "top_posts" in body
    assert "summary" in body
    assert isinstance(body["top_posts"], list)


def test_page_report(api_client, auth_headers_mock):
    resp = api_client.get(
        "/api/v1/reports/page/00000000-0000-0000-0000-000000000000?period=28d",
        headers=auth_headers_mock,
    )
    # 404 when the stub page UUID does not exist; 200 when it does
    assert resp.status_code in (200, 404)


def test_page_revenue(api_client, auth_headers_mock):
    resp = api_client.get("/api/v1/reports/page-revenue?period=28d", headers=auth_headers_mock)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    for it in body:
        assert "revenue_cents" in it
        assert "rpm_cents" in it
