"""Post CRUD API — full state machine support."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Query
from app.core.auth import CurrentUser, require_org
from app.core.database import get_db_cursor
from app.core.permissions import (
    Permission, require_permission, is_platform_wide, get_user_roles_and_batches, has_permission
)
from app.models.schemas import (
    PostCreate, PostUpdate, PostOut, PostMediaOut, ThreadCommentOut, MessageResponse
)

router = APIRouter(prefix="/posts", tags=["posts"])


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


def _enrich_post(post: dict) -> PostOut:
    """Add media and thread_comments to post."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT * FROM post_media WHERE post_id = %s ORDER BY sort_order",
            (post["id"],),
        )
        media = [PostMediaOut(**r) for r in cur.fetchall()]

        cur.execute(
            "SELECT * FROM thread_comments WHERE post_id = %s ORDER BY sort_order",
            (post["id"],),
        )
        comments = [ThreadCommentOut(**r) for r in cur.fetchall()]

    return PostOut(**post, media=media, thread_comments=comments)


@router.get("", response_model=list[PostOut])
async def list_posts(
    page_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_org),
):
    org_id = _get_org_id(user)
    user_id = _get_user_id(user, org_id)
    roles, batch_ids, _ = get_user_roles_and_batches(user.clerk_user_id, user.org_id)

    with get_db_cursor() as cur:
        query = "SELECT p.* FROM posts p WHERE p.org_id = %s"
        params: list = [org_id]

        # Batch scoping
        if not is_platform_wide(roles) and batch_ids:
            query += " AND p.page_id IN (SELECT id FROM pages WHERE batch_id = ANY(%s))"
            params.append(batch_ids)
        elif not is_platform_wide(roles):
            return []

        # Publishers can only see their own posts (except in queue read-only)
        if "publisher" in roles and not has_permission(roles, Permission.VIEW_ALL_DRAFTS):
            query += " AND p.created_by = %s"
            params.append(user_id)

        if page_id:
            query += " AND p.page_id = %s"
            params.append(page_id)

        if status:
            query += " AND p.status = %s"
            params.append(status)

        query += " ORDER BY p.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cur.execute(query, params)
        rows = cur.fetchall()
        return [_enrich_post(r) for r in rows]


@router.get("/{post_id}", response_model=PostOut)
async def get_post(post_id: UUID, user: CurrentUser = Depends(require_org)):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM posts WHERE id = %s AND org_id = %s", (post_id, org_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
        return _enrich_post(row)


@router.post("", response_model=PostOut, status_code=201)
async def create_post(
    body: PostCreate,
    user: CurrentUser = require_permission(Permission.UPLOAD),
):
    org_id = _get_org_id(user)
    user_id = _get_user_id(user, org_id)

    with get_db_cursor() as cur:
        # Verify page belongs to org
        cur.execute("SELECT id, require_approval FROM pages WHERE id = %s AND org_id = %s", (body.page_id, org_id))
        page = cur.fetchone()
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")

        cur.execute(
            """INSERT INTO posts (org_id, page_id, created_by, media_type,
                caption_facebook, caption_instagram, caption_threads,
                publish_to_facebook, publish_to_instagram, publish_to_threads,
                scheduled_at, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft')
            RETURNING *""",
            (
                org_id, body.page_id, user_id, body.media_type.value,
                body.caption_facebook, body.caption_instagram, body.caption_threads,
                body.publish_to_facebook, body.publish_to_instagram,
                body.publish_to_threads, body.scheduled_at,
            ),
        )
        post = cur.fetchone()

        # Create thread comments if provided
        if body.thread_comments:
            for i, comment_text in enumerate(body.thread_comments[:3]):
                cur.execute(
                    "INSERT INTO thread_comments (post_id, content, sort_order) VALUES (%s, %s, %s)",
                    (post["id"], comment_text, i),
                )

        return _enrich_post(post)


@router.patch("/{post_id}", response_model=PostOut)
async def update_post(
    post_id: UUID,
    body: PostUpdate,
    user: CurrentUser = require_permission(Permission.UPLOAD),
):
    org_id = _get_org_id(user)
    updates = body.model_dump(exclude_unset=True)

    # Handle thread_comments separately
    thread_comments = updates.pop("thread_comments", None)

    if not updates and thread_comments is None:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_db_cursor() as cur:
        if updates:
            # Convert enums
            for k, v in updates.items():
                if hasattr(v, "value"):
                    updates[k] = v.value

            set_clauses = ", ".join(f"{k} = %s" for k in updates)
            values = list(updates.values()) + [post_id, org_id]
            cur.execute(
                f"UPDATE posts SET {set_clauses} WHERE id = %s AND org_id = %s RETURNING *",
                values,
            )
            row = cur.fetchone()
        else:
            cur.execute("SELECT * FROM posts WHERE id = %s AND org_id = %s", (post_id, org_id))
            row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Post not found")

        # Update thread comments
        if thread_comments is not None:
            cur.execute("DELETE FROM thread_comments WHERE post_id = %s", (post_id,))
            for i, comment_text in enumerate(thread_comments[:3]):
                cur.execute(
                    "INSERT INTO thread_comments (post_id, content, sort_order) VALUES (%s, %s, %s)",
                    (post_id, comment_text, i),
                )

        return _enrich_post(row)


@router.post("/{post_id}/submit", response_model=PostOut)
async def submit_for_approval(
    post_id: UUID,
    user: CurrentUser = require_permission(Permission.UPLOAD),
):
    """Submit a draft for approval (status: draft → pending_approval)."""
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT * FROM posts WHERE id = %s AND org_id = %s AND status = 'draft'",
            (post_id, org_id),
        )
        post = cur.fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="Draft post not found")

        # Check if page requires approval
        cur.execute("SELECT require_approval FROM pages WHERE id = %s", (post["page_id"],))
        page = cur.fetchone()

        if page and page["require_approval"]:
            new_status = "pending_approval"
        else:
            new_status = "queued"

        cur.execute(
            "UPDATE posts SET status = %s WHERE id = %s RETURNING *",
            (new_status, post_id),
        )
        return _enrich_post(cur.fetchone())


@router.post("/{post_id}/schedule", response_model=PostOut)
async def schedule_post(
    post_id: UUID,
    user: CurrentUser = require_permission(Permission.UPLOAD),
):
    """Direct schedule a draft to queue (skipping approval)."""
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE posts SET status = 'queued' WHERE id = %s AND org_id = %s AND status IN ('draft', 'changes_requested') RETURNING *",
            (post_id, org_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found or not in schedulable state")
        return _enrich_post(row)


@router.post("/{post_id}/retry", response_model=PostOut)
async def retry_post(
    post_id: UUID,
    user: CurrentUser = require_permission(Permission.UPLOAD),
):
    """Retry a failed post."""
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            """UPDATE posts SET status = 'queued', failed_category = NULL,
            failure_reason = NULL, retry_count = retry_count + 1
            WHERE id = %s AND org_id = %s AND status IN ('failed_temporary', 'failed_needs_editing')
            RETURNING *""",
            (post_id, org_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Failed post not found")
        return _enrich_post(row)


@router.delete("/{post_id}", response_model=MessageResponse)
async def delete_post(
    post_id: UUID,
    user: CurrentUser = require_permission(Permission.UPLOAD),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            "DELETE FROM posts WHERE id = %s AND org_id = %s AND status IN ('draft', 'rejected', 'changes_requested') RETURNING id",
            (post_id, org_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Post not found or cannot be deleted in current state")
    return MessageResponse(message="Post deleted")
