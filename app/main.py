"""SocialClaw — FastAPI web application.

Run:
    uvicorn app.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import DB_PATH, STATIC_DIR
from .database import get_db, init_db
from .routers import agents, chat, contacts, inbox, schedule, sessions, tasks
from .routers.debug import router as debug_router
from .routers.a2a_inbound import router as a2a_inbound_router
from .routers.a2a_rpc import router as a2a_rpc_router
from .routers.history import router as history_router
from .routers.auth_router import router as auth_router
from .routers.feed import router as feed_router
from .routers.platform import router as platform_router
from .routers.integrations import router as integrations_router
from .routers.skills import router as skills_router

logger = logging.getLogger(__name__)

# Platform agents to seed into the agents table on startup
_PLATFORM_AGENTS = [
    {
        "id": "solestyle",
        "name": "Foot Locker",
        "type": "merchant",
        "description": "Premium footwear retailer with Nike, Adidas, New Balance",
        "host": "localhost",
        "port": 8010,
        "is_local": True,
        "agent_card_url": "http://localhost:8010/.well-known/agent-card.json",
    },
    {
        "id": "techmart",
        "name": "Best Buy",
        "type": "merchant",
        "description": "Electronics retailer with phones, laptops, accessories",
        "host": "localhost",
        "port": 8011,
        "is_local": True,
        "agent_card_url": "http://localhost:8011/.well-known/agent-card.json",
    },
    {
        "id": "freshbite",
        "name": "Whole Foods",
        "type": "merchant",
        "description": "Organic grocery store with fresh produce and health foods",
        "host": "localhost",
        "port": 8012,
        "is_local": True,
        "agent_card_url": "http://localhost:8012/.well-known/agent-card.json",
    },
]


def _seed_platform_agents():
    """Insert platform agents into the agents table."""
    conn = get_db()
    try:
        for a in _PLATFORM_AGENTS:
            conn.execute(
                """INSERT OR REPLACE INTO agents
                   (id, name, type, description, host, port, is_local, agent_card_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (a["id"], a["name"], a["type"], a["description"],
                 a["host"], a["port"], a["is_local"], a["agent_card_url"]),
            )
        conn.commit()
        logger.info("Platform agents seeded")
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    init_db()
    logger.info("Database initialized at %s", DB_PATH)

    # Seed platform agents
    _seed_platform_agents()

    # Seed skills catalog
    from .services.skill_service import seed_skills_catalog
    seed_skills_catalog()
    logger.info("Skills catalog ready")

    # Empty runner pool — runners created lazily per user
    app.state.runners = {}

    # Inbox store (created before local router so messages are logged)
    from .services.inbox import InboxStore
    app.state.inbox_store = InboxStore(DB_PATH)

    # Initialize local router for platform:// URLs (platform users)
    from .services.local_router import init_local_router
    init_local_router(app.state.runners, DB_PATH, inbox_store=app.state.inbox_store)

    # Background task system
    from .services.task_store import TaskStore
    from .services.task_runner import BackgroundTaskRunner
    app.state.task_store = TaskStore(DB_PATH)
    app.state.task_runner = BackgroundTaskRunner(app.state.runners, DB_PATH, app.state.task_store)
    await app.state.task_runner.start()

    # Scheduler service
    from .services.scheduler import SchedulerService
    app.state.scheduler = SchedulerService(app.state.task_runner, DB_PATH)
    await app.state.scheduler.start()

    # Simulation engine disabled (personal-agent-only app)
    app.state.simulation = None

    yield

    if app.state.simulation:
        await app.state.simulation.stop()
    await app.state.scheduler.stop()
    await app.state.task_runner.stop()


app = FastAPI(title="SocialClaw", lifespan=lifespan)

# API routers
app.include_router(auth_router, prefix="/api")
app.include_router(platform_router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(contacts.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(inbox.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(feed_router, prefix="/api")
app.include_router(integrations_router, prefix="/api")
app.include_router(skills_router, prefix="/api")
app.include_router(a2a_inbound_router, prefix="/api")
app.include_router(debug_router, prefix="/api")
app.include_router(a2a_rpc_router)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─── Page routes ──────────────────────────────────────────────────

@app.get("/")
async def landing_page():
    return FileResponse(str(STATIC_DIR / "landing.html"))


@app.get("/auth")
async def auth_page():
    return FileResponse(str(STATIC_DIR / "auth.html"))


@app.get("/app")
async def app_page():
    return FileResponse(str(STATIC_DIR / "app.html"))


@app.get("/skills")
async def skills_page():
    return FileResponse(str(STATIC_DIR / "skills.html"))
