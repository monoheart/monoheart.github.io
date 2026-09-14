# -*- coding: utf-8 -*-
"""一次性迁移：把 4 个 CSV 里非空 comment 转成 docs/reviews/ 下一篇一文件。

幂等：目标文件已存在（按 key 匹配）则跳过。CSV 本体不动。
用法：python tools/import_comments.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_lib as lib


def main():
    os.makedirs(lib.REVIEWS_DIR, exist_ok=True)
    existing = lib.load_reviews()
    created, skipped = 0, []
    for medium in lib.MEDIUMS:
        for row in lib.load_csv_rows(medium):
            comment = (row.get("comment") or "").strip()
            if not comment:
                continue
            key = lib.row_key(medium, row)
            if key in existing:
                skipped.append(row.get("title") or key)
                continue
            douban_id = lib.extract_douban_id(row.get("links", ""))
            neodb_id = lib.extract_neodb_id(row.get("links", ""))
            title = (row.get("title") or "").strip() or "未命名"
            date = (row.get("timestamp") or "")[:10]
            stars = lib.CSV_TO_STARS.get((row.get("rating") or "").strip(), None)
            tags = [t.strip() for t in (row.get("tags") or "").split("|") if t.strip()]
            text = lib.dump_review(
                title, medium, (row.get("status") or "complete").strip(),
                stars, date,
                lib.first_douban_url(row.get("links", "")),
                lib.first_neodb_url(row.get("links", "")),
                tags, comment + "\n",
            )
            fname = lib.review_filename(medium, title, douban_id, neodb_id, date)
            path = lib.unique_path(lib.REVIEWS_DIR, fname)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            created += 1
            existing[key] = {"path": path}
    print(f"created={created} skipped={len(skipped)}")
    for t in skipped[:20]:
        print("  skip(exists):", t)


if __name__ == "__main__":
    main()
