import streamlit as st
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.init_db import init_database
from importer.import_service import import_pdf
from queries.results import get_competitions

st.set_page_config(page_title="导入数据", layout="wide")
st.title("📥 导入比赛数据")

# Show existing competitions
comps = get_competitions()
if not comps.empty:
    st.markdown("### 已导入的比赛")
    st.dataframe(comps[['name', 'short_name', 'date']].rename(columns={
        'name': '比赛名称', 'short_name': '简称', 'date': '日期'
    }), use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("### 导入新比赛")

# Admin password protection
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "swim2026admin")

password = st.text_input("请输入管理员密码", type="password", placeholder="输入密码解锁导入功能...")

if not password:
    st.info("导入功能需要管理员密码。")
    st.stop()

if password != ADMIN_PASSWORD:
    st.error("密码错误。")
    st.stop()

st.success("验证通过，可以导入数据。")

# Upload form
uploaded_file = st.file_uploader("上传成绩册 PDF", type=['pdf'])

col1, col2, col3 = st.columns(3)
with col1:
    comp_name = st.text_input("比赛名称", placeholder="例：2026游泳第二站")
with col2:
    short_name = st.text_input("简称", placeholder="例：第二站")
with col3:
    comp_date = st.date_input("比赛日期")

if uploaded_file and comp_name and short_name:
    if st.button("开始导入", type="primary"):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        try:
            with st.spinner("正在解析 PDF 并导入数据..."):
                init_database()
                stats = import_pdf(
                    tmp_path,
                    comp_name,
                    short_name,
                    str(comp_date)
                )

            st.success(f"""
            导入成功！
            - 组别数：{stats['groups']}
            - 选手数：{stats['participants']}
            - 成绩记录数：{stats['results']}
            """)
            st.balloons()

        except Exception as e:
            st.error(f"导入失败：{str(e)}")
        finally:
            os.unlink(tmp_path)
else:
    if uploaded_file:
        st.info("请填写比赛名称和简称后点击「开始导入」。")
