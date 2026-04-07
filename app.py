import streamlit as st
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from db.init_db import init_database
from db.connection import get_db

init_database()

st.set_page_config(
    page_title="SwimRank - 游泳成绩分析",
    page_icon="🏊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.markdown("## 🏊 SwimRank")

# ---- Header ----
st.markdown("""
<div style="text-align: center; padding: 2rem 0 1rem 0;">
    <h1 style="font-size: 3rem; margin-bottom: 0.2rem;">🏊 SwimRank</h1>
    <p style="font-size: 1.2rem; color: #666;">上海青少年游泳成绩分析平台</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ---- Load stats ----
from queries.results import get_competitions

comps = get_competitions()

if comps.empty:
    st.info("尚未导入任何比赛数据。请前往「导入数据」页面上传 PDF。")
    st.stop()

conn = get_db()
total_participants = conn.execute("SELECT COUNT(*) FROM participant").fetchone()[0]
total_results = conn.execute("SELECT COUNT(*) FROM result").fetchone()[0]
total_districts = conn.execute("SELECT COUNT(DISTINCT district) FROM participant").fetchone()[0]
total_groups = conn.execute("SELECT COUNT(*) FROM enrollment").fetchone()[0]
conn.close()

# ---- Metric cards ----
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("比赛站数", f"{len(comps)} 站")
with col2:
    st.metric("选手总数", f"{total_participants} 人")
with col3:
    st.metric("成绩记录", f"{total_results} 条")
with col4:
    st.metric("参赛区县", f"{total_districts} 个")

st.markdown("")

# ---- Competition list ----
st.markdown("### 已导入的比赛")
for _, comp in comps.iterrows():
    conn = get_db()
    comp_count = conn.execute(
        "SELECT COUNT(*) FROM enrollment WHERE competition_id=?", (comp['id'],)
    ).fetchone()[0]
    conn.close()
    st.markdown(f"- **{comp['name']}**　📅 {comp['date'] or '日期未知'}　👤 {comp_count} 人参赛")

st.markdown("")

# ---- District overview for latest competition ----
latest_comp = comps.iloc[0]
conn = get_db()
district_stats = pd.read_sql_query("""
    SELECT p.district as 区县,
           COUNT(DISTINCT p.id) as 参赛人数,
           ROUND(AVG(e.total_score), 1) as 平均分
    FROM enrollment e
    JOIN participant p ON p.id = e.participant_id
    WHERE e.competition_id = ?
    GROUP BY p.district
    ORDER BY 平均分 DESC
""", conn, params=(latest_comp['id'],))
conn.close()

col_left, col_right = st.columns(2)

with col_left:
    st.markdown(f"### 各区平均分（{latest_comp['short_name']}）")
    import plotly.express as px
    fig = px.bar(
        district_stats,
        x='区县', y='平均分',
        color='平均分',
        color_continuous_scale='blues',
        text='平均分',
    )
    fig.update_traces(textposition='outside', textfont_size=11)
    fig.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        margin=dict(t=10, b=0),
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.markdown(f"### 各区参赛人数（{latest_comp['short_name']}）")
    fig2 = px.bar(
        district_stats.sort_values('参赛人数', ascending=False),
        x='区县', y='参赛人数',
        color='参赛人数',
        color_continuous_scale='greens',
        text='参赛人数',
    )
    fig2.update_traces(textposition='outside', textfont_size=11)
    fig2.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        margin=dict(t=10, b=0),
        height=350,
    )
    st.plotly_chart(fig2, use_container_width=True)

# ---- Quick nav ----
st.markdown("---")
st.markdown("### 快速导航")

nav1, nav2, nav3, nav4 = st.columns(4)
with nav1:
    st.page_link("pages/1_📊_成绩总览.py", label="📊 成绩总览", icon="📊")
    st.caption("按比赛、组别浏览完整成绩表")
with nav2:
    st.page_link("pages/2_🔍_选手查询.py", label="🔍 选手查询", icon="🔍")
    st.caption("搜索选手，查看个人档案")
with nav3:
    st.page_link("pages/3_📈_对比分析.py", label="📈 对比分析", icon="📈")
    st.caption("选手对比、跨站追踪趋势")
with nav4:
    st.page_link("pages/4_🏆_区县排名.py", label="🏆 区县排名", icon="🏆")
    st.caption("各区整体实力分析")

st.markdown("")
st.markdown("<div style='text-align: center; color: #aaa; padding: 2rem 0;'>SwimRank v1.0 — Built for swimmers 🏊</div>", unsafe_allow_html=True)
