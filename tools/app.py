# -*- coding: utf-8 -*-
"""本地书影音/文章管理台（仅监听 127.0.0.1，无外部依赖）。

启动：python tools/app.py   （或双击 管理.bat）
浏览器会自动打开 http://127.0.0.1:8765
"""
import base64
import json
import mimetypes
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import media_lib as lib
import build_posts
import add_item

HOST = "127.0.0.1"
PORT = 8765
WEB_DIR = os.path.join(lib.ROOT, "tools", "web")

PUBLISH = {"running": False, "lines": [], "code": None, "label": ""}
PUBLISH_LOCK = threading.Lock()


# --------------------------------------------------------------------------
# 业务处理
# --------------------------------------------------------------------------

def api_media():
    return {"items": lib.list_entries()}


def api_media_add(data):
    url = (data.get("url") or "").strip()
    if not url:
        raise ValueError("请填写 NeoDB 链接")
    rating = data.get("rating")
    rating = int(rating) if rating else None
    return add_item.add_entry(url, rating, (data.get("comment") or "").strip(),
                              data.get("date") or None, bool(data.get("wishlist")))


def api_media_preview(data):
    url = (data.get("url") or "").strip()
    if not url:
        raise ValueError("请填写 NeoDB 链接")
    info = add_item.preview_entry(url)
    info.pop("nd", None)
    return info


def api_media_save(data):
    lib.save_entry(data["medium"], data["key"], data.get("title", ""),
                   data.get("status", "complete"),
                   int(data["rating"]) if data.get("rating") else None,
                   data.get("date", ""), data.get("tags") or [],
                   data.get("body", ""))
    return {"ok": True}


def api_media_delete(data):
    lib.delete_entry(data["medium"], data["key"])
    return {"ok": True}


def api_articles():
    posts = build_posts.load_posts()
    for p in posts:
        p["path"] = p.pop("file")
    return {"items": posts}


def api_article_get(name):
    path = safe_join(lib.POSTS_DIR, name)
    if not path or not os.path.exists(path):
        raise ValueError("文章不存在")
    with open(path, encoding="utf-8") as f:
        fm, body = lib.parse_frontmatter(f.read())
    return {"file": name, "frontmatter": fm, "body": body}


def api_article_save(data):
    title = (data.get("title") or "").strip() or "未命名"
    date = (data.get("date") or "").strip()[:10]
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
    fm = {"title": title, "date": date, "tags": tags}
    if data.get("summary"):
        fm["summary"] = data["summary"].strip()
    if data.get("draft"):
        fm["draft"] = True
    body = data.get("body") or ""
    os.makedirs(lib.POSTS_DIR, exist_ok=True)
    old = (data.get("file") or "").strip()
    if old:
        path = safe_join(lib.POSTS_DIR, old)
        if not path or not os.path.exists(path):
            raise ValueError("原文章不存在")
        if not date:
            fm["date"] = ""
    else:
        fname = f"{date or '0000-00-00'}-{lib.slug(title)}.md"
        path = lib.unique_path(lib.POSTS_DIR, fname)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(lib.dump_frontmatter(fm, body))
    build_posts.build_posts()
    return {"ok": True, "file": os.path.basename(path)}


def api_article_delete(data):
    path = safe_join(lib.POSTS_DIR, data.get("file", ""))
    if not path or not os.path.exists(path):
        raise ValueError("文章不存在")
    os.remove(path)
    build_posts.build_posts()
    return {"ok": True}


def api_upload_image(data):
    name = os.path.basename(data.get("filename") or "image.png")
    raw = data.get("data") or ""
    if "," in raw and raw.strip().startswith("data:"):
        raw = raw.split(",", 1)[1]
    blob = base64.b64decode(raw)
    if len(blob) > 20 * 1024 * 1024:
        raise ValueError("图片过大（>20MB）")
    os.makedirs(lib.POSTS_IMG_DIR, exist_ok=True)
    ext = os.path.splitext(name)[1] or ".png"
    stem = lib.slug(os.path.splitext(name)[0]) or "image"
    dest = lib.unique_path(lib.POSTS_IMG_DIR, f"{stem}{ext}")
    with open(dest, "wb") as f:
        f.write(blob)
    return {"ok": True, "url": "images/" + os.path.basename(dest),
            "markdown": f"![]({'images/' + os.path.basename(dest)})"}


def api_publish(data):
    with PUBLISH_LOCK:
        if PUBLISH["running"]:
            raise ValueError("正在发布中，请稍候")
        deploy = bool(data.get("deploy"))
        cmd = [sys.executable, os.path.join(lib.ROOT, "tools", "build.py")]
        if deploy:
            cmd.append("--deploy")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        PUBLISH.update({"running": True, "lines": [], "code": None,
                        "label": "发布" if deploy else "本地构建"})
        proc = subprocess.Popen(cmd, cwd=lib.ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", env=env)

        def reader():
            for line in proc.stdout:
                with PUBLISH_LOCK:
                    PUBLISH["lines"].append(line.rstrip("\n"))
            proc.wait()
            with PUBLISH_LOCK:
                PUBLISH["running"] = False
                PUBLISH["code"] = proc.returncode
                PUBLISH["lines"].append(f"[退出码 {proc.returncode}]")

        threading.Thread(target=reader, daemon=True).start()
    return {"ok": True, "label": PUBLISH["label"]}


def api_publish_log(since):
    with PUBLISH_LOCK:
        lines = PUBLISH["lines"][since:]
        return {"lines": lines, "next": since + len(lines),
                "running": PUBLISH["running"], "code": PUBLISH["code"],
                "label": PUBLISH["label"]}


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def safe_join(base, name):
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    return os.path.join(base, name)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path):
        if not path or not os.path.isfile(path):
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if path.endswith(".html"):
            ctype = "text/html; charset=utf-8"
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)
        try:
            if path == "/":
                return self._file(os.path.join(WEB_DIR, "index.html"))
            if path.startswith("/web/"):
                return self._file(safe_join(WEB_DIR, path[len("/web/"):]))
            if path.startswith("/covers/"):
                return self._file(safe_join(lib.COVERS_DIR, path[len("/covers/"):]))
            if path.startswith("/postimg/"):
                return self._file(safe_join(lib.POSTS_IMG_DIR, path[len("/postimg/"):]))
            if path == "/api/media":
                return self._json(api_media())
            if path == "/api/articles":
                return self._json(api_articles())
            if path == "/api/article":
                return self._json(api_article_get(qs.get("file", [""])[0]))
            if path == "/api/publish_log":
                return self._json(api_publish_log(int(qs.get("since", ["0"])[0])))
            self.send_error(404)
        except Exception as e:
            self._json({"error": str(e)}, 400)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self._read_json()
            if path == "/api/media/add":
                return self._json(api_media_add(data))
            if path == "/api/media/preview":
                return self._json(api_media_preview(data))
            if path == "/api/media/save":
                return self._json(api_media_save(data))
            if path == "/api/media/delete":
                return self._json(api_media_delete(data))
            if path == "/api/article/save":
                return self._json(api_article_save(data))
            if path == "/api/article/delete":
                return self._json(api_article_delete(data))
            if path == "/api/upload_image":
                return self._json(api_upload_image(data))
            if path == "/api/publish":
                return self._json(api_publish(data))
            self.send_error(404)
        except Exception as e:
            self._json({"error": str(e)}, 400)


def main():
    if not os.path.exists(os.path.join(WEB_DIR, "index.html")):
        print("缺少 tools/web/index.html")
        sys.exit(1)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"管理台已启动: {url}")
    print("（关闭此窗口即停止；数据只写在本机仓库内）")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
