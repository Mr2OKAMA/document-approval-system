"""起動中のデモサーバー(seed_demo投入済み)を巡回し、閲覧専用の静的HTMLを docs/demo/ に書き出す。

使い方: python -m scripts.build_static_demo http://127.0.0.1:8000
GitHub Pages(静的配信のみ)で見た目を確認するためのもの。ダミーデータ専用。
"""
import os
import posixpath
import re
import shutil
import sys
from urllib.parse import urldefrag, urlparse

import httpx

OUT = os.path.join("docs", "demo")
SKIP = ("/logout", "/export", "/password", "/login")
BANNER = ('<div style="background:#fff3cd;border-bottom:1px solid #e0c36a;padding:8px 16px;font-size:13px">'
          "これは見た目確認用の<b>静的デモ</b>です(ダミーデータ・操作は動作しません)。</div>")


def rel(from_file: str, to_path: str) -> str:
    return posixpath.relpath(to_path, posixpath.dirname(from_file)) or "."


def to_file(path: str) -> str:
    path = path.rstrip("/") or "/"
    if path.startswith("/static/"):
        return path.lstrip("/")
    return "index.html" if path == "/" else path.lstrip("/") + "/index.html"


def main(base: str) -> None:
    c = httpx.Client(base_url=base, follow_redirects=True)
    page = c.get("/login").text
    token = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    c.post("/login", data={"csrf": token, "login_id": "admin", "password": "demo-pass-1234"})
    shutil.rmtree(OUT, ignore_errors=True)
    seen, queue = set(), ["/", "/static/style.css"]
    while queue:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        r = c.get(path)
        if r.status_code != 200:
            continue
        dest = to_file(path)
        full = os.path.join(OUT, dest)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if "text/html" not in r.headers.get("content-type", ""):
            with open(full, "wb") as f:
                f.write(r.content)
            continue
        html = r.text

        def fix(m):
            url = urldefrag(m.group(2))[0]
            p = urlparse(url)
            if not url.startswith("/") or p.netloc:
                return m.group(0)
            if any(p.path.startswith(s) for s in SKIP) or p.path.endswith("/file"):
                return m.group(1) + "#" + m.group(3)
            if p.query:
                return m.group(1) + "#" + m.group(3)
            queue.append(p.path)
            return m.group(1) + rel(dest, to_file(p.path)) + m.group(3)

        html = re.sub(r'(href=")([^"]*)(")', fix, html)
        html = re.sub(r'(src=")([^"]*)(")', fix, html)
        html = re.sub(r'<form[^>]*action="[^"]*"', lambda m: re.sub(r'action="[^"]*"', 'action="#" onsubmit="return false"', m.group(0)), html)
        html = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + BANNER, html, count=1)
        with open(full, "w", encoding="utf-8") as f:
            f.write(html)
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print(len(seen), "files")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000")
