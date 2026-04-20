from datetime import date, timedelta
from app.core.database import get_connection
from app.core.encryption import decrypt_token
from app.services.meta import get_meta_client


def _load_page_ctx(cur, page_id: str):
    cur.execute(
        """SELECT platform_page_id, encrypted_access_token, org_id
             FROM pages WHERE id=%s""",
        (page_id,),
    )
    row = cur.fetchone()
    if not row or not row["encrypted_access_token"]:
        return None
    token = decrypt_token(bytes(row["encrypted_access_token"]))
    return row, token


def ingest_page_insights(page_id: str, days: int = 7):
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            ctx = _load_page_ctx(cur, page_id)
            if not ctx:
                return 0
            row, token = ctx
            until = date.today()
            since = until - timedelta(days=days - 1)
            data = get_meta_client().get_page_insights(
                row["platform_page_id"], token, since.isoformat(), until.isoformat()
            )
            for pt in data:
                # Each point is a single day; period_start = period_end = pt.date
                cur.execute("""
                    INSERT INTO page_insights
                        (page_id, org_id, period_start, period_end,
                         views, viewers, interactions, follows, video_views,
                         reactions, comments, shares)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (page_id, period_start, period_end) DO UPDATE SET
                        views        = EXCLUDED.views,
                        viewers      = EXCLUDED.viewers,
                        interactions = EXCLUDED.interactions,
                        follows      = EXCLUDED.follows,
                        video_views  = EXCLUDED.video_views,
                        reactions    = EXCLUDED.reactions,
                        comments     = EXCLUDED.comments,
                        shares       = EXCLUDED.shares,
                        fetched_at   = now()
                """, (
                    page_id, row["org_id"], pt.date, pt.date,
                    pt.views, pt.viewers, pt.interactions, pt.follows, pt.video_views,
                    pt.reactions, pt.comments, pt.shares,
                ))
            return len(data)
    finally:
        conn.close()


def ingest_page_revenue(page_id: str, days: int = 7):
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            ctx = _load_page_ctx(cur, page_id)
            if not ctx:
                return 0
            row, token = ctx
            until = date.today()
            since = until - timedelta(days=days - 1)
            data = get_meta_client().get_monetization_insights(
                row["platform_page_id"], token, since.isoformat(), until.isoformat()
            )
            for pt in data:
                cur.execute("""
                    INSERT INTO revenue_records
                        (page_id, org_id, date, total_cents,
                         reels_cents, photos_cents, stories_cents, text_cents)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (page_id, date) DO UPDATE SET
                        total_cents   = EXCLUDED.total_cents,
                        reels_cents   = EXCLUDED.reels_cents,
                        photos_cents  = EXCLUDED.photos_cents,
                        stories_cents = EXCLUDED.stories_cents,
                        text_cents    = EXCLUDED.text_cents,
                        fetched_at    = now()
                """, (
                    page_id, row["org_id"], pt.date, pt.total_cents,
                    pt.reels_cents, pt.photos_cents, pt.stories_cents, pt.text_cents,
                ))
            return len(data)
    finally:
        conn.close()
