from __future__ import annotations

from .models import CatalogItem, NegotiationState


# In-memory negotiation sessions keyed by (merchant, item_id)
_sessions: dict[tuple[str, str], NegotiationState] = {}


def start_negotiation(
    merchant: str, item: CatalogItem, offer: float
) -> NegotiationState:
    """Start a new negotiation session."""
    state = NegotiationState(
        item_id=item.id,
        item_name=item.name,
        listed_price=item.price,
        current_offer=offer,
        rounds=1,
    )
    _sessions[(merchant, item.id)] = state
    return state


def get_session(merchant: str, item_id: str) -> NegotiationState | None:
    return _sessions.get((merchant, item_id))


def evaluate_offer(item: CatalogItem, offered_price: float) -> dict:
    """Evaluate an offer against the item's pricing policy.

    Returns a dict with 'decision' (accept/counter/reject) and reasoning.
    """
    if offered_price >= item.price:
        return {
            "decision": "accept",
            "final_price": item.price,
            "reason": "Offer meets or exceeds listed price.",
        }

    if offered_price >= item.min_price:
        # Accept if within 5% of listed price, otherwise counter
        if offered_price >= item.price * 0.95:
            return {
                "decision": "accept",
                "final_price": offered_price,
                "reason": "Offer is within acceptable range.",
            }
        # Counter with a midpoint between offer and listed price
        counter = round((offered_price + item.price) / 2, 2)
        counter = max(counter, item.min_price)
        return {
            "decision": "counter",
            "counter_price": counter,
            "reason": f"We can meet you at ${counter:.2f}.",
        }

    # Below minimum price
    counter = item.min_price
    return {
        "decision": "counter",
        "counter_price": counter,
        "reason": f"Our lowest possible price is ${counter:.2f}.",
    }


def process_round(
    state: NegotiationState, item: CatalogItem, new_offer: float
) -> dict:
    """Process a new round of negotiation."""
    state.current_offer = new_offer
    state.rounds += 1

    if state.rounds > state.max_rounds:
        state.status = "expired"
        return {
            "decision": "final_offer",
            "final_price": item.min_price,
            "reason": f"Maximum negotiation rounds reached. Final offer: ${item.min_price:.2f}.",
        }

    result = evaluate_offer(item, new_offer)
    if result["decision"] == "accept":
        state.status = "accepted"
    return result
