from __future__ import annotations

import json
from pathlib import Path
import hashlib

from common.a2a_client import fetch_agent_card, message_agent
from common.contacts import ContactRegistry
from common.history import HistoryStore
from common.models import Contact

_BASE = Path(__file__).parent
_contacts = ContactRegistry(_BASE / "contacts.json")
_history = HistoryStore(_BASE / "history.json")
SENDER_NAME = "Bob"
SENDER_CARD_URL = "http://localhost:8002/.well-known/agent-card.json"


# ─── Contact management ────────────────────────────────────────────

def get_my_contacts() -> str:
    """List all contacts in Bob's contact book with their type, description, and tags."""
    contacts = _contacts.all()
    if not contacts:
        return "No contacts found."
    lines = []
    for c in contacts:
        lines.append(
            f"- {c.name} ({c.type}) — {c.description} "
            f"[tags: {', '.join(c.tags)}] [status: {c.status}]"
        )
    return "\n".join(lines)


def search_contacts_by_tag(tag: str) -> str:
    """Find contacts matching a specific tag (e.g. 'shoes', 'electronics', 'friend')."""
    matches = _contacts.find_by_tag(tag)
    if not matches:
        return f"No contacts found with tag '{tag}'."
    lines = [f"- {c.name} ({c.type}) — {c.description}" for c in matches]
    return "\n".join(lines)


def get_merchant_contacts() -> str:
    """List only merchant contacts."""
    merchants = _contacts.find_by_type("merchant")
    if not merchants:
        return "No merchant contacts."
    lines = [f"- {c.name} — {c.description} [tags: {', '.join(c.tags)}]" for c in merchants]
    return "\n".join(lines)


def get_friend_contacts() -> str:
    """List only personal (friend) contacts."""
    friends = _contacts.find_by_type("personal")
    if not friends:
        return "No friend contacts."
    lines = [f"- {c.name} — {c.description} [tags: {', '.join(c.tags)}]" for c in friends]
    return "\n".join(lines)


async def add_contact(
    name: str,
    agent_card_url: str,
    contact_type: str,
    description: str,
    tags: str = "",
) -> str:
    """Add a new contact to Bob's contact book.

    Args:
        name: Display name for the contact
        agent_card_url: The agent card URL
        contact_type: Either 'personal' or 'merchant'
        description: Brief description of what this contact does
        tags: Comma-separated tags
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    contact = Contact(
        name=name,
        type=contact_type,
        agent_card_url=agent_card_url,
        description=description,
        tags=tag_list,
    )
    return _contacts.add(contact)


def remove_contact(name: str) -> str:
    """Remove a contact from Bob's contact book by name."""
    return _contacts.remove(name)


async def discover_agent(agent_card_url: str) -> str:
    """Fetch an agent card URL and show what the agent can do.
    Use this to learn about a new agent before adding them as a contact."""
    from a2a.types import AgentCard

    try:
        card = await fetch_agent_card(agent_card_url)

        if isinstance(card, AgentCard):
            name = card.name
            desc = card.description or "No description"
            skills = card.skills or []
            skill_lines = [
                f"  - {s.name}: {s.description} [tags: {', '.join(s.tags or [])}]"
                for s in skills
            ]
        else:
            name = card.get("name", "Unknown")
            desc = card.get("description", "No description")
            skills = card.get("skills", [])
            skill_lines = [
                f"  - {s.get('name', '?')}: {s.get('description', '?')} [tags: {', '.join(s.get('tags', []))}]"
                for s in skills
            ]

        skills_text = "\n".join(skill_lines) if skill_lines else "  (no skills listed)"
        return (
            f"Agent: {name}\n"
            f"Description: {desc}\n"
            f"Skills:\n{skills_text}\n"
            f"Card URL: {agent_card_url}"
        )
    except Exception as e:
        return f"Failed to fetch agent card at {agent_card_url}: {e}"


# ─── Communication ──────────────────────────────────────────────────

async def send_message_to_contact(contact_name: str, message: str) -> str:
    """Send a message to a contact's agent and get their response.

    Looks up the contact in Bob's contact book, resolves their agent card,
    sends the message via A2A protocol, and returns the response.
    """
    contact = _contacts.find(contact_name)
    if not contact:
        return f"Contact '{contact_name}' not found in your contacts. Use get_my_contacts to see available contacts."
    conv_seed = f"{SENDER_NAME.lower()}::{(contact.agent_card_url or '').lower()}"
    conv_id = f"conv_a2a_{hashlib.sha1(conv_seed.encode('utf-8')).hexdigest()[:10]}"
    return await message_agent(
        contact.agent_card_url,
        message,
        sender_name=SENDER_NAME,
        sender_agent_card_url=SENDER_CARD_URL,
        sender_type="personal",
        conversation_id=conv_id,
    )


async def ping_contact(contact_name: str) -> str:
    """Check if a contact's agent is online and reachable."""
    return await _contacts.ping(contact_name)


# ─── History ─────────────────────────────────────────────────────────

def get_my_history(query: str) -> str:
    """Search Bob's interaction history for relevant past experiences.
    Use this to recall past purchases, reviews, or recommendations."""
    entries = _history.search(query)
    if not entries:
        return f"No history entries found matching '{query}'."
    lines = []
    for e in entries:
        lines.append(
            f"[{e.timestamp}] {e.type.upper()}: {e.summary} "
            f"(sentiment: {e.sentiment})"
        )
    return "\n".join(lines)
