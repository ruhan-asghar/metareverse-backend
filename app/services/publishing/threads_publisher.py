from pydantic import BaseModel
from app.services.meta.client import MetaClient, ThreadsPublishPayload


class ThreadsPublishOutcome(BaseModel):
    platform_post_id: str
    published_at: str


def publish_threads_post(
    client: MetaClient, *, page_id: str, token: str, media_type: str,
    caption: str, media_urls: list[str],
) -> ThreadsPublishOutcome:
    r = client.publish_threads(ThreadsPublishPayload(
        page_id=page_id, token=token, media_type=media_type,
        caption=caption, media_urls=media_urls,
    ))
    return ThreadsPublishOutcome(platform_post_id=r.platform_post_id, published_at=r.published_at.isoformat())
