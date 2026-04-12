import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.results import (
    get_competitions,
    get_events_for_competition,
    get_event_results,
    get_relay_results,
)
from queries.insights import (
    analyze_district,
    compare_districts,
    compare_athletes,
)

st.set_page_config(page_title="项目详情", layout="wide")

from style import init_page
init_page(
    title="🏊 项目详情",
    subtitle="按项目浏览成绩、分段数据与自动生成的深度分析洞察（含接力）。",
    kicker="02 · Event Details",
)

# ---- Filters ----
comps = get_competitions()
if comps.empty:
    st.warning("尚未导入任何比赛数据。")
    st.stop()

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    comp_options = {row['id']: row['name'] for _, row in comps.iterrows()}
    comp_id = st.selectbox("选择比赛", options=list(comp_options.keys()),
                           format_func=lambda x: comp_options[x])
with col2:
    gender = st.selectbox("性别", ['男', '女'])
with col3:
    group = st.selectbox("组别", ['A', 'B', 'C', 'D', 'E', 'F'])

from queries.results import get_all_districts
district_options = ['全部'] + get_all_districts()
district = st.selectbox("代表队", district_options)

events_df = get_events_for_competition(comp_id, gender, group)
if events_df.empty:
    st.info("该筛选条件下暂无项目。")
    st.stop()

# Build event option list with kind tag
def label_for(row):
    tag = '🏊‍♂️' if row['kind'] == 'individual' else '👥'
    return f"{tag} {row['name']}"

event_labels = [label_for(r) for _, r in events_df.iterrows()]
sel_idx = st.selectbox("选择项目", options=range(len(event_labels)),
                       format_func=lambda i: event_labels[i])
sel = events_df.iloc[sel_idx]
event_name = sel['name']
event_kind = sel['kind']

st.markdown(f"### {gender}子 {group} 组 — {event_name}")

# ====================================================================
# Individual events
# ====================================================================
if event_kind == 'individual':
    df = get_event_results(comp_id, gender, group, event_name)
    if df.empty:
        st.info("暂无数据。")
        st.stop()

    if district != '全部':
        df = df[df['district'] == district].reset_index(drop=True)
        if df.empty:
            st.info(f"{district} 在该项目暂无成绩。")
            st.stop()

    # Determine if any row has segment data
    has_splits = any(len(s) > 0 for s in df['splits'])
    is_im = '个人混合泳' in event_name

    # Build display rows
    def fmt_status(row):
        if row['status'] == 'foul':
            return '犯规'
        if row['status'] == 'withdrew':
            return '弃权'
        return row['raw_value'] or ''

    base = pd.DataFrame({
        '名次': df['rank'].apply(lambda x: int(x) if pd.notna(x) else ''),
        '姓名': df['name'],
        '代表队': df['district'],
        'R.T.': df['reaction_time'].apply(lambda x: f'{x:.2f}' if pd.notna(x) else ''),
        '成绩': df.apply(fmt_status, axis=1),
        '总得分': df['score'].apply(lambda x: f'{x:.1f}' if pd.notna(x) else ''),
        '运动等级': df['athlete_level'].fillna(''),
    })

    # If there are splits, append segment columns
    seg_cols = []
    if has_splits:
        n_segs = max((len(s) for s in df['splits']), default=0)
        for i in range(n_segs):
            dist = (i + 1) * 50
            if is_im:
                # Find stroke for this segment from any row that has it
                stroke = None
                for s in df['splits']:
                    if i < len(s) and s[i].get('stroke'):
                        stroke = s[i]['stroke']
                        break
                col_label = f'{stroke or ""}{dist}m' if stroke else f'{dist}m'
            else:
                col_label = f'{dist}m'
            seg_cols.append(col_label)

            def _fmt_seg(s, i=i):
                if i >= len(s):
                    return ''
                seg = s[i]
                lap = seg.get('lap')
                cum = seg.get('cum')
                if lap is None and cum is None:
                    return ''
                if lap is None:
                    return f"({cum:.2f})" if cum is not None else ''
                if cum is None:
                    return f"{lap:.2f}"
                return f"{lap:.2f} ({cum:.2f})"

            base[col_label] = df['splits'].apply(_fmt_seg)

    st.dataframe(base, use_container_width=True, hide_index=True)

    # ---- Segment comparison table ----
    if has_splits:
        st.markdown("#### 分段对比（本段时间 / 括号内累积，秒）")

        normal_df = df[df['status'] == 'normal'].copy()
        normal_df['label'] = normal_df['name'] + '（' + normal_df['district'] + '）'
        default_pick = normal_df['label'].head(3).tolist()
        picked = st.multiselect("选择要对比的选手", options=normal_df['label'].tolist(),
                                default=default_pick, max_selections=8)

        if picked:
            cmp_rows = []
            for label in picked:
                row = normal_df[normal_df['label'] == label].iloc[0]
                rec = {'选手': label}
                for i, seg in enumerate(row['splits']):
                    if is_im and seg.get('stroke'):
                        col_label = f"{seg['stroke']}{seg['dist']}m"
                    else:
                        col_label = f"{seg['dist']}m"
                    lap = seg.get('lap')
                    cum = seg.get('cum')
                    if lap is None and cum is None:
                        rec[col_label] = ''
                    elif lap is None:
                        rec[col_label] = f"({cum:.2f})"
                    elif cum is None:
                        rec[col_label] = f"{lap:.2f}"
                    else:
                        rec[col_label] = f"{lap:.2f} ({cum:.2f})"
                rec['总成绩'] = row['raw_value'] or ''
                cmp_rows.append(rec)
            cmp_df = pd.DataFrame(cmp_rows)
            st.dataframe(cmp_df, use_container_width=True, hide_index=True)

        # ---- 🔬 深度分析 ----
        st.markdown("---")
        st.markdown("### 🔬 深度分析")
        st.caption("自动生成的中文洞察，帮助快速定位优势/差距来源。")

        # Use the *unfiltered* event data for analysis so 区/选手 维度可以独立选择，
        # 不受顶部「代表队」筛选的影响。
        full_df = get_event_results(comp_id, gender, group, event_name)
        full_normal = full_df[full_df['status'] == 'normal']
        districts_in_event = sorted(full_normal['district'].dropna().unique().tolist())

        tab_d, tab_dd, tab_a = st.tabs(["单区分析", "双区对比", "选手对比"])

        def _render_result(res):
            for w in res.get('warnings') or []:
                st.warning(w)
            st.markdown(res['summary'])
            for b in res.get('bullets') or []:
                st.markdown(f"- {b}")
            seg = res.get('segment_stats')
            if seg is not None and not seg.empty:
                with st.expander("查看分段数据明细"):
                    st.dataframe(seg, hide_index=True, use_container_width=True)

        with tab_d:
            if not districts_in_event:
                st.info("该项目暂无可分析的区。")
            else:
                default_idx = districts_in_event.index(district) if (
                    district in districts_in_event) else 0
                d_pick = st.selectbox(
                    "选择代表队", options=districts_in_event,
                    index=default_idx, key='insight_single_district',
                )
                _render_result(analyze_district(full_df, event_name, d_pick))

        with tab_dd:
            if len(districts_in_event) < 2:
                st.info("该项目可对比的区不足 2 个。")
            else:
                cca, ccb = st.columns(2)
                with cca:
                    a_pick = st.selectbox(
                        "区 A", options=districts_in_event,
                        index=0, key='insight_dd_a',
                    )
                with ccb:
                    b_pick = st.selectbox(
                        "区 B", options=districts_in_event,
                        index=1, key='insight_dd_b',
                    )
                if a_pick == b_pick:
                    st.info("请选择两个不同的代表队。")
                else:
                    _render_result(
                        compare_districts(full_df, event_name, a_pick, b_pick)
                    )

        with tab_a:
            if not picked or len(picked) < 2:
                st.info("请先在上方「分段对比」选择至少 2 名选手。")
            else:
                _render_result(compare_athletes(full_df, event_name, picked))
    else:
        st.caption("此项目没有分段数据（v1.0 数据或老格式）。")

