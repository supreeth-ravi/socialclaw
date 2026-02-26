"""Skills marketplace — browse, install, and manage agent skills."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..auth import get_current_user
from ..config import DB_PATH
from ..services import skill_service as svc

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def list_skills(
    category: str | None = Query(None),
    q: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """List the full skill catalog with the current user's install status."""
    catalog = svc.list_catalog(DB_PATH, category=category, q=q)
    installed = {s["skill_slug"] for s in svc.get_user_skills(current_user["handle"], DB_PATH)}
    for skill in catalog:
        skill["installed"] = skill["slug"] in installed
    return catalog


@router.get("/installed")
async def list_installed(current_user: dict = Depends(get_current_user)):
    """List skills installed by the current user."""
    return svc.get_user_skills(current_user["handle"], DB_PATH)


@router.get("/categories")
async def list_categories(current_user: dict = Depends(get_current_user)):
    """List distinct categories in the catalog."""
    catalog = svc.list_catalog(DB_PATH)
    cats = sorted({s["category"] for s in catalog if s["category"]})
    return cats


@router.get("/{slug:path}/detail")
async def skill_detail(slug: str, current_user: dict = Depends(get_current_user)):
    skill = svc.get_skill(slug, DB_PATH)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    installed_skills = svc.get_user_skills(current_user["handle"], DB_PATH)
    installed_map = {s["skill_slug"]: s for s in installed_skills}
    skill["installed"] = slug in installed_map
    if slug in installed_map:
        skill["enabled"] = installed_map[slug]["enabled"]
    return skill


def _invalidate_runner(request: Request, user_handle: str) -> None:
    """Remove the cached agent runner so it rebuilds with updated skills on next chat."""
    try:
        runners: dict = request.app.state.runners
        runners.pop(user_handle, None)
    except Exception:
        pass


@router.post("/{slug:path}/install")
async def install_skill(request: Request, slug: str, current_user: dict = Depends(get_current_user)):
    try:
        result = svc.install_skill(current_user["handle"], slug, DB_PATH)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    _invalidate_runner(request, current_user["handle"])
    return result


@router.delete("/{slug:path}/install")
async def uninstall_skill(request: Request, slug: str, current_user: dict = Depends(get_current_user)):
    result = svc.uninstall_skill(current_user["handle"], slug, DB_PATH)
    _invalidate_runner(request, current_user["handle"])
    return result


@router.patch("/{slug:path}/toggle")
async def toggle_skill(request: Request, slug: str, body: dict, current_user: dict = Depends(get_current_user)):
    enabled = body.get("enabled", True)
    result = svc.toggle_skill(current_user["handle"], slug, enabled, DB_PATH)
    _invalidate_runner(request, current_user["handle"])
    return result


@router.put("/{slug:path}/config")
async def save_config(slug: str, body: dict, current_user: dict = Depends(get_current_user)):
    return svc.save_skill_config(current_user["handle"], slug, body, DB_PATH)


@router.get("/browse/clawhub")
async def browse_clawhub(
    q: str = Query("", description="Search query"),
    limit: int = Query(20, le=30),
    current_user: dict = Depends(get_current_user),
):
    """Live search of the ClawhHub registry via GitHub API."""
    results = await svc.browse_clawhub(q, limit)
    # Mark which ones are already in our catalog
    catalog_slugs = {s["slug"] for s in svc.list_catalog(DB_PATH)}
    for r in results:
        r["in_catalog"] = r["slug"] in catalog_slugs
    return results


@router.post("/import/clawhub")
async def import_from_clawhub(body: dict, current_user: dict = Depends(get_current_user)):
    """Import a skill from ClawhHub into the local catalog."""
    slug = body.get("slug", "").strip()
    raw_url = body.get("raw_url", "").strip()
    if not slug or not raw_url:
        raise HTTPException(status_code=400, detail="slug and raw_url are required")
    try:
        result = await svc.import_from_clawhub(slug, raw_url, DB_PATH)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch from ClawhHub: {e}")
    return result
