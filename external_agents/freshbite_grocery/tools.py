from __future__ import annotations

import json
from pathlib import Path

from common.models import CatalogItem
from common.negotiation import evaluate_offer

_CATALOG_FILE = Path(__file__).parent / "catalog.json"
_POLICY_FILE = Path(__file__).parent / "negotiation_policy.json"
_catalog: list[CatalogItem] | None = None
_policy: dict | None = None


def _load_catalog() -> list[CatalogItem]:
    global _catalog
    if _catalog is None:
        data = json.loads(_CATALOG_FILE.read_text())
        _catalog = [CatalogItem(**item) for item in data]
    return _catalog


def _load_policy() -> dict:
    global _policy
    if _policy is None:
        _policy = json.loads(_POLICY_FILE.read_text())
    return _policy


def search_catalog(query: str, category: str = "", max_price: float = 0) -> str:
    """Search the Whole Foods grocery catalog by keyword. Optionally filter by category or maximum price."""
    catalog = _load_catalog()
    results = []
    query_lower = query.lower()
    for item in catalog:
        text = f"{item.name} {item.description} {item.category}".lower()
        if query_lower and not any(w in text for w in query_lower.split()):
            continue
        if category and item.category.lower() != category.lower():
            continue
        if max_price > 0 and item.price > max_price:
            continue
        results.append(item)

    if not results:
        return "No products found matching your criteria."

    lines = []
    for item in results:
        stock = "In Stock" if item.in_stock else "Out of Stock"
        lines.append(
            f"- {item.name} (ID: {item.id}) | ${item.price:.2f} | "
            f"{item.category} | {stock} | Rating: {item.rating}/5"
        )
    return "\n".join(lines)


def get_product_details(product_id: str) -> str:
    """Get detailed information about a specific product by its ID."""
    catalog = _load_catalog()
    for item in catalog:
        if item.id.upper() == product_id.upper():
            return (
                f"Name: {item.name}\n"
                f"ID: {item.id}\n"
                f"Category: {item.category}\n"
                f"Description: {item.description}\n"
                f"Price: ${item.price:.2f}\n"
                f"In Stock: {'Yes' if item.in_stock else 'No'}\n"
                f"Specs: {json.dumps(item.specs)}\n"
                f"Rating: {item.rating}/5\n"
                f"Reviews: {item.reviews_summary}"
            )
    return f"Product '{product_id}' not found."


def check_inventory(product_id: str) -> str:
    """Check if a product is currently in stock."""
    catalog = _load_catalog()
    for item in catalog:
        if item.id.upper() == product_id.upper():
            if item.in_stock:
                return f"{item.name} is in stock and available for purchase."
            return f"{item.name} is currently out of stock."
    return f"Product '{product_id}' not found in catalog."


def quote_price(product_id: str, quantity: int = 1) -> str:
    """Generate a price quote for a product. Specify quantity for bulk pricing."""
    catalog = _load_catalog()
    policy = _load_policy()
    for item in catalog:
        if item.id.upper() == product_id.upper():
            unit_price = item.price
            if quantity >= 2:
                discount = policy.get("max_discount_bulk_pct", 15) / 100
                unit_price = round(item.price * (1 - discount), 2)
                unit_price = max(unit_price, item.min_price)
            total = round(unit_price * quantity, 2)
            return (
                f"Quote for {item.name}:\n"
                f"  Unit price: ${unit_price:.2f}\n"
                f"  Quantity: {quantity}\n"
                f"  Total: ${total:.2f}"
            )
    return f"Product '{product_id}' not found."


def check_negotiation_policy(product_id: str, offered_price: float) -> str:
    """Check if an offered price is acceptable per our negotiation policy. Returns accept, counter, or reject."""
    catalog = _load_catalog()
    for item in catalog:
        if item.id.upper() == product_id.upper():
            result = evaluate_offer(item, offered_price)
            decision = result["decision"]
            reason = result["reason"]
            if decision == "accept":
                final = result.get("final_price", offered_price)
                return f"ACCEPT: We can sell {item.name} at ${final:.2f}. {reason}"
            elif decision == "counter":
                counter = result["counter_price"]
                return f"COUNTER: {reason} Our counter-offer for {item.name} is ${counter:.2f}."
            else:
                return f"REJECT: {reason}"
    return f"Product '{product_id}' not found."


def get_customer_reviews(product_id: str) -> str:
    """Get customer reviews summary for a product."""
    catalog = _load_catalog()
    for item in catalog:
        if item.id.upper() == product_id.upper():
            return (
                f"Reviews for {item.name}:\n"
                f"  Rating: {item.rating}/5\n"
                f"  Summary: {item.reviews_summary}"
            )
    return f"Product '{product_id}' not found."
