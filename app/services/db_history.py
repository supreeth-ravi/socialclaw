"""SQLite-backed history store — same interface as common.history.HistoryStore."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from common.models import HistoryEntry

from ..database import get_db


class SqliteHistoryStore:
    """Drop-in replacement for ``common.history.HistoryStore`` using SQLite."""

    def __init__(self, db_path: str | Path, owner_agent_id: str) -> None:
        self.db_path = str(db_path)
        self.owner = owner_agent_id

    def _conn(self) -> sqlite3.Connection:
        return get_db(self.db_path)

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> HistoryEntry:
        return HistoryEntry(
            timestamp=row["timestamp"],
            type=row["type"],
            summary=row["summary"],
            details=json.loads(row["details_json"]),
            contacts_involved=json.loads(row["contacts_involved"]),
            sentiment=row["sentiment"],
            visibility=row["visibility"] if "visibility" in row.keys() else "personal",
        )

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "type": row["type"],
            "summary": row["summary"],
            "details": json.loads(row["details_json"]),
            "contacts_involved": json.loads(row["contacts_involved"]),
            "sentiment": row["sentiment"],
            "visibility": row["visibility"] if "visibility" in row.keys() else "personal",
        }

    def all(self) -> list[HistoryEntry]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM history WHERE owner_agent_id = ? ORDER BY timestamp",
                (self.owner,),
            ).fetchall()
            return [self._row_to_entry(r) for r in rows]
        finally:
            conn.close()

    def all_with_id(self) -> list[dict]:
        """Return all entries as dicts including the DB ``id``."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM history WHERE owner_agent_id = ? ORDER BY timestamp DESC",
                (self.owner,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def search(self, query: str) -> list[HistoryEntry]:
        """Keyword search across summary and details."""
        entries = self.all()
        keywords = query.lower().split()
        results: list[HistoryEntry] = []
        for entry in entries:
            text = f"{entry.summary} {json.dumps(entry.details)}".lower()
            if any(kw in text for kw in keywords):
                results.append(entry)
        return results

    def search_with_id(self, query: str) -> list[dict]:
        """Keyword search returning dicts with id."""
        all_entries = self.all_with_id()
        keywords = query.lower().split()
        return [
            e for e in all_entries
            if any(kw in f"{e['summary']} {json.dumps(e['details'])}".lower() for kw in keywords)
        ]

    def get_by_id(self, entry_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM history WHERE id = ? AND owner_agent_id = ?",
                (entry_id, self.owner),
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def add(self, entry: HistoryEntry) -> None:
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO history (owner_agent_id, timestamp, type, summary, details_json, contacts_involved, sentiment, visibility)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.owner,
                    entry.timestamp,
                    entry.type,
                    entry.summary,
                    json.dumps(entry.details),
                    json.dumps(entry.contacts_involved),
                    entry.sentiment,
                    entry.visibility,
                ),
            )
            conn.commit()
            history_id = cur.lastrowid
        finally:
            conn.close()

        if getattr(entry, "visibility", "personal") == "sharable":
            self._auto_post_to_feed(history_id, entry)

    def _auto_post_to_feed(self, history_id: int, entry: HistoryEntry) -> None:
        from .feed_store import FeedStore

        conn = get_db(self.db_path)
        try:
            row = conn.execute(
                "SELECT display_name FROM users WHERE handle = ?", (self.owner,)
            ).fetchone()
            display = row["display_name"] if row else self.owner
        finally:
            conn.close()
        FeedStore(self.db_path).create_post(
            author_handle=self.owner,
            author_display=display,
            post_type=entry.type,
            content=entry.summary,
            details=entry.details,
            history_id=history_id,
            visibility="public",
        )

    def delete(self, entry_id: int) -> bool:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id FROM history WHERE id = ? AND owner_agent_id = ?",
                (entry_id, self.owner),
            ).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM history WHERE id = ?", (entry_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    def update(self, entry_id: int, **fields) -> bool:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id FROM history WHERE id = ? AND owner_agent_id = ?",
                (entry_id, self.owner),
            ).fetchone()
            if not row:
                return False
            sets = []
            vals = []
            for k, v in fields.items():
                if v is not None:
                    sets.append(f"{k} = ?")
                    vals.append(v)
            if not sets:
                return True
            vals.append(entry_id)
            conn.execute(f"UPDATE history SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
            return True
        finally:
            conn.close()
