# -*- coding: utf-8 -*-
"""批量抓取 NeoDB 条目 API 元数据到 .cache/neodb_meta.json。

用法：python tools/fetch_neodb_meta.py [--refresh]
- 幂等：已有缓存则跳过；--refresh 强制全部重抓。
- 之后 build.py 会自动为新增条目补抓，一般无需手动运行。
"""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_lib as lib
from build import load_neodb_meta, save_neodb_meta, fetch_neodb_meta_api


def main():
    refresh = "--refresh" in sys.argv
    cache = load_neodb_meta()
    pairs = {}
    for medium in lib.MEDIUMS:
        for row in lib.load_csv_rows(medium):
            nid = lib.extract_neodb_id(row.get("links", ""))
            if nid:
                pairs[nid] = (row.get("title") or "")[:24]
    todo = [nid for nid in pairs if refresh or nid not in cache]
    print(f"total={len(pairs)} cached={len(pairs) - len(todo)} todo={len(todo)}", flush=True)
    ok = fail = 0
    for i, nid in enumerate(todo):
        try:
            time.sleep(0.5)
            cache[nid] = fetch_neodb_meta_api(nid)
            ok += 1
        except Exception as e:
            fail += 1
            print(f"[{i + 1}/{len(todo)}] FAIL {nid} {str(e)[:80]}", flush=True)
        if i % 10 == 9:
            save_neodb_meta(cache)
    save_neodb_meta(cache)
    print(f"done ok={ok} fail={fail} cache_size={len(cache)}", flush=True)


if __name__ == "__main__":
    main()