# ====================================================================
# Relay events
# ====================================================================
else:
    teams_df, legs_df = get_relay_results(comp_id, gender, group, event_name)
    if teams_df.empty:
        st.info("暂无接力数据。")
        st.stop()

    if district != '全部':
        teams_df = teams_df[teams_df['district'] == district].reset_index(drop=True)
        if teams_df.empty:
            st.info(f"{district} 在该项目暂无接力队伍。")
            st.stop()
        legs_df = legs_df[legs_df['team_id'].isin(teams_df['team_id'])]

    # Top-level team table
    teams_view = pd.DataFrame({
        '名次': teams_df['rank'].apply(lambda x: int(x) if pd.notna(x) else ''),
        '组次': teams_df['heat'].apply(lambda x: int(x) if pd.notna(x) else ''),
        '泳道': teams_df['lane'].apply(lambda x: int(x) if pd.notna(x) else ''),
        '代表队': teams_df['district'],
        '成绩': teams_df['final_time'].fillna(''),
        '总得分': teams_df['total_score'].apply(lambda x: f'{x:.1f}' if pd.notna(x) else ''),
        '运动等级': teams_df['athlete_level'].fillna(''),
    })
    st.dataframe(teams_view, use_container_width=True, hide_index=True)

    # Per-team expanders showing legs
    st.markdown("#### 各队接力分段")
    for _, team in teams_df.iterrows():
        team_legs = legs_df[legs_df['team_id'] == team['team_id']].sort_values('leg_order')
        rank_str = f"第{int(team['rank'])}名 " if pd.notna(team['rank']) else ""
        with st.expander(f"{rank_str}{team['district']} — {team['final_time']}"):
            leg_view = pd.DataFrame({
                '棒次': team_legs['leg_order'],
                '选手': team_legs['swimmer_name'],
                'R.T.': team_legs['reaction_time'].apply(
                    lambda x: f'{x:.2f}' if pd.notna(x) else ''),
                '本棒成绩': team_legs['leg_seconds'].apply(
                    lambda x: f'{x:.2f}' if pd.notna(x) else ''),
                '累积成绩': team_legs['cumulative_time'].fillna(''),
            })
            st.dataframe(leg_view, hide_index=True, use_container_width=True)

    # Compare teams: per-leg cumulative chart
    st.markdown("#### 队伍累积时间对比")
    teams_df_norm = teams_df[teams_df['status'] == 'normal'].copy()
    pick_opts = teams_df_norm['district'].tolist()
    default_pick = pick_opts[:5]
    picked = st.multiselect("选择要对比的队伍", options=pick_opts,
                            default=default_pick, max_selections=8,
                            key='relay_pick')
    if picked:
        fig = go.Figure()
        for d in picked:
            tid = teams_df_norm[teams_df_norm['district'] == d].iloc[0]['team_id']
            ll = legs_df[legs_df['team_id'] == tid].sort_values('leg_order')
            xs = ll['leg_order'].tolist()
            ys = ll['cumulative_seconds'].tolist()
            fig.add_trace(go.Scatter(x=xs, y=ys, mode='lines+markers', name=d))
        fig.update_layout(
            xaxis_title='棒次', yaxis_title='累积时间（秒）',
            xaxis=dict(dtick=1), hovermode='x unified', height=420,
        )
        st.plotly_chart(fig, use_container_width=True)
