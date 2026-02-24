"""Demo script: send real tasks to agents to demonstrate intelligent A2A collaboration.

Shows that agents are smart about WHEN to contact others vs. handle things solo.
Requires all agents to be running (use scripts/run_all.sh first).

Each scenario sends a real message via JSON-RPC, which triggers real Gemini LLM calls
inside the agent. The agent reasons about the task, decides whether to involve contacts,
and responds.
"""

import asyncio
import sys
import uuid

import httpx

AGENT_URLS = {
    "alice": "http://localhost:8001/",
    "bob": "http://localhost:8002/",
    "solestyle": "http://localhost:8010/",
    "techmart": "http://localhost:8011/",
    "freshbite": "http://localhost:8012/",
}


async def send_message(
    client: httpx.AsyncClient, agent_url: str, message: str
) -> dict:
    """Send a JSON-RPC message/send to an agent and return the response."""
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [{"kind": "text", "text": message}],
            },
        },
    }
    resp = await client.post(agent_url, json=payload, timeout=180.0)
    return resp.json()


def extract_text(response: dict) -> str:
    """Extract the text content from a JSON-RPC response."""
    result = response.get("result", {})

    texts = []

    # Task-based response (status message)
    if "status" in result:
        msg = result["status"].get("message", {})
        if msg:
            for part in msg.get("parts", []):
                if "text" in part:
                    texts.append(part["text"])

    # Artifact-based response
    for artifact in result.get("artifacts", []):
        for part in artifact.get("parts", []):
            if "text" in part:
                texts.append(part["text"])

    if texts:
        return "\n".join(texts)

    error = response.get("error", {})
    if error:
        return f"[ERROR] {error.get('message', str(error))}"

    return f"[RAW] {response}"


def print_scenario(num: int, title: str, description: str):
    print()
    print(f"{'=' * 70}")
    print(f"  SCENARIO {num}: {title}")
    print(f"  {description}")
    print(f"{'=' * 70}")


def print_message(agent: str, message: str):
    print(f"\n  >> Sending to {agent.upper()}: \"{message}\"")


def print_response(response_text: str, max_len: int = 800):
    text = response_text[:max_len]
    if len(response_text) > max_len:
        text += "\n  ... [truncated]"
    for line in text.split("\n"):
        print(f"  << {line}")


async def run_demo() -> None:
    print()
    print("*" * 70)
    print("*  AI Social Platform — Live Demo                                  *")
    print("*  Real LLM calls via Google A2A protocol                          *")
    print("*" * 70)

    async with httpx.AsyncClient() as client:

        # ─── SCENARIO 1: Collaborative — purchase research across network ───
        print_scenario(
            1,
            "Running Shoes (COLLABORATIVE)",
            "Alice wants shoes → agent should ask Bob for experience + query SoleStyle",
        )
        print_message("alice", "I want to buy running shoes under $150. Can you check with Bob and SoleStyle?")
        resp = await send_message(
            client,
            AGENT_URLS["alice"],
            "I want to buy running shoes under $150. Can you check with Bob "
            "if he has any recommendations and also check what SoleStyle has available?",
        )
        print_response(extract_text(resp))

        # ─── SCENARIO 2: Solo — personal task, no agents needed ───
        print_scenario(
            2,
            "Personal Reminder (SOLO — no agents contacted)",
            "Alice sets a reminder → agent should handle this locally, no contacts involved",
        )
        print_message("alice", "Remind me to go for a run tomorrow at 7am")
        resp = await send_message(
            client,
            AGENT_URLS["alice"],
            "Remind me to go for a run tomorrow at 7am.",
        )
        print_response(extract_text(resp))

        # ─── SCENARIO 3: Solo — general knowledge, no agents needed ───
        print_scenario(
            3,
            "General Knowledge (SOLO — no agents contacted)",
            "Alice asks a factual question → agent should answer directly",
        )
        print_message("alice", "What's the difference between trail and road running shoes?")
        resp = await send_message(
            client,
            AGENT_URLS["alice"],
            "What's the difference between trail running shoes and road running shoes?",
        )
        print_response(extract_text(resp))

        # ─── SCENARIO 4: Collaborative — Bob shares his experience ───
        print_scenario(
            4,
            "Ask Bob Directly (COLLABORATIVE — Bob checks his history)",
            "Another agent asks Bob for shoe advice → Bob should check his history and share",
        )
        print_message("bob", "Hey Bob, what running shoes have you bought recently? Were they good?")
        resp = await send_message(
            client,
            AGENT_URLS["bob"],
            "Hey Bob, what running shoes have you bought recently? How are they? "
            "My friend is looking for a pair.",
        )
        print_response(extract_text(resp))

        # ─── SCENARIO 5: Direct merchant query ───
        print_scenario(
            5,
            "Merchant Query (DIRECT — SoleStyle catalog)",
            "Directly ask SoleStyle for running shoes → merchant responds from catalog",
        )
        print_message("solestyle", "Show me your running shoes under $150")
        resp = await send_message(
            client,
            AGENT_URLS["solestyle"],
            "What running shoes do you have under $150?",
        )
        print_response(extract_text(resp))

        # ─── SCENARIO 6: Collaborative — group research across merchants ───
        print_scenario(
            6,
            "Headphones Research (COLLABORATIVE — multi-merchant)",
            "Alice wants headphones → agent should query TechMart and ask Bob for opinions",
        )
        print_message("alice", "What headphones should I get around $300? Ask Bob and check TechMart.")
        resp = await send_message(
            client,
            AGENT_URLS["alice"],
            "I'm looking for noise-cancelling headphones around $300. "
            "Can you check what TechMart has and ask Bob if he has any experience with headphones?",
        )
        print_response(extract_text(resp))

        # ─── SCENARIO 7: Collaborative — grocery + meal planning ───
        print_scenario(
            7,
            "Healthy Meal Plan (COLLABORATIVE — FreshBite query)",
            "Alice needs groceries → agent should query FreshBite for available items",
        )
        print_message("alice", "Help me plan a healthy dinner. Check what FreshBite has available.")
        resp = await send_message(
            client,
            AGENT_URLS["alice"],
            "I want to cook a healthy dinner tonight. Can you check what FreshBite "
            "Grocery has available and suggest a meal with their products?",
        )
        print_response(extract_text(resp))

    print()
    print("*" * 70)
    print("*  Demo complete!                                                  *")
    print("*" * 70)
    print()


if __name__ == "__main__":
    asyncio.run(run_demo())
