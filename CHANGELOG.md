# 版本记录

本文件记录游泳成绩分析系统的版本迭代。越靠上越新。

格式：`## [版本号] — 发布日期` + 对应 git commit + 更新内容。

---

## [v1.6.2] — 2026-04-09

**Commit**：待提交

### 修改

- **侧边栏图标统一换成 Material Symbols 矢量图标**（替代之前文件名里的 emoji），
  跨平台渲染一致，告别 macOS 的 3D 彩色 emoji
- 入口架构重构：
  - 新建 `home.py` 承载首页内容（hero / KPI / 卡片网格）
  - `app.py` 改为 router，使用 `st.navigation([st.Page(...), ...])`
  - 每个 `st.Page` 显式指定 `icon=":material/xxx:"`
- 8 个子页面统一去掉自身的 `st.set_page_config(...)`，避免与 router 冲突

### 图标映射

| 页面 | Material Symbol |
|---|---|
| 首页 | `home` |
| 成绩总览 | `leaderboard` |
| 项目详情 | `pool` |
| 排兵布阵 | `groups` |
| 选手查询 | `person_search` |
| 对比分析 | `compare_arrows` |
| 区县排名 | `workspace_premium` |
| 进步榜 | `trending_up` |
| 反馈与帮助 | `help` |

### 注意事项

- 仅改 `app.py` / 新建 `home.py` / 改各 `pages/*.py` 的开头几行；功能逻辑零改动
- Streamlit ≥ 1.30 支持 `st.navigation` + `st.Page`，本机 1.50 OK

---

## [v1.6.1] — 2026-04-09

**Commit**：`f884c1a`

### 新增

- **统一的子页面顶部 banner**：所有 8 个 page 现在使用同一个 `page_header()` helper，
  显示紧凑版的 WA 风格深蓝渐变 banner（kicker 英文 + 中文大标题 + 副标题），
  视觉风格与首页 hero 一致
- 新增 CSS 类 `.wa-page-header` 在 `style.py`
- 新增 `page_header(title, subtitle, kicker)` 辅助函数

### 修改

- `style.py` — 增加 `.wa-page-header` 样式 + `page_header()` 函数
- `pages/1_📊_成绩总览.py` 至 `pages/8_📈_进步榜.py` — 全部 8 个页面把 `st.title()` + `st.caption()` 换成 `page_header(...)`

### 视觉细节

| 页面 | Kicker (Oswald 全大写英文) |
|---|---|
| 1 成绩总览 | 01 · Results Overview |
| 2 项目详情 | 02 · Event Details |
| 3 排兵布阵 | 03 · Relay Lineup |
| 4 选手查询 | 04 · Athlete Profile |
| 5 对比分析 | 05 · Comparison |
| 6 区县排名 | 06 · District Ranking |
| 7 反馈与帮助 | 07 · Feedback & Help |
| 8 进步榜 | 08 · Progress Leaderboard |

---

## [v1.6] — 2026-04-09

**Commit**：`4e62c37`

### 新增

- **✨ 选手赛季战报**（嵌入「🔍 选手查询」页底部）
  - 选中任一选手 → 展开「✨ 生成赛季战报」面板 → 自动生成 markdown 战报
  - 包含 4 个 section：
    - **📊 综合表现** — 各场比赛的排名 / 总分 / 评级
    - **🏆 最佳单项** — 在同组别同性别全市选手中的 percentile（前 10% / 前 25% / 中上游 / 待提升 分级措辞）
    - **🚀 最大进步** — 复用进步榜数据，找到该选手提升幅度最大的项目，并按 Δ% 给出鼓励语
    - **📋 全部游泳项目** — 按同组排位升序的完整项目表
  - 战报可直接截图分享
  - 已预留 LLM 润色接口 `rewrite_with_llm()`，未来开通 API key 后可一键升级

### 修改

- `queries/season_report.py` — 新建。`build_report()` 计算结构化数据，`render_report_markdown()` 模板渲染；带 `_peer_times()` cached helper 算 percentile
- `pages/4_🔍_选手查询.py` — 底部新增 expander，调用上述两函数

### 约束

