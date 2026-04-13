# MetaReverse — Backend API

## Architecture
- **Stack**: Python 3.12 + FastAPI + Uvicorn + psycopg2
- **Purpose**: Backend API for MetaReverse platform
- **Folder**: `/backend` within the metareverse monorepo
- **Deployment**: Railway (persistent server, SSE support, background workers)
- **Entry point**: `main.py` → imports from `app/` package

### Project Structure
```
backend/
├── main.py                  # FastAPI app entry point, route wiring
├── app/
│   ├── api/                 # Route handlers
│   │   ├── webhooks.py      # Clerk webhook (user/org sync)
│   │   ├── batches.py       # Batch CRUD
│   │   ├── pages.py         # Page CRUD (batch-scoped)
│   │   ├── posts.py         # Post CRUD + state machine transitions
│   │   ├── approvals.py     # Approval with race condition guard (FOR UPDATE)
│   │   ├── posting_ids.py   # Posting ID CRUD + retire + page assignments
│   │   ├── team.py          # Team members + invite links (7-day expiry)
│   │   ├── uploads.py       # R2 presigned URLs, confirm upload, duplicate detection
│   │   ├── reports.py       # Overview, earnings, page revenue, posting ID health
│   │   └── sse.py           # Server-Sent Events for real-time updates
│   ├── core/                # Shared infrastructure
│   │   ├── config.py        # Pydantic Settings from .env
│   │   ├── database.py      # psycopg2 connection + context managers
│   │   ├── auth.py          # Clerk JWT verification (RS256 + JWKS)
│   │   ├── permissions.py   # 6-role permission matrix from PRD
│   │   ├── encryption.py    # AES-256-GCM for Facebook tokens
│   │   └── storage.py       # Cloudflare R2 (S3-compatible) operations
│   └── models/
│       └── schemas.py       # All Pydantic request/response models
├── migrations/
│   ├── 001_initial_schema.sql   # 15 tables, enums, indexes, triggers
│   ├── 002_rls_policies.sql     # Row Level Security on all tables
│   └── 003_seed_data.sql        # 3 batches, 7 pages, 10 posts, insights, revenue
├── Procfile                 # Railway start command
├── runtime.txt              # Python 3.12
└── requirements.txt         # Pinned dependencies
```

### API Routes (44 endpoints)
- `POST /api/v1/webhooks/clerk` — Clerk webhook handler
- `GET/POST/PATCH/DELETE /api/v1/batches` — Batch CRUD
- `GET/POST/PATCH /api/v1/pages` — Page CRUD (batch-scoped for non-owners)
- `GET/POST/PATCH/DELETE /api/v1/posts` — Post CRUD + state transitions
- `POST /api/v1/posts/{id}/submit` — Submit for approval
- `POST /api/v1/posts/{id}/schedule` — Direct schedule to queue
- `POST /api/v1/posts/{id}/retry` — Retry failed post
- `GET/POST /api/v1/approvals` — Approval with race condition guard
- `GET/POST /api/v1/posting-ids` — Posting ID CRUD
- `POST /api/v1/posting-ids/{id}/retire` — Permanent retirement
- `POST/DELETE /api/v1/posting-ids/{id}/assign/{page_id}` — Page assignments
- `GET/PATCH/DELETE /api/v1/team/members` — Team member management
- `GET/POST /api/v1/team/invites` — Invite links
- `POST /api/v1/team/invites/{id}/resend` — Resend (invalidates old)
- `POST /api/v1/team/invites/accept/{token}` — Accept invite
- `POST /api/v1/uploads/presigned-url` — R2 presigned upload URL
- `POST /api/v1/uploads/confirm` — Confirm upload + duplicate check
- `DELETE /api/v1/uploads/media/{id}` — Delete media
- `GET /api/v1/reports/overview` — KPI metrics
- `GET /api/v1/reports/earnings` — Revenue breakdown
- `GET /api/v1/reports/page-revenue` — Per-page revenue
- `GET /api/v1/reports/posting-id-health` — Health scores
- `GET /api/v1/sse/events` — SSE real-time stream

## Environment
All env vars in `.env` (gitignored):
- `CLERK_SECRET_KEY` — Clerk secret for JWT verification
- `CLERK_WEBHOOK_SECRET` — Webhook signing (svix)
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT`
- `CLOUDFLARE_API_TOKEN`
- `META_APP_ID`, `META_APP_SECRET`
- `RESEND_API_KEY`

## Services & APIs
- **PostgreSQL** via psycopg2 (direct connection to Supabase)
- **Clerk** — JWT verification via JWKS, webhook sync
- **Cloudflare R2** — S3-compatible file storage via boto3
- **Resend** — Email (API key configured, DNS pending)
- **SSE** via sse-starlette for real-time queue updates

## Database
- 15 tables with RLS enabled on all
- Key tables: organizations, users, batches, pages, posting_ids, posts, post_media, thread_comments, approvals, team_members, invite_links, page_insights, revenue_records, post_insights, page_posting_id_assignments
- `updated_at` triggers on all mutable tables
- Business rule triggers: batch deletion guard, posting ID unretire prevention
- Seed data: 1 org, 1 owner, 3 batches, 7 pages, 3 posting IDs, 10 posts, 7 insight records, 28 revenue records

## How We Solved It
- Used psycopg2 directly instead of Supabase Python SDK (build issues with pyiceberg dependency)
- DATABASE_URL has `@` in password — use host/port/dbname params instead of URL string
- RLS uses `current_setting('app.current_org_id')` — backend sets this via `SET LOCAL` before queries (defense-in-depth; service_role bypasses RLS)
- Approval race condition solved with `SELECT ... FOR UPDATE` row lock
- Revenue stored in cents (BIGINT) to avoid float precision issues
- AES-256-GCM encryption key derived from CLERK_SECRET_KEY via SHA-256 hash

## Gotchas
- Railway free plan limit — need to delete old projects or upgrade
- `venv/` must stay gitignored
- Vercel config removed — backend is Railway-only
- `Meta@reverse123` in DATABASE_URL needs URL encoding (`%40`) when used as connection string
