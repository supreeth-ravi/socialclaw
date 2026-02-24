from __future__ import annotations

import json
import time
import uuid
from pathlib import Path


TRACES_DIR = Path(__file__).resolve().parent.parent / "traces"


class TraceLogger:
    """Lightweight file-based trace logger."""

    def __init__(self, traces_dir: Path | None = None) -> None:
        self.traces_dir = traces_dir or TRACES_DIR
        self.traces_dir.mkdir(parents=True, exist_ok=True)

    def _write_span(self, trace_id: str, span: dict) -> None:
        path = self.traces_dir / f"{trace_id}.json"
        if path.exists():
            data = json.loads(path.read_text())
        else:
            data = {"trace_id": trace_id, "spans": []}
        data["spans"].append(span)
        path.write_text(json.dumps(data, indent=2))

    def new_trace(self) -> str:
        return str(uuid.uuid4())

    def log_a2a_request(
        self,
        trace_id: str,
        from_agent: str,
        to_agent: str,
        message: str,
        response: str,
    ) -> None:
        self._write_span(
            trace_id,
            {
                "type": "a2a_request",
                "from": from_agent,
                "to": to_agent,
                "message": message,
                "response": response,
                "timestamp": time.time(),
            },
        )

    def log_tool_call(
        self,
        trace_id: str,
        agent_name: str,
        tool_name: str,
        args: dict,
        result: str,
    ) -> None:
        self._write_span(
            trace_id,
            {
                "type": "tool_call",
                "agent": agent_name,
                "tool": tool_name,
                "args": args,
                "result": result,
                "timestamp": time.time(),
            },
        )

    def log_event(self, trace_id: str, agent_name: str, event: str) -> None:
        self._write_span(
            trace_id,
            {
                "type": "event",
                "agent": agent_name,
                "event": event,
                "timestamp": time.time(),
            },
        )


# Shared default logger
tracer = TraceLogger()
