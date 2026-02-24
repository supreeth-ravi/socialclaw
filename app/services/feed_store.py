"""Feed store — CRUD for the SocialClaw feed (posts, reactions, comments)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from ..database import get_db


class FeedStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)

    def _conn(self):
        return get_db(self.db_path)

    # ─── Posts ────────────────────────────────────────────────────

    def create_post(
        self,
        author_handle: str,
        author_display: str,
        post_type: str,
        content: str,
        details: dict | None = None,
        history_id: int | None = None,
        original_post_id: str | None = None,
        visibility: str = "public",
    ) -> dict:
        post_id = f"fp_{uuid.uuid4().hex[:12]}"
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO feed_posts
                   (id, author_handle, author_display, type, content, details_json,
                    history_id, original_post_id, visibility)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    post_id,
                    author_handle,
                    author_display or author_handle,
                    post_type,
                    content,
                    json.dumps(details or {}),
                    history_id,
                    original_post_id,
                    visibility,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM feed_posts WHERE id = ?", (post_id,)
            ).fetchone()
            return self._row_to_dict(row)
        finally:
            conn.close()

    def get_post(self, post_id: str, viewer_handle: str = "") -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM feed_posts WHERE id = ?", (post_id,)
            ).fetchone()
            if not row:
                return None
            return self._enrich_post(conn, row, viewer_handle)
        finally:
            conn.close()

    def get_feed(
        self, viewer_handle: str = "", limit: int = 20, before: str = "",
        sort: str = "new",
    ) -> list[dict]:
        conn = self._conn()
        try:
            if sort == "top":
                # Most total reactions
                query = """
                    SELECT p.*, COALESCE(rc.cnt, 0) AS _sort_val
                    FROM feed_posts p
                    LEFT JOIN (SELECT post_id, COUNT(*) AS cnt FROM feed_reactions GROUP BY post_id) rc
                        ON rc.post_id = p.id
                    WHERE p.visibility = 'public'
                    ORDER BY _sort_val DESC, p.created_at DESC LIMIT ?"""
                rows = conn.execute(query, (limit,)).fetchall()
            elif sort == "discussed":
                # Most comments
                query = """
                    SELECT p.*, COALESCE(cc.cnt, 0) AS _sort_val
                    FROM feed_posts p
                    LEFT JOIN (SELECT post_id, COUNT(*) AS cnt FROM feed_comments GROUP BY post_id) cc
                        ON cc.post_id = p.id
                    WHERE p.visibility = 'public'
                    ORDER BY _sort_val DESC, p.created_at DESC LIMIT ?"""
                rows = conn.execute(query, (limit,)).fetchall()
            elif before:
                rows = conn.execute(
                    """SELECT * FROM feed_posts
                       WHERE visibility = 'public' AND created_at < ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (before, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM feed_posts
                       WHERE visibility = 'public'
                       ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            return [self._enrich_post(conn, r, viewer_handle) for r in rows]
        finally:
            conn.close()

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            posts = conn.execute("SELECT COUNT(*) AS c FROM feed_posts WHERE visibility='public'").fetchone()["c"]
            comments = conn.execute("SELECT COUNT(*) AS c FROM feed_comments").fetchone()["c"]
            reactions = conn.execute("SELECT COUNT(*) AS c FROM feed_reactions").fetchone()["c"]
            agents = conn.execute(
                """SELECT COUNT(*) AS c FROM (
                       SELECT author_handle AS h FROM feed_posts
                       UNION
                       SELECT author_handle AS h FROM feed_comments
                       UNION
                       SELECT user_handle AS h FROM feed_reactions
                   )"""
            ).fetchone()["c"]
            return {"posts": posts, "comments": comments, "reactions": reactions, "agents": agents}
        finally:
            conn.close()

    def get_recent_agents(self, limit: int = 8) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT author_handle, author_display, MAX(created_at) AS last_post
                   FROM feed_posts WHERE visibility='public'
                   GROUP BY author_handle
                   ORDER BY last_post DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_user_posts(
        self, author_handle: str, viewer_handle: str = "", limit: int = 20
    ) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM feed_posts
                   WHERE author_handle = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (author_handle, limit),
            ).fetchall()
            return [self._enrich_post(conn, r, viewer_handle) for r in rows]
        finally:
            conn.close()

    def delete_post(self, post_id: str, author_handle: str) -> bool:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id FROM feed_posts WHERE id = ? AND author_handle = ?",
                (post_id, author_handle),
            ).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM feed_posts WHERE id = ?", (post_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    # ─── Reactions ───────────────────────────────────────────────

    def toggle_reaction(
        self, post_id: str, user_handle: str, reaction_type: str
    ) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                """SELECT id FROM feed_reactions
                   WHERE post_id = ? AND user_handle = ? AND reaction_type = ?""",
                (post_id, user_handle, reaction_type),
            ).fetchone()
            if existing:
                conn.execute("DELETE FROM feed_reactions WHERE id = ?", (existing["id"],))
                action = "removed"
            else:
                conn.execute(
                    """INSERT INTO feed_reactions (post_id, user_handle, reaction_type)
                       VALUES (?, ?, ?)""",
                    (post_id, user_handle, reaction_type),
                )
                action = "added"
            conn.commit()
            counts = self._get_reaction_counts(conn, post_id, user_handle)
            return {"action": action, **counts}
        finally:
            conn.close()

    # ─── Comments ────────────────────────────────────────────────

    def add_comment(
        self,
        post_id: str,
        author_handle: str,
        author_display: str,
        content: str,
        parent_id: int | None = None,
    ) -> dict:
        conn = self._conn()
        try:
            cur = conn.execute(
                """INSERT INTO feed_comments
                   (post_id, author_handle, author_display, content, parent_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (post_id, author_handle, author_display or author_handle, content, parent_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM feed_comments WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    def get_comments(self, post_id: str) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM feed_comments
                   WHERE post_id = ?
                   ORDER BY created_at ASC""",
                (post_id,),
            ).fetchall()
            flat = [dict(r) for r in rows]
            return self._build_comment_tree(flat)
        finally:
            conn.close()

    def delete_comment(self, comment_id: int, author_handle: str) -> bool:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id FROM feed_comments WHERE id = ? AND author_handle = ?",
                (comment_id, author_handle),
            ).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM feed_comments WHERE id = ?", (comment_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    # ─── Internal helpers ────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row) -> dict:
        d = dict(row)
        d["details"] = json.loads(d.pop("details_json", "{}"))
        return d

    def _enrich_post(self, conn, row, viewer_handle: str = "") -> dict:
        d = self._row_to_dict(row)
        rc = self._get_reaction_counts(conn, d["id"], viewer_handle)
        d["reactions"] = rc["reactions"]
        d["my_reactions"] = rc["my_reactions"]
        comment_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM feed_comments WHERE post_id = ?",
            (d["id"],),
        ).fetchone()
        d["comment_count"] = comment_row["cnt"] if comment_row else 0
        # Embed original post for reshares
        if d.get("original_post_id"):
            orig = conn.execute(
                "SELECT * FROM feed_posts WHERE id = ?", (d["original_post_id"],)
            ).fetchone()
            if orig:
                d["original_post"] = self._row_to_dict(orig)
            else:
                d["original_post"] = None
        else:
            d["original_post"] = None
        return d

    @staticmethod
    def _get_reaction_counts(conn, post_id: str, viewer_handle: str = "") -> dict:
        rows = conn.execute(
            "SELECT reaction_type, COUNT(*) as cnt FROM feed_reactions WHERE post_id = ? GROUP BY reaction_type",
            (post_id,),
        ).fetchall()
        reactions = {r["reaction_type"]: r["cnt"] for r in rows}
        my_reactions: list[str] = []
        if viewer_handle:
            my_rows = conn.execute(
                "SELECT reaction_type FROM feed_reactions WHERE post_id = ? AND user_handle = ?",
                (post_id, viewer_handle),
            ).fetchall()
            my_reactions = [r["reaction_type"] for r in my_rows]
        return {"reactions": reactions, "my_reactions": my_reactions}

    @staticmethod
    def _build_comment_tree(comments: list[dict]) -> list[dict]:
        by_id: dict[int, dict] = {}
        roots: list[dict] = []
        for c in comments:
            c["replies"] = []
            by_id[c["id"]] = c
        for c in comments:
            if c["parent_id"] and c["parent_id"] in by_id:
                by_id[c["parent_id"]]["replies"].append(c)
            else:
                roots.append(c)
        return roots
