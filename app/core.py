import os
import secrets
import sqlite3
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from . import db

ROLES = {
    "admin": "管理者",
    "author": "申請者",
    "reviewer": "確認者",
    "approver": "承認者",
    "viewer": "閲覧者",
}
STAFF = ("admin", "author", "reviewer", "approver")
MIN_PASSWORD = 8
MAX_UPLOAD = 20 * 1024 * 1024

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["today"] = lambda: db.today().isoformat()


def get_conn():
    conn = db.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class Redirect(Exception):
    def __init__(self, url: str):
        self.url = url


def current_user(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    uid = request.session.get("uid")
    user = conn.execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone() if uid else None
    if not user:
        request.session.clear()
        raise Redirect("/login")
    if user["must_change_pw"] and request.url.path not in ("/password", "/logout"):
        raise Redirect("/password")
    return user


def require(*roles: str):
    def dep(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "権限がありません")
        return user

    return dep


def csrf_token(request: Request) -> str:
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_hex(16)
    return request.session["csrf"]


async def check_csrf(request: Request):
    if request.method == "POST":
        form = await request.form()
        sent = str(form.get("csrf", ""))
        if not sent or not secrets.compare_digest(sent, request.session.get("csrf", "")):
            raise HTTPException(403, "不正なリクエストです")


def render(request: Request, name: str, user=None, **ctx):
    ctx.update(user=user, roles=ROLES, csrf=csrf_token(request), msg=request.session.pop("msg", None))
    return templates.TemplateResponse(request, name, ctx)


def flash(request: Request, msg: str):
    request.session["msg"] = msg


def back(request: Request, url: str, msg: str | None = None):
    if msg:
        flash(request, msg)
    return RedirectResponse(url, status_code=303)


def secret_key() -> str:
    key = os.environ.get("DOCMGMT_SECRET")
    if not key:
        if os.environ.get("DOCMGMT_DEV") == "1":
            return "dev-only-not-for-production"
        raise RuntimeError("環境変数 DOCMGMT_SECRET を設定してください(開発時のみ DOCMGMT_DEV=1 で省略可)")
    return key
