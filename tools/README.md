# 书影音工作流

日常两步：

1. **写影评**：`python tools/new_review.py "标题关键字"` 建文件，然后在
   `reviews/` 里用 Markdown 写正文，改 `rating: 1-5` / `status` 即可。
   旧短评已由 `tools/import_comments.py` 一次性迁入（CSV 本体不动）。
   注意：`reviews/` 只是写作源，不会发布成详情页，短评全文直接展示在表格里。
2. **发布**：双击 `tools/publish.bat`（= `python tools/build.py --deploy`），
   自动补封面 -> 重建 `docs/media/*.md` -> `mkdocs build --strict` ->
   同步到 `main` 分支并 push（`master`=源码，`main`=网站成品）。

只想本地预览不发布：`python tools/build.py` 然后 `mkdocs serve`。

- 可编辑源：`data/*.csv`（改状态/补新条目都在这）。
- 离线封面库：`data/subjects.ndjson`，封面下载到 `docs/media/covers/`。
- 标题/评分/短评永远以本地为准：有影评文件的用影评全文，否则用 CSV。
- 缺封面清单：`.cache/failures.json`；限流时过几天跑
  `python tools/backfill_covers.py` 再 `build` 即可补上。
