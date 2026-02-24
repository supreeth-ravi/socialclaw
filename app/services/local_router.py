"""Local message router for platform:// URLs.

Routes messages between platform users.  Each message is stored twice:
one outbound copy for the sender and one inbound copy for the target.
The target's agent responds automatically, creating a continuous
back-and-forth conversation until the depth limit is reached or the
conversation is stopped.

Each new interaction creates a separate conversation thread so that
the inbox shows distinct conversations rather than one giant thread
per contact pair.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum auto-respond messages in a 10-minute window to prevent infinite loops
MAX_AUTO_MESSAGES = 20

# Limit concurrent auto-process tasks to avoid overwhelming the API
_auto_process_semaphore = asyncio.Semaphore(2)

# Max retries for transient network errors
_MAX_RETRIES = 3

# Module-level references, set by ``init_local_router``
_runners: dict | None = None
_db_path: Path | None = None
_inbox_store = None


def init_local_router(runners: dict, db_path: str | Path, inbox_store=None) -> None:
    """Store references to the shared runner pool, DB path, and inbox."""
    global _runners, _db_path, _inbox_store
    _runners = runners
    _db_path = Path(db_path)
    _inbox_store = inbox_store
    logger.info("Local router initialized")


def _new_conversation_id(a: str, b: str) -> str:
    """Generate a unique conversation ID for a pair of users."""
    pair = "_".join(sorted([a.lower(), b.lower()]))
    short_id = uuid.uuid4().hex[:8]
    return f"conv_{pair}_{short_id}"


async def route_local_message(
    target_handle: str,
    message: str,
    sender: str = "friend",
    conversation_id: str | None = None,
) -> str:
    """Deliver *message* from *sender* to *target_handle*.

    If *conversation_id* is provided, the message is added to that
    existing conversation (used for auto-respond replies).  Otherwise
    a new conversation thread is created.
    """
    if _inbox_store is None:
        return "[Local router not initialized — no inbox store]"

    # Use existing conversation or create a new one
    if conversation_id:
        conv_id = conversation_id
    else:
        conv_id = _new_conversation_id(sender, target_handle)

    # Ensure conversation record exists and is active
    _inbox_store.ensure_conversation(conv_id, sender, target_handle)

    # Resume stopped conversations — new messages always restart them
    if _inbox_store.is_conversation_stopped(conv_id):
        _inbox_store.resume_conversation(conv_id)
        logger.info("Auto-resumed stopped conversation %s", conv_id)

    # Save outbound copy for the sender's view
    _inbox_store.deliver(
        conversation_id=conv_id,
        recipient_id=sender,
        sender_name=sender,
        sender_type="friend",
        message=message,
        direction="outbound",
    )

    # Save inbound copy for the target
    delivered = _inbox_store.deliver(
        conversation_id=conv_id,
        recipient_id=target_handle,
        sender_name=sender,
        sender_type="friend",
        message=message,
        direction="inbound",
    )

    # Auto-process only if user opted in
    try:
        from app.database import get_db
        conn = get_db(_db_path)
        row = conn.execute(
            "SELECT auto_inbox_enabled FROM users WHERE handle = ?",
            (target_handle,),
        ).fetchone()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    auto_enabled = bool(row["auto_inbox_enabled"]) if row else False

    # Auto-process: run the target's agent to respond (within depth limit)
    recent = _inbox_store.count_recent_messages(conv_id, limit_minutes=10)
    if auto_enabled and recent < MAX_AUTO_MESSAGES:
        asyncio.create_task(_auto_process_message(delivered, target_handle))
        return (
            f"Message delivered to {target_handle}. "
            f"Their agent is responding automatically."
        )

    logger.info(
        "Auto-respond depth limit (%d) reached for conversation %s",
        MAX_AUTO_MESSAGES, conv_id,
    )
    return (
        f"Message delivered to {target_handle}'s inbox. "
        f"Awaiting manual response."
    )


async def _auto_process_message(msg: dict, agent_id: str) -> None:
    """Auto-process an inbox message without user interaction.

    Uses a semaphore to limit concurrent API calls and retries on
    transient network errors (DNS failures, connection resets).
    """
    async with _auto_process_semaphore:
        # Small stagger to avoid simultaneous API calls
        await asyncio.sleep(1)
        await _run_auto_process(msg, agent_id)


async def _run_auto_process(msg: dict, agent_id: str) -> None:
    """Inner logic for auto-processing with retry on transient errors."""
    import httpx

    from .agent_runner import get_or_create_runner
    from .event_serializer import serialize_event
    from .interaction_context import reset_interaction_channel, set_interaction_channel

    from google.adk.agents.run_config import RunConfig, StreamingMode
    from google.genai import types

    if _runners is None or _db_path is None or _inbox_store is None:
        return

    runner = get_or_create_runner(_runners, agent_id, _db_path, agent_id)

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
    # NONE mode: no long-lived streaming connection — more reliable for background work
    run_config = RunConfig(streaming_mode=StreamingMode.NONE)
    session_id = f"inbox_{msg.get('conversation_id', '')}_{agent_id}"

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            collected_text: list[str] = []
            processing_log: list[dict] = []

            token = set_interaction_channel("inbox")
            try:
                async for event in runner.runner.run_async(
                    user_id=agent_id,
                    session_id=session_id,
                    new_message=content,
                    run_config=run_config,
                ):
                    for payload in serialize_event(event):
                        if payload["type"] == "text" and not payload.get("partial"):
                            collected_text.append(payload["content"])
                        elif payload["type"] in ("function_call", "function_response"):
                            processing_log.append(payload)
            finally:
                reset_interaction_channel(token)

            response_text = "\n".join(collected_text) if collected_text else "[No response generated]"

            _inbox_store.update_processing_log(msg["id"], processing_log)
            _inbox_store.mark_processed(msg["id"])

            # Route the response back — this saves outbound for responder,
            # inbound for original sender, and may trigger the other side's
            # auto-respond for continuous conversation.
            conv_id = msg.get("conversation_id", "")
            if conv_id:
                await send_response_to_sender(
                    msg["sender_name"], agent_id, response_text,
                    conversation_id=conv_id,
                )

            logger.info("Auto-processed message %s for %s", msg["id"], agent_id)
            return  # Success — exit retry loop

        except (ConnectionError, OSError, TimeoutError, httpx.ConnectError, httpx.ReadError) as exc:
            last_error = exc
            wait = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(
                "Auto-process attempt %d/%d failed for %s (retrying in %ds): %s",
                attempt + 1, _MAX_RETRIES, agent_id, wait, exc,
            )
            await asyncio.sleep(wait)
        except Exception:
            logger.exception("Auto-process failed for message %s", msg.get("id"))
            return  # Non-transient error — don't retry

    logger.error(
        "Auto-process gave up after %d retries for message %s: %s",
        _MAX_RETRIES, msg.get("id"), last_error,
    )


async def send_response_to_sender(
    sender_handle: str,
    recipient_handle: str,
    response: str,
    conversation_id: str = "",
) -> None:
    """Route a response back to the original sender.

    Goes through ``route_local_message`` so the outbound/inbound copies
    are created correctly and auto_respond can trigger on the other side,
    enabling continuous back-and-forth conversations.

    The *conversation_id* keeps replies in the same thread.
    """
    await route_local_message(
        sender_handle, response,
        sender=recipient_handle,
        conversation_id=conversation_id,
    )


async def route_local_message_direct(
    target_handle: str,
    message: str,
    sender: str = "friend",
) -> str:
    """Directly run the target's agent without writing to inbox."""
    if _runners is None or _db_path is None:
        return "[Local router not initialized]"

    from .agent_runner import get_or_create_runner
    from .event_serializer import serialize_event

    from google.adk.agents.run_config import RunConfig, StreamingMode
    from google.genai import types

    runner = get_or_create_runner(_runners, target_handle, _db_path, target_handle)

    prompt = (
        f"You received a message from {sender}:\n\n"
        f'"{message}"\n\n'
        "Please respond naturally and conversationally."
    )
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    run_config = RunConfig(streaming_mode=StreamingMode.NONE)
    session_id = f"direct_{sender}_{target_handle}"

    collected_text: list[str] = []
    async for event in runner.runner.run_async(
        user_id=target_handle,
        session_id=session_id,
        new_message=content,
        run_config=run_config,
    ):
        for payload in serialize_event(event):
            if payload["type"] == "text" and not payload.get("partial"):
                collected_text.append(payload["content"])

    return "\n".join(collected_text) if collected_text else "[No response generated]"
