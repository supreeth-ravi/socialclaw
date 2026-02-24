"""CRUD endpoints for chat sessions."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user
from ..database import get_db
from ..models import MessageOut, SessionCreate, SessionOut

router = APIRouter()


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM chat_sessions WHERE agent_id = ? ORDER BY updated_at DESC",
            (agent_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/sessions", response_model=SessionOut)
async def create_session(body: SessionCreate, current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    session_id = str(uuid.uuid4())
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, agent_id, title) VALUES (?, ?, ?)",
            (session_id, agent_id, body.title),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row["agent_id"] != agent_id:
            raise HTTPException(status_code=403, detail="Not your session")
        session = dict(row)

        msgs = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        ).fetchall()
        session["messages"] = [dict(m) for m in msgs]
        return session
    finally:
        conn.close()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        row = conn.execute("SELECT agent_id FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row["agent_id"] != agent_id:
            raise HTTPException(status_code=403, detail="Not your session")
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
