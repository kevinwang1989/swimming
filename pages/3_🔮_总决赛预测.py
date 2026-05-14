"""总决赛预测 — Finals prediction from the two 2026 qualifying stations."""

import streamlit as st
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.finals_prediction import (
    get_station_results,
    get_group_enrollment_counts,
    compute_qualifiers,
    compute_event_predictions,
    compute_event_cutoffs,
    get_filter_options,
    PATH_A_PCT,
    PATH_B_TOP_N,
    FINALS_CUTOFF_RANK,
)
from queries.lineup import fmt_time

st.set_page_config(page_title="总决赛预测", layout="wide")

from style import init_page
init_page(
    title="🔮 总决赛预测",
    subtitle="基于第一站、第二站两站资格赛，预测 2026 总决赛晋级名单与各单项前16名。",
    kicker="03 · Finals Prediction",
)

# ---- Load data ----
results_df = get_station_results()

if results_df.empty:
    st.info("当前数据库里没有第一站 / 第二站的成绩数据，无法预测。")
    st.stop()

counts = get_group_enrollment_counts()
qualifiers_df = compute_qualifiers(results_df, counts)
predictions_df = compute_event_predictions(results_df, qualifiers_df)
cutoffs_df = compute_event_cutoffs(predictions_df)

opts = get_filter_options(results_df)

# ---- Filters ----
c1, c2, _ = st.columns([1, 1, 3])
with c1:
    gender = st.selectbox("性别", opts['genders'], index=0)
with c2:
    group_name = st.selectbox("组别", opts['groups'], index=0)

group_label = f"{gender}{group_name}"

grp_quals = qualifiers_df[qualifiers_df['group_label'] == group_label] \
    if not qualifiers_df.empty else pd.DataFrame()
grp_preds = predictions_df[predictions_df['group_label'] == group_label] \
    if not predictions_df.empty else pd.DataFrame()
grp_cutoffs = cutoffs_df[cutoffs_df['group_label'] == group_label] \
    if not cutoffs_df.empty else pd.DataFrame()

if grp_quals.empty:
    st.warning(f"{group_label} 组暂无可预测的数据。")
    st.stop()

# ---- Tabs ----
tab1, tab2 = st.tabs(["🎫 晋级名单", "🥇 各单项前16预测"])

