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

st.title("🏊 游泳成绩分析系统")
st.markdown("---")

st.markdown("""
### 功能导航

使用左侧菜单访问各功能页面：

- **📊 成绩总览** — 按比赛、组别浏览完整成绩表
- **🔍 选手查询** — 搜索选手，查看个人档案和历史成绩
- **📈 对比分析** — 选手横向对比、跨站追踪趋势
- **🏆 区县排名** — 各区整体实力分析
- **💬 反馈与帮助** — 意见反馈、数据导入
""")

# Show quick stats
from queries.results import get_competitions
comps = get_competitions()
if not comps.empty:
    st.markdown("### 已导入的比赛")
    for _, comp in comps.iterrows():
        st.markdown(f"- **{comp['name']}** ({comp['date'] or '日期未知'})")
else:
    st.info("尚未导入任何比赛数据。请前往「导入数据」页面上传 PDF。")
