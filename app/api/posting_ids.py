"""Posting ID CRUD API."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from app.core.auth import CurrentUser
from app.core.database import get_db_cursor
from app.core.permissions import Permission, require_permission
from app.models.schemas import PostingIdCreate, PostingIdOut, PostingIdRetire, MessageResponse

router = APIRouter(prefix="/posting-ids", tags=["posting-ids"])


def _get_org_id(user: CurrentUser) -> UUID:
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE clerk_org_id = %s", (user.org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        return row["id"]


@router.get("", response_model=list[PostingIdOut])
async def list_posting_ids(
    user: CurrentUser = require_permission(Permission.MANAGE_PAGES),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT * FROM posting_ids WHERE org_id = %s ORDER BY created_at",
            (org_id,),
        )
        return [PostingIdOut(**r) for r in cur.fetchall()]


@router.get("/{pid_id}", response_model=PostingIdOut)
async def get_posting_id(
    pid_id: UUID,
    user: CurrentUser = require_permission(Permission.MANAGE_PAGES),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT * FROM posting_ids WHERE id = %s AND org_id = %s",
            (pid_id, org_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Posting ID not found")
        return PostingIdOut(**row)


@router.post("", response_model=PostingIdOut, status_code=201)
async def create_posting_id(
    body: PostingIdCreate,
    user: CurrentUser = require_permission(Permission.MANAGE_PAGES),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO posting_ids (org_id, facebook_user_id, name, avatar_url)
            VALUES (%s, %s, %s, %s) RETURNING *""",
            (org_id, body.facebook_user_id, body.name, body.avatar_url),
        )
        return PostingIdOut(**cur.fetchone())


@router.post("/{pid_id}/retire", response_model=PostingIdOut)
async def retire_posting_id(
    pid_id: UUID,
    body: PostingIdRetire,
    user: CurrentUser = require_permission(Permission.MANAGE_PAGES),
):
    """Retire a posting ID. This is permanent — cannot be undone."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Must confirm retirement")

    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            """UPDATE posting_ids SET status = 'retired', retired_at = now()
            WHERE id = %s AND org_id = %s AND status != 'retired'
            RETURNING *""",
            (pid_id, org_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Posting ID not found or already retired")
        return PostingIdOut(**row)


@router.post("/{pid_id}/assign/{page_id}", response_model=MessageResponse)
async def assign_to_page(
    pid_id: UUID,
    page_id: UUID,
    user: CurrentUser = require_permission(Permission.MANAGE_PAGES),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        # Verify both belong to org
        cur.execute("SELECT id FROM posting_ids WHERE id = %s AND org_id = %s AND status = 'active'", (pid_id, org_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Active Posting ID not found")

        cur.execute("SELECT id FROM pages WHERE id = %s AND org_id = %s", (page_id, org_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Page not found")

        # Get next sort order
        cur.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM page_posting_id_assignments WHERE page_id = %s",
            (page_id,),
        )
        next_order = cur.fetchone()["next_order"]

        cur.execute(
            """INSERT INTO page_posting_id_assignments (page_id, posting_id_id, sort_order)
            VALUES (%s, %s, %s)
            ON CONFLICT (page_id, posting_id_id) DO NOTHING""",
            (page_id, pid_id, next_order),
        )
    return MessageResponse(message="Posting ID assigned to page")


@router.delete("/{pid_id}/assign/{page_id}", response_model=MessageResponse)
async def unassign_from_page(
    pid_id: UUID,
    page_id: UUID,
    user: CurrentUser = require_permission(Permission.MANAGE_PAGES),
):
    with get_db_cursor() as cur:
        cur.execute(
            "DELETE FROM page_posting_id_assignments WHERE page_id = %s AND posting_id_id = %s RETURNING id",
            (page_id, pid_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Assignment not found")
    return MessageResponse(message="Posting ID unassigned from page")
