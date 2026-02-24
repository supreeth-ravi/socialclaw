"""Simulation engine — generates social activity for demos.

Merchants send promos, friends share discoveries, friends ask questions.
Delivers messages via InboxStore.
"""

from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path

from ..database import get_db
from .inbox import InboxStore

logger = logging.getLogger(__name__)

# ─── Message templates ───────────────────────────────────────────

MERCHANT_PROMOS = {
    "SoleStyle": [
        "Flash Sale! 30% off all running shoes this weekend only!",
        "New arrival: Nike Air Zoom Pegasus 41 — just landed in store!",
        "Member exclusive: Buy 2 pairs, get 20% off your entire order.",
        "Limited stock alert: Adidas Ultraboost Light in your favorite colors.",
        "End of season clearance — up to 50% off select styles!",
    ],
    "TechMart": [
        "Deal of the day: Sony WH-1000XM5 headphones — $50 off!",
        "New in stock: MacBook Pro M4 — pre-order now with free AirPods.",
        "Weekend special: 25% off all smartwatches!",
        "Just arrived: Samsung Galaxy S25 Ultra — come check it out!",
        "Clearance: Last gen iPads starting at $299.",
    ],
    "FreshBite": [
        "Fresh catch today! Wild salmon and organic greens — perfect dinner combo.",
        "New meal kit: Mediterranean Bowl — everything you need for $12.99!",
        "Weekend brunch box: Artisan bread, farm eggs, smoked salmon. Order by Friday!",
        "Seasonal special: Organic strawberries are in! $4.99/lb this week only.",
        "Free delivery on orders over $50 this weekend!",
    ],
}

FRIEND_SHARE_TEMPLATES = [
    "Just bought {product} from {merchant} — really impressed with the quality!",
    "Hey, wanted to let you know {merchant} has a great deal on {product} right now.",
    "Been using my new {product} from {merchant} for a week. Totally worth it!",
    "Thought of you — {merchant} just got some new {product} in stock.",
]

FRIEND_QUESTION_TEMPLATES = [
    "Have you tried anything from {merchant} lately? Thinking about checking them out.",
    "Looking for a good {category} — any recommendations?",
    "What do you think about {merchant}? Worth shopping there?",
    "Need some advice — have you bought {category} recently?",
]

PRODUCTS = {
    "SoleStyle": ["running shoes", "sneakers", "hiking boots", "casual shoes"],
    "TechMart": ["wireless earbuds", "smartwatch", "laptop", "tablet"],
    "FreshBite": ["meal kits", "organic produce", "artisan bread", "fresh seafood"],
}

CATEGORIES = ["shoes", "electronics", "headphones", "groceries", "meal kits", "sneakers"]


class SimulationEngine:
    """Runs periodic social activity simulation."""

    def __init__(self, inbox_store: InboxStore, db_path: str | Path, interval: int = 120) -> None:
        self.inbox = inbox_store
        self.db_path = db_path
        self.interval = interval
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())
        logger.info("SimulationEngine started (interval=%ds)", self.interval)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SimulationEngine stopped")

    async def _loop(self) -> None:
        # Wait a bit before first action
        await asyncio.sleep(30)
        while True:
            try:
                await self._act()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Simulation error")
            await asyncio.sleep(self.interval)

    async def _act(self) -> None:
        users = self._get_users()
        if not users:
            return

        action = random.choice(["merchant_promo", "friend_share", "friend_question"])

        if action == "merchant_promo":
            await self._merchant_promo(users)
        elif action == "friend_share":
            await self._friend_share(users)
        else:
            await self._friend_question(users)

    def _conv_id(self, a: str, b: str) -> str:
        """Deterministic conversation ID — same pair always shares one thread."""
        return "conv_" + "_".join(sorted([a.lower(), b.lower()]))

    async def _merchant_promo(self, users: list[dict]) -> None:
        merchant = random.choice(list(MERCHANT_PROMOS.keys()))
        promo = random.choice(MERCHANT_PROMOS[merchant])

        # Find users who have this merchant as a contact
        for user in users:
            handle = user["handle"]
            conn = get_db(self.db_path)
            try:
                row = conn.execute(
                    "SELECT 1 FROM contacts WHERE owner_agent_id = ? AND name = ?",
                    (handle, merchant),
                ).fetchone()
            finally:
                conn.close()
            if row:
                conv_id = self._conv_id(merchant, handle)
                self.inbox.ensure_conversation(conv_id, merchant, handle)
                self.inbox.deliver(
                    recipient_id=handle,
                    sender_name=merchant,
                    sender_type="merchant",
                    message=promo,
                    conversation_id=conv_id,
                    direction="inbound",
                )
                logger.info("Sim: %s sent promo to %s", merchant, handle)
                break  # One promo per cycle

    def _deliver_friend_message(self, sender_handle: str, recipient_handle: str,
                                sender_name: str, message: str) -> None:
        """Deliver a friend message with outbound copy for sender + inbound for recipient."""
        conv_id = self._conv_id(sender_handle, recipient_handle)
        self.inbox.ensure_conversation(conv_id, sender_handle, recipient_handle)
        # Outbound copy for sender's view
        self.inbox.deliver(
            recipient_id=sender_handle,
            sender_name=sender_handle,
            sender_type="friend",
            message=message,
            conversation_id=conv_id,
            direction="outbound",
        )
        # Inbound copy for recipient
        self.inbox.deliver(
            recipient_id=recipient_handle,
            sender_name=sender_name,
            sender_type="friend",
            message=message,
            conversation_id=conv_id,
            direction="inbound",
        )

    async def _friend_share(self, users: list[dict]) -> None:
        if len(users) < 2:
            return
        sender, recipient = random.sample(users, 2)
        merchant = random.choice(list(PRODUCTS.keys()))
        product = random.choice(PRODUCTS[merchant])
        template = random.choice(FRIEND_SHARE_TEMPLATES)
        message = template.format(product=product, merchant=merchant)

        sender_name = sender["display_name"] or sender["handle"]
        self._deliver_friend_message(sender["handle"], recipient["handle"], sender_name, message)
        logger.info("Sim: %s shared with %s", sender["handle"], recipient["handle"])

    async def _friend_question(self, users: list[dict]) -> None:
        if len(users) < 2:
            return
        sender, recipient = random.sample(users, 2)
        merchant = random.choice(list(PRODUCTS.keys()))
        category = random.choice(CATEGORIES)
        template = random.choice(FRIEND_QUESTION_TEMPLATES)
        message = template.format(merchant=merchant, category=category)

        sender_name = sender["display_name"] or sender["handle"]
        self._deliver_friend_message(sender["handle"], recipient["handle"], sender_name, message)
        logger.info("Sim: %s asked %s a question", sender["handle"], recipient["handle"])

    def _get_users(self) -> list[dict]:
        conn = get_db(self.db_path)
        try:
            rows = conn.execute("SELECT handle, display_name FROM users").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
