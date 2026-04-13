"""Reports API — insights, revenue, health scores."""

from uuid import UUID
from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query
from app.core.auth import CurrentUser
from app.core.database import get_db_cursor
from app.core.permissions import (
    Permission, require_permission, is_platform_wide, get_user_roles_and_batches
)
from app.models.schemas import PageInsightOut, RevenueRecordOut

router = APIRouter(prefix="/reports", tags=["reports"])


def _get_org_id(user: CurrentUser) -> UUID:
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE clerk_org_id = %s", (user.org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        return row["id"]


@router.get("/overview")
async def overview(
    period: str = Query(default="28d", pattern=r"^(7d|28d|90d)$"),
    batch_id: UUID | None = None,
    page_id: UUID | None = None,
    user: CurrentUser = require_permission(Permission.VIEW_REPORTS_OVERVIEW),
):
    """Dashboard overview KPI cards."""
    org_id = _get_org_id(user)
    roles, batch_ids, _ = get_user_roles_and_batches(user.clerk_user_id, user.org_id)

    days = {"7d": 7, "28d": 28, "90d": 90}[period]
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    prev_start = start_date - timedelta(days=days)

    with get_db_cursor() as cur:
        # Build page filter
        page_filter = ""
        params: list = [org_id]

        if page_id:
            page_filter = "AND pi.page_id = %s"
            params.append(page_id)
        elif batch_id:
            page_filter = "AND pi.page_id IN (SELECT id FROM pages WHERE batch_id = %s)"
            params.append(batch_id)
        elif not is_platform_wide(roles) and batch_ids:
            page_filter = "AND pi.page_id IN (SELECT id FROM pages WHERE batch_id = ANY(%s))"
            params.append(batch_ids)

        # Current period aggregates
        cur.execute(
            f"""SELECT
                COALESCE(SUM(views), 0) AS total_views,
                COALESCE(SUM(viewers), 0) AS total_viewers,
                COALESCE(SUM(follows), 0) AS total_follows,
                COALESCE(SUM(unfollows), 0) AS total_unfollows,
                COALESCE(SUM(visits), 0) AS total_visits,
                COALESCE(SUM(interactions), 0) AS total_interactions,
                COALESCE(SUM(link_clicks), 0) AS total_link_clicks,
                COALESCE(SUM(video_views), 0) AS total_video_views
            FROM page_insights pi
            WHERE pi.org_id = %s {page_filter}
            AND pi.period_start >= %s AND pi.period_end <= %s""",
            params + [start_date, end_date],
        )
        current = cur.fetchone()

        # Previous period for comparison
        cur.execute(
            f"""SELECT
                COALESCE(SUM(views), 0) AS total_views,
                COALESCE(SUM(follows), 0) AS total_follows,
                COALESCE(SUM(visits), 0) AS total_visits,
                COALESCE(SUM(interactions), 0) AS total_interactions
            FROM page_insights pi
            WHERE pi.org_id = %s {page_filter}
            AND pi.period_start >= %s AND pi.period_end <= %s""",
            params + [prev_start, start_date],
        )
        previous = cur.fetchone()

        def pct_change(curr_val, prev_val):
            if prev_val == 0:
                return 0
            return round(((curr_val - prev_val) / prev_val) * 100, 1)

        return {
            "period": period,
            "metrics": {
                "views": {
                    "value": current["total_views"],
                    "change": pct_change(current["total_views"], previous["total_views"]),
                },
                "viewers": {"value": current["total_viewers"]},
                "follows": {
                    "value": current["total_follows"],
                    "unfollows": current["total_unfollows"],
                    "change": pct_change(current["total_follows"], previous["total_follows"]),
                },
                "visits": {
                    "value": current["total_visits"],
                    "change": pct_change(current["total_visits"], previous["total_visits"]),
                },
                "interactions": {
                    "value": current["total_interactions"],
                    "change": pct_change(current["total_interactions"], previous["total_interactions"]),
                },
                "video_views": {"value": current["total_video_views"]},
                "link_clicks": {"value": current["total_link_clicks"]},
            },
        }


