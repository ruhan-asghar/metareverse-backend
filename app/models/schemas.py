"""Pydantic models for all API request/response schemas."""

from datetime import datetime, date, time
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# ── Enums ──────────────────────────────────────────────

class UserRole(str, Enum):
    owner = "owner"
    co_owner = "co_owner"
    manager = "manager"
    publisher = "publisher"
    approver = "approver"
    analyst = "analyst"


class PlatformType(str, Enum):
    facebook = "facebook"
    instagram = "instagram"
    threads = "threads"


class PostStatus(str, Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    changes_requested = "changes_requested"
    rejected = "rejected"
    queued = "queued"
    publishing = "publishing"
    published = "published"
    failed_temporary = "failed_temporary"
    failed_needs_editing = "failed_needs_editing"
    reconnect_required = "reconnect_required"
    paused = "paused"


class MediaType(str, Enum):
    photo = "photo"
    reel = "reel"
    text = "text"


class ApprovalAction(str, Enum):
    approved = "approved"
    rejected = "rejected"
    changes_requested = "changes_requested"


class PostingIdStatus(str, Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"
    retired = "retired"


class PageStatus(str, Enum):
    ready = "ready"
    needs_setup = "needs_setup"
    paused = "paused"
    inactive = "inactive"
    token_expired = "token_expired"
    token_expiring = "token_expiring"


class MonetizationStatus(str, Enum):
    enrolled = "enrolled"
    not_enrolled = "not_enrolled"
    ineligible = "ineligible"


class FailedCategory(str, Enum):
    temporary_issue = "temporary_issue"
    reconnect_needed = "reconnect_needed"
    needs_editing = "needs_editing"


# ── Organizations ──────────────────────────────────────

class OrgOut(BaseModel):
    id: UUID
    clerk_org_id: str
    name: str
    slug: Optional[str] = None
    plan: str
    storage_used_bytes: int
    storage_limit_bytes: int
    created_at: datetime


# ── Users ─────���────────────────────────────────────────

class UserOut(BaseModel):
    id: UUID
    clerk_user_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime


# ── Batches ─────────���──────────────────────────────────

class BatchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#3b82f6", pattern=r"^#[0-9a-fA-F]{6}$")
    description: Optional[str] = None


class BatchUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    description: Optional[str] = None


class BatchOut(BaseModel):
    id: UUID
    name: str
    color: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    page_count: Optional[int] = 0


# ── Pages ─���────────────────────────────────────────────

class PageCreate(BaseModel):
    batch_id: UUID
    platform: PlatformType
    platform_page_id: str
    name: str
    avatar_url: Optional[str] = None
    timezone: str = "UTC"
    post_interval_hours: int = Field(default=4, ge=1, le=8)
    active_hours_start: Optional[str] = None  # HH:MM format
    active_hours_end: Optional[str] = None
    require_approval: bool = False
    monetization_status: MonetizationStatus = MonetizationStatus.not_enrolled


class PageUpdate(BaseModel):
    batch_id: Optional[UUID] = None
    name: Optional[str] = None
    timezone: Optional[str] = None
    post_interval_hours: Optional[int] = Field(default=None, ge=1, le=8)
    active_hours_start: Optional[str] = None
    active_hours_end: Optional[str] = None
    require_approval: Optional[bool] = None
    monetization_status: Optional[MonetizationStatus] = None
    status: Optional[PageStatus] = None
    is_active: Optional[bool] = None


class PageOut(BaseModel):
    id: UUID
    batch_id: UUID
    platform: PlatformType
    platform_page_id: str
    name: str
    avatar_url: Optional[str] = None
    follower_count: int = 0
    timezone: str
    post_interval_hours: int
    active_hours_start: Optional[str] = None
    active_hours_end: Optional[str] = None
    require_approval: bool
    rotation_mode: str = "round_robin"
    monetization_status: MonetizationStatus
    status: PageStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── Posting IDs ────────────────────────────────────────

class PostingIdCreate(BaseModel):
    facebook_user_id: str
    name: str
    avatar_url: Optional[str] = None


class PostingIdOut(BaseModel):
    id: UUID
    facebook_user_id: str
    name: str
    avatar_url: Optional[str] = None
    status: PostingIdStatus
    health_score: int
    reach_28d: int = 0
    last_used_at: Optional[datetime] = None
    retired_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PostingIdRetire(BaseModel):
    confirm: bool = Field(description="Must be true to retire")


# ── Posts ──────────────────────────────────────────────

class PostCreate(BaseModel):
    page_id: UUID
    media_type: MediaType = MediaType.photo
    caption_facebook: Optional[str] = Field(default=None, max_length=63206)
    caption_instagram: Optional[str] = Field(default=None, max_length=2200)
    caption_threads: Optional[str] = Field(default=None, max_length=500)
    publish_to_facebook: bool = True
    publish_to_instagram: bool = False
    publish_to_threads: bool = False
    scheduled_at: Optional[datetime] = None
    thread_comments: Optional[list[str]] = Field(default=None, max_length=3)


class PostUpdate(BaseModel):
    caption_facebook: Optional[str] = Field(default=None, max_length=63206)
    caption_instagram: Optional[str] = Field(default=None, max_length=2200)
    caption_threads: Optional[str] = Field(default=None, max_length=500)
    publish_to_facebook: Optional[bool] = None
    publish_to_instagram: Optional[bool] = None
    publish_to_threads: Optional[bool] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[PostStatus] = None
    thread_comments: Optional[list[str]] = Field(default=None, max_length=3)


class PostOut(BaseModel):
    id: UUID
    page_id: UUID
    created_by: UUID
    posting_id_used: Optional[UUID] = None
    status: PostStatus
    failed_category: Optional[FailedCategory] = None
    media_type: MediaType
    caption_facebook: Optional[str] = None
    caption_instagram: Optional[str] = None
    caption_threads: Optional[str] = None
    publish_to_facebook: bool
    publish_to_instagram: bool
    publish_to_threads: bool
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    retry_count: int = 0
    file_hash: Optional[str] = None
    is_outside_active_hours: bool = False
    created_at: datetime
    updated_at: datetime
    media: Optional[list["PostMediaOut"]] = None
    thread_comments: Optional[list["ThreadCommentOut"]] = None


class PostMediaOut(BaseModel):
    id: UUID
    file_url: str
    file_key: str
    mime_type: str
    file_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    duration_secs: Optional[float] = None
    sort_order: int


class ThreadCommentOut(BaseModel):
    id: UUID
    content: str
    sort_order: int


# ── Approvals ─���────────────────────────────────────────

class ApprovalCreate(BaseModel):
    post_id: UUID
    action: ApprovalAction
    comment: Optional[str] = None


class ApprovalOut(BaseModel):
    id: UUID
    post_id: UUID
    reviewed_by: UUID
    action: ApprovalAction
    comment: Optional[str] = None
    created_at: datetime
    reviewer_name: Optional[str] = None


# ── Team Members ───────────────��───────────────────────

class TeamMemberCreate(BaseModel):
    email: EmailStr
    roles: list[UserRole]
    batch_ids: list[UUID] = []


class TeamMemberUpdate(BaseModel):
    roles: Optional[list[UserRole]] = None
    batch_ids: Optional[list[UUID]] = None
    status: Optional[str] = None


class TeamMemberOut(BaseModel):
    id: UUID
    user_id: UUID
    roles: list[str]
    batch_ids: list[UUID]
    status: str
    invited_by: Optional[UUID] = None
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None
    created_at: datetime
    user: Optional[UserOut] = None


# ── Invite Links ───────────────────────────────────────

class InviteLinkCreate(BaseModel):
    email: EmailStr
    roles: list[UserRole]
    batch_ids: list[UUID] = []


class InviteLinkOut(BaseModel):
    id: UUID
    token: str
    email: str
    roles: list[str]
    batch_ids: list[UUID]
    invited_by: UUID
    expires_at: datetime
    status: str
    created_at: datetime


# ── File Upload ────────────────────────────────────────

class PresignedUrlRequest(BaseModel):
    filename: str
    content_type: str
    file_size: int


class PresignedUrlResponse(BaseModel):
    upload_url: str
    object_key: str
    file_url: str


class FileUploadConfirm(BaseModel):
    post_id: UUID
    object_key: str
    file_hash: str
    file_size: int
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_secs: Optional[float] = None


# ── Insights / Revenue ────────────────────────────────

class PageInsightOut(BaseModel):
    id: UUID
    page_id: UUID
    period_start: date
    period_end: date
    views: int = 0
    viewers: int = 0
    follows: int = 0
    unfollows: int = 0
    visits: int = 0
    interactions: int = 0
    link_clicks: int = 0
    video_views: int = 0
    reactions: int = 0
    comments: int = 0
    shares: int = 0
    fetched_at: datetime


class RevenueRecordOut(BaseModel):
    id: UUID
    page_id: UUID
    date: date
    total_cents: int
    reels_cents: int
    photos_cents: int
    stories_cents: int
    text_cents: int
    views: int
    currency: str
    fetched_at: datetime


# ── Generic ────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
