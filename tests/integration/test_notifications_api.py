"""Integration tests for notifications — deferred to Phase 9."""
import pytest

pytestmark = pytest.mark.integration


def test_list_notifications(api_client, auth_headers_mock):
    resp = api_client.get("/api/v1/notifications", headers=auth_headers_mock)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_notifications_unread_only(api_client, auth_headers_mock):
    resp = api_client.get("/api/v1/notifications?unread_only=true", headers=auth_headers_mock)
    assert resp.status_code == 200


def test_mark_notification_read_404_if_missing(api_client, auth_headers_mock):
    resp = api_client.post(
        "/api/v1/notifications/00000000-0000-0000-0000-000000000000/read",
        headers=auth_headers_mock,
    )
    assert resp.status_code in (404, 400)


def test_mark_all_read(api_client, auth_headers_mock):
    resp = api_client.post("/api/v1/notifications/read-all", headers=auth_headers_mock)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
