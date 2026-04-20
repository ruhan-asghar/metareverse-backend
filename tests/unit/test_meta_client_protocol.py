from app.services.meta.client import MetaClient, FBPublishPayload, IGPublishPayload, ThreadsPublishPayload


def test_protocol_has_required_methods():
    required = {"exchange_code", "list_pages", "get_page_token", "publish_fb", "publish_ig",
                "publish_threads", "add_thread_comment", "get_page_insights",
                "get_monetization_insights", "ping_token"}
    assert required.issubset({m for m in dir(MetaClient) if not m.startswith("_")})


def test_payload_types():
    p = FBPublishPayload(page_id="p1", token="t", media_type="photo", caption="hi", media_urls=["http://x"])
    assert p.caption == "hi"
