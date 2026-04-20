from app.core.redis import get_redis


def test_redis_client_singleton():
    a = get_redis()
    b = get_redis()
    assert a is b
