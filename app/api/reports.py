"""Reports API — insights, revenue, health scores, per-ID perf, results, per-page detail.

All queries use the real schema from migrations/001_initial_schema.sql:
  * page_insights.period_start (NOT a "date" column)
  * page_insights: views, viewers, follows, unfollows, visits, interactions,
                   link_clicks, video_views (no reach/impressions/engagement/followers)
  * revenue_records.total_cents + per-media-type splits (reels/photos/stories/text)
  * posting_ids.facebook_user_id (masked for display)
  * posts caption columns: caption_facebook/instagram/threads (platform comes from pages)
"""

from uuid import UUID
from datetime import date, timedelta
from fastapi import APIRouter, HTTPException, Query
from app.core.auth import CurrentUser
from app.core.database import get_db_cursor
from app.core.permissions import (
    Permission, require_permission, is_platform_wide, get_user_roles_and_batches
)

router = APIRouter(prefix="/reports", tags=["reports"])

_PERIOD_DAYS = {"7d": 7, "28d": 28, "90d": 90}


def _get_org_id(user: CurrentUser) -> UUID:
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE clerk_org_id = %s", (user.org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        return row["id"]


def _mask_fb_user_id(uid: str | None) -> str:
    if not uid:
        return ""
    if len(uid) <= 8:
        return uid[0] + "…" + uid[-1] if len(uid) > 2 else uid
    return f"{uid[:4]}…{uid[-4:]}"


@router.get("/overview")
async def overview(
    period: str = Query(default="28d", pattern=r"^(7d|28d|90d)$"),
    batch_id: UUID | None = None,
    page_id: UUID | None = None,
    user: CurrentUser = require_permission(Permission.VIEW_REPORTS_OVERVIEW),
):
    """Dashboard overview KPI cards — real page_insights columns only."""
    org_id = _get_org_id(user)
    roles, batch_ids, _ = get_user_roles_and_batches(user.clerk_user_id, user.org_id)

    days = _PERIOD_DAYS[period]
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    prev_start = start_date - timedelta(days=days)

    with get_db_cursor() as cur:
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
    """Revenue broken out by media type (reels/photos/stories/text) + daily series."""
    org_id = _get_org_id(user)
    days = _PERIOD_DAYS[period]
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
        totals = cur.fetchone()

        cur.execute(
            f"""SELECT rr.date,
                   COALESCE(SUM(total_cents), 0) AS total_cents,
                   COALESCE(SUM(reels_cents), 0) AS reels_cents,
                   COALESCE(SUM(photos_cents), 0) AS photos_cents,
                   COALESCE(SUM(stories_cents), 0) AS stories_cents,
                   COALESCE(SUM(text_cents), 0) AS text_cents
            FROM revenue_records rr
            WHERE rr.org_id = %s {page_filter}
              AND rr.date >= %s AND rr.date <= %s
            GROUP BY rr.date
            ORDER BY rr.date""",
            params + [start_date, end_date],
        )
        series_rows = cur.fetchall()

        total_cents = int(totals["total_cents"])
        total_views = int(totals["total_views"])
        rpm_cents = round((total_cents / total_views) * 1000) if total_views > 0 else 0

        return {
            "period": period,
            "total_cents": total_cents,
            "reels_cents": int(totals["reels_cents"]),
            "photos_cents": int(totals["photos_cents"]),
            "stories_cents": int(totals["stories_cents"]),
            "text_cents": int(totals["text_cents"]),
            "total_views": total_views,
            "rpm_cents": rpm_cents,
            "currency": "USD",
            "series": [
                {
                    "date": r["date"].isoformat() if r["date"] else None,
                    "total_cents": int(r["total_cents"]),
                    "reels_cents": int(r["reels_cents"]),
                    "photos_cents": int(r["photos_cents"]),
                    "stories_cents": int(r["stories_cents"]),
                    "text_cents": int(r["text_cents"]),
                }
                for r in series_rows
            ],
        }


@router.get("/page-revenue")
async def page_revenue(
    period: str = Query(default="28d", pattern=r"^(7d|28d|90d)$"),
    user: CurrentUser = require_permission(Permission.VIEW_REPORTS_EARNINGS),
):
    """Per-page revenue breakdown."""
    org_id = _get_org_id(user)
    days = _PERIOD_DAYS[period]
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
                "revenue_cents": int(r["total_cents"]),
                "rpm_cents": round(r["total_cents"] / r["total_views"] * 1000) if r["total_views"] > 0 else 0,
                "views": int(r["total_views"]),
                "pct": round(r["total_cents"] / grand_total * 100, 1),
                "monetized": r["monetization_status"] == "enrolled",
            }
            for r in rows
        ]


