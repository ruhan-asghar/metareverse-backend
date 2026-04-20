from datetime import date, timedelta
from app.core.database import get_connection
from app.core.encryption import decrypt_token
from app.services.meta import get_meta_client


def ingest_page_insights(page_id: str, days: int = 7):
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""SELECT platform_page_id, token_encrypted, token_iv, org_id
                             FROM pages WHERE id=%s""", (page_id,))
            row = cur.fetchone()
            if not row:
                return 0
            token = decrypt_token(bytes(row["token_encrypted"]), bytes(row["token_iv"]))
            until = date.today()
            since = until - timedelta(days=days - 1)
            data = get_meta_client().get_page_insights(row["platform_page_id"], token,
                                                       since.isoformat(), until.isoformat())
            for pt in data:
                cur.execute("""
                    INSERT INTO page_insights (page_id, org_id, date, reach, impressions, engagement, followers)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (page_id, date) DO UPDATE SET
                        reach=EXCLUDED.reach, impressions=EXCLUDED.impressions,
                        engagement=EXCLUDED.engagement, followers=EXCLUDED.followers
                """, (page_id, row["org_id"], pt.date, pt.reach, pt.impressions, pt.engagement, pt.followers))
            return len(data)
    finally:
        conn.close()


def ingest_page_revenue(page_id: str, days: int = 7):
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""SELECT platform_page_id, token_encrypted, token_iv, org_id
                             FROM pages WHERE id=%s""", (page_id,))
            row = cur.fetchone()
            if not row:
                return 0
            token = decrypt_token(bytes(row["token_encrypted"]), bytes(row["token_iv"]))
            until = date.today()
            since = until - timedelta(days=days - 1)
            data = get_meta_client().get_monetization_insights(row["platform_page_id"], token,
                                                               since.isoformat(), until.isoformat())
            for pt in data:
                cur.execute("""
                    INSERT INTO revenue_records (page_id, org_id, date, cpm_cents, network_cents, other_cents)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (page_id, date) DO UPDATE SET
                        cpm_cents=EXCLUDED.cpm_cents, network_cents=EXCLUDED.network_cents,
                        other_cents=EXCLUDED.other_cents
                """, (page_id, row["org_id"], pt.date, pt.cpm_cents, pt.network_cents, pt.other_cents))
            return len(data)
    finally:
        conn.close()
