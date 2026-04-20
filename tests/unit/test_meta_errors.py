import pytest
from app.services.meta.errors import (
    MetaError, TokenExpired, RateLimited, PostingIDRevoked,
    MediaRejected, MetaTimeout, TransientMetaError, classify_error
)


def test_classify_190():
    e = classify_error({"error": {"code": 190, "message": "Token expired"}})
    assert isinstance(e, TokenExpired)


def test_classify_4():
    e = classify_error({"error": {"code": 4, "message": "Rate limited"}}, retry_after=30)
    assert isinstance(e, RateLimited) and e.retry_after == 30


def test_classify_100_user():
    e = classify_error({"error": {"code": 100, "message": "user invalid"}}, is_posting_id=True)
    assert isinstance(e, PostingIDRevoked)


def test_classify_media_rejected():
    e = classify_error({"error": {"code": 1366046, "message": "bad media"}})
    assert isinstance(e, MediaRejected)


def test_classify_transient():
    e = classify_error({"error": {"code": 2, "message": "server"}})
    assert isinstance(e, TransientMetaError)
