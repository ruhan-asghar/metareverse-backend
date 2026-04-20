import asyncio
from celery import shared_task
from app.core.database import get_connection
from app.core.encryption import decrypt_token
from app.core.logging import get_logger
from app.services.meta import get_meta_client
from app.services.meta.errors import (
    TokenExpired, RateLimited, PostingIDRevoked, MediaRejected,
    MetaTimeout, TransientMetaError,
)
from app.services.publishing.fb_publisher import publish_fb_post
from app.services.publishing.ig_publisher import publish_ig_post
from app.services.publishing.threads_publisher import publish_threads_post
from app.services.publishing.rotation import pick_round_robin, PostingIDCandidate
from app.services.sse_bus import get_sse_bus

log = get_logger("tasks.publishing")


_PLATFORM_POST_ID_COL = {
    "facebook": "platform_post_id_fb",
    "instagram": "platform_post_id_ig",
    "threads": "platform_post_id_th",
}

_CAPTION_KEY = {
    "facebook": "caption_facebook",
    "instagram": "caption_instagram",
    "threads": "caption_threads",
}


def _publish_event(org_id: str, event_type: str, payload: dict):
    try:
        asyncio.run(get_sse_bus().publish(org_id, event_type, payload))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(get_sse_bus().publish(org_id, event_type, payload))


