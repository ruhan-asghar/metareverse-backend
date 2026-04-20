# Railway Deploy — MetaReverse Backend

## Overview
One Railway project, four services: `api`, `worker`, `beat`, `redis`. All three Python services share the same Dockerfile and codebase; they differ only in start command. Redis is a Railway plugin, not a repo service.

## Prerequisites
- Railway account + CLI (`npm i -g @railway/cli` then `railway login`)
- GitHub repo `ruhan-asghar/metareverse-backend` connected to Railway org
- Supabase `DATABASE_URL` (has `@` in password — keep full URL string)
- Meta app credentials (or `META_MODE=mock` for dev)
- Resend API key
- Cloudflare R2 bucket credentials
- Clerk secret + webhook secret

## Service 1 — api
Public HTTP service. Serves FastAPI + SSE.

1. Railway dashboard → project → **New → GitHub Repo** → pick `metareverse-backend` → Branch `master`.
2. After provisioning: **Settings → Source → Root Directory** = `/` (backend repo root).
3. **Settings → Build → Builder** = Dockerfile (auto-detected from `Dockerfile`).
4. **Settings → Deploy → Start Command**:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
5. **Settings → Networking → Generate Domain** → produces `metareverse-backend-production.up.railway.app`.
6. **Settings → Health Check → Path** = `/health`, **Timeout** = `30`.
7. Set all env vars from the table below.

## Service 2 — worker
Celery worker. No public port.

1. **New → GitHub Repo** → same repo, same branch.
2. Rename service to `worker`.
3. **Settings → Deploy → Start Command**:
   ```
   celery -A app.celery_app worker -Q publish,insights,email,health --loglevel=info --concurrency=4
   ```
4. **Settings → Networking** → leave private (no domain).
5. Reuse the same env vars as `api`.

## Service 3 — beat
Celery beat scheduler (redbeat). Exactly one replica — do not scale horizontally.

1. **New → GitHub Repo** → same repo, same branch.
2. Rename service to `beat`.
3. **Settings → Deploy → Start Command**:
   ```
   celery -A app.celery_app beat --scheduler redbeat.RedBeatScheduler --loglevel=info
   ```
4. **Settings → Deploy → Replicas** = `1` (enforce).
5. Reuse the same env vars as `api`.

## Service 4 — redis
1. **New → Database → Add Redis**.
2. Railway exposes `REDIS_URL` on the Redis service as `${{Redis.REDIS_URL}}`.
3. In each Python service (`api`, `worker`, `beat`): **Variables → New Reference** → pick Redis → `REDIS_URL`. Also add references for `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` pointing at the same `${{Redis.REDIS_URL}}`.

## Env vars (full list)
Values come from `backend/app/core/config.py::Settings`.

| Var | Required | Notes |
|---|---|---|
| `CLERK_SECRET_KEY` | yes | Clerk backend key. Also used to derive AES-256-GCM encryption key. |
| `CLERK_WEBHOOK_SECRET` | yes | Svix signing secret. |
| `SUPABASE_URL` | yes | `https://<project>.supabase.co` |
| `SUPABASE_ANON_KEY` | yes | Public anon key. |
| `SUPABASE_SERVICE_ROLE_KEY` | yes | Bypasses RLS. Backend only. |
| `DATABASE_URL` | yes | Full Postgres URL. `@` in password must stay URL-encoded (`%40`). |
| `R2_ACCOUNT_ID` | yes | Cloudflare account ID. |
| `R2_ACCESS_KEY_ID` | yes | R2 access key. |
| `R2_SECRET_ACCESS_KEY` | yes | R2 secret. |
| `R2_BUCKET_NAME` | no | Defaults to `metareverse-media`. |
| `R2_ENDPOINT` | yes | `https://<account>.r2.cloudflarestorage.com` |
| `META_APP_ID` | yes | Facebook app ID. Use `975156345457739` for dev app. |
| `META_APP_SECRET` | yes | Facebook app secret. |
| `META_MODE` | no | `mock` or `live`. Defaults to `mock`. |
| `META_OAUTH_REDIRECT_URI` | yes in live | `https://api.metareverse.xyz/api/v1/oauth/facebook/callback` |
| `RESEND_API_KEY` | yes | Resend email. |
| `RESEND_FROM_EMAIL` | no | Defaults to `noreply@metareverse.xyz`. |
| `CLOUDFLARE_API_TOKEN` | no | For DNS / WAF automation. |
| `REDIS_URL` | yes | Reference `${{Redis.REDIS_URL}}`. |
| `CELERY_BROKER_URL` | no | Falls back to `REDIS_URL`. |
| `CELERY_RESULT_BACKEND` | no | Falls back to `REDIS_URL`. |
| `SENTRY_DSN_API` | no | DSN for api service. |
| `SENTRY_DSN_WORKER` | no | DSN for worker + beat. |
| `LOG_LEVEL` | no | `info` / `debug` / `warning`. |
| `ENVIRONMENT` | no | `production` on Railway; defaults to `development`. |
| `PORT` | auto | Railway injects. Only api uses it. |

Tip: define once on `api`, then use Railway's **Shared Variables** to reference the same set on `worker` and `beat`.

## Deploy trigger
Every push to `master` auto-redeploys all three Python services. Redis is not tied to the repo.

## First-time migration
Run migrations locally (or from a one-off Railway shell) against the Supabase `DATABASE_URL`. The psycopg2 URL variant of `DATABASE_URL` expects `%40` for `@`; plain `psql` handles either.

```bash
# From backend/
psql "$DATABASE_URL" -f migrations/001_initial_schema.sql
psql "$DATABASE_URL" -f migrations/002_rls_policies.sql
psql "$DATABASE_URL" -f migrations/003_seed_data.sql
psql "$DATABASE_URL" -f migrations/004_week2_tables.sql
```

Re-running a migration is safe only if it is written idempotently. Week-2 tables (`004`) add Celery-specific tables — apply once per environment.

## Health check
```bash
curl https://metareverse-backend-production.up.railway.app/health
# expected: {"status":"healthy"}
```

Root also returns a small status payload:
```bash
curl https://metareverse-backend-production.up.railway.app/
# {"status":"ok","service":"metareverse-api","version":"0.1.0"}
```

For worker/beat: check Railway logs. Worker prints `celery@<host> ready.`; beat prints `beat: Starting...`.

## Observability
- **Sentry** — set `SENTRY_DSN_API` on `api`, `SENTRY_DSN_WORKER` on `worker` and `beat`. Init is in `app/core/sentry.py` (imported from `main.py` and the Celery entrypoint).
- **Logs** — Railway ships stdout/stderr. `LOG_LEVEL=info` is the default; bump to `debug` during incidents.
- **Metrics** — Railway dashboard per-service CPU/RAM/network. For Celery queue depth, inspect Redis directly (`redis-cli -u $REDIS_URL llen publish`).

## Custom domain
Production target: `api.metareverse.xyz` → Cloudflare CNAME (proxied) → Railway `api` service domain. Set the domain in **api → Settings → Networking → Custom Domain**; Railway issues a managed cert.
