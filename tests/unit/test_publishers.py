from app.services.meta.mock_client import MockMetaClient
from app.services.publishing.fb_publisher import publish_fb_post
from app.services.publishing.ig_publisher import publish_ig_post
from app.services.publishing.threads_publisher import publish_threads_post


def test_fb_photo():
    c = MockMetaClient(seed=1)
    r = publish_fb_post(c, page_id="p", token="t", media_type="photo",
                       caption="hi", media_urls=["u"], thread_comments=[])
    assert r.platform_post_id.startswith("fb_")


def test_fb_with_thread_comments():
    c = MockMetaClient(seed=1)
    r = publish_fb_post(c, page_id="p", token="t", media_type="photo",
                       caption="hi", media_urls=["u"], thread_comments=["c1", "c2"])
    assert len(r.thread_comment_ids) == 2


def test_ig_reel():
    c = MockMetaClient(seed=1)
    r = publish_ig_post(c, page_id="p", token="t", media_type="reel",
                       caption="hi", media_urls=["u"])
    assert r.platform_post_id.startswith("ig_")


def test_threads_text():
    c = MockMetaClient(seed=1)
    r = publish_threads_post(c, page_id="p", token="t", media_type="text", caption="hi", media_urls=[])
    assert r.platform_post_id.startswith("th_")
