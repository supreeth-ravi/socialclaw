from __future__ import annotations

import json
from pathlib import Path

import httpx

from .models import Contact


class ContactRegistry:
    """JSON file-backed contact registry. Acts as the agent's contact book DB.

    Supports dynamic add/remove at runtime — changes persist to disk.
    """

    def __init__(self, contacts_file: str | Path) -> None:
        self.path = Path(contacts_file)
        self._contacts: list[Contact] | None = None

    def _load(self) -> list[Contact]:
        if self._contacts is None:
            if self.path.exists():
                data = json.loads(self.path.read_text())
                self._contacts = [Contact(**c) for c in data]
            else:
                self._contacts = []
        return self._contacts

    def _save(self) -> None:
        contacts = self._load()
        self.path.write_text(
            json.dumps([c.model_dump() for c in contacts], indent=2)
        )

    def all(self) -> list[Contact]:
        return list(self._load())

    def find(self, name: str) -> Contact | None:
        for c in self._load():
            if c.name.lower() == name.lower():
                return c
        return None

    def find_by_tag(self, tag: str) -> list[Contact]:
        return [c for c in self._load() if tag.lower() in [t.lower() for t in c.tags]]

    def find_by_type(self, contact_type: str) -> list[Contact]:
        return [c for c in self._load() if c.type == contact_type]

    def add(self, contact: Contact) -> str:
        """Add a new contact. Returns status message."""
        existing = self.find(contact.name)
        if existing:
            return f"Contact '{contact.name}' already exists. Use update instead."
        contacts = self._load()
        contacts.append(contact)
        self._save()
        return f"Added '{contact.name}' to contacts."

    def remove(self, name: str) -> str:
        """Remove a contact by name. Returns status message."""
        contacts = self._load()
        original_len = len(contacts)
        self._contacts = [c for c in contacts if c.name.lower() != name.lower()]
        if len(self._contacts) == original_len:
            return f"Contact '{name}' not found."
        self._save()
        return f"Removed '{name}' from contacts."

    def update(self, name: str, **fields) -> str:
        """Update fields on an existing contact."""
        contact = self.find(name)
        if not contact:
            return f"Contact '{name}' not found."
        for key, value in fields.items():
            if hasattr(contact, key):
                setattr(contact, key, value)
        self._save()
        return f"Updated '{name}'."

    async def ping(self, name: str) -> str:
        """Check if a contact's agent card URL is reachable."""
        contact = self.find(name)
        if not contact:
            return f"Contact '{name}' not found."
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(
                    contact.agent_card_url,
                    headers={"ngrok-skip-browser-warning": "true"},
                )
                if resp.status_code == 200:
                    contact.status = "active"
                    self._save()
                    return f"{name} is active and reachable."
                else:
                    contact.status = "unreachable"
                    self._save()
                    return f"{name} returned status {resp.status_code}."
        except Exception as e:
            contact.status = "unreachable"
            self._save()
            return f"{name} is unreachable: {e}"
