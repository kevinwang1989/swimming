import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.results import get_participant_history, get_all_districts
from queries.results import get_group_total_count
from db.connection import get_db

st.set_page_config(page_title="选手查询", layout="wide")

from style import apply_style
apply_style()
st.title("🔍 选手查询")


@st.cache_data
def load_all_participants():
    conn = get_db()
    df = pd.read_sql_query(
        "SELECT id, name, district FROM participant ORDER BY name", conn
    )
    conn.close()
    df['label'] = df['name'] + '（' + df['district'] + '）'
    return df


all_participants = load_all_participants()

# District filter
col1, col2 = st.columns([1, 3])
with col1:
    districts = ['全部'] + get_all_districts()
    district = st.selectbox("所属区", districts)

# Filter participant list by district
if district != '全部':
    filtered = all_participants[all_participants['district'] == district]
else:
    filtered = all_participants

# Searchable selectbox
with col2:
    options = filtered['label'].tolist()
    selected_label = st.selectbox(
        "选择选手（可输入姓名搜索）",
        options=[''] + options,
        index=0,
        placeholder="输入姓名搜索..."
    )

if not selected_label:
    st.info("请选择一名选手查看详细成绩。")
    st.stop()

# Find selected participant
match = all_participants[all_participants['label'] == selected_label]
if match.empty:
    st.stop()

pid = int(match.iloc[0]['id'])
pname = match.iloc[0]['name']
pdistrict = match.iloc[0]['district']

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

    # Calculate percentile
    percentile_str = ""
    if first['rank']:
        total = get_group_total_count(comp_name, first['gender'], first['group_name'])
        if total > 0:
            percentile = (1 - (first['rank'] - 1) / total) * 100
            percentile_str = f"  |  超越 {percentile:.0f}% 的选手"

    st.markdown(f"**{rank_info}  |  {score_info}{percentile_str}**")

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

        score_val = f"{r['score']:.1f}" if pd.notna(r['score']) else ''
        display_data.append({
            '项目': r['event_name'],
            '类别': '游泳' if r['category'] == 'swimming' else '体能',
            '成绩': status_display,
            '得分': score_val,
        })

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
