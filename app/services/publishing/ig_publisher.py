from pydantic import BaseModel
from app.services.meta.client import MetaClient, IGPublishPayload


class IGPublishOutcome(BaseModel):
    platform_post_id: str
    published_at: str


def publish_ig_post(
    client: MetaClient, *, page_id: str, token: str, media_type: str,
    caption: str, media_urls: list[str],
) -> IGPublishOutcome:
    r = client.publish_ig(IGPublishPayload(
        page_id=page_id, token=token, media_type=media_type,
        caption=caption, media_urls=media_urls,
    ))
    return IGPublishOutcome(platform_post_id=r.platform_post_id, published_at=r.published_at.isoformat())
