"""首页文章卡片，以及按日期排序的侧边栏。"""

from __future__ import annotations

import html
import os
import posixpath
import re
from datetime import datetime

DATE_PATTERNS = (
    re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日(\d{1,2})点(\d{1,2})分"),
    re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[-_ ]|$)"),
    re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日"),
    re.compile(r"^(\d{4})(\d{2})(\d{2})(?:[-_ ]|$)"),
)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
BLOCK_RE = re.compile(r"(?:^|\n\s*\n)(.*?)(?=\n\s*\n|\Z)", re.DOTALL)


def _date_from_stem(stem: str) -> datetime | None:
    for pattern in DATE_PATTERNS:
        match = pattern.match(stem)
        if match:
            try:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4)) if match.lastindex and match.lastindex >= 4 else 0
                minute = int(match.group(5)) if match.lastindex and match.lastindex >= 5 else 0
                return datetime(year, month, day, hour, minute)
            except ValueError:
                return None
    return None


def _plain(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*_~`]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _title(text: str, stem: str) -> str:
    match = H1_RE.search(text)
    if match:
        return _plain(match.group(1))

    name = stem
    for pattern in DATE_PATTERNS:
        match = pattern.match(name)
        if match:
            name = name[match.end():]
            break
    name = name.strip(" -_")
    return name or stem


def _title_from_path(path: str, stem: str) -> str:
    try:
        with open(path, encoding="utf-8-sig") as handle:
            text = handle.read().lstrip("\ufeff")
    except OSError:
        return _title("", stem)
    return _title(text, stem)


def _iter_blocks(text: str):
    for match in BLOCK_RE.finditer(text):
        block = match.group(1).strip()
        if block:
            yield match.start(1), match.end(1), block


def _is_summary_block(block: str) -> bool:
    if not block:
        return False
    if block.startswith("#"):
        return False
    if block.startswith(("![", "<img", "```", "|", ">", "- ", "* ", "+ ")):
        return False
    if re.match(r"^\d+\.\s", block):
        return False
    return True


def _summary(text: str) -> str:
    text = FENCE_RE.sub("", text)
    blocks = [block for _, _, block in _iter_blocks(text)]
    h1_index = next(
        (index for index, block in enumerate(blocks) if re.match(r"^#\s+", block)),
        -1,
    )
    candidates = blocks[h1_index + 1:] if h1_index >= 0 else blocks

    for block in candidates:
        if _is_summary_block(block):
            return _plain(block)
    return ""


def _split_summary(markdown: str) -> tuple[str, str]:
    blocks = list(_iter_blocks(markdown))
    h1_index = next(
        (
            index
            for index, (_, _, block) in enumerate(blocks)
            if re.match(r"^#\s+", block)
        ),
        -1,
    )
    if h1_index < 0:
        return "", markdown

    for start, end, block in blocks[h1_index + 1:]:
        if not _is_summary_block(block):
            continue
        before = markdown[:start].rstrip()
        after = markdown[end:].lstrip()
        return block, before + "\n\n" + after

    return "", markdown


def _page_url(file) -> str:
    url = getattr(file, "url", "") or ""
    if url:
        return url
    dest = getattr(file, "dest_uri", "") or ""
    if dest.endswith("index.html"):
        return dest[: -len("index.html")]
    return dest


def _card(post: dict) -> str:
    url = html.escape(post["url"], quote=True)
    title = html.escape(post["title"], quote=True)
    summary = html.escape(post["summary"], quote=True)
    summary_html = f'<p class="post-card__summary">{summary}</p>' if summary else ""
    return (
        f'<a class="post-card" href="{url}">'
        f'<h2 class="post-card__title">{title}</h2>'
        f"{summary_html}"
        "</a>"
    )


def _article_paths(docs_dir: str):
    for root, dirs, filenames in os.walk(docs_dir):
        dirs[:] = [name for name in dirs if not name.startswith(".")]
        for name in filenames:
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, docs_dir).replace(os.sep, "/")
            if rel in {"index.md", "404.md"}:
                continue
            yield path, rel, posixpath.splitext(name)[0]


def on_config(config):
    docs_dir = config["docs_dir"]
    articles = [
        {
            "path": rel,
            "title": _title_from_path(path, stem),
            "date": _date_from_stem(stem),
        }
        for path, rel, stem in _article_paths(docs_dir)
    ]
    articles.sort(
        key=lambda article: (
            article["date"] or datetime.min,
            article["title"],
        ),
        reverse=True,
    )

    config["nav"] = [{"首页": "index.md"}] + [
        {article["title"]: article["path"]} for article in articles
    ]
    return config


def on_page_markdown(markdown, page, config, files):
    if page.file.src_path == "index.md":
        posts = []
        for file in files.documentation_pages():
            if file.src_path in {"index.md", "404.md"} or not file.src_path.endswith(".md"):
                continue

            path = os.path.join(config["docs_dir"], file.src_path)
            try:
                with open(path, encoding="utf-8-sig") as handle:
                    text = handle.read().lstrip("\ufeff")
            except OSError:
                continue

            stem = posixpath.splitext(posixpath.basename(file.src_path))[0]
            summary = _summary(text)
            posts.append(
                {
                    "url": _page_url(file),
                    "title": _title(text, stem),
                    "date": _date_from_stem(stem),
                    "summary": summary[:100] + ("…" if len(summary) > 100 else ""),
                }
            )

        posts.sort(
            key=lambda post: (post["date"] or datetime.min, post["title"]),
            reverse=True,
        )
        if not posts:
            return markdown

        cards = "\n".join(_card(post) for post in posts)
        return (
            markdown.rstrip()
            + '\n\n<div class="post-list">\n'
            + cards
            + "\n</div>\n"
        )

    if page.file.src_path == "404.md":
        return markdown

    _, body = _split_summary(markdown)
    return body
