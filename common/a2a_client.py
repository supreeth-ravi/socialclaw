"""Dynamic A2A client — send a message to any agent given its card URL.

Uses the official ``a2a`` SDK types and ``JsonRpcTransport`` so the
JSON-RPC payloads match exactly what the protocol expects.
"""

from __future__ import annotations

import logging
import uuid
from urllib.parse import urlparse

import httpx

from a2a.client.helpers import create_text_message_object
from a2a.client.transports.jsonrpc import JsonRpcTransport
from a2a.types import (
    AgentCard,
    Message,
    MessageSendParams,
    Task,
)

from .tracing import tracer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent card fetching
# ---------------------------------------------------------------------------

async def fetch_agent_card(agent_card_url: str) -> AgentCard | dict:
    """Fetch an agent card from a well-known URL.

    Returns a validated :class:`AgentCard` when the remote payload conforms
    to the current spec, otherwise falls back to the raw *dict*.

    Cards using the old v0.3 ``supportedInterfaces`` field are returned as
    raw dicts so the JSON-RPC endpoint URL is preserved (the current SDK
    model drops that field during validation).
    """
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(
            agent_card_url,
            headers={"ngrok-skip-browser-warning": "true"},
        )
        resp.raise_for_status()
        data = resp.json()

    # Old-spec cards carry the RPC endpoint in supportedInterfaces which
    # the current SDK AgentCard model silently drops.  Keep the raw dict
    # so _get_rpc_url can extract the correct endpoint.
    if "supportedInterfaces" in data:
        logger.info(
            "Agent card at %s uses old supportedInterfaces field; keeping raw dict",
            agent_card_url,
        )
        return data

    try:
        return AgentCard.model_validate(data)
    except Exception:
        logger.warning(
            "Agent card at %s did not validate as AgentCard; using raw dict",
            agent_card_url,
        )
        return data


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _derive_base_url(agent_card_url: str) -> str:
    """Derive the service base URL from the agent-card URL.

    ``https://x.ngrok-free.app/.well-known/agent-card.json`` → ``https://x.ngrok-free.app``
    """
    parsed = urlparse(agent_card_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _get_rpc_url(card: AgentCard | dict, agent_card_url: str) -> str:
    """Determine the JSON-RPC endpoint URL from an agent card."""

    if isinstance(card, AgentCard):
        # SDK AgentCard: check additional_interfaces for a JSONRPC binding,
        # then fall back to the card's primary url.
        if card.additional_interfaces:
            for iface in card.additional_interfaces:
                transport = getattr(iface, "transport", None) or ""
                if "jsonrpc" in str(transport).lower():
                    iface_url = getattr(iface, "url", None)
                    if iface_url:
                        return iface_url.strip()
        return card.url.strip()

    # --- Raw dict fallback (card didn't validate as AgentCard) ---

    def _find_jsonrpc_url(interfaces: list) -> str | None:
        for iface in interfaces:
            binding = (
                iface.get("protocolBinding")
                or iface.get("protocol")
                or ""
            )
            if "jsonrpc" in str(binding).lower():
                url = iface.get("url")
                if url:
                    return url.strip()
        return None

    # Old spec: supportedInterfaces
    url = _find_jsonrpc_url(card.get("supportedInterfaces", []))
    if url:
        return url

    # Snake-case variant
    url = _find_jsonrpc_url(card.get("supported_interfaces", []))
    if url:
        return url

    # Endpoints variant
    for ep in card.get("endpoints", []):
        binding = (ep.get("protocolBinding") or ep.get("protocol") or "").lower()
        if "jsonrpc" in binding or "a2a" in binding:
            url = (ep.get("endpoint") or ep.get("url") or "").strip()
            if url:
                return url

    # Standard url key
    if card.get("url"):
        return card["url"].strip()

    # Last resort: strip the well-known path from the card URL
    return _derive_base_url(agent_card_url)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _extract_text_from_result(result: Task | Message) -> str:
    """Pull readable text out of a ``Task`` or ``Message`` response."""
    texts: list[str] = []

    if isinstance(result, Message):
        for part in result.parts:
            inner = part.root
            if hasattr(inner, "text"):
                texts.append(inner.text)
        return "\n".join(texts) if texts else "[Empty message from agent]"

    # Task-based response — check status.message first, then artifacts
    if result.status and result.status.message:
        for part in result.status.message.parts:
            inner = part.root
            if hasattr(inner, "text"):
                texts.append(inner.text)

    if result.artifacts:
        for artifact in result.artifacts:
            for part in artifact.parts:
                inner = part.root
                if hasattr(inner, "text"):
                    texts.append(inner.text)

    if texts:
        return "\n".join(texts)

    status_label = result.status.state if result.status else "unknown"
    return f"[No text in task response — status={status_label}]"


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

async def send_a2a_message(
    rpc_url: str,
    message: str,
    agent_card: AgentCard | None = None,
    *,
    timeout: float = 120.0,
    sender_name: str | None = None,
    sender_agent_card_url: str | None = None,
    sender_type: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """Send ``message/send`` to an A2A agent and return the text response.

    Uses :class:`JsonRpcTransport` so the JSON-RPC payload is built
    identically to what the official SDK produces.
    """
    msg_obj = create_text_message_object(role="user", content=message)
    params = MessageSendParams(message=msg_obj)

    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"ngrok-skip-browser-warning": "true"},
    ) as client:
        # If sender metadata is provided, send a manual JSON-RPC payload
        # so the receiver can register the sender for pure A2A routing.
        if sender_name or sender_agent_card_url or sender_type or conversation_id:
            payload = {
                "jsonrpc": "2.0",
                "id": f"msg-{uuid.uuid4().hex}",
                "method": "message/send",
                "params": {
                    "message": msg_obj.model_dump(),
                    "sender_name": sender_name,
                    "sender_agent_card_url": sender_agent_card_url,
                    "sender_type": sender_type,
                    "conversation_id": conversation_id,
                },
            }
            logger.warning(
                "A2A RPC SEND url=%s sender=%s conv=%s method=message/send",
                rpc_url,
                sender_name or "",
                conversation_id or "",
            )
            resp = await client.post(rpc_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result")
            if not result:
                return "[No response from agent]"
            if isinstance(result, dict) and "parts" in result:
                try:
                    msg = Message.model_validate(result)
                    out = _extract_text_from_result(msg)
                    logger.warning("A2A RPC RECV url=%s conv=%s chars=%d", rpc_url, conversation_id or "", len(out))
                    return out
                except Exception:
                    out = "\n".join(
                        part.get("text", "")
                        for part in (result.get("parts") or [])
                        if isinstance(part, dict)
                    ).strip() or "[Empty message from agent]"
                    logger.warning("A2A RPC RECV url=%s conv=%s chars=%d", rpc_url, conversation_id or "", len(out))
                    return out
            if isinstance(result, dict) and ("status" in result or "artifacts" in result):
                try:
                    task = Task.model_validate(result)
                    out = _extract_text_from_result(task)
                    logger.warning("A2A RPC RECV url=%s conv=%s chars=%d", rpc_url, conversation_id or "", len(out))
                    return out
                except Exception:
                    return "[Task response from agent]"
            return str(result)

        transport = JsonRpcTransport(
            client,
            agent_card=agent_card,
            url=rpc_url,
        )
        result = await transport.send_message(params)

    return _extract_text_from_result(result)


# ---------------------------------------------------------------------------
# High-level convenience
# ---------------------------------------------------------------------------

async def message_agent(
    agent_card_url: str,
    message: str,
    *,
    sender_name: str | None = None,
    sender_agent_card_url: str | None = None,
    sender_type: str | None = None,
    conversation_id: str | None = None,
) -> str:
    """Fetch an agent card, send a message, return the text response.

    This is the main entry point for dynamically talking to any A2A agent.
    """
    trace_id = tracer.new_trace()
    try:
        card = await fetch_agent_card(agent_card_url)
        rpc_url = _get_rpc_url(card, agent_card_url)
        agent_name = (
            card.name if isinstance(card, AgentCard) else card.get("name", "unknown")
        )

        tracer.log_event(
            trace_id, "a2a_client", f"Sending to {agent_name} at {rpc_url}"
        )

        ac = card if isinstance(card, AgentCard) else None
        response = await send_a2a_message(
            rpc_url,
            message,
            agent_card=ac,
            sender_name=sender_name,
            sender_agent_card_url=sender_agent_card_url,
            sender_type=sender_type,
            conversation_id=conversation_id,
        )
        tracer.log_a2a_request(trace_id, "self", agent_name, message, response)
        return response
    except Exception as e:
        tracer.log_event(trace_id, "a2a_client", f"Error: {e}")
        return f"[Error contacting agent at {agent_card_url}] {e}"
