# -*- coding: utf-8 -*-
"""封面源迁移到 NeoDB：逐行抓 neodb.social 条目页 og:image，存到本地。

- 幂等：本地已有 neodb-*.jpg 则跳过；限频 2s/条。
- 用法：python tools/fetch_neodb_covers.py
- 跑完后执行 python tools/build.py 重建页面。
"""
import os
import re
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_lib as lib
from build import load_meta, save_meta

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Referer": "https://neodb.social/"}


def neodb_fname(neodb_id):
    return "neodb-" + neodb_id.replace("/", "-") + ".jpg"


def fetch_og(page_url, timeout=25):
    req = urllib.request.Request(page_url, headers=UA)
    html = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
    m = re.search(r'og:image"\s+content="([^"]+)"', html)
    return m.group(1) if m else ""


def download(url, dest, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if len(data) < 2000 or data[:1] == b"<":
        raise ValueError(f"bad image: {len(data)} bytes")
    with open(dest, "wb") as f:
        f.write(data)


def main():
    meta = load_meta()
    os.makedirs(lib.COVERS_DIR, exist_ok=True)
    tasks = []
    no_neodb = []
    for medium in lib.MEDIUMS:
        for row in lib.load_csv_rows(medium):
            neodb_url = lib.first_neodb_url(row.get("links", ""))
            if not neodb_url:
                no_neodb.append((medium, (row.get("title") or "")[:20]))
                continue
            neodb_id = lib.extract_neodb_id(row.get("links", ""))
            dest = os.path.join(lib.COVERS_DIR, neodb_fname(neodb_id))
            if os.path.exists(dest):
                continue
            tasks.append((medium, (row.get("title") or "")[:20], neodb_url, neodb_id, dest))
    print(f"total-missing={len(tasks)} no-neodb-url={len(no_neodb)}", flush=True)
    for m, t in no_neodb:
        print(f"  NO-NEODB {m} {t}", flush=True)
    ok = 0
    for i, (medium, title, page_url, neodb_id, dest) in enumerate(tasks):
        try:
            time.sleep(2)
            img = fetch_og(page_url)
            if not img:
                print(f"[{i + 1}/{len(tasks)}] NO-OG {medium} {title}", flush=True)
                continue
            download(img, dest)
            meta["neodb:" + neodb_id] = {"cover_url": img, "file": os.path.basename(dest)}
            ok += 1
            print(f"[{i + 1}/{len(tasks)}] OK {medium} {title}", flush=True)
        except Exception as e:
            print(f"[{i + 1}/{len(tasks)}] FAIL {medium} {title} {str(e)[:80]}", flush=True)
        if i % 10 == 9:
            save_meta(meta)
    save_meta(meta)
    print(f"done ok={ok}/{len(tasks)}", flush=True)


if __name__ == "__main__":
    main()
