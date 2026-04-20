import asyncio
from collections import defaultdict
from typing import Any


class SSEBus:
    def __init__(self):
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, org_id: str, user_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subs[org_id].append(q)
        return q

    async def unsubscribe(self, org_id: str, user_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            if q in self._subs.get(org_id, []):
                self._subs[org_id].remove(q)

    async def publish(self, org_id: str, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload}
        async with self._lock:
            subs = list(self._subs.get(org_id, []))
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass


_bus = SSEBus()


def get_sse_bus() -> SSEBus:
    return _bus
