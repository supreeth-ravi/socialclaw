"""CRUD endpoints for contacts + invite-by-URL flow."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException

from common.a2a_client import fetch_agent_card
from common.models import Contact

from ..auth import get_current_user
from ..database import get_db
from ..models import ContactAdd, ContactInvite, ContactOut
from ..services.db_contacts import SqliteContactRegistry
from ..config import DB_PATH, PUBLIC_BASE_URL

router = APIRouter()


def _row_to_out(row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    return d


@router.get("/contacts", response_model=list[ContactOut])
async def list_contacts(current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM contacts WHERE owner_agent_id = ? ORDER BY status, name",
            (agent_id,),
        ).fetchall()
        return [_row_to_out(r) for r in rows]
    finally:
        conn.close()


@router.post("/contacts", response_model=ContactOut)
async def add_contact(body: ContactAdd, current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    registry = SqliteContactRegistry(DB_PATH, agent_id)
    contact = Contact(
        name=body.name,
        type=body.type,
        agent_card_url=body.agent_card_url,
        description=body.description,
        tags=body.tags,
    )
    result = registry.add(contact)
    if "already exists" in result:
        raise HTTPException(status_code=409, detail=result)

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM contacts WHERE owner_agent_id = ? AND name = ?",
            (agent_id, body.name),
        ).fetchone()
        return _row_to_out(row)
    finally:
        conn.close()


@router.post("/contacts/ping-all")
async def ping_all_contacts(current_user: dict = Depends(get_current_user)):
    """Ping all contacts in parallel and return updated statuses."""
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM contacts
               WHERE owner_agent_id = ?
                 AND COALESCE(status, 'unknown') != 'pending'
               ORDER BY name""",
            (agent_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    registry = SqliteContactRegistry(DB_PATH, agent_id)

    async def _ping_one(row):
        try:
            await registry.ping(row["name"])
        except Exception:
            pass
        # Re-read the status after ping updated it
        c = registry.find(row["name"])
        return {"id": row["id"], "status": c.status if c else "unknown"}

    results = await asyncio.gather(*[_ping_one(r) for r in rows])
    return list(results)


@router.post("/contacts/invite")
async def invite_by_url(body: ContactInvite, current_user: dict = Depends(get_current_user)):
    """Fetch an agent card URL, extract info, and add as a contact."""
    from a2a.types import AgentCard

    agent_id = current_user["handle"]

    try:
        card = await fetch_agent_card(body.agent_card_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch agent card: {e}")

    if isinstance(card, AgentCard):
        name = card.name
        desc = card.description or ""
        skills = card.skills or []
        tags = []
        for s in skills:
            tags.extend(s.tags or [])
    else:
        name = card.get("name", "Unknown Agent")
        desc = card.get("description", "")
        skills = card.get("skills", [])
        tags = []
        for s in skills:
            tags.extend(s.get("tags", []))

    tags = list(set(tags))[:10]  # deduplicate, limit

    registry = SqliteContactRegistry(DB_PATH, agent_id)
    contact = Contact(
        name=name,
        type="merchant",
        agent_card_url=body.agent_card_url,
        description=desc,
        tags=tags,
    )
    result = registry.add(contact)

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM contacts WHERE owner_agent_id = ? AND name = ? COLLATE NOCASE",
            (agent_id, name),
        ).fetchone()
        return {
            "message": result,
            "contact": _row_to_out(row) if row else None,
        }
    finally:
        conn.close()


@router.post("/contacts/{contact_id}/approve")
async def approve_contact(contact_id: int, current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM contacts WHERE id = ? AND owner_agent_id = ?",
            (contact_id, agent_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        conn.execute(
            "UPDATE contacts SET status = 'active' WHERE id = ?",
            (contact_id,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM contacts WHERE id = ?",
            (contact_id,),
        ).fetchone()
        return _row_to_out(row)
    finally:
        conn.close()


@router.post("/contacts/{contact_id}/reject")
async def reject_contact(contact_id: int, current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM contacts WHERE id = ? AND owner_agent_id = ?",
            (contact_id, agent_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/contacts/{contact_id}/agent-card")
async def get_agent_card(contact_id: int, current_user: dict = Depends(get_current_user)):
    """Fetch and return the agent card for a contact."""
    from a2a.types import AgentCard

    agent_id = current_user["handle"]
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        if row["owner_agent_id"] != agent_id:
            raise HTTPException(status_code=403, detail="Not your contact")
        agent_card_url = row["agent_card_url"]
        if (agent_card_url or "").startswith("platform://user/"):
            handle = agent_card_url.replace("platform://user/", "").strip("/")
            agent_card_url = f"{PUBLIC_BASE_URL}/a2a/{handle}/.well-known/agent-card.json"
    finally:
        conn.close()

    try:
        card = await fetch_agent_card(agent_card_url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not reach agent: {e}")

    # Normalize into consistent response shape
    if isinstance(card, AgentCard):
        skills = []
        for s in card.skills or []:
            skills.append({
                "name": s.name,
                "description": s.description or "",
                "tags": s.tags or [],
            })
        return {
            "name": card.name,
            "description": card.description or "",
            "url": card.url,
            "version": card.version or "",
            "skills": skills,
            "capabilities": {},
            "agent_card_url": agent_card_url,
        }
    else:
        skills = []
        for s in card.get("skills", []):
            skills.append({
                "name": s.get("name", ""),
                "description": s.get("description", ""),
                "tags": s.get("tags", []),
            })
        return {
            "name": card.get("name", "Unknown"),
            "description": card.get("description", ""),
            "url": card.get("url", ""),
            "version": card.get("version", ""),
            "skills": skills,
            "capabilities": card.get("capabilities", {}),
            "agent_card_url": agent_card_url,
        }


@router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: int, current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        row = conn.execute("SELECT owner_agent_id FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        if row["owner_agent_id"] != agent_id:
            raise HTTPException(status_code=403, detail="Not your contact")
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.post("/contacts/{contact_id}/ping")
async def ping_contact(contact_id: int, current_user: dict = Depends(get_current_user)):
    agent_id = current_user["handle"]
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        if row["owner_agent_id"] != agent_id:
            raise HTTPException(status_code=403, detail="Not your contact")
        registry = SqliteContactRegistry(DB_PATH, row["owner_agent_id"])
        result = await registry.ping(row["name"])
        return {"result": result}
    finally:
        conn.close()
