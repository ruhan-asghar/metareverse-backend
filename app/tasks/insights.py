import asyncio
from celery import shared_task
from app.core.database import get_connection
from app.services.insights.ingestor import ingest_page_insights, ingest_page_revenue
from app.services.insights.health_score import recompute_org_health_scores
from app.services.sse_bus import get_sse_bus


def _emit(org_id: str, event_type: str, payload: dict):
    try:
        asyncio.run(get_sse_bus().publish(org_id, event_type, payload))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(get_sse_bus().publish(org_id, event_type, payload))


def refresh_page_insights_impl(page_id: str, days: int = 1) -> int:
    n = ingest_page_insights(page_id, days=days)
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT org_id FROM pages WHERE id=%s", (page_id,))
            row = cur.fetchone()
            if row:
                _emit(str(row["org_id"]), "insights_refreshed", {"page_id": page_id, "points": n})
    finally:
        conn.close()
    return n


def refresh_page_revenue_impl(page_id: str, days: int = 1) -> int:
    n = ingest_page_revenue(page_id, days=days)
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT org_id FROM pages WHERE id=%s", (page_id,))
            row = cur.fetchone()
            if row:
                _emit(str(row["org_id"]), "revenue_refreshed", {"page_id": page_id, "points": n})
    finally:
        conn.close()
    return n


@shared_task(name="app.tasks.insights.refresh_page_insights", acks_late=True, max_retries=3)
def refresh_page_insights(page_id: str, days: int = 1):
    return refresh_page_insights_impl(page_id, days=days)


@shared_task(name="app.tasks.insights.refresh_page_revenue", acks_late=True, max_retries=3)
def refresh_page_revenue(page_id: str, days: int = 1):
    return refresh_page_revenue_impl(page_id, days=days)


@shared_task(name="app.tasks.insights.refresh_all_page_insights")
def refresh_all_page_insights():
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM pages WHERE status IN ('ready','token_expiring')")
            for row in cur.fetchall():
                refresh_page_insights.apply_async(args=[str(row["id"])], queue="insights")
    finally:
        conn.close()


@shared_task(name="app.tasks.insights.refresh_all_revenue")
def refresh_all_revenue():
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM pages WHERE status IN ('ready','token_expiring')")
            for row in cur.fetchall():
                refresh_page_revenue.apply_async(args=[str(row["id"])], queue="insights")
    finally:
        conn.close()


@shared_task(name="app.tasks.insights.recompute_health_scores")
def recompute_health_scores(org_id: str):
    recompute_org_health_scores(org_id)
