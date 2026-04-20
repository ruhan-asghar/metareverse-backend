"""Server-Sent Events endpoint — bridges the in-process SSEBus to clients.

Uses `app.services.sse_bus.get_sse_bus()` (subscribe(org_id, user_id) -> Queue).
Events are emitted elsewhere (publishers, task hooks) via `bus.publish(org_id, type, payload)`.
"""

import asyncio
import json
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.core.auth import CurrentUser, require_org
from app.services.sse_bus import get_sse_bus

router = APIRouter(prefix="/sse", tags=["real-time"])

_KEEPALIVE_SECONDS = 25


@router.get("/events")
async def event_stream(
    request: Request,
    user: CurrentUser = Depends(require_org),
):
    """SSE stream for real-time updates (queue state, publish progress, notifications)."""
    bus = get_sse_bus()
    queue = await bus.subscribe(user.org_id, user.clerk_user_id)

    async def generate():
        try:
            # Initial hello so the client knows the stream is live
            yield {
                "event": "connected",
                "data": json.dumps({"org_id": user.org_id}),
            }
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_SECONDS)
                    yield {
                        "event": event.get("type", "message"),
                        "data": json.dumps(event.get("payload", {})),
                    }
                except asyncio.TimeoutError:
                    # Keepalive — comments are also fine but named ping is easier on clients
                    yield {"event": "ping", "data": "{}"}
        finally:
            await bus.unsubscribe(user.org_id, user.clerk_user_id, queue)

    return EventSourceResponse(generate())
