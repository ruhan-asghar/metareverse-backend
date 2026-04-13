"""File upload API — presigned URLs, validation, duplicate detection."""

from uuid import UUID
import os
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.core.auth import CurrentUser
from app.core.database import get_db_cursor
from app.core.permissions import Permission, require_permission
from app.core.storage import (
    validate_file, compute_file_hash, generate_presigned_upload_url,
    upload_file, ALLOWED_MIME_TYPES,
)
from app.models.schemas import (
    PresignedUrlRequest, PresignedUrlResponse, FileUploadConfirm,
    PostMediaOut, MessageResponse,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _get_org_id(user: CurrentUser) -> UUID:
    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE clerk_org_id = %s", (user.org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        return row["id"]


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def get_presigned_url(
    body: PresignedUrlRequest,
    user: CurrentUser = require_permission(Permission.UPLOAD),
):
    """Get a presigned URL for direct upload to R2."""
    org_id = _get_org_id(user)

    if body.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"File type {body.content_type} not allowed")

    # Check storage quota
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT storage_used_bytes, storage_limit_bytes FROM organizations WHERE id = %s",
            (org_id,),
        )
        org = cur.fetchone()
        if org["storage_used_bytes"] + body.file_size > org["storage_limit_bytes"]:
            raise HTTPException(status_code=413, detail="Storage quota exceeded")

    ext = os.path.splitext(body.filename)[1] or ".bin"
    upload_url, object_key = generate_presigned_upload_url(
        str(org_id), ext, body.content_type
    )

    from app.core.config import get_settings
    settings = get_settings()
    file_url = f"{settings.r2_endpoint}/{settings.r2_bucket_name}/{object_key}"

    return PresignedUrlResponse(
        upload_url=upload_url,
        object_key=object_key,
        file_url=file_url,
    )


@router.post("/confirm", response_model=PostMediaOut, status_code=201)
async def confirm_upload(
    body: FileUploadConfirm,
    user: CurrentUser = require_permission(Permission.UPLOAD),
):
    """Confirm an upload — register media in DB, check duplicates, update storage."""
    org_id = _get_org_id(user)

    with get_db_cursor() as cur:
        # Verify post belongs to org
        cur.execute(
            "SELECT id FROM posts WHERE id = %s AND org_id = %s",
            (body.post_id, org_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Post not found")

        # Check for duplicate hash in same org
        cur.execute(
            "SELECT pm.id, p.id AS post_id FROM post_media pm JOIN posts p ON pm.post_id = p.id WHERE pm.file_hash = %s AND p.org_id = %s LIMIT 1",
            (body.file_hash, org_id),
        )
        dup = cur.fetchone()
        if dup:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate file detected (matches post media {dup['id']})",
            )

        # Get next sort order for this post
        cur.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM post_media WHERE post_id = %s",
            (body.post_id,),
        )
        next_order = cur.fetchone()["next_order"]

        from app.core.config import get_settings
        settings = get_settings()
        file_url = f"{settings.r2_endpoint}/{settings.r2_bucket_name}/{body.object_key}"

        # Insert media record
        cur.execute(
            """INSERT INTO post_media (post_id, org_id, file_url, file_key, file_hash,
                file_size, mime_type, width, height, duration_secs, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *""",
            (
                body.post_id, org_id, file_url, body.object_key, body.file_hash,
                body.file_size, body.mime_type, body.width, body.height,
                body.duration_secs, next_order,
            ),
        )
        media = cur.fetchone()

        # Update file_hash on post for quick lookup
        cur.execute(
            "UPDATE posts SET file_hash = %s WHERE id = %s",
            (body.file_hash, body.post_id),
        )

        # Update org storage usage
        cur.execute(
            "UPDATE organizations SET storage_used_bytes = storage_used_bytes + %s WHERE id = %s",
            (body.file_size, org_id),
        )

        return PostMediaOut(**media)


@router.delete("/media/{media_id}", response_model=MessageResponse)
async def delete_media(
    media_id: UUID,
    user: CurrentUser = require_permission(Permission.UPLOAD),
):
    org_id = _get_org_id(user)
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT * FROM post_media WHERE id = %s AND org_id = %s",
            (media_id, org_id),
        )
        media = cur.fetchone()
        if not media:
            raise HTTPException(status_code=404, detail="Media not found")

        # Delete from R2
        from app.core.storage import delete_file
        try:
            delete_file(media["file_key"])
        except Exception:
            pass  # File might already be deleted

        # Delete from DB
        cur.execute("DELETE FROM post_media WHERE id = %s", (media_id,))

        # Update org storage
        cur.execute(
            "UPDATE organizations SET storage_used_bytes = GREATEST(storage_used_bytes - %s, 0) WHERE id = %s",
            (media["file_size"], org_id),
        )

    return MessageResponse(message="Media deleted")
