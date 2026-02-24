"""POST /api/chat/stream — SSE endpoint for chat with the active agent."""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..auth import get_current_user
from ..config import DB_PATH
from ..database import get_db
from ..models import ChatRequest
from ..services.agent_runner import get_or_create_runner

router = APIRouter()


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest, current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    display_name = current_user["display_name"] or agent_id

    # Verify session ownership
    conn = get_db()
    try:
        row = conn.execute("SELECT agent_id FROM chat_sessions WHERE id = ?", (body.session_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if row["agent_id"] != agent_id:
            raise HTTPException(status_code=403, detail="Not your session")
    finally:
        conn.close()

    runner = get_or_create_runner(request.app.state.runners, agent_id, DB_PATH, display_name)

    # Persist the user message
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO chat_messages (session_id, role, author, content, metadata_json, timestamp)
               VALUES (?, 'user', 'user', ?, '{}', ?)""",
            (body.session_id, body.message, time.time()),
        )
        # Update session title from first message
        row = conn.execute(
            "SELECT title FROM chat_sessions WHERE id = ?", (body.session_id,)
        ).fetchone()
        if row and row["title"] == "New Chat":
            title = body.message[:50] + ("..." if len(body.message) > 50 else "")
            conn.execute(
                "UPDATE chat_sessions SET title = ?, updated_at = datetime('now') WHERE id = ?",
                (title, body.session_id),
            )
        conn.commit()
    finally:
        conn.close()

    async def event_generator():
        collected_text = []
        async for payload in runner.run_message(body.session_id, body.message, user_id=agent_id):
            yield f"data: {json.dumps(payload)}\n\n"

            # Persist agent messages
            if payload["type"] == "text" and not payload.get("partial"):
                collected_text.append(payload["content"])
            elif payload["type"] in ("function_call", "function_response"):
                conn2 = get_db()
                try:
                    conn2.execute(
                        """INSERT INTO chat_messages
                           (session_id, role, author, content, metadata_json, timestamp)
                           VALUES (?, 'assistant', ?, ?, ?, ?)""",
                        (
                            body.session_id,
                            payload.get("author", ""),
                            payload.get("name", ""),
                            json.dumps(payload),
                            time.time(),
                        ),
                    )
                    conn2.commit()
                finally:
                    conn2.close()

        # Persist final agent text
        if collected_text:
            full_text = "\n".join(collected_text)
            conn3 = get_db()
            try:
                conn3.execute(
                    """INSERT INTO chat_messages
                       (session_id, role, author, content, metadata_json, timestamp)
                       VALUES (?, 'assistant', ?, ?, '{}', ?)""",
                    (body.session_id, "agent", full_text, time.time()),
                )
                conn3.execute(
                    "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?",
                    (body.session_id,),
                )
                conn3.commit()
            finally:
                conn3.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
