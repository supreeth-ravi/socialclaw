"""Schedule REST API — create, list, cancel scheduled tasks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import get_current_user
from ..config import DB_PATH
from ..database import get_db
from ..models import ScheduleCreate, ScheduleOut
from ..services.scheduler import SchedulerService

router = APIRouter()


@router.post("/schedule", response_model=ScheduleOut)
async def create_schedule(
    body: ScheduleCreate,
    current_user: dict = Depends(get_current_user),
):
    agent_id = current_user["handle"]
    sched_id = SchedulerService.create_schedule_static(
        DB_PATH, agent_id, body.intent, body.trigger_at, body.recurrence
    )
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (sched_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.get("/schedule")
async def list_schedules(current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM scheduled_tasks WHERE owner_agent_id = ? ORDER BY created_at DESC",
            (agent_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.delete("/schedule/{schedule_id}")
async def cancel_schedule(schedule_id: str, current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (schedule_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Schedule not found")
        if row["owner_agent_id"] != agent_id:
            raise HTTPException(403, "Not your schedule")
        conn.execute(
            "UPDATE scheduled_tasks SET status = 'cancelled' WHERE id = ?",
            (schedule_id,),
        )
        conn.commit()
        return {"status": "cancelled"}
    finally:
        conn.close()
