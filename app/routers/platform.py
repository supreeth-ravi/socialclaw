"""Platform discovery — lets users find/add merchant agents and other users."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from common.models import Contact

from ..auth import get_current_user
from ..config import DB_PATH, PUBLIC_BASE_URL
from ..database import get_db
from ..services.db_contacts import SqliteContactRegistry

router = APIRouter(prefix="/platform")


@router.get("/agents")
async def list_platform_agents(current_user: dict = Depends(get_current_user)):
    """Return platform agents the user hasn't already added as contacts."""
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        # Get all platform agents (personal + merchant)
        agents = conn.execute(
            "SELECT * FROM agents ORDER BY type, name"
        ).fetchall()

        # Get user's existing contact names
        existing = conn.execute(
            "SELECT name FROM contacts WHERE owner_agent_id = ?",
            (agent_id,),
        ).fetchall()
        existing_names = {r["name"].lower() for r in existing}

        result = []
        for a in agents:
            if a["name"].lower() not in existing_names:
                result.append(dict(a))
        return result
    finally:
        conn.close()


@router.post("/agents/{agent_db_id}/add")
async def add_platform_agent(agent_db_id: str, current_user: dict = Depends(get_current_user)):
    """Add a platform agent as a contact for the current user."""
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_db_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")
        agent_data = dict(row)
    finally:
        conn.close()

    registry = SqliteContactRegistry(DB_PATH, agent_id)
    contact_type = agent_data.get("type") or "merchant"
    tags = ["external-agent"]
    if contact_type == "merchant":
        tags.append("merchant")
    else:
        tags.append("friend")
    contact = Contact(
        name=agent_data["name"],
        type=contact_type,
        agent_card_url=agent_data["agent_card_url"] or "",
        description=agent_data["description"],
        tags=tags,
    )
    result = registry.add(contact)
    if "already exists" in result:
        raise HTTPException(status_code=409, detail=result)
    return {"ok": True, "message": result}


@router.get("/users")
async def list_platform_users(current_user: dict = Depends(get_current_user)):
    """Return other registered users the current user hasn't already added as contacts."""
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        users = conn.execute(
            "SELECT handle, display_name, created_at FROM users WHERE handle != ? ORDER BY display_name, handle",
            (agent_id,),
        ).fetchall()

        existing = conn.execute(
            "SELECT name FROM contacts WHERE owner_agent_id = ?",
            (agent_id,),
        ).fetchall()
        existing_names = {r["name"].lower() for r in existing}

        result = []
        for u in users:
            if u["handle"].lower() not in existing_names:
                result.append({
                    "handle": u["handle"],
                    "display_name": u["display_name"] or u["handle"],
                    "created_at": u["created_at"],
                })
        return result
    finally:
        conn.close()


@router.post("/users/{handle}/add")
async def add_platform_user(handle: str, current_user: dict = Depends(get_current_user)):
    """Add another platform user as a personal (friend) contact."""
    agent_id = current_user["handle"]
    if handle.lower() == agent_id.lower():
        raise HTTPException(status_code=400, detail="Cannot add yourself as a contact")

    conn = get_db()
    try:
        row = conn.execute("SELECT handle, display_name FROM users WHERE handle = ?", (handle,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        user_data = dict(row)
    finally:
        conn.close()

    display = user_data["display_name"] or user_data["handle"]
    registry = SqliteContactRegistry(DB_PATH, agent_id)
    contact = Contact(
        name=display,
        type="personal",
        agent_card_url=f"{PUBLIC_BASE_URL}/a2a/{user_data['handle']}/.well-known/agent-card.json",
        description=f"Platform user @{user_data['handle']}",
        tags=["friend", "platform-user"],
    )
    result = registry.add(contact)
    if "already exists" in result:
        raise HTTPException(status_code=409, detail=result)
    return {"ok": True, "message": result}
