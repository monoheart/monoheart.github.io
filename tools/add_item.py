# -*- coding: utf-8 -*-
"""新增一条书影音记录（自动抓 NeoDB 标题并归类到对应 CSV，可同时建影评文件）。

用法：
  python tools/add_item.py <NeoDB链接> [选项]

选项：
  --rating 1-5     评分（1-5 星，可省略）
  --comment "..."  短评（会写入 reviews/ 影评文件）
  --date YYYY-MM-DD 标记日期（默认今天）
  --wishlist       标为"想看/想读"（默认"看过"）
  --dry-run        只演示，不写文件

示例：
  python tools/add_item.py https://neodb.social/movie/xxxx --rating 5 --comment "神作"
  python tools/add_item.py https://neodb.social/book/yyyy --wishlist
"""
import csv
import datetime
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_lib as lib
from build import fetch_neodb_meta_api, load_neodb_meta, save_neodb_meta

CSV_HEADER = ["title", "info", "links", "timestamp", "status", "rating", "comment", "tags"]
MEDIUM_BY_KIND = {"book": "book", "movie": "movie", "tv": "tv", "game": "game"}


def parse_args(argv):
    if not argv:
        print(__doc__)
        sys.exit(1)
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


def detect(url):
    """从 NeoDB 链接判断类型并取出完整 id（含 season/episode）。"""
    nid = lib.extract_neodb_id(url)
    if not nid:
        return None, None
    kind = nid.split("/")[0]
    medium = MEDIUM_BY_KIND.get(kind)
    return medium, nid


def existing_ids(medium):
    ids = set()
    for row in lib.load_csv_rows(medium):
        nid = lib.extract_neodb_id(row.get("links", ""))
        if nid:
            ids.add(nid)
    return ids


def main():
    url, opts = parse_args(sys.argv[1:])
    medium, nid = detect(url)
    if not medium:
        print("无法识别链接类型（需 book/movie/tv/game）。")
        sys.exit(1)
    # 抓标题（顺带把 API 元数据缓存好）
    cache = load_neodb_meta()
    nd = cache.get(nid)
    if not nd:
        try:
            nd = fetch_neodb_meta_api(nid)
            cache[nid] = nd
        except Exception as e:
            print("抓取 NeoDB 资料失败:", str(e)[:120])
            nd = {}
    title = (nd.get("display_title") or nd.get("title") or "").strip()
    if not title:
        title = input("没抓到标题，请手动输入标题: ").strip()
    if nid in existing_ids(medium):
        print(f"该条目已存在于 data/{medium}.csv：{title}（如需修改评分/短评，请编辑它的 reviews/ 影评文件）")
        sys.exit(1)

    date = opts["date"] or datetime.date.today().isoformat()
    status = "wishlist" if opts["wishlist"] else "complete"
    rating = lib.STARS_TO_CSV.get(opts["rating"], "") if opts["rating"] else ""
    info = ""
    if nd.get("year"):
        info = f"year:{nd['year']}"
    fields = [title, info, url, f"{date}T00:00:00+00:00", status, rating, "", ""]

    print("将新增：")
    print(f"  类型: {medium}")
    print(f"  标题: {title}")
    print(f"  链接: {url}")
    print(f"  状态: {status}  评分: {opts['rating'] or '无'}  日期: {date}")
    if opts["comment"]:
        print(f"  短评: {opts['comment'][:40]}")

    if opts["dry"]:
        print("（dry-run，未写文件）")
        return

    csv_path = lib.CSV_FILES[medium]
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(fields)
    save_neodb_meta(cache)
    print(f"已写入 {os.path.relpath(csv_path, lib.ROOT)}")

    if opts["comment"]:
        os.makedirs(lib.REVIEWS_DIR, exist_ok=True)
        path = lib.unique_path(lib.REVIEWS_DIR, lib.review_filename(medium, title, None, nid, date))
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(lib.dump_review(title, medium, status, opts["rating"], date,
                                    "", url, [], opts["comment"] + "\n"))
        print("已创建影评文件:", os.path.relpath(path, lib.ROOT))
    print("\n下一步：双击 tools/publish.bat 发布。想写长评就编辑 reviews/ 里对应文件。")


if __name__ == "__main__":
    main()