with tab1:
    n_total = len(grp_quals)
    n_a_only = int(((grp_quals['path_a']) & (~grp_quals['path_b'])).sum())
    n_b_only = int(((~grp_quals['path_a']) & (grp_quals['path_b'])).sum())
    n_both = int(((grp_quals['path_a']) & (grp_quals['path_b'])).sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("晋级总人数", n_total)
    k2.metric("仅途径 A", n_a_only, help="仅靠第一站综合前30%晋级")
    k3.metric("仅途径 B", n_b_only, help="仅靠第二站单项前10晋级")
    k4.metric("两者皆有", n_both)

    st.markdown(f"**{group_label} 组晋级名单**（晋级总决赛 = 第一站综合前30% ∪ 第二站各单项前10）")

    display = pd.DataFrame({
        '选手': grp_quals['name'].values,
        '区县': grp_quals['district'].values,
        '第一站综合排名': grp_quals['enrollment_rank'].apply(
            lambda x: f"第{int(x)}名" if pd.notna(x) else "—"
        ).values,
        '晋级途径': grp_quals['paths'].apply(lambda p: "；".join(p)).values,
    })
    # Sort: by 第一站综合排名 ascending (NaN last)
    display['_sort'] = grp_quals['enrollment_rank'].fillna(1e9).values
    display = display.sort_values('_sort').drop(columns='_sort').reset_index(drop=True)
    display.insert(0, '序号', range(1, len(display) + 1))

    st.dataframe(
        display,
        hide_index=True,
        use_container_width=True,
        column_config={
            '序号': st.column_config.NumberColumn(width="small"),
            '选手': st.column_config.TextColumn(width="small"),
            '区县': st.column_config.TextColumn(width="small"),
            '第一站综合排名': st.column_config.TextColumn(width="small"),
            '晋级途径': st.column_config.TextColumn(width="large"),
        },
    )

with tab2:
    st.markdown(
        f"**{group_label} 组各单项预测**：晋级选手按两站 PB 排序，"
        f"第 {FINALS_CUTOFF_RANK} 名即「前 {FINALS_CUTOFF_RANK} 名至少要游进的时间」。"
    )

    if grp_cutoffs.empty:
        st.info("该组暂无项目预测数据。")
    else:
        for _, crow in grp_cutoffs.iterrows():
            event = crow['event']
            st.subheader(event)

            if crow['insufficient']:
                st.warning(
                    f"晋级且有该项目成绩的选手仅 {crow['n_qualified']} 人，"
                    f"不足 {FINALS_CUTOFF_RANK} 人 — 预计全部进入决赛圈。"
                )
            else:
                st.metric(
                    f"第 {FINALS_CUTOFF_RANK} 名预测线",
                    fmt_time(crow['cutoff_seconds']),
                    help=f"晋级且有成绩的选手共 {crow['n_qualified']} 人",
                )

            ev_preds = grp_preds[grp_preds['event'] == event] \
                .sort_values('pb_seconds').head(FINALS_CUTOFF_RANK)
            ev_display = pd.DataFrame({
                '预测排名': ev_preds['predicted_rank'].values,
                '选手': ev_preds['name'].values,
                '区县': ev_preds['district'].values,
                '预测用时 (PB)': ev_preds['pb_seconds'].apply(fmt_time).values,
                'PB 来源': ev_preds['pb_station'].values,
            })
            st.dataframe(
                ev_display,
                hide_index=True,
                use_container_width=True,
                column_config={
                    '预测排名': st.column_config.NumberColumn(width="small"),
                    '选手': st.column_config.TextColumn(width="small"),
                    '区县': st.column_config.TextColumn(width="small"),
                    '预测用时 (PB)': st.column_config.TextColumn(width="small"),
                    'PB 来源': st.column_config.TextColumn(width="small"),
                },
            )

with st.expander("📖 计算口径"):
    st.markdown(
        f"""
        ### 晋级规则（按组别分别计算）
        - **途径 A**：第一站综合排名前 {PATH_A_PCT:.0%} —— `综合排名 <= round(组人数 × {PATH_A_PCT})`。
          综合排名基于第一站各项目总分，并列者共享名次，边界并列者全部纳入。
        - **途径 B**：第二站各单项前 {PATH_B_TOP_N} 名（按成绩时间升序）。
        - **晋级名单 = 途径 A ∪ 途径 B**（按选手取并集）。

        ### 预测用时
        - **预测用时 = 两站 PB**：取该选手在第一站、第二站该项目所有正常完赛成绩中的最快一次。
        - 跨站打平时记为第二站（更近期）。
        - 每个项目：所有「晋级 + 有该项目成绩」的选手按 PB 升序排，
          第 {FINALS_CUTOFF_RANK} 名即预测的前 {FINALS_CUTOFF_RANK} 名分界线。

        ### 范围与口径
        - **预测项目范围**：仅预测该组在**第二站**出现过的项目（第二站阵容最接近总决赛）。
        - 仅纳入计时类游泳项目，排除「腿」（踢腿）项和体能项 —— 这些项目第二站无数据，无法预测。
        - 事件名归一化：男A/女A 第一站的「200米混合泳」即「200米个人混合泳」，已合并统计。
        - **不足 {FINALS_CUTOFF_RANK} 人**：若某项目晋级且有成绩的选手不足 {FINALS_CUTOFF_RANK} 人，
          则无分界线，预计全部进入决赛圈。
        - 本页是基于历史成绩的**机械外推**，不含状态、伤病、临场发挥等因素，仅供参考。
        """
    )
