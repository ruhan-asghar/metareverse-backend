"""Clerk webhook handlers — user/org sync to Supabase."""

from fastapi import APIRouter, Request, HTTPException
from svix.webhooks import Webhook, WebhookVerificationError
from app.core.config import get_settings
from app.core.database import get_db_cursor

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_webhook(request_body: bytes, headers: dict) -> dict:
    settings = get_settings()
    wh = Webhook(settings.clerk_webhook_secret)
    try:
        return wh.verify(request_body, headers)
    except WebhookVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")


@router.post("/clerk")
async def clerk_webhook(request: Request):
    body = await request.body()
    headers = {
        "svix-id": request.headers.get("svix-id", ""),
        "svix-timestamp": request.headers.get("svix-timestamp", ""),
        "svix-signature": request.headers.get("svix-signature", ""),
    }

    payload = _verify_webhook(body, headers)
    event_type = payload.get("type", "")
    data = payload.get("data", {})

    if event_type == "user.created":
        await _handle_user_created(data)
    elif event_type == "user.updated":
        await _handle_user_updated(data)
    elif event_type == "user.deleted":
        await _handle_user_deleted(data)
    elif event_type == "organization.created":
        await _handle_org_created(data)
    elif event_type == "organization.updated":
        await _handle_org_updated(data)
    elif event_type == "organizationMembership.created":
        await _handle_org_member_created(data)
    elif event_type == "organizationMembership.deleted":
        await _handle_org_member_deleted(data)

    return {"status": "ok"}


async def _handle_user_created(data: dict):
    clerk_id = data.get("id")
    email = ""
    email_addresses = data.get("email_addresses", [])
    for ea in email_addresses:
        if ea.get("id") == data.get("primary_email_address_id"):
            email = ea.get("email_address", "")
            break

    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    avatar = data.get("image_url", "")

    # User created without org — store in users table with null org
    # They'll be linked when they join/create an org
    # For now, we can't insert without org_id (FK constraint)
    # This will be handled by organizationMembership.created
    pass


async def _handle_user_updated(data: dict):
    clerk_id = data.get("id")
    email = ""
    email_addresses = data.get("email_addresses", [])
    for ea in email_addresses:
        if ea.get("id") == data.get("primary_email_address_id"):
            email = ea.get("email_address", "")
            break

    with get_db_cursor() as cur:
        cur.execute(
            """UPDATE users SET
                email = %s,
                first_name = %s,
                last_name = %s,
                avatar_url = %s
            WHERE clerk_user_id = %s""",
            (
                email,
                data.get("first_name", ""),
                data.get("last_name", ""),
                data.get("image_url", ""),
                clerk_id,
            ),
        )


async def _handle_user_deleted(data: dict):
    clerk_id = data.get("id")
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE users SET is_active = false WHERE clerk_user_id = %s",
            (clerk_id,),
        )


async def _handle_org_created(data: dict):
    with get_db_cursor() as cur:
        cur.execute(
            """INSERT INTO organizations (clerk_org_id, name, slug)
            VALUES (%s, %s, %s)
            ON CONFLICT (clerk_org_id) DO UPDATE SET name = EXCLUDED.name, slug = EXCLUDED.slug""",
            (data.get("id"), data.get("name", ""), data.get("slug")),
        )


async def _handle_org_updated(data: dict):
    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE organizations SET name = %s, slug = %s WHERE clerk_org_id = %s",
            (data.get("name", ""), data.get("slug"), data.get("id")),
        )


async def _handle_org_member_created(data: dict):
    """When a user joins an org, create/link their user record and team_member."""
    org_clerk_id = data.get("organization", {}).get("id")
    user_data = data.get("public_user_data", {})
    clerk_user_id = user_data.get("user_id")
    role = data.get("role", "")  # Clerk org role: "org:admin" or "org:member"

    if not org_clerk_id or not clerk_user_id:
        return

    email = user_data.get("identifier", "")
    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    avatar = user_data.get("image_url", "")

    with get_db_cursor() as cur:
        # Ensure org exists
        cur.execute(
            "SELECT id FROM organizations WHERE clerk_org_id = %s", (org_clerk_id,)
        )
        org_row = cur.fetchone()
        if not org_row:
            return
        org_id = org_row["id"]

        # Upsert user
        cur.execute(
            """INSERT INTO users (clerk_user_id, org_id, email, first_name, last_name, avatar_url)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (clerk_user_id) DO UPDATE SET
                org_id = EXCLUDED.org_id,
                email = EXCLUDED.email,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                avatar_url = EXCLUDED.avatar_url
            RETURNING id""",
            (clerk_user_id, org_id, email, first_name, last_name, avatar),
        )
        user_id = cur.fetchone()["id"]

        # Determine initial role — Clerk "org:admin" → owner
        mr_role = "owner" if role == "org:admin" else "publisher"

        # Create team_member if not exists
        cur.execute(
            """INSERT INTO team_members (org_id, user_id, roles, status, joined_at)
            VALUES (%s, %s, %s, 'active', now())
            ON CONFLICT (org_id, user_id) DO NOTHING""",
            (org_id, user_id, [mr_role]),
        )


async def _handle_org_member_deleted(data: dict):
    org_clerk_id = data.get("organization", {}).get("id")
    clerk_user_id = data.get("public_user_data", {}).get("user_id")

    if not org_clerk_id or not clerk_user_id:
        return

    with get_db_cursor() as cur:
        cur.execute(
            """UPDATE team_members SET status = 'removed'
            WHERE user_id = (SELECT id FROM users WHERE clerk_user_id = %s)
            AND org_id = (SELECT id FROM organizations WHERE clerk_org_id = %s)""",
            (clerk_user_id, org_clerk_id),
        )
