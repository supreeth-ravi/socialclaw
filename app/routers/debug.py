"""Debug/simulation endpoints (disabled unless DEBUG_SIMULATION=1)."""

from __future__ import annotations

import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth import get_current_user
from ..config import DB_PATH, PUBLIC_BASE_URL
from ..database import get_db
from ..services.local_router import route_local_message
from ..services.inbox import InboxStore
from common.a2a_client import message_agent

router = APIRouter(prefix="/debug")


class LocalRouteRequest(BaseModel):
    sender: str
    target: str
    message: str
    conversation_id: str | None = None


def _require_debug():
    if os.getenv("DEBUG_SIMULATION", "0") != "1":
        raise HTTPException(status_code=403, detail="Debug simulation disabled")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug or "friend"


def _resolve_agent_card_url(url: str) -> str:
    raw = (url or "").strip()
    if raw.startswith("platform://user/"):
        handle = raw.replace("platform://user/", "").strip("/")
        return f"{PUBLIC_BASE_URL}/a2a/{handle}/.well-known/agent-card.json"
    return raw


@router.post("/route-local")
async def debug_route_local(body: LocalRouteRequest, current_user: dict = Depends(get_current_user)):
    _require_debug()
    sender = (body.sender or "").strip().lower()
    target = (body.target or "").strip().lower()
    if not sender:
        raise HTTPException(status_code=400, detail="Sender handle is required")

    conn = get_db()
    try:
        sender_row = conn.execute("SELECT 1 FROM users WHERE handle = ?", (sender,)).fetchone()
        target_row = conn.execute("SELECT 1 FROM users WHERE handle = ?", (target,)).fetchone()
    finally:
        conn.close()

    if not sender_row:
        raise HTTPException(status_code=400, detail="Sender handle must be an existing platform user")
    if not target_row:
        raise HTTPException(status_code=404, detail="Target handle not found")

    # Allow simulation between platform users.
    return {
        "status": await route_local_message(
            target,
            body.message,
            sender=sender,
            conversation_id=body.conversation_id,
        )
    }


@router.post("/run-social-pulse")
async def debug_run_social_pulse(request: Request, current_user: dict = Depends(get_current_user)):
    _require_debug()
    handle = current_user["handle"]
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT social_pulse_enabled FROM users WHERE handle = ?",
            (handle,),
        ).fetchone()
    finally:
        conn.close()
    if not row or not bool(row["social_pulse_enabled"]):
        raise HTTPException(status_code=400, detail="Social pulse is disabled for this user")

    intent = (
        "Social pulse: check in with 1-3 friends or colleagues, "
        "share a short update or ask how they are doing, and log a brief summary."
    )
    task_store = request.app.state.task_store
    task_runner = request.app.state.task_runner
    task = task_store.create(handle, intent)
    task_runner.submit(task["id"], handle, intent)
    return {"status": "submitted", "task_id": task["id"]}


@router.post("/simulate/friends")
async def debug_simulate_friends(current_user: dict = Depends(get_current_user)):
    """Run one simulation: this agent talks to all active personal contacts."""
    _require_debug()
    owner = current_user["handle"]

    conn = get_db()
    try:
        user_row = conn.execute(
            "SELECT a2a_max_turns FROM users WHERE handle = ?",
            (owner,),
        ).fetchone()
        contacts = conn.execute(
            """SELECT name, agent_card_url
               FROM contacts
               WHERE owner_agent_id = ?
                 AND type = 'personal'
                 AND status = 'active'
                 AND COALESCE(agent_card_url, '') <> ''
               ORDER BY name""",
            (owner,),
        ).fetchall()
        turn_limit = int(user_row["a2a_max_turns"]) if user_row and user_row["a2a_max_turns"] else 3
        turn_limit = max(1, min(10, turn_limit))
    finally:
        conn.close()

    if not contacts:
        return {"status": "ok", "count": 0, "turn_limit": turn_limit, "threads": []}

    sender_card = f"{PUBLIC_BASE_URL}/a2a/{owner}/.well-known/agent-card.json"
    inbox = InboxStore(DB_PATH)
    threads: list[dict] = []

    for row in contacts:
        contact = dict(row)
        contact_name = (contact.get("name") or "").strip() or "Friend"
        target_card_url = _resolve_agent_card_url(contact.get("agent_card_url") or "")
        if not target_card_url:
            continue

        conversation_id = f"sim-{owner}-friend-{_slug(contact_name)}"
        inbox.ensure_conversation(conversation_id, owner, contact_name)
        last_response = ""
        error = None
        turns_executed = 0

        for turn in range(1, turn_limit + 1):
            turns_executed = turn
            if turn == 1:
                outbound_text = (
                    f"Hey {contact_name}, this is {owner}. Starting our autonomous check-in thread. "
                    "Share one update and one recommendation."
                )
            else:
                summarized = (last_response or "").replace("\n", " ").strip()
                if len(summarized) > 300:
                    summarized = summarized[:300].rstrip() + "..."
                outbound_text = (
                    f"Turn {turn}/{turn_limit}. Continuing the same thread."
                    + (f" Your previous reply: {summarized}" if summarized else "")
                    + " Give one concise follow-up."
                )

            inbox.deliver(
                conversation_id=conversation_id,
                recipient_id=owner,
                sender_name=owner,
                sender_type="friend",
                message=outbound_text,
                direction="outbound",
            )
            last_response = await message_agent(
                target_card_url,
                outbound_text,
                sender_name=owner,
                sender_agent_card_url=sender_card,
                sender_type="personal",
                conversation_id=conversation_id,
            )
            inbox.deliver(
                conversation_id=conversation_id,
                recipient_id=owner,
                sender_name=contact_name,
                sender_type="friend",
                message=last_response,
                direction="inbound",
            )
            if (last_response or "").startswith("[Error contacting agent"):
                error = last_response
                break

        threads.append(
            {
                "contact_name": contact_name,
                "conversation_id": conversation_id,
                "turns_executed": turns_executed,
                "last_response": last_response,
                "error": error,
            }
        )

    return {"status": "ok", "count": len(threads), "turn_limit": turn_limit, "threads": threads}
