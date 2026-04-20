"""Real Meta Graph API client. Compiled but not exercised in tests (META_MODE=live only)."""
import requests
from datetime import datetime, timezone
from app.services.meta.client import (
    FBPublishPayload, IGPublishPayload, ThreadsPublishPayload,
    PublishResult, PageInsightPoint, RevenuePoint, FBPageSummary, OAuthExchangeResult,
)
from app.services.meta.errors import classify_error, MetaTimeout

GRAPH_URL = "https://graph.facebook.com/v21.0"
TIMEOUT = 60


class LiveMetaClient:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret

    def _get(self, path: str, **params):
        try:
            r = requests.get(f"{GRAPH_URL}/{path}", params=params, timeout=TIMEOUT)
        except requests.Timeout:
            raise MetaTimeout("Meta API timeout")
        data = r.json()
        if "error" in data:
            raise classify_error(data)
        return data

    def _post(self, path: str, **data):
        try:
            r = requests.post(f"{GRAPH_URL}/{path}", data=data, timeout=TIMEOUT)
        except requests.Timeout:
            raise MetaTimeout("Meta API timeout")
        resp = r.json()
        if "error" in resp:
            raise classify_error(resp)
        return resp

    def exchange_code(self, code: str, redirect_uri: str) -> OAuthExchangeResult:
        d = self._get("oauth/access_token", client_id=self.app_id, client_secret=self.app_secret,
                      redirect_uri=redirect_uri, code=code)
        me = self._get("me", access_token=d["access_token"])
        return OAuthExchangeResult(user_id=me["id"], user_access_token=d["access_token"],
                                   expires_at=datetime.now(timezone.utc))

    def list_pages(self, user_token: str) -> list[FBPageSummary]:
        d = self._get("me/accounts", access_token=user_token)
        return [FBPageSummary(id=p["id"], name=p["name"], access_token=p["access_token"],
                              category=p.get("category", "")) for p in d.get("data", [])]

    def get_page_token(self, page_id: str, user_token: str) -> str:
        d = self._get(f"{page_id}", access_token=user_token, fields="access_token")
        return d["access_token"]

    def publish_fb(self, payload: FBPublishPayload) -> PublishResult:
        if payload.media_type == "text":
            r = self._post(f"{payload.page_id}/feed", message=payload.caption, access_token=payload.token)
            return PublishResult(platform_post_id=r["id"], published_at=datetime.now(timezone.utc))
        if payload.media_type == "photo":
            r = self._post(f"{payload.page_id}/photos", url=payload.media_urls[0],
                           caption=payload.caption, access_token=payload.token)
            return PublishResult(platform_post_id=r["post_id"], published_at=datetime.now(timezone.utc))
        init = self._post(f"{payload.page_id}/video_reels", upload_phase="start", access_token=payload.token)
        video_id = init["video_id"]
        upload_url = init["upload_url"]
        requests.post(upload_url, headers={"file_url": payload.media_urls[0],
                                           "Authorization": f"OAuth {payload.token}"}, timeout=TIMEOUT)
        self._post(f"{payload.page_id}/video_reels", upload_phase="finish", video_id=video_id,
                   description=payload.caption, access_token=payload.token)
        return PublishResult(platform_post_id=f"{payload.page_id}_{video_id}",
                             published_at=datetime.now(timezone.utc))

    def publish_ig(self, payload: IGPublishPayload) -> PublishResult:
        key = "image_url" if payload.media_type == "photo" else "video_url"
        container = self._post(f"{payload.page_id}/media", **{key: payload.media_urls[0]},
                               caption=payload.caption,
                               media_type=("REELS" if payload.media_type == "reel" else "IMAGE"),
                               access_token=payload.token)
        import time
        for _ in range(20):
            s = self._get(container["id"], access_token=payload.token, fields="status_code")
            if s.get("status_code") == "FINISHED":
                break
            time.sleep(3)
        pub = self._post(f"{payload.page_id}/media_publish", creation_id=container["id"],
                         access_token=payload.token)
        return PublishResult(platform_post_id=pub["id"], published_at=datetime.now(timezone.utc))

    def publish_threads(self, payload: ThreadsPublishPayload) -> PublishResult:
        body = {"media_type": "TEXT" if payload.media_type == "text" else "IMAGE",
                "text": payload.caption, "access_token": payload.token}
        if payload.media_type == "photo":
            body["image_url"] = payload.media_urls[0]
        container = self._post(f"{payload.page_id}/threads", **body)
        pub = self._post(f"{payload.page_id}/threads_publish", creation_id=container["id"],
                         access_token=payload.token)
        return PublishResult(platform_post_id=pub["id"], published_at=datetime.now(timezone.utc))

    def add_thread_comment(self, page_id: str, token: str, parent_post_id: str, text: str) -> str:
        r = self._post(f"{parent_post_id}/comments", message=text, access_token=token)
        return r["id"]

    def get_page_insights(self, page_id: str, token: str, since: str, until: str) -> list[PageInsightPoint]:
        d = self._get(f"{page_id}/insights", access_token=token, since=since, until=until,
                      metric="page_impressions,page_post_engagements,page_fans,page_reach")
        return []

    def get_monetization_insights(self, page_id: str, token: str, since: str, until: str) -> list[RevenuePoint]:
        return []

    def ping_token(self, token: str) -> bool:
        try:
            self._get("me", access_token=token)
            return True
        except Exception:
            return False
