"""Notifications API — lists, marks read."""

from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from app.core.auth import CurrentUser, require_org
from app.core.database import get_db_cursor
from app.core.permissions import get_user_roles_and_batches

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _resolve_org_uuid(clerk_org_id: str) -> str:
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE clerk_org_id = %s", (clerk_org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        return str(row["id"])


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user: CurrentUser = Depends(require_org),
):
    org_uuid = _resolve_org_uuid(user.org_id)
    _roles, _batches, internal_user_id = get_user_roles_and_batches(user.clerk_user_id, user.org_id)

    where = ["org_id = %s"]
    params: list = [org_uuid]
    if internal_user_id:
        where.append("(user_id = %s OR user_id IS NULL)")
        params.append(internal_user_id)
    if unread_only:
        where.append("read_at IS NULL")

    q = f"""SELECT id, org_id, user_id, kind, title, body, data, read_at, created_at
            FROM notifications
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT %s"""
    params.append(max(1, min(limit, 200)))

    with get_db_cursor() as cur:
        cur.execute(q, params)
        rows = cur.fetchall()
        return [
            {
                "id": str(r["id"]),
                "kind": r["kind"],
                "title": r["title"],
                "body": r["body"],
                "data": r["data"],
                "read_at": r["read_at"].isoformat() if r["read_at"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]


@router.post("/{notification_id}/read")
async def mark_read(notification_id: UUID, user: CurrentUser = Depends(require_org)):
    org_uuid = _resolve_org_uuid(user.org_id)
    with get_db_cursor() as cur:
        cur.execute(
            """UPDATE notifications SET read_at = now()
               WHERE id = %s AND org_id = %s AND read_at IS NULL
               RETURNING id""",
            (notification_id, org_uuid),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Notification not found or already read")
        return {"id": str(row["id"]), "read": True}


@router.post("/read-all")
async def mark_all_read(user: CurrentUser = Depends(require_org)):
    org_uuid = _resolve_org_uuid(user.org_id)
    _roles, _batches, internal_user_id = get_user_roles_and_batches(user.clerk_user_id, user.org_id)
    with get_db_cursor() as cur:
        if internal_user_id:
            cur.execute(
                """UPDATE notifications SET read_at = now()
                   WHERE org_id = %s AND (user_id = %s OR user_id IS NULL) AND read_at IS NULL""",
                (org_uuid, internal_user_id),
            )
        else:
            cur.execute(
                """UPDATE notifications SET read_at = now()
                   WHERE org_id = %s AND read_at IS NULL""",
                (org_uuid,),
            )
    return {"ok": True}
