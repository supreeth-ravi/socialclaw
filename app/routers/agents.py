"""CRUD endpoints for the agent registry."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..database import get_db
from ..models import AgentOut, AgentRegister

router = APIRouter()


@router.get("/agents", response_model=list[AgentOut])
async def list_agents():
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM agents ORDER BY name").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/agents", response_model=AgentOut)
async def register_agent(body: AgentRegister):
    conn = get_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO agents
               (id, name, type, description, agent_card_url, host, port, is_local)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (body.id, body.name, body.type, body.description,
             body.agent_card_url, body.host, body.port, body.is_local),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (body.id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


@router.get("/agents/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: str):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")
        return dict(row)
    finally:
        conn.close()
