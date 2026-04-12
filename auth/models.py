"""Database operations for user authentication and session management."""

from __future__ import annotations

import os
import secrets
import string
from datetime import datetime, timedelta

import pandas as pd

from db.connection import get_db


# ---------------------------------------------------------------------------
# Invite-code generation
# ---------------------------------------------------------------------------

_CODE_CHARS = string.ascii_uppercase + string.digits  # A-Z 0-9
_CODE_LEN = 4
_CODE_PREFIX = "SWIM-"


def _random_code() -> str:
    """Generate a random invite code like SWIM-A3K9."""
    suffix = "".join(secrets.choice(_CODE_CHARS) for _ in range(_CODE_LEN))
    return f"{_CODE_PREFIX}{suffix}"


def create_invite_code(display_name: str, role: str = "viewer") -> str:
    """Generate a unique invite code and insert an app_user row.

    Returns the invite code string (e.g. 'SWIM-A3K9').
    """
    conn = get_db()
    try:
        for _ in range(20):  # retry on collision
            code = _random_code()
            try:
                conn.execute(
                    "INSERT INTO app_user (display_name, role, invite_code) VALUES (?, ?, ?)",
                    (display_name, role, code),
                )
                conn.commit()
                return code
            except Exception:
                continue
        raise RuntimeError("Failed to generate unique invite code after 20 attempts")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Code redemption
# ---------------------------------------------------------------------------

def redeem_code(code: str) -> dict | None:
    """Look up an invite code (case-insensitive). Return user dict or None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, display_name, role, invite_code, is_active FROM app_user WHERE UPPER(invite_code) = ?",
            (code.strip().upper(),),
        ).fetchone()
        if row is None:
            return None
        if not row["is_active"]:
            return None
        return dict(row)
    finally:
        conn.close()


def update_display_name(user_id: int, display_name: str):
    """Update the display name for a user (first login personalization)."""
    conn = get_db()
    try:
        conn.execute("UPDATE app_user SET display_name = ? WHERE id = ?", (display_name, user_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

_SESSION_DURATION_HOURS = 24


def create_session(user_id: int) -> str:
    """Create a new session token (24h expiry). Returns the token string."""
    token = secrets.token_hex(16)
    expires = datetime.utcnow() + timedelta(hours=_SESSION_DURATION_HOURS)
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO user_session (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires.strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.execute(
            "UPDATE app_user SET last_login_at = datetime('now') WHERE id = ?",
            (user_id,),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def validate_session(token: str) -> dict | None:
    """Validate a session token. Returns user dict or None if invalid/expired."""
    if not token:
        return None
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT u.id, u.display_name, u.role, u.invite_code, u.is_active,
                   s.id AS session_id, s.expires_at
            FROM user_session s
            JOIN app_user u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
        if row is None:
            return None
        if not row["is_active"]:
            return None
        # Check expiry
        expires = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
        if datetime.utcnow() > expires:
            return None
        return {
            "id": row["id"],
            "display_name": row["display_name"],
            "role": row["role"],
            "invite_code": row["invite_code"],
            "session_id": row["session_id"],
        }
    finally:
        conn.close()


def touch_last_login(user_id: int):
    """Update last_login_at timestamp."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE app_user SET last_login_at = datetime('now') WHERE id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Admin: user management
# ---------------------------------------------------------------------------

def list_users() -> pd.DataFrame:
    """Return all users as a DataFrame."""
    conn = get_db()
    try:
        df = pd.read_sql_query(
            "SELECT id, display_name, role, invite_code, is_active, created_at, last_login_at FROM app_user ORDER BY created_at",
            conn,
        )
        return df
    finally:
        conn.close()


def deactivate_user(user_id: int):
    """Deactivate a user (revoke access)."""
    conn = get_db()
    try:
        conn.execute("UPDATE app_user SET is_active = 0 WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def activate_user(user_id: int):
    """Re-activate a previously deactivated user."""
    conn = get_db()
    try:
        conn.execute("UPDATE app_user SET is_active = 1 WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def delete_expired_sessions():
    """Remove expired sessions from the database."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM user_session WHERE expires_at < datetime('now')")
        conn.commit()
    finally:
        conn.close()
