"""Admin API — dead-letter queue + system metrics. Owner-only."""

import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, require_org
from app.core.database import get_db_cursor
from app.core.permissions import get_user_roles_and_batches
from app.celery_app import celery_app

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_owner(user: CurrentUser) -> None:
    roles, _batches, _uid = get_user_roles_and_batches(user.clerk_user_id, user.org_id)
    if "owner" not in roles and "co_owner" not in roles:
        raise HTTPException(status_code=403, detail="Owner or co-owner required")


def _maybe_json(val):
    """Postgres JSONB → already dict/list; TEXT → json.loads. Be permissive."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, (bytes, bytearray)):
        try:
            return json.loads(val.decode("utf-8"))
        except Exception:
            return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


@router.get("/dead-letter")
async def list_dead_letter(
    unresolved_only: bool = True,
    limit: int = 50,
    user: CurrentUser = Depends(require_org),
):
    _require_owner(user)
    where = []
    if unresolved_only:
        where.append("resolved_at IS NULL")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with get_db_cursor() as cur:
        cur.execute(
            f"""SELECT id, task_name, args, kwargs, exception, traceback, org_id,
                        retries, created_at, resolved_at
                FROM dead_letter
                {where_sql}
                ORDER BY created_at DESC
                LIMIT %s""",
            (max(1, min(limit, 200)),),
        )
        rows = cur.fetchall()
        return [
            {
                "id": str(r["id"]),
                "task_name": r["task_name"],
                "args": _maybe_json(r["args"]),
                "kwargs": _maybe_json(r["kwargs"]),
                "exception": r["exception"],
                "retries": r["retries"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "resolved_at": r["resolved_at"].isoformat() if r["resolved_at"] else None,
            }
            for r in rows
        ]


@router.post("/dead-letter/{dl_id}/replay")
async def replay_dead_letter(dl_id: UUID, user: CurrentUser = Depends(require_org)):
    _require_owner(user)
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT id, task_name, args, kwargs, resolved_at
               FROM dead_letter WHERE id = %s""",
            (dl_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Dead letter entry not found")
        if row["resolved_at"]:
            raise HTTPException(status_code=400, detail="Already resolved")

        args = _maybe_json(row["args"]) or []
        kwargs = _maybe_json(row["kwargs"]) or {}
        if not isinstance(args, list):
            args = list(args) if isinstance(args, (tuple,)) else [args]
        if not isinstance(kwargs, dict):
            kwargs = {}

        celery_app.send_task(row["task_name"], args=args, kwargs=kwargs)

        cur.execute(
            "UPDATE dead_letter SET resolved_at = now() WHERE id = %s",
            (dl_id,),
        )

    return {"id": str(dl_id), "replayed": True}


@router.get("/metrics")
async def system_metrics(user: CurrentUser = Depends(require_org)):
    _require_owner(user)
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT recorded_at, queue_depth_publish, queue_depth_insights,
                      queue_depth_email, avg_publish_latency_ms, error_rate_5m
               FROM system_metrics
               ORDER BY recorded_at DESC
               LIMIT 60"""
        )
        rows = cur.fetchall()
        return [
            {
                "recorded_at": r["recorded_at"].isoformat() if r["recorded_at"] else None,
                "queue_depth_publish": r["queue_depth_publish"],
                "queue_depth_insights": r["queue_depth_insights"],
                "queue_depth_email": r["queue_depth_email"],
                "avg_publish_latency_ms": r["avg_publish_latency_ms"],
                "error_rate_5m": float(r["error_rate_5m"]) if r["error_rate_5m"] is not None else None,
            }
            for r in rows
        ]
