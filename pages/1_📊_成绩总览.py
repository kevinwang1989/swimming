import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.results import get_competitions, get_group_results, get_events_for_group, get_all_districts

st.set_page_config(page_title="成绩总览", layout="wide")
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
for _, evt in events.iterrows():
    ename = evt['name']
    score_col = f'{ename}_成绩'
    point_col = f'{ename}_得分'
    if score_col in df.columns:
        display_cols.append(score_col)
        col_rename[score_col] = f'{ename}\n成绩'
    if point_col in df.columns:
        display_cols.append(point_col)
        col_rename[point_col] = f'{ename}\n得分'

# Filter to existing columns only
display_cols = [c for c in display_cols if c in df.columns]
display_df = df[display_cols].rename(columns=col_rename)

# Format: scores to 1 decimal, None to empty
score_cols = ['总分'] + [c for c in display_df.columns if c.endswith('得分')]
for c in score_cols:
    if c in display_df.columns:
        display_df[c] = display_df[c].apply(
            lambda x: f'{x:.1f}' if pd.notna(x) else ''
        )
display_df = display_df.fillna('')

# Apply styling
def highlight_special(val):
    if val == '犯规':
        return 'color: red; font-weight: bold'
    elif val == '弃权':
        return 'color: gray'
    return ''

styled = display_df.style.map(highlight_special)
st.dataframe(styled, use_container_width=True, height=600)
