import streamlit as st
import pandas as pd
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.results import get_competitions, get_events_for_group
from queries.district import district_summary, district_event_comparison

st.set_page_config(page_title="区县排名", layout="wide")

from style import init_page
init_page(
    title="🏆 区县排名",
    subtitle="各区分项目聚合排名与整体实力评估。",
    kicker="06 · District Ranking",
)

comps = get_competitions()
if comps.empty:
    st.warning("尚未导入任何比赛数据。")
    st.stop()

# Filters
col1, col2, col3 = st.columns(3)
with col1:
    comp_options = {row['id']: row['name'] for _, row in comps.iterrows()}
    comp_id = st.selectbox("选择比赛", options=list(comp_options.keys()),
                           format_func=lambda x: comp_options[x])
with col2:
    gender_opt = st.selectbox("性别", ['全部', '男', '女'])
    gender = None if gender_opt == '全部' else gender_opt

with col3:
    group_opt = st.selectbox("组别", ['全部', 'A', 'B', 'C', 'D', 'E', 'F'])
    group_name = None if group_opt == '全部' else group_opt

# Summary table
summary = district_summary(comp_id, gender, group_name)

if summary.empty:
    st.info("暂无数据。")
    st.stop()

st.markdown("### 各区综合统计")
display_summary = summary.rename(columns={
    'district': '区县',
    'participant_count': '参赛人数',
    'avg_score': '平均分',
    'total_score': '总分',
    'promoted_count': '晋级人数',
    'excellent_count': '优秀人数',
})
st.dataframe(display_summary, use_container_width=True, hide_index=True)

# Charts
col1, col2 = st.columns(2)

with col1:
    fig = px.bar(
        summary.sort_values('avg_score', ascending=False),
        x='district', y='avg_score',
        title='各区平均分',
        labels={'district': '区县', 'avg_score': '平均分'},
        color='avg_score',
        color_continuous_scale='blues'
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig2 = px.bar(
        summary.sort_values('participant_count', ascending=False),
        x='district', y='participant_count',
        title='各区参赛人数',
        labels={'district': '区县', 'participant_count': '人数'},
        color='participant_count',
        color_continuous_scale='greens'
    )
    fig2.update_layout(showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

# Promotion/excellence rate
if summary['promoted_count'].sum() > 0:
    summary_rate = summary.copy()
    summary_rate['promoted_rate'] = (summary_rate['promoted_count'] / summary_rate['participant_count'] * 100).round(1)
    summary_rate['excellent_rate'] = (summary_rate['excellent_count'] / summary_rate['participant_count'] * 100).round(1)

    fig3 = px.bar(
        summary_rate.sort_values('promoted_rate', ascending=False),
        x='district', y=['promoted_rate', 'excellent_rate'],
        title='晋级率与优秀率（%）',
        labels={'district': '区县', 'value': '百分比', 'variable': '指标'},
        barmode='group'
    )
    st.plotly_chart(fig3, use_container_width=True)

# Event-level district comparison
st.markdown("---")
st.markdown("### 各区单项对比")

# Get available events
if group_name:
    events = get_events_for_group(comp_id, gender or '男', group_name)
else:
    events = get_events_for_group(comp_id, gender or '男', 'B')  # fallback

if not events.empty:
    event_name = st.selectbox("选择项目", events['name'].tolist())

    event_comp = district_event_comparison(comp_id, event_name, gender)
    if not event_comp.empty:
        evt_info = events[events['name'] == event_name].iloc[0]

        display_event = event_comp.rename(columns={
            'district': '区县',
            'athlete_count': '参赛人数',
            'avg_result': '平均成绩',
            'best_result': '最佳成绩',
            'avg_score': '平均得分',
        })
        st.dataframe(display_event, use_container_width=True, hide_index=True)

        # Chart
        sort_order = 'avg_result'
        fig4 = px.bar(
            event_comp.sort_values(sort_order),
            x='district', y='avg_result',
            title=f'{event_name} — 各区平均成绩',
            labels={'district': '区县', 'avg_result': '平均成绩'},
            color='avg_result',
            color_continuous_scale='reds_r' if evt_info['result_type'] == 'time' else 'blues'
        )
        fig4.update_layout(showlegend=False)
        st.plotly_chart(fig4, use_container_width=True)
