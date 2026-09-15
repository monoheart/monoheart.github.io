# -*- coding: utf-8 -*-
"""扫描 docs/posts/*.md，生成文章列表页 docs/posts/index.md。

用法：python tools/build_posts.py
- 每篇文章带 frontmatter：title / date / tags / summary / cover / draft
- draft: true 的文章不出现在列表页
- 由 tools/build.py 在构建时自动调用
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_lib as lib


def load_posts():
    posts = []
    if not os.path.isdir(lib.POSTS_DIR):
        return posts
    for name in os.listdir(lib.POSTS_DIR):
        if not name.endswith(".md") or name == "index.md":
            continue
        path = os.path.join(lib.POSTS_DIR, name)
        with open(path, encoding="utf-8") as f:
            fm, body = lib.parse_frontmatter(f.read())
        posts.append({
            "file": name,
            "title": fm.get("title") or os.path.splitext(name)[0],
            "date": str(fm.get("date") or ""),
            "tags": fm.get("tags") or [],
            "summary": fm.get("summary") or lib.excerpt(body, 90),
            "draft": bool(fm.get("draft")),
        })
    posts.sort(key=lambda p: (p["date"], p["file"]), reverse=True)
    return posts


def build_posts():
    os.makedirs(lib.POSTS_DIR, exist_ok=True)
    posts = [p for p in load_posts() if not p["draft"]]
    lines = ["# 文章\n", f"共 {len(posts)} 篇。\n"]
    if not posts:
        lines.append("（还没有文章）\n")
    for p in posts:
        date = p["date"][:10]
        tags = " ".join(f"`{t}`" for t in p["tags"]) if p["tags"] else ""
        lines.append(f"## [{p['title']}]({p['file']})\n")
        meta = " · ".join(x for x in [date, tags] if x)
        if meta:
            lines.append(meta + "\n")
        if p["summary"]:
            lines.append(p["summary"] + "\n")
    with open(os.path.join(lib.POSTS_DIR, "index.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return len(posts)


if __name__ == "__main__":
    n = build_posts()
    print(f"posts={n}")
