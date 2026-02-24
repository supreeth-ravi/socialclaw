"""Serialize ADK Event objects into JSON-friendly dicts for SSE streaming."""

from __future__ import annotations


def serialize_event(event) -> list[dict]:
    """Convert a single ADK Event into a list of SSE payload dicts.

    ADK Event has: content.parts[] (with .text, .function_call, .function_response),
    .author, .partial, .id, .timestamp.
    """
    payloads: list[dict] = []

    if not event.content or not event.content.parts:
        return payloads

    for part in event.content.parts:
        if part.text:
            payloads.append({
                "type": "text",
                "author": event.author,
                "content": part.text,
                "partial": bool(getattr(event, "partial", False)),
            })
        elif part.function_call:
            payloads.append({
                "type": "function_call",
                "author": event.author,
                "name": part.function_call.name,
                "args": dict(part.function_call.args or {}),
            })
        elif part.function_response:
            resp = part.function_response.response
            if isinstance(resp, dict):
                display = str(resp.get("result", resp))
            else:
                display = str(resp)
            payloads.append({
                "type": "function_response",
                "author": event.author,
                "name": part.function_response.name,
                "response": display,
            })

    return payloads
