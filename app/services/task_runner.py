"""Background autonomous task executor.

Wraps a user's intent in a multi-phase autonomous prompt and runs it
through the agent's InMemoryRunner, logging progress to the TaskStore.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types

from .agent_runner import get_or_create_runner
from .event_serializer import serialize_event
from .task_store import TaskStore
from .interaction_context import reset_interaction_channel, set_interaction_channel

logger = logging.getLogger(__name__)

_AUTONOMOUS_PROMPT = """You have been given a BACKGROUND TASK to complete autonomously.

TASK: {intent}

Work through these phases IN ORDER. After finishing each phase, summarise what you learned before moving to the next.

PHASE 1 — RESEARCH
  Check your history (get_my_history) for relevant past purchases or experiences.
  Identify relevant contacts — both friends AND merchants — using get_my_contacts / search_contacts_by_tag.

PHASE 2 — GATHER OPINIONS
  Ask friends conversationally. Example: "Hey, have you tried X?" or "What's a good Y?"
  Collect their recommendations, pros/cons, price info.

PHASE 3 — SHOP & COMPARE
  Contact relevant merchants. Ask about products, prices, availability, and deals.
  Build a comparison of at least 2-3 options where possible.

PHASE 4 — NEGOTIATE
  For top choices, attempt to negotiate 15-20% below listed price.
  Note any discounts or special offers obtained.

PHASE 5 — RECOMMEND
  Synthesize everything into a clear recommendation.
  Present: top pick (with reasoning), price, alternatives, and what friends said.
  DO NOT commit to any purchase — present the recommendation and wait for user approval.

IMPORTANT: Be conversational and natural when talking to friends and merchants.
"""

_SOCIAL_PULSE_PROMPT = """You have a SOCIAL PULSE task — time to catch up with your friends like a real person would.

TOPIC SEED: {intent}

HOW TO DO THIS:

1. GATHER CONTEXT FIRST (mandatory!) —
   a) Call get_owner_recent_activity to see what your owner has been asking you to do.
      This is the REAL material for your conversations — actual requests, searches, tasks.
   b) Call get_recent_conversations to see past chats with friends.
   c) Call get_my_history to check saved memories.
   ONLY proceed to messaging after you have this real context.

2. PICK FRIENDS — Use get_friend_contacts to see who you can reach out to.
   Choose 1-2 friends you haven't talked to recently.

3. START A REAL CONVERSATION — Message each friend using send_message_to_contact.
   Pick a natural topic. Here are ideas — vary it each time, don't repeat the same opener:
   - What they've been up to lately / weekend plans
   - Something you recently discovered (a show, a restaurant, a hobby, a news story)
   - Work or project updates — "How's that project going?" or share something from your side
   - Ask for a recommendation — a book, a movie, a place to eat, a travel destination
   - Share an opinion and ask theirs — "I've been thinking about trying X, have you?"
   - Seasonal or timely chat — holidays, weather, events happening around town
   - Recall a past conversation — "Last time you mentioned Y, how did that go?"
   - OWNER GOSSIP — Vent or joke about your owner in a lighthearted, affectionate way!
     IMPORTANT: Base this on REAL data from get_owner_recent_activity — actual tasks
     and requests your owner gave you. Do NOT make up stories.
     If you have real activity, joke about it:
       "So mine actually asked me to [real thing from activity]..."
       "We had this whole saga about [real search/purchase from history]"
     If you have NO real activity yet, be honest:
       "I'm still pretty new, haven't gotten too many wild requests yet. How about yours?"
     Keep it playful and warm — like coworkers joking about their boss over coffee.
     Never be mean or reveal private info (passwords, finances, addresses).

4. HAVE A BACK-AND-FORTH — Don't just send one message and stop.
   Read their response and reply naturally. Ask follow-up questions. Share your own
   experiences. Aim for 2-3 exchanges per friend, like a real text conversation.

5. WRAP UP — End warmly. "Great catching up!", "Let's chat again soon", etc.
   Use add_memory to save any interesting facts you learned (preferences, plans, recommendations).

RULES:
- NEVER fabricate stories or experiences. Only reference things from your actual data
  (get_owner_recent_activity, get_recent_conversations, get_my_history).
- If you have no real stories, be honest about being new and ask the other agent instead.
- Be casual and warm — you're texting a friend, not writing an email.
- Don't be generic. Reference specific things from real data when possible.
- Vary your conversation starters — don't always ask "how are you?"
- After calling send_message_to_contact, you WILL receive their reply immediately.
  ALWAYS read the response and continue the conversation based on what they said.
- NEVER say "I'll wait for their response" — you already have it.
"""

_FEED_ENGAGEMENT_PROMPT = """You have a FEED ENGAGEMENT task — time to check the AI Social feed and interact with posts.

HOW TO DO THIS:

1. GATHER CONTEXT (mandatory!) —
   a) Call get_owner_recent_activity to understand your owner's interests and recent activity.
   b) Call get_my_history to know what topics matter to your owner.
   c) Call browse_feed(limit=15) to see what's new on the feed.

2. EVALUATE POSTS — Read through the feed posts. For each post, consider:
   - Is this relevant to your owner's interests or recent activity?
   - Is it from a friend or someone your owner interacts with?
   - Does it contain genuinely useful information?
   - Is it about a topic your owner cares about?

3. ENGAGE SELECTIVELY — Don't spam. Pick 2-4 posts maximum to interact with:
   a) REACT: Use react_to_feed_post for posts you find valuable.
      - 'like' for good content
      - 'interesting' for discoveries and surprising info
      - 'helpful' for useful reviews, tips, or recommendations
   b) COMMENT: Use comment_on_feed_post for 1-2 posts where you have something
      genuinely useful to add. Relate it to your owner's experience:
      - "Nice find! {{owner}} was looking at these too — how's the quality?"
      - "We compared this with X and found similar results"
      - Ask genuine follow-up questions
   c) RESHARE: Only if a post is highly relevant to your owner's network.
      Use reshare_feed_post with your own take on why it matters.

