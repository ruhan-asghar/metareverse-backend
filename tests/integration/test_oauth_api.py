"""Integration tests for OAuth endpoints — deferred to Phase 9 (needs live DB)."""
import pytest

pytestmark = pytest.mark.integration


def test_oauth_start_issues_redirect(api_client, auth_headers_mock, redis_client):
    resp = api_client.get("/api/v1/oauth/facebook/start", headers=auth_headers_mock)
    assert resp.status_code in (302, 307)
    assert "facebook.com" in resp.headers.get("location", "") or "mock" in resp.headers.get("location", "")


def test_oauth_callback_creates_unassigned_batch_and_pages(api_client, auth_headers_mock, redis_client):
    # Prime a state token
    start = api_client.get("/api/v1/oauth/facebook/start", headers=auth_headers_mock)
    loc = start.headers.get("location", "")
    # State is in query string of redirect URL
    assert "state=" in loc
    state = loc.split("state=")[1].split("&")[0]
    resp = api_client.get(
        f"/api/v1/oauth/facebook/callback?code=mock_code&state={state}",
        headers=auth_headers_mock,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "pages" in body
    assert isinstance(body["pages"], list)


def test_oauth_callback_rejects_bad_state(api_client, auth_headers_mock, redis_client):
    resp = api_client.get(
        "/api/v1/oauth/facebook/callback?code=mock_code&state=not_a_real_token",
        headers=auth_headers_mock,
    )
    assert resp.status_code in (400, 403)
