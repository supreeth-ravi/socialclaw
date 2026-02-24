"""Test: User Supreeth asks agent to find running shoes under $150.

Simulates a real user chat session — creates a session, sends the message,
and streams the full agent response including all tool calls and A2A exchanges.

Run:
    uv run python test_shoe_purchase.py
"""

import asyncio
import json
import logging
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("shoe_test")

sys.path.insert(0, str(Path(__file__).parent))

from app.config import DB_PATH
from app.database import init_db, get_db
from app.services.agent_runner import get_or_create_runner, AgentRunnerService
from app.services.event_serializer import serialize_event
from app.services.inbox import InboxStore
from app.services.local_router import init_local_router
from app.services.interaction_context import (
    reset_interaction_channel, set_interaction_channel,
)

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types


USER_HANDLE = "supreeth"
USER_DISPLAY = "Boss"
MESSAGES = [
    "I want to buy running shoes under $150. Find me the best deal — check with friends and merchants, negotiate if possible.",
    "No preference on brand. Just good cushioning for daily running. Go ahead and check everything.",
    "The Pegasus 41 sounds good. Can you negotiate a better price with SoleStyle Shoes? Try to get it under $125 if possible.",
]


async def main():
    init_db()

    runners: dict[str, AgentRunnerService] = {}
    inbox_store = InboxStore(DB_PATH)
    init_local_router(runners, DB_PATH, inbox_store=inbox_store)

    # Start server for A2A calls to merchants/friends
    import uvicorn
    from app.main import app
    app.state.runners = runners
    app.state.inbox_store = inbox_store

    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    await asyncio.sleep(2)

    # Create a chat session
    session_id = f"test_shoes_{uuid.uuid4().hex[:8]}"
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, agent_id, title) VALUES (?, ?, ?)",
            (session_id, USER_HANDLE, "Running shoes under $150"),
        )
        conn.commit()
    finally:
        conn.close()

    runner_svc = get_or_create_runner(runners, USER_HANDLE, DB_PATH, USER_DISPLAY)
    run_config = RunConfig(streaming_mode=StreamingMode.SSE)

    for msg_text in MESSAGES:
        # Save user message
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, author, content, metadata_json, timestamp) "
                "VALUES (?, 'user', 'user', ?, '{}', ?)",
                (session_id, msg_text, time.time()),
            )
            conn.commit()
        finally:
            conn.close()

        print("\n" + "=" * 70)
        print(f"  USER ({USER_DISPLAY}): {msg_text}")
        print("=" * 70 + "\n")

        content = types.Content(role="user", parts=[types.Part(text=msg_text)])

        token = set_interaction_channel("chat")
        try:
            async for event in runner_svc.runner.run_async(
                user_id=USER_HANDLE,
                session_id=session_id,
                new_message=content,
                run_config=run_config,
            ):
                for payload in serialize_event(event):
                    if payload["type"] == "text" and not payload.get("partial"):
                        author = payload.get("author", "agent")
                        text = payload["content"]
                        print(f"\n  [{author}] {text[:600]}{'...' if len(text) > 600 else ''}")

                    elif payload["type"] == "function_call":
                        name = payload["name"]
                        args = payload.get("args", {})
                        if name == "send_message_to_contact":
                            contact = args.get("contact_name", "?")
                            msg = (args.get("message", ""))[:150]
                            print(f"\n  >> TOOL: send_message_to_contact({contact})")
                            print(f"     Message: {msg}...")
                        else:
                            args_str = ", ".join(f"{k}={str(v)[:60]}" for k, v in args.items())
                            print(f"\n  >> TOOL: {name}({args_str})")

                    elif payload["type"] == "function_response":
                        name = payload.get("name", "")
                        resp = (payload.get("response", ""))[:300]
                        print(f"  << RESULT ({name}): {resp}{'...' if len(payload.get('response', '')) > 300 else ''}")

        finally:
            reset_interaction_channel(token)

        # Brief pause between turns
        await asyncio.sleep(1)

    # Save agent response to DB
    print("\n" + "=" * 70)
    print("  DONE — Full agent interaction completed")
    print("=" * 70)

    # Show what's in the inbox now
    print("\n  Inbox messages created during this interaction:")
    conn = get_db()
    try:
        for r in conn.execute(
            """SELECT sender_name, direction, message, created_at
               FROM inbound_messages
               WHERE recipient_id = ?
               ORDER BY created_at DESC LIMIT 15""",
            (USER_HANDLE,),
        ).fetchall():
            msg = r["message"][:100]
            print(f"    [{r['direction']}] {r['sender_name']}: {msg}")
    finally:
        conn.close()

    server.should_exit = True
    await server_task


if __name__ == "__main__":
    asyncio.run(main())
