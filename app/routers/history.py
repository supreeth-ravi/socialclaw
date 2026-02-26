"""History endpoints for personal agent memory."""

from __future__ import annotations

import json as json_mod

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone

from ..auth import get_current_user
from ..config import DB_PATH
from ..models import HistoryOut, HistoryAdd, HistoryUpdate, UrlExtractRequest
from common.models import HistoryEntry
from ..services.db_history import SqliteHistoryStore

router = APIRouter()


@router.get("/history", response_model=list[HistoryOut])
async def list_history(
    q: str | None = None,
    type: str | None = None,
    visibility: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    """Return history entries for the current user."""
    store = SqliteHistoryStore(DB_PATH, current_user["handle"])
    entries = store.search_with_id(q) if q else store.all_with_id()
    if type:
        entries = [e for e in entries if e["type"] == type]
    if visibility:
        entries = [e for e in entries if e["visibility"] == visibility]
    return entries


@router.post("/history", response_model=HistoryOut)
async def add_history(body: HistoryAdd, current_user: dict = Depends(get_current_user)):
    """Add a memory entry for the current user."""
    store = SqliteHistoryStore(DB_PATH, current_user["handle"])
    entry = HistoryEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        type=body.type,
        summary=body.summary,
        details=body.details,
        contacts_involved=body.contacts_involved,
        sentiment=body.sentiment,
        visibility=body.visibility,
    )
    store.add(entry)
    entries = store.all_with_id()
    return entries[0]  # DESC order, newest first


@router.delete("/history/{entry_id}")
async def delete_history(entry_id: int, current_user: dict = Depends(get_current_user)):
    store = SqliteHistoryStore(DB_PATH, current_user["handle"])
    if not store.delete(entry_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}


@router.patch("/history/{entry_id}", response_model=HistoryOut)
async def update_history(
    entry_id: int,
    body: HistoryUpdate,
    current_user: dict = Depends(get_current_user),
):
    store = SqliteHistoryStore(DB_PATH, current_user["handle"])
    fields = body.model_dump(exclude_none=True)
    if not store.update(entry_id, **fields):
        raise HTTPException(status_code=404, detail="Memory not found")
    return store.get_by_id(entry_id)


@router.post("/history/extract-url")
async def extract_url(body: UrlExtractRequest, current_user: dict = Depends(get_current_user)):
    """Fetch a URL, extract key facts via the configured model, and store as memory entries."""
    import httpx

    # 1. Fetch the URL content
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        resp = await client.get(body.url, headers={"User-Agent": "SocialClaw-Bot/1.0"})
        resp.raise_for_status()
        page_text = resp.text[:15000]

    # 2. Use the configured model (via LiteLLM) to extract structured facts
    from litellm import completion as litellm_completion
    from common.model import _litellm_model_name
    extraction_prompt = (
        f"Extract key facts from this webpage about a person or merchant.\n"
        f"Context hint: {body.context}\n"
        f"URL: {body.url}\n\n"
        f"Page content:\n{page_text}\n\n"
        "Return a JSON array of objects, each with:\n"
        '- "summary": one concise fact (1-2 sentences)\n'
        '- "type": one of purchase, recommendation, inquiry, review, research, note, preference\n'
        '- "sentiment": positive, negative, neutral, or mixed\n'
        '- "visibility": "sharable"\n'
        "Extract 3-8 distinct, useful facts. Return ONLY the JSON array, no markdown."
    )
    litellm_result = litellm_completion(
        model=_litellm_model_name(),
        messages=[{"role": "user", "content": extraction_prompt}],
    )
    result_text = litellm_result.choices[0].message.content

    # 3. Parse and store each fact
    raw = result_text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    facts = json_mod.loads(raw)

    store = SqliteHistoryStore(DB_PATH, current_user["handle"])
    saved = []
    for fact in facts:
        entry = HistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            type=fact.get("type", "note"),
            summary=fact["summary"],
            details={"source_url": body.url},
            contacts_involved=[],
            sentiment=fact.get("sentiment", "neutral"),
            visibility=fact.get("visibility", "sharable"),
        )
        store.add(entry)
        entries = store.all_with_id()
        saved.append(entries[0])

    return {"count": len(saved), "entries": saved}
