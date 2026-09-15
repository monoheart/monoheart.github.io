# 书影音工作流

## 三种日常操作

### 1. 刚看完一部新作品
```bat
python tools/add_item.py https://neodb.social/movie/xxxx --rating 5 --comment "神作"
```
- 链接从 [NeoDB](https://neodb.social) 对应条目页复制即可（book/movie/tv/game 都行）。
- 自动抓标题、归类到对应 `data/*.csv`，并生成 `reviews/` 影评文件。
- 选项：`--rating 1-5`、`--comment "短评"`、`--date 2026-09-15`、`--wishlist`、`--dry-run`。

### 2. 修改旧条目的评分 / 短评 / 状态
直接编辑它的影评文件（`reviews/` 下按标题能找到）：
```markdown
---
title: "三体"
rating: 5          # 1-5 星，改成空则无评分
status: complete   # complete=看过；wishlist=想看（想看的不展示）
---
正文随便写，支持 Markdown。
```
没有影评文件的作品，用 `python tools/new_review.py "标题关键字"` 生成一个再改。

### 3. 发布
双击 `tools/publish.bat`（= `python tools/build.py --deploy`）：
自动补封面/资料 → 重建 `docs/media/*.md` → `mkdocs build --strict` → 同步到 `main` 分支发布。
只本地预览不发布：`python tools/build.py` 然后 `mkdocs serve`。

## 数据与文件

- `data/*.csv`：条目目录（add_item 自动写，一般不用手改）。
- `reviews/`：一部作品一篇影评，**评分/短评/状态的编辑入口**；不发布成独立页面，正文直接显示在卡片里。
- `data/subjects.ndjson`：旧豆瓣离线资料（仅作文字兜底）。
- `docs/media/covers/`：封面本地图，全部来自 neodb.social。
- `.cache/neodb_meta.json`：NeoDB API 资料缓存（作者/导演/原作名/类型/日期等）。
- `.cache/failures.json`：缺封面清单。

## 维护命令

- `python tools/fetch_neodb_covers.py`：补抓缺失封面（幂等）。
- `python tools/fetch_neodb_meta.py [--refresh]`：补抓/刷新 NeoDB 资料（幂等）。
- 新增条目时 `build` 会自动补封面与资料，通常无需手动跑上面两个。
