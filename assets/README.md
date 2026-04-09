# assets/

静态资源目录。

## Hero 图片（v1.4+ 首页）

首页 hero banner 当前使用纯蓝色渐变兜底。若要叠真实照片：

1. 放一张高清游泳照片到 `assets/hero_pool.jpg`
   - 推荐尺寸：**1600×480 或更大**（横向比例约 10:3）
   - 内容：游泳池 / 比赛起跳 / 泳道俯拍 等
   - 格式：JPG，文件大小 ≤ 500KB（Streamlit Cloud 冷启动友好）
2. 打开 `style.py` 中 `.wa-hero` 的注释行（搜索 `hero_pool.jpg`）
3. Commit & push；Streamlit Cloud 自动部署

## 其他文件

- `xhs_profile.jpg` — 小红书联系方式二维码（「反馈与帮助」页使用）