@router.get("/posting-id-health")
async def posting_id_health(
    user: CurrentUser = require_permission(Permission.VIEW_REPORTS_POSTING_ID),
):
    """Posting ID health scores. Column is facebook_user_id (no platform_user_id)."""
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT id, name, avatar_url, facebook_user_id, status,
                      health_score, reach_28d, last_used_at
               FROM posting_ids
               WHERE org_id = %s AND status != 'retired'
               ORDER BY health_score DESC""",
            (org_id,),
        )
        rows = cur.fetchall()

        out = []
        for r in rows:
            score = int(r["health_score"] or 0)
            out.append({
                "id": str(r["id"]),
                "name": r["name"],
                "avatar_url": r["avatar_url"],
                "facebook_user_id_masked": _mask_fb_user_id(r["facebook_user_id"]),
                "status": r["status"],
                "health_score": score,
                "reach_28d": int(r["reach_28d"] or 0),
                "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None,
                "health_label": (
                    "Healthy" if score >= 70
                    else "Declining" if score >= 40
                    else "Replace"
                ),
            })
        return out


@router.get("/id-performance")
async def id_performance(
    user: CurrentUser = require_permission(Permission.VIEW_REPORTS_POSTING_ID),
):
    """Posting ID perf with usage stats (posts published, reach). Masks user IDs."""
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT pid.id, pid.name, pid.avatar_url, pid.facebook_user_id,
                      pid.status, pid.health_score, pid.reach_28d, pid.last_used_at,
                      COUNT(DISTINCT po.id) FILTER (WHERE po.status = 'published') AS posts_published_28d
               FROM posting_ids pid
               LEFT JOIN posts po
                 ON po.posting_id_used = pid.id
                AND po.published_at >= current_date - interval '28 days'
               WHERE pid.org_id = %s
               GROUP BY pid.id
               ORDER BY pid.health_score DESC""",
            (org_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "avatar_url": r["avatar_url"],
                "facebook_user_id_masked": _mask_fb_user_id(r["facebook_user_id"]),
                "status": r["status"],
                "health_score": int(r["health_score"] or 0),
                "reach_28d": int(r["reach_28d"] or 0),
                "posts_published_28d": int(r["posts_published_28d"] or 0),
                "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None,
            }
            for r in rows
        ]


@router.get("/results")
async def results(
    period: str = Query(default="28d", pattern=r"^(7d|28d|90d)$"),
    batch_id: UUID | None = None,
    user: CurrentUser = require_permission(Permission.VIEW_REPORTS_RESULTS),
):
    """Top posts by reach. Joins pages for platform, uses COALESCE caption."""
    org_id = _get_org_id(user)
    days = _PERIOD_DAYS[period]
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    with get_db_cursor() as cur:
        extra_where = ""
        params: list = [org_id, start_date, end_date]
        if batch_id:
            extra_where = "AND p.batch_id = %s"
            params.append(batch_id)

        cur.execute(
            f"""SELECT po.id, po.status, po.media_type, po.published_at,
                        COALESCE(po.caption_facebook, po.caption_instagram, po.caption_threads) AS caption,
                        p.id AS page_id, p.name AS page_name, p.platform, p.avatar_url,
                        COALESCE(pi.reach, 0) AS reach,
                        COALESCE(pi.views, 0) AS views,
                        COALESCE(pi.reactions, 0) + COALESCE(pi.comments, 0) + COALESCE(pi.shares, 0) AS engagement,
                        COALESCE(pi.revenue_cents, 0) AS revenue_cents
                FROM posts po
                JOIN pages p ON p.id = po.page_id
                LEFT JOIN post_insights pi ON pi.post_id = po.id
                WHERE po.org_id = %s
                  AND po.status = 'published'
                  AND po.published_at::date >= %s
                  AND po.published_at::date <= %s
                  {extra_where}
                ORDER BY COALESCE(pi.reach, 0) DESC
                LIMIT 20""",
            params,
        )
        top_rows = cur.fetchall()

        cur.execute(
            f"""SELECT
                  COUNT(*) FILTER (WHERE po.status = 'published') AS total_published,
                  COUNT(*) FILTER (WHERE po.status = 'failed_temporary'
                                      OR po.status = 'failed_needs_editing') AS total_failed
                FROM posts po
                JOIN pages p ON p.id = po.page_id
                WHERE po.org_id = %s
                  AND COALESCE(po.published_at, po.failed_at, po.scheduled_at)::date >= %s
                  AND COALESCE(po.published_at, po.failed_at, po.scheduled_at)::date <= %s
                  {extra_where}""",
            params,
        )
        summary = cur.fetchone()

        return {
            "period": period,
            "summary": {
                "total_published": int(summary["total_published"] or 0),
                "total_failed": int(summary["total_failed"] or 0),
            },
            "top_posts": [
                {
                    "id": str(r["id"]),
                    "caption": (r["caption"] or "")[:160],
                    "media_type": r["media_type"],
                    "status": r["status"],
                    "published_at": r["published_at"].isoformat() if r["published_at"] else None,
                    "page": {
                        "id": str(r["page_id"]),
                        "name": r["page_name"],
                        "platform": r["platform"],
                        "avatar_url": r["avatar_url"],
                    },
                    "reach": int(r["reach"] or 0),
                    "views": int(r["views"] or 0),
                    "engagement": int(r["engagement"] or 0),
                    "revenue_cents": int(r["revenue_cents"] or 0),
                }
                for r in top_rows
            ],
        }


