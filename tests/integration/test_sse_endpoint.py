"""Integration tests for the /sse/events endpoint.

Streaming responses are inherently blocking on a TestClient, so we verify:
  1. Unauthenticated requests are rejected (401/403).
  2. With auth overrides, the initial "connected" event is sent and the bus
     fan-out works. We pull a single event then disconnect.
"""
import asyncio
import json
import threading
import pytest

pytestmark = pytest.mark.integration


def test_events_requires_auth(api_client):
    resp = api_client.get("/api/v1/sse/events")
    # No Authorization header -> 401/403 (HTTPBearer returns 403 on missing creds)
    assert resp.status_code in (401, 403)


def test_events_stream_publishes_event(api_client, auth_headers_mock):
    from app.services.sse_bus import get_sse_bus

    bus = get_sse_bus()

    def publisher():
        # Give the subscriber a moment to register before publishing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(asyncio.sleep(0.3))
            loop.run_until_complete(bus.publish("org_test", "post_published", {"id": "p1"}))
        finally:
            loop.close()

    t = threading.Thread(target=publisher, daemon=True)
    t.start()

    with api_client.stream("GET", "/api/v1/sse/events", headers=auth_headers_mock) as resp:
        assert resp.status_code == 200
        seen_events: list[str] = []
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("event:"):
                evt = line.split(":", 1)[1].strip()
                seen_events.append(evt)
                if evt == "post_published":
                    break
            if len(seen_events) > 5:
                break
        assert "connected" in seen_events
        assert "post_published" in seen_events
