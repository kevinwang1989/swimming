import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queries.results import get_competitions, get_group_results, get_events_for_group

st.set_page_config(page_title="成绩总览", layout="wide")
st.title("📊 成绩总览")

comps = get_competitions()
if comps.empty:
    st.warning("尚未导入任何比赛数据。")
    st.stop()

# Filters
col1, col2, col3 = st.columns(3)
with col1:
    comp_options = {row['id']: row['name'] for _, row in comps.iterrows()}
    comp_id = st.selectbox("选择比赛", options=list(comp_options.keys()),
                           format_func=lambda x: comp_options[x])

with col2:
    gender = st.selectbox("性别", ['男', '女'])

with col3:
    group = st.selectbox("组别", ['A', 'B', 'C', 'D', 'E', 'F'])

# Get results
df = get_group_results(comp_id, gender, group)

if df.empty:
    st.info("该组别暂无数据。")
    st.stop()

st.markdown(f"### {gender}子{group}组 — 共 {len(df)} 人")

# Get event list for this group
events = get_events_for_group(comp_id, gender, group)

# Format display columns
display_cols = ['rank', 'name', 'district', 'total_score']
col_rename = {'rank': '排名', 'name': '姓名', 'district': '所属区', 'total_score': '总分'}

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

# Apply styling
def highlight_special(val):
    if val == '犯规':
        return 'color: red; font-weight: bold'
    elif val == '弃权':
        return 'color: gray'
    return ''

styled = display_df.style.map(highlight_special)
st.dataframe(styled, use_container_width=True, height=600)
