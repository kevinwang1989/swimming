import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.results import get_competitions, get_group_results, get_events_for_group, get_all_districts

st.set_page_config(page_title="成绩总览", layout="wide")

from style import apply_style
apply_style()
st.title("📊 成绩总览")

comps = get_competitions()
if comps.empty:
    st.warning("尚未导入任何比赛数据。")
    st.stop()

# Filters
col1, col2, col3, col4 = st.columns([2, 1.5, 1, 2])
with col1:
    comp_options = {row['id']: row['name'] for _, row in comps.iterrows()}
    comp_id = st.selectbox("选择比赛", options=list(comp_options.keys()),
                           format_func=lambda x: comp_options[x])

with col2:
    genders = st.multiselect("性别", ['男', '女'], default=['男'])

with col3:
    group = st.selectbox("组别", ['A', 'B', 'C', 'D', 'E', 'F'])

with col4:
    districts = ['全部'] + get_all_districts()
    district = st.selectbox("所属区", districts)

if not genders:
    st.info("请至少选择一个性别。")
    st.stop()

# Get results for each selected gender and merge
all_dfs = []
all_events = pd.DataFrame()
for g in genders:
    df = get_group_results(comp_id, g, group)
    if not df.empty:
        df['gender_label'] = f'{g}子'
        all_dfs.append(df)
    evt = get_events_for_group(comp_id, g, group)
    if not evt.empty:
        all_events = pd.concat([all_events, evt]).drop_duplicates(subset='name')

if not all_dfs:
    st.info("该组别暂无数据。")
    st.stop()

df = pd.concat(all_dfs, ignore_index=True)

# Filter by district
if district != '全部':
    df = df[df['district'] == district]

if df.empty:
    st.info("该筛选条件下暂无数据。")
    st.stop()

# Title
gender_str = '/'.join([f'{g}子' for g in genders])
district_str = f" — {district}" if district != '全部' else ""
st.markdown(f"### {gender_str}{group}组{district_str} — 共 {len(df)} 人")

events = all_events.sort_values('sort_order') if not all_events.empty else all_events

# Format display columns
display_cols = ['rank', 'name', 'district', 'total_score']
col_rename = {'rank': '排名', 'name': '姓名', 'district': '所属区', 'total_score': '总分'}

# Show gender column if multiple genders selected
if len(genders) > 1:
    display_cols.insert(1, 'gender_label')
    col_rename['gender_label'] = '性别'

if 'rating' in df.columns and df['rating'].notna().any():
    display_cols.append('rating')
    col_rename['rating'] = '评级'

if 'remark' in df.columns:
    display_cols.append('remark')
    col_rename['remark'] = '备注'

# Add event columns
event_cols = []  # list of (original_col, event_name, sub_label)
for _, evt in events.iterrows():
    ename = evt['name']
    score_col = f'{ename}_成绩'
    point_col = f'{ename}_得分'
    if score_col in df.columns:
        display_cols.append(score_col)
        event_cols.append((score_col, ename, '成绩'))
    if point_col in df.columns:
        display_cols.append(point_col)
        event_cols.append((point_col, ename, '得分'))

# Filter to existing columns only
display_cols = [c for c in display_cols if c in df.columns]
display_df = df[display_cols].copy()

# Format: scores to 1 decimal, None to empty
score_format_cols = ['total_score'] + [c for c in display_df.columns if c.endswith('_得分')]
for c in score_format_cols:
    if c in display_df.columns:
        display_df[c] = display_df[c].apply(
            lambda x: f'{x:.1f}' if pd.notna(x) else ''
        )
display_df = display_df.fillna('')

# Don't rename columns - we'll use original keys for data access

# Build HTML table with proper two-level headers
# Separate base columns and event columns
base_col_labels = [col_rename.get(c, c) for c in display_cols if c not in {ec[0] for ec in event_cols}]
# Group events: list of (event_name, [(col_label, sub_label)])
from collections import OrderedDict
event_groups = OrderedDict()
for orig, ename, sub in event_cols:
    if ename not in event_groups:
        event_groups[ename] = []
    event_groups[ename].append(sub)

def cell_style(val):
    """Return inline style for special values."""
    if val == '犯规':
        return ' style="color: red; font-weight: bold;"'
    elif val == '弃权':
        return ' style="color: #999;"'
    return ''

