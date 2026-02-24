"""SQLite-backed contact registry — same interface as common.contacts.ContactRegistry."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import httpx

from common.models import Contact

from ..database import get_db
from ..config import PUBLIC_BASE_URL


class SqliteContactRegistry:
    """Drop-in replacement for ``common.contacts.ContactRegistry`` using SQLite."""

    def __init__(self, db_path: str | Path, owner_agent_id: str) -> None:
        self.db_path = str(db_path)
        self.owner = owner_agent_id

    def _conn(self) -> sqlite3.Connection:
        return get_db(self.db_path)

    @staticmethod
    def _row_to_contact(row: sqlite3.Row) -> Contact:
        status = (row["status"] or "").strip().lower()
        # Contact model supports only these states; keep pending-request
        # rows readable in registry methods by mapping to unknown.
        if status not in {"active", "unreachable", "unknown"}:
            status = "unknown"
        return Contact(
            name=row["name"],
            type=row["type"],
            agent_card_url=row["agent_card_url"],
            description=row["description"],
            tags=json.loads(row["tags"]),
            status=status,
        )

    def all(self) -> list[Contact]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM contacts WHERE owner_agent_id = ? ORDER BY name",
                (self.owner,),
            ).fetchall()
            return [self._row_to_contact(r) for r in rows]
        finally:
            conn.close()

    def find(self, name: str) -> Contact | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM contacts WHERE owner_agent_id = ? AND name = ? COLLATE NOCASE",
                (self.owner, name),
            ).fetchone()
            return self._row_to_contact(row) if row else None
        finally:
            conn.close()

    def find_by_tag(self, tag: str) -> list[Contact]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM contacts
                   WHERE owner_agent_id = ?
                     AND EXISTS (
                       SELECT 1 FROM json_each(tags)
                       WHERE LOWER(json_each.value) = LOWER(?)
                     )
                   ORDER BY name""",
                (self.owner, tag),
            ).fetchall()
            return [self._row_to_contact(r) for r in rows]
        finally:
            conn.close()

    def find_by_type(self, contact_type: str) -> list[Contact]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM contacts WHERE owner_agent_id = ? AND type = ? ORDER BY name",
                (self.owner, contact_type),
            ).fetchall()
            return [self._row_to_contact(r) for r in rows]
        finally:
            conn.close()

    def add(self, contact: Contact) -> str:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO contacts (owner_agent_id, name, type, agent_card_url, description, tags, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.owner,
                    contact.name,
                    contact.type,
                    contact.agent_card_url,
                    contact.description,
                    json.dumps(contact.tags),
                    contact.status,
                ),
            )
            conn.commit()
            return f"Added '{contact.name}' to contacts."
        except sqlite3.IntegrityError:
            return f"Contact '{contact.name}' already exists. Use update instead."
        finally:
            conn.close()

    def remove(self, name: str) -> str:
        conn = self._conn()
        try:
            cur = conn.execute(
                "DELETE FROM contacts WHERE owner_agent_id = ? AND name = ? COLLATE NOCASE",
                (self.owner, name),
            )
            conn.commit()
            if cur.rowcount == 0:
                return f"Contact '{name}' not found."
            return f"Removed '{name}' from contacts."
        finally:
            conn.close()

    def update(self, name: str, **fields) -> str:
        contact = self.find(name)
        if not contact:
            return f"Contact '{name}' not found."
        for key, value in fields.items():
            if hasattr(contact, key):
                setattr(contact, key, value)
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE contacts SET type=?, agent_card_url=?, description=?, tags=?, status=?
                   WHERE owner_agent_id = ? AND name = ? COLLATE NOCASE""",
                (
                    contact.type,
                    contact.agent_card_url,
                    contact.description,
                    json.dumps(contact.tags),
                    contact.status,
                    self.owner,
                    name,
                ),
            )
            conn.commit()
            return f"Updated '{name}'."
        finally:
            conn.close()

    async def ping(self, name: str) -> str:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM contacts WHERE owner_agent_id = ? AND name = ? COLLATE NOCASE",
                (self.owner, name),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return f"Contact '{name}' not found."
        if (row["status"] or "").strip().lower() == "pending":
            return f"{name} is pending approval; skipping ping."
        contact = self._row_to_contact(row)
        url = (contact.agent_card_url or "").strip()
        if url.startswith("platform://user/"):
            handle = url.replace("platform://user/", "").strip("/")
            url = f"{PUBLIC_BASE_URL}/a2a/{handle}/.well-known/agent-card.json"
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={"ngrok-skip-browser-warning": "true"},
                )
                if resp.status_code == 200:
                    self.update(name, status="active")
                    return f"{name} is active and reachable."
                else:
                    self.update(name, status="unreachable")
                    return f"{name} returned status {resp.status_code}."
        except Exception as e:
            self.update(name, status="unreachable")
            return f"{name} is unreachable: {e}"
