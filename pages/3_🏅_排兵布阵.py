import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.results import (
    get_competitions,
    get_events_for_competition,
    get_all_districts,
)
from queries.lineup import (
    build_swimmer_table,
    recommend_medley_relay,
    recommend_free_relay,
    get_actual_relay,
    fmt_time,
)

st.set_page_config(page_title="排兵布阵", layout="wide")

from style import apply_style, page_header
apply_style()

page_header(
    title="🏅 排兵布阵",
    subtitle="根据单项成绩，为代表队推荐最强接力阵容，并与实际派出阵容对比。",
    kicker="03 · Relay Lineup",
)

# ---- Filters ----
comps = get_competitions()
if comps.empty:
    st.warning("尚未导入任何比赛数据。")
    st.stop()

col1, col2, col3, col4 = st.columns([2, 1, 1, 1.3])
with col1:
    comp_options = {row['id']: row['name'] for _, row in comps.iterrows()}
    comp_id = st.selectbox("选择比赛", options=list(comp_options.keys()),
                           format_func=lambda x: comp_options[x])
with col2:
    gender = st.selectbox("性别", ['男', '女'])
with col3:
    group = st.selectbox("组别", ['A', 'B', 'C', 'D', 'E', 'F'])
with col4:
    source = st.radio(
        "数据来源",
        options=['this_comp', 'historical_pb'],
        format_func=lambda x: '本次比赛' if x == 'this_comp' else '历史 PB（跨站最佳）',
        horizontal=False,
    )

# Check if this competition has any relay events at all
relay_events = get_events_for_competition(comp_id, gender, group, include_relay=True)
relay_events = relay_events[relay_events['kind'] == 'relay']
if relay_events.empty:
    st.info(f"该比赛的 {gender} {group} 组无接力项目。（v1.0 老站数据不含接力）")
    st.stop()

# District selector — only districts with any swimmer in this (comp, gender, group)
all_districts = get_all_districts()
district = st.selectbox("代表队", all_districts)

st.markdown(
    f"### {gender}子 {group} 组 — **{district}**  "
    f"<span style='font-size: 0.85em; color: #888;'>数据源：{'本次比赛' if source == 'this_comp' else '历史 PB'}</span>",
    unsafe_allow_html=True,
)

# Build swimmer table once for the district
swimmer_table = build_swimmer_table(comp_id, gender, group, district, source=source)

if not swimmer_table:
    st.warning(f"{district} 在该组无选手成绩数据。")
    st.stop()

st.caption(
    f"📊 候选选手：{len(swimmer_table)} 人  |  "
    "💡 估计时间来源优先级：**单项** > 按 100m 推算 > 400/200 个混分段"
)

# ---- Render each relay event ----

def render_lineup_table(lineup, key_prefix, is_medley=True):
    rows = []
    cum = 0.0
    for leg in lineup:
        cum += leg['est_seconds']
        rows.append({
            '棒次': leg['leg_order'],
            '泳姿': leg['stroke'],
            '选手': leg['swimmer_name'],
            '估计时间': f"{leg['est_seconds']:.2f}",
            '数据来源': leg['source'],
            '累积': fmt_time(cum),
        })
    return pd.DataFrame(rows)


def render_actual_table(lineup):
    rows = []
    cum = 0.0
    for leg in lineup:
        t = leg['actual_seconds']
        if t is not None:
            cum += t
            t_str = f"{t:.2f}"
        else:
            t_str = '—'
        rows.append({
            '棒次': leg['leg_order'],
            '泳姿': leg['stroke'],
            '选手': leg['swimmer_name'],
            '实际成绩': t_str,
            '累积': fmt_time(cum) if t is not None else '—',
        })
    return pd.DataFrame(rows)


