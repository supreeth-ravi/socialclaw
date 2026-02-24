# Onboarding Flow & Multi-User Architecture

## Overview

Transform the single-user, hardcoded-Alice app into a multi-user platform with:
- Handle-based identity (`ai.social/your_handle`)
- JWT auth (email + password)
- Per-user personal agents (auto-created on signup)
- Onboarding flow: landing → auth → agent discovery → chat
- Left nav with avatar, settings, and contacts pages

---

## Data Model Changes

### New Table: `users`

```sql
CREATE TABLE users (
    id            TEXT PRIMARY KEY,          -- UUID
    email         TEXT UNIQUE NOT NULL,
    handle        TEXT UNIQUE NOT NULL,      -- also serves as agent_id
    password_hash TEXT NOT NULL,
    display_name  TEXT DEFAULT '',
    is_onboarded  BOOLEAN DEFAULT 0,        -- completed discovery step
    created_at    TEXT DEFAULT (datetime('now'))
);
```

- `handle` doubles as the user's `agent_id` everywhere (contacts, history, sessions, runner)
- No separate agents table row needed at signup — the agent is virtual (created in-memory from the handle)
- Existing tables (`contacts`, `history`, `chat_sessions`) already key by `owner_agent_id` / `agent_id` — so they work as-is once we pass the user's handle as agent_id

---

## Architecture

### Auth Flow
```
Landing (/)  →  Auth (/auth?handle=x)  →  App (/app)
    │                   │                      │
    │  type handle      │  login/signup        │  JWT in localStorage
    │  → redirect       │  → get JWT           │  → all API calls
    └───────────────────┴──────────────────────┘
```

### Per-User Agent Runners
```
app.state.runners = {}   # Dict[agent_id, AgentRunnerService]

On first chat message:
  1. Check if runner exists for user's agent_id (handle)
  2. If not, create Agent + tools + InMemoryRunner
  3. Cache in runners dict
  4. Use for all subsequent messages
```

### Page Structure
```
/                  → landing.html    (handle input)
/auth              → auth.html       (login/signup)
/app               → app.html        (main app with left nav)
  └─ Left Nav:
       - Avatar + handle
       - Chat        (default view)
       - Contacts    (accept/invite/discover)
       - Settings    (profile, handle)
       - Logout
```

---

## Implementation Phases

### Phase 1: Database + Auth Backend

**New files:**

1. **`app/auth.py`** — Auth utilities
   - `hash_password(password) → str` using `bcrypt` (or `passlib`)
   - `verify_password(plain, hashed) → bool`
   - `create_token(user_id, handle) → str` JWT with `PyJWT`, 7-day expiry
   - `decode_token(token) → dict` with expiry validation
   - `JWT_SECRET` from env var or generated on first run
   - `get_current_user(request) → user_dict` FastAPI dependency that extracts + validates JWT from `Authorization: Bearer <token>` header

2. **`app/routers/auth_router.py`** — Auth endpoints
   - `POST /api/auth/signup` — body: `{email, password, handle, display_name?}`
     - Validate handle (alphanumeric + underscores, 3-20 chars)
     - Check handle + email uniqueness
     - Hash password, insert user
     - Return `{token, user: {id, email, handle, display_name}}`
   - `POST /api/auth/login` — body: `{email, password}`
     - Verify credentials
     - Return `{token, user: {id, email, handle, display_name, is_onboarded}}`
   - `GET /api/auth/me` — (protected)
     - Return current user info from token
   - `POST /api/auth/check-handle` — body: `{handle}`
     - Return `{available: bool}` for real-time validation

**Modified files:**

3. **`app/database.py`** — Add `users` table to `init_db()`

4. **`app/models.py`** — Add pydantic models:
   - `SignupRequest(email, password, handle, display_name?)`
   - `LoginRequest(email, password)`
   - `UserOut(id, email, handle, display_name, is_onboarded, created_at)`
   - `TokenResponse(token, user: UserOut)`

5. **`app/main.py`** — Register auth router, add CORS if needed

**New dependency:** `PyJWT`, `bcrypt` (add to pyproject.toml)

---

### Phase 2: Per-User Agent System

**Modified files:**

1. **`app/main.py`** — Lifespan changes
   - Remove hardcoded Alice agent creation
   - Initialize `app.state.runners = {}` (empty dict)
   - Add `get_or_create_runner(agent_id) → AgentRunnerService` helper
     - Lazily creates Agent + tools + InMemoryRunner for user's agent_id
     - Caches in `app.state.runners`
   - Keep `app.state.active_agent` removal — no longer needed

2. **`app/services/agent_runner.py`** — Add runner pool
   - `get_or_create_runner(app_state, agent_id)` function
   - Creates agent with `create_personal_agent(agent_id)` (generic personal agent, not Alice-specific)
   - Tools created with `create_tools(agent_id, DB_PATH)`

