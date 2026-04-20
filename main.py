from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv()

from app.core.logging import configure_logging
from app.core.sentry import init_sentry_api
configure_logging()
init_sentry_api()

from app.core.config import get_settings
from app.api import webhooks, batches, pages, posts, approvals, posting_ids, team, uploads, reports, sse, oauth, notifications, admin, dashboard

settings = get_settings()

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="MetaReverse API",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return Response(
        content='{"detail": "Rate limit exceeded"}',
        status_code=429,
        media_type="application/json",
    )


# X-Robots-Tag middleware — block search engine indexing on all responses
class NoIndexMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

app.add_middleware(NoIndexMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(batches.router, prefix="/api/v1")
app.include_router(pages.router, prefix="/api/v1")
app.include_router(posts.router, prefix="/api/v1")
app.include_router(approvals.router, prefix="/api/v1")
app.include_router(posting_ids.router, prefix="/api/v1")
app.include_router(team.router, prefix="/api/v1")
app.include_router(uploads.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(sse.router, prefix="/api/v1")
app.include_router(oauth.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    return "User-agent: *\nDisallow: /\n"


@app.get("/")
async def root():
    return {"status": "ok", "service": "metareverse-api", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