def _claim(cur, post_id: str) -> dict | None:
    cur.execute("""
        UPDATE posts
           SET status='publishing', publishing_started_at=now()
         WHERE id=%s AND status IN ('queued', 'failed_temporary')
         RETURNING id, org_id, page_id, media_type,
                   caption_facebook, caption_instagram, caption_threads,
                   publish_to_facebook, publish_to_instagram, publish_to_threads
    """, (post_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def _load_page_and_token(cur, page_id: str):
    cur.execute("""SELECT id, platform, platform_page_id, encrypted_access_token,
                          token_expires_at, status, batch_id, org_id
                     FROM pages WHERE id=%s""", (page_id,))
    page = cur.fetchone()
    if not page or not page["encrypted_access_token"]:
        return None
    token = decrypt_token(bytes(page["encrypted_access_token"]))
    return dict(page), token


def _load_media_urls(cur, post_id: str) -> list[str]:
    cur.execute(
        """SELECT file_url FROM post_media WHERE post_id=%s ORDER BY sort_order""",
        (post_id,),
    )
    return [r["file_url"] for r in cur.fetchall()]


def _load_thread_comments(cur, post_id: str) -> list[str]:
    cur.execute(
        """SELECT content FROM thread_comments WHERE post_id=%s ORDER BY sort_order""",
        (post_id,),
    )
    return [r["content"] for r in cur.fetchall()]


def _load_candidates(cur, page_id: str) -> list[PostingIDCandidate]:
    cur.execute("""
        SELECT pi.id, pi.status, pi.health_score, pi.last_used_at
          FROM posting_ids pi
          JOIN page_posting_id_assignments a ON a.posting_id_id = pi.id
         WHERE a.page_id = %s
    """, (page_id,))
    return [PostingIDCandidate(id=str(r["id"]), status=r["status"],
                                health_score=r["health_score"],
                                last_used_at=r["last_used_at"])
            for r in cur.fetchall()]


def publish_post_impl(post_id: str) -> None:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            post = _claim(cur, post_id)
            if not post:
                log.info("publish_skipped", post_id=str(post_id), reason="already_processed")
                return
            org_id = str(post["org_id"])
            _publish_event(org_id, "post_publishing", {"post_id": str(post_id)})

            page_tok = _load_page_and_token(cur, post["page_id"])
            if not page_tok:
                cur.execute(
                    """UPDATE posts
                          SET status='failed_needs_editing',
                              failed_category='needs_editing',
                              publishing_started_at=NULL
                        WHERE id=%s""",
                    (post_id,),
                )
                return
            page, token = page_tok

            platform = page["platform"]
            caption = post.get(_CAPTION_KEY[platform]) or ""
            media_urls = _load_media_urls(cur, post_id)
            thread_comments = _load_thread_comments(cur, post_id)

            candidates = _load_candidates(cur, post["page_id"])
            posting_id = pick_round_robin(candidates)
            if not posting_id:
                cur.execute(
                    "UPDATE posts SET status='paused', publishing_started_at=NULL WHERE id=%s",
                    (post_id,),
                )
                _publish_event(org_id, "post_paused", {"post_id": str(post_id)})
                return

            try:
                if platform == "facebook":
                    out = publish_fb_post(
                        get_meta_client(), page_id=page["platform_page_id"], token=token,
                        media_type=post["media_type"], caption=caption,
                        media_urls=media_urls, thread_comments=thread_comments,
                    )
                elif platform == "instagram":
                    out = publish_ig_post(
                        get_meta_client(), page_id=page["platform_page_id"], token=token,
                        media_type=post["media_type"], caption=caption,
                        media_urls=media_urls,
                    )
                else:
                    out = publish_threads_post(
                        get_meta_client(), page_id=page["platform_page_id"], token=token,
                        media_type=post["media_type"], caption=caption,
                        media_urls=media_urls,
                    )
                platform_col = _PLATFORM_POST_ID_COL[platform]
                cur.execute(
                    f"""
                    UPDATE posts SET status='published', {platform_col}=%s,
                           posting_id_used=%s, published_at=now(),
                           publishing_started_at=NULL
                     WHERE id=%s
                    """,
                    (out.platform_post_id, posting_id.id, post_id),
                )
                cur.execute(
                    "UPDATE posting_ids SET last_used_at=now() WHERE id=%s",
                    (posting_id.id,),
                )
                cur.execute(
                    """UPDATE page_posting_id_assignments
                          SET last_used_at=now()
                        WHERE page_id=%s AND posting_id_id=%s""",
                    (post["page_id"], posting_id.id),
                )
                _publish_event(org_id, "post_published",
                               {"post_id": str(post_id), "platform_post_id": out.platform_post_id})
            except TokenExpired:
                cur.execute(
                    "UPDATE posts SET status='reconnect_required', publishing_started_at=NULL WHERE id=%s",
                    (post_id,),
                )
                _publish_event(org_id, "token_expired",
                               {"post_id": str(post_id), "page_id": str(post["page_id"])})
            except PostingIDRevoked:
                cur.execute("UPDATE posting_ids SET status='retired' WHERE id=%s", (posting_id.id,))
                cur.execute(
                    "UPDATE posts SET status='paused', publishing_started_at=NULL WHERE id=%s",
                    (post_id,),
                )
                _publish_event(org_id, "post_paused", {"post_id": str(post_id)})
            except MediaRejected:
                cur.execute(
                    """UPDATE posts
                          SET status='failed_needs_editing',
                              failed_category='needs_editing',
                              publishing_started_at=NULL
                        WHERE id=%s""",
                    (post_id,),
                )
                _publish_event(org_id, "post_failed", {"post_id": str(post_id), "permanent": True})
            except (MetaTimeout, TransientMetaError, RateLimited):
                cur.execute(
                    """UPDATE posts
                          SET status='failed_temporary',
                              failed_category='temporary_issue',
                              publishing_started_at=NULL
                        WHERE id=%s""",
                    (post_id,),
                )
                _publish_event(org_id, "post_failed", {"post_id": str(post_id), "permanent": False})
                raise
    finally:
        conn.close()


@shared_task(
    bind=True,
    autoretry_for=(TransientMetaError, MetaTimeout, RateLimited),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
    reject_on_worker_lost=True,
    name="app.tasks.publishing.publish_post",
)
def publish_post(self, post_id: str):
    publish_post_impl(post_id)


@shared_task(name="app.tasks.publishing.reclaim_orphans")
def reclaim_orphans():
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE posts
                   SET status = CASE WHEN reclaim_count >= 3 THEN 'failed_temporary' ELSE 'queued' END,
                       reclaim_count = reclaim_count + 1,
                       publishing_started_at = NULL
                 WHERE status = 'publishing'
                   AND publishing_started_at < now() - interval '5 minutes'
                RETURNING id, reclaim_count
            """)
            for row in cur.fetchall():
                if row["reclaim_count"] < 3:
                    publish_post.delay(str(row["id"]))
    finally:
        conn.close()
