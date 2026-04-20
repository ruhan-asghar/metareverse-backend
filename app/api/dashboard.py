"""Dashboard stats — consolidated top-level KPI card counts."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, require_org
from app.core.database import get_db_cursor

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _resolve_org_uuid(clerk_org_id: str) -> str:
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE clerk_org_id = %s", (clerk_org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        return str(row["id"])


@router.get("/stats")
async def dashboard_stats(user: CurrentUser = Depends(require_org)):
    org_uuid = _resolve_org_uuid(user.org_id)
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT
                (SELECT COUNT(*) FROM pages WHERE org_id = %s AND status = 'ready') AS pages_ready,
                (SELECT COUNT(*) FROM pages WHERE org_id = %s AND status = 'token_expired') AS pages_expired,
                (SELECT COUNT(*) FROM pages WHERE org_id = %s AND status = 'needs_setup') AS pages_needs_setup,
                (SELECT COUNT(*) FROM posts WHERE org_id = %s AND status = 'queued') AS queued,
                (SELECT COUNT(*) FROM posts WHERE org_id = %s AND status = 'pending_approval') AS pending,
                (SELECT COUNT(*) FROM posts WHERE org_id = %s AND status = 'failed_temporary') AS failed,
                (SELECT COALESCE(SUM(r.total_cents), 0)
                   FROM revenue_records r
                   JOIN pages p ON p.id = r.page_id
                  WHERE p.org_id = %s
                    AND r.date >= current_date - interval '30 days') AS revenue_30d_cents
            """,
            (org_uuid, org_uuid, org_uuid, org_uuid, org_uuid, org_uuid, org_uuid),
        )
        row = cur.fetchone()
        return {
            "pages_ready": row["pages_ready"],
            "pages_expired": row["pages_expired"],
            "pages_needs_setup": row["pages_needs_setup"],
            "posts_queued": row["queued"],
            "posts_pending_approval": row["pending"],
            "posts_failed": row["failed"],
            "revenue_30d_cents": int(row["revenue_30d_cents"] or 0),
        }
