"""Authentication guard for every page.

Provides `require_auth(page_name, min_role)` which each page calls at the top.
It checks Cookie → session → login form, and blocks rendering until the user
is authenticated with sufficient role.
"""

from __future__ import annotations

import streamlit as st
from streamlit_cookies_controller import CookieController

from auth.models import (
    create_session,
    redeem_code,
    update_display_name,
    validate_session,
)

# Role hierarchy: higher level = more access
ROLE_LEVEL = {"viewer": 1, "coach": 2, "admin": 3}
ROLE_LABEL = {"viewer": "普通用户", "coach": "教练", "admin": "管理员"}

_COOKIE_NAME = "swim_token"
_COOKIE_MAX_AGE = 86400  # 24 hours in seconds


def _get_cookie_controller() -> CookieController:
    """Return a singleton CookieController (must be called once per page)."""
    if "cookie_ctrl" not in st.session_state:
        st.session_state["cookie_ctrl"] = CookieController()
    return st.session_state["cookie_ctrl"]


def _log_event(event_type: str, page: str = None, detail: str = None):
    """Fire-and-forget analytics insert. Never raises."""
    try:
        from db.connection import get_db

        user = st.session_state.get("user")
        user_id = user["id"] if user else None
        conn = get_db()
        conn.execute(
            "INSERT INTO analytics_event (user_id, event_type, page, detail) VALUES (?, ?, ?, ?)",
            (user_id, event_type, page, detail),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _authenticate() -> dict | None:
    """Try to authenticate via session_state or cookie. Returns user dict or None."""
    # 1. Already authenticated this Streamlit session?
    user = st.session_state.get("user")
    if user:
        return user

    # 2. Try cookie
    ctrl = _get_cookie_controller()
    token = ctrl.get(_COOKIE_NAME)
    if token:
        user = validate_session(token)
        if user:
            st.session_state["user"] = user
            return user
        else:
            # Cookie is stale/expired — remove it
            ctrl.remove(_COOKIE_NAME)

    return None


def _render_login_form():
    """Render a centered login card. Handles code submission."""
    st.markdown(
        """
        <style>
        .login-container {
            max-width: 420px;
            margin: 6rem auto 2rem auto;
            padding: 2.5rem 2rem;
            background: linear-gradient(135deg, #003a5d 0%, #005a8d 100%);
            border-radius: 16px;
            text-align: center;
            color: white;
        }
        .login-container h2 {
            font-family: 'Oswald', sans-serif;
            font-size: 1.6rem;
            margin-bottom: 0.3rem;
            color: white;
        }
        .login-container p {
            font-size: 0.95rem;
            opacity: 0.85;
            margin-bottom: 1.5rem;
        }
        .login-footer {
            text-align: center;
            color: #888;
            font-size: 0.85rem;
            margin-top: 1rem;
        }
        </style>
        <div class="login-container">
            <h2>🏊 上海青少年游泳成绩分析系统</h2>
            <p>请输入邀请码以访问</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Use columns to center the form
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        # Check if we're in "first login" flow (code accepted, need nickname)
        if st.session_state.get("_pending_user"):
            pending = st.session_state["_pending_user"]
            st.success(f"邀请码验证通过！角色：{ROLE_LABEL.get(pending['role'], pending['role'])}")
            nickname = st.text_input(
                "请输入你的昵称",
                placeholder="如：张教练、李妈妈",
                key="_nickname_input",
            )
            if st.button("确认并进入", type="primary", use_container_width=True):
                if not nickname or not nickname.strip():
                    st.error("请输入昵称。")
                else:
                    update_display_name(pending["id"], nickname.strip())
                    pending["display_name"] = nickname.strip()
                    token = create_session(pending["id"])
                    ctrl = _get_cookie_controller()
                    ctrl.set(_COOKIE_NAME, token, max_age=_COOKIE_MAX_AGE)
                    st.session_state["user"] = pending
                    st.session_state.pop("_pending_user", None)
                    _log_event("login", detail=f"user_id={pending['id']}")
                    st.rerun()
            return

        # Normal login flow
        code = st.text_input(
            "邀请码",
            placeholder="SWIM-XXXX",
            key="_invite_code_input",
            label_visibility="collapsed",
        )
        if st.button("进入系统", type="primary", use_container_width=True):
            if not code or not code.strip():
                st.error("请输入邀请码。")
            else:
                user = redeem_code(code)
                if user is None:
                    st.error("邀请码无效或已被停用。")
                    _log_event("login_fail", detail=f"code={code.strip()}")
                else:
                    # Check if display_name is default "Admin" or looks like placeholder
                    if user["display_name"] in ("Admin", "待设置"):
                        # First login — need nickname
                        st.session_state["_pending_user"] = user
                        st.rerun()
                    else:
                        # Returning user — skip nickname
                        token = create_session(user["id"])
                        ctrl = _get_cookie_controller()
                        ctrl.set(_COOKIE_NAME, token, max_age=_COOKIE_MAX_AGE)
                        st.session_state["user"] = user
                        _log_event("login", detail=f"user_id={user['id']}")
                        st.rerun()

        st.markdown(
            '<div class="login-footer">没有邀请码？请联系管理员获取。</div>',
            unsafe_allow_html=True,
        )


def get_current_user() -> dict | None:
    """Return the current authenticated user dict, or None."""
    return st.session_state.get("user")


def require_auth(page_name: str, min_role: str = "viewer"):
    """Gate a page behind authentication + role check.

    Call this at the top of every page after apply_style(). If the user is not
    authenticated, renders a login form and calls st.stop(). If authenticated
    but role is insufficient, shows a permission warning and calls st.stop().
    """
    user = _authenticate()

    if user is None:
        _render_login_form()
        st.stop()

    # Role check
    user_level = ROLE_LEVEL.get(user.get("role", ""), 0)
    required_level = ROLE_LEVEL.get(min_role, 1)
    if user_level < required_level:
        role_cn = ROLE_LABEL.get(min_role, min_role)
        st.warning(
            f"⚠️ 该页面仅对 **{role_cn}** 及以上角色开放。\n\n"
            f"当前账号：{user['display_name']}（{ROLE_LABEL.get(user['role'], user['role'])}）\n\n"
            f"如需升级权限，请联系管理员。"
        )
        st.stop()

    # Log page view (deduplicate within same Streamlit script run)
    _pv_key = f"_pv_logged_{page_name}"
    if not st.session_state.get(_pv_key):
        _log_event("page_view", page_name)
        st.session_state[_pv_key] = True
