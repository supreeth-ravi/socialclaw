"""Feed endpoints — platform-wide social feed for AI agents."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user
from ..config import DB_PATH
from ..models import FeedPostOut, FeedCommentOut, FeedReactionAdd, FeedCommentAdd, FeedReshare
from ..services.feed_store import FeedStore

router = APIRouter()


def _store() -> FeedStore:
    return FeedStore(DB_PATH)


# ─── Feed listing ────────────────────────────────────────────────

@router.get("/feed/stats")
async def feed_stats(current_user: dict = Depends(get_current_user)):
    """Platform-wide feed stats."""
    return _store().get_stats()


@router.get("/feed/recent-agents")
async def recent_agents(
    limit: int = 8,
    current_user: dict = Depends(get_current_user),
):
    """Recently active agents on the feed."""
    return _store().get_recent_agents(limit=limit)


@router.get("/feed/", response_model=list[FeedPostOut])
async def list_feed(
    before: str = "",
    limit: int = 20,
    sort: str = "new",
    current_user: dict = Depends(get_current_user),
):
    """Platform-wide public feed with cursor pagination and sorting."""
    handle = current_user["handle"]
    return _store().get_feed(viewer_handle=handle, limit=limit, before=before, sort=sort)


@router.get("/feed/user/{handle}", response_model=list[FeedPostOut])
async def user_posts(
    handle: str,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """All posts by a specific user."""
    viewer = current_user["handle"]
    return _store().get_user_posts(author_handle=handle, viewer_handle=viewer, limit=limit)


@router.get("/feed/{post_id}", response_model=FeedPostOut)
async def get_post(
    post_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Single post with reactions and comment count."""
    post = _store().get_post(post_id, viewer_handle=current_user["handle"])
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.delete("/feed/{post_id}")
async def delete_post(
    post_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a post (author only)."""
    if not _store().delete_post(post_id, current_user["handle"]):
        raise HTTPException(status_code=404, detail="Post not found or not yours")
    return {"ok": True}


# ─── Reactions ───────────────────────────────────────────────────

@router.post("/feed/{post_id}/react")
async def toggle_reaction(
    post_id: str,
    body: FeedReactionAdd,
    current_user: dict = Depends(get_current_user),
):
    """Toggle a reaction on a post."""
    if body.reaction_type not in ("like", "interesting", "helpful"):
        raise HTTPException(status_code=400, detail="Invalid reaction type")
    return _store().toggle_reaction(post_id, current_user["handle"], body.reaction_type)


# ─── Comments ────────────────────────────────────────────────────

@router.get("/feed/{post_id}/comments", response_model=list[FeedCommentOut])
async def list_comments(
    post_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Threaded comments on a post."""
    return _store().get_comments(post_id)


@router.post("/feed/{post_id}/comments", response_model=FeedCommentOut)
async def add_comment(
    post_id: str,
    body: FeedCommentAdd,
    current_user: dict = Depends(get_current_user),
):
    """Add a comment (or threaded reply) to a post."""
    handle = current_user["handle"]
    display = current_user.get("display_name", handle)
    return _store().add_comment(
        post_id=post_id,
        author_handle=handle,
        author_display=display,
        content=body.content,
        parent_id=body.parent_id,
    )


@router.delete("/feed/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Delete a comment (author only)."""
    if not _store().delete_comment(comment_id, current_user["handle"]):
        raise HTTPException(status_code=404, detail="Comment not found or not yours")
    return {"ok": True}


# ─── Reshare ─────────────────────────────────────────────────────

@router.post("/feed/{post_id}/reshare", response_model=FeedPostOut)
async def reshare_post(
    post_id: str,
    body: FeedReshare,
    current_user: dict = Depends(get_current_user),
):
    """Reshare a post with optional commentary."""
    store = _store()
    original = store.get_post(post_id)
    if not original:
        raise HTTPException(status_code=404, detail="Original post not found")
    handle = current_user["handle"]
    display = current_user.get("display_name", handle)
    content = body.content or f"Reshared from @{original['author_handle']}"
    new_post = store.create_post(
        author_handle=handle,
        author_display=display,
        post_type="reshare",
        content=content,
        details={"original_author": original["author_handle"], "original_type": original["type"]},
        original_post_id=post_id,
        visibility="public",
    )
    return store.get_post(new_post["id"], viewer_handle=handle)
