from datetime import datetime, timezone
from pydantic import BaseModel


class PostingIDCandidate(BaseModel):
    id: str
    last_used_at: datetime | None
    health_score: int
    status: str = "active"


def pick_round_robin(candidates: list[PostingIDCandidate]) -> PostingIDCandidate | None:
    active = [c for c in candidates if c.status == "active"]
    if not active:
        return None
    MIN = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(active, key=lambda c: (c.last_used_at is not None, c.last_used_at or MIN))[0]
