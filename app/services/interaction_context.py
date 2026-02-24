"""Context vars for interaction channel (chat vs inbox)."""

from __future__ import annotations

from contextvars import ContextVar

_interaction_channel: ContextVar[str] = ContextVar("interaction_channel", default="chat")
_a2a_turn_budget: ContextVar[int | None] = ContextVar("a2a_turn_budget", default=None)
_a2a_conversation_id: ContextVar[str | None] = ContextVar("a2a_conversation_id", default=None)


def get_interaction_channel() -> str:
    return _interaction_channel.get()


def set_interaction_channel(channel: str):
    return _interaction_channel.set(channel)


def reset_interaction_channel(token) -> None:
    _interaction_channel.reset(token)


def get_a2a_turn_budget() -> int | None:
    return _a2a_turn_budget.get()


def set_a2a_turn_budget(value: int | None):
    return _a2a_turn_budget.set(value)


def reset_a2a_turn_budget(token) -> None:
    _a2a_turn_budget.reset(token)


def decrement_a2a_turn_budget() -> int | None:
    current = _a2a_turn_budget.get()
    if current is None:
        return None
    remaining = max(0, current - 1)
    _a2a_turn_budget.set(remaining)
    return remaining


def get_a2a_conversation_id() -> str | None:
    return _a2a_conversation_id.get()


def set_a2a_conversation_id(value: str | None):
    return _a2a_conversation_id.set(value)


def reset_a2a_conversation_id(token) -> None:
    _a2a_conversation_id.reset(token)
