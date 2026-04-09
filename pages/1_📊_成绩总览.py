import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.results import get_competitions, get_group_results, get_events_for_group, get_all_districts

st.set_page_config(page_title="成绩总览", layout="wide")

from style import apply_style, page_header
apply_style()
page_header(
    title="📊 成绩总览",
    subtitle="按比赛、组别浏览完整成绩表，支持区县与百分位筛选。",
    kicker="01 · Results Overview",
)

comps = get_competitions()
if comps.empty:
    st.warning("尚未导入任何比赛数据。")
    st.stop()

# Filters
col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1, 2, 1.5])
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

with col5:
    top_pct_options = {'全部': 100, '前10%': 10, '前20%': 20, '前30%': 30, '前50%': 50}
    top_pct_label = st.selectbox("成绩筛选", options=list(top_pct_options.keys()))

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

# Filter by top percentage (based on total_score ranking within the group)
top_pct = top_pct_options[top_pct_label]
total_count = len(df)
if top_pct < 100:
    cutoff = max(1, int(total_count * top_pct / 100))
    df = df.head(cutoff)

# Title
gender_str = '/'.join([f'{g}子' for g in genders])
district_str = f" — {district}" if district != '全部' else ""
pct_str = f" — {top_pct_label}" if top_pct < 100 else ""
st.markdown(f"### {gender_str}{group}组{district_str}{pct_str} — 共 {len(df)} 人（总计 {total_count} 人）")

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
    if val == '弃权':
        return ' style="color: #999;"'
    return ''

# Single table with CSS sticky frozen columns (no rowspan, no split tables)
FREEZE_COLS = 4  # 排名, 姓名, 所属区, 总分

event_col_set = {ec[0] for ec in event_cols}
base_keys = [c for c in display_cols if c not in event_col_set]
rest_base_keys = base_keys[FREEZE_COLS:]
ordered_keys = list(base_keys)
for orig, ename, sub in event_cols:
    ordered_keys.append(orig)

# All columns in order with display labels
all_col_labels = [col_rename.get(c, c) for c in base_keys]

# Build CSS: frozen columns need fixed left positions
# Measure each frozen column width based on content
frozen_widths = []
for i in range(FREEZE_COLS):
    label = all_col_labels[i]
    key = base_keys[i]
    # Find max content width: check header + all data
    max_len = len(label)
    for _, row in display_df.iterrows():
        val = str(row.get(key, ''))
        if val != 'nan':
            max_len = max(max_len, len(val))
    # Approximate: each CJK char ~16px, each ASCII char ~9px, plus 20px padding
    avg_char_w = 14
    w = max_len * avg_char_w + 24
    w = max(w, 50)  # minimum 50px
    frozen_widths.append(w)

# Calculate cumulative left offsets
frozen_lefts = []
cum = 0
for w in frozen_widths:
    frozen_lefts.append(cum)
    cum += w

# Header row height
HDR_H = 37

html = '<style>\n'
html += '''.rt-wrap {
    overflow: auto;
    max-height: 620px;
    border-radius: 8px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08);
}
.rt {
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.85rem;
    white-space: nowrap;
}
.rt th, .rt td {
    border: 1px solid #e0e0e0;
    padding: 6px 10px;
    text-align: center;
}
.rt thead th {
    background: #f5f5fa;
    position: sticky;
    top: 0;
    z-index: 3;
    font-weight: 600;
}
'''
# Use actual measured row height: border(1) + padding(6+6) + font(~18) = ~31, use safe value
HDR_ROW_H = 33
html += f'.rt thead tr:nth-child(2) th {{ top: {HDR_ROW_H}px; z-index: 2; }}\n'
html += f'.rt thead tr:nth-child(2) th.fz {{ z-index: 5; top: {HDR_ROW_H}px; }}\n'

# Frozen column CSS per column index
for i in range(FREEZE_COLS):
    html += f'''.rt .fz{i} {{
    position: sticky;
    left: {frozen_lefts[i]}px;
    min-width: {frozen_widths[i]}px;
    max-width: {frozen_widths[i]}px;
    z-index: 1;
    background: #fff;
}}
.rt thead .fz{i} {{
    z-index: 5;
    background: #f5f5fa;
}}
'''

# Right border + shadow on last frozen column to cover scroll gap
html += f'''.rt .fz{FREEZE_COLS - 1} {{
    border-right: 2px solid #d0d0d0;
    box-shadow: 3px 0 6px rgba(0,0,0,0.08);
    clip-path: inset(0 -6px 0 0);
}}
'''

html += '''.rt tbody tr:hover td { background: #f0f4ff; }
.rt tbody td { font-variant-numeric: tabular-nums; }
</style>
'''

# Build table HTML
html += '<div class="rt-wrap"><table class="rt"><thead>\n'

# ---- Header Row 1 ----
html += '<tr>'
# Frozen + non-frozen base columns: show label in row 1
for i in range(len(base_keys)):
    cls = f' class="fz fz{i}"' if i < FREEZE_COLS else ''
    html += f'<th{cls}>{all_col_labels[i]}</th>'
# Event group headers with colspan
for ename, subs in event_groups.items():
    html += f'<th colspan="{len(subs)}">{ename}</th>'
html += '</tr>\n'

# ---- Header Row 2 ----
html += '<tr>'
# Frozen + non-frozen base columns: empty cell (keeps borders, no gap)
for i in range(len(base_keys)):
    cls = f' class="fz fz{i}"' if i < FREEZE_COLS else ''
    html += f'<th{cls}>&nbsp;</th>'
# Event sub-headers (成绩, 得分)
for ename, subs in event_groups.items():
    for sub in subs:
        html += f'<th>{sub}</th>'
html += '</tr>\n</thead>\n<tbody>\n'

# ---- Body Rows ----
for _, row in display_df.iterrows():
    html += '<tr>'
    for col_idx, key in enumerate(ordered_keys):
        val = str(row.get(key, ''))
        if val == 'nan':
            val = ''
        s = cell_style(val)
        if col_idx < FREEZE_COLS:
            if s:
                inner = s.replace(' style="', '').rstrip('"')
                html += f'<td class="fz{col_idx}" style="{inner}">{val}</td>'
            else:
                html += f'<td class="fz{col_idx}">{val}</td>'
        else:
            html += f'<td{s}>{val}</td>'
    html += '</tr>\n'

html += '</tbody></table></div>'

st.markdown(html, unsafe_allow_html=True)
