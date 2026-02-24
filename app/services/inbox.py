"""Inbound message store with conversation threading."""

from __future__ import annotations

import json
from pathlib import Path

from ..database import get_db


class InboxStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path

    def _conn(self):
        return get_db(self.db_path)

    # ─── Conversations ───────────────────────────────────────────

    def ensure_conversation(self, conv_id: str, participant_a: str, participant_b: str) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT OR IGNORE INTO conversations (id, participant_a, participant_b)
                   VALUES (?, ?, ?)""",
                (conv_id, participant_a, participant_b),
            )
            conn.commit()
        finally:
            conn.close()

    def is_conversation_stopped(self, conv_id: str) -> bool:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT status FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            return row["status"] == "stopped" if row else False
        finally:
            conn.close()

    def stop_conversation(self, conv_id: str) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE conversations SET status = 'stopped' WHERE id = ?", (conv_id,)
            )
            # Mark pending inbound messages as stopped
            conn.execute(
                "UPDATE inbound_messages SET status = 'stopped' WHERE conversation_id = ? AND status = 'unread'",
                (conv_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_conversation(self, conv_id: str) -> None:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM inbound_messages WHERE conversation_id = ?", (conv_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_all_conversations(self, user_handle: str) -> int:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id FROM conversations WHERE participant_a = ? OR participant_b = ?",
                (user_handle, user_handle),
            ).fetchall()
            count = 0
            for r in rows:
                conn.execute("DELETE FROM inbound_messages WHERE conversation_id = ?", (r["id"],))
                conn.execute("DELETE FROM conversations WHERE id = ?", (r["id"],))
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def resume_conversation(self, conv_id: str) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE conversations SET status = 'active' WHERE id = ?", (conv_id,)
            )
            conn.commit()
        finally:
            conn.close()

    def set_auto_respond(self, conv_id: str, enabled: bool) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE conversations SET auto_respond = ? WHERE id = ?",
                (1 if enabled else 0, conv_id),
            )
            conn.commit()
        finally:
            conn.close()

    def is_auto_respond(self, conv_id: str) -> bool:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT auto_respond FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            return bool(row["auto_respond"]) if row else False
        finally:
            conn.close()

    def get_conversations(self, user_handle: str) -> list[dict]:
        """Get all conversations for a user, with last message preview."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT c.*,
                      (SELECT COUNT(*) FROM inbound_messages m
                       WHERE m.conversation_id = c.id
                         AND m.recipient_id = ?
                         AND m.status = 'unread') as unread_count
                   FROM conversations c
                   WHERE c.participant_a = ? OR c.participant_b = ?
                   ORDER BY c.last_message_at DESC""",
                (user_handle, user_handle, user_handle),
            ).fetchall()
            convos = []
            for r in rows:
                d = dict(r)
                # Determine the "other" participant
                d["partner"] = d["participant_b"] if d["participant_a"] == user_handle else d["participant_a"]
                # Get last message visible to this user
                last = conn.execute(
                    """SELECT message, sender_name, direction, created_at
                       FROM inbound_messages
                       WHERE conversation_id = ? AND recipient_id = ?
                       ORDER BY created_at DESC LIMIT 1""",
                    (d["id"], user_handle),
                ).fetchone()
                d["last_message"] = dict(last) if last else None
                convos.append(d)
            return convos
        finally:
            conn.close()

    def get_conversation_messages(self, conv_id: str, user_handle: str) -> list[dict]:
        """Get all messages in a conversation visible to user_handle.

        Each message is stored per-recipient: inbound messages addressed to
        this user plus outbound messages sent by this user (also stored with
        recipient_id = this user).  This prevents showing the copy delivered
        to the other participant.
        """
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM inbound_messages
                   WHERE conversation_id = ? AND recipient_id = ?
                   ORDER BY created_at ASC""",
                (conv_id, user_handle),
            ).fetchall()
            messages = []
            for r in rows:
                d = dict(r)
                d["processing_log"] = json.loads(d.get("processing_log") or "[]")
                d["is_from_me"] = d["direction"] == "outbound"
                messages.append(d)
            return messages
        finally:
            conn.close()

    # ─── Message delivery ────────────────────────────────────────

    @staticmethod
    def _normalize_sender_type(sender_type: str) -> str:
        normalized = (sender_type or "").strip().lower()
        # A2A callers use "personal"; DB uses "friend".
        if normalized in ("personal", "user", "human", "contact"):
            return "friend"
        if normalized in ("friend", "merchant", "system"):
            return normalized
        return "system"

    def deliver(
        self,
        recipient_id: str,
        sender_name: str,
        sender_type: str = "system",
        message: str = "",
        conversation_id: str = "",
        direction: str = "inbound",
    ) -> dict:
        sender_type = self._normalize_sender_type(sender_type)
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO inbound_messages
                   (conversation_id, recipient_id, sender_name, sender_type, direction, message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (conversation_id, recipient_id, sender_name, sender_type, direction, message),
            )
            # Update conversation timestamp
            if conversation_id:
                conn.execute(
                    "UPDATE conversations SET last_message_at = datetime('now') WHERE id = ?",
                    (conversation_id,),
                )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM inbound_messages WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    # ─── Status helpers ──────────────────────────────────────────

    def get_unread(self, recipient_id: str) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM inbound_messages WHERE recipient_id = ? AND status = 'unread' ORDER BY created_at",
                (recipient_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_all(self, recipient_id: str) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM inbound_messages WHERE recipient_id = ? ORDER BY created_at DESC LIMIT 50",
                (recipient_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def unread_count(self, recipient_id: str) -> int:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM inbound_messages WHERE recipient_id = ? AND status = 'unread'",
                (recipient_id,),
            ).fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def mark_read(self, message_id: int) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE inbound_messages SET status = 'read' WHERE id = ? AND status = 'unread'",
                (message_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_read_conversation(self, conv_id: str, user_handle: str) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE inbound_messages SET status = 'read' WHERE conversation_id = ? AND recipient_id = ? AND status = 'unread'",
                (conv_id, user_handle),
            )
            conn.commit()
        finally:
            conn.close()

    def update_processing_log(self, message_id: int, log: list) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE inbound_messages SET processing_log = ? WHERE id = ?",
                (json.dumps(log), message_id),
            )
            conn.commit()
        finally:
            conn.close()

    def count_recent_messages(self, conv_id: str, limit_minutes: int = 10) -> int:
        """Count messages in a conversation within the last N minutes."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM inbound_messages
                   WHERE conversation_id = ?
                     AND created_at > datetime('now', '-' || ? || ' minutes')""",
                (conv_id, limit_minutes),
            ).fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def mark_processed(self, message_id: int) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE inbound_messages SET status = 'processed', processed_at = datetime('now') WHERE id = ?",
                (message_id,),
            )
            conn.commit()
        finally:
            conn.close()
