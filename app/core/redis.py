import redis
from functools import lru_cache
from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    s = get_settings()
    return redis.from_url(s.redis_url, decode_responses=True)
