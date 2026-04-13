"""Clerk JWT verification and auth dependencies."""

from typing import Any
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx
import jwt
from jwt import PyJWKClient
from app.core.config import Settings, get_settings

security = HTTPBearer()

_jwks_client: PyJWKClient | None = None


def _get_jwks_client(settings: Settings) -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        # Clerk JWKS endpoint — derived from secret key's instance
        # Clerk public JWKS URL: https://<clerk-frontend-api>/.well-known/jwks.json
        # We fetch the frontend API URL from Clerk's API
        _jwks_client = PyJWKClient(
            f"https://api.clerk.com/v1/jwks",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            cache_keys=True,
            max_cached_keys=4,
        )
    return _jwks_client


async def _get_clerk_jwks_url(settings: Settings) -> str:
    """Fetch the JWKS URL from Clerk's instance config."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.clerk.com/v1/instance",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
        )
        resp.raise_for_status()
        # Clerk returns the JWKS URI in the instance config
        return f"https://api.clerk.com/v1/jwks"


def verify_jwt(token: str, settings: Settings) -> dict[str, Any]:
    """Verify a Clerk JWT and return its claims."""
    try:
        client = _get_jwks_client(settings)
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},  # Clerk JWTs don't always have aud
        )
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


class CurrentUser:
    """Parsed auth context from JWT."""

    def __init__(self, claims: dict[str, Any]):
        self.clerk_user_id: str = claims.get("sub", "")
        self.org_id: str | None = claims.get("org_id")
        self.org_role: str | None = claims.get("org_role")
        self.org_slug: str | None = claims.get("org_slug")
        self.email: str = claims.get("email", "")
        self.claims = claims


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """FastAPI dependency: extract and verify the current user from JWT."""
    claims = verify_jwt(credentials.credentials, settings)
    user = CurrentUser(claims)
    if not user.clerk_user_id:
        raise HTTPException(status_code=401, detail="Invalid user identity")
    return user


async def require_org(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Require that the user belongs to an organization."""
    if not user.org_id:
        raise HTTPException(
            status_code=403, detail="Organization membership required"
        )
    return user
