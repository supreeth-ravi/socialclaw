"""JWT + bcrypt utilities and FastAPI dependency for authentication."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Request

from .config import JWT_ALGORITHM, JWT_EXPIRY_DAYS, JWT_SECRET
from .database import get_db

_HANDLE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,19}$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: str, handle: str) -> str:
    payload = {
        "sub": user_id,
        "handle": handle,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def validate_handle(handle: str) -> bool:
    return bool(_HANDLE_RE.match(handle))


def get_current_user(request: Request) -> dict:
    """FastAPI dependency — extracts JWT from Authorization header, returns user row."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = auth_header[7:]
    claims = decode_token(token)

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (claims["sub"],)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="User not found")
        return dict(row)
    finally:
        conn.close()
