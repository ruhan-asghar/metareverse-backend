from datetime import datetime, timezone
from app.services.publishing.rotation import pick_round_robin, PostingIDCandidate


def test_picks_oldest_last_used():
    a = PostingIDCandidate(id="a", last_used_at=datetime(2026, 1, 1, tzinfo=timezone.utc), health_score=80)
    b = PostingIDCandidate(id="b", last_used_at=datetime(2026, 1, 2, tzinfo=timezone.utc), health_score=80)
    assert pick_round_robin([a, b]).id == "a"


def test_excludes_retired():
    a = PostingIDCandidate(id="a", last_used_at=None, health_score=80, status="retired")
    b = PostingIDCandidate(id="b", last_used_at=None, health_score=80, status="active")
    assert pick_round_robin([a, b]).id == "b"


def test_returns_none_when_all_retired():
    a = PostingIDCandidate(id="a", last_used_at=None, health_score=80, status="retired")
    assert pick_round_robin([a]) is None


def test_null_last_used_goes_first():
    a = PostingIDCandidate(id="a", last_used_at=None, health_score=80)
    b = PostingIDCandidate(id="b", last_used_at=datetime(2026, 1, 1, tzinfo=timezone.utc), health_score=80)
    assert pick_round_robin([a, b]).id == "a"