- 战报基于已导入的两场比赛；第三场导入后自动更丰富
- 对单场新手 / 无进步项目的选手会自动跳过对应 section，不会报错
- LLM 润色版本暂未开通（用户当前无 API key），后续触发条件：用户配置好 `LLM_API_KEY` 后另开 plan 实现

---

## [v1.5] — 2026-04-09

**Commit**：`9ec1d42`

### 新增

- **📈 跨站进步榜**（新 page `pages/8_📈_进步榜.py`）
  - 对在两场比赛都参加同一组别同一项目的选手，自动配对计算成绩变化
  - 默认全站 Top 20 进步榜；支持按性别 / 组别 / 项目 / 区县筛选
  - 排序可切：按绝对秒数 vs 按相对百分比（对不同距离公平）
  - KPI 卡：可对比项目数 / 进步项目数 / 退步项目数 / 平均 Δ
  - 三个 tab：进步榜 / 退步榜 / 全部明细
  - 计算口径在折叠面板里完整说明

### 修改

- `queries/progress.py` — 新建。核心 SQL 用 `enrollment.group_id` 配对避免跨年龄段误判，按 `competition.date` 取前后两场

### 约束

- 单场新手 / 跨年龄段升组的选手 / 犯规弃权记录 → 不会出现在榜上
- 当前数据基础：2 场比赛 × 244 条可对比记录（123 进步 / 121 退步）
- 第三场比赛导入后样本量会显著上升

---

## [v1.4] — 2026-04-09

**Commit**：`6d138b1`

### 新增

- **🎨 视觉风格升级**：参考 World Aquatics 官网（worldaquatics.com/swimming）的编辑风重设计
  - **Hero banner**：首页顶部深蓝渐变 banner + 全大写英文大标题 + 中文副标题 + 核心数据 meta
  - **Stat cards**：`st.metric` 从粉紫 pastel 改为白底 + 4px 蓝色 accent bar，数字用 Oswald display 字体
  - **Editorial cards**（`.wa-card`）：首页「Recent Competitions」和「Explore the Data」section 换成卡片网格，hover 蓝边 + 微上浮
  - **字体**：引入 **Oswald**（英文 display，用于 h1/h2/数字/按钮），中文继续 Noto Sans SC
  - **品牌色统一**：WA 同款深蓝 `#0282c6` + 深海军蓝 `#003a5d`，通过 CSS 变量全局复用
  - **Sidebar**：从灰蓝 pastel 改为深海军蓝 + 白字，模拟 WA 顶部 nav 风格
  - **Tabs**：下划线式替换圆角 tab
  - **DataFrame / Button / h1-h3** 统一收敛到 WA 配色和排版

### 修改

- `app.py` 首页完全重写：Hero + KPI row + Competition cards + 7 张 Quick-link cards
- `.streamlit/config.toml` 主题色改为 `#0282c6`
- `queries/results.py` 新增 `get_site_stats()` 返回首页 KPI 4 项 count

### 约束

- 本次仅改动 `app.py` / `style.py` / `.streamlit/config.toml` / `queries/results.py`（+1 函数）/ 新建 `assets/`
- **完全不动** `pages/*`、`queries/lineup.py`、`queries/insights.py`、DB、importer
- Oswald 仅用于标题 / 数字 / 按钮，中文正文绝不使用（Oswald 无 CJK 支持）
- 高清游泳照片待用户提供后，在 `style.py` 打开一行注释即可叠加到 hero 背景

### 注意事项

- 纯代码改动 → Streamlit Cloud 自动部署，**无需 reboot**

---

## [v1.3] — 2026-04-08

**Commit**：`935d48c`

### 新增

- **🏅 排兵布阵** 新页：为任意代表队 + 组别自动推荐最强接力阵容
  - **混合泳接力**：枚举所有 4 人组合 × 4 种泳姿分配，选总时间最小
  - **自由泳接力**：取自由泳最快前 4 名
  - **推荐 vs 实际**：若该区在本次比赛实际参加了该接力，同步展示实际阵容 + 成绩 + 理论可优化空间
  - **数据来源切换**：本次比赛 / 历史 PB（跨站最佳），用户一键切换
  - **多来源兜底**：每个棒次的估计时间优先级 `单项 → 按100米推算 → 400/200个混分段`，表格明确标注来源
