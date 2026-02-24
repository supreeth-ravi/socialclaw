"""Test: Agent query routing + MS SQL text-to-query (mocked DB).

Tests:
  1. Direct question  → agent answers without tools
  2. History question → agent calls get_my_history only
  3. DB question      → agent calls describe_mssql_schema then query_mssql

Run:
    uv run python test_agent_flow.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("flow_test")

sys.path.insert(0, str(Path(__file__).parent))

from app.database import init_db, get_db
from app.services.agent_runner import get_or_create_runner, AgentRunnerService
from app.services.event_serializer import serialize_event
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types

# ── Fake MS SQL setup ─────────────────────────────────────────────

FAKE_SCHEMA = """Database: SalesDB

Table: dbo.Orders
  OrderID          int            NOT NULL  [PK]
  CustomerName     varchar(100)   NOT NULL
  Product          varchar(200)   NOT NULL
  Amount           decimal        NOT NULL
  Status           varchar(50)    NOT NULL
  CreatedAt        datetime       NOT NULL

Table: dbo.Products
  ProductID        int            NOT NULL  [PK]
  Name             varchar(200)   NOT NULL
  Category         varchar(100)   NOT NULL
  Price            decimal        NOT NULL
  Stock            int            NOT NULL
"""

FAKE_QUERY_RESULTS = {
    "pending": "Status         | COUNT\nPending        | 12",
    "default": "OrderID | CustomerName | Product            | Amount | Status  \n1       | Alice        | Running Shoes      | 129.99 | Pending \n2       | Bob          | Wireless Headphones| 89.99  | Shipped ",
}


def make_fake_pymssql(query: str = "") -> str:
    q = query.upper()
    if "COUNT" in q and "PENDING" in q:
        return FAKE_QUERY_RESULTS["pending"]
    return FAKE_QUERY_RESULTS["default"]


# ── Test infrastructure ───────────────────────────────────────────

DB_PATH = Path("/tmp/test_agent_flow.db")

TEST_USER = "testuser"
TEST_DISPLAY = "Test User"


def seed_db():
    init_db(DB_PATH)
    conn = get_db(DB_PATH)
    try:
        # Upsert test user
        conn.execute("""
            INSERT OR REPLACE INTO users
              (id, email, handle, password_hash, display_name, is_onboarded)
            VALUES (?, ?, ?, 'x', ?, 1)
        """, (TEST_USER, f"{TEST_USER}@test.com", TEST_USER, TEST_DISPLAY))

        # Seed fake MSSQL config
        conn.execute("""
            INSERT OR REPLACE INTO user_integrations
              (user_handle, integration_type, config_json)
            VALUES (?, 'mssql', ?)
        """, (TEST_USER, json.dumps({
            "server": "fake-server",
            "port": 1433,
            "database": "SalesDB",
            "username": "sa",
            "password": "fake-password",
        })))

        # Seed a bit of history
        conn.execute("""
            INSERT OR IGNORE INTO history
              (owner_agent_id, timestamp, type, summary, details_json, sentiment)
            VALUES (?, datetime('now'), 'purchase', 'Bought Nike Air Zoom Pegasus 41 for $142', '{}', 'positive')
        """, (TEST_USER,))

        conn.commit()
    finally:
        conn.close()


def make_session() -> str:
    sid = f"test_{uuid.uuid4().hex[:8]}"
    conn = get_db(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO chat_sessions (id, agent_id, title) VALUES (?, ?, ?)",
            (sid, TEST_USER, "Flow test"),
        )
        conn.commit()
    finally:
        conn.close()
    return sid


async def run_query(runner_svc: AgentRunnerService, session_id: str, message: str):
    """Send a message and collect all tool calls + final text."""
    from app.services.interaction_context import reset_interaction_channel, set_interaction_channel

    content = types.Content(role="user", parts=[types.Part(text=message)])
    run_config = RunConfig(streaming_mode=StreamingMode.SSE)

    tool_calls: list[str] = []
    tool_args: dict[str, dict] = {}
    final_text = ""

    token = set_interaction_channel("chat")
    try:
        async for event in runner_svc.runner.run_async(
            user_id=TEST_USER,
            session_id=session_id,
            new_message=content,
            run_config=run_config,
        ):
            for payload in serialize_event(event):
                if payload["type"] == "function_call":
                    tool_calls.append(payload["name"])
                    tool_args[payload["name"]] = payload.get("args", {})
                elif payload["type"] == "text" and not payload.get("partial"):
                    final_text = payload["content"]
    finally:
        reset_interaction_channel(token)

    return tool_calls, tool_args, final_text


def print_result(label: str, tool_calls: list, tool_args: dict, text: str):
    print(f"\n{'─'*60}")
    print(f"  TEST: {label}")
    print(f"{'─'*60}")
    if tool_calls:
        print(f"  Tools called: {', '.join(tool_calls)}")
        if "query_mssql" in tool_args:
            q = tool_args["query_mssql"].get("query", "")
            print(f"  SQL generated:\n    {q}")
    else:
        print("  Tools called: (none)")
    print(f"  Response: {text[:300]}{'...' if len(text) > 300 else ''}")


def check(label: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    return condition


# ── Patched pymssql that returns fake data ────────────────────────

class FakeCursor:
    def __init__(self):
        self._rows = []

    def execute(self, sql, *args):
        sql_upper = sql.upper().strip()
        if "INFORMATION_SCHEMA.TABLES" in sql_upper:
            # Schema columns query
            self._rows = [
                {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Orders", "TABLE_TYPE": "BASE TABLE",
                 "COLUMN_NAME": "OrderID", "DATA_TYPE": "int", "CHARACTER_MAXIMUM_LENGTH": None,
                 "IS_NULLABLE": "NO", "ORDINAL_POSITION": 1},
                {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Orders", "TABLE_TYPE": "BASE TABLE",
                 "COLUMN_NAME": "CustomerName", "DATA_TYPE": "varchar", "CHARACTER_MAXIMUM_LENGTH": 100,
                 "IS_NULLABLE": "NO", "ORDINAL_POSITION": 2},
                {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Orders", "TABLE_TYPE": "BASE TABLE",
                 "COLUMN_NAME": "Product", "DATA_TYPE": "varchar", "CHARACTER_MAXIMUM_LENGTH": 200,
                 "IS_NULLABLE": "NO", "ORDINAL_POSITION": 3},
                {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Orders", "TABLE_TYPE": "BASE TABLE",
                 "COLUMN_NAME": "Amount", "DATA_TYPE": "decimal", "CHARACTER_MAXIMUM_LENGTH": None,
                 "IS_NULLABLE": "NO", "ORDINAL_POSITION": 4},
                {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Orders", "TABLE_TYPE": "BASE TABLE",
                 "COLUMN_NAME": "Status", "DATA_TYPE": "varchar", "CHARACTER_MAXIMUM_LENGTH": 50,
                 "IS_NULLABLE": "NO", "ORDINAL_POSITION": 5},
                {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Products", "TABLE_TYPE": "BASE TABLE",
                 "COLUMN_NAME": "ProductID", "DATA_TYPE": "int", "CHARACTER_MAXIMUM_LENGTH": None,
                 "IS_NULLABLE": "NO", "ORDINAL_POSITION": 1},
                {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Products", "TABLE_TYPE": "BASE TABLE",
                 "COLUMN_NAME": "Name", "DATA_TYPE": "varchar", "CHARACTER_MAXIMUM_LENGTH": 200,
                 "IS_NULLABLE": "NO", "ORDINAL_POSITION": 2},
                {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Products", "TABLE_TYPE": "BASE TABLE",
                 "COLUMN_NAME": "Price", "DATA_TYPE": "decimal", "CHARACTER_MAXIMUM_LENGTH": None,
                 "IS_NULLABLE": "NO", "ORDINAL_POSITION": 3},
                {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Products", "TABLE_TYPE": "BASE TABLE",
                 "COLUMN_NAME": "Stock", "DATA_TYPE": "int", "CHARACTER_MAXIMUM_LENGTH": None,
                 "IS_NULLABLE": "NO", "ORDINAL_POSITION": 4},
            ]
        elif "TABLE_CONSTRAINTS" in sql_upper:
            # Primary keys query
            self._rows = [
                {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Orders", "COLUMN_NAME": "OrderID"},
                {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Products", "COLUMN_NAME": "ProductID"},
            ]
        elif "@@VERSION" in sql_upper:
            self._rows = [("Microsoft SQL Server 2022 (RTM)",)]
        else:
            # Data query — return sample rows
            self._rows = [
                {"OrderID": 1, "CustomerName": "Alice", "Product": "Running Shoes", "Amount": 129.99, "Status": "Pending"},
                {"OrderID": 2, "CustomerName": "Bob",   "Product": "Headphones",    "Amount": 89.99,  "Status": "Shipped"},
                {"OrderID": 3, "CustomerName": "Carol", "Product": "Running Shoes", "Amount": 142.00, "Status": "Pending"},
            ]

    def fetchall(self):
        return self._rows

    def fetchmany(self, n):
        return self._rows[:n]

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def cursor(self, as_dict=False):
        return FakeCursor()


def fake_pymssql_connect(**kwargs):
    return FakeConnection()


# ── Main ──────────────────────────────────────────────────────────

async def main():
    print("\n" + "=" * 60)
    print("  AGENT FLOW + MS SQL TEXT-TO-QUERY TESTS")
    print("=" * 60)

    seed_db()

    # Patch pymssql globally before runner is created
    fake_pymssql = MagicMock()
    fake_pymssql.connect = fake_pymssql_connect

    with patch.dict("sys.modules", {"pymssql": fake_pymssql}):
        runners: dict[str, AgentRunnerService] = {}
        runner_svc = get_or_create_runner(runners, TEST_USER, DB_PATH, TEST_DISPLAY)

        # Fresh session per test to avoid cross-contamination
        results = []

        # ── Test 1: Direct question ──────────────────────────────
        print("\n[1/3] Running: Direct factual question...")
        sid = make_session()
        tools, args, text = await run_query(
            runner_svc, sid,
            "What is the capital of Japan?"
        )
        print_result("Direct question — no tools expected", tools, args, text)
        social_tools = [t for t in tools if t in (
            "send_message_to_contact", "get_friend_contacts",
            "get_merchant_contacts", "search_contacts_by_tag",
        )]
        p1a = check("No social tools triggered", len(social_tools) == 0,
                    f"got: {social_tools}" if social_tools else "")
        p1b = check("Response is not empty", len(text) > 5)
        results.append(("Direct question", p1a and p1b))

        # ── Test 2: History question ─────────────────────────────
        print("\n[2/3] Running: History question...")
        sid = make_session()
        tools, args, text = await run_query(
            runner_svc, sid,
            "What was the last thing I bought?"
        )
        print_result("History question — get_my_history expected", tools, args, text)
        p2a = check("get_my_history called", "get_my_history" in tools)
        p2b = check("No unsolicited merchant/friend contact", not any(
            t in tools for t in ("send_message_to_contact",)
        ))
        results.append(("History question", p2a and p2b))

        # ── Test 3: MS SQL text-to-query ─────────────────────────
        print("\n[3/3] Running: MS SQL natural language → SQL...")
        sid = make_session()
        tools, args, text = await run_query(
            runner_svc, sid,
            "How many orders are there in the database? Show me by status."
        )
        print_result("MS SQL — describe_schema then query_mssql expected", tools, args, text)

        p3a = check("describe_mssql_schema called", "describe_mssql_schema" in tools)
        p3b = check("query_mssql called", "query_mssql" in tools)
        sql = args.get("query_mssql", {}).get("query", "")
        p3c = check("Generated SQL is a SELECT",
                    sql.strip().upper().startswith("SELECT"),
                    f"got: {sql[:120]}")
        p3d = check("SQL references Orders table",
                    "orders" in sql.lower() or "order" in sql.lower(),
                    f"sql: {sql[:120]}")
        results.append(("MS SQL text-to-query", p3a and p3b and p3c and p3d))

    # ── Summary ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"\n  {passed}/{len(results)} tests passed")
    print("=" * 60 + "\n")

    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
