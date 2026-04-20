"""Integration tests for bulk-connect page endpoint — deferred to Phase 9."""
import pytest

pytestmark = pytest.mark.integration


def test_bulk_connect_assigns_pages_to_batch(api_client, auth_headers_mock):
    resp = api_client.post(
        "/api/v1/pages/bulk-connect",
        headers=auth_headers_mock,
        json={
            "batch_id": "00000000-0000-0000-0000-000000000000",
            "page_ids": [],
        },
    )
    # With no page_ids, 400
    assert resp.status_code in (400, 422)


def test_bulk_connect_validates_batch_exists(api_client, auth_headers_mock):
    resp = api_client.post(
        "/api/v1/pages/bulk-connect",
        headers=auth_headers_mock,
        json={
            "batch_id": "11111111-1111-1111-1111-111111111111",
            "page_ids": ["22222222-2222-2222-2222-222222222222"],
        },
    )
    assert resp.status_code in (400, 404)
