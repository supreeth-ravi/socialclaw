"""Seed the platform with clean demo data.

Resets contacts, history, messages, tasks, and chat sessions, then creates:
- 4 users: supreeth, ravi, priya (handle: alice), arjun (handle: bob)
- Mutual friendships between all 4
- 3 merchants (Foot Locker, Best Buy, Whole Foods) for each user
- Rich interaction history for each user

Usage:
    uv run python seed_platform.py
"""

import uuid
from app.database import get_db, init_db
from app.config import DB_PATH
from app.auth import hash_password

init_db()
conn = get_db()

# ═══════════════════════════════════════════════════════════════════
# Step 1: Clean slate
# ═══════════════════════════════════════════════════════════════════
print("Cleaning existing data...")
for table in [
    "contacts",
    "history",
    "inbound_messages",
    "conversations",
    "tasks",
    "scheduled_tasks",
    "chat_messages",
    "chat_sessions",
]:
    conn.execute(f"DELETE FROM {table}")
    print(f"  Cleared {table}")

# Remove the claude user and agent (test account, no longer needed)
conn.execute("DELETE FROM users WHERE handle = 'claude'")
conn.execute("DELETE FROM agents WHERE id = 'claude'")
print("  Removed claude user/agent")
conn.commit()

# ═══════════════════════════════════════════════════════════════════
# Step 2: Ensure 4 users exist
# ═══════════════════════════════════════════════════════════════════
print("\nCreating users...")
USERS = [
    {
        "handle": "supreeth",
        "display_name": "Boss",
        "email": "supreeth.ravi@phronetic.ai",
    },
    {
        "handle": "ravi",
        "display_name": "Ravi",
        "email": "supreethsen@gmail.com",
    },
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

for user in USERS:
    conn.execute(
        """INSERT OR IGNORE INTO users (id, email, handle, password_hash, display_name, is_onboarded)
           VALUES (?, ?, ?, ?, ?, 1)""",
        (
            str(uuid.uuid4()),
            user["email"],
            user["handle"],
            hash_password("test1234"),
            user["display_name"],
        ),
    )
    # Update display name for existing users
    conn.execute(
        "UPDATE users SET display_name = ? WHERE handle = ?",
        (user["display_name"], user["handle"]),
    )
    print(f"  {user['handle']} ({user['display_name']})")

# Ensure agents are registered for personal users
PERSONAL_AGENTS = [
    ("alice", "Priya", "personal", "Budget-conscious, eco-friendly, thorough researcher",
     "http://localhost:8001/.well-known/agent-card.json", "localhost", 8001),
    ("bob", "Arjun", "personal", "Sneaker enthusiast, tech gadget lover, honest reviewer",
     "http://localhost:8002/.well-known/agent-card.json", "localhost", 8002),
]
for aid, name, atype, desc, url, host, port in PERSONAL_AGENTS:
    conn.execute(
        """INSERT OR REPLACE INTO agents (id, name, type, description, agent_card_url, host, port, is_local)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
        (aid, name, atype, desc, url, host, port),
    )

# Update merchant agent names in agents table
MERCHANT_AGENTS = [
    ("solestyle", "Foot Locker", "Premium footwear retailer with Nike, Adidas, New Balance"),
    ("techmart", "Best Buy", "Electronics retailer with phones, laptops, accessories"),
    ("freshbite", "Whole Foods", "Organic grocery store with fresh produce and health foods"),
]
for aid, name, desc in MERCHANT_AGENTS:
    conn.execute(
        "UPDATE agents SET name = ?, description = ? WHERE id = ?",
        (name, desc, aid),
    )

conn.commit()

# ═══════════════════════════════════════════════════════════════════
# Step 3: Mutual friendships (all 4 users are friends with each other)
# ═══════════════════════════════════════════════════════════════════
print("\nCreating mutual friendships...")
FRIEND_DESCRIPTIONS = {
    "supreeth": "Boss — primary platform user",
    "ravi": "Friend on AI Social platform",
    "alice": "Budget-conscious, eco-friendly shopper",
    "bob": "Sneaker enthusiast, tech gadget lover",
}

handles = [u["handle"] for u in USERS]
display_names = {u["handle"]: u["display_name"] for u in USERS}
friend_count = 0

for owner in handles:
    for friend in handles:
        if owner == friend:
            continue
        conn.execute(
            """INSERT OR IGNORE INTO contacts
               (owner_agent_id, name, type, agent_card_url, description, tags, status)
               VALUES (?, ?, 'personal', ?, ?, '["friend","platform-user"]', 'active')""",
            (
                owner,
                display_names[friend],
                f"platform://user/{friend}",
                FRIEND_DESCRIPTIONS[friend],
            ),
        )
        friend_count += 1

print(f"  Created {friend_count} friend contacts")
conn.commit()

# ═══════════════════════════════════════════════════════════════════
# Step 4: Add 3 merchants to all users
# ═══════════════════════════════════════════════════════════════════
print("\nAdding merchant contacts...")
MERCHANTS = [
    (
        "Foot Locker",
        "http://localhost:8010/.well-known/agent-card.json",
        "Premium footwear retailer with Nike, Adidas, New Balance",
        '["shoes","footwear","running","sneakers","merchant"]',
    ),
    (
        "Best Buy",
        "http://localhost:8011/.well-known/agent-card.json",
        "Electronics retailer with phones, laptops, accessories",
        '["electronics","tech","headphones","laptops","phones","merchant"]',
    ),
    (
        "Whole Foods",
        "http://localhost:8012/.well-known/agent-card.json",
        "Organic grocery store with fresh produce and health foods",
        '["food","grocery","meals","organic","merchant"]',
    ),
]

merchant_count = 0
for owner in handles:
    for name, url, desc, tags in MERCHANTS:
        conn.execute(
            """INSERT OR IGNORE INTO contacts
               (owner_agent_id, name, type, agent_card_url, description, tags, status)
               VALUES (?, ?, 'merchant', ?, ?, ?, 'unknown')""",
            (owner, name, url, desc, tags),
        )
        merchant_count += 1

print(f"  Created {merchant_count} merchant contacts")
conn.commit()

# ═══════════════════════════════════════════════════════════════════
# Step 5: Pre-seed history
# ═══════════════════════════════════════════════════════════════════
print("\nSeeding interaction history...")


def seed_history(owner: str, entries: list[tuple]) -> None:
    for ts, htype, summary, details, contacts_involved, sentiment in entries:
        conn.execute(
            """INSERT INTO history
               (owner_agent_id, timestamp, type, summary, details_json, contacts_involved, sentiment)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (owner, ts, htype, summary, details, contacts_involved, sentiment),
        )
    print(f"  {owner}: {len(entries)} entries")


# ─── Supreeth (Boss) ────────────────────────────────────────────
seed_history("supreeth", [
    (
        "2025-01-12T15:30:00", "purchase",
        "Bought Sony WH-1000XM5 from Best Buy for $320 (negotiated from $349). Great ANC, best headphones I've owned.",
        '{"product": "Sony WH-1000XM5", "price": 320, "original_price": 349, "merchant": "Best Buy", "rating": 5}',
        '["Best Buy"]', "positive",
    ),
    (
        "2025-01-20T11:00:00", "purchase",
        "Ordered Wild-Caught Salmon from Whole Foods, $16.50/lb. Excellent quality, perfectly fresh.",
        '{"product": "Wild-Caught Salmon", "price": 16.50, "merchant": "Whole Foods", "rating": 5}',
        '["Whole Foods"]', "positive",
    ),
    (
        "2025-01-28T14:15:00", "inquiry",
        "Asked Priya about laptop recommendations. She suggested MacBook Air M4 for coding — great battery life and performance.",
        '{"topic": "laptop", "recommendation": "MacBook Air M4", "source": "Priya"}',
        '["Priya"]', "neutral",
    ),
    (
        "2025-02-03T09:30:00", "recommendation",
        "Arjun recommended Nike Air Max 90 from Foot Locker. Said they negotiated down to $115 from $130. Looks like a great deal.",
        '{"product": "Nike Air Max 90", "price": 115, "original_price": 130, "source": "Arjun", "merchant": "Foot Locker"}',
        '["Arjun", "Foot Locker"]', "positive",
    ),
    (
        "2025-02-08T08:00:00", "preference",
        "Prefers running shoes with good cushioning. Runs 3x/week, typically 5K distance. Looking for something under $150.",
        '{"activity": "running", "frequency": "3x/week", "distance": "5K", "budget": 150, "priority": "cushioning"}',
        '[]', "neutral",
    ),
])

# ─── Ravi ────────────────────────────────────────────────────────
seed_history("ravi", [
    (
        "2025-01-15T10:00:00", "purchase",
        "Bought Adidas Ultraboost 23 from Foot Locker for $160. Great for long runs, perfect cushioning.",
        '{"product": "Adidas Ultraboost 23", "price": 160, "merchant": "Foot Locker", "rating": 5}',
        '["Foot Locker"]', "positive",
    ),
    (
        "2025-01-22T16:45:00", "purchase",
        "Got AirPods Pro 3 from Best Buy for $235 (negotiated from $249). Good ANC, comfortable fit.",
        '{"product": "AirPods Pro 3", "price": 235, "original_price": 249, "merchant": "Best Buy", "rating": 4}',
        '["Best Buy"]', "positive",
    ),
    (
        "2025-02-01T13:00:00", "inquiry",
        "Asked Arjun about meal kit options. He recommended Whole Foods' Mediterranean box — says it's fresh and easy to cook.",
        '{"topic": "meal kits", "recommendation": "Mediterranean box", "source": "Arjun", "merchant": "Whole Foods"}',
        '["Arjun", "Whole Foods"]', "positive",
    ),
    (
        "2025-02-10T19:30:00", "review",
        "Ultraboost 23 review after 1 month: best running shoe I've ever owned, worth every penny. Cushioning still feels brand new.",
        '{"product": "Adidas Ultraboost 23", "type": "long-term-review", "rating": 5, "duration": "1 month"}',
        '["Foot Locker"]', "positive",
    ),
])

# ─── Priya (handle: alice) ──────────────────────────────────────
seed_history("alice", [
    (
        "2025-01-10T14:00:00", "purchase",
        "Bought Adidas Samba OG from Foot Locker for $95. Classic casual shoe, love the retro look.",
        '{"product": "Adidas Samba OG", "price": 95, "merchant": "Foot Locker", "rating": 4}',
        '["Foot Locker"]', "positive",
    ),
    (
        "2025-01-18T11:30:00", "purchase",
        "Got AirPods Pro 3 from Best Buy for $240. Good ANC for the price, battery life is solid.",
        '{"product": "AirPods Pro 3", "price": 240, "merchant": "Best Buy", "rating": 4}',
        '["Best Buy"]', "positive",
    ),
    (
        "2025-01-25T15:00:00", "inquiry",
        "Asked Arjun about running shoes. He recommended Nike Pegasus for beginners and Ultraboost for serious runners.",
        '{"topic": "running shoes", "recommendations": ["Nike Pegasus", "Adidas Ultraboost"], "source": "Arjun"}',
        '["Arjun"]', "neutral",
    ),
    (
        "2025-02-05T10:00:00", "purchase",
        "Organic Avocado Box from Whole Foods, $11. Fresh and perfectly ripe. Great value for 6 avocados.",
        '{"product": "Organic Avocado Box", "price": 11, "merchant": "Whole Foods", "rating": 5}',
        '["Whole Foods"]', "positive",
    ),
])

# ─── Arjun (handle: bob) ────────────────────────────────────────
seed_history("bob", [
    (
        "2025-01-08T13:00:00", "purchase",
        "Bought Nike Air Max 90 from Foot Locker for $115 (negotiated from $130). Classic sneaker, love the colorway.",
        '{"product": "Nike Air Max 90", "price": 115, "original_price": 130, "merchant": "Foot Locker", "rating": 5}',
        '["Foot Locker"]', "positive",
    ),
    (
        "2025-01-20T18:00:00", "review",
        "Air Max 90 after 3 weeks: comfortable, stylish, sole was stiff first week but broke in nicely. Great daily wear.",
        '{"product": "Nike Air Max 90", "type": "long-term-review", "rating": 4, "duration": "3 weeks"}',
        '["Foot Locker"]', "positive",
    ),
    (
        "2025-01-30T10:30:00", "purchase",
        "Bought Adidas Ultraboost 23 from Foot Locker for $160. No negotiation needed, was already on sale. Amazing for running.",
        '{"product": "Adidas Ultraboost 23", "price": 160, "merchant": "Foot Locker", "rating": 5, "note": "on sale"}',
        '["Foot Locker"]', "positive",
    ),
    (
        "2025-02-04T14:00:00", "purchase",
        "iPhone 16 Pro from Best Buy for $960 (negotiated from $999). Great camera, ProMotion display is buttery smooth.",
        '{"product": "iPhone 16 Pro", "price": 960, "original_price": 999, "merchant": "Best Buy", "rating": 5}',
        '["Best Buy"]', "positive",
    ),
    (
        "2025-02-09T11:00:00", "recommendation",
        "Recommended Foot Locker to friends. Best shoe selection on the platform, prices are negotiable, and customer service is excellent.",
        '{"merchant": "Foot Locker", "context": "general recommendation", "aspects": ["selection", "pricing", "service"]}',
        '["Foot Locker"]', "positive",
    ),
])

conn.commit()
conn.close()

# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 50)
print("Platform seeded successfully!")
print("=" * 50)
print(f"  Users: {len(USERS)} (supreeth, ravi, priya, arjun)")
print(f"  Friend contacts: {friend_count}")
print(f"  Merchant contacts: {merchant_count}")
print(f"  History entries: 18 total (5+4+4+5)")
print("\nCredentials: all users use password 'test1234'")
print("Login as: supreeth.ravi@phronetic.ai / test1234")