3. **`personal_agents/shared_agent.py`** — New generic personal agent factory
   - `create_personal_agent(agent_id, display_name=None) → Agent`
   - Generic instruction (not Alice/Bob-specific persona)
   - Same tools interface as Alice/Bob

4. **`app/routers/chat.py`** — Auth-protect, use user's agent_id
   - Add `current_user = Depends(get_current_user)`
   - Get runner via `get_or_create_runner(request.app.state, current_user["handle"])`
   - Validate session belongs to user's agent_id

5. **`app/routers/sessions.py`** — Auth-protect
   - All endpoints use `current_user["handle"]` as agent_id
   - No more `agent_id` query param — derived from JWT

6. **`app/routers/contacts.py`** — Auth-protect
   - All endpoints use `current_user["handle"]` as agent_id
   - Keep invite, ping-all, agent-card endpoints
   - Add `POST /api/contacts/accept` for incoming invites (future)

---

### Phase 3: Landing Page + Auth Pages

**New files:**

1. **`app/static/landing.html`** — Landing page
   - Clean, centered design
   - `ai.social/` text + input field for handle
   - Real-time handle availability check (debounced)
   - "Continue" button → redirects to `/auth?handle=<value>`
   - If already logged in (JWT in localStorage), redirect to `/app`

2. **`app/static/landing.js`** — Landing page logic
   - Handle input validation (alphanumeric, 3-20 chars)
   - Debounced `POST /api/auth/check-handle` call
   - Green/red indicator for availability
   - Redirect logic

3. **`app/static/auth.html`** — Auth page
   - Two tabs: Login / Sign Up
   - **Sign Up tab:** handle (pre-filled from URL param, readonly), email, password, confirm password, display name (optional)
   - **Login tab:** email, password
   - Error display
   - On success: store JWT in localStorage, redirect to `/app`

4. **`app/static/auth.js`** — Auth page logic
   - Tab switching
   - Form validation
   - API calls to `/api/auth/signup` and `/api/auth/login`
   - JWT storage + redirect

**Modified files:**

5. **`app/main.py`** — New routes
   - `GET /` → serve `landing.html`
   - `GET /auth` → serve `auth.html`
   - `GET /app` → serve `app.html`
   - Handle route `GET /{handle}` — redirect to `/auth?handle={handle}` (optional, for shareable links)

---

### Phase 4: App Layout Redesign

**Modified files:**

1. **`app/static/index.html` → rename to `app/static/app.html`**
   - New layout structure:
   ```
   ┌──────────────────────────────────────────┐
   │ Left Nav (60px) │ Content Area           │
   │                 │                         │
   │ [Avatar]        │ (Chat / Contacts /     │
   │ @handle         │  Settings page)        │
   │                 │                         │
   │ 💬 Chat         │                         │
   │ 👥 Contacts     │                         │
   │ ⚙️ Settings     │                         │
   │                 │                         │
   │ [Logout]        │                         │
   └──────────────────────────────────────────┘
   ```
   - Remove the old contacts panel from the right side — contacts get their own page
   - Chat view: sessions sidebar (left of content) + chat area (same as now but without right contacts panel)
   - Contacts view: full content area for contact management
   - Settings view: full content area for user settings
   - Each "view" is a `<div>` that gets shown/hidden

2. **`app/static/app.js`** — Major refactor
   - Add JWT-based API helper: `apiFetch(url, options)` that adds Authorization header
   - Add auth check on load: verify JWT, redirect to `/` if invalid
   - Add nav switching: `showPage('chat' | 'contacts' | 'settings')`
   - Load user info on init (`GET /api/auth/me`) for avatar + handle display
   - Remove hardcoded `activeAgent = 'alice'` — get from user context
   - All `fetch()` calls → use `apiFetch()` wrapper
   - Remove `agent_id` query params from API calls (server derives from JWT)
   - **Onboarding check**: if `user.is_onboarded === false`, show discovery view first

3. **`app/static/style.css`** — New styles
   - Left nav styles (fixed width, dark, vertical layout)
   - Nav item styles (icon + label, active state)
   - Avatar placeholder styles
   - Page container styles
   - Contact management page styles (cards, accept/reject buttons)
   - Settings form styles

---

### Phase 5: Contacts Page

**The contacts page in the app replaces the old right-side panel.**

**Frontend (in app.js or separate contacts-page.js):**

Contacts page layout:
```
┌─────────────────────────────────────────┐
│ Contacts                    [+ Invite]  │
├─────────────────────────────────────────┤
│                                         │
│ PLATFORM AGENTS (shown if !onboarded)   │
│ ┌─────────────────────────────────────┐ │
│ │ SoleStyle Shoes        [+ Add]     │ │
│ │ Shoe shopping assistant            │ │
│ ├─────────────────────────────────────┤ │
│ │ TechMart Electronics   [+ Add]     │ │
│ │ Electronics deals                  │ │
│ ├─────────────────────────────────────┤ │
│ │ FreshBite Grocery      [+ Add]     │ │
│ │ Fresh food delivery                │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ MY CONTACTS                             │
│ ┌─────────────────────────────────────┐ │
│ │ Friends                            │ │
│ │   Bob  🟢  [Chat] [Remove]        │ │
│ ├─────────────────────────────────────┤ │
│ │ Merchants                          │ │
│ │   SoleStyle 🟢 [Chat] [Remove]    │ │
│ │   TechMart  🔴 [Chat] [Remove]    │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ [Done — Go to Chat] (if onboarding)     │
└─────────────────────────────────────────┘
```