# Number of base columns to freeze (排名, 姓名, 所属区, 总分)
FREEZE_COLS = 4

# Fixed widths for frozen columns (px) - must match CSS min/max-width
frozen_col_widths = {'排名': 50, '姓名': 80, '所属区': 80, '总分': 55, '性别': 50}
# Calculate left offsets from fixed widths
freeze_lefts = []
cumulative = 0
for i, label in enumerate(base_col_labels):
    if i < FREEZE_COLS:
        freeze_lefts.append(cumulative)
        cumulative += frozen_col_widths.get(label, 60)

# Generate CSS for frozen column positions
frozen_css = ""
for i in range(min(FREEZE_COLS, len(base_col_labels))):
    left = freeze_lefts[i]
    w = frozen_col_widths.get(base_col_labels[i], 60)
    frozen_css += f"""
.results-table td.fz{i}, .results-table th.fz{i} {{
    position: sticky;
    left: {left}px;
    min-width: {w}px;
    max-width: {w}px;
    width: {w}px;
    box-sizing: border-box;
}}"""

# Add shadow on the last frozen column for visual separation
last_fz = min(FREEZE_COLS, len(base_col_labels)) - 1
frozen_css += f"""
.results-table td.fz{last_fz}, .results-table th.fz{last_fz} {{
    box-shadow: 2px 0 4px rgba(0,0,0,0.06);
}}"""

html = f'''<style>
.results-table-wrap {{
    overflow-x: auto;
    max-height: 600px;
    overflow-y: auto;
    border-radius: 8px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08);
}}
.results-table {{
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.85rem;
    white-space: nowrap;
}}
.results-table th, .results-table td {{
    border: 1px solid #e0e0e0;
    padding: 6px 10px;
    text-align: center;
}}
.results-table thead th {{
    background: #f5f5fa;
    position: sticky;
    top: 0;
    z-index: 2;
    font-weight: 600;
}}
.results-table thead tr:first-child th {{
    top: 0;
    z-index: 3;
}}
.results-table thead tr:nth-child(2) th {{
    top: 33px;
    z-index: 2;
}}
/* Frozen column base styles */
.results-table td[class^="fz"] {{
    background: #fff;
    z-index: 1;
}}
.results-table thead th[class^="fz"] {{
    background: #f5f5fa;
    z-index: 5;
}}
.results-table tbody tr:hover td[class^="fz"] {{
    background: #f0f4ff;
}}
.results-table tbody tr:hover {{
    background: #f0f4ff;
}}
.results-table tbody td {{
    font-variant-numeric: tabular-nums;
}}
{frozen_css}
</style>
'''

html += '<div class="results-table-wrap"><table class="results-table"><thead>\n<tr>'

# Header row 1: base columns with rowspan=2, event groups with colspan
for i, label in enumerate(base_col_labels):
    if i < FREEZE_COLS:
        html += f'<th rowspan="2" class="fz{i}">{label}</th>'
    else:
        html += f'<th rowspan="2">{label}</th>'
for ename, subs in event_groups.items():
    html += f'<th colspan="{len(subs)}">{ename}</th>'
html += '</tr>\n<tr>'

# Header row 2: only event sub-labels (成绩, 得分)
for ename, subs in event_groups.items():
    for sub in subs:
        html += f'<th>{sub}</th>'
html += '</tr></thead>\n<tbody>'

# Build ordered column keys matching the header layout (use original df column names)
event_col_set = {ec[0] for ec in event_cols}
base_keys = [c for c in display_cols if c not in event_col_set]
ordered_keys = list(base_keys)
for orig, ename, sub in event_cols:
    ordered_keys.append(orig)

# Render rows
for _, row in display_df.iterrows():
    html += '<tr>'
    for col_idx, key in enumerate(ordered_keys):
        val = str(row.get(key, ''))
        if val == 'nan':
            val = ''
        extra_style = cell_style(val)
        if col_idx < FREEZE_COLS:
            if extra_style:
                inner = extra_style.replace(' style="', '').rstrip('"')
                html += f'<td class="fz{col_idx}" style="{inner}">{val}</td>'
            else:
                html += f'<td class="fz{col_idx}">{val}</td>'
        else:
            html += f'<td{extra_style}>{val}</td>'
    html += '</tr>\n'

html += '</tbody></table></div>'

st.markdown(html, unsafe_allow_html=True)
