"""Composio integrations proxy + first-party connectors (MS SQL)."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import httpx

from ..auth import get_current_user
from ..config import COMPOSIO_API_KEY
from ..database import get_db

router = APIRouter(prefix="/integrations", tags=["integrations"])

_BASE = "https://backend.composio.dev/api/v1"


# ─── Composio passthrough ─────────────────────────────────────────

@router.get("/apps")
async def list_apps(category: str | None = Query(None)):
    if not COMPOSIO_API_KEY:
        return JSONResponse({"error": "COMPOSIO_API_KEY not configured"}, status_code=503)
    params: dict[str, str] = {}
    if category:
        params["category"] = category
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_BASE}/apps",
            headers={"X-API-Key": COMPOSIO_API_KEY},
            params=params,
        )
    return JSONResponse(resp.json(), status_code=resp.status_code)


@router.get("/apps/{slug}")
async def get_app(slug: str):
    if not COMPOSIO_API_KEY:
        return JSONResponse({"error": "COMPOSIO_API_KEY not configured"}, status_code=503)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_BASE}/apps/{slug}",
            headers={"X-API-Key": COMPOSIO_API_KEY},
        )
    return JSONResponse(resp.json(), status_code=resp.status_code)


# ─── MS SQL connector ─────────────────────────────────────────────

def _get_mssql_config(user_handle: str) -> dict | None:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT config_json FROM user_integrations WHERE user_handle = ? AND integration_type = 'mssql'",
            (user_handle,),
        ).fetchone()
    finally:
        conn.close()
    return json.loads(row["config_json"]) if row else None


@router.get("/mssql/config")
async def get_mssql_config(user: Annotated[dict, Depends(get_current_user)]):
    cfg = _get_mssql_config(user["handle"])
    if not cfg:
        return JSONResponse({"configured": False})
    cfg["password"] = "••••••••" if cfg.get("password") else ""
    cfg["configured"] = True
    return JSONResponse(cfg)


@router.put("/mssql/config")
async def save_mssql_config(body: dict, user: Annotated[dict, Depends(get_current_user)]):
    for field in ("server", "database", "username", "password"):
        if not body.get(field):
            return JSONResponse({"error": f"Missing required field: {field}"}, status_code=400)

    cfg = {
        "server": body["server"].strip(),
        "port": int(body.get("port") or 1433),
        "database": body["database"].strip(),
        "username": body["username"].strip(),
        "password": body["password"],
    }

    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO user_integrations (user_handle, integration_type, config_json, updated_at)
               VALUES (?, 'mssql', ?, datetime('now'))
               ON CONFLICT(user_handle, integration_type) DO UPDATE SET
                 config_json = excluded.config_json,
                 updated_at  = datetime('now')""",
            (user["handle"], json.dumps(cfg)),
        )
        conn.commit()
    finally:
        conn.close()

    return JSONResponse({"ok": True})


@router.delete("/mssql/config")
async def delete_mssql_config(user: Annotated[dict, Depends(get_current_user)]):
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM user_integrations WHERE user_handle = ? AND integration_type = 'mssql'",
            (user["handle"],),
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"ok": True})


@router.post("/mssql/test")
async def test_mssql_connection(body: dict, user: Annotated[dict, Depends(get_current_user)]):
    cfg = _get_mssql_config(user["handle"]) or {}

    # Overlay non-empty request fields
    for field in ("server", "database", "username"):
        if body.get(field, "").strip():
            cfg[field] = body[field].strip()
    if body.get("port"):
        cfg["port"] = int(body["port"])
    if body.get("password") and body["password"] != "••••••••":
        cfg["password"] = body["password"]

    for field in ("server", "database", "username", "password"):
        if not cfg.get(field):
            return JSONResponse({"ok": False, "error": f"Missing field: {field}"}, status_code=400)

    def _connect():
        import pymssql  # noqa: PLC0415
        with pymssql.connect(
            server=cfg["server"],
            port=str(cfg.get("port", 1433)),
            database=cfg["database"],
            user=cfg["username"],
            password=cfg["password"],
            login_timeout=10,
            timeout=10,
        ) as c:
            cur = c.cursor()
            cur.execute("SELECT @@VERSION")
            row = cur.fetchone()
            return (row[0] or "")[:120] if row else "Connected"

    try:
        version = await asyncio.wait_for(asyncio.to_thread(_connect), timeout=15)
        return JSONResponse({"ok": True, "message": f"Connected — {version}"})
    except asyncio.TimeoutError:
        return JSONResponse({"ok": False, "error": "Connection timed out (15s)"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})
