"""Team member and invite link APIs."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from app.core.auth import CurrentUser
from app.core.database import get_db_cursor
from app.core.permissions import Permission, require_permission
from app.models.schemas import (
    TeamMemberCreate, TeamMemberUpdate, TeamMemberOut, UserOut,
    InviteLinkCreate, InviteLinkOut, MessageResponse,
)

router = APIRouter(prefix="/team", tags=["team"])


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


# ── Team Members ──────────────────────────────────────

@router.get("/members", response_model=list[TeamMemberOut])
async def list_members(
    user: CurrentUser = require_permission(Permission.MANAGE_TEAM),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT tm.*, row_to_json(u.*) AS user_data
            FROM team_members tm
            JOIN users u ON tm.user_id = u.id
            WHERE tm.org_id = %s AND tm.status != 'removed'
            ORDER BY tm.created_at""",
            (org_id,),
        )
        rows = cur.fetchall()
        result = []
        for r in rows:
            user_data = r.pop("user_data", None)
            tm = TeamMemberOut(**r)
            if user_data:
                tm.user = UserOut(**user_data)
            result.append(tm)
        return result


@router.patch("/members/{member_id}", response_model=TeamMemberOut)
async def update_member(
    member_id: UUID,
    body: TeamMemberUpdate,
    user: CurrentUser = require_permission(Permission.MANAGE_TEAM),
):
    org_id = _get_org_id(user)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Convert roles list to postgres array
    if "roles" in updates:
        updates["roles"] = [r.value if hasattr(r, "value") else r for r in updates["roles"]]
    if "batch_ids" in updates:
        updates["batch_ids"] = [str(b) for b in updates["batch_ids"]]

    set_clauses = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [member_id, org_id]

    with get_db_cursor() as cur:
        cur.execute(
            f"UPDATE team_members SET {set_clauses} WHERE id = %s AND org_id = %s RETURNING *",
            values,
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Team member not found")
        return TeamMemberOut(**row)


@router.delete("/members/{member_id}", response_model=MessageResponse)
async def remove_member(
    member_id: UUID,
    user: CurrentUser = require_permission(Permission.MANAGE_TEAM),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE team_members SET status = 'removed' WHERE id = %s AND org_id = %s RETURNING id",
            (member_id, org_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Team member not found")
    return MessageResponse(message="Team member removed")


# ── Invite Links ──────────────────────────────────────

@router.get("/invites", response_model=list[InviteLinkOut])
async def list_invites(
    user: CurrentUser = require_permission(Permission.MANAGE_TEAM),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT * FROM invite_links WHERE org_id = %s ORDER BY created_at DESC",
            (org_id,),
        )
        return [InviteLinkOut(**r) for r in cur.fetchall()]


@router.post("/invites", response_model=InviteLinkOut, status_code=201)
async def create_invite(
    body: InviteLinkCreate,
    user: CurrentUser = require_permission(Permission.INVITE_MANAGER),
):
    org_id = _get_org_id(user)
    user_id = _get_user_id(user, org_id)

    # Validate role permissions
    roles_requesting = [r.value for r in body.roles]
    if "co_owner" in roles_requesting:
        # Only owner can invite co-owner
        from app.core.permissions import get_user_roles_and_batches
        user_roles, _, _ = get_user_roles_and_batches(user.clerk_user_id, user.org_id)
        if "owner" not in user_roles:
            raise HTTPException(status_code=403, detail="Only owners can invite co-owners")

    if "manager" in roles_requesting:
        from app.core.permissions import get_user_roles_and_batches, has_permission
        user_roles, _, _ = get_user_roles_and_batches(user.clerk_user_id, user.org_id)
        if not has_permission(user_roles, Permission.INVITE_MANAGER):
            raise HTTPException(status_code=403, detail="Cannot invite managers")

    with get_db_cursor() as cur:
        # Invalidate any existing pending invites for this email
        cur.execute(
            """UPDATE invite_links SET status = 'invalidated', invalidated_at = now()
            WHERE org_id = %s AND email = %s AND status = 'pending'""",
            (org_id, body.email),
        )

        batch_ids = [str(b) for b in body.batch_ids]
        cur.execute(
            """INSERT INTO invite_links (org_id, email, roles, batch_ids, invited_by)
            VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (org_id, body.email, roles_requesting, batch_ids, user_id),
        )
        return InviteLinkOut(**cur.fetchone())


@router.post("/invites/{invite_id}/resend", response_model=InviteLinkOut)
async def resend_invite(
    invite_id: UUID,
    user: CurrentUser = require_permission(Permission.MANAGE_TEAM),
):
    """Resend invite — invalidates old link, creates fresh one."""
    org_id = _get_org_id(user)
    user_id = _get_user_id(user, org_id)

    with get_db_cursor() as cur:
        # Get old invite
        cur.execute(
            "SELECT * FROM invite_links WHERE id = %s AND org_id = %s",
            (invite_id, org_id),
        )
        old = cur.fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="Invite not found")

        # Invalidate old
        cur.execute(
            "UPDATE invite_links SET status = 'invalidated', invalidated_at = now() WHERE id = %s",
            (invite_id,),
        )

        # Create new
        cur.execute(
            """INSERT INTO invite_links (org_id, email, roles, batch_ids, invited_by)
            VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (org_id, old["email"], old["roles"], old["batch_ids"], user_id),
        )
        return InviteLinkOut(**cur.fetchone())


@router.post("/invites/accept/{token}", response_model=MessageResponse)
async def accept_invite(token: str):
    """Accept an invite link (called after Clerk sign-up)."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT * FROM invite_links
            WHERE token = %s AND status = 'pending' AND expires_at > now()""",
            (token,),
        )
        invite = cur.fetchone()
        if not invite:
            raise HTTPException(status_code=404, detail="Invalid or expired invite link")

        # Mark as accepted
        cur.execute(
            "UPDATE invite_links SET status = 'accepted', accepted_at = now() WHERE id = %s",
            (invite["id"],),
        )

    return MessageResponse(message="Invite accepted. Complete sign-up to join the team.")