- 页面顺序调整为：`成绩总览 → 项目详情 → 排兵布阵 → 选手查询 → 对比分析 → 区县排名 → 反馈与帮助`

### 注意事项

- 推荐阵容的预计总时间**不包含接力飞跃出发红利**（通常比单项快 1-3 秒/棒），因此"理论可优化 X 秒"只反映选人层面的优化空间
- 若某组别没有某泳姿的单项数据（如 F 组女生没有 50 米单项），会回退到 100 米单项换算或 IM 分段，**估算误差会放大**；好在对排名影响小

---

## [v1.2] — 2026-04-08

**Commit**：`a86d0df` (rename) + `099d0e2` (insights)

### 新增

- **🔬 深度分析** section 加入「项目详情」页，三个 Tab 自动生成中文洞察（无 LLM）
  - **单区分析**：某区在该项目的分段优势/劣势排序（带 z-score）
  - **双区对比**：两区总成绩差 + 每段强弱分布 + 🏁 汇总结论
  - **选手对比**：复用分段对比选手列表，自动指出「关键差距来自哪一段」
- 支持个混项目（带泳姿标签）和普通项目（前 50m / 后 50m 通用叙述）

### 修改

- 两场比赛改名：
  - `2026游泳第一站` → **2026上海精英赛第一站**
  - `2025上海游泳总决赛` → **2025上海精英赛总决赛**

### 注意事项

- 纯代码改动自动部署；**DB 改动需手动 Reboot Streamlit Cloud** 才能清 `@st.cache_data` 缓存

---

## [v1.1] — 2026-04-08

**Commit**：`33d60c2` (import) → `a8ce3e6` (UI polish)

### 新增

- 导入 **2025 上海游泳总决赛** PDF（212 页，全新格式）
  - 每段成绩（lap + cumulative）
  - 反应时间 R.T.
  - 运动员等级（athlete_level）
  - **接力项目**（男/女 A-F 组 4×100 混合泳/自由泳接力），独立 `relay_team` + `relay_leg` 表
- 「🏊 项目详情」页新建
  - 代表队筛选
  - 分段格式 `本段 (累积)`
  - 分段对比表格（代替原线图）
  - 接力项目独立展示（队伍表 + 各棒详情 expander）
- 「项目详情」页顺位调整到第 2 位

### 修复

- Expander 箭头显示 `keyboard_arrow_right` 字面字符（CSS 字体覆盖冲突）
- `放弃` 状态行夹带脏数据污染区下拉
- 跨页接力棒次拼接丢失
- IM 项目泳姿顺序强制 蝶 → 仰 → 蛙 → 自由

### 约束

- v1.0 老数据（第一站）零影响：新字段 nullable、新表隔离

---

## [v1.0] — 2026 年初期

**起点 commit**：`da74ce7` Initial commit
**v1.0 末尾 commit**：`cd124b0` Add top percentage filter

### 初始系统

- **成绩总览**：组别内所有项目多列展示 + 冻结前 4 列 + 区/性别/组别/百分位筛选
- **选手查询**：跨站追踪单个选手
- **对比分析**：多选手同站 / 跨站对比
- **区县排名**：各区分项目聚合排名
- **反馈与帮助**：老版 PDF 导入页（密码保护）+ 小红书联系方式

### 数据支持

- 老格式 PDF 导入（per-group 表格，12 个组别 × 3 种格式）
- 单站多项目聚合
- 选手跨站去重（UNIQUE(name, district)）

### 技术栈

- Python 3 + Streamlit
- SQLite（单文件，checked into git）
- pdfplumber 解析
- `@st.cache_data(ttl=600)` 查询层缓存
- 自定义 CSS 主题

---

## 维护约定

- 每次发版后在顶部追加一段
- 版本号规则：
  - **主版本号**（x.0）：数据模型/架构重大变化
  - **次版本号**（1.x）：新功能 / 新数据源 / 新页面
  - **修订号**（1.1.x）：bug 修复、文案/UI 小改，一般不单独发版记录
- 每段必须包含：版本号 + 发布日期 + 关键 commit + 新增/修改/修复分类
- 部署注意事项（如需手动 reboot）写在对应版本下
