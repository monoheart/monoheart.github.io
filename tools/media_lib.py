# -*- coding: utf-8 -*-
"""书影音工具链共享库：CSV 解析、主键、评分换算、影评文件读写。"""
import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
REVIEWS_DIR = os.path.join(ROOT, "docs", "reviews")
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
