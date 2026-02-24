"""Verify all agent cards are reachable."""

import asyncio
import sys

import httpx

AGENTS = {
    "Alice": "http://localhost:8001/.well-known/agent.json",
    "Bob": "http://localhost:8002/.well-known/agent.json",
    "SoleStyle Shoes": "http://localhost:8010/.well-known/agent.json",
    "TechMart Electronics": "http://localhost:8011/.well-known/agent.json",
    "FreshBite Grocery": "http://localhost:8012/.well-known/agent.json",
}


async def ping_all() -> bool:
    all_ok = True
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in AGENTS.items():
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    card = resp.json()
                    print(f"  [OK] {name:25s} — {card.get('name', '?')}")
                else:
                    print(f"  [FAIL] {name:25s} — HTTP {resp.status_code}")
                    all_ok = False
            except Exception as e:
                print(f"  [FAIL] {name:25s} — {e}")
                all_ok = False
    return all_ok


def main() -> None:
    print("Pinging all AI Social agents...\n")
    ok = asyncio.run(ping_all())
    print()
    if ok:
        print("All agents are reachable!")
    else:
        print("Some agents are unreachable. Make sure all agents are running.")
        sys.exit(1)


if __name__ == "__main__":
    main()
