"""Page CRUD API."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from app.core.auth import CurrentUser, require_org
from app.core.database import get_db_cursor
from app.core.permissions import Permission, require_permission, is_platform_wide, get_user_roles_and_batches
from app.models.schemas import PageCreate, PageUpdate, PageOut, MessageResponse

router = APIRouter(prefix="/pages", tags=["pages"])


def _get_org_id(user: CurrentUser) -> UUID:
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE clerk_org_id = %s", (user.org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        return row["id"]


@router.get("", response_model=list[PageOut])
async def list_pages(
    batch_id: UUID | None = None,
    user: CurrentUser = Depends(require_org),
):
    org_id = _get_org_id(user)
    roles, batch_ids, _ = get_user_roles_and_batches(user.clerk_user_id, user.org_id)

    with get_db_cursor() as cur:
        query = "SELECT * FROM pages WHERE org_id = %s"
        params: list = [org_id]

        # Batch scoping for non-platform-wide roles
        if not is_platform_wide(roles) and batch_ids:
            query += " AND batch_id = ANY(%s)"
            params.append(batch_ids)
        elif not is_platform_wide(roles):
            return []

        if batch_id:
            query += " AND batch_id = %s"
            params.append(batch_id)

        query += " ORDER BY name"
        cur.execute(query, params)
        rows = cur.fetchall()
        return [PageOut(**_serialize_page(r)) for r in rows]


def _serialize_page(row: dict) -> dict:
    """Convert DB row to PageOut-compatible dict."""
    d = dict(row)
    if d.get("active_hours_start"):
        d["active_hours_start"] = str(d["active_hours_start"])
    if d.get("active_hours_end"):
        d["active_hours_end"] = str(d["active_hours_end"])
    return d


@router.get("/{page_id}", response_model=PageOut)
async def get_page(page_id: UUID, user: CurrentUser = Depends(require_org)):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM pages WHERE id = %s AND org_id = %s", (page_id, org_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Page not found")
        return PageOut(**_serialize_page(row))


@router.post("", response_model=PageOut, status_code=201)
async def create_page(
    body: PageCreate,
    user: CurrentUser = require_permission(Permission.MANAGE_PAGES),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        # Verify batch belongs to org
        cur.execute("SELECT id FROM batches WHERE id = %s AND org_id = %s", (body.batch_id, org_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Batch not found")

        cur.execute(
            """INSERT INTO pages (org_id, batch_id, platform, platform_page_id, name,
                avatar_url, timezone, post_interval_hours, active_hours_start,
                active_hours_end, require_approval, monetization_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *""",
            (
                org_id, body.batch_id, body.platform.value, body.platform_page_id,
                body.name, body.avatar_url, body.timezone, body.post_interval_hours,
                body.active_hours_start, body.active_hours_end,
                body.require_approval, body.monetization_status.value,
            ),
        )
        row = cur.fetchone()
        return PageOut(**_serialize_page(row))


@router.patch("/{page_id}", response_model=PageOut)
async def update_page(
    page_id: UUID,
    body: PageUpdate,
    user: CurrentUser = require_permission(Permission.MANAGE_PAGES),
):
    org_id = _get_org_id(user)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Convert enums to values
    for k, v in updates.items():
        if hasattr(v, "value"):
            updates[k] = v.value

    set_clauses = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [page_id, org_id]

    with get_db_cursor() as cur:
        cur.execute(
            f"UPDATE pages SET {set_clauses} WHERE id = %s AND org_id = %s RETURNING *",
            values,
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Page not found")
        return PageOut(**_serialize_page(row))
