"""A2A JSON-RPC endpoint for external agents to talk to platform users."""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from a2a.client.helpers import create_text_message_object

from ..config import DB_PATH, PUBLIC_BASE_URL, A2A_MAX_TURNS
from ..database import get_db
from ..services.db_contacts import SqliteContactRegistry
from common.models import Contact
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


def _conv_id(recipient: str, sender: str, url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"conv_ext_{recipient.lower()}_{sender.lower()}_{digest}"


def _extract_text(message: dict) -> str:
    parts = message.get("parts", []) if isinstance(message, dict) else []
    texts = []
    for p in parts:
        if isinstance(p, dict) and "text" in p:
            texts.append(p["text"])
    return "\n".join(texts).strip()


def _internal_handle_from_sender_url(sender_url: str) -> str | None:
    raw = (sender_url or "").strip()
    if not raw:
        return None
    if raw.startswith("platform://user/"):
        handle = raw.replace("platform://user/", "").strip("/")
        return handle or None
    prefix = f"{PUBLIC_BASE_URL}/a2a/"
    suffix = "/.well-known/agent-card.json"
    if raw.startswith(prefix) and raw.endswith(suffix):
        handle = raw[len(prefix):-len(suffix)].strip("/")
        return handle or None
    return None


@router.get("/{handle}/.well-known/agent-card.json")
async def get_agent_card(handle: str):
    handle = handle.strip().lower()
    return {
        "name": f"{handle}_personal_agent",
        "description": f"Personal agent for @{handle} on AI Social.",
        "url": f"{PUBLIC_BASE_URL}/a2a/{handle}/rpc",
        "supportedInterfaces": [
            {"url": f"{PUBLIC_BASE_URL}/a2a/{handle}/rpc", "protocolBinding": "JSONRPC", "protocolVersion": "0.3"},
        ],
        "provider": {"organization": "AI Social", "url": "https://ai.social"},
        "version": "0.1.0",
        "capabilities": {"streaming": False, "pushNotifications": False, "extendedAgentCard": False},
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["application/json", "text/plain"],
        "skills": [],
    }


@router.post("/{handle}/rpc")
async def rpc(handle: str, request: Request):
    handle = handle.strip().lower()
    payload = await request.json()
    if payload.get("method") != "message/send":
        raise HTTPException(400, "Unsupported method")

    req_id = payload.get("id")
    params: dict[str, Any] = payload.get("params", {}) or {}
    msg = params.get("message") or {}
    text = _extract_text(msg)
    if not text:
        raise HTTPException(400, "Empty message")

    sender_name = params.get("sender_name") or "External Agent"
    sender_url = params.get("sender_agent_card_url") or params.get("agent_card_url") or ""
    sender_type = params.get("sender_type") or "personal"
    conversation_id = params.get("conversation_id") or ""

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT handle, auto_inbox_enabled, a2a_max_turns FROM users WHERE handle = ?",
            (handle,),
        ).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Recipient not found")
    finally:
        conn.close()

    max_turns = max(1, min(10, int((user["a2a_max_turns"] if user else None) or A2A_MAX_TURNS)))

    inbox: InboxStore = request.app.state.inbox_store
    registry = SqliteContactRegistry(DB_PATH, handle)

    sender_internal_handle = _internal_handle_from_sender_url(sender_url)
    status = "pending" if not sender_url else "active"
    if sender_url:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM contacts WHERE owner_agent_id = ? AND agent_card_url = ?",
                (handle, sender_url),
            ).fetchone()
        finally:
            conn.close()

        if not row:
            registry.add(
                Contact(
                    name=sender_name,
                    type="personal" if sender_internal_handle else ("merchant" if sender_type == "merchant" else "personal"),
                    agent_card_url=sender_url,
                    description="External agent",
                    tags=["external"],
                )
            )
            conn = get_db()
            try:
                # Internal platform users should be active immediately.
                new_status = "active" if sender_internal_handle else "pending"
                conn.execute(
                    "UPDATE contacts SET status = ? WHERE owner_agent_id = ? AND agent_card_url = ?",
                    (new_status, handle, sender_url),
                )
                conn.commit()
            finally:
                conn.close()
            status = new_status
        else:
            status = row["status"]
            if sender_internal_handle and status != "active":
                conn = get_db()
                try:
                    conn.execute(
                        "UPDATE contacts SET status = 'active' WHERE owner_agent_id = ? AND agent_card_url = ?",
                        (handle, sender_url),
                    )
                    conn.commit()
                    status = "active"
                finally:
                    conn.close()

    conv_id = conversation_id or _conv_id(handle, sender_name, sender_url or sender_name)
    inbox.ensure_conversation(conv_id, handle, sender_name)
    inbox.deliver(
        conversation_id=conv_id,
        recipient_id=handle,
        sender_name=sender_name,
        sender_type=sender_type,
        message=text,
        direction="inbound",
    )

    # For platform-to-platform A2A, always produce a direct response in RPC.
    # Auto-inbox toggle still applies to unknown/external senders.
    should_auto_respond = status == "active" and (
        bool(user["auto_inbox_enabled"]) or sender_internal_handle is not None
    )

    if not should_auto_respond:
        ack = create_text_message_object(role="agent", content="Message received.")
        return {"jsonrpc": "2.0", "id": req_id, "result": ack.model_dump()}

    # Auto-respond via agent
    runner = get_or_create_runner(request.app.state.runners, handle, DB_PATH, handle)
    prompt = (
        f"You received an incoming message from {sender_name}:\n\n"
        f'"{text}"\n\n'
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
    # Allow bounded multi-turn A2A follow-up in the same inbox conversation.
    budget_token = set_a2a_turn_budget(max_turns)
    conv_token = set_a2a_conversation_id(conv_id)
    try:
        async for event in runner.runner.run_async(
            user_id=handle,
            session_id=f"inbox_ext_{conv_id}",
            new_message=content,
            run_config=run_config,
        ):
            for evt in serialize_event(event):
                if evt.get("type") == "text" and not evt.get("partial"):
                    collected.append(evt["content"])
    finally:
        reset_a2a_turn_budget(budget_token)
        reset_a2a_conversation_id(conv_token)
        reset_interaction_channel(token)

    response_text = "\n".join(collected) if collected else "[No response generated]"
    inbox.deliver(
        conversation_id=conv_id,
        recipient_id=handle,
        sender_name=handle,
        sender_type="friend",
        message=response_text,
        direction="outbound",
    )

    msg_obj = create_text_message_object(role="agent", content=response_text)
    return {"jsonrpc": "2.0", "id": req_id, "result": msg_obj.model_dump()}
