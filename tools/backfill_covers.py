# -*- coding: utf-8 -*-
"""慢速补封面：只处理本地缺失的，3 秒一条，绕开豆瓣图片限频。

用法：python tools/backfill_covers.py
跑完后重跑 python tools/build.py 生成页面即可。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_lib as lib
from build import ensure_cover, META_PATH, load_meta, save_meta


def main():
    import build
    subjects = lib.load_subjects()
    meta = load_meta()
    have = {f.split("-", 1)[1].rsplit(".", 1)[0]
            for f in os.listdir(lib.COVERS_DIR) if f.endswith(".jpg")} if os.path.isdir(lib.COVERS_DIR) else set()
    tasks = []
    for medium in lib.MEDIUMS:
        for row in lib.load_csv_rows(medium):
            d = lib.extract_douban_id(row.get("links", ""))
            if d and d not in have:
                tasks.append((medium, d, subjects.get(d)))
    print(f"missing={len(tasks)}", flush=True)
    ok = 0
    for i, (medium, d, subj) in enumerate(tasks):
        if not subj and medium in ("book", "movie", "tv"):
            # 本地库没有：先抓豆瓣页拿 og:image（自带 2s 限频）
            og = build.fetch_og_image(d, medium)
            if og:
                subj = {"cover_url": og, "info": {}, "url": ""}
        if subj and subj.get("cover_url"):
            got = ensure_cover(d, subj, meta, medium, fetch_missing=False)
            if got.startswith("covers/"):
                ok += 1
                print(f"[{i + 1}/{len(tasks)}] OK {medium} {d}", flush=True)
            else:
                print(f"[{i + 1}/{len(tasks)}] FAIL {medium} {d}", flush=True)
        else:
            print(f"[{i + 1}/{len(tasks)}] NO-SOURCE {medium} {d}", flush=True)
        save_meta(meta)
        time.sleep(3)
    print(f"done ok={ok}/{len(tasks)}")


if __name__ == "__main__":
    main()
