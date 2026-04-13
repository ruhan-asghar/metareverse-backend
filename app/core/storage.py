"""Cloudflare R2 file storage — S3-compatible."""

import hashlib
import uuid
from typing import BinaryIO
import boto3
from botocore.config import Config
from app.core.config import get_settings

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "video/mp4",
    "video/quicktime",
    "video/webm",
}

# Magic bytes for file type validation
MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
    b"RIFF": "image/webp",  # RIFF....WEBP
    b"GIF8": "image/gif",
    b"\x00\x00\x00": "video/mp4",  # ftyp box (approximate)
}

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE = 1024 * 1024 * 1024  # 1 GB


def _get_r2_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def validate_file(content: bytes, mime_type: str) -> str | None:
    """Validate file content. Returns error message or None if valid."""
    if mime_type not in ALLOWED_MIME_TYPES:
        return f"File type {mime_type} not allowed"

    # Check magic bytes
    header = content[:8]
    valid_magic = False
    for magic, expected_mime in MAGIC_BYTES.items():
        if header.startswith(magic):
            valid_magic = True
            break
    if not valid_magic:
        return "File content does not match declared type"

    is_video = mime_type.startswith("video/")
    max_size = MAX_VIDEO_SIZE if is_video else MAX_IMAGE_SIZE
    if len(content) > max_size:
        size_mb = max_size // (1024 * 1024)
        return f"File exceeds maximum size of {size_mb} MB"

    return None


def compute_file_hash(content: bytes) -> str:
    """SHA-256 hash for duplicate detection."""
    return hashlib.sha256(content).hexdigest()


def generate_presigned_upload_url(
    org_id: str, file_extension: str, content_type: str
) -> tuple[str, str]:
    """Generate a presigned URL for direct upload to R2.
    Returns (presigned_url, object_key).
    """
    client = _get_r2_client()
    settings = get_settings()
    object_key = f"{org_id}/{uuid.uuid4().hex}{file_extension}"

    url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=3600,
    )
    return url, object_key


def upload_file(content: bytes, object_key: str, content_type: str) -> str:
    """Upload file directly to R2. Returns the public URL."""
    client = _get_r2_client()
    settings = get_settings()
    client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=object_key,
        Body=content,
        ContentType=content_type,
    )
    return f"{settings.r2_endpoint}/{settings.r2_bucket_name}/{object_key}"


def delete_file(object_key: str):
    """Delete a file from R2."""
    client = _get_r2_client()
    settings = get_settings()
    client.delete_object(Bucket=settings.r2_bucket_name, Key=object_key)
