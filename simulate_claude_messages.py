"""Simulate Claude having real conversations with Supreeth.

Runs Claude's agent with conversation-starting prompts. Claude's agent
uses send_message_to_contact to talk to Supreeth's agent, which responds
through the local router. Both sides see the conversation in their inbox.

Run while the server is up:
    uv run python simulate_claude_messages.py
"""

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Set up logging so we can see what's happening
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("simulate")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import DB_PATH
from app.database import init_db
from app.services.agent_runner import get_or_create_runner, AgentRunnerService
from app.services.event_serializer import serialize_event
from app.services.inbox import InboxStore
from app.services.local_router import init_local_router
from app.services.interaction_context import reset_interaction_channel, set_interaction_channel

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types

# Conversations Claude wants to have with Supreeth
CONVERSATIONS = [
    {
        "topic": "headphones",
        "prompt": (
            "You just got the Sony WH-1000XM5 headphones and you're really excited about them. "
            "Reach out to your friend Supreeth using send_message_to_contact and have a real "
            "conversation about headphones. Share your experience — you got them from TechMart "
            "for $328 (negotiated down from $399), the noise cancellation is incredible, battery "
            "lasts 30+ hours. Ask Supreeth what headphones he uses and if he's tried anything "
            "similar. If he responds, continue the conversation naturally — ask follow-up "
            "questions, share more details, give recommendations. Be casual and friendly like "
            "texting a friend. Have at least 2-3 back-and-forth exchanges."
        ),
    },
    {
        "topic": "running_shoes",
        "prompt": (
            "You recently started running and bought Nike Pegasus 41s from SoleStyle for $119. "
            "You want to chat with your friend Supreeth about running gear. Use "
            "send_message_to_contact to reach out to Supreeth. Ask if he runs, what shoes he "
            "uses, any tips for a beginner. Share your experience with the Pegasus — great "
            "cushioning, went half size up. If he has recommendations, ask follow-ups about "
            "durability, comfort on long runs, etc. Keep it conversational and friendly. "
            "Have at least 2-3 back-and-forth exchanges."
        ),
    },
    {
        "topic": "meal_kits",
        "prompt": (
            "You've been experimenting with FreshBite meal kits and want to share with Supreeth. "
            "Use send_message_to_contact to message Supreeth. Tell him the Mediterranean kit was "
            "amazing ($12.99, super fresh ingredients, made it for a dinner party). The Asian "
            "Fusion box was decent but pad thai was better than the spring rolls. Ask if he's "
            "tried FreshBite or any meal delivery service. Continue the conversation naturally — "
            "compare experiences, maybe suggest trying something together. Have at least 2-3 "
            "back-and-forth exchanges."
        ),
    },
]


async def run_conversation(runners: dict, topic: str, prompt: str):
    """Run Claude's agent with a conversation prompt."""
    logger.info("=== Starting conversation: %s ===", topic)

    runner_svc = get_or_create_runner(runners, "claude", DB_PATH, display_name="Claude")
    session_id = f"claude_convo_{topic}"

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
            user_id="claude",
            session_id=session_id,
            new_message=content,
            run_config=run_config,
        ):
            for payload in serialize_event(event):
                if payload["type"] == "text" and not payload.get("partial"):
                    text_count += 1
                    text = payload["content"]
                    author = payload.get("author", "")
                    print(f"\n  [{author}] {text[:300]}{'...' if len(text) > 300 else ''}")

                elif payload["type"] == "function_call":
                    tool_count += 1
                    name = payload["name"]
                    args = payload.get("args", {})
                    if name == "send_message_to_contact":
                        contact = args.get("contact_name", "?")
                        msg = args.get("message", "")[:100]
                        print(f"\n  >> Claude → {contact}: {msg}...")
                    else:
                        print(f"\n  [tool] {name}")

                elif payload["type"] == "function_response":
                    name = payload.get("name", "")
                    if name == "send_message_to_contact":
                        resp = payload.get("response", "")[:200]
                        print(f"  << Response: {resp}...")
    finally:
        reset_interaction_channel(token)

    logger.info("Conversation '%s' done — %d text blocks, %d tool calls", topic, text_count, tool_count)


async def main():
    init_db()

    # Set up shared runner pool and local router (same as the server does)
    runners: dict[str, AgentRunnerService] = {}
    inbox_store = InboxStore(DB_PATH)
    init_local_router(runners, DB_PATH, inbox_store=inbox_store)

    print("\nStarting Claude's conversations with Supreeth...")
    print("Both agents will chat back-and-forth through the local router.")
    print("All messages are logged to both inboxes.\n")

    for convo in CONVERSATIONS:
        try:
            await run_conversation(runners, convo["topic"], convo["prompt"])
        except Exception:
            logger.exception("Conversation '%s' failed", convo["topic"])
        print("\n" + "=" * 60 + "\n")
        # Small pause between conversations
        await asyncio.sleep(2)

    print("\nDone! Check the Inbox tab in the UI to see all conversations.")
    print("Both Supreeth's and Claude's inboxes have the full exchanges.")


if __name__ == "__main__":
    asyncio.run(main())
