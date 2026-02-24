from __future__ import annotations

import os
from pathlib import Path

# Directories
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
STATIC_DIR = APP_DIR / "static"

# Database
DB_PATH = DATA_DIR / "ai_social.db"

# Web server
HOST: str = "0.0.0.0"
PORT: int = 8080
PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", f"http://localhost:{PORT}")
PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", f"http://localhost:{PORT}")

# JWT Auth
JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_DAYS: int = 7

# Simulation
SIMULATION_ENABLED: bool = os.getenv("SIMULATION_ENABLED", "false").lower() in ("1", "true", "yes")
SIMULATION_INTERVAL: int = int(os.getenv("SIMULATION_INTERVAL", "120"))

# A2A multi-turn
A2A_MAX_TURNS: int = int(os.getenv("A2A_MAX_TURNS", "3"))

# Model
MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-2.0-flash")
OLLAMA_API_BASE: str = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

# Composio
COMPOSIO_API_KEY: str = os.getenv("COMPOSIO_API_KEY", "")
