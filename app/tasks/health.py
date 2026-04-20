import asyncio
from celery import shared_task
from app.core.database import get_connection
from app.services.oauth.token_monitor import ping_token_for_page
from app.services.insights.health_score import recompute_org_health_scores
from app.services.sse_bus import get_sse_bus


def ping_page_token_impl(page_id: str) -> str:
    return ping_token_for_page(page_id)


@shared_task(name="app.tasks.health.ping_page_token", acks_late=True, max_retries=2)
def ping_page_token(page_id: str):
    status = ping_page_token_impl(page_id)
    if status in ("token_expired", "token_expiring"):
        from app.tasks.email import send_transactional_email
        conn = get_connection()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("""SELECT p.org_id, p.name, u.email, u.id
                                 FROM pages p
                                 JOIN team_members tm ON tm.org_id = p.org_id
                                 JOIN users u ON u.id = tm.user_id
                                WHERE p.id=%s
                                  AND ('owner' = ANY(tm.roles) OR 'co_owner' = ANY(tm.roles))
                                LIMIT 1""", (page_id,))
                row = cur.fetchone()
                if row:
                    org_id = str(row["org_id"])
                    try:
                        asyncio.run(get_sse_bus().publish(org_id, "token_expired",
                                                          {"page_id": page_id, "severity": status}))
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        loop.run_until_complete(get_sse_bus().publish(org_id, "token_expired",
                                                                      {"page_id": page_id, "severity": status}))
                    send_transactional_email.delay(
                        to=row["email"], template="token_expired",
                        data={"page_name": row["name"], "severity": status},
                    )
        finally:
            conn.close()
    return status


@shared_task(name="app.tasks.health.check_all_tokens")
def check_all_tokens():
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""SELECT id FROM pages
                            WHERE token_expires_at IS NOT NULL
                              AND status IN ('ready', 'token_expiring')""")
            for row in cur.fetchall():
                ping_page_token.apply_async(args=[str(row["id"])], queue="health")
    finally:
        conn.close()


@shared_task(name="app.tasks.health.recompute_health_scores")
def recompute_health_scores(org_id: str):
    recompute_org_health_scores(org_id)
