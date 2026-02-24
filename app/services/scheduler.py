"""Scheduler service — polls for due scheduled tasks and submits them."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..database import get_db
from .task_runner import BackgroundTaskRunner

logger = logging.getLogger(__name__)


class SchedulerService:
    """Polls every 30s for due tasks and submits them to BackgroundTaskRunner."""

    def __init__(self, task_runner: BackgroundTaskRunner, db_path: str | Path) -> None:
        self.task_runner = task_runner
        self.db_path = db_path
        self._poll_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("SchedulerService started")

    async def stop(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("SchedulerService stopped")

    async def _poll_loop(self) -> None:
        while True:
            try:
                await self._check_due_tasks()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Scheduler poll error")
            await asyncio.sleep(30)

    async def _check_due_tasks(self) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM scheduled_tasks WHERE status = 'active' AND trigger_at <= ?",
                (now,),
            ).fetchall()
        finally:
            conn.close()

        for row in rows:
            row = dict(row)
            sched_id = row["id"]
            owner = row["owner_agent_id"]
            intent = row["intent"]
            recurrence = row["recurrence"]

            logger.info("Firing scheduled task %s for %s: %s", sched_id, owner, intent)

            # Create a background task
            from .task_store import TaskStore
            store = TaskStore(self.db_path)
            task = store.create(owner, intent)
            self.task_runner.submit(task["id"], owner, intent)

            # Update the scheduled task
            conn = get_db(self.db_path)
            try:
                if recurrence == "once":
                    conn.execute(
                        "UPDATE scheduled_tasks SET status = 'completed', last_run_at = ?, task_id = ? WHERE id = ?",
                        (now, task["id"], sched_id),
                    )
                else:
                    next_trigger = self._advance_trigger(row["trigger_at"], recurrence)
                    conn.execute(
                        "UPDATE scheduled_tasks SET trigger_at = ?, last_run_at = ?, task_id = ? WHERE id = ?",
                        (next_trigger, now, task["id"], sched_id),
                    )
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _advance_trigger(current: str, recurrence: str) -> str:
        try:
            dt = datetime.fromisoformat(current)
        except ValueError:
            dt = datetime.now(timezone.utc)
        deltas = {
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "monthly": timedelta(days=30),
        }
        dt += deltas.get(recurrence, timedelta(days=1))
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    # ─── Static helper for agent tool ────────────────────────────

    @staticmethod
    def create_schedule_static(
        db_path: str | Path,
        owner_agent_id: str,
        intent: str,
        trigger_at: str,
        recurrence: str = "once",
    ) -> str:
        sched_id = uuid.uuid4().hex[:12]
        conn = get_db(db_path)
        try:
            conn.execute(
                """INSERT INTO scheduled_tasks (id, owner_agent_id, intent, trigger_at, recurrence)
                   VALUES (?, ?, ?, ?, ?)""",
                (sched_id, owner_agent_id, intent, trigger_at, recurrence),
            )
            conn.commit()
            return sched_id
        finally:
            conn.close()
