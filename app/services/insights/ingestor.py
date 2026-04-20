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
                         views, interactions, video_views, follows)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (page_id, period_start, period_end) DO UPDATE SET
                        views        = EXCLUDED.views,
                        interactions = EXCLUDED.interactions,
                        video_views  = EXCLUDED.video_views,
                        follows      = EXCLUDED.follows,
                        fetched_at   = now()
                """, (
                    page_id, row["org_id"], pt.date, pt.date,
                    pt.reach, pt.engagement, pt.impressions, pt.followers,
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
                total = int(pt.cpm_cents) + int(pt.network_cents) + int(pt.other_cents)
                cur.execute("""
                    INSERT INTO revenue_records
                        (page_id, org_id, date, total_cents)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (page_id, date) DO UPDATE SET
                        total_cents = EXCLUDED.total_cents,
                        fetched_at  = now()
                """, (page_id, row["org_id"], pt.date, total))
            return len(data)
    finally:
        conn.close()
