# 书影音 / 文章 工作流

## 最快方式：本地管理台（推荐）

双击仓库根目录的 **`管理.bat`**，会自动打开浏览器 `http://127.0.0.1:8765`：

- **书影音**：搜索/筛选条目；`+ 新增作品` 粘贴 NeoDB 链接自动识别；点条目「编辑」改标题/评分/状态/日期/标签/短评；「删除」连带影评与本地封面。
- **文章**：左侧列表，右侧 Markdown 编辑器；支持图片上传（自动插入 Markdown）、导入已有 `.md`、草稿、删除。
- 顶部 **「仅本地构建」/「发布到网站」** 按钮，实时日志。默认不自动发布。

关闭那个黑窗口即停止服务。服务只监听本机 `127.0.0.1`。

## 命令行方式（等价）

```bat
python tools/add_item.py <NeoDB链接> --rating 5 --comment "神作"
python tools/new_review.py "标题关键字"      # 为已有条目建/开影评文件
python tools/build.py                         # 本地构建
python tools/build.py --deploy                # 构建并发布（提交 master + 同步 main）
```

## 数据与目录

- `data/*.csv`：条目目录（add_item / 管理台自动写，通常不用手改）。
- `reviews/`：一部作品一篇影评，评分/状态/短评的**编辑入口**（有影评文件时以它为准）。
- `docs/posts/`：文章正文（真正发布的页面）+ `index.md` 列表页（`tools/build_posts.py` 自动生成）。
- `docs/posts/images/`：文章图片。
- `docs/media/covers/`：封面本地图，全部来自 neodb.social。
- `.cache/neodb_meta.json`：NeoDB API 资料缓存（作者/导演/原作名/类型/日期）。
- `.cache/meta.json`、`.cache/failures.json`：封面缓存与缺图清单。

## 维护命令

- `python tools/fetch_neodb_covers.py`：补抓缺失封面（幂等）。
- `python tools/fetch_neodb_meta.py [--refresh]`：补抓/刷新 NeoDB 资料（幂等）。
- 新增条目时 `build` 会自动补封面与资料，通常无需手动跑。

## 发布机制

`tools/build.py --deploy`：提交并推 `master`（源码）→ `mkdocs build --strict` →
把 `site/` 同步到 `main` 分支并推（`main` 即 GitHub Pages 源）。
GitHub 偶发连不上，重试即可。

完整说明（含给下一个 AI 的技术交接）见上一层目录的 `说明书.md`。
