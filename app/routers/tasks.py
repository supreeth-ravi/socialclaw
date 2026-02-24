"""Tasks REST API — create, list, detail, stream progress, cancel."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..auth import get_current_user
from ..models import TaskCreate, TaskOut

router = APIRouter()


def _get_task_store(request: Request):
    return request.app.state.task_store


def _get_task_runner(request: Request):
    return request.app.state.task_runner


@router.post("/tasks", response_model=TaskOut)
async def create_task(
    body: TaskCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    agent_id = current_user["handle"]
    store = _get_task_store(request)
    runner = _get_task_runner(request)

    task = store.create(agent_id, body.intent, body.session_id or "")
    runner.submit(task["id"], agent_id, body.intent)
    return task


@router.get("/tasks")
async def list_tasks(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    agent_id = current_user["handle"]
    store = _get_task_store(request)
    return store.list_by_owner(agent_id)


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    store = _get_task_store(request)
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["owner_agent_id"] != current_user["handle"]:
        raise HTTPException(403, "Not your task")
    return task


@router.get("/tasks/{task_id}/stream")
async def stream_task(
    task_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    store = _get_task_store(request)
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["owner_agent_id"] != current_user["handle"]:
        raise HTTPException(403, "Not your task")

    async def event_stream():
        last_len = 0
        while True:
            t = store.get(task_id)
            if not t:
                break
            log = t["progress_log"]
            if len(log) > last_len:
                for entry in log[last_len:]:
                    yield f"data: {json.dumps(entry)}\n\n"
                last_len = len(log)
            if t["status"] in ("completed", "failed", "cancelled"):
                yield f"data: {json.dumps({'type': 'done', 'status': t['status'], 'result': t['result_summary']})}\n\n"
                break
            await asyncio.sleep(2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    store = _get_task_store(request)
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["owner_agent_id"] != current_user["handle"]:
        raise HTTPException(403, "Not your task")

    runner = _get_task_runner(request)
    cancelled = runner.cancel(task_id)
    if not cancelled:
        store.update_status(task_id, "cancelled")
    return {"status": "cancelled"}
