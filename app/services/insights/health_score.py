from app.core.database import get_connection


def recompute_org_health_scores(org_id: str) -> None:
    """Recompute health scores for all posting_ids in an org.

    Formula: round((reach_28d / max_reach_28d_on_account) * 100), scoped per org.
    Uses posting_ids.reach_28d (populated separately by insights ingestion).
    """
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH max_reach AS (
                    SELECT GREATEST(COALESCE(MAX(reach_28d), 0), 1) AS m
                      FROM posting_ids
                     WHERE org_id = %s
                )
                UPDATE posting_ids pi
                   SET health_score = LEAST(100, GREATEST(0,
                       ROUND((COALESCE(pi.reach_28d, 0)::numeric / mr.m) * 100)::int))
                  FROM max_reach mr
                 WHERE pi.org_id = %s
                """,
                (org_id, org_id),
            )
    finally:
        conn.close()
