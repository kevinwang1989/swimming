import streamlit as st
import pandas as pd
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.connection import get_db
from queries.results import get_competitions, get_all_districts
from queries.comparison import compare_participants, participant_progression

st.set_page_config(page_title="对比分析", layout="wide")
st.title("📈 对比分析")


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

tab1, tab2 = st.tabs(["选手对比", "跨站追踪"])

# ==================== Tab 1: Head-to-head comparison ====================
with tab1:
    st.markdown("### 选择要对比的选手（2-5人）")

    # District filter to narrow down
    district_filter = st.selectbox("先选区县缩小范围（可选）",
                                   ['全部'] + get_all_districts(),
                                   key="cmp_district")

    if district_filter != '全部':
        filtered = all_participants[all_participants['district'] == district_filter]
    else:
        filtered = all_participants

    options_list = filtered['label'].tolist()

    selected_labels = st.multiselect(
        "选择选手（可输入姓名搜索，选 2-5 人）",
        options=options_list,
        max_selections=5,
        placeholder="输入姓名搜索并选择..."
    )

    if len(selected_labels) >= 2:
        # Map labels back to IDs
        selected_ids = []
        for label in selected_labels:
            match = all_participants[all_participants['label'] == label]
            if not match.empty:
                selected_ids.append(int(match.iloc[0]['id']))

        # Competition filter
        comps = get_competitions()
        comp_options = {0: '全部比赛'}
        comp_options.update({row['id']: row['name'] for _, row in comps.iterrows()})
        comp_id = st.selectbox(
            "选择比赛",
            options=list(comp_options.keys()),
            format_func=lambda x: comp_options[x],
            key="compare_comp"
        )

        comp_filter = comp_id if comp_id != 0 else None
        df = compare_participants(selected_ids, comp_filter)

        if df.empty:
            st.info("所选选手没有共同的比赛数据。")
        else:
            st.markdown("### 对比结果")

            # Build comparison table
            all_events = df.sort_values('sort_order')['event_name'].unique()
            comp_data = []
            for event in all_events:
                event_df = df[df['event_name'] == event]
                row_data = {'项目': event}
                for pid in selected_ids:
                    pdata = event_df[event_df['participant_id'] == pid]
                    if not pdata.empty:
                        p = pdata.iloc[0]
                        label = f"{p['name']}（{p['district']}）"
                        if p['status'] == 'foul':
                            row_data[label] = '犯规'
                        elif p['status'] == 'withdrew':
                            row_data[label] = '弃权'
                        else:
                            row_data[label] = p['raw_value']
                    else:
                        # Find name for this pid
                        m = all_participants[all_participants['id'] == pid]
                        if not m.empty:
                            label = m.iloc[0]['label']
                            row_data[label] = ''
                comp_data.append(row_data)

            comp_df = pd.DataFrame(comp_data)
            st.dataframe(comp_df, use_container_width=True, hide_index=True)

            # Chart: swimming events comparison
            swim_df = df[
                (df['result_type'] == 'time') &
                (df['status'] == 'normal')
            ].copy()
            if not swim_df.empty:
                swim_df['display_name'] = swim_df['name'] + '（' + swim_df['district'] + '）'
                fig = px.bar(
                    swim_df,
                    x='event_name', y='numeric_value',
                    color='display_name',
                    barmode='group',
                    labels={'event_name': '项目', 'numeric_value': '成绩（秒）',
                            'display_name': '选手'},
                    title='游泳成绩对比（越低越好）'
                )
                st.plotly_chart(fig, use_container_width=True)

            # Chart: fitness comparison
            fitness_df = df[
                (df['result_type'] != 'time') &
                (df['status'] == 'normal')
            ].copy()
            if not fitness_df.empty:
                fitness_df['display_name'] = fitness_df['name'] + '（' + fitness_df['district'] + '）'
                fig2 = px.bar(
                    fitness_df,
                    x='event_name', y='numeric_value',
                    color='display_name',
                    barmode='group',
                    labels={'event_name': '项目', 'numeric_value': '成绩',
                            'display_name': '选手'},
                    title='体能成绩对比（越高越好）'
                )
                st.plotly_chart(fig2, use_container_width=True)

    elif len(selected_labels) == 1:
        st.info("请至少选择 2 名选手进行对比。")
    else:
        st.info("在上方搜索框中输入姓名，选择 2-5 名选手即可开始对比。")

