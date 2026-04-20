from app.services.publishing.state_machine import can_transition, LEGAL_TRANSITIONS, PostStatus


def test_legal_transition_queued_to_publishing():
    assert can_transition(PostStatus.QUEUED, PostStatus.PUBLISHING)


def test_illegal_published_to_queued():
    assert not can_transition(PostStatus.PUBLISHED, PostStatus.QUEUED)


def test_all_64_pairs():
    statuses = list(PostStatus)
    for a in statuses:
        for b in statuses:
            got = can_transition(a, b)
            expected = (a, b) in LEGAL_TRANSITIONS
            assert got == expected, f"{a}->{b}"
