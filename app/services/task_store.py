"""CRUD operations for the ``tasks`` table."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..database import get_db


class TaskStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path

    def _conn(self):
        return get_db(self.db_path)

    def create(self, owner_agent_id: str, intent: str, session_id: str = "") -> dict:
        task_id = uuid.uuid4().hex[:12]
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO tasks (id, owner_agent_id, intent, status, session_id)
                   VALUES (?, ?, ?, 'pending', ?)""",
                (task_id, owner_agent_id, intent, session_id),
            )
            conn.commit()
            return self.get(task_id)
        finally:
            conn.close()

    def get(self, task_id: str) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def list_by_owner(self, owner_agent_id: str) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_agent_id = ? ORDER BY created_at DESC",
                (owner_agent_id,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def update_status(self, task_id: str, status: str, **extra) -> None:
        conn = self._conn()
        try:
            sets = ["status = ?", "updated_at = datetime('now')"]
            vals: list = [status]
            if status in ("completed", "failed"):
                sets.append("completed_at = datetime('now')")
            for key in ("phase", "result_summary"):
                if key in extra:
                    sets.append(f"{key} = ?")
                    vals.append(extra[key])
            vals.append(task_id)
            conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
        finally:
            conn.close()

    def append_progress(self, task_id: str, entry: str) -> None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT progress_log FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return
            log = json.loads(row["progress_log"] or "[]")
            log.append({"ts": datetime.now(timezone.utc).isoformat(), "msg": entry})
            conn.execute(
                "UPDATE tasks SET progress_log = ?, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(log), task_id),
            )
            conn.commit()
        finally:
            conn.close()

    def list_pending(self) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = 'pending' ORDER BY created_at"
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row) -> dict:
        d = dict(row)
        d["progress_log"] = json.loads(d.get("progress_log") or "[]")
        return d