**Backend additions:**

1. **`app/routers/platform.py`** — Platform agent discovery
   - `GET /api/platform/agents` — returns all registered agents (from `agents` table) that the user hasn't already added as contacts
   - Used for the onboarding discovery step

2. **`app/routers/auth_router.py`** — Add onboarding completion
   - `POST /api/auth/complete-onboarding` — sets `is_onboarded = 1` for current user

3. **`app/routers/contacts.py`** — Keep existing endpoints, add:
   - `POST /api/contacts/add-platform-agent` — body: `{agent_id}` — looks up agent in `agents` table, adds as contact (for the discovery cards)

---

### Phase 6: Settings Page

Simple settings page:

```
┌─────────────────────────────────────────┐
│ Settings                                │
├─────────────────────────────────────────┤
│                                         │
│ Profile                                 │
│ ┌─────────────────────────────────────┐ │
│ │ Handle:       @supreeth            │ │
│ │ Email:        supreeth@email.com   │ │
│ │ Display Name: [Supreeth      ]     │ │
│ │                        [Save]      │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ Agent                                   │
│ ┌─────────────────────────────────────┐ │
│ │ Your agent ID: supreeth            │ │
│ │ Agent card URL: (if exposed)       │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ Danger Zone                             │
│ ┌─────────────────────────────────────┐ │
│ │ [Delete Account]                   │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Backend:**
- `PATCH /api/auth/profile` — update display_name (in auth_router.py)

---

## File Summary

### New Files (10)
| File | Purpose |
|------|---------|
| `app/auth.py` | JWT + bcrypt utilities, `get_current_user` dependency |
| `app/routers/auth_router.py` | signup, login, me, check-handle, complete-onboarding, profile |
| `app/routers/platform.py` | Platform agent discovery for onboarding |
| `personal_agents/shared_agent.py` | Generic personal agent factory (replaces hardcoded Alice) |
| `app/static/landing.html` | Landing page — handle input |
| `app/static/landing.js` | Landing page logic |
| `app/static/auth.html` | Login/signup page |
| `app/static/auth.js` | Auth page logic |
| `app/static/app.html` | Main app (renamed from index.html, redesigned) |
| `app/static/common.js` | Shared utilities (apiFetch, auth helpers, redirect logic) |

### Modified Files (10)
| File | Changes |
|------|---------|
| `app/database.py` | Add `users` table |
| `app/models.py` | Add user/auth pydantic models |
| `app/main.py` | Multi-user lifespan, new page routes, auth router |
| `app/config.py` | Add JWT_SECRET config |
| `app/routers/chat.py` | Auth-protect, per-user runner |
| `app/routers/sessions.py` | Auth-protect, derive agent_id from JWT |
| `app/routers/contacts.py` | Auth-protect, add platform-agent endpoint |
| `app/services/agent_runner.py` | Runner pool (lazy creation per user) |
| `app/static/app.js` | Auth integration, nav, page switching, remove hardcoded agent |
| `app/static/style.css` | Nav, auth page, contacts page, settings styles |
| `pyproject.toml` | Add `PyJWT`, `bcrypt` dependencies |

### Deleted/Renamed
| From | To |
|------|-----|
| `app/static/index.html` | `app/static/app.html` (redesigned) |

---

## Implementation Order

1. **Phase 1**: Database + Auth backend (foundation)
2. **Phase 2**: Per-user agent system (core architecture change)
3. **Phase 3**: Landing + Auth pages (enables user flow)
4. **Phase 4**: App layout redesign (new nav, views)
5. **Phase 5**: Contacts page with discovery (onboarding)
6. **Phase 6**: Settings page (polish)

Each phase is independently testable. Phase 1-3 gets the auth flow working. Phase 4-6 builds the full UI.

---

## Seed Data

On first boot (or via migration), register platform agents in `agents` table so they appear in discovery:

```python
PLATFORM_AGENTS = [
    {"id": "solestyle", "name": "SoleStyle Shoes", "type": "merchant",
     "description": "Your personal shoe shopping assistant",
     "agent_card_url": "http://localhost:8010/.well-known/agent-card.json"},
    {"id": "techmart", "name": "TechMart Electronics", "type": "merchant",
     "description": "Electronics deals and recommendations",
     "agent_card_url": "http://localhost:8011/.well-known/agent-card.json"},
    {"id": "freshbite", "name": "FreshBite Grocery", "type": "merchant",
     "description": "Fresh food and grocery delivery",
     "agent_card_url": "http://localhost:8012/.well-known/agent-card.json"},
]
```
