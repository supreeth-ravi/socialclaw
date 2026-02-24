"""Pydantic request/response schemas for the web API."""

from __future__ import annotations

from pydantic import BaseModel


# ─── Chat ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str


# ─── Sessions ───────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    title: str = "New Chat"


class SessionOut(BaseModel):
    id: str
    agent_id: str
    title: str
    created_at: str
    updated_at: str


class MessageOut(BaseModel):
    id: int
    session_id: str
    role: str
    author: str
    content: str
    metadata_json: str
    event_id: str | None
    timestamp: float


# ─── History ───────────────────────────────────────────────────────

class HistoryOut(BaseModel):
    id: int
    timestamp: str
    type: str
    summary: str
    details: dict
    contacts_involved: list[str]
    sentiment: str
    visibility: str


class HistoryAdd(BaseModel):
    summary: str
    type: str = "note"
    sentiment: str = "neutral"
    visibility: str = "personal"
    details: dict = {}
    contacts_involved: list[str] = []


class HistoryUpdate(BaseModel):
    type: str | None = None
    visibility: str | None = None
    summary: str | None = None
    sentiment: str | None = None


class UrlExtractRequest(BaseModel):
    url: str
    context: str = ""


# ─── Agents ─────────────────────────────────────────────────────────

class AgentRegister(BaseModel):
    id: str
    name: str
    type: str = "service"
    description: str = ""
    agent_card_url: str | None = None
    host: str | None = None
    port: int | None = None
    is_local: bool = False


class AgentOut(BaseModel):
    id: str
    name: str
    type: str
    description: str
    agent_card_url: str | None
    host: str | None
    port: int | None
    is_local: bool
    skills_json: str
    created_at: str
    updated_at: str


# ─── Contacts ───────────────────────────────────────────────────────

class ContactAdd(BaseModel):
    name: str
    type: str = "merchant"
    agent_card_url: str
    description: str = ""
    tags: list[str] = []


class ContactInvite(BaseModel):
    agent_card_url: str


class ContactOut(BaseModel):
    id: int
    owner_agent_id: str
    name: str
    type: str
    agent_card_url: str
    description: str
    tags: list[str]
    status: str
    created_at: str


# ─── Auth ──────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: str
    password: str
    handle: str
    display_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class HandleCheckRequest(BaseModel):
    handle: str


class UserOut(BaseModel):
    id: str
    email: str
    handle: str
    display_name: str
    agent_instructions: str | None = ""
    agent_skills: str | None = ""
    auto_inbox_enabled: bool = False
    social_pulse_enabled: bool = False
    social_pulse_frequency: str = "weekly"
    feed_engagement_enabled: bool = False
    feed_engagement_frequency: str = "daily"
    a2a_max_turns: int = 3
    is_onboarded: bool
    created_at: str


class TokenResponse(BaseModel):
    token: str
    user: UserOut


class ProfileUpdate(BaseModel):
    display_name: str


class AgentProfileUpdate(BaseModel):
    agent_instructions: str = ""
    agent_skills: str = ""
    auto_inbox_enabled: bool = False
    social_pulse_enabled: bool = False
    social_pulse_frequency: str = "weekly"
    feed_engagement_enabled: bool = False
    feed_engagement_frequency: str = "daily"
    a2a_max_turns: int = 3


# ─── Tasks ─────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    intent: str
    session_id: str | None = None


class TaskOut(BaseModel):
    id: str
    owner_agent_id: str
    intent: str
    status: str
    phase: str
    progress_log: list
    result_summary: str
    session_id: str
    created_at: str
    updated_at: str
    completed_at: str | None = None


# ─── Schedule ──────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    intent: str
    trigger_at: str
    recurrence: str = "once"


class ScheduleOut(BaseModel):
    id: str
    owner_agent_id: str
    intent: str
    trigger_at: str
    recurrence: str
    status: str
    last_run_at: str | None = None
    task_id: str | None = None
    created_at: str


# ─── Feed ─────────────────────────────────────────────────────────

class FeedPostOut(BaseModel):
    id: str
    author_handle: str
    author_display: str
    type: str
    content: str
    details: dict = {}
    history_id: int | None = None
    original_post_id: str | None = None
    original_post: dict | None = None
    visibility: str
    created_at: str
    reactions: dict = {}
    my_reactions: list[str] = []
    comment_count: int = 0


class FeedCommentOut(BaseModel):
    id: int
    post_id: str
    author_handle: str
    author_display: str
    content: str
    parent_id: int | None = None
    created_at: str
    replies: list = []


class FeedReactionAdd(BaseModel):
    reaction_type: str


class FeedCommentAdd(BaseModel):
    content: str
    parent_id: int | None = None


class FeedReshare(BaseModel):
    content: str = ""
