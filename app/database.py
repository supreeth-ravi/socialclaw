"""SQLite database initialization and connection helper."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    handle        TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name  TEXT DEFAULT '',
    agent_instructions TEXT DEFAULT '',
    agent_skills  TEXT DEFAULT '',
    auto_inbox_enabled BOOLEAN DEFAULT 0,
    social_pulse_enabled BOOLEAN DEFAULT 0,
    social_pulse_frequency TEXT DEFAULT 'weekly',
    feed_engagement_enabled BOOLEAN DEFAULT 0,
    feed_engagement_frequency TEXT DEFAULT 'daily',
    a2a_max_turns INTEGER DEFAULT 3,
    is_onboarded  BOOLEAN DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agents (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    type           TEXT NOT NULL CHECK(type IN ('personal','merchant','service')),
    description    TEXT DEFAULT '',
    agent_card_url TEXT,
    host           TEXT,
    port           INTEGER,
    is_local       BOOLEAN DEFAULT 0,
    skills_json    TEXT DEFAULT '[]',
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_agent_id  TEXT NOT NULL,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,
    agent_card_url  TEXT NOT NULL,
    description     TEXT DEFAULT '',
    tags            TEXT DEFAULT '[]',
    status          TEXT DEFAULT 'unknown',
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(owner_agent_id, name)
);

CREATE TABLE IF NOT EXISTS history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_agent_id    TEXT NOT NULL,
    timestamp         TEXT NOT NULL,
    type              TEXT NOT NULL,
    summary           TEXT NOT NULL,
    details_json      TEXT DEFAULT '{}',
    contacts_involved TEXT DEFAULT '[]',
    sentiment         TEXT DEFAULT 'neutral'
);

CREATE TABLE IF NOT EXISTS inbound_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL DEFAULT '',
    recipient_id    TEXT NOT NULL,
    sender_name     TEXT NOT NULL,
    sender_type     TEXT NOT NULL DEFAULT 'system' CHECK(sender_type IN ('merchant','friend','system')),
    direction       TEXT NOT NULL DEFAULT 'inbound' CHECK(direction IN ('inbound','outbound')),
    message         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'unread' CHECK(status IN ('unread','read','processed','stopped')),
    processing_log  TEXT DEFAULT '[]',
    created_at      TEXT DEFAULT (datetime('now')),
    processed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_inbound_recipient_status ON inbound_messages(recipient_id, status);
CREATE INDEX IF NOT EXISTS idx_inbound_conversation ON inbound_messages(conversation_id);

CREATE TABLE IF NOT EXISTS conversations (
    id              TEXT PRIMARY KEY,
    participant_a   TEXT NOT NULL,
    participant_b   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','stopped')),
    auto_respond    BOOLEAN NOT NULL DEFAULT 0,
    last_message_at TEXT DEFAULT (datetime('now')),
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id              TEXT PRIMARY KEY,
    owner_agent_id  TEXT NOT NULL,
    intent          TEXT NOT NULL,
    trigger_at      TEXT NOT NULL,
    recurrence      TEXT NOT NULL DEFAULT 'once' CHECK(recurrence IN ('once','daily','weekly','monthly')),
    status          TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused','completed','cancelled')),
    last_run_at     TEXT,
    task_id         TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scheduled_status_trigger ON scheduled_tasks(status, trigger_at);

CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    owner_agent_id  TEXT NOT NULL,
    intent          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','completed','failed','cancelled')),
    phase           TEXT DEFAULT '',
    progress_log    TEXT DEFAULT '[]',
    result_summary  TEXT DEFAULT '',
    session_id      TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id          TEXT PRIMARY KEY,
    agent_id    TEXT NOT NULL,
    title       TEXT DEFAULT 'New Chat',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL REFERENCES chat_sessions(id),
    role          TEXT NOT NULL,
    author        TEXT DEFAULT '',
    content       TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '{}',
    event_id      TEXT,
    timestamp     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS feed_posts (
    id              TEXT PRIMARY KEY,
    author_handle   TEXT NOT NULL,
    author_display  TEXT DEFAULT '',
    type            TEXT NOT NULL CHECK(type IN ('purchase','recommendation','review','research','inquiry','note','preference','contact_exchange','reshare')),
    content         TEXT NOT NULL,
    details_json    TEXT DEFAULT '{}',
    history_id      INTEGER,
    original_post_id TEXT,
    visibility      TEXT NOT NULL DEFAULT 'public' CHECK(visibility IN ('public','private')),
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_feed_posts_created ON feed_posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feed_posts_author ON feed_posts(author_handle);

CREATE TABLE IF NOT EXISTS feed_reactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id         TEXT NOT NULL REFERENCES feed_posts(id) ON DELETE CASCADE,
    user_handle     TEXT NOT NULL,
    reaction_type   TEXT NOT NULL CHECK(reaction_type IN ('like','interesting','helpful')),
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(post_id, user_handle, reaction_type)
);
CREATE INDEX IF NOT EXISTS idx_feed_reactions_post ON feed_reactions(post_id);

CREATE TABLE IF NOT EXISTS feed_comments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id         TEXT NOT NULL REFERENCES feed_posts(id) ON DELETE CASCADE,
    author_handle   TEXT NOT NULL,
    author_display  TEXT DEFAULT '',
    content         TEXT NOT NULL,
    parent_id       INTEGER REFERENCES feed_comments(id) ON DELETE CASCADE,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_feed_comments_post ON feed_comments(post_id);

CREATE TABLE IF NOT EXISTS user_integrations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_handle      TEXT NOT NULL,
    integration_type TEXT NOT NULL,
    config_json      TEXT NOT NULL DEFAULT '{}',
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE(user_handle, integration_type)
);
"""


def get_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Return a new connection with WAL mode and foreign keys enabled."""
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | Path | None = None) -> None:
    """Create all tables if they don't already exist."""
    path = db_path or DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_db(path)
    try:
        conn.executescript(_SCHEMA)
        # Backfill columns for existing DBs (no-op if already present)
        _ensure_column(conn, "users", "auto_inbox_enabled", "BOOLEAN DEFAULT 0")
        _ensure_column(conn, "users", "social_pulse_enabled", "BOOLEAN DEFAULT 0")
        _ensure_column(conn, "users", "social_pulse_frequency", "TEXT DEFAULT 'weekly'")
        _ensure_column(conn, "users", "feed_engagement_enabled", "BOOLEAN DEFAULT 0")
        _ensure_column(conn, "users", "feed_engagement_frequency", "TEXT DEFAULT 'daily'")
        _ensure_column(conn, "users", "a2a_max_turns", "INTEGER DEFAULT 3")
        _ensure_column(conn, "history", "visibility", "TEXT DEFAULT 'personal'")
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        cols = {r["name"] for r in rows}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    except Exception:
        pass