# ==================== Tab 2: Cross-competition progression ====================
with tab2:
    st.markdown("### 跨站成绩追踪")
    st.markdown("选择一名选手，查看其在不同站比赛中的成绩变化。")

    district_filter2 = st.selectbox("先选区县缩小范围（可选）",
                                     ['全部'] + get_all_districts(),
                                     key="prog_district")

    if district_filter2 != '全部':
        filtered2 = all_participants[all_participants['district'] == district_filter2]
    else:
        filtered2 = all_participants

    selected_label2 = st.selectbox(
        "选择选手（可输入姓名搜索）",
        options=[''] + filtered2['label'].tolist(),
        index=0,
        placeholder="输入姓名搜索...",
        key="progression_select"
    )

    if not selected_label2:
        st.info("选择一名选手查看跨站成绩变化。")
    else:
        match2 = all_participants[all_participants['label'] == selected_label2]
        if match2.empty:
            st.stop()

        selected_id = int(match2.iloc[0]['id'])
        prog = participant_progression(selected_id)

        if prog.empty:
            st.info("该选手暂无比赛记录。")
        else:
            competitions = prog['short_name'].unique()

            if len(competitions) < 2:
                st.info("该选手目前仅有一站比赛记录，导入更多比赛后可查看趋势。")

            # Overall rank/score progression
            rank_data = prog.drop_duplicates(subset=['competition_id'])[
                ['short_name', 'rank', 'total_score', 'group_name']
            ]
            st.markdown("#### 排名与总分")
            st.dataframe(rank_data.rename(columns={
                'short_name': '比赛', 'rank': '排名',
                'total_score': '总分', 'group_name': '组别'
            }), use_container_width=True, hide_index=True)

            # Per-event progression
            swim = prog[
                (prog['result_type'] == 'time') &
                (prog['status'] == 'normal')
            ]

            if not swim.empty:
                st.markdown("#### 游泳成绩变化")

                events_to_show = swim['event_name'].unique()
                for event in events_to_show:
                    edata = swim[swim['event_name'] == event].sort_values('competition_id')
                    if len(edata) >= 1:
                        cols = st.columns([1, 2])
                        with cols[0]:
                            display = edata[['short_name', 'raw_value', 'score']].rename(columns={
                                'short_name': '比赛', 'raw_value': '成绩', 'score': '得分'
                            })
                            st.markdown(f"**{event}**")
                            st.dataframe(display, hide_index=True)

                            if len(edata) >= 2:
                                first_val = edata.iloc[0]['numeric_value']
                                last_val = edata.iloc[-1]['numeric_value']
                                delta = last_val - first_val
                                if delta < 0:
                                    st.success(f"进步 {abs(delta):.2f} 秒")
                                elif delta > 0:
                                    st.error(f"退步 {delta:.2f} 秒")
                                else:
                                    st.info("成绩持平")

            # Fitness progression
            fitness = prog[
                (prog['result_type'] != 'time') &
                (prog['status'] == 'normal')
            ]
            if not fitness.empty:
                st.markdown("#### 体能成绩变化")
                for event in fitness['event_name'].unique():
                    edata = fitness[fitness['event_name'] == event].sort_values('competition_id')
                    display = edata[['short_name', 'raw_value', 'score']].rename(columns={
                        'short_name': '比赛', 'raw_value': '成绩', 'score': '得分'
                    })
                    st.markdown(f"**{event}**")
                    st.dataframe(display, hide_index=True)
