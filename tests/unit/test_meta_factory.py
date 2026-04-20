from app.services.meta import get_meta_client
from app.services.meta.mock_client import MockMetaClient


def test_factory_returns_mock_when_env_is_mock(monkeypatch):
    monkeypatch.setenv("META_MODE", "mock")
    from app.core.config import get_settings
    get_settings.cache_clear()  # type: ignore
    get_meta_client.cache_clear()  # type: ignore
    c = get_meta_client()
    assert isinstance(c, MockMetaClient)
