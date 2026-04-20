import inspect
from app.services.meta.mock_client import MockMetaClient
from app.services.meta.live_client import LiveMetaClient


def _methods(cls):
    return {m for m, _ in inspect.getmembers(cls, predicate=inspect.isfunction) if not m.startswith("_")}


def test_mock_and_live_expose_same_public_surface():
    assert _methods(MockMetaClient) == _methods(LiveMetaClient)


def test_mock_and_live_same_signatures():
    for name in _methods(MockMetaClient):
        m_sig = inspect.signature(getattr(MockMetaClient, name))
        l_sig = inspect.signature(getattr(LiveMetaClient, name))
        m_params = [p for n, p in m_sig.parameters.items() if n != "self"]
        l_params = [p for n, p in l_sig.parameters.items() if n != "self"]
        assert [p.name for p in m_params] == [p.name for p in l_params], f"{name} params differ"
