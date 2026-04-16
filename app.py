import streamlit as st
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from db.init_db import init_database

init_database()

st.set_page_config(
    page_title="游泳成绩分析系统",
    page_icon="🏊",
    layout="wide",
)

from style import apply_style
apply_style()

from auth import require_auth
require_auth("首页")

from queries.results import get_competitions, get_site_stats

# ----------------------------------------------------------------------
# Hero banner
# ----------------------------------------------------------------------
stats = get_site_stats()
comps = get_competitions()

hero_meta = (
    f"{stats['competitions']} COMPETITIONS &nbsp;·&nbsp; "
    f"{stats['participants']} ATHLETES &nbsp;·&nbsp; "
    f"{stats['results']} RESULTS &nbsp;·&nbsp; "
    f"{stats['districts']} DISTRICTS"
)

st.markdown(
    f"""
    <div class="wa-hero">
        <div class="wa-hero-kicker">Shanghai · Youth Swimming</div>
        <h1 class="wa-hero-title">Shanghai Youth<br/>Swimming Analytics</h1>
        <div class="wa-hero-sub">
            2025-2026 赛季上海青少年游泳赛事数据分析平台 —— 成绩总览、分段洞察、
            排兵布阵、跨站追踪，一站式决策辅助。
        </div>
        <div class="wa-hero-meta">{hero_meta}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# KPI row
# ----------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("比赛场次", stats['competitions'])
k2.metric("参赛选手", stats['participants'])
k3.metric("成绩记录", stats['results'])
k4.metric("代表队", stats['districts'])

# ----------------------------------------------------------------------
# Recent competitions
# ----------------------------------------------------------------------
st.markdown("## Recent Competitions")

if comps.empty:
    st.info("尚未导入任何比赛数据。请前往「反馈与帮助」页面上传 PDF。")
else:
    cols = st.columns(max(len(comps), 1))
    for col, (_, comp) in zip(cols, comps.iterrows()):
        date_str = comp['date'] if comp['date'] else '日期未知'
        short = comp['short_name'] if 'short_name' in comp and comp['short_name'] else ''
        col.markdown(
            f"""
            <div class="wa-card">
                <div class="wa-card-kicker">Competition</div>
                <h3>{comp['name']}</h3>
                <p>{short}</p>
                <div class="wa-card-meta">{date_str}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ----------------------------------------------------------------------
# Explore the data — quick-link cards
# ----------------------------------------------------------------------
st.markdown("## Explore the Data")

QUICK_LINKS = [
    ("01", "成绩总览", "Results Overview",
     "按比赛、组别浏览完整成绩表，支持区/性别/百分位筛选。", "成绩总览"),
    ("02", "项目详情", "Event Details",
     "单项成绩 + 分段对比 + 自动生成中文深度分析洞察。", "项目详情"),
    ("03", "选手查询", "Athlete Profile",
     "跨站追踪单个选手的成绩演进，查看个人档案。", "选手查询"),
    ("04", "对比分析", "Comparison",
     "多选手同站 / 跨站对比，分段趋势一目了然。", "对比分析"),
    ("05", "区县排名", "District Ranking",
     "各区分项目聚合排名，整体实力评估。", "区县排名"),
    ("06", "进步榜", "Progress Leaderboard",
     "跨站对比同一选手的成绩变化，进步 / 退步一目了然。", "进步榜"),
    ("07", "反馈与帮助", "Feedback & Help",
     "意见反馈、数据导入、查看版本更新记录。", "反馈与帮助"),
]

# Render in 4-col grid (2 rows of 4 cards each).
# Wrap each card in an <a> tag pointing to the matching Streamlit page slug
# so clicking anywhere on the card navigates to that page.
for row_start in range(0, len(QUICK_LINKS), 4):
    row_items = QUICK_LINKS[row_start:row_start + 4]
    cols = st.columns(4)
    for col, item in zip(cols, row_items):
        num, cn, en, desc, slug = item
        col.markdown(
            f"""
            <a class="wa-card-link" href="/{slug}" target="_self">
                <div class="wa-card">
                    <div class="wa-card-kicker">{num} &nbsp;·&nbsp; {en}</div>
                    <h3>{cn}</h3>
                    <p>{desc}</p>
                </div>
            </a>
            """,
            unsafe_allow_html=True,
        )

st.markdown(
    """
    <div style="margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid #e3e8ef;
                color: #5b6b7d; font-size: 0.82rem; text-align: center;">
        使用左侧菜单切换页面 &nbsp;·&nbsp; 数据截至最近一次导入
    </div>
    """,
    unsafe_allow_html=True,
)
