"""Approval API — with race condition guard."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from app.core.auth import CurrentUser, require_org
from app.core.database import get_db_cursor
from app.core.permissions import Permission, require_permission
from app.models.schemas import ApprovalCreate, ApprovalOut

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _get_org_id(user: CurrentUser) -> UUID:
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE clerk_org_id = %s", (user.org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        return row["id"]


def _get_user_id(user: CurrentUser, org_id: UUID) -> UUID:
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE clerk_user_id = %s AND org_id = %s",
            (user.clerk_user_id, org_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return row["id"]


@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    post_id: UUID | None = None,
    user: CurrentUser = Depends(require_org),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        query = """
            SELECT a.*, CONCAT(u.first_name, ' ', u.last_name) AS reviewer_name
            FROM approvals a
            JOIN users u ON a.reviewed_by = u.id
            JOIN posts p ON a.post_id = p.id
            WHERE p.org_id = %s
        """
        params: list = [org_id]
        if post_id:
            query += " AND a.post_id = %s"
            params.append(post_id)
        query += " ORDER BY a.created_at DESC"
        cur.execute(query, params)
        return [ApprovalOut(**r) for r in cur.fetchall()]


@router.post("", response_model=ApprovalOut, status_code=201)
async def create_approval(
    body: ApprovalCreate,
    user: CurrentUser = require_permission(Permission.APPROVE),
):
    """Review a post. Race condition guard: first action wins."""
    org_id = _get_org_id(user)
    user_id = _get_user_id(user, org_id)

    with get_db_cursor() as cur:
        # Lock the post row to prevent simultaneous approvals
        cur.execute(
            "SELECT id, status FROM posts WHERE id = %s AND org_id = %s FOR UPDATE",
            (body.post_id, org_id),
        )
        post = cur.fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        if post["status"] != "pending_approval":
            # Race condition: someone else already reviewed
            # Find who reviewed it
            cur.execute(
                """SELECT CONCAT(u.first_name, ' ', u.last_name) AS name
                FROM approvals a JOIN users u ON a.reviewed_by = u.id
                WHERE a.post_id = %s ORDER BY a.created_at DESC LIMIT 1""",
                (body.post_id,),
            )
            reviewer = cur.fetchone()
            reviewer_name = reviewer["name"] if reviewer else "another user"
            raise HTTPException(
                status_code=409,
                detail=f"Already reviewed by {reviewer_name}",
            )

        # Determine new post status based on action
        status_map = {
            "approved": "queued",
            "rejected": "rejected",
            "changes_requested": "changes_requested",
        }
        new_status = status_map[body.action.value]

        # Update post status
        cur.execute(
            "UPDATE posts SET status = %s WHERE id = %s",
            (new_status, body.post_id),
        )

        # Create approval record
        cur.execute(
            """INSERT INTO approvals (post_id, reviewed_by, action, comment)
            VALUES (%s, %s, %s, %s) RETURNING *""",
            (body.post_id, user_id, body.action.value, body.comment),
        )
        approval = cur.fetchone()

        # Get reviewer name
        cur.execute(
            "SELECT CONCAT(first_name, ' ', last_name) AS name FROM users WHERE id = %s",
            (user_id,),
        )
        name_row = cur.fetchone()

        return ApprovalOut(**approval, reviewer_name=name_row["name"] if name_row else None)
