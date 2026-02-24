# External Agents

These agents are **standalone** and **not part of the core application**. They are intended to be run as separate services (A2A endpoints) and can be pre-registered in the platform for testing.

## Run locally

```bash
uv run python -m external_agents.alice.main
uv run python -m external_agents.bob.main
uv run python -m external_agents.solestyle_shoes.main
uv run python -m external_agents.techmart_electronics.main
uv run python -m external_agents.freshbite_grocery.main
```

These agents expose their own `.well-known/agent-card.json` endpoints for A2A discovery.
