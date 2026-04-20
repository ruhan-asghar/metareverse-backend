from typing import Protocol, Literal
from pydantic import BaseModel
from datetime import datetime


class FBPublishPayload(BaseModel):
    page_id: str
    token: str
    media_type: Literal["text", "photo", "reel"]
    caption: str
    media_urls: list[str] = []


class IGPublishPayload(BaseModel):
    page_id: str
    token: str
    media_type: Literal["photo", "reel"]
    caption: str
    media_urls: list[str]


class ThreadsPublishPayload(BaseModel):
    page_id: str
    token: str
    media_type: Literal["text", "photo"]
    caption: str
    media_urls: list[str] = []


class PublishResult(BaseModel):
    platform_post_id: str
    published_at: datetime


class PageInsightPoint(BaseModel):
    date: str
    reach: int
    impressions: int
    engagement: int
    followers: int


class RevenuePoint(BaseModel):
    date: str
    cpm_cents: int
    network_cents: int
    other_cents: int


class FBPageSummary(BaseModel):
    id: str
    name: str
    access_token: str
    category: str


class OAuthExchangeResult(BaseModel):
    user_id: str
    user_access_token: str
    expires_at: datetime


class MetaClient(Protocol):
    def exchange_code(self, code: str, redirect_uri: str) -> OAuthExchangeResult: ...
    def list_pages(self, user_token: str) -> list[FBPageSummary]: ...
    def get_page_token(self, page_id: str, user_token: str) -> str: ...
    def publish_fb(self, payload: FBPublishPayload) -> PublishResult: ...
    def publish_ig(self, payload: IGPublishPayload) -> PublishResult: ...
    def publish_threads(self, payload: ThreadsPublishPayload) -> PublishResult: ...
    def add_thread_comment(self, page_id: str, token: str, parent_post_id: str, text: str) -> str: ...
    def get_page_insights(self, page_id: str, token: str, since: str, until: str) -> list[PageInsightPoint]: ...
    def get_monetization_insights(self, page_id: str, token: str, since: str, until: str) -> list[RevenuePoint]: ...
    def ping_token(self, token: str) -> bool: ...
