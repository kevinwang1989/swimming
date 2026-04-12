"""Analytics event logging helpers.

The core page_view logging is handled inside guard.py's require_auth().
This module provides additional helpers for action-level tracking.
"""

from __future__ import annotations

import json

import streamlit as st

from db.connection import get_db


def log_event(event_type: str, page: str | None = None, detail=None):
    """Insert an analytics event. Never raises — analytics must not break the app."""
    try:
        user = st.session_state.get("user")
        user_id = user["id"] if user else None
        detail_str = json.dumps(detail, ensure_ascii=False) if isinstance(detail, dict) else detail
        conn = get_db()
        conn.execute(
            "INSERT INTO analytics_event (user_id, event_type, page, detail) VALUES (?, ?, ?, ?)",
            (user_id, event_type, page, detail_str),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def log_action(page: str, action: str, detail=None):
    """Convenience wrapper for logging a user action on a specific page."""
    log_event(action, page, detail)
