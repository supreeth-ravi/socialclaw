#!/usr/bin/env bash
# Start all AI Social agents.
#
# Usage:
#   ./scripts/run_all.sh           # A2A multi-service mode (separate ports)
#   ./scripts/run_all.sh --web     # ADK Web UI mode (single UI at http://localhost:8000)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [ "$1" = "--web" ]; then
    echo "Starting AI Social with ADK Web UI..."
    echo ""
    echo "  UI:  http://localhost:8000"
    echo ""
    echo "All 5 agents available in the sidebar:"
    echo "  alice, bob, solestyle_shoes, techmart_electronics, freshbite_grocery"
    echo ""
    echo "NOTE: In Web UI mode each agent runs inside the same process."
    echo "      A2A cross-agent calls (RemoteA2aAgent) need the separate"
    echo "      multi-service mode to work across HTTP."
    echo ""
    uv run adk web --a2a agents
    exit 0
fi

echo "Starting AI Social agents (multi-service A2A mode)..."
echo ""

# Start merchant agents first (they're dependencies for personal agents)
echo "[1/5] Starting SoleStyle Shoes on port 8010..."
uv run python -m external_agents.solestyle_shoes.main &
PIDS[0]=$!

echo "[2/5] Starting TechMart Electronics on port 8011..."
uv run python -m external_agents.techmart_electronics.main &
PIDS[1]=$!

echo "[3/5] Starting FreshBite Grocery on port 8012..."
uv run python -m external_agents.freshbite_grocery.main &
PIDS[2]=$!

# Give merchant agents a moment to start
sleep 3

# Start personal agents
echo "[4/5] Starting Alice's agent on port 8001..."
uv run python -m external_agents.alice.main &
PIDS[3]=$!

echo "[5/5] Starting Bob's agent on port 8002..."
uv run python -m external_agents.bob.main &
PIDS[4]=$!

echo ""
echo "All agents started!"
echo "  Alice:     http://localhost:8001"
echo "  Bob:       http://localhost:8002"
echo "  SoleStyle: http://localhost:8010"
echo "  TechMart:  http://localhost:8011"
echo "  FreshBite: http://localhost:8012"
echo ""
echo "Press Ctrl+C to stop all agents."

# Wait for all background processes; forward Ctrl+C to kill them
trap 'echo "Stopping all agents..."; kill "${PIDS[@]}" 2>/dev/null; wait; echo "Done."' INT TERM

wait
