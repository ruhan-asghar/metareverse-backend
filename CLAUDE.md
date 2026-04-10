# MetaReverse — Backend API

## Architecture
- **Stack**: Python + FastAPI + Uvicorn
- **Purpose**: Backend API for MetaReverse system
- **Folder**: `/backend` within the metareverse monorepo
- **Deployment**: Vercel (via vercel.json serverless config)
- **Entry point**: `main.py`

## Environment
- No env vars yet
- Virtual env in `venv/` (gitignored)

## Services & APIs
- None yet — skeleton only

## How We Solved It
- FastAPI chosen for async performance and auto-docs at /docs

## Gotchas
- Part of a monorepo — each sub-project has its own git repo and Vercel deployment
- venv/ must stay gitignored
