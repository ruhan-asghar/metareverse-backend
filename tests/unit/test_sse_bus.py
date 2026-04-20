import pytest
import asyncio
from app.services.sse_bus import SSEBus


@pytest.mark.asyncio
async def test_publish_reaches_all_subscribers():
    bus = SSEBus()
    q1 = await bus.subscribe("org1", "u1")
    q2 = await bus.subscribe("org1", "u2")
    q3 = await bus.subscribe("org2", "u1")
    await bus.publish("org1", "post_published", {"id": "p1"})
    e1 = await asyncio.wait_for(q1.get(), timeout=0.5)
    e2 = await asyncio.wait_for(q2.get(), timeout=0.5)
    assert e1["type"] == "post_published"
    assert e2["type"] == "post_published"
    assert q3.empty()


@pytest.mark.asyncio
async def test_unsubscribe_removes_queue():
    bus = SSEBus()
    q = await bus.subscribe("org1", "u1")
    await bus.unsubscribe("org1", "u1", q)
    await bus.publish("org1", "x", {})
    assert q.empty()
