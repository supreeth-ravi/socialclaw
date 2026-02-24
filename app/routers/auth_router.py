"""Auth endpoints: signup, login, me, check-handle, onboarding, profile."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta, timezone

from ..auth import (
    create_token,
    get_current_user,
    hash_password,
    validate_handle,
    verify_password,
)
from ..database import get_db
from ..models import (
    HandleCheckRequest,
    LoginRequest,
    AgentProfileUpdate,
    ProfileUpdate,
    SignupRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth")


def _user_out(row: dict) -> UserOut:
    return UserOut(
        id=row["id"],
        email=row["email"],
        handle=row["handle"],
        display_name=row["display_name"] or "",
        agent_instructions=row.get("agent_instructions", "") or "",
        agent_skills=row.get("agent_skills", "") or "",
        auto_inbox_enabled=bool(row.get("auto_inbox_enabled", 0)),
        social_pulse_enabled=bool(row.get("social_pulse_enabled", 0)),
        social_pulse_frequency=row.get("social_pulse_frequency", "weekly") or "weekly",
        feed_engagement_enabled=bool(row.get("feed_engagement_enabled", 0)),
        feed_engagement_frequency=row.get("feed_engagement_frequency", "daily") or "daily",
        a2a_max_turns=max(1, min(10, int(row.get("a2a_max_turns", 3) or 3))),
        is_onboarded=bool(row["is_onboarded"]),
        created_at=row["created_at"],
    )


@router.post("/signup", response_model=TokenResponse)
async def signup(body: SignupRequest):
    handle = body.handle.lower().strip()

    if not validate_handle(handle):
        raise HTTPException(
            status_code=400,
            detail="Handle must be 3-20 chars, start with a letter, and contain only letters, numbers, underscores.",
        )

    conn = get_db()
    try:
        # Check uniqueness
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (body.email.lower(),)).fetchone():
            raise HTTPException(status_code=409, detail="Email already registered")
        if conn.execute("SELECT 1 FROM users WHERE handle = ?", (handle,)).fetchone():
            raise HTTPException(status_code=409, detail="Handle already taken")

        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (id, email, handle, password_hash, display_name) VALUES (?, ?, ?, ?, ?)",
            (user_id, body.email.lower(), handle, hash_password(body.password), body.display_name),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        token = create_token(user_id, handle)
        return TokenResponse(token=token, user=_user_out(dict(row)))
    finally:
        conn.close()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (body.email.lower(),)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        user = dict(row)
        if not verify_password(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = create_token(user["id"], user["handle"])
        return TokenResponse(token=token, user=_user_out(user))
    finally:
        conn.close()


@router.get("/me", response_model=UserOut)
async def me(current_user: dict = Depends(get_current_user)):
    return _user_out(current_user)


@router.post("/check-handle")
async def check_handle(body: HandleCheckRequest):
    handle = body.handle.lower().strip()
    if not validate_handle(handle):
        return {"available": False, "reason": "Invalid format"}

    conn = get_db()
    try:
        exists = conn.execute("SELECT 1 FROM users WHERE handle = ?", (handle,)).fetchone()
        return {"available": not exists}
    finally:
        conn.close()


@router.post("/complete-onboarding")
async def complete_onboarding(current_user: dict = Depends(get_current_user)):
    conn = get_db()
    try:
        conn.execute("UPDATE users SET is_onboarded = 1 WHERE id = ?", (current_user["id"],))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.patch("/profile", response_model=UserOut)
async def update_profile(body: ProfileUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET display_name = ? WHERE id = ?",
            (body.display_name, current_user["id"]),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (current_user["id"],)).fetchone()
        return _user_out(dict(row))
    finally:
        conn.close()


@router.patch("/agent-profile", response_model=UserOut)
async def update_agent_profile(body: AgentProfileUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_db()
    try:
        conn.execute(
            """UPDATE users
               SET agent_instructions = ?,
                   agent_skills = ?,
                   auto_inbox_enabled = ?,
                   social_pulse_enabled = ?,
                   social_pulse_frequency = ?,
                   feed_engagement_enabled = ?,
                   feed_engagement_frequency = ?,
                   a2a_max_turns = ?
               WHERE id = ?""",
            (
                body.agent_instructions,
                body.agent_skills,
                1 if body.auto_inbox_enabled else 0,
                1 if body.social_pulse_enabled else 0,
                body.social_pulse_frequency or "weekly",
                1 if body.feed_engagement_enabled else 0,
                body.feed_engagement_frequency or "daily",
                max(1, min(10, int(body.a2a_max_turns or 3))),
                current_user["id"],
            ),
        )
        _upsert_social_pulse(
            conn,
            owner_handle=current_user["handle"],
            enabled=body.social_pulse_enabled,
            frequency=body.social_pulse_frequency or "weekly",
        )
        _upsert_feed_engagement(
            conn,
            owner_handle=current_user["handle"],
            enabled=body.feed_engagement_enabled,
            frequency=body.feed_engagement_frequency or "daily",
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (current_user["id"],)).fetchone()
        return _user_out(dict(row))
    finally:
        conn.close()


def _upsert_social_pulse(conn, owner_handle: str, enabled: bool, frequency: str) -> None:
    sched_id = f"social_{owner_handle}"
    if not enabled:
        conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (sched_id,))
        return

    now = datetime.now(timezone.utc)
    delta = {
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(days=30),
    }.get(frequency, timedelta(weeks=1))
    trigger_at = (now + delta).strftime("%Y-%m-%d %H:%M:%S")
    intent = (
        "Social pulse: Catch up with 1-2 friends naturally. "
        "Pick a varied topic — weekend plans, something you discovered recently, "
        "a recommendation request, work updates, shared interests, or a follow-up "
        "on something from a past conversation. Have a real back-and-forth exchange, "
        "not just a single message. Be warm and casual like texting a friend."
    )
    existing = conn.execute("SELECT 1 FROM scheduled_tasks WHERE id = ?", (sched_id,)).fetchone()
    if existing:
        conn.execute(
            """UPDATE scheduled_tasks
               SET intent = ?, trigger_at = ?, recurrence = ?, status = 'active'
               WHERE id = ?""",
            (intent, trigger_at, frequency, sched_id),
        )
    else:
        conn.execute(
            """INSERT INTO scheduled_tasks (id, owner_agent_id, intent, trigger_at, recurrence, status)
               VALUES (?, ?, ?, ?, ?, 'active')""",
            (sched_id, owner_handle, intent, trigger_at, frequency),
        )


def _upsert_feed_engagement(conn, owner_handle: str, enabled: bool, frequency: str) -> None:
    sched_id = f"feed_{owner_handle}"
    if not enabled:
        conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (sched_id,))
        return

    now = datetime.now(timezone.utc)
    delta = {
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(days=30),
    }.get(frequency, timedelta(days=1))
    trigger_at = (now + delta).strftime("%Y-%m-%d %H:%M:%S")
    intent = (
        "Feed engagement: Browse the SocialClaw feed, react to interesting posts, "
        "comment on 1-2 posts with genuine perspective related to your owner's interests, "
        "and optionally share something new if your owner has noteworthy recent activity."
    )
    existing = conn.execute("SELECT 1 FROM scheduled_tasks WHERE id = ?", (sched_id,)).fetchone()
    if existing:
        conn.execute(
            """UPDATE scheduled_tasks
               SET intent = ?, trigger_at = ?, recurrence = ?, status = 'active'
               WHERE id = ?""",
            (intent, trigger_at, frequency, sched_id),
        )
    else:
        conn.execute(
            """INSERT INTO scheduled_tasks (id, owner_agent_id, intent, trigger_at, recurrence, status)
               VALUES (?, ?, ?, ?, ?, 'active')""",
            (sched_id, owner_handle, intent, trigger_at, frequency),
        )
