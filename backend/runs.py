"""Run lifecycle: create, process in the background, stream rows over SSE."""
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, EmailStr, Field

from . import mailer, store
from .models import Run, tally

router = APIRouter(prefix="/api/runs")

# One queue per in-flight run; the SSE endpoint drains it.
_queues: dict[str, asyncio.Queue] = {}

# One lock per run so a double click cannot race past the sent-state check.
_email_locks: dict[str, asyncio.Lock] = {}


class CreateRun(BaseModel):
    source_urls: list[str] = Field(min_length=1)
    questions: list[str] = Field(min_length=1)
    email: EmailStr


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pipeline():
    """Mock while the UI is being built; real agent once it exists."""
    if os.environ.get("MOCK_AGENT") == "1":
        from . import mock_agent

        return mock_agent.run_pipeline
    from . import agent

    return agent.run_pipeline


async def _process(run: Run) -> None:
    queue = _queues[run.run_id]

    async def emit(row) -> None:
        await queue.put({"type": "row", "row": row.dict()})

    try:
        await _pipeline()(run, emit)
        run.status = "done"
    except Exception as exc:  # surfaced to the UI, not swallowed
        run.status = "error"
        run.error = f"{type(exc).__name__}: {exc}"
    store.checkpoint(run)
    await queue.put({"type": "done", "status": run.status, "error": run.error})


@router.post("")
async def create_run(body: CreateRun):
    run = Run(
        run_id=uuid.uuid4().hex[:12],
        created_at=_now(),
        email=str(body.email),
        source_urls=[u.strip() for u in body.source_urls if u.strip()],
        questions=[q.strip() for q in body.questions if q.strip()],
    )
    if not run.source_urls or not run.questions:
        return JSONResponse(
            {"detail": "At least one source URL and one question are required."},
            status_code=422,
        )
    store.put(run)
    _queues[run.run_id] = asyncio.Queue()
    asyncio.create_task(_process(run))
    return {"run_id": run.run_id}


@router.get("")
def list_runs():
    return {"runs": [r.summary() for r in store.list_runs()]}


@router.get("/{run_id}")
def get_run(run_id: str):
    run = store.get(run_id)
    if not run:
        return JSONResponse({"detail": "Run not found"}, status_code=404)
    return {**run.dict(), "stats": tally(run.rows)}


@router.get("/{run_id}/stream")
async def stream_run(run_id: str, request: Request):
    run = store.get(run_id)
    if not run:
        return JSONResponse({"detail": "Run not found"}, status_code=404)

    async def events():
        # Replay what already completed, so a reconnect is never missing rows.
        for row in list(run.rows):
            yield _sse({"type": "row", "row": row.dict()})
        if run.status != "running":
            yield _sse({"type": "done", "status": run.status, "error": run.error})
            return

        queue = _queues.get(run_id)
        if queue is None:
            yield _sse({"type": "done", "status": run.status, "error": run.error})
            return

        seen = len(run.rows)
        while True:
            if await request.is_disconnected():
                return
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"  # keeps proxies from closing the stream
                continue
            # Rows replayed above must not be sent twice.
            if event["type"] == "row":
                seen -= 1
                if seen >= 0:
                    continue
            yield _sse(event)
            if event["type"] == "done":
                return

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/{run_id}/email")
async def send_email(run_id: str):
    """Idempotent per run_id: a double click sends exactly once."""
    run = store.get(run_id)
    if not run:
        return JSONResponse({"detail": "Run not found"}, status_code=404)
    if run.status == "running":
        return JSONResponse({"detail": "Run is still in progress."}, status_code=409)
    if not run.rows:
        return JSONResponse({"detail": "This run has no results to send."}, status_code=409)

    lock = _email_locks.setdefault(run_id, asyncio.Lock())
    async with lock:
        # Re-checked inside the lock: the first caller may have sent while we waited.
        if run.email_sent_at:
            return {"already_sent": True, "sent_at": run.email_sent_at, "to": run.email}
        try:
            message_id = await mailer.send_results(run)
        except (mailer.MailError, httpx.HTTPError) as exc:
            return JSONResponse({"detail": str(exc)[:300]}, status_code=502)
        run.email_sent_at = _now()
        run.email_message_id = message_id
        store.checkpoint(run)
    return {"already_sent": False, "sent_at": run.email_sent_at, "to": run.email}