@router.get("/earnings")
async def earnings(
    period: str = Query(default="28d", pattern=r"^(7d|28d|90d)$"),
    batch_id: UUID | None = None,
    page_id: UUID | None = None,
    user: CurrentUser = require_permission(Permission.VIEW_REPORTS_EARNINGS),
):
    """Revenue/earnings breakdown."""
    org_id = _get_org_id(user)
    days = {"7d": 7, "28d": 28, "90d": 90}[period]
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    with get_db_cursor() as cur:
        page_filter = ""
        params: list = [org_id]

        if page_id:
            page_filter = "AND rr.page_id = %s"
            params.append(page_id)
        elif batch_id:
            page_filter = "AND rr.page_id IN (SELECT id FROM pages WHERE batch_id = %s)"
            params.append(batch_id)

        cur.execute(
            f"""SELECT
                COALESCE(SUM(total_cents), 0) AS total_cents,
                COALESCE(SUM(reels_cents), 0) AS reels_cents,
                COALESCE(SUM(photos_cents), 0) AS photos_cents,
                COALESCE(SUM(stories_cents), 0) AS stories_cents,
                COALESCE(SUM(text_cents), 0) AS text_cents,
                COALESCE(SUM(views), 0) AS total_views
            FROM revenue_records rr
            WHERE rr.org_id = %s {page_filter}
            AND rr.date >= %s AND rr.date <= %s""",
            params + [start_date, end_date],
        )
        row = cur.fetchone()

        total_cents = row["total_cents"]
        total_views = row["total_views"]
        rpm = (total_cents / total_views * 10) if total_views > 0 else 0  # cents per 1000 views

        return {
            "period": period,
            "total": total_cents / 100,
            "reels": row["reels_cents"] / 100,
            "photos": row["photos_cents"] / 100,
            "stories": row["stories_cents"] / 100,
            "text": row["text_cents"] / 100,
            "rpm": round(rpm, 2),
            "total_views": total_views,
            "currency": "USD",
        }


@router.get("/page-revenue")
async def page_revenue(
    period: str = Query(default="28d", pattern=r"^(7d|28d|90d)$"),
    user: CurrentUser = require_permission(Permission.VIEW_REPORTS_EARNINGS),
):
    """Per-page revenue breakdown."""
    org_id = _get_org_id(user)
    days = {"7d": 7, "28d": 28, "90d": 90}[period]
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    with get_db_cursor() as cur:
        cur.execute(
            """SELECT
                p.id, p.name, p.avatar_url, p.monetization_status,
                COALESCE(SUM(rr.total_cents), 0) AS total_cents,
                COALESCE(SUM(rr.views), 0) AS total_views
            FROM pages p
            LEFT JOIN revenue_records rr ON rr.page_id = p.id
                AND rr.date >= %s AND rr.date <= %s
            WHERE p.org_id = %s AND p.is_active = true
            GROUP BY p.id
            ORDER BY total_cents DESC""",
            (start_date, end_date, org_id),
        )
        rows = cur.fetchall()

        grand_total = sum(r["total_cents"] for r in rows) or 1

        return [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "avatar_url": r["avatar_url"],
                "revenue": r["total_cents"] / 100,
                "rpm": round((r["total_cents"] / r["total_views"] * 10), 2) if r["total_views"] > 0 else 0,
                "views": r["total_views"],
                "pct": round(r["total_cents"] / grand_total * 100, 1),
                "monetized": r["monetization_status"] == "enrolled",
            }
            for r in rows
        ]


@router.get("/posting-id-health")
async def posting_id_health(
    user: CurrentUser = require_permission(Permission.VIEW_REPORTS_POSTING_ID),
):
    """Posting ID health scores."""
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT id, name, avatar_url, facebook_user_id, status,
                health_score, reach_28d, last_used_at
            FROM posting_ids WHERE org_id = %s AND status != 'retired'
            ORDER BY health_score DESC""",
            (org_id,),
        )
        rows = cur.fetchall()

        return [
            {
                **r,
                "id": str(r["id"]),
                "health_label": (
                    "Healthy" if r["health_score"] >= 70
                    else "Declining" if r["health_score"] >= 40
                    else "Replace"
                ),
            }
            for r in rows
        ]
