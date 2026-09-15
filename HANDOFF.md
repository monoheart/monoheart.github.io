# 交接文档（给下一个 AI / 未来的自己）

> 项目：`monoheart电波站` —— 个人书影音 + 文章的静态网站
> 仓库：`D:\_workspace3\mkdocs\mono`（工作区）→ GitHub `monoheart/monoheart.github.io`
> 站点：https://monoheart.github.io/
> 最后更新：2026-09-15

---

## 1. 一句话概览

用 **MkDocs + Material** 生成静态站，数据源是**本地 CSV + 影评文件 + 文章文件**，
封面与元数据**自动从 NeoDB 抓取**，产物推到 GitHub Pages（`main` 分支）。
日常操作通过**本地网页管理台**（`管理.bat`）完成，一个按钮发布。

---

## 2. 分支与发布模型（重要，不要搞错）

| 分支 | 内容 | 说明 |
|---|---|---|
| `master` | **源码**：`data/` `reviews/` `docs/` `tools/` `mkdocs.yml` | 日常提交到这里 |
| `main` | **构建产物**：`mkdocs build` 出的 `site/` 内容 | GitHub Pages 的源（root） |
| `gh-pages` | 历史遗留，**已弃用** | 不要用 `mkdocs gh-deploy` |

发布逻辑写在 `tools/build.py` 的 `deploy()`：提交并 push `master` → `mkdocs build --strict` →
用临时 git worktree 把 `site/` 覆盖到 `main` 并 push。

* GitHub Pages 设置在仓库 Settings → Pages = **Deploy from a branch / `main` / root**。
* 本机到 github.com 的网络**经常中断**，push 会失败；`tools/app.py` 的发布日志会显示，
  重试即可（`git push origin master` / 同理 `main`）。**不要**改成 force push。

---

## 3. 目录结构

```
mono/
├─ mkdocs.yml               # 站点配置（含 nav：首页/书/影/剧/游戏/文章）
├─ 管理.bat                 # 双击启动本地管理台
├─ data/                    # 可编辑数据源
│  ├─ books.csv movies.csv tv.csv games.csv   # 条目目录
│  └─ subjects.ndjson       # 旧豆瓣离线资料（仅文字兜底，作者/原作名等）
├─ reviews/                 # 影评源：一部作品一篇 .md（写作用，不生成独立页面）
├─ docs/                    # MkDocs 文档根
│  ├─ index.md              # 首页（用户要求：保持原样，不要动）
│  ├─ media/                # 自动生成的表格→卡片页（books/movies/tv/games.md）
│  │  └─ covers/            # 本地封面 neodb-<id>.jpg
│  ├─ posts/                # 文章正文 + index.md（列表页）+ images/
│  └─ stylesheets/extra.css # 卡片样式
├─ tools/                   # 全部脚本
├─ .cache/                  # 封面/元数据缓存（不入库体积大？实际上入库了）
└─ site/                    # 构建产物（.gitignore，不进 master）
```

---

## 4. 数据模型

### 4.1 条目 CSV（`data/*.csv`）
列：`title, info, links, timestamp, status, rating, comment, tags`
- `links`：空格分隔的多个 URL，**第一个 neodb.social 与 douban 用于主键抓取**。
- `status`：`complete`（看过，展示）/ `wishlist`（想看，**不展示**）。
- `rating`：`10 / 8 / 6 / 4 / 2`（对应 5/4/3/2/1 星），空=无评分。
- 主键（`media_lib.row_key`）：优先 `douban:<id>`，否则 `neodb:<id>`，否则 `title:日期`。

### 4.2 影评（`reviews/*.md`）
frontmatter：`title, medium, status, rating(1-5), date, douban, neodb, tags`；正文=短评/长评。
**规则：某条目存在影评文件时，`status / rating / 正文` 以影评文件为准**（见 `build.py` 中 `_status`）。
没有影评文件则用 CSV 的 `rating / comment`。

### 4.3 文章（`docs/posts/*.md`）
frontmatter：`title, date, tags, summary, cover(可选), draft(可选)`。
`draft: true` 不进列表页。列表页 `docs/posts/index.md` 由 `tools/build_posts.py` 生成。

### 4.4 缓存
- `.cache/neodb_meta.json`：`neodb id -> {display_title, orig_title, director/author/developer, genre, release_date, pub_year, ...}`（453 条全量）。
- `.cache/meta.json`：封面下载记录。
- `.cache/failures.json`：缺封面清单。

---

## 5. 工具清单（`tools/`）

| 文件 | 作用 |
|---|---|
| `app.py` | **本地管理台**服务（标准库 http.server，127.0.0.1:8765），全部 API |
| `web/index.html` | 管理台前端（原生 JS 单页） |
| `media_lib.py` | 共享库：路径/键/星级换算/影评与 frontmatter 读写/条目增删改 |
| `build.py` | 构建：补封面+元数据 → 生成 `docs/media/*.md` → 调 `build_posts` → `--deploy` 发布 |
| `build_posts.py` | 扫描 `docs/posts` 生成列表页 |
| `add_item.py` | 新增条目（CLI + 被 app 调用的 `preview_entry/add_entry`） |
| `new_review.py` | 为已有条目建/开影评文件 |
| `fetch_neodb_covers.py` | 批量补封面（NeoDB og:image，2s/条） |
| `fetch_neodb_meta.py` | 批量补元数据（NeoDB API，幂等） |
| `import_comments.py` | 一次性把 CSV 短评迁移成影评文件（已跑完，保留备用） |
| `publish.bat` | 双击 = `python tools/build.py --deploy` |
| `README.md` | 面向使用者的简版说明 |

