"""Integration tests for dashboard stats — deferred to Phase 9."""
import pytest

pytestmark = pytest.mark.integration


def test_dashboard_stats_shape(api_client, auth_headers_mock):
    resp = api_client.get("/api/v1/dashboard/stats", headers=auth_headers_mock)
    assert resp.status_code == 200
    data = resp.json()
    for key in (
        "pages_ready",
        "pages_expired",
        "posts_queued",
        "posts_pending_approval",
        "posts_failed",
        "revenue_30d_cents",
    ):
        assert key in data
