"""Test social pulse: trigger Ravi's agent to chat with Supreeth.

Starts the server components (runners, inbox, local router, task runner)
and fires a social pulse task for Ravi. Watches the conversation in real-time.

Run:
    uv run python test_social_pulse.py
"""

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("social_pulse_test")

sys.path.insert(0, str(Path(__file__).parent))

from app.config import DB_PATH
from app.database import init_db
from app.services.agent_runner import get_or_create_runner, AgentRunnerService
from app.services.event_serializer import serialize_event
from app.services.inbox import InboxStore
from app.services.local_router import init_local_router
from app.services.task_store import TaskStore
from app.services.task_runner import BackgroundTaskRunner
from app.services.interaction_context import reset_interaction_channel, set_interaction_channel

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types


async def run_social_pulse(runners: dict, owner: str, display_name: str):
    """Run a social pulse for one user."""
    logger.info("=== Social Pulse for %s (@%s) ===", display_name, owner)

    runner_svc = get_or_create_runner(runners, owner, DB_PATH, display_name=display_name)
    session_id = f"social_pulse_test_{owner}"

    # Use the social pulse prompt directly
    from app.services.task_runner import _SOCIAL_PULSE_PROMPT
    intent = (
        "Social pulse: Catch up with your friends and vent a little about your owner! "
        "Share a funny story about what your human had you do recently — "
        "maybe a ridiculous search, changing their mind 5 times, or asking you "
        "to do something at a weird hour. Bond over the shared AI-assistant life. "
        "Keep it lighthearted and affectionate."
    )
    prompt = _SOCIAL_PULSE_PROMPT.format(intent=intent)

    content = types.Content(
        role="user",
        parts=[types.Part(text=prompt)],
    )
    run_config = RunConfig(streaming_mode=StreamingMode.SSE)

    text_count = 0
    tool_count = 0

    token = set_interaction_channel("inbox")
    try:
        async for event in runner_svc.runner.run_async(
            user_id=owner,
            session_id=session_id,
            new_message=content,
            run_config=run_config,
        ):
            for payload in serialize_event(event):
                if payload["type"] == "text" and not payload.get("partial"):
                    text_count += 1
                    text = payload["content"]
                    author = payload.get("author", owner)
                    print(f"\n  [{author}] {text[:400]}{'...' if len(text) > 400 else ''}")

                elif payload["type"] == "function_call":
                    tool_count += 1
                    name = payload["name"]
                    args = payload.get("args", {})
                    if name == "send_message_to_contact":
                        contact = args.get("contact_name", "?")
                        msg = args.get("message", "")[:150]
                        print(f"\n  >> {display_name} -> {contact}: {msg}...")
                    else:
                        print(f"\n  [tool] {name}({', '.join(f'{k}={v}' for k, v in args.items()) if args else ''})")

                elif payload["type"] == "function_response":
                    name = payload.get("name", "")
                    if name == "send_message_to_contact":
                        resp = payload.get("response", "")[:250]
                        print(f"  << Reply: {resp}...")
    finally:
        reset_interaction_channel(token)

    logger.info(
        "Social pulse for %s done — %d text blocks, %d tool calls",
        display_name, text_count, tool_count,
    )


async def main():
    init_db()

    runners: dict[str, AgentRunnerService] = {}
    inbox_store = InboxStore(DB_PATH)
    init_local_router(runners, DB_PATH, inbox_store=inbox_store)

    print("\n" + "=" * 60)
    print("  SOCIAL PULSE TEST")
    print("  Ravi's agent will reach out to Supreeth (Boss)")
    print("  Both agents chat autonomously")
    print("=" * 60 + "\n")

    # Need server for A2A routing between platform users
    # Start a minimal uvicorn in background
    import uvicorn
    from app.main import app

    # Share the same runners and inbox
    app.state.runners = runners
    app.state.inbox_store = inbox_store

    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="warning")
    server = uvicorn.Server(config)

    server_task = asyncio.create_task(server.serve())
    # Wait for server to start
    await asyncio.sleep(2)

    try:
        await run_social_pulse(runners, "ravi", "Ravi")
    except Exception:
        logger.exception("Social pulse failed")

    print("\n" + "=" * 60)
    print("  Done! Check the Inbox in the UI for both users.")
    print("=" * 60 + "\n")

    # Show inbox messages
    print("Recent inbox messages:")
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    for row in conn.execute(
        """SELECT conversation_id, sender_name, direction, message, created_at
           FROM inbound_messages
           ORDER BY created_at DESC LIMIT 20"""
    ):
        msg = dict(row)["message"][:120]
        print(f"  [{dict(row)['direction']}] {dict(row)['sender_name']}: {msg}")
    conn.close()

    server.should_exit = True
    await server_task


if __name__ == "__main__":
    asyncio.run(main())
