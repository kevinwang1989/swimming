import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.results import get_participant_history, get_all_districts
from queries.results import get_group_total_count
from queries.season_report import build_report, render_report_markdown
from queries.splits_dna import build_dna_profile
from db.connection import get_db

st.set_page_config(page_title="选手查询", layout="wide")

from style import init_page
init_page(
    title="🔍 选手查询",
    subtitle="搜索任一选手，查看完整成绩档案、跨站趋势图与赛季战报。",
    kicker="04 · Athlete Profile",
)


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

# ---- 分段 DNA 画像 ----
st.markdown("---")
st.markdown("### 🧬 分段 DNA 画像")

_dna = build_dna_profile(pid)

if _dna is None:
    st.info("该选手暂无可用于分段分析的成绩（需要 100m 及以上的游泳项目且录入了分段数据）。")
else:
    _agg = _dna['aggregate']
    _emoji = _agg['archetype_emoji']
    _arche = _agg['archetype']
    _arche_en = _agg['archetype_en']

    # Archetype badge + core metrics row
    _bc = st.columns([2, 1, 1, 1])
    with _bc[0]:
        st.markdown(
            f"""
            <div class="wa-card" style="border-left:4px solid var(--wa-blue);">
                <div class="wa-card-kicker">ARCHETYPE · {_arche_en}</div>
                <div style="font-family:'Oswald',sans-serif;font-size:2rem;
                            font-weight:700;color:var(--wa-navy);
                            letter-spacing:0.03em;line-height:1.1;margin-top:0.2rem;">
                    {_emoji} {_arche}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    _bc[1].metric("分段比赛", f"{_dna['n_races']} 场")
    if _agg['avg_fb_ratio'] is not None:
        _bc[2].metric(
            "前后程比",
            f"{_agg['avg_fb_ratio']:.3f}",
            help="= 前半段 lap 均值 / 后半段 lap 均值。<1 前快型（正分段），>1 后劲型（负分段）。仅对 200m+ 非混合泳项目计算。",
        )
    else:
        _bc[2].metric("前后程比", "—", help="需要 200m+ 非混合泳项目才能计算")
    if _agg['avg_cv'] is not None:
        _bc[3].metric(
            "节奏波动 CV",
            f"{_agg['avg_cv']:.3f}",
            help="中间段（去掉出发段和最后一段）lap 的变异系数。越低越稳。",
        )
    else:
        _bc[3].metric("节奏波动 CV", "—", help="需要 200m+ 项目才能计算")

    st.info(_dna['narrative'])

    # Per-race pace curves
    import plotly.graph_objects as go
    _fig = go.Figure()
    _wa_blue = '#0282c6'
    for _race in _dna['per_race']:
        _label = f"{_race['event_name']} · {_race['comp']}"
        _fig.add_trace(go.Scatter(
            x=_race['seg_labels'],
            y=_race['laps'],
            mode='lines+markers',
            name=_label,
        ))
        if _race['peer_avg_laps']:
            _fig.add_trace(go.Scatter(
                x=_race['seg_labels'],
                y=_race['peer_avg_laps'],
                mode='lines',
                name=f"{_label} · 同组均值",
                line=dict(dash='dash', width=1),
                opacity=0.6,
            ))
    _fig.update_layout(
        title="分段节奏曲线（纵轴：单段时间，越低越快）",
        xaxis_title="分段",
        yaxis_title="单段时间（秒）",
        height=420,
        legend=dict(orientation='h', y=-0.25),
        margin=dict(l=40, r=20, t=50, b=40),
    )
    st.plotly_chart(_fig, use_container_width=True)

    with st.expander("📖 画像口径说明"):
        st.markdown(
            """
            - **前后程比 (F/B)**：前半段 lap 均值 / 后半段 lap 均值。
              `<1.0` → 前半段更快（正分段，典型前快型）；
              `>1.0` → 后半段更快（负分段，后劲型）。
              100m 项目只有 2 段且首段包含出发跳水增益，**不参与** F/B 计算；
              个人混合泳由于泳姿差异也**不参与**。
            - **节奏波动 CV**：中间段（去掉第一段和最后一段）lap 的标准差 / 均值，
              衡量匀速能力。仅对 200m+ 项目有意义。
            - **后程衰减 (fade_index)**：最后一段相对中间段最快 lap 的衰减比例。
            - **Archetype 分类**：基于上述指标的启发式规则，分为 🔥前快 / 🚀后劲 /
              ⚖️均衡 / 💥爆发 四类，用于快速识别节奏风格，不代表绝对能力优劣。
            - **同组均值参考线**：同项目 + 同性别 + 同组别的所有 peer 成绩的 lap 均值
              （至少 3 位 peer 才显示），用于对照。
            - **数据来源**：仅包含正常完赛、录入了分段数据的游泳计时项目。
              2025 赛季约 12.8% 的成绩有分段，A/B 组主力覆盖率较高。
            """
        )

# ---- 赛季战报 ----
st.markdown("---")
with st.expander("✨ 生成赛季战报（自动总结 / 可截图分享）", expanded=False):
    report = build_report(pid)
    if report is None:
        st.info("该选手暂无可生成战报的数据。")
    else:
        st.markdown(render_report_markdown(report, pname, pdistrict))
        st.caption(
            "未来开通 LLM API 后，这里可切换 AI 润色版叙述（已预留接口）。"
        )
