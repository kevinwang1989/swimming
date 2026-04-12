"""跨站进步榜 — Cross-competition progress leaderboard."""

import streamlit as st
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.progress import (
    get_progress_data,
    filter_progress,
    summary_stats,
    top_improvers,
    top_regressors,
    get_filter_options,
)
from queries.lineup import fmt_time

st.set_page_config(page_title="进步榜", layout="wide")

from style import init_page
init_page(
    title="📈 跨站进步榜",
    subtitle="对比同一选手在不同比赛中的成绩变化，找出进步最大 / 退步最大的人和项目。",
    kicker="08 · Progress Leaderboard",
)

# ---- Load data ----
raw_df = get_progress_data()

if raw_df.empty:
    st.info("当前数据库里没有可对比的跨站成绩。需要至少两场比赛中同一选手参加同一项目。")
    st.stop()

opts = get_filter_options(raw_df)

# ---- Filters ----
c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
with c1:
    gender = st.selectbox("性别", ["全部"] + opts['genders'], index=0)
with c2:
    group_name = st.selectbox("组别", ["全部"] + opts['groups'], index=0)
with c3:
    event_name = st.selectbox("项目", ["全部"] + opts['events'], index=0)
with c4:
    district = st.selectbox("区县", ["全部"] + opts['districts'], index=0)

c5, c6 = st.columns([1, 1])
with c5:
    top_n = st.slider("Top N", min_value=5, max_value=50, value=20, step=5)
with c6:
    sort_by = st.radio(
        "排序方式",
        options=["按秒数 (绝对值)", "按百分比 (相对值)"],
        horizontal=True,
        index=0,
    )

by = 'seconds' if sort_by.startswith("按秒") else 'pct'

filtered = filter_progress(
    raw_df,
    gender=None if gender == "全部" else gender,
    group_name=None if group_name == "全部" else group_name,
    event_name=None if event_name == "全部" else event_name,
    district=None if district == "全部" else district,
)

# ---- Summary KPI row ----
stats = summary_stats(filtered)
k1, k2, k3, k4 = st.columns(4)
k1.metric("可对比项目", stats['total'])
k2.metric("进步项目", stats['improved'])
k3.metric("退步项目", stats['regressed'])
k4.metric("平均 Δ", f"{stats['avg_delta']:+.2f}s")

if stats['total'] == 0:
    st.warning("当前筛选条件下没有数据。请放宽条件。")
    st.stop()


# ---- Render helper ----
def _render_table(df: pd.DataFrame, kind: str):
    """Render a leaderboard slice as a styled DataFrame."""
    if df.empty:
        st.info(f"暂无{kind}数据。")
        return

    display = pd.DataFrame({
        '排名': range(1, len(df) + 1),
        '选手': df['name'].values,
        '区县': df['district'].values,
        '组别': df['group_label'].values,
        '项目': df['event_name'].values,
        '旧成绩': df['earlier_seconds'].apply(fmt_time).values,
        '新成绩': df['later_seconds'].apply(fmt_time).values,
        'Δ秒': df['delta_seconds'].apply(lambda x: f"{x:+.2f}").values,
        'Δ%': df['delta_pct'].apply(lambda x: f"{x:+.1f}%").values,
    })
    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        column_config={
            '排名': st.column_config.NumberColumn(width="small"),
            '选手': st.column_config.TextColumn(width="small"),
            '区县': st.column_config.TextColumn(width="small"),
            '组别': st.column_config.TextColumn(width="medium",
                help="若跨年导致年龄组变动，会显示「旧组 → 新组」"),
            '项目': st.column_config.TextColumn(width="medium"),
        },
    )


# ---- Tabs: improvers / regressors ----
tab1, tab2, tab3 = st.tabs([
    f"🚀 进步榜 Top {top_n}",
    f"📉 退步榜 Top {top_n}",
    "📋 全部明细",
])

with tab1:
    st.markdown("**进步榜**：成绩变快的选手，按变化幅度排序")
    _render_table(top_improvers(filtered, top_n=top_n, by=by), "进步")

with tab2:
    st.markdown("**退步榜**：成绩变慢的选手，按变化幅度排序")
    _render_table(top_regressors(filtered, top_n=top_n, by=by), "退步")

with tab3:
    st.markdown(f"全部 {stats['total']} 条可对比记录（按 Δ 升序排列，越靠前进步越大）")
    sort_col = 'delta_seconds' if by == 'seconds' else 'delta_pct'
    _render_table(filtered.sort_values(sort_col).reset_index(drop=True), "明细")


with st.expander("📖 计算口径"):
    st.markdown(
        """
        - **数据来源**：同一选手在两场不同比赛中参加**同一项目**，即可纳入对比。
        - **跨年升组**：C/D/E/F 是按年龄分组的窄年龄段，跨年后会整体平移
          （例如 2025 年的女 C → 2026 年的女 B），此时"组别"列会显示
          `女C → 女B`，表示该选手虽然分组标签变了，但还是同一个人的进步。
        - **顶部"组别"筛选器**基于**旧比赛的组别**（即起点组别）。
        - **过滤条件**：仅纳入正常完赛（排除犯规、弃权、缺赛）；
          仅纳入计时类游泳项目（排除体能类项目）。
        - **Δ 秒**：负数代表进步（变快），正数代表退步（变慢）。
        - **Δ %**：相对旧成绩的百分比变化，对不同距离项目更公平
          （50 米快 0.5 秒 ≈ 200 米快 2 秒）。
        """
    )
