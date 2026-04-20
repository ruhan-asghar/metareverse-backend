from app.core.database import get_connection


def recompute_org_health_scores(org_id: str) -> None:
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                WITH pid_reach AS (
                  SELECT pi.id AS posting_id, COALESCE(SUM(post_i.reach), 0) AS reach_28d
                    FROM posting_ids pi
                    LEFT JOIN posts p ON p.posting_id_id = pi.id
                       AND p.published_at >= now() - interval '28 days'
                    LEFT JOIN post_insights post_i ON post_i.post_id = p.id
                   WHERE pi.org_id = %s
                GROUP BY pi.id
                ),
                max_reach AS (SELECT GREATEST(MAX(reach_28d), 1) AS m FROM pid_reach)
                UPDATE posting_ids pi
                   SET health_score = LEAST(100, GREATEST(0, ROUND((pr.reach_28d::numeric / mr.m) * 100)::int)),
                       reach_28d = pr.reach_28d
                  FROM pid_reach pr, max_reach mr
                 WHERE pi.id = pr.posting_id
            """, (org_id,))
    finally:
        conn.close()
