import hashlib
import random
from datetime import datetime, timedelta, timezone
from app.services.meta.client import (
    FBPublishPayload, IGPublishPayload, ThreadsPublishPayload,
    PublishResult, PageInsightPoint, RevenuePoint, FBPageSummary, OAuthExchangeResult,
)
from app.services.meta.errors import TokenExpired, RateLimited, MediaRejected, TransientMetaError, MetaTimeout

_FORCE_MAP = {
    "token_expired": lambda: (_ for _ in ()).throw(TokenExpired("mock token expired", code=190)),
    "rate_limited": lambda: (_ for _ in ()).throw(RateLimited("mock rate limited", code=4, retry_after=1)),
    "media_rejected": lambda: (_ for _ in ()).throw(MediaRejected("mock media rejected", code=1366046)),
    "transient": lambda: (_ for _ in ()).throw(TransientMetaError("mock transient", code=2)),
    "timeout": lambda: (_ for _ in ()).throw(MetaTimeout("mock timeout")),
}


def _id(prefix: str, *parts: str) -> str:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
    return f"{prefix}_{h}"


class MockMetaClient:
    def __init__(self, seed: int = 0, force_error: str | None = None, publish_latency_ms: int = 0):
        self.rng = random.Random(seed)
        self.force_error = force_error
        self.publish_latency_ms = publish_latency_ms

    def _maybe_raise(self):
        if self.force_error and self.force_error in _FORCE_MAP:
            _FORCE_MAP[self.force_error]()

    def exchange_code(self, code: str, redirect_uri: str) -> OAuthExchangeResult:
        self._maybe_raise()
        return OAuthExchangeResult(
            user_id=_id("u", code),
            user_access_token=_id("ut", code, redirect_uri),
            expires_at=datetime.now(timezone.utc) + timedelta(days=60),
        )

    def list_pages(self, user_token: str) -> list[FBPageSummary]:
        self._maybe_raise()
        rng = random.Random(user_token)
        n = rng.randint(3, 6)
        return [FBPageSummary(
            id=_id("pg", user_token, str(i)),
            name=f"Mock Page {i+1}",
            access_token=_id("pt", user_token, str(i)),
            category=rng.choice(["News", "Entertainment", "Sports", "Education"]),
        ) for i in range(n)]

    def get_page_token(self, page_id: str, user_token: str) -> str:
        self._maybe_raise()
        return _id("pt", page_id, user_token)

    def publish_fb(self, payload: FBPublishPayload) -> PublishResult:
        self._maybe_raise()
        return PublishResult(
            platform_post_id=_id("fb", payload.page_id, payload.caption[:32]),
            published_at=datetime.now(timezone.utc),
        )

    def publish_ig(self, payload: IGPublishPayload) -> PublishResult:
        self._maybe_raise()
        return PublishResult(
            platform_post_id=_id("ig", payload.page_id, payload.caption[:32]),
            published_at=datetime.now(timezone.utc),
        )

    def publish_threads(self, payload: ThreadsPublishPayload) -> PublishResult:
        self._maybe_raise()
        return PublishResult(
            platform_post_id=_id("th", payload.page_id, payload.caption[:32]),
            published_at=datetime.now(timezone.utc),
        )

    def add_thread_comment(self, page_id: str, token: str, parent_post_id: str, text: str) -> str:
        self._maybe_raise()
        return _id("cm", page_id, parent_post_id, text[:16])

    def get_page_insights(self, page_id: str, token: str, since: str, until: str) -> list[PageInsightPoint]:
        self._maybe_raise()
        start = datetime.fromisoformat(since).date()
        end = datetime.fromisoformat(until).date()
        days = (end - start).days + 1
        rng = random.Random(f"{page_id}:{since}")
        base_viewers = rng.randint(5000, 15000)
        out = []
        for i in range(days):
            d = start + timedelta(days=i)
            growth = 1 + (i * 0.002)
            noise = rng.uniform(0.85, 1.15)
            viewers = int(base_viewers * growth * noise)
            views = int(viewers * rng.uniform(1.2, 1.8))
            interactions = int(viewers * rng.uniform(0.03, 0.08))
            out.append(PageInsightPoint(
                date=d.isoformat(),
                views=views,
                viewers=viewers,
                interactions=interactions,
                follows=rng.randint(5, 25) * (i + 1),
                video_views=int(views * rng.uniform(0.2, 0.5)),
                reactions=int(interactions * rng.uniform(0.5, 0.75)),
                comments=int(interactions * rng.uniform(0.08, 0.18)),
                shares=int(interactions * rng.uniform(0.05, 0.12)),
            ))
        return out

    def get_monetization_insights(self, page_id: str, token: str, since: str, until: str) -> list[RevenuePoint]:
        self._maybe_raise()
        start = datetime.fromisoformat(since).date()
        end = datetime.fromisoformat(until).date()
        days = (end - start).days + 1
        rng = random.Random(f"rev:{page_id}:{since}")
        out = []
        for i in range(days):
            d = start + timedelta(days=i)
            out.append(RevenuePoint(
                date=d.isoformat(),
                reels_cents=rng.randint(600, 3800),
                photos_cents=rng.randint(100, 900),
                stories_cents=rng.randint(50, 500),
                text_cents=rng.randint(0, 200),
            ))
        return out

    def ping_token(self, token: str) -> bool:
        if self.force_error == "token_expired":
            return False
        return True
