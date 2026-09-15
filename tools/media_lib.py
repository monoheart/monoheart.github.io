# -*- coding: utf-8 -*-
"""书影音工具链共享库：CSV 解析、主键、评分换算、影评文件读写。"""
import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
REVIEWS_DIR = os.path.join(ROOT, "reviews")  # 影评源（一部作品一篇），不在 docs/ 下，不生成详情页
MEDIA_DIR = os.path.join(ROOT, "docs", "media")
COVERS_DIR = os.path.join(MEDIA_DIR, "covers")
CACHE_DIR = os.path.join(ROOT, ".cache")

MEDIUMS = ("book", "movie", "tv", "game")
CSV_FILES = {
    "book": os.path.join(DATA_DIR, "books.csv"),
    "movie": os.path.join(DATA_DIR, "movies.csv"),
    "tv": os.path.join(DATA_DIR, "tv.csv"),
    "game": os.path.join(DATA_DIR, "games.csv"),
}
MEDIUM_NAMES = {"book": "书", "movie": "影", "tv": "剧", "game": "游戏"}

RE_DOUBAN = re.compile(r"(?:book|movie|music)\.douban\.com/subject/(\d+)")
RE_NEODB = re.compile(r"neodb\.social/(book|movie|tv|game|music|podcast)(?:/(season|episode))?/([A-Za-z0-9]+)")

# CSV 十分制 <-> 影评五星制
CSV_TO_STARS = {"10": 5, "8": 4, "6": 3, "4": 2, "2": 1, "": None}
STARS_TO_CSV = {5: "10", 4: "8", 3: "6", 2: "4", 1: "2", None: ""}


def stars_text(csv_rating):
    n = CSV_TO_STARS.get((csv_rating or "").strip(), None)
    if n is None:
        return "未评分"
    return "★" * n + "☆" * (5 - n)


