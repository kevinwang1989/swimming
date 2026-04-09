import streamlit as st
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

st.set_page_config(page_title="反馈与帮助", layout="wide")

from style import apply_style, page_header
apply_style()

page_header(
    title="💬 反馈与帮助",
    subtitle="意见反馈、数据导入、查看完整版本更新记录。",
    kicker="07 · Feedback & Help",
)

# ---- Feedback section ----
st.markdown("### 意见反馈")
st.markdown("如果你在使用中遇到问题或有功能建议，欢迎通过小红书联系我：")

col1, col2 = st.columns([1, 2])
with col1:
    xhs_img = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "xhs_profile.jpg")
    if os.path.exists(xhs_img):
        st.image(xhs_img, use_container_width=True)
    else:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #ff2442 0%, #ff6b81 100%);
            border-radius: 16px;
            padding: 1.5rem;
            text-align: center;
            color: white;
        ">
            <div style="font-size: 1.3rem; font-weight: 700; margin-bottom: 0.3rem;">KK下泳池</div>
            <div style="font-size: 0.9rem; opacity: 0.9;">小红书号：542518058</div>
        </div>
        """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    **关注方式：**
    1. 打开小红书 App
    2. 搜索 **KK下泳池** 或小红书号 **542518058**
    3. 关注后私信即可反馈

    **可以反馈的内容：**
    - 🐛 数据错误或显示问题
    - 💡 功能建议和需求
    - ❓ 使用过程中的疑问
    """)

st.markdown("---")

# ---- Data import section (password protected) ----
st.markdown("### 数据导入（管理员）")

from db.init_db import init_database
from importer.import_service import import_pdf, import_final_pdf
from queries.results import get_competitions

comps = get_competitions()
if not comps.empty:
    st.markdown("**已导入的比赛：**")
    st.dataframe(comps[['name', 'short_name', 'date']].rename(columns={
        'name': '比赛名称', 'short_name': '简称', 'date': '日期'
    }), use_container_width=True, hide_index=True)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "swim2026admin")

password = st.text_input("请输入管理员密码", type="password", placeholder="输入密码解锁导入功能...")

if not password:
    st.info("导入功能需要管理员密码。")
    st.stop()

if password != ADMIN_PASSWORD:
    st.error("密码错误。")
    st.stop()

st.success("验证通过，可以导入数据。")

uploaded_file = st.file_uploader("上传成绩册 PDF", type=['pdf'])

col1, col2, col3 = st.columns(3)
with col1:
    comp_name = st.text_input("比赛名称", placeholder="例：2026游泳第二站")
with col2:
    short_name = st.text_input("简称", placeholder="例：第二站")
with col3:
    comp_date = st.date_input("比赛日期")

# Heuristic: filename containing "总决赛" or "final" defaults to finals format
default_format_idx = 0
if uploaded_file is not None:
    fn = uploaded_file.name.lower()
    if '总决赛' in uploaded_file.name or 'final' in fn:
        default_format_idx = 1

format_label = st.radio(
    "PDF 格式",
    options=['老格式（按组别）', '总决赛格式（按项目，含分段成绩 / 接力）'],
    index=default_format_idx,
    horizontal=True,
)

if uploaded_file and comp_name and short_name:
    if st.button("开始导入", type="primary"):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        try:
            with st.spinner("正在解析 PDF 并导入数据..."):
                init_database()
                if format_label.startswith('总决赛'):
                    stats = import_final_pdf(tmp_path, comp_name, short_name, str(comp_date))
                    st.success(f"""
                    导入成功！
                    - 项目数：{stats['events']}
                    - 个人成绩记录：{stats['records']}
                    - 接力队伍：{stats['relay_teams']}
                    - 接力选手段次：{stats['relay_legs']}
                    """)
                else:
                    stats = import_pdf(tmp_path, comp_name, short_name, str(comp_date))
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

# ---- Version history ----
st.markdown("---")
st.markdown("### 📋 版本记录")
changelog_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "CHANGELOG.md")
if os.path.exists(changelog_path):
    with open(changelog_path, "r", encoding="utf-8") as f:
        changelog_text = f.read()
    with st.expander("查看完整版本更新记录", expanded=False):
        st.markdown(changelog_text)
else:
    st.caption("暂无版本记录文件。")