def render_section(event_name, is_medley, leg_distance):
    st.markdown("---")
    st.markdown(f"### {'🏊‍♀️' if not is_medley else '🏊'} {event_name}")

    if is_medley:
        rec = recommend_medley_relay(swimmer_table, leg_distance)
    else:
        rec = recommend_free_relay(swimmer_table, leg_distance)

    # Warnings (e.g., not enough candidates)
    for w in rec['warnings']:
        st.warning(w)

    if not rec['lineup']:
        return

    # Recommended lineup
    st.markdown(
        f"#### 🎯 推荐阵容 — 预计总成绩 **{fmt_time(rec['total_seconds'])}**"
    )
    rec_df = render_lineup_table(rec['lineup'], event_name, is_medley)
    st.dataframe(rec_df, hide_index=True, use_container_width=True)

    # Actual lineup
    actual = get_actual_relay(comp_id, gender, group, event_name, district)
    if actual is None:
        st.caption(f"{district} 未派出该项目的接力队伍。")
    else:
        rank_str = f"第 {actual['rank']} 名" if actual['rank'] else actual['status']
        st.markdown(
            f"#### 📋 实际出战 — 成绩 **{actual['final_time']}**（{rank_str}）"
        )
        actual_df = render_actual_table(actual['lineup'])
        st.dataframe(actual_df, hide_index=True, use_container_width=True)

        # Diff analysis
        if actual['total_seconds'] and rec['total_seconds']:
            diff = actual['total_seconds'] - rec['total_seconds']
            if diff > 0.5:
                st.success(
                    f"💡 理论可优化 **{diff:+.2f} 秒**  "
                    f"（推荐基于单项成绩估算，未计入接力交接棒反应时间差异；"
                    f"通常实际会比估算快 1-3 秒/棒）"
                )
            elif diff < -0.5:
                st.info(
                    f"✨ 实际成绩比推荐阵容估算快 {abs(diff):.2f} 秒 "
                    f"—— 派出阵容已接近最优，或选手临场发挥极佳。"
                )
            else:
                st.info(f"⚖️ 推荐与实际阵容估算接近（差距 {diff:+.2f} 秒）。")


# Render all relay events in this group
for _, ev_row in relay_events.iterrows():
    ev_name = ev_row['name']
    is_medley = '混合泳' in ev_name
    # Detect leg distance from event name (4X100 or 4X50)
    if '100' in ev_name:
        leg_dist = 100
    elif '50' in ev_name:
        leg_dist = 50
    else:
        leg_dist = 100  # default
    render_section(ev_name, is_medley, leg_dist)

# ---- Methodology disclaimer ----
st.markdown("---")
with st.expander("ℹ️ 关于推荐算法和数据来源"):
    st.markdown("""
**推荐算法**
- 混合泳接力：在所有有成绩的候选选手中，**枚举所有 4 人组合 × 4 种泳姿分配**，选择总时间最小的方案
- 自由泳接力：取自由泳时间最快的前 4 名

**数据来源优先级**（每个棒次的估计时间）
1. **单项** — 该距离该泳姿的独立比赛成绩（最准）
2. **按 X 米推算** — 用另一距离的单项成绩 × 0.485（50m≈100m 的 48.5%）换算
3. **400/200 个混分段** — 个人混合泳中对应泳姿的分段时间（仅作保底，受疲劳影响会偏慢）

**估算与实际的差距**
- 接力的 2-4 棒有 **飞跃出发**，通常比单项快 0.5-1.0 秒/棒，所以推荐阵容的预计总时间通常会**略慢于**实际比赛成绩
- 因此"理论可优化 X 秒"指的是派出阵容本身的选择空间（选对人），不包括接力技术红利

**历史 PB 模式** 跨所有已导入的比赛，取每人每项的最佳成绩；只包含参加本次比赛本组别的选手。

**已知限制**
- 未计入反应时间、出发反应、选手状态（疲劳/伤病）、教练战术
- 若候选选手不足 4 人或缺少某种泳姿数据，无法推荐
    """)
