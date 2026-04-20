"""Role-based permission system matching the PRD permission matrix."""

from enum import Enum
from functools import wraps
from typing import Callable
from fastapi import HTTPException, Depends
from app.core.auth import CurrentUser, require_org
from app.core.database import get_db_cursor


class Permission(str, Enum):
    # Revenue & KPIs
    VIEW_REVENUE = "view_revenue"
    VIEW_RPM = "view_rpm"

    # Content
    UPLOAD = "upload"
    VIEW_OWN_DRAFTS = "view_own_drafts"
    VIEW_ALL_DRAFTS = "view_all_drafts"
    APPROVE = "approve"
    VIEW_OWN_QUEUE = "view_own_queue"
    VIEW_ALL_QUEUE = "view_all_queue"
    RESCHEDULE = "reschedule"
    VIEW_OWN_FAILED = "view_own_failed"
    VIEW_ALL_FAILED = "view_all_failed"

    # Reports
    VIEW_REPORTS_OVERVIEW = "view_reports_overview"
    VIEW_REPORTS_RESULTS = "view_reports_results"
    VIEW_REPORTS_EARNINGS = "view_reports_earnings"
    VIEW_REPORTS_POSTING_ID = "view_reports_posting_id"
    VIEW_REPORTS_BATCHES = "view_reports_batches"

    # Settings
    MANAGE_PAGES = "manage_pages"
    MANAGE_BILLING = "manage_billing"
    INVITE_MANAGER = "invite_manager"
    INVITE_CO_OWNER = "invite_co_owner"
    MANAGE_TEAM = "manage_team"


# Permission matrix from PRD
ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "owner": set(Permission),  # all permissions
    "co_owner": set(Permission) - {Permission.INVITE_CO_OWNER},
    "manager": {
        Permission.VIEW_RPM,
        Permission.UPLOAD,
        Permission.VIEW_OWN_DRAFTS,
        Permission.VIEW_ALL_DRAFTS,
        Permission.APPROVE,
        Permission.VIEW_OWN_QUEUE,
        Permission.VIEW_ALL_QUEUE,
        Permission.RESCHEDULE,
        Permission.VIEW_OWN_FAILED,
        Permission.VIEW_ALL_FAILED,
        Permission.VIEW_REPORTS_OVERVIEW,
        Permission.VIEW_REPORTS_RESULTS,
        Permission.VIEW_REPORTS_POSTING_ID,
        Permission.VIEW_REPORTS_BATCHES,
        Permission.MANAGE_PAGES,
        Permission.MANAGE_TEAM,
    },
    "publisher": {
        Permission.UPLOAD,
        Permission.VIEW_OWN_DRAFTS,
        Permission.VIEW_OWN_QUEUE,
        Permission.VIEW_OWN_FAILED,
    },
    "approver": {
        Permission.VIEW_ALL_DRAFTS,
        Permission.APPROVE,
        Permission.VIEW_ALL_QUEUE,  # read-only
    },
    "analyst": {
        Permission.VIEW_REPORTS_OVERVIEW,
        Permission.VIEW_REPORTS_RESULTS,
        Permission.VIEW_REPORTS_BATCHES,
    },
}


def get_user_roles_and_batches(clerk_user_id: str, org_id: str) -> tuple[list[str], list[str], str | None]:
    """Fetch user's roles, batch_ids, and internal user_id from DB."""
    with get_db_cursor() as cur:
        # Get internal user id
        cur.execute(
            "SELECT u.id FROM users u JOIN organizations o ON u.org_id = o.id WHERE u.clerk_user_id = %s AND o.clerk_org_id = %s",
            (clerk_user_id, org_id),
        )
        user_row = cur.fetchone()
        if not user_row:
            return [], [], None

        user_id = str(user_row["id"])

        cur.execute(
            "SELECT roles, batch_ids FROM team_members WHERE user_id = %s AND org_id = (SELECT id FROM organizations WHERE clerk_org_id = %s) AND status = 'active'",
            (user_row["id"], org_id),
        )
        row = cur.fetchone()
        if not row:
            return [], [], user_id

        roles = row["roles"] or []
        batch_ids = [str(b) for b in (row["batch_ids"] or [])]
        return roles, batch_ids, user_id


def has_permission(roles: list[str], permission: Permission) -> bool:
    """Check if any of the user's roles grant a specific permission."""
    for role in roles:
        role_perms = ROLE_PERMISSIONS.get(role, set())
        if permission in role_perms:
            return True
    return False


def is_platform_wide(roles: list[str]) -> bool:
    """Owner and co_owner have platform-wide access (not batch-scoped)."""
    return "owner" in roles or "co_owner" in roles


def require_roles(*required_roles: str):
    """FastAPI dependency factory: require one of the listed roles on the user."""

    async def checker(user: CurrentUser = Depends(require_org)):
        roles, batch_ids, internal_id = get_user_roles_and_batches(
            user.clerk_user_id, user.org_id
        )
        if not roles:
            raise HTTPException(status_code=403, detail="No role assigned")
        if not any(r in required_roles for r in roles):
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of: {', '.join(required_roles)}",
            )
        user._roles = roles
        user._batch_ids = batch_ids
        user._internal_id = internal_id
        user._is_platform_wide = is_platform_wide(roles)
        return user

    return Depends(checker)


def require_permission(*permissions: Permission):
    """FastAPI dependency factory: require one or more permissions."""

    async def checker(user: CurrentUser = Depends(require_org)):
        roles, batch_ids, internal_id = get_user_roles_and_batches(
            user.clerk_user_id, user.org_id
        )
        if not roles:
            raise HTTPException(status_code=403, detail="No role assigned")

        for perm in permissions:
            if not has_permission(roles, perm):
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing permission: {perm.value}",
                )

        # Attach resolved info to user object
        user._roles = roles
        user._batch_ids = batch_ids
        user._internal_id = internal_id
        user._is_platform_wide = is_platform_wide(roles)
        return user

    return Depends(checker)
