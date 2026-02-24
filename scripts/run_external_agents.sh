#!/usr/bin/env bash
set -euo pipefail

uv run python -m external_agents.alice.main &
uv run python -m external_agents.bob.main &
uv run python -m external_agents.claude.main &
uv run python -m external_agents.solestyle_shoes.main &
uv run python -m external_agents.techmart_electronics.main &
uv run python -m external_agents.freshbite_grocery.main &

wait
