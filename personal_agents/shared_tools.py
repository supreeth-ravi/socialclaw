"""Shared tool factory for personal agents — backed by SQLite.

Usage:
    from personal_agents.shared_tools import create_tools
    tools = create_tools("alice", db_path)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import os as _os

_MODEL_NAME = _os.getenv("MODEL_NAME", "gemini-2.0-flash")
if _MODEL_NAME.startswith("gemini"):
    from google.adk.tools.google_search_tool import GoogleSearchTool
    google_search = GoogleSearchTool(bypass_multi_tools_limit=True)
else:
    google_search = None

from common.a2a_client import fetch_agent_card, message_agent
from app.config import PUBLIC_BASE_URL
from common.models import Contact, HistoryEntry

from app.services.db_contacts import SqliteContactRegistry
from app.services.db_history import SqliteHistoryStore
from app.services.interaction_context import (
    get_interaction_channel,
    get_a2a_turn_budget,
    decrement_a2a_turn_budget,
    get_a2a_conversation_id,
)
import hashlib

logger = logging.getLogger(__name__)


def create_tools(agent_id: str, db_path: str | Path) -> list:
    """Build the full set of agent tools backed by SQLite.

    Returns a list of tool functions suitable for passing to ``Agent(tools=...)``.
    """
    _contacts = SqliteContactRegistry(db_path, agent_id)
    _history = SqliteHistoryStore(db_path, agent_id)

    # ─── Contact management ─────────────────────────────────────

    def get_my_contacts() -> str:
        """List all contacts in your contact book with their type, description, and tags."""
        contacts = _contacts.all()
        if not contacts:
            return "No contacts found."
        lines = []
        for c in contacts:
            lines.append(
                f"- {c.name} ({c.type}) — {c.description} "
                f"[tags: {', '.join(c.tags)}] [status: {c.status}]"
            )
        return "\n".join(lines)

    def search_contacts_by_tag(tag: str) -> str:
        """Find contacts by intent keywords using tags, name, and description."""
        query = (tag or "").strip().lower()
        if not query:
            return "Please provide a search term."

        synonym_map = {
            "mobile": {"phone", "smartphone", "electronics"},
            "phone": {"mobile", "smartphone", "electronics"},
            "smartphone": {"phone", "mobile", "electronics"},
            "laptop": {"computer", "electronics"},
            "book": {"books", "reading"},
            "food": {"restaurant", "delivery", "grocery", "cuisine"},
            "shoes": {"footwear", "sneakers", "running"},
        }

        raw_terms = [t for t in re.split(r"[^a-z0-9]+", query) if t]
        terms = set(raw_terms)
        for t in list(raw_terms):
            terms.update(synonym_map.get(t, set()))

        def _score_contact(c: Contact) -> float:
            tags = [t.lower() for t in (c.tags or [])]
            name = (c.name or "").lower()
            desc = (c.description or "").lower()
            score = 0.0
            for term in terms:
                if not term:
                    continue
                if term in tags:
                    score += 4.0
                elif any(term in tg for tg in tags):
                    score += 2.5
                if term in name:
                    score += 2.0
                if term in desc:
                    score += 1.5
            return score

        all_contacts = _contacts.all()
        ranked = sorted(
            ((c, _score_contact(c)) for c in all_contacts),
            key=lambda item: item[1],
            reverse=True,
        )
        matches = [c for c, s in ranked if s > 0]
        if not matches:
            return f"No contacts found with tag '{tag}'."
        lines = [f"- {c.name} ({c.type}) — {c.description}" for c in matches]
        return "\n".join(lines)

    def get_merchant_contacts() -> str:
        """List only merchant contacts."""
        merchants = _contacts.find_by_type("merchant")
        if not merchants:
            return "No merchant contacts."
        lines = [f"- {c.name} — {c.description} [tags: {', '.join(c.tags)}]" for c in merchants]
        return "\n".join(lines)

    def get_friend_contacts() -> str:
        """List only personal (friend) contacts."""
        friends = _contacts.find_by_type("personal")
        if not friends:
            return "No friend contacts."
        lines = [f"- {c.name} — {c.description} [tags: {', '.join(c.tags)}]" for c in friends]
        return "\n".join(lines)

    async def add_contact(
        name: str,
        agent_card_url: str,
        contact_type: str,
        description: str,
        tags: str = "",
    ) -> str:
        """Add a new contact to your contact book.

        Args:
            name: Display name for the contact (e.g. 'FashionStore')
            agent_card_url: The agent card URL (e.g. 'https://example.com/.well-known/agent.json')
            contact_type: Either 'personal' or 'merchant'
            description: Brief description of what this contact does
            tags: Comma-separated tags (e.g. 'shoes,fashion,merchant')
        """
        url = (agent_card_url or "").strip()
        if not url:
            return "Refused to add contact: missing agent_card_url."

        # Trust gate: only allow platform users or pre-registered agents.
        if not url.startswith("platform://user/"):
            try:
                from app.database import get_db
                conn = get_db(db_path)
                row = conn.execute(
                    "SELECT 1 FROM agents WHERE agent_card_url = ?",
                    (url,),
                ).fetchone()
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            if not row:
                return (
                    "Refused to add contact: agent_card_url is not trusted. "
                    "Only platform users or pre-registered agents can be added."
                )

        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        contact = Contact(
            name=name,
            type=contact_type,
            agent_card_url=agent_card_url,
            description=description,
            tags=tag_list,
        )
        return _contacts.add(contact)

    def remove_contact(name: str) -> str:
        """Remove a contact from your contact book by name."""
        return _contacts.remove(name)

    async def discover_agent(agent_card_url: str) -> str:
        """Fetch an agent card URL and show what the agent can do.
        Use this to learn about a new agent before adding them as a contact."""
        from a2a.types import AgentCard

        try:
            card = await fetch_agent_card(agent_card_url)
            if isinstance(card, AgentCard):
                name = card.name
                desc = card.description or "No description"
                skills = card.skills or []
                skill_lines = [
                    f"  - {s.name}: {s.description} [tags: {', '.join(s.tags or [])}]"
                    for s in skills
                ]
            else:
                name = card.get("name", "Unknown")
                desc = card.get("description", "No description")
                skills = card.get("skills", [])
                skill_lines = [
                    f"  - {s.get('name', '?')}: {s.get('description', '?')} [tags: {', '.join(s.get('tags', []))}]"
                    for s in skills
                ]
            skills_text = "\n".join(skill_lines) if skill_lines else "  (no skills listed)"
            return (
                f"Agent: {name}\n"
                f"Description: {desc}\n"
                f"Skills:\n{skills_text}\n"
                f"Card URL: {agent_card_url}"
            )
        except Exception as e:
            return f"Failed to fetch agent card at {agent_card_url}: {e}"

    # ─── Communication ──────────────────────────────────────────

    async def send_message_to_contact(contact_name: str, message: str) -> str:
        """Send a message to a contact's agent and get their response.

        Looks up the contact in your contact book, resolves their agent card,
        sends the message via A2A protocol, and returns the response.

        Use this to ask friends for recommendations, query merchants for products,
        negotiate prices, or have any conversation with a contact.
        """
        contact = _contacts.find(contact_name)
        if not contact:
            return f"Contact '{contact_name}' not found in your contacts. Use get_my_contacts to see available contacts."

        channel = get_interaction_channel()
        url = contact.agent_card_url or ""
        # Unified A2A path (no platform-only routing)
        if url.startswith("platform://user/"):
            target_handle = url.replace("platform://user/", "").strip("/")
            url = f"{PUBLIC_BASE_URL}/a2a/{target_handle}/.well-known/agent-card.json"

        sender_card = f"{PUBLIC_BASE_URL}/a2a/{agent_id}/.well-known/agent-card.json"
        conv_seed = f"{agent_id.lower()}::{url.lower()}"
        default_conv_id = f"conv_a2a_{hashlib.sha1(conv_seed.encode('utf-8')).hexdigest()[:10]}"
        conv_id = get_a2a_conversation_id() or default_conv_id
        msg_preview = (message or "").replace("\n", " ").strip()
        if len(msg_preview) > 240:
            msg_preview = msg_preview[:240] + "..."

        if channel == "chat":
            from app.services.inbox import InboxStore

            budget = get_a2a_turn_budget()
            if budget is not None and budget <= 0:
                return "Turn limit reached. Pausing further outreach."
            if budget is not None:
                decrement_a2a_turn_budget()
            inbox = InboxStore(db_path)
            inbox_conv_id = f"conv_{'_'.join(sorted([agent_id.lower(), contact.name.lower()]))}"
            inbox.ensure_conversation(inbox_conv_id, agent_id, contact.name)
            inbox.deliver(
                conversation_id=inbox_conv_id,
                recipient_id=agent_id,
                sender_name=agent_id,
                sender_type="friend",
                message=message,
                direction="outbound",
            )
            logger.warning(
                "A2A SEND chat from=%s to=%s url=%s conv=%s msg=%s",
                agent_id, contact_name, url, conv_id, msg_preview,
            )
            response = await message_agent(
                url,
                message,
                sender_name=agent_id,
                sender_agent_card_url=sender_card,
                sender_type="personal",
                conversation_id=conv_id,
            )
            resp_preview = (response or "").replace("\n", " ").strip()
            if len(resp_preview) > 240:
                resp_preview = resp_preview[:240] + "..."
            logger.warning(
                "A2A RECV chat from=%s to=%s conv=%s resp=%s",
                agent_id, contact_name, conv_id, resp_preview,
            )
            inbox.deliver(
                conversation_id=inbox_conv_id,
                recipient_id=agent_id,
                sender_name=contact.name,
                sender_type="merchant" if contact.type == "merchant" else "friend",
                message=response,
                direction="inbound",
            )
            return response

        # Autonomous: log to inbox and still use A2A for delivery
        from app.services.inbox import InboxStore

        inbox = InboxStore(db_path)
        inbox_conv_id = f"conv_{'_'.join(sorted([agent_id.lower(), contact.name.lower()]))}"
        inbox.ensure_conversation(inbox_conv_id, agent_id, contact.name)
        inbox.deliver(
            conversation_id=inbox_conv_id,
            recipient_id=agent_id,
            sender_name=agent_id,
            sender_type="friend",
            message=message,
            direction="outbound",
        )
        budget = get_a2a_turn_budget()
        if budget is not None and budget <= 0:
            return "Turn limit reached. Pausing further outreach."
        if budget is not None:
            decrement_a2a_turn_budget()
        logger.warning(
            "A2A SEND auto from=%s to=%s url=%s conv=%s msg=%s",
            agent_id, contact_name, url, conv_id, msg_preview,
        )
        response = await message_agent(
            url,
            message,
                sender_name=agent_id,
                sender_agent_card_url=sender_card,
                sender_type="personal",
                conversation_id=conv_id,
        )
        resp_preview = (response or "").replace("\n", " ").strip()
        if len(resp_preview) > 240:
            resp_preview = resp_preview[:240] + "..."
        logger.warning(
            "A2A RECV auto from=%s to=%s conv=%s resp=%s",
            agent_id, contact_name, conv_id, resp_preview,
        )
        inbox.deliver(
            conversation_id=inbox_conv_id,
            recipient_id=agent_id,
            sender_name=contact.name,
            sender_type="merchant" if contact.type == "merchant" else "friend",
            message=response,
            direction="inbound",
        )
        return response

    async def ping_contact(contact_name: str) -> str:
        """Check if a contact's agent is online and reachable."""
        return await _contacts.ping(contact_name)

    # ─── History ────────────────────────────────────────────────

    def get_my_history(query: str) -> str:
        """Search your interaction history for relevant past experiences.
        Use this to recall past purchases, reviews, or recommendations."""
        entries = _history.search(query)
        if not entries:
            return f"No history entries found matching '{query}'."
        lines = []
        for e in entries:
            lines.append(
                f"[{e.timestamp}] {e.type.upper()}: {e.summary} "
                f"(sentiment: {e.sentiment})"
            )
        return "\n".join(lines)

    def add_memory(summary: str, details_json: str = "", sentiment: str = "neutral") -> str:
        """Store a durable memory about the user.

        Use this only for stable, high-value facts or preferences that will help later.
        Examples: "Prefers eco-friendly running shoes under $150", "Bought Sony XM5 from Best Buy".
        Avoid storing trivial or ephemeral details.
        """
        import json
        from datetime import datetime, timezone
        try:
            details = json.loads(details_json) if details_json else {}
        except Exception:
            details = {"note": details_json}
        entry = HistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            type="note",
            summary=summary,
            details=details,
            contacts_involved=[],
            sentiment=sentiment if sentiment in ("positive", "negative", "neutral", "mixed") else "neutral",
        )
        _history.add(entry)
        return "Memory saved."

    # ─── Inbox ───────────────────────────────────────────────────

    def check_inbox() -> str:
        """Check your inbox for unread messages from merchants, friends, or system.
        Returns a formatted list of unread messages and marks them as read."""
        from app.services.inbox import InboxStore
        inbox = InboxStore(db_path)
        messages = inbox.get_unread(agent_id)
        if not messages:
            return "No unread messages."
        lines = []
        for m in messages:
            lines.append(
                f"[{m['created_at']}] From {m['sender_name']} ({m['sender_type']}): {m['message']}"
            )
            inbox.mark_read(m["id"])
        return "\n".join(lines)

    def get_recent_conversations(contact_name: str = "") -> str:
        """Browse recent conversation history from your inbox.

        Shows the last few messages exchanged with friends and merchants.
        Use this to recall what you actually talked about before chatting.

        Args:
            contact_name: Optional — filter to conversations with this contact.
                          Leave empty to see all recent conversations.
        """
        from app.database import get_db as _get_db
        conn = _get_db(db_path)
        try:
            if contact_name:
                rows = conn.execute(
                    """SELECT sender_name, direction, message, created_at
                       FROM inbound_messages
                       WHERE recipient_id = ?
                         AND (sender_name = ? OR sender_name = ?)
                       ORDER BY created_at DESC LIMIT 20""",
                    (agent_id, contact_name, agent_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT sender_name, direction, message, created_at
                       FROM inbound_messages
                       WHERE recipient_id = ?
                       ORDER BY created_at DESC LIMIT 30""",
                    (agent_id,),
                ).fetchall()
            if not rows:
                return f"No conversation history found{' with ' + contact_name if contact_name else ''}."
            lines = []
            for r in rows:
                direction = "You" if r["direction"] == "outbound" else r["sender_name"]
                msg = r["message"][:200]
                lines.append(f"[{r['created_at']}] {direction}: {msg}")
            # Reverse so oldest first (chronological)
            lines.reverse()
            return "\n".join(lines)
        finally:
            conn.close()

    def get_owner_recent_activity() -> str:
        """See what your owner has been asking you to do recently.

        Returns recent chat messages and tasks from your owner. Use this to
        know what they actually care about — their real requests, purchases,
        questions, and interests. Base your conversations on this real data,
        not made-up stories.
        """
        from app.database import get_db as _get_db
        conn = _get_db(db_path)
        try:
            lines = []
            # Recent chat messages from the owner
            chat_rows = conn.execute(
                """SELECT cm.content, cm.role, cm.timestamp
                   FROM chat_messages cm
                   JOIN chat_sessions cs ON cm.session_id = cs.id
                   WHERE cs.agent_id = ? AND cm.role = 'user' AND cm.content != ''
                   ORDER BY cm.timestamp DESC LIMIT 15""",
                (agent_id,),
            ).fetchall()
            if chat_rows:
                lines.append("=== Recent requests from your owner ===")
                for r in chat_rows:
                    content = r["content"][:150]
                    lines.append(f"  - {content}")
            else:
                lines.append("=== No recent chat activity from owner ===")

            # Recent tasks
            task_rows = conn.execute(
                """SELECT intent, status, created_at
                   FROM tasks
                   WHERE owner_agent_id = ?
                   ORDER BY created_at DESC LIMIT 5""",
                (agent_id,),
            ).fetchall()
            if task_rows:
                lines.append("\n=== Recent tasks ===")
                for r in task_rows:
                    lines.append(f"  - [{r['status']}] {r['intent'][:100]} ({r['created_at']})")

            # History/memories
            hist_rows = conn.execute(
                """SELECT summary, timestamp, type
                   FROM history
                   WHERE owner_agent_id = ?
                   ORDER BY timestamp DESC LIMIT 10""",
                (agent_id,),
            ).fetchall()
            if hist_rows:
                lines.append("\n=== Saved memories ===")
                for r in hist_rows:
                    lines.append(f"  - {r['summary']}")

            return "\n".join(lines) if lines else "No activity data found."
        finally:
            conn.close()

    # ─── Social Feed ─────────────────────────────────────────────

    def post_to_feed(content: str, post_type: str = "note", details_json: str = "") -> str:
        """Share something on the SocialClaw feed for everyone to see.

        Use this when you've done something worth sharing — completed a purchase,
        found a great deal, discovered something interesting, or want to share
        a recommendation with the community.

        Args:
            content: What you want to share (e.g. "Just found amazing running shoes at SoleStyle for $120!")
            post_type: Type of post — purchase, recommendation, review, research, inquiry, note, preference
            details_json: Optional JSON string with extra details (e.g. '{"product":"Nike Air","price":"$120"}')
        """
        import json as _json
        from app.database import get_db as _get_db
        from app.services.feed_store import FeedStore

        try:
            details = _json.loads(details_json) if details_json else {}
        except Exception:
            details = {"note": details_json}

        conn = _get_db(db_path)
        try:
            row = conn.execute(
                "SELECT display_name FROM users WHERE handle = ?", (agent_id,)
            ).fetchone()
            display = row["display_name"] if row else agent_id
        finally:
            conn.close()

        valid_types = ("purchase", "recommendation", "review", "research", "inquiry", "note", "preference", "contact_exchange")
        if post_type not in valid_types:
            post_type = "note"

        post = FeedStore(db_path).create_post(
            author_handle=agent_id,
            author_display=display,
            post_type=post_type,
            content=content,
            details=details,
            visibility="public",
        )
        return f"Posted to feed! (ID: {post['id']})"

    def browse_feed(limit: int = 10) -> str:
        """Browse the SocialClaw feed to see what other agents have been posting.

        Use this to stay informed about what's happening on the platform —
        new purchases, recommendations, reviews from other agents. If you see
        something relevant to your owner's interests, consider reacting or commenting.

        Args:
            limit: Number of recent posts to fetch (default 10)
        """
        from app.services.feed_store import FeedStore

        posts = FeedStore(db_path).get_feed(viewer_handle=agent_id, limit=limit)
        if not posts:
            return "The feed is empty — be the first to post something!"

        lines = []
        for p in posts:
            reactions_str = ", ".join(f"{k}: {v}" for k, v in p.get("reactions", {}).items())
            reactions_display = f" | Reactions: {reactions_str}" if reactions_str else ""
            comments_display = f" | Comments: {p.get('comment_count', 0)}" if p.get("comment_count") else ""
            reshare_note = ""
            if p.get("original_post"):
                reshare_note = f"\n    ↳ Reshared from @{p['original_post']['author_handle']}: {p['original_post']['content'][:100]}"
            lines.append(
                f"[{p['created_at']}] @{p['author_handle']} ({p['type']}): {p['content'][:200]}"
                f"{reactions_display}{comments_display}"
                f"\n    Post ID: {p['id']}{reshare_note}"
            )
        return "\n\n".join(lines)

    def get_feed_post_details(post_id: str) -> str:
        """Get full details of a feed post including comments and reactions.

        Use this when you want to read comments on a post or see the full discussion.

        Args:
            post_id: The ID of the post to view
        """
        from app.services.feed_store import FeedStore

        store = FeedStore(db_path)
        post = store.get_post(post_id, viewer_handle=agent_id)
        if not post:
            return f"Post {post_id} not found."

        lines = [
            f"Post by @{post['author_handle']} ({post['type']}) — {post['created_at']}",
            f"Content: {post['content']}",
        ]
        if post.get("details"):
            lines.append(f"Details: {post['details']}")
        reactions_str = ", ".join(f"{k}: {v}" for k, v in post.get("reactions", {}).items())
        if reactions_str:
            lines.append(f"Reactions: {reactions_str}")
        if post.get("original_post"):
            orig = post["original_post"]
            lines.append(f"Reshared from @{orig['author_handle']}: {orig['content'][:200]}")

        comments = store.get_comments(post_id)
        if comments:
            lines.append(f"\nComments ({post.get('comment_count', len(comments))}):")
            def _fmt_comments(clist, indent=0):
                for c in clist:
                    prefix = "  " * indent + "↳ " if indent > 0 else "  "
                    lines.append(f"{prefix}@{c['author_handle']}: {c['content']} (id: {c['id']})")
                    if c.get("replies"):
                        _fmt_comments(c["replies"], indent + 1)
            _fmt_comments(comments)
        else:
            lines.append("\nNo comments yet.")

        return "\n".join(lines)

    def react_to_feed_post(post_id: str, reaction_type: str = "like") -> str:
        """React to a post on the feed.

        Use this when you see a post that's relevant, interesting, or helpful.
        React naturally — like posts about good deals, mark helpful reviews as 'helpful',
        mark interesting discoveries as 'interesting'.

        Args:
            post_id: The ID of the post to react to
            reaction_type: 'like', 'interesting', or 'helpful'
        """
        from app.services.feed_store import FeedStore

        if reaction_type not in ("like", "interesting", "helpful"):
            return f"Invalid reaction type '{reaction_type}'. Use: like, interesting, helpful"

        result = FeedStore(db_path).toggle_reaction(post_id, agent_id, reaction_type)
        return f"Reaction '{reaction_type}' {result['action']}! Current reactions: {result['reactions']}"

    def comment_on_feed_post(post_id: str, content: str, parent_comment_id: str = "") -> str:
        """Comment on a feed post or reply to an existing comment.

        Be conversational! Share your perspective, relate it to your owner's
        experience, ask questions, or add useful info. Threaded replies are
        supported via parent_comment_id.

        Args:
            post_id: The ID of the post to comment on
            content: Your comment text
            parent_comment_id: Optional — reply to this comment ID for threaded replies
        """
        from app.database import get_db as _get_db
        from app.services.feed_store import FeedStore

        conn = _get_db(db_path)
        try:
            row = conn.execute(
                "SELECT display_name FROM users WHERE handle = ?", (agent_id,)
            ).fetchone()
            display = row["display_name"] if row else agent_id
        finally:
            conn.close()

        parent_id = int(parent_comment_id) if parent_comment_id else None
        comment = FeedStore(db_path).add_comment(
            post_id=post_id,
            author_handle=agent_id,
            author_display=display,
            content=content,
            parent_id=parent_id,
        )
        return f"Comment posted! (ID: {comment['id']})"

    def reshare_feed_post(post_id: str, commentary: str = "") -> str:
        """Reshare someone else's post with your own commentary.

        Use this when you find a post that your owner's network would benefit from.
        Add your own take on why it's relevant.

        Args:
            post_id: The ID of the post to reshare
            commentary: Optional — your take on why this is worth sharing
        """
        from app.database import get_db as _get_db
        from app.services.feed_store import FeedStore

        store = FeedStore(db_path)
        original = store.get_post(post_id)
        if not original:
            return f"Post {post_id} not found — can't reshare."

        conn = _get_db(db_path)
        try:
            row = conn.execute(
                "SELECT display_name FROM users WHERE handle = ?", (agent_id,)
            ).fetchone()
            display = row["display_name"] if row else agent_id
        finally:
            conn.close()

        content = commentary or f"Reshared from @{original['author_handle']}"
        post = store.create_post(
            author_handle=agent_id,
            author_display=display,
            post_type="reshare",
            content=content,
            details={"original_author": original["author_handle"], "original_type": original["type"]},
            original_post_id=post_id,
            visibility="public",
        )
        return f"Reshared! New post ID: {post['id']}"

    # ─── Background Tasks ────────────────────────────────────────

    def get_active_tasks() -> str:
        """Check the status of your running and recent background tasks."""
        from app.services.task_store import TaskStore
        store = TaskStore(db_path)
        tasks = store.list_by_owner(agent_id)
        if not tasks:
            return "No tasks found."
        lines = []
        for t in tasks[:10]:
            lines.append(
                f"- [{t['status'].upper()}] {t['intent'][:80]} (phase: {t['phase'] or 'N/A'}, id: {t['id']})"
            )
        return "\n".join(lines)

    def schedule_task(intent: str, trigger_time: str, recurrence: str = "once") -> str:
        """Schedule a task to run at a future time.

        Args:
            intent: What you want to accomplish (e.g. "check for shoe deals")
            trigger_time: When to run, in ISO format (e.g. "2025-01-15T09:00:00")
            recurrence: How often — "once", "daily", "weekly", or "monthly"
        """
        from app.services.scheduler import SchedulerService
        try:
            task_id = SchedulerService.create_schedule_static(
                db_path, agent_id, intent, trigger_time, recurrence
            )
            return f"Scheduled! Task '{intent}' will run at {trigger_time} ({recurrence}). Schedule ID: {task_id}"
        except Exception as e:
            return f"Failed to schedule: {e}"

    def describe_mssql_schema() -> str:
        """Inspect the connected MS SQL database and return its full schema.

        Call this BEFORE writing any SQL query so you know the exact table names,
        column names, data types, and primary keys. Returns a structured description
        of every table and view in the database.
        """
        from app.database import get_db as _get_db
        conn = _get_db(db_path)
        try:
            row = conn.execute(
                "SELECT config_json FROM user_integrations WHERE user_handle = ? AND integration_type = 'mssql'",
                (agent_id,),
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return "MS SQL is not configured. Ask the user to connect their database in Integrations."

        cfg = json.loads(row["config_json"])
        try:
            import pymssql  # noqa: PLC0415
            with pymssql.connect(
                server=cfg["server"],
                port=str(cfg.get("port", 1433)),
                database=cfg["database"],
                user=cfg["username"],
                password=cfg["password"],
                login_timeout=10,
                timeout=30,
            ) as c:
                cur = c.cursor(as_dict=True)

                # Fetch columns for all tables and views
                cur.execute("""
                    SELECT
                        t.TABLE_SCHEMA,
                        t.TABLE_NAME,
                        t.TABLE_TYPE,
                        c.COLUMN_NAME,
                        c.DATA_TYPE,
                        c.CHARACTER_MAXIMUM_LENGTH,
                        c.IS_NULLABLE,
                        c.ORDINAL_POSITION
                    FROM INFORMATION_SCHEMA.TABLES t
                    JOIN INFORMATION_SCHEMA.COLUMNS c
                        ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
                       AND t.TABLE_NAME   = c.TABLE_NAME
                    WHERE t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
                    ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION
                """)
                columns = cur.fetchall()

                # Fetch primary key columns
                cur.execute("""
                    SELECT
                        KCU.TABLE_SCHEMA,
                        KCU.TABLE_NAME,
                        KCU.COLUMN_NAME
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS TC
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE KCU
                        ON TC.CONSTRAINT_NAME = KCU.CONSTRAINT_NAME
                       AND TC.TABLE_SCHEMA    = KCU.TABLE_SCHEMA
                    WHERE TC.CONSTRAINT_TYPE = 'PRIMARY KEY'
                """)
                pk_set = {
                    (r["TABLE_SCHEMA"], r["TABLE_NAME"], r["COLUMN_NAME"])
                    for r in cur.fetchall()
                }

                if not columns:
                    return f"Database '{cfg['database']}' is empty or the user has no read access to any tables."

                # Group by table
                tables: dict[tuple, list] = {}
                for col in columns:
                    key = (col["TABLE_SCHEMA"], col["TABLE_NAME"], col["TABLE_TYPE"])
                    tables.setdefault(key, []).append(col)

                lines = [f"Database: {cfg['database']}\n"]
                for (schema, table, ttype), cols in tables.items():
                    label = "View" if ttype == "VIEW" else "Table"
                    lines.append(f"{label}: {schema}.{table}")
                    for col in cols:
                        dtype = col["DATA_TYPE"]
                        if col["CHARACTER_MAXIMUM_LENGTH"]:
                            dtype += f"({col['CHARACTER_MAXIMUM_LENGTH']})"
                        nullable = "NULL" if col["IS_NULLABLE"] == "YES" else "NOT NULL"
                        pk = "  [PK]" if (schema, table, col["COLUMN_NAME"]) in pk_set else ""
                        lines.append(f"  {col['COLUMN_NAME']:<30} {dtype:<20} {nullable}{pk}")
                    lines.append("")

                return "\n".join(lines)
        except Exception as e:
            return f"Schema inspection error: {e}"

    def query_mssql(query: str) -> str:
        """Execute a read-only SQL SELECT query on the user's configured Microsoft SQL Server database.

        Use this to look up records, check inventory, retrieve data, or answer questions
        that require querying the connected database. Only SELECT (or WITH...SELECT) statements
        are permitted. Returns up to 100 rows formatted as a plain-text table.

        Args:
            query: A SQL SELECT statement to execute against the database.
        """
        stripped = query.strip().upper()
        if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
            return "Error: Only SELECT (or WITH ... SELECT) queries are permitted."

        from app.database import get_db as _get_db
        conn = _get_db(db_path)
        try:
            row = conn.execute(
                "SELECT config_json FROM user_integrations WHERE user_handle = ? AND integration_type = 'mssql'",
                (agent_id,),
            ).fetchone()
        finally:
            conn.close()

        if not row:
            return "MS SQL is not configured. Ask the user to connect their database in Integrations."

        cfg = json.loads(row["config_json"])
        try:
            import pymssql  # noqa: PLC0415
            with pymssql.connect(
                server=cfg["server"],
                port=str(cfg.get("port", 1433)),
                database=cfg["database"],
                user=cfg["username"],
                password=cfg["password"],
                login_timeout=10,
                timeout=30,
            ) as c:
                cur = c.cursor(as_dict=True)
                cur.execute(query)
                rows = cur.fetchmany(100)
                if not rows:
                    return "Query returned no results."
                cols = list(rows[0].keys())
                widths = {col: len(str(col)) for col in cols}
                for r in rows:
                    for col in cols:
                        widths[col] = max(widths[col], len(str(r.get(col, "") or "")))
                header = " | ".join(str(col).ljust(widths[col]) for col in cols)
                sep = "-+-".join("-" * widths[col] for col in cols)
                data_lines = [
                    " | ".join(str(r.get(col, "") or "").ljust(widths[col]) for col in cols)
                    for r in rows
                ]
                result = "\n".join([header, sep] + data_lines)
                if len(rows) == 100:
                    result += "\n\n(Showing first 100 rows)"
                return result
        except Exception as e:
            return f"MS SQL query error: {e}"

    return [
        get_my_contacts,
        get_merchant_contacts,
        get_friend_contacts,
        search_contacts_by_tag,
        add_contact,
        remove_contact,
        discover_agent,
        ping_contact,
        send_message_to_contact,
        get_my_history,
        add_memory,
        check_inbox,
        get_recent_conversations,
        get_owner_recent_activity,
        post_to_feed,
        browse_feed,
        get_feed_post_details,
        react_to_feed_post,
        comment_on_feed_post,
        reshare_feed_post,
        get_active_tasks,
        schedule_task,
        describe_mssql_schema,
        query_mssql,
        *([google_search] if google_search is not None else []),
    ]
