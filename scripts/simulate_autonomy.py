"""Simulation script for auto-inbox + social pulse + external A2A pending flow.

Usage:
  DEBUG_SIMULATION=1 uv run python scripts/simulate_autonomy.py \
    --base http://localhost:8080 \
    --email you@example.com --password YOURPASS \
    --sender claude --recipient supreeth \
    --external-name GiftVoucherMerchantAgent \
    --external-url http://app.codeshwar.com:9204/.well-known/agent-card.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time

import httpx


def login(base: str, email: str, password: str) -> str:
    resp = httpx.post(f"{base}/api/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()
    return resp.json()["token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def patch_agent_settings(base: str, token: str, auto_inbox: bool, social_pulse: bool, freq: str) -> None:
    resp = httpx.patch(
        f"{base}/api/auth/agent-profile",
        headers=auth_headers(token),
        json={
            "agent_instructions": "",
            "agent_skills": "",
            "auto_inbox_enabled": auto_inbox,
            "social_pulse_enabled": social_pulse,
            "social_pulse_frequency": freq,
        },
    )
    resp.raise_for_status()


def debug_route_local(base: str, token: str, sender: str, target: str, message: str) -> None:
    resp = httpx.post(
        f"{base}/api/debug/route-local",
        headers=auth_headers(token),
        json={"sender": sender, "target": target, "message": message},
    )
    resp.raise_for_status()


def send_external_inbound(base: str, sender_name: str, url: str, recipient: str, message: str) -> None:
    resp = httpx.post(
        f"{base}/api/a2a/inbound",
        json={
            "recipient_handle": recipient,
            "sender_name": sender_name,
            "agent_card_url": url,
            "message": message,
            "sender_type": "personal",
        },
    )
    resp.raise_for_status()


def get_contacts(base: str, token: str) -> list[dict]:
    resp = httpx.get(f"{base}/api/contacts", headers=auth_headers(token))
    resp.raise_for_status()
    return resp.json()


def approve_contact(base: str, token: str, contact_id: int) -> None:
    resp = httpx.post(f"{base}/api/contacts/{contact_id}/approve", headers=auth_headers(token))
    resp.raise_for_status()


def force_social_pulse(db_path: str, handle: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE scheduled_tasks SET trigger_at = datetime('now','-1 minute') WHERE id = ?",
            (f"social_{handle}",),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--sender", required=True)
    ap.add_argument("--recipient", required=True)
    ap.add_argument("--external-name", required=True)
    ap.add_argument("--external-url", required=True)
    ap.add_argument("--db", default="/Users/supreethravi/phronetics/ai.social/app/data/ai_social.db")
    args = ap.parse_args()

    print("Logging in...")
    token = login(args.base, args.email, args.password)

    print("Enabling auto inbox + social pulse...")
    patch_agent_settings(args.base, token, True, True, "daily")

    print("Triggering platform-to-platform auto-inbox...")
    debug_route_local(
        args.base,
        token,
        sender=args.sender,
        target=args.recipient,
        message="Hey! Quick check-in from platform user.",
    )

    print("Sending external inbound (should be pending)...")
    send_external_inbound(
        args.base,
        args.external_name,
        args.external_url,
        args.recipient,
        "External agent checking in.",
    )

    print("Approving pending contact...")
    contacts = get_contacts(args.base, token)
    pending = [c for c in contacts if c.get("status") == "pending" and c.get("agent_card_url") == args.external_url]
    if pending:
        approve_contact(args.base, token, pending[0]["id"])
    else:
        print("No pending contact found to approve.")

    print("Resending external inbound (should auto-respond)...")
    send_external_inbound(
        args.base,
        args.external_name,
        args.external_url,
        args.recipient,
        "External agent follow-up after approval.",
    )

    print("Forcing social pulse to run now...")
    force_social_pulse(args.db, args.recipient)

    print("Waiting 10 seconds for scheduler to pick up social pulse...")
    time.sleep(10)
    print("Done. Check Inbox + Tasks UI for activity.")


if __name__ == "__main__":
    main()
