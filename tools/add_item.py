# -*- coding: utf-8 -*-
"""新增一条书影音记录。

命令行用法：
  python tools/add_item.py <NeoDB链接> [--rating 1-5] [--comment "..."] [--date YYYY-MM-DD] [--wishlist] [--dry-run]

也可被 tools/app.py 作为函数调用：preview_entry() / add_entry()。
"""
import csv
import datetime
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_lib as lib
from build import fetch_neodb_meta_api, load_neodb_meta, save_neodb_meta

MEDIUM_BY_KIND = {"book": "book", "movie": "movie", "tv": "tv", "game": "game"}


def detect(url):
    """从 NeoDB 链接判断类型并取出完整 id（含 season/episode）。"""
    nid = lib.extract_neodb_id(url)
    if not nid:
        return None, None
    return MEDIUM_BY_KIND.get(nid.split("/")[0]), nid


def existing_ids(medium):
    ids = set()
    for row in lib.load_csv_rows(medium):
        nid = lib.extract_neodb_id(row.get("links", ""))
        if nid:
            ids.add(nid)
    return ids


def preview_entry(url):
    """抓取标题等，返回预览信息（不写文件）。"""
    medium, nid = detect(url)
    if not medium:
        raise ValueError("无法识别链接类型（需 book/movie/tv/game）")
    cache = load_neodb_meta()
    nd = cache.get(nid)
    if not nd:
        nd = fetch_neodb_meta_api(nid)
        cache[nid] = nd
    title = (nd.get("display_title") or nd.get("title") or "").strip()
    return {
        "medium": medium, "medium_name": lib.MEDIUM_NAMES[medium], "neodb_id": nid,
        "title": title, "year": nd.get("year") or nd.get("pub_year") or "",
        "duplicate": nid in existing_ids(medium), "nd": nd,
    }


def add_entry(url, rating=None, comment="", date=None, wishlist=False):
    """写入 data/<medium>.csv（并在有短评时建 reviews/ 影评文件）。返回结果 dict。"""
    medium, nid = detect(url)
    if not medium:
        raise ValueError("无法识别链接类型（需 book/movie/tv/game）")
    if nid in existing_ids(medium):
        raise ValueError("该条目已存在")

    cache = load_neodb_meta()
    nd = cache.get(nid)
    if not nd:
        nd = fetch_neodb_meta_api(nid)
        cache[nid] = nd
    title = (nd.get("display_title") or nd.get("title") or "").strip()

    date = date or datetime.date.today().isoformat()
    status = "wishlist" if wishlist else "complete"
    rating_val = lib.STARS_TO_CSV.get(rating, "") if rating else ""
    fields = [title, f"year:{nd['year']}" if nd.get("year") else "", url,
              f"{date}T00:00:00+00:00", status, rating_val, "", ""]

    with open(lib.CSV_FILES[medium], "a", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerow(fields)
    save_neodb_meta(cache)

    review_file = ""
    if comment:
        os.makedirs(lib.REVIEWS_DIR, exist_ok=True)
        path = lib.unique_path(lib.REVIEWS_DIR, lib.review_filename(medium, title, None, nid, date))
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(lib.dump_review(title, medium, status, rating, date, "", url, [], comment + "\n"))
        review_file = os.path.basename(path)

    return {"medium": medium, "title": title, "neodb_id": nid,
            "date": date, "status": status, "review_file": review_file}


def parse_args(argv):
    url = argv[0].strip()
    opts = {"rating": None, "comment": "", "date": None, "wishlist": False, "dry": False}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--rating":
            opts["rating"] = int(argv[i + 1]); i += 2
        elif a == "--comment":
            opts["comment"] = argv[i + 1]; i += 2
        elif a == "--date":
            opts["date"] = argv[i + 1]; i += 2
        elif a == "--wishlist":
            opts["wishlist"] = True; i += 1
        elif a == "--dry-run":
            opts["dry"] = True; i += 1
        else:
            print("未知参数:", a); sys.exit(1)
    return url, opts


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    url, opts = parse_args(sys.argv[1:])
    info = preview_entry(url)
    print(f"类型: {info['medium_name']}  标题: {info['title']}")
    if info["duplicate"]:
        print("该条目已存在（如需修改请用 reviews/ 影评文件或管理台）")
        sys.exit(1)
    if opts["dry"]:
        print("（dry-run，未写文件）")
        return
    res = add_entry(url, opts["rating"], opts["comment"], opts["date"], opts["wishlist"])
    print(f"已写入 data/{res['medium']}.csv")
    if res["review_file"]:
        print("已创建影评文件:", res["review_file"])
    print("下一步：双击 tools/publish.bat 发布。")


if __name__ == "__main__":
    main()
