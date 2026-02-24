"""Wraps ADK InMemoryRunner to run a personal agent locally with full event streaming."""

from __future__ import annotations

import logging
from pathlib import Path

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import InMemoryRunner
from google.genai import types

from .event_serializer import serialize_event
from .interaction_context import reset_interaction_channel, set_interaction_channel

logger = logging.getLogger(__name__)


class AgentRunnerService:
    """Run a personal agent locally via ADK InMemoryRunner.

    Yields serialized event dicts suitable for SSE streaming.
    """

    def __init__(self, agent, app_name: str = "ai_social") -> None:
        self.runner = InMemoryRunner(agent=agent, app_name=app_name)
        self.runner.auto_create_session = True
        self.app_name = app_name

    async def run_message(self, session_id: str, user_message: str, user_id: str = "web_user"):
        """Send *user_message* to the agent in *session_id* and yield event payloads."""
        content = types.Content(
            role="user",
            parts=[types.Part(text=user_message)],
        )
        run_config = RunConfig(streaming_mode=StreamingMode.SSE)

        token = set_interaction_channel("chat")
        try:
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
                run_config=run_config,
            ):
                for payload in serialize_event(event):
                    yield payload
        finally:
            reset_interaction_channel(token)

        yield {"type": "done"}


def get_or_create_runner(
    runners: dict[str, AgentRunnerService],
    agent_id: str,
    db_path: str | Path,
    display_name: str = "",
) -> AgentRunnerService:
    """Lazily create and cache an AgentRunnerService for a given user."""
    if agent_id not in runners:
        from personal_agents.shared_tools import create_tools

        tools = create_tools(agent_id, db_path)

        from personal_agents.shared_agent import create_personal_agent
        # Load extra instructions from user profile
        try:
            from app.database import get_db
            conn = get_db(db_path)
            row = conn.execute(
                "SELECT agent_instructions FROM users WHERE handle = ?",
                (agent_id,),
            ).fetchone()
            extra = row["agent_instructions"] if row else ""
        finally:
            try:
                conn.close()
            except Exception:
                pass
        agent = create_personal_agent(agent_id, display_name=display_name, tools=tools, extra_instructions=extra)

        runners[agent_id] = AgentRunnerService(agent, app_name="ai_social")
        logger.info("Created runner for agent '%s'", agent_id)

    return runners[agent_id]