@router.get("/page/{page_id}")
async def page_report(
    page_id: UUID,
    period: str = Query(default="28d", pattern=r"^(7d|28d|90d)$"),
    user: CurrentUser = require_permission(Permission.VIEW_REPORTS_OVERVIEW),
):
    """Per-page detail: insights rows + revenue rows over the period."""
    org_id = _get_org_id(user)
    days = _PERIOD_DAYS[period]
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    with get_db_cursor() as cur:
        cur.execute(
            """SELECT id, name, platform, avatar_url, status, follower_count,
                      monetization_status, batch_id
               FROM pages WHERE id = %s AND org_id = %s""",
            (page_id, org_id),
        )
        page = cur.fetchone()
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")

        cur.execute(
            """SELECT period_start AS date, views, viewers, follows, unfollows,
                      visits, interactions, link_clicks, video_views
               FROM page_insights
               WHERE page_id = %s
                 AND period_start >= %s
                 AND period_end <= %s
               ORDER BY period_start""",
            (page_id, start_date, end_date),
        )
        insights_rows = cur.fetchall()

        cur.execute(
            """SELECT date, total_cents, reels_cents, photos_cents,
                      stories_cents, text_cents, views
               FROM revenue_records
               WHERE page_id = %s AND date >= %s AND date <= %s
               ORDER BY date""",
            (page_id, start_date, end_date),
        )
        revenue_rows = cur.fetchall()

        total_rev_cents = sum(int(r["total_cents"] or 0) for r in revenue_rows)
        total_views = sum(int(r["views"] or 0) for r in insights_rows) or sum(
            int(r["views"] or 0) for r in revenue_rows
        )

        return {
            "page": {
                "id": str(page["id"]),
                "name": page["name"],
                "platform": page["platform"],
                "avatar_url": page["avatar_url"],
                "status": page["status"],
                "follower_count": int(page["follower_count"] or 0),
                "monetization_status": page["monetization_status"],
                "batch_id": str(page["batch_id"]) if page["batch_id"] else None,
            },
            "period": period,
            "insights": [
                {
                    "date": r["date"].isoformat() if r["date"] else None,
                    "views": int(r["views"] or 0),
                    "viewers": int(r["viewers"] or 0),
                    "follows": int(r["follows"] or 0),
                    "unfollows": int(r["unfollows"] or 0),
                    "visits": int(r["visits"] or 0),
                    "interactions": int(r["interactions"] or 0),
                    "link_clicks": int(r["link_clicks"] or 0),
                    "video_views": int(r["video_views"] or 0),
                }
                for r in insights_rows
            ],
            "revenue": [
                {
                    "date": r["date"].isoformat() if r["date"] else None,
                    "total_cents": int(r["total_cents"] or 0),
                    "reels_cents": int(r["reels_cents"] or 0),
                    "photos_cents": int(r["photos_cents"] or 0),
                    "stories_cents": int(r["stories_cents"] or 0),
                    "text_cents": int(r["text_cents"] or 0),
                }
                for r in revenue_rows
            ],
            "totals": {
                "revenue_cents": total_rev_cents,
                "views": total_views,
                "rpm_cents": round(total_rev_cents / total_views * 1000) if total_views > 0 else 0,
            },
        }
