# -*- coding: utf-8 -*-
"""一键构建：补封面(本地缓存) -> 重建 docs/media + docs/reviews/index.md。

用法：
  python tools/build.py                 # 增量构建（只下载缺失封面）
  python tools/build.py --fetch-missing # 对无封面条目尝试抓豆瓣 og:image（需网络，2s/条限频）
  python tools/build.py --deploy        # 构建成功后执行 mkdocs gh-deploy --force

数据源优先级：本地 subjects.ndjson > 已下载封面缓存 > 豆瓣直抓(仅补漏)。
标题/评分/短评永远以本地为准：有影评文件的用影评，否则用 CSV。
"""
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_lib as lib

META_PATH = os.path.join(lib.CACHE_DIR, "meta.json")
FAIL_PATH = os.path.join(lib.CACHE_DIR, "failures.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) monoheart-media/1.0",
      "Referer": "https://www.douban.com/"}


def load_meta():
    if os.path.exists(META_PATH):
        with open(META_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_meta(meta):
    os.makedirs(lib.CACHE_DIR, exist_ok=True)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


def download(url, dest, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if len(data) < 2000:  # 占位小图/错误页直接判失败
        raise ValueError(f"too small: {len(data)} bytes")
    with open(dest, "wb") as f:
        f.write(data)


def fetch_og_image(douban_id, medium, timeout=25):
    sections = {"book": ("book",), "movie": ("movie",), "tv": ("movie",), "game": ("book", "movie", "music")}.get(medium, ("book", "movie"))
    for sec in sections:
        try:
            time.sleep(2)
            req = urllib.request.Request(f"https://{sec}.douban.com/subject/{douban_id}/", headers=UA)
            html = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
            m = re.search(r'og:image"\s+content="([^"]+)"', html)
            if m:
                return m.group(1)
        except Exception:
            continue
    return ""


def ensure_cover(douban_id, subject, meta, medium="", fetch_missing=False):
    """返回相对 docs/media 的封面路径（covers/x.jpg）或远端 URL 或空。"""
    if not douban_id:
        return ""
    medium_hint = "x"
    fname = f"{medium_hint}-{douban_id}.jpg"
    local = os.path.join(lib.COVERS_DIR, fname)
    if os.path.exists(local):
        return f"covers/{fname}"
    cover_url = (subject or {}).get("cover_url", "")
    cands = []
    if cover_url:
        cands.append(cover_url.replace("/s/public/", "/m/public/"))
        cands.append(cover_url)
    for url in cands:
        try:
            os.makedirs(lib.COVERS_DIR, exist_ok=True)
            download(url, local)
            meta[douban_id] = {"cover_url": url, "file": fname}
            return f"covers/{fname}"
        except Exception:
            if os.path.exists(local):
                os.remove(local)
            continue
    if fetch_missing:
        og = ""
        if (subject or {}).get("url"):
            try:
                time.sleep(2)
                req = urllib.request.Request(subject["url"], headers=UA)
                html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
                m = re.search(r'og:image"\s+content="([^"]+)"', html)
                og = m.group(1) if m else ""
            except Exception as e:
                meta.setdefault("_errors", {})[douban_id] = str(e)[:120]
        if not og:
            og = fetch_og_image(douban_id, medium)
        if og:
            try:
                os.makedirs(lib.COVERS_DIR, exist_ok=True)
                download(og, local)
                meta[douban_id] = {"cover_url": og, "file": fname}
                return f"covers/{fname}"
            except Exception as e:
                if os.path.exists(local):
                    os.remove(local)
                meta.setdefault("_errors", {})[douban_id] = str(e)[:120]
    return cover_url  # 实在下不到就热链，表格照样能看


def cover_cell(cover):
    if not cover:
        return "—"
    if cover.startswith("covers/"):
        return f'<img src="{cover}" width="60" loading="lazy">'
    return f"[封面]({cover})"


def build(fetch_missing=False):
    subjects = lib.load_subjects()
    meta = load_meta()
    reviews = lib.load_reviews()
    failures = []
    all_rows = []
    for medium in lib.MEDIUMS:
        rows = lib.load_csv_rows(medium)
        for row in rows:
            row["_medium"] = medium
            row["_key"] = lib.row_key(medium, row)
            row["_douban"] = lib.extract_douban_id(row.get("links", ""))
            row["_subject"] = subjects.get(row["_douban"]) if row["_douban"] else None
            row["_cover"] = ensure_cover(row["_douban"], row["_subject"], meta, medium,
                                            fetch_missing and not (row["_subject"] or {}).get("cover_url"))
            if row["_douban"] and not row["_cover"]:
                failures.append({"medium": medium, "title": row.get("title"), "douban": row["_douban"]})
            all_rows.append(row)
    save_meta(meta)

    os.makedirs(lib.MEDIA_DIR, exist_ok=True)
    # --- 各类型页 ---
    for medium in lib.MEDIUMS:
        rows = sorted([r for r in all_rows if r["_medium"] == medium],
                      key=lambda r: (r.get("status") != "complete", r.get("timestamp", "")), reverse=False)
        # complete 在前、时间倒序
        done = sorted([r for r in rows if r.get("status") == "complete"],
                      key=lambda r: r.get("timestamp", ""), reverse=True)
        wish = sorted([r for r in rows if r.get("status") != "complete"],
                      key=lambda r: r.get("timestamp", ""), reverse=True)
        name = lib.MEDIUM_NAMES[medium]
        lines = [f"# {name}\n", f"共 {len(rows)}（看过 {len(done)} / 想看 {len(wish)}）\n"]
        for sec, items in (("看过", done), ("想看", wish)):
            lines.append(f"## {sec}（{len(items)}）\n")
            lines.append("| 封面 | 标题 | 作者/导演 | 评分 | 时间 | 短评 | 链接 |")
            lines.append("|---|---|---|---|---|---|---|")
            for r in items:
                rev = reviews.get(r["_key"])
                if rev:
                    fm, body = rev["fm"], rev["body"]
                    rating = lib.STARS_TO_CSV.get(fm.get("rating"), "") if fm.get("rating") is not None else ""
                    short = lib.excerpt(body) or "（全文见影评）"
                    rel = os.path.relpath(rev["path"], lib.MEDIA_DIR).replace(os.sep, "/")
                    short = f"{lib.md_cell(short)} [全文]({rel})"
                    stars = lib.stars_text(rating)
                else:
                    stars = lib.stars_text(r.get("rating", ""))
                    short = lib.md_cell(lib.excerpt(r.get("comment", "")))
                links = []
                if lib.first_neodb_url(r.get("links", "")):
                    links.append(f"[NeoDB]({lib.first_neodb_url(r.get('links', ''))})")
                if lib.first_douban_url(r.get("links", "")):
                    links.append(f"[豆瓣]({lib.first_douban_url(r.get('links', ''))})")
                title = (r.get("title") or "未命名").strip()
                lines.append("| " + " | ".join([
                    cover_cell(r["_cover"]), lib.md_cell(title),
                    lib.md_cell(lib.author_line(medium, r, r["_subject"])),
                    stars, (r.get("timestamp") or "")[:10], short, " ".join(links),
                ]) + " |")
            lines.append("")
        with open(os.path.join(lib.MEDIA_DIR, {"book": "books.md", "movie": "movies.md", "tv": "tv.md", "game": "games.md"}[medium]),
                  "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
    # --- 总览 ---
    total = len(all_rows)
    lines = ["# 书影音\n", f"共 {total} 条，有影评 {len(reviews)} 篇。\n",
             "| 类型 | 总数 | 页面 |", "|---|---|---|"]
    for medium, page in (("book", "books.md"), ("movie", "movies.md"), ("tv", "tv.md"), ("game", "games.md")):
        n = len([r for r in all_rows if r["_medium"] == medium])
        lines.append(f"| {lib.MEDIUM_NAMES[medium]} | {n} | [{lib.MEDIUM_NAMES[medium]}]({page}) |")
    lines += ["\n## 最近更新\n", "| 日期 | 类型 | 标题 | 评分 | 短评 |", "|---|---|---|---|---|"]
    for r in sorted(all_rows, key=lambda r: r.get("timestamp", ""), reverse=True)[:8]:
        rev = reviews.get(r["_key"])
        short = lib.md_cell(lib.excerpt(rev["body"])) if rev else lib.md_cell(lib.excerpt(r.get("comment", "")))
        lines.append(f"| {(r.get('timestamp') or '')[:10]} | {lib.MEDIUM_NAMES[r['_medium']]} | "
                     f"{lib.md_cell((r.get('title') or '未命名').strip())} | {lib.stars_text(r.get('rating', ''))} | {short} |")
    with open(os.path.join(lib.MEDIA_DIR, "index.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    # --- 影评索引 ---
    items = []
    for key, rev in reviews.items():
        fm = rev["fm"]
        rel = os.path.relpath(rev["path"], lib.REVIEWS_DIR).replace(os.sep, "/")
        items.append((fm.get("date", ""), fm.get("medium", ""), fm.get("title", ""), fm.get("rating"), rel, rev["body"]))
    items.sort(reverse=True)
    lines = ["# 影评\n", f"共 {len(items)} 篇，一部作品一篇，源文件在 `docs/reviews/`。\n",
             "| 日期 | 类型 | 标题 | 评分 | 摘要 |", "|---|---|---|---|---|"]
    for date, medium, title, stars, rel, body in items:
        csv_r = lib.STARS_TO_CSV.get(stars, "") if stars is not None else ""
        lines.append(f"| {date} | {lib.MEDIUM_NAMES.get(medium, medium)} | [{lib.md_cell(title)}]({lib.md_cell(rel)}) | "
                     f"{lib.stars_text(csv_r)} | {lib.md_cell(lib.excerpt(body))} |")
    os.makedirs(lib.REVIEWS_DIR, exist_ok=True)
    with open(os.path.join(lib.REVIEWS_DIR, "index.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    with open(FAIL_PATH, "w", encoding="utf-8") as f:
        json.dump({"missing_covers": failures}, f, ensure_ascii=False, indent=1)
    n_covers = len([f for f in os.listdir(lib.COVERS_DIR) if f.endswith(".jpg")] ) if os.path.isdir(lib.COVERS_DIR) else 0
    print(f"rows={total} reviews={len(reviews)} covers_local={n_covers} failures={len(failures)}")
    for fb in failures[:10]:
        print("  no-cover:", fb["medium"], fb["title"], fb["douban"])


def deploy():
    """发布流程（适配本仓库：master=源码，main=构建产物即 Pages 源）：
    1) 提交 master 源码并 push；2) mkdocs build；3) site/ 同步到 main 并 push。"""
    import datetime
    import shutil
    import subprocess
    import tempfile

    def run(*args):
        r = subprocess.run(args, cwd=lib.ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            print("$", " ".join(args))
            print(r.stdout[-2000:] if r.stdout else "")
            print(r.stderr[-2000:] if r.stderr else "")
            sys.exit(r.returncode)
        return r.stdout.strip()

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    status = run("git", "status", "--short")
    if status:
        run("git", "add", "-A")
        run("git", "commit", "-m", f"media update {stamp}")
    run("git", "push", "origin", "master")
    r = subprocess.run(["mkdocs", "build", "--strict"], cwd=lib.ROOT)
    if r.returncode != 0:
        sys.exit(r.returncode)
    tmp = tempfile.mkdtemp(prefix="pages-")
    try:
        run("git", "worktree", "add", tmp, "main")
        for name in os.listdir(tmp):
            if name == ".git":
                continue
            p = os.path.join(tmp, name)
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
        site = os.path.join(lib.ROOT, "site")
        for name in os.listdir(site):
            s, d = os.path.join(site, name), os.path.join(tmp, name)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
        st = subprocess.run(["git", "status", "--short"], cwd=tmp, capture_output=True, text=True).stdout.strip()
        if st:
            subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
            subprocess.run(["git", "commit", "-m", f"site {stamp}"], cwd=tmp, check=True)
            run("git", "push", "origin", "main")
            print("deployed to main")
        else:
            print("site unchanged, skip push")
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", tmp], cwd=lib.ROOT)
        subprocess.run(["git", "worktree", "prune"], cwd=lib.ROOT)


if __name__ == "__main__":
    fetch = "--fetch-missing" in sys.argv
    build(fetch_missing=fetch)
    if "--deploy" in sys.argv:
        deploy()
