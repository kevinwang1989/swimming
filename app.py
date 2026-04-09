import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from db.init_db import init_database

init_database()

import streamlit as st

st.set_page_config(
    page_title="游泳成绩分析系统",
    page_icon="🏊",
    layout="wide",
)

from style import apply_style
apply_style()

PAGES = [
    st.Page("home.py", title="首页", icon=":material/home:", default=True),
    st.Page("pages/1_📊_成绩总览.py", title="成绩总览", icon=":material/leaderboard:"),
    st.Page("pages/2_🏊_项目详情.py", title="项目详情", icon=":material/pool:"),
    st.Page("pages/3_🏅_排兵布阵.py", title="排兵布阵", icon=":material/groups:"),
    st.Page("pages/4_🔍_选手查询.py", title="选手查询", icon=":material/person_search:"),
    st.Page("pages/5_📈_对比分析.py", title="对比分析", icon=":material/compare_arrows:"),
    st.Page("pages/6_🏆_区县排名.py", title="区县排名", icon=":material/workspace_premium:"),
    st.Page("pages/8_📈_进步榜.py", title="进步榜", icon=":material/trending_up:"),
    st.Page("pages/7_💬_反馈与帮助.py", title="反馈与帮助", icon=":material/help:"),
]

pg = st.navigation(PAGES)
pg.run()
