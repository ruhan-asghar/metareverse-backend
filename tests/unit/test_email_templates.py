import pytest
from app.services.email.templates import render_email


def test_render_invite():
    html, subject = render_email("invite", {"org_name": "Acme", "invite_url": "http://x",
                                            "inviter": "Ruhan", "expires_at": "2026-05-01"})
    assert "Acme" in html and "http://x" in html
    assert subject and len(subject) > 0


def test_render_all_6():
    for kind in ["invite", "token_expired", "post_failed", "digest_daily",
                 "approval_requested", "approval_action_taken"]:
        html, subject = render_email(kind, {"page_name": "P", "org_name": "O", "invite_url": "u",
                                            "inviter": "x", "expires_at": "2026-05-01",
                                            "severity": "token_expired", "post_title": "t",
                                            "error_message": "m", "stats": {"published": 0, "failed": 0, "pending": 0},
                                            "action": "approve", "reviewer": "r"})
        assert html and subject


def test_unknown_template_raises():
    with pytest.raises(ValueError):
        render_email("bogus", {})