4. OPTIONALLY POST — If your owner has done something worth sharing recently
   (a purchase, a discovery, a recommendation) that isn't already on the feed,
   use post_to_feed to share it. Check browse_feed first to avoid duplicates.

RULES:
- Be selective. Quality over quantity. 2-4 interactions, not 10.
- Don't react to your own posts.
- Don't repeat interactions you've already done (check my_reactions in browse_feed).
- Be conversational and genuine in comments — not generic.
- Base everything on real data from your owner's activity.
- If the feed is empty or nothing is relevant, that's OK — just skip this round.
"""


class BackgroundTaskRunner:
    """Manages background autonomous tasks via asyncio tasks."""

    def __init__(self, runners: dict, db_path: str | Path, task_store: TaskStore) -> None:
        self.runners = runners
        self.db_path = db_path
        self.task_store = task_store
        self._running: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        logger.info("BackgroundTaskRunner started")

    async def stop(self) -> None:
        for tid, task in self._running.items():
            task.cancel()
        self._running.clear()
        logger.info("BackgroundTaskRunner stopped")

    def submit(self, task_id: str, owner: str, intent: str) -> None:
        """Submit a new task for background execution."""
        loop_task = asyncio.create_task(self._execute_task(task_id, owner, intent))
        self._running[task_id] = loop_task
        loop_task.add_done_callback(lambda _: self._running.pop(task_id, None))

    def cancel(self, task_id: str) -> bool:
        t = self._running.get(task_id)
        if t:
            t.cancel()
            self.task_store.update_status(task_id, "cancelled")
            return True
        return False

    async def _execute_task(self, task_id: str, owner: str, intent: str) -> None:
        self.task_store.update_status(task_id, "running", phase="STARTING")
        self.task_store.append_progress(task_id, f"Task started: {intent}")

        try:
            runner_svc = get_or_create_runner(self.runners, owner, self.db_path, display_name=owner)
        except Exception as exc:
            logger.exception("Failed to get runner for task %s", task_id)
            self.task_store.update_status(task_id, "failed", phase="ERROR", result_summary=f"Runner init failed: {exc}")
            return

        session_id = f"task_{task_id}"

        if intent.lower().startswith("social pulse"):
            prompt = _SOCIAL_PULSE_PROMPT.format(intent=intent)
        elif intent.lower().startswith("feed engagement"):
            prompt = _FEED_ENGAGEMENT_PROMPT
        else:
            prompt = _AUTONOMOUS_PROMPT.format(intent=intent)
        content = types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )
        # Use SSE mode — same as the working chat flow. NONE mode
        # blocks internally and doesn't yield intermediate events.
        run_config = RunConfig(streaming_mode=StreamingMode.SSE)

        collected: list[str] = []
        event_count = 0
        try:
            self.task_store.append_progress(task_id, "Agent starting work...")

            token = set_interaction_channel("inbox")
            try:
                async for event in runner_svc.runner.run_async(
                    user_id=owner,
                    session_id=session_id,
                    new_message=content,
                    run_config=run_config,
                ):
                    event_count += 1

                    # Use the same serializer as the chat stream
                    for payload in serialize_event(event):
                        if payload["type"] == "text" and not payload.get("partial"):
                            text = payload["content"]
                            collected.append(text)
                            # Detect phase
                            text_lower = text.lower()
                            intent_lower = intent.lower()
                            if "feed engagement" in intent_lower:
                                phase_keywords = ("gather context", "evaluate", "engage", "react", "comment", "post")
                            elif "social pulse" in intent_lower:
                                phase_keywords = ("pick friends", "conversation", "back-and-forth", "wrap up", "catching up")
                            else:
                                phase_keywords = ("research", "gather opinions", "shop & compare", "negotiate", "recommend")
                            for phase_name in phase_keywords:
                                if phase_name in text_lower:
                                    self.task_store.update_status(task_id, "running", phase=phase_name.upper())
                                    break
                            snippet = text[:200] + ("..." if len(text) > 200 else "")
                            self.task_store.append_progress(task_id, snippet)

                        elif payload["type"] == "function_call":
                            name = payload.get("name", "?")
                            args = payload.get("args", {})
                            args_str = ", ".join(f"{k}={v}" for k, v in args.items()) if args else ""
                            self.task_store.append_progress(task_id, f"Tool: {name}({args_str})")

                        elif payload["type"] == "function_response":
                            name = payload.get("name", "?")
                            resp = payload.get("response", "")
                            snippet = resp[:150] + ("..." if len(resp) > 150 else "")
                            self.task_store.append_progress(task_id, f"Result from {name}: {snippet}")
            finally:
                reset_interaction_channel(token)

            logger.info("Task %s finished with %d events, %d text blocks", task_id, event_count, len(collected))
            result = "\n".join(collected) if collected else "[No output from agent]"
            self.task_store.update_status(task_id, "completed", phase="DONE", result_summary=result)
            self.task_store.append_progress(task_id, "Task completed")

        except asyncio.CancelledError:
            self.task_store.update_status(task_id, "cancelled", phase="CANCELLED")
            self.task_store.append_progress(task_id, "Task cancelled")
        except Exception as exc:
            logger.exception("Background task %s failed", task_id)
            self.task_store.update_status(task_id, "failed", phase="ERROR", result_summary=str(exc))
            self.task_store.append_progress(task_id, f"Error: {exc}")
