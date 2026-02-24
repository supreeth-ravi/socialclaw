from __future__ import annotations

import json
from pathlib import Path

from .models import HistoryEntry


class HistoryStore:
    """JSON file-backed history store."""

    def __init__(self, history_file: str | Path) -> None:
        self.path = Path(history_file)
        self._entries: list[HistoryEntry] | None = None

    def _load(self) -> list[HistoryEntry]:
        if self._entries is None:
            if self.path.exists():
                data = json.loads(self.path.read_text())
                self._entries = [HistoryEntry(**e) for e in data]
            else:
                self._entries = []
        return self._entries

    def search(self, query: str) -> list[HistoryEntry]:
        """Return history entries whose summary or details match *query* keywords."""
        entries = self._load()
        keywords = query.lower().split()
        results: list[HistoryEntry] = []
        for entry in entries:
            text = f"{entry.summary} {json.dumps(entry.details)}".lower()
            if any(kw in text for kw in keywords):
                results.append(entry)
        return results

    def all(self) -> list[HistoryEntry]:
        return list(self._load())

    def add(self, entry: HistoryEntry) -> None:
        entries = self._load()
        entries.append(entry)
        self.path.write_text(
            json.dumps([e.model_dump() for e in entries], indent=2)
        )
