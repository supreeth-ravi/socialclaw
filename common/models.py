from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Contact(BaseModel):
    """Represents an entry in an agent's contact book."""

    name: str
    type: Literal["personal", "merchant"]
    agent_card_url: str
    description: str
    tags: list[str] = []
    status: Literal["active", "unreachable", "unknown"] = "unknown"


class HistoryEntry(BaseModel):
    """Seeded/recorded past interaction."""

    timestamp: str
    type: Literal["purchase", "recommendation", "inquiry", "review", "research", "note", "preference"]
    summary: str
    details: dict = {}
    contacts_involved: list[str] = []
    sentiment: Literal["positive", "negative", "neutral", "mixed"] = "neutral"
    visibility: Literal["personal", "sharable"] = "personal"


class CatalogItem(BaseModel):
    """Product in a merchant's catalog."""

    id: str
    name: str
    category: str
    description: str
    price: float
    min_price: float
    in_stock: bool = True
    specs: dict = {}
    rating: float = 0.0
    reviews_summary: str = ""


class NegotiationState(BaseModel):
    """Tracks the state of a price negotiation."""

    item_id: str
    item_name: str
    listed_price: float
    current_offer: float
    counter_offer: float | None = None
    rounds: int = 0
    max_rounds: int = 3
    status: Literal["open", "accepted", "rejected", "expired"] = "open"
