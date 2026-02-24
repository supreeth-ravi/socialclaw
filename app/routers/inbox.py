"""Inbox REST API — conversations, messages, SSE processing, stop."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..auth import get_current_user
from ..config import DB_PATH
from ..services.interaction_context import reset_interaction_channel, set_interaction_channel

router = APIRouter()


class DeliverMessage(BaseModel):
    recipient: str
    sender_name: str
    sender_type: str = "system"
    message: str
    conversation_id: str = ""


class SendMessage(BaseModel):
    message: str


def _get_inbox(request: Request):
    return request.app.state.inbox_store


# ─── Conversations ───────────────────────────────────────────────

@router.get("/inbox/conversations")
async def list_conversations(request: Request, current_user: dict = Depends(get_current_user)):
    store = _get_inbox(request)
    return store.get_conversations(current_user["handle"])


@router.get("/inbox/conversations/{conv_id}/messages")
async def get_conversation_messages(
    conv_id: str, request: Request, current_user: dict = Depends(get_current_user)
):
    store = _get_inbox(request)
    # Mark messages as read
    store.mark_read_conversation(conv_id, current_user["handle"])
    return store.get_conversation_messages(conv_id, current_user["handle"])


@router.post("/inbox/conversations/{conv_id}/stop")
async def stop_conversation(
    conv_id: str, request: Request, current_user: dict = Depends(get_current_user)
):
    store = _get_inbox(request)
    store.stop_conversation(conv_id)
    return {"status": "stopped"}


@router.post("/inbox/conversations/{conv_id}/resume")
async def resume_conversation(
    conv_id: str, request: Request, current_user: dict = Depends(get_current_user)
):
    store = _get_inbox(request)
    store.resume_conversation(conv_id)
    return {"status": "active"}


@router.delete("/inbox/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str, request: Request, current_user: dict = Depends(get_current_user)
):
    store = _get_inbox(request)
    store.delete_conversation(conv_id)
    return {"status": "deleted"}


@router.delete("/inbox/conversations")
async def delete_all_conversations(
    request: Request, current_user: dict = Depends(get_current_user)
):
    store = _get_inbox(request)
    count = store.delete_all_conversations(current_user["handle"])
    return {"status": "deleted", "count": count}


@router.post("/inbox/conversations/{conv_id}/auto-respond")
async def toggle_auto_respond(
    conv_id: str, request: Request, current_user: dict = Depends(get_current_user)
):
    store = _get_inbox(request)
    currently = store.is_auto_respond(conv_id)
    store.set_auto_respond(conv_id, not currently)
    return {"auto_respond": not currently}


@router.post("/inbox/conversations/{conv_id}/send")
async def send_conversation_message(
    conv_id: str,
    body: SendMessage,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Send a manual message from the user into an existing conversation.

    Routes through ``route_local_message`` so the partner's agent will
    auto-respond.
    """
    store = _get_inbox(request)
    handle = current_user["handle"]

    # Find who the partner is in this conversation
    convos = store.get_conversations(handle)
    conv = next((c for c in convos if c["id"] == conv_id), None)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    partner = conv["partner"]

    from ..services.local_router import route_local_message

    result = await route_local_message(
        partner, body.message,
        sender=handle,
        conversation_id=conv_id,
    )
    return {"status": "sent", "detail": result}


# ─── Process a message (SSE stream with tool calls) ─────────────

@router.post("/inbox/{message_id}/process")
async def process_message(
    message_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Run the user's agent to respond to an inbox message. Streams events via SSE."""
    store = _get_inbox(request)
    agent_id = current_user["handle"]

    # Find the message
    all_msgs = store.get_all(agent_id)
    msg = next((m for m in all_msgs if m["id"] == message_id), None)
    if not msg:
        raise HTTPException(404, "Message not found")

    from ..services.agent_runner import get_or_create_runner
    from ..services.event_serializer import serialize_event
    from ..services.local_router import send_response_to_sender

    from google.adk.agents.run_config import RunConfig, StreamingMode
    from google.genai import types

    display_name = current_user.get("display_name") or agent_id
    runner = get_or_create_runner(
        request.app.state.runners, agent_id, DB_PATH, display_name
    )

    prompt = (
        f"You received a message from {msg['sender_name']}:\n\n"
        f'"{msg["message"]}"\n\n'
        "IMPORTANT RULES FOR THIS RESPONSE:\n"
        "1. You MUST provide a COMPLETE answer in this response. Do NOT say "
        "\"I'll get back to you\", \"I'm still gathering info\", or \"let me check "
        "and follow up\" — there is NO follow-up mechanism. This is your only chance to respond.\n"
        "2. Use your tools to look up information BEFORE responding:\n"
        "   - get_my_history to check past experiences\n"
        "   - search_contacts_by_tag or get_merchant_contacts to find relevant contacts\n"
        "   - google_search to look up current information online\n"
        "3. If someone asks for recommendations, check your history and give specific "
        "answers based on what you know. If you have no experience, say so honestly.\n"
        "4. Do NOT use send_message_to_contact to reply to "
        f"{msg['sender_name']} — your text response will be sent back automatically.\n"
        "5. If it's casual chat, just reply naturally like a friend.\n"
        "Be helpful, specific, and genuine."
    )

    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    run_config = RunConfig(streaming_mode=StreamingMode.SSE)
    session_id = f"inbox_{msg.get('conversation_id', '')}_{agent_id}"

    # Enable auto-respond for this conversation on first approval
    conv_id = msg.get("conversation_id", "")
    if conv_id:
        store.set_auto_respond(conv_id, True)

    async def event_stream():
        collected_text = []
        processing_log = []
        token = set_interaction_channel("inbox")
        try:
            async for event in runner.runner.run_async(
                user_id=agent_id,
                session_id=session_id,
                new_message=content,
                run_config=run_config,
            ):
                for payload in serialize_event(event):
                    # Stream every event to the UI
                    yield f"data: {json.dumps(payload)}\n\n"

                    if payload["type"] == "text" and not payload.get("partial"):
                        collected_text.append(payload["content"])
                    elif payload["type"] in ("function_call", "function_response"):
                        processing_log.append(payload)
        finally:
            reset_interaction_channel(token)

        # Assemble the final response
        response_text = "\n".join(collected_text) if collected_text else "[No response generated]"

        # Save processing log
        store.update_processing_log(message_id, processing_log)
        store.mark_processed(message_id)

        # Route the response back to the sender
        conv_id = msg.get("conversation_id", "")
        if conv_id:
            await send_response_to_sender(
                    msg["sender_name"], agent_id, response_text,
                    conversation_id=conv_id,
                )

        yield f"data: {json.dumps({'type': 'done', 'response': response_text})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ─── Legacy / simple endpoints ───────────────────────────────────

@router.post("/inbox/deliver")
async def deliver_message(body: DeliverMessage, request: Request):
    """Internal endpoint for agents/simulation to send messages to a user."""
    store = _get_inbox(request)
    msg = store.deliver(
        recipient_id=body.recipient,
        sender_name=body.sender_name,
        sender_type=body.sender_type,
        message=body.message,
        conversation_id=body.conversation_id,
    )
    return msg


@router.get("/inbox")
async def list_inbox(request: Request, current_user: dict = Depends(get_current_user)):
    store = _get_inbox(request)
    return store.get_all(current_user["handle"])


@router.get("/inbox/unread-count")
async def unread_count(request: Request, current_user: dict = Depends(get_current_user)):
    store = _get_inbox(request)
    return {"count": store.unread_count(current_user["handle"])}
