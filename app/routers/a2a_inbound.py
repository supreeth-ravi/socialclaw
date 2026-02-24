"""Inbound A2A messages from external agents.

Creates a pending friend request if sender is unknown.
If approved + auto-inbox enabled, auto-responds via A2A.
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from common.a2a_client import fetch_agent_card, message_agent
from common.models import Contact

from ..config import DB_PATH, PUBLIC_BASE_URL, A2A_MAX_TURNS
from ..database import get_db
from ..services.db_contacts import SqliteContactRegistry
from ..services.inbox import InboxStore
from ..services.agent_runner import get_or_create_runner
from ..services.event_serializer import serialize_event
from ..services.interaction_context import (
    reset_interaction_channel,
    set_interaction_channel,
    set_a2a_turn_budget,
    reset_a2a_turn_budget,
    set_a2a_conversation_id,
    reset_a2a_conversation_id,
)

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types

router = APIRouter(prefix="/a2a")


class ExternalInbound(BaseModel):
    recipient_handle: str
    sender_name: str
    agent_card_url: str
    message: str
    sender_type: str = "personal"
    conversation_id: str | None = None


def _conv_id(recipient: str, sender: str, url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"conv_ext_{recipient.lower()}_{sender.lower()}_{digest}"


@router.post("/inbound")
async def inbound_a2a_message(body: ExternalInbound, request: Request):
    recipient = body.recipient_handle.strip().lower()
    sender_name = body.sender_name.strip() or "External Agent"
    url = body.agent_card_url.strip()

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT handle, auto_inbox_enabled, a2a_max_turns FROM users WHERE handle = ?",
            (recipient,),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Recipient not found")
    finally:
        conn.close()

    max_turns = max(1, min(10, int((user["a2a_max_turns"] if user else None) or A2A_MAX_TURNS)))

    registry = SqliteContactRegistry(DB_PATH, recipient)

    # Check if contact already exists by URL
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM contacts WHERE owner_agent_id = ? AND agent_card_url = ?",
            (recipient, url),
        ).fetchone()
    finally:
        conn.close()

    status = None
    if not row:
        # Try to fetch card for description
        desc = "External agent"
        try:
            card = await fetch_agent_card(url)
            desc = getattr(card, "description", None) or (card.get("description") if isinstance(card, dict) else desc)
        except Exception:
            pass
        contact = Contact(
            name=sender_name,
            type=body.sender_type,
            agent_card_url=url,
            description=desc or "External agent",
            tags=["external"],
        )
        registry.add(contact)
        # Mark as pending
        conn = get_db()
        try:
            conn.execute(
                "UPDATE contacts SET status = 'pending' WHERE owner_agent_id = ? AND agent_card_url = ?",
                (recipient, url),
            )
            conn.commit()
        finally:
            conn.close()
        status = "pending"
    else:
        status = row["status"]

    conv_id = body.conversation_id or _conv_id(recipient, sender_name, url)
    inbox = request.app.state.inbox_store
    inbox.ensure_conversation(conv_id, recipient, sender_name)
    inbox.deliver(
        conversation_id=conv_id,
        recipient_id=recipient,
        sender_name=sender_name,
        sender_type=body.sender_type,
        message=body.message,
        direction="inbound",
    )

    if status != "active" or not bool(user["auto_inbox_enabled"]):
        return {"status": "queued", "contact_status": status}

    # Auto-respond via A2A
    runner = get_or_create_runner(request.app.state.runners, recipient, DB_PATH, recipient)
    prompt = (
        f"You received an incoming message from {sender_name}:\n\n"
        f'"{body.message}"\n\n'
        "RESPOND DIRECTLY — just write your reply as text. Your response will be "
        f"sent back to {sender_name} automatically. Do NOT use send_message_to_contact "
        f"to reply to {sender_name} — that would create a loop.\n"
        "You MAY use other tools (get_my_history, search_contacts_by_tag, etc.) to "
        "look up information before responding. If this is casual conversation, just "
        "chat naturally like a friend. Do not create background tasks."
    )
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    run_config = RunConfig(streaming_mode=StreamingMode.SSE)

    collected = []
    token = set_interaction_channel("inbox")
    budget_token = set_a2a_turn_budget(max_turns)
    conv_token = set_a2a_conversation_id(conv_id)
    try:
        async for event in runner.runner.run_async(
            user_id=recipient,
            session_id=f"inbox_ext_{conv_id}",
            new_message=content,
            run_config=run_config,
        ):
            for payload in serialize_event(event):
                if payload.get("type") == "text" and not payload.get("partial"):
                    collected.append(payload["content"])
    finally:
        reset_a2a_turn_budget(budget_token)
        reset_a2a_conversation_id(conv_token)
        reset_interaction_channel(token)

    response_text = "\n".join(collected) if collected else "[No response generated]"
    inbox.deliver(
        conversation_id=conv_id,
        recipient_id=recipient,
        sender_name=recipient,
        sender_type="friend",
        message=response_text,
        direction="outbound",
    )
    # Send to external agent
    await message_agent(
        url,
        response_text,
        sender_name=recipient,
        sender_agent_card_url=f"{PUBLIC_BASE_URL}/a2a/{recipient}/.well-known/agent-card.json",
        sender_type="personal",
        conversation_id=conv_id,
    )

    return {"status": "responded"}
