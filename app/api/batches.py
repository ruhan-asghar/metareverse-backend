"""Batch CRUD API."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from app.core.auth import CurrentUser, require_org
from app.core.database import get_db_cursor
from app.core.permissions import Permission, require_permission
from app.models.schemas import BatchCreate, BatchUpdate, BatchOut, MessageResponse

router = APIRouter(prefix="/batches", tags=["batches"])


def _get_org_id(user: CurrentUser) -> UUID:
    """Resolve Clerk org_id to internal org UUID."""
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE clerk_org_id = %s", (user.org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        return row["id"]


@router.get("", response_model=list[BatchOut])
async def list_batches(user: CurrentUser = Depends(require_org)):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT b.*, COUNT(p.id) FILTER (WHERE p.is_active = true) AS page_count
            FROM batches b
            LEFT JOIN pages p ON p.batch_id = b.id
            WHERE b.org_id = %s
            GROUP BY b.id
            ORDER BY b.created_at""",
            (org_id,),
        )
        rows = cur.fetchall()
        return [BatchOut(**r) for r in rows]


@router.get("/{batch_id}", response_model=BatchOut)
async def get_batch(batch_id: UUID, user: CurrentUser = Depends(require_org)):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT b.*, COUNT(p.id) FILTER (WHERE p.is_active = true) AS page_count
            FROM batches b
            LEFT JOIN pages p ON p.batch_id = b.id
            WHERE b.id = %s AND b.org_id = %s
            GROUP BY b.id""",
            (batch_id, org_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Batch not found")
        return BatchOut(**row)


@router.post("", response_model=BatchOut, status_code=201)
async def create_batch(
    body: BatchCreate,
    user: CurrentUser = require_permission(Permission.MANAGE_PAGES),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO batches (org_id, name, color, description)
            VALUES (%s, %s, %s, %s) RETURNING *, 0 AS page_count""",
            (org_id, body.name, body.color, body.description),
        )
        row = cur.fetchone()
        return BatchOut(**row)


@router.patch("/{batch_id}", response_model=BatchOut)
async def update_batch(
    batch_id: UUID,
    body: BatchUpdate,
    user: CurrentUser = require_permission(Permission.MANAGE_PAGES),
):
    org_id = _get_org_id(user)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [batch_id, org_id]

    with get_db_cursor() as cur:
        cur.execute(
            f"""UPDATE batches SET {set_clauses}
            WHERE id = %s AND org_id = %s
            RETURNING *, (SELECT COUNT(*) FROM pages WHERE batch_id = batches.id AND is_active = true) AS page_count""",
            values,
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Batch not found")
        return BatchOut(**row)


@router.delete("/{batch_id}", response_model=MessageResponse)
async def delete_batch(
    batch_id: UUID,
    user: CurrentUser = require_permission(Permission.MANAGE_PAGES),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        # The DB trigger check_batch_deletable will raise if batch has active pages/posts
        try:
            cur.execute(
                "DELETE FROM batches WHERE id = %s AND org_id = %s RETURNING id",
                (batch_id, org_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Batch not found")
        except Exception as e:
            if "Cannot delete batch" in str(e):
                raise HTTPException(status_code=409, detail=str(e))
            raise
    return MessageResponse(message="Batch deleted")
