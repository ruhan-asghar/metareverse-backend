from pydantic import BaseModel
from app.services.meta.client import MetaClient, FBPublishPayload, PublishResult


class FBPublishOutcome(BaseModel):
    platform_post_id: str
    published_at: str
    thread_comment_ids: list[str] = []


def publish_fb_post(
    client: MetaClient, *, page_id: str, token: str, media_type: str,
    caption: str, media_urls: list[str], thread_comments: list[str],
) -> FBPublishOutcome:
    r: PublishResult = client.publish_fb(FBPublishPayload(
        page_id=page_id, token=token, media_type=media_type,
        caption=caption, media_urls=media_urls,
    ))
    comment_ids = [
        client.add_thread_comment(page_id, token, r.platform_post_id, text)
        for text in thread_comments[:3]
    ]
    return FBPublishOutcome(
        platform_post_id=r.platform_post_id,
        published_at=r.published_at.isoformat(),
        thread_comment_ids=comment_ids,
    )
