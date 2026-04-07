import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.results import search_participants, get_participant_history, get_all_districts

st.set_page_config(page_title="选手查询", layout="wide")
st.title("🔍 选手查询")

# Search controls
col1, col2 = st.columns([2, 1])
with col1:
    name_query = st.text_input("姓名搜索（支持模糊搜索）", placeholder="输入姓名...")
with col2:
    districts = ['全部'] + get_all_districts()
    district = st.selectbox("所属区", districts)

if name_query or district != '全部':
    d = None if district == '全部' else district
    results = search_participants(name_query, d)

    if results.empty:
        st.info("未找到匹配的选手。")
        st.stop()

    st.markdown(f"找到 **{len(results)}** 名选手")

    # Display as clickable list
    for _, p in results.iterrows():
        if st.button(f"{p['name']} — {p['district']}", key=f"p_{p['id']}"):
            st.session_state['selected_participant'] = p['id']
            st.session_state['selected_name'] = p['name']
            st.session_state['selected_district'] = p['district']

# Show participant details
if 'selected_participant' in st.session_state:
    pid = st.session_state['selected_participant']
    pname = st.session_state['selected_name']
    pdistrict = st.session_state['selected_district']

    st.markdown("---")
    st.markdown(f"## {pname}（{pdistrict}）")

    history = get_participant_history(pid)

    if history.empty:
        st.info("暂无比赛记录。")
        st.stop()

    # Group by competition
    for comp_name, comp_group in history.groupby('competition', sort=False):
        first = comp_group.iloc[0]
        group_label = f"{first['gender']}子{first['group_name']}组"
        rank_info = f"排名 {first['rank']}" if first['rank'] else ""
        score_info = f"总分 {first['total_score']}" if first['total_score'] else ""

        st.markdown(f"### {comp_name} — {group_label}")
        st.markdown(f"**{rank_info}  |  {score_info}**")

        if first['rating']:
            st.markdown(f"评级：**{first['rating']}**")

        # Results table
        display_data = []
        for _, r in comp_group.iterrows():
            status_display = r['raw_value'] or ''
            if r['status'] == 'foul':
                status_display = '犯规'
            elif r['status'] == 'withdrew':
                status_display = '弃权'

            display_data.append({
                '项目': r['event_name'],
                '类别': '游泳' if r['category'] == 'swimming' else '体能',
                '成绩': status_display,
                '得分': r['score'],
            })

        import pandas as pd
        st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)

    # Progression chart if multiple competitions
    competitions = history['competition'].unique()
    if len(competitions) > 1:
        st.markdown("### 跨站成绩趋势")
        import plotly.express as px

        swim_events = history[
            (history['category'] == 'swimming') &
            (history['status'] == 'normal')
        ]

        if not swim_events.empty:
            common_events = swim_events.groupby('event_name').filter(
                lambda x: x['competition'].nunique() > 1
            )
            if not common_events.empty:
                fig = px.line(
                    common_events,
                    x='short_name', y='numeric_value',
                    color='event_name',
                    markers=True,
                    labels={'short_name': '比赛', 'numeric_value': '成绩（秒）',
                            'event_name': '项目'},
                    title='游泳项目成绩变化'
                )
                fig.update_yaxes(autorange='reversed')
                st.plotly_chart(fig, use_container_width=True)
else:
    st.info("请输入姓名或选择区县开始搜索。")
