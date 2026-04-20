"""Facebook OAuth endpoints — start (redirect) and callback (exchange + persist)."""

import secrets
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.core.auth import CurrentUser, require_org
from app.core.config import get_settings
from app.core.database import get_db_cursor
from app.core.encryption import encrypt_token
from app.core.redis import get_redis
from app.services.meta import get_meta_client

router = APIRouter(prefix="/oauth", tags=["oauth"])

_STATE_TTL_SECONDS = 600  # 10 minutes
_STATE_PREFIX = "oauth:state:"


def _issue_state(org_id: str, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    r = get_redis()
    r.setex(f"{_STATE_PREFIX}{token}", _STATE_TTL_SECONDS, f"{org_id}:{user_id}")
    return token


def _consume_state(token: str, org_id: str, user_id: str) -> bool:
    r = get_redis()
    key = f"{_STATE_PREFIX}{token}"
    val = r.get(key)
    if not val:
        return False
    r.delete(key)
    expected = f"{org_id}:{user_id}"
    return val == expected


def _resolve_org_uuid(clerk_org_id: str) -> str:
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE clerk_org_id = %s", (clerk_org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        return str(row["id"])


@router.get("/facebook/start")
async def oauth_start(user: CurrentUser = Depends(require_org)):
    """Redirect the user to Facebook's OAuth dialog (or a mock URL in test mode)."""
    settings = get_settings()
    state = _issue_state(user.org_id, user.clerk_user_id)
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_oauth_redirect_uri,
        "state": state,
        "scope": "pages_show_list,pages_manage_posts,pages_read_engagement,instagram_basic,instagram_content_publish",
        "response_type": "code",
    }
    if settings.meta_mode == "mock":
        url = f"https://mock.metareverse.local/oauth?{urlencode(params)}"
    else:
        url = f"https://www.facebook.com/v20.0/dialog/oauth?{urlencode(params)}"
    return RedirectResponse(url, status_code=302)


@router.get("/facebook/callback")
async def oauth_callback(
    request: Request,
    user: CurrentUser = Depends(require_org),
):
    """Exchange code for tokens, upsert pages + posting_id."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    if not _consume_state(state, user.org_id, user.clerk_user_id):
        raise HTTPException(status_code=403, detail="Invalid or expired state")

    settings = get_settings()
    client = get_meta_client()

    try:
        oauth = client.exchange_code(code, settings.meta_oauth_redirect_uri)
        pages = client.list_pages(oauth.user_access_token)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Meta OAuth failed: {e}")

    org_uuid = _resolve_org_uuid(user.org_id)

    with get_db_cursor() as cur:
        # Ensure an Unassigned batch exists for this org
        cur.execute(
            """INSERT INTO batches (org_id, name, color)
               VALUES (%s, 'Unassigned', '#6b7280')
               ON CONFLICT (org_id, name) DO UPDATE SET name = EXCLUDED.name
               RETURNING id""",
            (org_uuid,),
        )
        unassigned_batch_id = cur.fetchone()["id"]

        inserted_pages = []
        for p in pages:
            # Each page gets its own page-scoped token
            try:
                page_token = client.get_page_token(p.id, oauth.user_access_token)
            except Exception:
                page_token = p.access_token
            enc = encrypt_token(page_token)
            cur.execute(
                """INSERT INTO pages (
                     org_id, batch_id, platform, platform_page_id, name,
                     avatar_url, encrypted_access_token, token_expires_at, status
                   )
                   VALUES (%s, %s, 'facebook', %s, %s, %s, %s, %s, 'needs_setup')
                   ON CONFLICT (org_id, platform, platform_page_id) DO UPDATE
                     SET encrypted_access_token = EXCLUDED.encrypted_access_token,
                         token_expires_at        = EXCLUDED.token_expires_at,
                         name                    = EXCLUDED.name,
                         avatar_url              = EXCLUDED.avatar_url
                   RETURNING id, name, platform_page_id""",
                (
                    org_uuid,
                    unassigned_batch_id,
                    p.id,
                    p.name,
                    None,
                    enc,
                    oauth.expires_at,
                ),
            )
            row = cur.fetchone()
            inserted_pages.append(
                {"id": str(row["id"]), "name": row["name"], "platform_page_id": row["platform_page_id"]}
            )

        # Upsert the Facebook user account as a Posting ID
        cur.execute(
            """INSERT INTO posting_ids (org_id, facebook_user_id, name, status, health_score,
                                        encrypted_access_token, token_expires_at)
               VALUES (%s, %s, %s, 'active', 100, %s, %s)
               ON CONFLICT (org_id, facebook_user_id) DO UPDATE
                 SET encrypted_access_token = EXCLUDED.encrypted_access_token,
                     token_expires_at       = EXCLUDED.token_expires_at
               RETURNING id""",
            (
                org_uuid,
                oauth.user_id,
                f"FB User {oauth.user_id[:8]}",
                encrypt_token(oauth.user_access_token),
                oauth.expires_at,
            ),
        )
        posting_id_row = cur.fetchone()

    return {
        "pages": inserted_pages,
        "posting_id": str(posting_id_row["id"]),
        "unassigned_batch_id": str(unassigned_batch_id),
    }
