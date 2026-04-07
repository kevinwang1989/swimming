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

# Split into frozen (base) columns and scrollable (event) columns
FREEZE_COLS = 4  # 排名, 姓名, 所属区, 总分

event_col_set = {ec[0] for ec in event_cols}
base_keys = [c for c in display_cols if c not in event_col_set]
frozen_keys = base_keys[:FREEZE_COLS]
rest_base_keys = base_keys[FREEZE_COLS:]  # 评级, 备注 etc.
event_keys = [orig for orig, ename, sub in event_cols]

# Scrollable column keys = remaining base columns + event columns
scroll_keys = rest_base_keys + event_keys

# Row height must be consistent
ROW_H = 35

html = f'''<style>
.split-table-wrap {{
    display: flex;
    max-height: 620px;
    border-radius: 8px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08);
    overflow: hidden;
}}
/* Left frozen table */
.frozen-part {{
    flex-shrink: 0;
    overflow-y: auto;
    border-right: 2px solid #ccc;
    box-shadow: 2px 0 6px rgba(0,0,0,0.08);
    z-index: 2;
    scrollbar-width: none;
}}
.frozen-part::-webkit-scrollbar {{ display: none; }}
/* Right scrollable table */
.scroll-part {{
    flex: 1;
    overflow-x: auto;
    overflow-y: auto;
}}
/* Sync scroll: hide scrollbar on frozen side, real scrollbar on scroll side */
.tbl {{
    border-collapse: collapse;
    font-size: 0.85rem;
    white-space: nowrap;
}}
.tbl th, .tbl td {{
    border: 1px solid #e0e0e0;
    padding: 6px 10px;
    text-align: center;
    height: {ROW_H}px;
    box-sizing: border-box;
}}
.tbl thead th {{
    background: #f5f5fa;
    font-weight: 600;
    position: sticky;
    top: 0;
    z-index: 2;
}}
.tbl thead tr:first-child th {{ top: 0; z-index: 3; }}
.tbl thead tr:nth-child(2) th {{ top: {ROW_H}px; z-index: 2; }}
.tbl tbody tr:hover {{ background: #f0f4ff; }}
.tbl tbody td {{ font-variant-numeric: tabular-nums; }}
</style>

<script>
// Synchronize vertical scroll between frozen and scroll parts
document.addEventListener('DOMContentLoaded', function() {{
    setTimeout(function() {{
        var pairs = document.querySelectorAll('.split-table-wrap');
        pairs.forEach(function(wrap) {{
            var fp = wrap.querySelector('.frozen-part');
            var sp = wrap.querySelector('.scroll-part');
            if (!fp || !sp) return;
            var syncing = false;
            sp.addEventListener('scroll', function() {{
                if (syncing) return;
                syncing = true;
                fp.scrollTop = sp.scrollTop;
                syncing = false;
            }});
            fp.addEventListener('scroll', function() {{
                if (syncing) return;
                syncing = true;
                sp.scrollTop = fp.scrollTop;
                syncing = false;
            }});
        }});
    }}, 500);
}});
</script>

<div class="split-table-wrap">
<div class="frozen-part">
<table class="tbl"><thead>
<tr>'''

# Frozen header: base columns with rowspan=2
frozen_labels = [col_rename.get(c, c) for c in frozen_keys]
for label in frozen_labels:
    html += f'<th rowspan="2">{label}</th>'
html += f'</tr>\n<tr style="height:{ROW_H}px;"></tr></thead>\n<tbody>'

# Frozen body rows
for _, row in display_df.iterrows():
    html += '<tr>'
    for key in frozen_keys:
        val = str(row.get(key, ''))
        if val == 'nan':
            val = ''
        s = cell_style(val)
        html += f'<td{s}>{val}</td>'
    html += '</tr>\n'
html += '</tbody></table></div>\n'

# Scrollable part
html += '<div class="scroll-part"><table class="tbl"><thead>\n<tr>'

# Rest base columns with rowspan=2
rest_base_labels = [col_rename.get(c, c) for c in rest_base_keys]
for label in rest_base_labels:
    html += f'<th rowspan="2">{label}</th>'
# Event group headers with colspan
for ename, subs in event_groups.items():
    html += f'<th colspan="{len(subs)}">{ename}</th>'
html += '</tr>\n<tr>'
# Event sub-headers
for ename, subs in event_groups.items():
    for sub in subs:
        html += f'<th>{sub}</th>'
html += '</tr></thead>\n<tbody>'

# Scrollable body rows
for _, row in display_df.iterrows():
    html += '<tr>'
    for key in scroll_keys:
        val = str(row.get(key, ''))
        if val == 'nan':
            val = ''
        s = cell_style(val)
        html += f'<td{s}>{val}</td>'
    html += '</tr>\n'
html += '</tbody></table></div>\n</div>'

st.markdown(html, unsafe_allow_html=True)
