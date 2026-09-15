# -*- coding: utf-8 -*-
"""一键构建：补封面(NeoDB 本地缓存) -> 重建 docs/media 表格页。

用法：
  python tools/build.py                 # 增量构建（缺封面自动抓 NeoDB，2s/条限频）
  python tools/build.py --deploy        # 构建成功后提交 master 并同步成品到 main 发布

封面源：全部来自 neodb.social 条目页 og:image，下载到 docs/media/covers/。
标题/评分/短评永远以本地为准：有影评文件的用影评全文，否则用 CSV。
"""
import json
import html
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_lib as lib

META_PATH = os.path.join(lib.CACHE_DIR, "meta.json")
FAIL_PATH = os.path.join(lib.CACHE_DIR, "failures.json")
UA_BASE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) monoheart-media/1.0"


def headers_for(url):
    if "neodb.social" in url:
        return {"User-Agent": UA_BASE, "Referer": "https://neodb.social/"}
    return {"User-Agent": UA_BASE, "Referer": "https://www.douban.com/"}


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
    req = urllib.request.Request(url, headers=headers_for(url))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if len(data) < 2000 or data[:1] == b"<":  # 占位小图/错误页直接判失败
        raise ValueError(f"bad image: {len(data)} bytes")
    with open(dest, "wb") as f:
        f.write(data)


def neodb_fname(neodb_id):
    return "neodb-" + neodb_id.replace("/", "-") + ".jpg"


def fetch_neodb_og(page_url, timeout=25):
    req = urllib.request.Request(page_url, headers=headers_for(page_url))
    html = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
    m = re.search(r'og:image"\s+content="([^"]+)"', html)
    return m.group(1) if m else ""


def try_download(url, dest, meta_key, meta):
    try:
        os.makedirs(lib.COVERS_DIR, exist_ok=True)
        download(url, dest)
        meta[meta_key] = {"cover_url": url, "file": os.path.basename(dest)}
        return True
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        meta.setdefault("_errors", {})[meta_key] = str(e)[:120]
        return False


def ensure_cover(row, subject, meta, medium="", fetch_missing=True):
    """返回相对 docs/media 的封面路径（covers/neodb-*.jpg）或旧豆瓣图兜底或空。"""
    # 1) NeoDB 本地（主源）
    neodb_id = lib.extract_neodb_id(row.get("links", ""))
    if neodb_id:
        fname = neodb_fname(neodb_id)
        local = os.path.join(lib.COVERS_DIR, fname)
        if os.path.exists(local):
            return f"covers/{fname}"
        key = "neodb:" + neodb_id
        if meta.get(key, {}).get("cover_url"):
            if try_download(meta[key]["cover_url"], local, key, meta):
                return f"covers/{fname}"
        if fetch_missing:
            page_url = lib.first_neodb_url(row.get("links", ""))
            if page_url:
                try:
                    time.sleep(2)
                    og = fetch_neodb_og(page_url)
                    if og and try_download(og, local, key, meta):
                        return f"covers/{fname}"
                except Exception as e:
                    meta.setdefault("_errors", {})[key] = str(e)[:120]
    return ""


def esc(text):
    return html.escape((text or "").strip(), quote=True)


def esc_multi(text):
    """转义并按换行拆成 <br>，供卡片正文全文展示。"""
    t = html.escape((text or "").strip(), quote=True)
    return t.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def cover_block(cover, prefix="../"):
    if cover and cover.startswith("covers/"):
        return f'<div class="media-cover"><img src="{prefix}{cover}" alt="" loading="lazy"></div>'
    return '<div class="media-cover media-cover--empty">无封面</div>'


def card_html(r, subject, medium, reviews):
    rev = reviews.get(r["_key"])
    if rev:
        fm, body = rev["fm"], rev["body"]
        rating = lib.STARS_TO_CSV.get(fm.get("rating"), "") if fm.get("rating") is not None else ""
        stars = lib.stars_text(rating)
        comment = esc_multi(body)
    else:
        stars = lib.stars_text(r.get("rating", ""))
        comment = esc_multi(r.get("comment", ""))
    if not comment:
        comment = '<span class="media-comment--empty">（暂无短评）</span>'
    author = lib.author_line(medium, r, subject) or "—"
    meta_bits = [stars]
    date = (r.get("timestamp") or "")[:10]
    if date:
        meta_bits.append(esc(date))
    links = []
    neodb = lib.first_neodb_url(r.get("links", ""))
    if neodb:
        links.append(f'<a href="{esc(neodb)}" target="_blank" rel="noopener">NeoDB</a>')
    douban = lib.first_douban_url(r.get("links", ""))
    if douban:
        links.append(f'<a href="{esc(douban)}" target="_blank" rel="noopener">豆瓣</a>')
    meta_line = " · ".join(meta_bits)
    if links:
        meta_line += " · " + " ".join(links)
    return (
        '<div class="media-card">\n'
        '<div class="media-head">\n'
        f'{cover_block(r["_cover"])}\n'
        '<div class="media-titles">\n'
        f'<div class="media-title">{esc(r.get("title") or "未命名")}</div>\n'
        f'<div class="media-author">{esc(author)}</div>\n'
        "</div>\n"
        "</div>\n"
        '<div class="media-body">\n'
        f'<div class="media-meta">{meta_line}</div>\n'
        f'<div class="media-comment">{comment}</div>\n'
        "</div>\n"
        "</div>"
    )


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
            row["_cover"] = ensure_cover(row, row["_subject"], meta, medium,
                                         fetch_missing=True)
            if not row["_cover"]:
                failures.append({"medium": medium, "title": row.get("title"),
                                 "neodb": lib.first_neodb_url(row.get("links", ""))})
            all_rows.append(row)
    save_meta(meta)

    os.makedirs(lib.MEDIA_DIR, exist_ok=True)
    # --- 各类型页（短评全文展示，无详情页）---
    for medium in lib.MEDIUMS:
        rows = [r for r in all_rows if r["_medium"] == medium]
        # 只展示看过的，时间倒序
        done = sorted([r for r in rows if r.get("status") == "complete"],
                      key=lambda r: r.get("timestamp", ""), reverse=True)
        name = lib.MEDIUM_NAMES[medium]
        lines = [f"# {name}\n", f"共 {len(done)} 条\n"]
        for r in done:
            lines.append(card_html(r, r["_subject"], medium, reviews))
            lines.append("")
        with open(os.path.join(lib.MEDIA_DIR, {"book": "books.md", "movie": "movies.md", "tv": "tv.md", "game": "games.md"}[medium]),
                  "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
    # --- 影评页不再生成详情页：reviews/ 仅为本地写作源 ---

    with open(FAIL_PATH, "w", encoding="utf-8") as f:
        json.dump({"missing_covers": failures}, f, ensure_ascii=False, indent=1)
    total = len(all_rows)
    n_covers = len([f for f in os.listdir(lib.COVERS_DIR) if f.endswith(".jpg")] ) if os.path.isdir(lib.COVERS_DIR) else 0
    print(f"rows={total} reviews={len(reviews)} covers_local={n_covers} failures={len(failures)}")
    for fb in failures[:10]:
        print("  no-cover:", fb["medium"], fb["title"], fb.get("neodb", ""))


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
