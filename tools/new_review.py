# -*- coding: utf-8 -*-
"""新建/打开某条作品的影评文件：python tools/new_review.py "三体"
按标题模糊匹配 CSV，在 reviews/ 建文件并预填资料；已存在则直接打印路径。
（若是全新作品，请先用 tools/add_item.py 添加。）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_lib as lib


def find(query):
    hits = []
    subjects = lib.load_subjects()
    for medium in lib.MEDIUMS:
        for row in lib.load_csv_rows(medium):
            if query.lower() in (row.get("title") or "").lower():
                douban_id = lib.extract_douban_id(row.get("links", ""))
                hits.append((medium, row, douban_id, subjects.get(douban_id) if douban_id else None))
    return hits


def main():
    if len(sys.argv) < 2:
        print('用法: python tools/new_review.py "作品标题"')
        sys.exit(1)
    query = sys.argv[1].strip()
    hits = find(query)
    if not hits:
        print(f"CSV 里没有包含 [{query}] 的条目。")
        print("如果是刚看完的新作品，请先添加：")
        print('  python tools/add_item.py <NeoDB链接> --rating 5 --comment "短评"')
        sys.exit(1)
    if len(hits) > 1:
        print(f"找到 {len(hits)} 条，请复制整标题再跑一次：")
        for i, (medium, row, _, _) in enumerate(hits[:15]):
            print(f"  [{i}] ({medium}) {row.get('title')} {(row.get('timestamp') or '')[:10]}")
        # 仍为第一条建文件，方便快速开始
    medium, row, douban_id, subject = hits[0]
    title = (row.get("title") or "").strip()
    key = lib.row_key(medium, row)
    reviews = lib.load_reviews()
    if key in reviews:
        print("已存在：", reviews[key]["path"])
        return
    neodb_id = lib.extract_neodb_id(row.get("links", ""))
    tags = [t.strip() for t in (row.get("tags") or "").split("|") if t.strip()]
    os.makedirs(lib.REVIEWS_DIR, exist_ok=True)
    path = lib.unique_path(lib.REVIEWS_DIR, lib.review_filename(
        medium, title, douban_id, neodb_id, (row.get("timestamp") or "")[:10]))
    hint = ""
    if subject and subject.get("info"):
        info = subject["info"]
        for k in ("作者", "导演"):
            if info.get(k):
                hint = f"\n> {'、'.join(info[k][:3])}\n"
                break
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(lib.dump_review(
            title, medium, (row.get("status") or "complete").strip(),
            lib.CSV_TO_STARS.get((row.get("rating") or "").strip(), None),
            (row.get("timestamp") or "")[:10],
            lib.first_douban_url(row.get("links", "")),
            lib.first_neodb_url(row.get("links", "")),
            tags, hint + "写点什么…\n"))
    print(path)


if __name__ == "__main__":
    main()
