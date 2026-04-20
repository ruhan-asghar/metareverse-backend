from enum import StrEnum


class PostStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    QUEUED = "queued"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED_TEMPORARY = "failed_temporary"
    FAILED_PERMANENT = "failed_permanent"
    RECONNECT_REQUIRED = "reconnect_required"
    PAUSED = "paused"


LEGAL_TRANSITIONS = frozenset({
    (PostStatus.DRAFT, PostStatus.PENDING_APPROVAL),
    (PostStatus.DRAFT, PostStatus.QUEUED),
    (PostStatus.PENDING_APPROVAL, PostStatus.QUEUED),
    (PostStatus.PENDING_APPROVAL, PostStatus.REJECTED),
    (PostStatus.PENDING_APPROVAL, PostStatus.CHANGES_REQUESTED),
    (PostStatus.CHANGES_REQUESTED, PostStatus.DRAFT),
    (PostStatus.REJECTED, PostStatus.DRAFT),
    (PostStatus.QUEUED, PostStatus.PUBLISHING),
    (PostStatus.QUEUED, PostStatus.RECONNECT_REQUIRED),
    (PostStatus.QUEUED, PostStatus.PAUSED),
    (PostStatus.PUBLISHING, PostStatus.PUBLISHED),
    (PostStatus.PUBLISHING, PostStatus.FAILED_TEMPORARY),
    (PostStatus.PUBLISHING, PostStatus.FAILED_PERMANENT),
    (PostStatus.PUBLISHING, PostStatus.RECONNECT_REQUIRED),
    (PostStatus.PUBLISHING, PostStatus.PAUSED),
    (PostStatus.FAILED_TEMPORARY, PostStatus.QUEUED),
    (PostStatus.FAILED_TEMPORARY, PostStatus.PUBLISHING),
    (PostStatus.RECONNECT_REQUIRED, PostStatus.QUEUED),
    (PostStatus.PAUSED, PostStatus.QUEUED),
})


def can_transition(src: PostStatus, dst: PostStatus) -> bool:
    if src == dst:
        return False
    return (src, dst) in LEGAL_TRANSITIONS