### 管理台 API（`app.py`）
```
GET  /api/media                      列出全部条目（合并 CSV+影评）
GET  /api/articles                   列出文章
GET  /api/article?file=              读文章
GET  /api/publish_log?since=N        轮询发布日志
POST /api/media/preview              {url} 识别 NeoDB 链接
POST /api/media/add                  {url,rating,comment,date,wishlist}
POST /api/media/save                 {medium,key,title,status,rating,date,tags,body}
POST /api/media/delete               {medium,key}
POST /api/article/save               {file?,title,date,tags,summary,draft,body}
POST /api/article/delete             {file}
POST /api/upload_image               {filename,data(base64)}
POST /api/publish                    {deploy:bool}
```

---

## 6. 关键设计与坑（务必阅读）

1. **封面全部来自 NeoDB**：`https://neodb.social/api/<neodb_id>` 免鉴权可拿 `cover_image_url`；
   但本仓库用 **og:image**（`fetch_neodb_covers.py`）下载到 `docs/media/covers/neodb-<id>.jpg`。
   豆瓣图片有防盗链/限频（曾返回 418 与验证页），已**不再使用豆瓣图**。
2. **NeoDB API 要带 `Accept-Language: zh-CN`**，否则标题返回英文/罗马音（`build.py` 已设置）。
3. **封面路径是相对路径**：页面在 `media/<page>/` 下（Material `use_directory_urls`），
   所以卡片里图片写 `../covers/xxx.jpg`。改模板时别忘了这点。
4. **卡片是手写 HTML**（不是 Markdown 表格）：`build.py::card_html`。为的是统一高度 +
   简评框内滚动 + 零横向滚动。CSS 在 `docs/stylesheets/extra.css`：
   - 卡片固定结构：`.media-head`(封面+标题/作者/资料，高 168px) + `.media-body`(星级行 + 简评框)。
   - 简评框 `height: calc(5 * 1.8em)` = 固定 5 行，超出内部滚动。
   - 任何新增长内容都要考虑 `min-width:0` + `overflow-wrap:anywhere`，否则长英文会撑破布局。
5. **星级换算**：CSV `10/8/6/4/2` ↔ 影评/UI `1-5`，用 `media_lib.CSV_TO_STARS / STARS_TO_CSV`。
6. **HTML 转义**：卡片内容必须 `html.escape`，短评换行转 `<br>`（`esc` / `esc_multi`）。
7. **删除条目**会连带删影评文件、本地封面、元数据缓存项（仅当无其他行共用）。
8. **`docs/index.md` 是测试页，用户明确要求不要动**。
9. `.gitignore` 忽略 `site/`、`.cache/`、`__pycache__/`；但 `.cache/*.json` 实际有被提交过
   （历史原因），不影响运行。

---

## 7. 已知问题 / 待办

- **1 个条目无封面**：`data/books.csv` 的《岩波日本史（全九卷）》——NeoDB 本身无图（占位 GIF），
  卡片显示灰色「无封面」。属正常，不是 bug。
- **7 个条目无作者**：NeoDB 无任何演职员信息（如《功勋》《疯狂动物城+》《千与千寻》见测试），
  卡片省略作者行。原作者缺失的根因已通过「导演→编剧→主演」回退解决（55→7）。
- **TV 有 episode 级脏数据**：`data/tv.csv` 里有标题为 `第1集` 的条目（`tv/episode/...`），
  会作为卡片出现。可考虑过滤 `episode` 级条目，但用户未要求。
- **游戏封面**：游戏走 NeoDB og:image，一般有；若缺失见 `failures.json`。
- **首页**：`docs/index.md` 仍是测试内容，未做首页汇总（用户要求不动）。
- **网络**：本机到 github.com / neodb.social 间歇性断连，脚本已做重试/幂等，但发布可能需手动重试。
- **`import_comments.py` 仅在首次迁移时跑过**，重复运行是幂等的（已存在则跳过）。

---

## 8. 当前数据快照（2026-09-15）

- 条目：**453** 行（书 198 / 影 158 / 剧 95 / 游戏 2），其中 **244** 条 `complete` 会展示。
- 影评文件：**128** 篇。封面：**452** 张本地图。元数据缓存：**453** 条。
- 站点导航：`首页 / 书 / 影 / 剧 / 游戏 / 文章`。

---

## 9. 常用操作速查

```bat
:: 打开管理台（推荐）
管理.bat

:: 本地预览（改完先看效果）
python tools/build.py
mkdocs serve

:: 发布
python tools/build.py --deploy        :: 或双击 publish.bat

:: 补数据
python tools/fetch_neodb_meta.py      :: 补元数据
python tools/fetch_neodb_covers.py    :: 补封面
```

## 10. 变更历史（本节追加，勿删）

- 2026-09-14 初始：CSV → MkDocs 卡片站，封面/影评/元数据管线，发布到 `main`。
- 2026-09-15 卡片改版（单列、统一高度、封面右置资料、简评 5 行内滚）。
- 2026-09-15 新增**本地管理台** `app.py` + 文章栏目（`docs/posts`）+ `build_posts.py`。
