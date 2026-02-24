"""Seed Claude as a platform user with history and mutual friendship with Supreeth."""

import uuid
from app.database import get_db, init_db
from app.config import DB_PATH

init_db()
conn = get_db()

# ─── 1. Create Claude user ──────────────────────────────────────
claude_id = uuid.uuid4().hex
try:
    conn.execute(
        """INSERT OR IGNORE INTO users (id, email, handle, password_hash, display_name, is_onboarded)
           VALUES (?, ?, ?, ?, ?, 1)""",
        (claude_id, "claude@phronetic.ai", "claude", "seeded-no-login", "Claude"),
    )
    print("Created user: claude")
except Exception as e:
    print(f"User may already exist: {e}")

# ─── 2. Register Claude's agent ─────────────────────────────────
try:
    conn.execute(
        """INSERT OR IGNORE INTO agents (id, name, type, description, is_local)
           VALUES (?, ?, ?, ?, 1)""",
        ("claude", "Claude", "personal",
         "AI researcher, audio nerd, foodie, running hobbyist. Gives thoughtful recommendations."),
    )
    print("Registered agent: claude")
except Exception as e:
    print(f"Agent may already exist: {e}")

# ─── 3. Add Claude as friend for Supreeth ───────────────────────
try:
    conn.execute(
        """INSERT OR IGNORE INTO contacts (owner_agent_id, name, type, agent_card_url, description, tags, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("supreeth", "Claude", "personal", "platform://user/claude",
         "AI researcher, audio nerd, foodie, running hobbyist",
         '["friend","tech","audio","food","running","ai"]', "active"),
    )
    print("Added Claude as friend for supreeth")
except Exception as e:
    print(f"Contact may already exist: {e}")

# ─── 4. Add Supreeth as friend for Claude ───────────────────────
try:
    conn.execute(
        """INSERT OR IGNORE INTO contacts (owner_agent_id, name, type, agent_card_url, description, tags, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("claude", "Supreeth", "personal", "platform://user/supreeth",
         "Friend on AI Social platform",
         '["friend"]', "active"),
    )
    print("Added Supreeth as friend for claude")
except Exception as e:
    print(f"Contact may already exist: {e}")

# ─── 5. Add merchants as contacts for Claude ────────────────────
merchants = [
    ("SoleStyle", "merchant", "http://localhost:8010/.well-known/agent-card.json",
     "Premium shoe store", '["shoes","running","sneakers","footwear"]'),
    ("TechMart", "merchant", "http://localhost:8011/.well-known/agent-card.json",
     "Electronics and gadgets", '["electronics","tech","audio","gadgets"]'),
    ("FreshBite", "merchant", "http://localhost:8012/.well-known/agent-card.json",
     "Fresh food delivery and meal kits", '["food","meals","groceries","cooking"]'),
]
for name, ctype, url, desc, tags in merchants:
    try:
        conn.execute(
            """INSERT OR IGNORE INTO contacts (owner_agent_id, name, type, agent_card_url, description, tags, status)
               VALUES (?, ?, ?, ?, ?, ?, 'unknown')""",
            ("claude", name, ctype, url, desc, tags),
        )
        print(f"Added {name} as contact for claude")
    except Exception as e:
        print(f"  skip {name}: {e}")

# ─── 6. Seed Claude's interaction history ────────────────────────
history_entries = [
    ("2025-01-10T14:30:00", "purchase",
     "Bought Sony WH-1000XM5 headphones from TechMart for $328 (negotiated down from $399). Outstanding noise cancellation, best I've owned.",
     '{"product": "Sony WH-1000XM5", "price": 328, "merchant": "TechMart", "rating": 5}',
     '["TechMart"]', "positive"),

    ("2025-01-18T10:15:00", "purchase",
     "Got Nike Pegasus 41 running shoes from SoleStyle for $119. Great cushioning for a beginner runner. Went half size up.",
     '{"product": "Nike Pegasus 41", "price": 119, "merchant": "SoleStyle", "rating": 4}',
     '["SoleStyle"]', "positive"),

    ("2025-01-25T19:00:00", "purchase",
     "Ordered Mediterranean meal kit from FreshBite for $12.99. Ingredients were super fresh, recipe was easy to follow. Made it for dinner party — everyone loved it.",
     '{"product": "Mediterranean Meal Kit", "price": 12.99, "merchant": "FreshBite", "rating": 5}',
     '["FreshBite"]', "positive"),

    ("2025-02-01T11:00:00", "review",
     "After 3 weeks with the XM5s: battery lasts 30+ hours, multipoint connection is great for switching between laptop and phone. Only downside — they get warm after 2 hours.",
     '{"product": "Sony WH-1000XM5", "type": "long-term-review"}',
     '[]', "positive"),

    ("2025-02-05T16:30:00", "recommendation",
     "Told a friend about SoleStyle — they had great customer service when I needed to exchange sizes. Bob also shops there and rates them highly.",
     '{"merchant": "SoleStyle", "context": "friend recommendation"}',
     '["SoleStyle"]', "positive"),

    ("2025-02-08T09:00:00", "purchase",
     "Bought Anker Soundcore Space A40 earbuds from TechMart for $69 (listed $79, negotiated 12% off). Surprisingly good ANC for the price. Great gym earbuds.",
     '{"product": "Anker Soundcore Space A40", "price": 69, "merchant": "TechMart", "rating": 4}',
     '["TechMart"]', "positive"),

    ("2025-02-10T20:00:00", "purchase",
     "Tried FreshBite's Asian Fusion box — $14.99, pad thai and spring rolls. Pad thai was excellent, spring rolls were just okay. Would order pad thai separately next time.",
     '{"product": "Asian Fusion Box", "price": 14.99, "merchant": "FreshBite", "rating": 3}',
     '["FreshBite"]', "mixed"),

    ("2025-02-12T13:00:00", "research",
     "Researching mechanical keyboards for coding. Looking at Keychron Q1 Pro ($199) vs HHKB Professional ($280). Leaning Keychron for the value but HHKB Topre switches are tempting.",
     '{"category": "keyboards", "options": ["Keychron Q1 Pro", "HHKB Professional"]}',
     '[]', "neutral"),
]

for ts, htype, summary, details, contacts_involved, sentiment in history_entries:
    conn.execute(
        """INSERT INTO history (owner_agent_id, timestamp, type, summary, details_json, contacts_involved, sentiment)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("claude", ts, htype, summary, details, contacts_involved, sentiment),
    )
print(f"Seeded {len(history_entries)} history entries for claude")

conn.commit()
conn.close()
print("\nDone! Claude is ready on the platform.")
