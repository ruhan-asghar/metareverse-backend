import pytest
from app.services.meta.mock_client import MockMetaClient
from app.services.meta.client import FBPublishPayload


def test_publish_fb_returns_platform_id():
    c = MockMetaClient(seed=1)
    r = c.publish_fb(FBPublishPayload(page_id="p1", token="t", media_type="photo", caption="x", media_urls=["u"]))
    assert r.platform_post_id.startswith("fb_")


def test_deterministic_same_seed():
    a = MockMetaClient(seed=42).list_pages("ut")
    b = MockMetaClient(seed=42).list_pages("ut")
    assert [p.id for p in a] == [p.id for p in b]


def test_insights_length_matches_range():
    c = MockMetaClient(seed=1)
    data = c.get_page_insights("p1", "t", "2026-01-01", "2026-01-10")
    assert len(data) == 10


def test_force_error_raises():
    c = MockMetaClient(seed=1, force_error="token_expired")
    from app.services.meta.errors import TokenExpired
    with pytest.raises(TokenExpired):
        c.publish_fb(FBPublishPayload(page_id="p1", token="t", media_type="text", caption="x"))
