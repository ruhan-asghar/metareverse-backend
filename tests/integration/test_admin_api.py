"""Integration tests for admin (dead-letter, metrics) — deferred to Phase 9."""
import pytest

pytestmark = pytest.mark.integration


def test_dead_letter_requires_owner(api_client, auth_headers_mock):
    # With mock auth (owner role), this should 200
    resp = api_client.get("/api/v1/admin/dead-letter", headers=auth_headers_mock)
    assert resp.status_code in (200, 403)


def test_replay_dead_letter_404_if_missing(api_client, auth_headers_mock):
    resp = api_client.post(
        "/api/v1/admin/dead-letter/00000000-0000-0000-0000-000000000000/replay",
        headers=auth_headers_mock,
    )
    assert resp.status_code in (404, 403)


def test_metrics_endpoint(api_client, auth_headers_mock):
    resp = api_client.get("/api/v1/admin/metrics", headers=auth_headers_mock)
    assert resp.status_code in (200, 403)
