# 书影音工作流

日常两步：

1. **写影评**：`python tools/new_review.py "标题关键字"` 建文件，然后在
   `docs/reviews/` 里用 Markdown 写正文，改 `rating: 1-5` / `status` 即可。
   已有短评已由 `tools/import_comments.py` 一次性迁入（CSV 本体不动）。
2. **发布**：双击 `tools/publish.bat`（= `python tools/build.py --deploy`），
   自动补封面 -> 重建 `docs/media/*.md` + `docs/reviews/index.md` ->
   `mkdocs build --strict` -> `mkdocs gh-deploy --force`。

只想本地预览不发布：`python tools/build.py` 然后 `mkdocs serve`。

- 可编辑源：`data/*.csv`（从 NeoDB 导出拷入，改状态/补新条目都在这）。
- 离线封面库：`data/subjects.ndjson`，封面下载到 `docs/media/covers/`。
- 标题/评分/短评永远以本地为准：有影评文件的用影评，否则用 CSV。
- 缺封面清单：`.cache/failures.json`。
