"""Migrate JSON data → SQLite and register all known agents.

Usage:
    python -m app.migrate
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from .config import DB_PATH
from .database import get_db, init_db
from .auth import hash_password


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Agent definitions to register
AGENTS = [
    {
        "id": "alice",
        "name": "Priya",
        "type": "personal",
        "description": "Priya's personal AI assistant — budget-conscious, eco-friendly, thorough researcher",
        "agent_card_url": "http://localhost:8001/.well-known/agent-card.json",
        "host": "localhost",
        "port": 8001,
        "is_local": True,
        "skills_json": "[]",
    },
    {
        "id": "bob",
        "name": "Arjun",
        "type": "personal",
        "description": "Arjun's personal AI assistant — sneaker enthusiast, tech gadget lover, honest reviewer",
        "agent_card_url": "http://localhost:8002/.well-known/agent-card.json",
        "host": "localhost",
        "port": 8002,
        "is_local": True,
        "skills_json": "[]",
    },
    {
        "id": "solestyle",
        "name": "Foot Locker",
        "type": "merchant",
        "description": "Premium footwear retailer with Nike, Adidas, New Balance",
        "agent_card_url": "http://localhost:8010/.well-known/agent-card.json",
        "host": "localhost",
        "port": 8010,
        "is_local": False,
        "skills_json": '["footwear", "shoes", "negotiation"]',
    },
    {
        "id": "techmart",
        "name": "Best Buy",
        "type": "merchant",
        "description": "Electronics retailer with phones, laptops, accessories",
        "agent_card_url": "http://localhost:8011/.well-known/agent-card.json",
        "host": "localhost",
        "port": 8011,
        "is_local": False,
        "skills_json": '["electronics", "tech", "gadgets"]',
    },
    {
        "id": "freshbite",
        "name": "Whole Foods",
        "type": "merchant",
        "description": "Organic grocery store with fresh produce and health foods",
        "agent_card_url": "http://localhost:8012/.well-known/agent-card.json",
        "host": "localhost",
        "port": 8012,
        "is_local": False,
        "skills_json": '["grocery", "food", "organic"]',
    },
]

SEED_USERS = [
    {
        "handle": "alice",
        "display_name": "Priya",
        "email": "alice@ai.social",
    },
    {
        "handle": "bob",
        "display_name": "Arjun",
        "email": "bob@ai.social",
    },
]


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def migrate() -> None:
    print(f"Initializing database at {DB_PATH}")
    init_db()

    conn = get_db()
    try:
        # Register agents
        for agent in AGENTS:
            conn.execute(
                """INSERT OR REPLACE INTO agents
                   (id, name, type, description, agent_card_url, host, port, is_local, skills_json)
                   VALUES (:id, :name, :type, :description, :agent_card_url, :host, :port, :is_local, :skills_json)""",
                agent,
            )
        print(f"  Registered {len(AGENTS)} agents")

        # Seed platform users (for discovery)
        for user in SEED_USERS:
            conn.execute(
                """INSERT OR IGNORE INTO users
                   (id, email, handle, password_hash, display_name, is_onboarded)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (
                    str(uuid.uuid4()),
                    user["email"],
                    user["handle"],
                    hash_password("test1234"),
                    user["display_name"],
                ),
            )
        print(f"  Seeded {len(SEED_USERS)} platform users")

        conn.commit()
        print("Migration complete!")

    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