def load_csv_rows(medium):
    with open(CSV_FILES[medium], encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def extract_douban_id(links):
    m = RE_DOUBAN.search(links or "")
    return m.group(1) if m else None


def extract_neodb_id(links):
    """返回如 book/xxx / tv/season/xxx 的完整 key，保证季/集不与剧集撞车。"""
    m = RE_NEODB.search(links or "")
    if not m:
        return None
    kind, sub, ident = m.group(1), m.group(2), m.group(3)
    return f"{kind}/{sub}/{ident}" if sub else f"{kind}/{ident}"


def row_key(medium, row):
    douban = extract_douban_id(row.get("links", ""))
    if douban:
        return f"{medium}:douban:{douban}"
    neodb = extract_neodb_id(row.get("links", ""))
    if neodb:
        return f"{medium}:neodb:{neodb}"
    return f"{medium}:title:{(row.get('title') or '').strip()}:{row.get('timestamp', '')[:10]}"


def first_neodb_url(links):
    for tok in (links or "").split():
        if "neodb.social" in tok:
            return tok.strip()
    return ""


def first_douban_url(links):
    for tok in (links or "").split():
        if "douban.com/subject/" in tok:
            return tok.strip()
    return ""


def load_subjects():
    """douban数字ID -> {title, cover_url, info, url}，本地离线封面库。"""
    path = os.path.join(DATA_DIR, "subjects.ndjson")
    index = {}
    if not os.path.exists(path):
        return index
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            url = obj.get("url", "")
            m = re.search(r"/subject/(\d+)", url)
            if not m:
                continue
            revs = obj.get("revisions") or []
            fields = revs[0].get("fields", {}) if revs else {}
            index[m.group(1)] = {
                "title": fields.get("title", ""),
                "cover_url": fields.get("cover_url", ""),
                "info": fields.get("info", {}) or {},
                "url": url,
            }
    return index


def author_line(medium, row, subject):
    """作者/导演一行：优先 subjects.info，其次 CSV info 字段。"""
    info = (subject or {}).get("info", {}) or {}
    for k in ("作者", "导演", "艺术家"):
        if info.get(k):
            vals = info[k][:3]
            more = "等" if len(info[k]) > 3 else ""
            return "、".join(vals) + more
    raw = (row.get("info") or "").strip()
    m = re.search(r"author:(.+?)(?: pub_year|$)", raw)
    if m:
        return m.group(1).strip()[:30]
    m = re.search(r"director:(.+?)(?: season_number|$)", raw)
    if m:
        return m.group(1).strip()[:30]
    return ""


def slugify(title, limit=28):
    s = re.sub(r"[\\/:*?\"<>|\s]+", "-", (title or "").strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:limit] or "未命名"


def review_filename(medium, title, douban_id, neodb_id, date):
    base = f"{medium}-{douban_id}" if douban_id else (
        f"{medium}-{neodb_id.replace('/', '-')}" if neodb_id else f"{medium}-{date}")
    return f"{base}-{slugify(title)}.md"


def unique_path(directory, filename):
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(filename)
    i = 2
    while True:
        cand = os.path.join(directory, f"{stem}-{i}{ext}")
        if not os.path.exists(cand):
            return cand
        i += 1


# --- 极简 frontmatter 读写（只支持本工具链的固定字段，不引 pyyaml） ---

def _q(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def dump_review(title, medium, status, stars, date, douban_url, neodb_url, tags, body):
    tags = [t for t in (tags or []) if t]
    fm = [
        "---",
        f"title: {_q(title)}",
        f"medium: {medium}",
        f"status: {status or 'complete'}",
        f"rating: {stars if stars else ''}",
        f"date: {_q(date or '')}",
        f"douban: {_q(douban_url or '')}",
        f"neodb: {_q(neodb_url or '')}",
        "tags: [" + ", ".join(_q(t) for t in tags) + "]",
        "---",
        "",
    ]
    return "\n".join(fm) + (body or "").rstrip() + "\n"


def parse_review(text):
    """返回 (frontmatter dict, body)。无 frontmatter 则返回 ({}, 全文)。"""
    fm = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            raw = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            for line in raw.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip()
                if len(v) >= 2 and v.startswith('"') and v.endswith('"'):
                    v = v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
                fm[k] = v
            tags = fm.get("tags", "")
            if tags.startswith("["):
                items = []
                for part in tags.strip("[]").split(","):
                    part = part.strip().strip('"').strip("'")
                    if part:
                        items.append(part)
                fm["tags"] = items
            else:
                fm["tags"] = []
            try:
                fm["rating"] = int(str(fm.get("rating", "")).strip()) if str(fm.get("rating", "")).strip() else None
            except ValueError:
                fm["rating"] = None
    return fm, body


def load_reviews():
    """key -> {fm, body, path}，key 规则与 row_key 对齐。"""
    reviews = {}
    if not os.path.isdir(REVIEWS_DIR):
        return reviews
    for name in os.listdir(REVIEWS_DIR):
        if not name.endswith(".md") or name == "index.md":
            continue
        path = os.path.join(REVIEWS_DIR, name)
        with open(path, encoding="utf-8") as f:
            fm, body = parse_review(f.read())
        medium = fm.get("medium", "")
        douban_id = None
        m = re.search(r"/subject/(\d+)", fm.get("douban", ""))
        if m:
            douban_id = m.group(1)
        neodb_key = None
        m2 = RE_NEODB.search(fm.get("neodb", ""))
        if m2:
            neodb_key = f"{m2.group(1)}/{m2.group(3)}" if not m2.group(2) else f"{m2.group(1)}/{m2.group(2)}/{m2.group(3)}"
        if douban_id:
            key = f"{medium}:douban:{douban_id}"
        elif neodb_key:
            key = f"{medium}:neodb:{neodb_key}"
        else:
            key = f"{medium}:title:{fm.get('title', '')}:{fm.get('date', '')}"
        reviews[key] = {"fm": fm, "body": body, "path": path}
    return reviews


def md_cell(text):
    return (text or "").replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>").strip()


def excerpt(body, limit=60):
    for line in (body or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        line = re.sub(r"!\[.*?\]\(.*?\)", "", line).strip()
        if line:
            return line[:limit] + ("…" if len(line) > limit else "")
    return ""


# ---------------------------------------------------------------------------
# 通用 frontmatter（文章 / 影评共用）
# ---------------------------------------------------------------------------

POSTS_DIR = os.path.join(ROOT, "docs", "posts")
POSTS_IMG_DIR = os.path.join(POSTS_DIR, "images")


def parse_frontmatter(text):
    """通用解析：返回 (dict, body)。支持字符串/数组/布尔。"""
    text = text or ""
    fm = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            raw = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            for line in raw.splitlines():
                if ":" not in line or line.lstrip().startswith("#"):
                    continue
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip()
                if v.startswith("[") and v.endswith("]"):
                    items = []
                    for part in v.strip("[]").split(","):
                        part = part.strip().strip('"').strip("'")
                        if part:
                            items.append(part)
                    fm[k] = items
                elif v.lower() in ("true", "false"):
                    fm[k] = v.lower() == "true"
                else:
                    if len(v) >= 2 and v.startswith('"') and v.endswith('"'):
                        v = v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
                    fm[k] = v
    return fm, body


def dump_frontmatter(fm, body):
    def q(x):
        return '"' + str(x).replace("\\", "\\\\").replace('"', '\\"') + '"'

    order = ["title", "date", "tags", "summary", "cover", "draft"]
    keys = [k for k in order if k in fm] + [k for k in fm if k not in order]
    lines = ["---"]
    for k in keys:
        v = fm[k]
        if k == "tags":
            lines.append("tags: [" + ", ".join(q(t) for t in (v or [])) + "]")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            lines.append(f"{k}: {q(v)}")
    lines += ["---", ""]
    return "\n".join(lines) + (body or "").rstrip() + "\n"


def slug(text, limit=40):
    s = re.sub(r"[\\/:*?\"<>|\s]+", "-", (text or "").strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:limit] or "untitled"


# ---------------------------------------------------------------------------
# 书影音条目：列出 / 保存 / 删除（CSV 目录 + reviews/ 影评文件）
# ---------------------------------------------------------------------------

def load_csv_full(medium):
    """返回 (fieldnames, rows)。"""
    with open(CSV_FILES[medium], encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv_rows(medium, fieldnames, rows):
    with open(CSV_FILES[medium], "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def find_row(medium, key):
    for r in load_csv_rows(medium):
        if row_key(medium, r) == key:
            return r
    return None


def list_entries():
    """所有条目，合并 CSV 与影评文件，供管理台使用。"""
    from build import load_neodb_meta, creator_text
    subjects = load_subjects()
    reviews = load_reviews()
    ndcache = load_neodb_meta()
    out = []
    for medium in MEDIUMS:
        for row in load_csv_rows(medium):
            key = row_key(medium, row)
            rev = reviews.get(key)
            fm = rev["fm"] if rev else {}
            rating = fm.get("rating") if fm.get("rating") is not None else CSV_TO_STARS.get((row.get("rating") or "").strip())
            status = (fm.get("status") or row.get("status") or "complete").strip() or "complete"
            date = (fm.get("date") or (row.get("timestamp") or "")[:10])
            body = rev["body"].strip() if rev else (row.get("comment") or "").strip()
            tags = fm.get("tags") if fm.get("tags") else [t.strip() for t in (row.get("tags") or "").split("|") if t.strip()]
            nid = extract_neodb_id(row.get("links", ""))
            did = extract_douban_id(row.get("links", ""))
            cover = ""
            if nid:
                fn = "neodb-" + nid.replace("/", "-") + ".jpg"
                if os.path.exists(os.path.join(COVERS_DIR, fn)):
                    cover = fn
            nd = ndcache.get(nid, {}) if nid else {}
            role, cname = creator_text(medium, row, subjects.get(did) if did else None, nd)
            out.append({
                "medium": medium, "medium_name": MEDIUM_NAMES[medium], "key": key,
                "title": (row.get("title") or "").strip(), "author": cname, "author_role": role,
                "status": status, "rating": rating, "date": date, "tags": tags, "body": body,
                "neodb": first_neodb_url(row.get("links", "")),
                "douban": first_douban_url(row.get("links", "")),
                "cover": cover, "has_review": bool(rev),
                "review_file": os.path.basename(rev["path"]) if rev else "",
            })
    return out


def save_entry(medium, key, title, status, rating, date, tags, body):
    """更新条目：CSV 的 title/status/rating/comment + reviews/ 影评文件。"""
    fieldnames, rows = load_csv_full(medium)
    target = None
    for r in rows:
        if row_key(medium, r) == key:
            target = r
            break
    if target is None:
        raise ValueError("找不到条目: " + key)
    target["title"] = title
    target["status"] = status
    target["rating"] = STARS_TO_CSV.get(rating, "") if rating else ""
    target["comment"] = body if not body else target.get("comment", "")
    write_csv_rows(medium, fieldnames, rows)

    reviews = load_reviews()
    rev = reviews.get(key)
    nid = extract_neodb_id(target.get("links", ""))
    did = extract_douban_id(target.get("links", ""))
    if rev:
        path = rev["path"]
    else:
        os.makedirs(REVIEWS_DIR, exist_ok=True)
        fname = review_filename(medium, title, did, nid, date)
        path = unique_path(REVIEWS_DIR, fname)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dump_review(title, medium, status, rating, date,
                            first_douban_url(target.get("links", "")),
                            first_neodb_url(target.get("links", "")), tags, body))
    return os.path.basename(path)


def delete_entry(medium, key):
    fieldnames, rows = load_csv_full(medium)
    keep = [r for r in rows if row_key(medium, r) != key]
    if len(keep) == len(rows):
        raise ValueError("找不到条目: " + key)
    removed = [r for r in rows if row_key(medium, r) == key][0]
    write_csv_rows(medium, fieldnames, keep)
    nid = extract_neodb_id(removed.get("links", ""))
    # 影评文件
    reviews = load_reviews()
    rev = reviews.get(key)
    if rev and os.path.exists(rev["path"]):
        os.remove(rev["path"])
    # 封面 + 元数据缓存（仅当没有其它行共用该 neodb id）
    if nid:
        still = any(extract_neodb_id(r.get("links", "")) == nid for r in keep)
        if not still:
            cover = os.path.join(COVERS_DIR, "neodb-" + nid.replace("/", "-") + ".jpg")
            if os.path.exists(cover):
                os.remove(cover)
            try:
                from build import load_neodb_meta, save_neodb_meta
                cache = load_neodb_meta()
                if nid in cache:
                    del cache[nid]
                    save_neodb_meta(cache)
            except Exception:
                pass
    return True
