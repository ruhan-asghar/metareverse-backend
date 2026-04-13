"""Server-Sent Events endpoint for real-time queue status updates."""

import asyncio
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from app.core.auth import CurrentUser, require_org

router = APIRouter(prefix="/sse", tags=["real-time"])

# In-memory event channels per org — production should use Redis pub/sub
_channels: dict[str, asyncio.Queue] = {}


def get_channel(org_id: str) -> asyncio.Queue:
    if org_id not in _channels:
        _channels[org_id] = asyncio.Queue(maxsize=100)
    return _channels[org_id]


async def publish_event(org_id: str, event_type: str, data: dict):
    """Publish an event to all SSE listeners for an org."""
    channel = get_channel(org_id)
    try:
        channel.put_nowait({"event": event_type, "data": data})
    except asyncio.QueueFull:
        pass  # Drop event if queue is full


@router.get("/events")
async def event_stream(
    request: Request,
    user: CurrentUser = Depends(require_org),
):
    """SSE stream for real-time updates (queue status, publish progress)."""

    async def generate():
        channel = get_channel(user.org_id)
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(channel.get(), timeout=30)
                yield {
                    "event": event["event"],
                    "data": str(event["data"]),
                }
            except asyncio.TimeoutError:
                # Send keepalive
                yield {"event": "ping", "data": ""}

    return EventSourceResponse(generate())
