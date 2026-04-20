"""Unit-level checks for the SSE endpoint wiring (no streaming)."""
from app.api import sse as sse_mod


def test_sse_router_has_events_route():
    paths = [r.path for r in sse_mod.router.routes]
    assert "/sse/events" in paths


def test_sse_uses_sse_bus_factory():
    """Regression: endpoint must pull the shared bus via get_sse_bus(), not
    maintain its own per-module channel dict (the pre-Phase-4 pattern)."""
    src = (sse_mod.__file__ or "").lower()
    assert src.endswith("sse.py")
    # The module body should reference get_sse_bus and not the legacy _channels
    import inspect
    code = inspect.getsource(sse_mod)
    assert "get_sse_bus" in code
    assert "_channels" not in code
