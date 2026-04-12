import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

st.set_page_config(page_title="使用分析", layout="wide")

from style import init_page
init_page(
    title="📊 使用分析",
    subtitle="用户访问行为分析与邀请码管理（仅管理员可见）。",
    kicker="09 · Analytics & User Management",
    min_role="admin",
)

from db.connection import get_db
from auth.models import (
    create_invite_code,
    deactivate_user,
    activate_user,
    list_users,
    delete_expired_sessions,
)
from auth.guard import ROLE_LABEL

# Clean up expired sessions on page load
delete_expired_sessions()

# ── Overview metrics ─────────────────────────────────────────
st.markdown("### 📈 访问概览")

conn = get_db()
try:
    total_users = conn.execute("SELECT COUNT(*) FROM app_user").fetchone()[0]
    active_users_7d = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM analytics_event WHERE event_type='page_view' AND created_at >= datetime('now', '-7 days')"
    ).fetchone()[0]
    pv_today = conn.execute(
        "SELECT COUNT(*) FROM analytics_event WHERE event_type='page_view' AND date(created_at) = date('now')"
    ).fetchone()[0]
    pv_week = conn.execute(
        "SELECT COUNT(*) FROM analytics_event WHERE event_type='page_view' AND created_at >= datetime('now', '-7 days')"
    ).fetchone()[0]
    pv_total = conn.execute(
        "SELECT COUNT(*) FROM analytics_event WHERE event_type='page_view'"
    ).fetchone()[0]
finally:
    conn.close()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("总用户数", total_users)
m2.metric("7日活跃", active_users_7d)
m3.metric("今日 PV", pv_today)
m4.metric("本周 PV", pv_week)
m5.metric("累计 PV", pv_total)

# ── Page popularity ──────────────────────────────────────────
st.markdown("---")
st.markdown("### 📊 页面热度")

conn = get_db()
try:
    page_df = pd.read_sql_query(
        """
        SELECT page, COUNT(*) as pv
        FROM analytics_event
        WHERE event_type = 'page_view' AND page IS NOT NULL
        GROUP BY page
        ORDER BY pv DESC
        """,
        conn,
    )
finally:
    conn.close()

if not page_df.empty:
    import plotly.express as px
    fig = px.bar(
        page_df, x="page", y="pv",
        labels={"page": "页面", "pv": "访问次数"},
        color_discrete_sequence=["#0282c6"],
    )
    fig.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("暂无访问数据。")

# ── Daily trend ──────────────────────────────────────────────
st.markdown("### 📅 每日趋势（近 30 天）")

conn = get_db()
try:
    daily_df = pd.read_sql_query(
        """
        SELECT date(created_at) as day, COUNT(*) as pv
        FROM analytics_event
        WHERE event_type = 'page_view'
          AND created_at >= datetime('now', '-30 days')
        GROUP BY date(created_at)
        ORDER BY day
        """,
        conn,
    )
finally:
    conn.close()

if not daily_df.empty:
    import plotly.express as px
    fig2 = px.line(
        daily_df, x="day", y="pv",
        labels={"day": "日期", "pv": "PV"},
        markers=True,
    )
    fig2.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("暂无趋势数据。")

# ── User activity table ──────────────────────────────────────
st.markdown("### 👤 用户活跃度")

conn = get_db()
try:
    user_activity = pd.read_sql_query(
        """
        SELECT u.display_name AS 昵称,
               u.role AS 角色,
               COUNT(a.id) AS 总访问,
               MAX(a.created_at) AS 最近在线,
               (SELECT a2.page FROM analytics_event a2
                WHERE a2.user_id = u.id AND a2.event_type='page_view'
                GROUP BY a2.page ORDER BY COUNT(*) DESC LIMIT 1
               ) AS 最常访问
        FROM app_user u
        LEFT JOIN analytics_event a ON a.user_id = u.id AND a.event_type = 'page_view'
        GROUP BY u.id
        ORDER BY 总访问 DESC
        """,
        conn,
    )
finally:
    conn.close()

if not user_activity.empty:
    st.dataframe(user_activity, use_container_width=True, hide_index=True)
else:
    st.info("暂无用户活跃数据。")

# ── User management ──────────────────────────────────────────
st.markdown("---")
st.markdown("### 👥 用户管理")

# Generate new invite code
st.markdown("**➕ 生成新邀请码**")
gc1, gc2, gc3 = st.columns([2, 1, 1])
with gc1:
    new_name = st.text_input("备注名", placeholder="如：张教练、李妈妈", key="new_user_name")
with gc2:
    new_role = st.selectbox("角色", ["viewer", "coach", "admin"], key="new_user_role",
                            format_func=lambda r: f"{r} ({ROLE_LABEL.get(r, r)})")
with gc3:
    st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)  # spacer
    gen_btn = st.button("生成邀请码", type="primary", use_container_width=True)

if gen_btn:
    if not new_name or not new_name.strip():
        st.error("请输入备注名。")
    else:
        code = create_invite_code(new_name.strip(), new_role)
        st.success(f"生成成功！邀请码：**{code}**")
        st.code(code, language=None)
        st.caption("请将此邀请码通过微信发送给对方。")

# User list with actions
st.markdown("---")
st.markdown("**📋 已有用户**")

users_df = list_users()
if not users_df.empty:
    for _, row in users_df.iterrows():
        uid = row["id"]
        name = row["display_name"]
        role = row["role"]
        code = row["invite_code"]
        active = bool(row["is_active"])
        last_login = row["last_login_at"] or "—"

        status_badge = "🟢 活跃" if active else "🔴 已停用"
        role_label = ROLE_LABEL.get(role, role)

        col_info, col_action = st.columns([4, 1])
        with col_info:
            st.markdown(
                f"**{name}** &nbsp;·&nbsp; {role_label} &nbsp;·&nbsp; "
                f"`{code}` &nbsp;·&nbsp; 最后登录：{last_login} &nbsp;·&nbsp; {status_badge}"
            )
        with col_action:
            # Don't allow deactivating yourself
            current_user = st.session_state.get("user", {})
            if uid != current_user.get("id"):
                if active:
                    if st.button("停用", key=f"deact_{uid}", type="secondary"):
                        deactivate_user(uid)
                        st.rerun()
                else:
                    if st.button("启用", key=f"act_{uid}", type="secondary"):
                        activate_user(uid)
                        st.rerun()
else:
    st.info("暂无用户。")
