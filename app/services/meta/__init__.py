from functools import lru_cache
from app.core.config import get_settings
from app.services.meta.client import MetaClient
from app.services.meta.mock_client import MockMetaClient


@lru_cache(maxsize=1)
def get_meta_client() -> MetaClient:
    s = get_settings()
    if s.meta_mode == "mock":
        return MockMetaClient(seed=42)
    from app.services.meta.live_client import LiveMetaClient
    return LiveMetaClient(app_id=s.meta_app_id, app_secret=s.meta_app_secret)
