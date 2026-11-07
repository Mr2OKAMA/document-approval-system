import hashlib
import os
import secrets
import sqlite3
import uuid
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import db

ROLES = {"admin": "管理者", "author": "申請者", "approver": "承認者", "viewer": "閲覧者"}
MAX_UPLOAD = 20 * 1024 * 1024
MIN_PASSWORD = 8

app = FastAPI(title="文書管理システム")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("DOCMGMT_SECRET", "dev-only-change-me"),
    same_site="lax",
    https_only=os.environ.get("DOCMGMT_HTTPS", "0") == "1",
    max_age=60 * 60 * 8,
)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
db.init_db()


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


@app.exception_handler(Redirect)
async def _redirect(_: Request, exc: Redirect):
    return RedirectResponse(exc.url, status_code=303)


def current_user(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    uid = request.session.get("uid")
    user = conn.execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone() if uid else None
    if not user:
        request.session.clear()
        raise Redirect("/login")
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


# ---------- 認証 ----------
@app.get("/login")
def login_form(request: Request):
    return render(request, "login.html")


@app.post("/login", dependencies=[Depends(check_csrf)])
def login(request: Request, login_id: str = Form(...), password: str = Form(...), conn=Depends(get_conn)):
    user = conn.execute("SELECT * FROM users WHERE login_id=? AND active=1", (login_id,)).fetchone()
    if not user or not db.verify_password(password, user["password_hash"]):
        db.log(conn, login_id, "ログイン失敗", "-")
        conn.commit()
        flash(request, "IDまたはパスワードが違います")
        return RedirectResponse("/login", status_code=303)
    request.session.clear()
    request.session["uid"] = user["id"]
    db.log(conn, login_id, "ログイン", "-")
    return RedirectResponse("/", status_code=303)


@app.post("/logout", dependencies=[Depends(check_csrf)])
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/password")
def password_form(request: Request, user=Depends(current_user)):
    return render(request, "password.html", user)


@app.post("/password", dependencies=[Depends(check_csrf)])
def password_change(
    request: Request,
    current: str = Form(...),
    new: str = Form(...),
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    if not db.verify_password(current, user["password_hash"]):
        flash(request, "現在のパスワードが違います")
    elif len(new) < MIN_PASSWORD:
        flash(request, f"パスワードは{MIN_PASSWORD}文字以上にしてください")
    else:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (db.hash_password(new), user["id"]))
        db.log(conn, user["login_id"], "パスワード変更", user["login_id"])
        flash(request, "パスワードを変更しました")
    return RedirectResponse("/password", status_code=303)


# ---------- 文書一覧・閲覧 ----------
@app.get("/")
def index(request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    docs = conn.execute(
        """SELECT d.doc_no, d.title, r.id AS rev_id, r.rev_no, r.effective_date, r.decided_at
           FROM documents d JOIN revisions r ON r.document_id=d.id
           WHERE r.status='承認済' AND r.rev_no=(
             SELECT MAX(rev_no) FROM revisions WHERE document_id=d.id AND status='承認済')
           ORDER BY d.doc_no"""
    ).fetchall()
    pending = 0
    if user["role"] in ("admin", "approver"):
        pending = conn.execute("SELECT COUNT(*) FROM revisions WHERE status='申請中'").fetchone()[0]
    return render(request, "index.html", user, docs=docs, pending=pending)


@app.get("/documents/{doc_no}")
def document_detail(doc_no: str, request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    doc = conn.execute("SELECT * FROM documents WHERE doc_no=?", (doc_no,)).fetchone()
    if not doc:
        raise HTTPException(404)
    revs = conn.execute(
        """SELECT r.*, s.name AS submitter, a.name AS decider FROM revisions r
           JOIN users s ON s.id=r.submitted_by LEFT JOIN users a ON a.id=r.decided_by
           WHERE r.document_id=? ORDER BY r.rev_no DESC""",
        (doc["id"],),
    ).fetchall()
    if user["role"] == "viewer":
        revs = [r for r in revs if r["status"] == "承認済"]
    return render(request, "document.html", user, doc=doc, revs=revs)


@app.get("/revisions/{rev_id}/file")
def download(rev_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    r = conn.execute("SELECT * FROM revisions WHERE id=?", (rev_id,)).fetchone()
    if not r or (user["role"] == "viewer" and r["status"] != "承認済"):
        raise HTTPException(404)
    path = db.DATA_DIR / "files" / r["file_path"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != r["sha256"]:
        db.log(conn, user["login_id"], "改ざん検知", f"rev:{rev_id}")
        conn.commit()
        raise HTTPException(500, "ファイルのハッシュが一致しません(改ざんの可能性)")
    db.log(conn, user["login_id"], "閲覧", f"rev:{rev_id}")
    return FileResponse(path, media_type="application/pdf", filename=r["file_name"], content_disposition_type="inline")


# ---------- 申請 ----------
@app.get("/submit")
def submit_form(request: Request, user=Depends(require("admin", "author")), conn=Depends(get_conn)):
    docs = conn.execute("SELECT doc_no, title FROM documents ORDER BY doc_no").fetchall()
    return render(request, "submit.html", user, docs=docs, today=date.today().isoformat())


@app.post("/submit", dependencies=[Depends(check_csrf)])
def submit(
    request: Request,
    doc_no: str = Form(...),
    title: str = Form(...),
    change_summary: str = Form(...),
    change_reason: str = Form(...),
    effective_date: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(require("admin", "author")),
    conn=Depends(get_conn),
):
    doc_no, title = doc_no.strip(), title.strip()
    data = file.file.read(MAX_UPLOAD + 1)
    error = None
    if not (doc_no and title and change_summary.strip() and change_reason.strip()):
        error = "すべての項目を入力してください(改訂理由は必須です)"
    elif len(data) > MAX_UPLOAD or not data.startswith(b"%PDF"):
        error = "PDFファイル(20MB以下)を添付してください"
    else:
        try:
            date.fromisoformat(effective_date)
        except ValueError:
            error = "適用開始日の形式が正しくありません"
    doc = conn.execute("SELECT * FROM documents WHERE doc_no=?", (doc_no,)).fetchone()
    if not error and doc:
        if conn.execute("SELECT 1 FROM revisions WHERE document_id=? AND status='申請中'", (doc["id"],)).fetchone():
            error = "この文書には承認待ちの申請があります"
    if error:
        flash(request, error)
        return RedirectResponse("/submit", status_code=303)

    if not doc:
        cur = conn.execute("INSERT INTO documents(doc_no,title) VALUES(?,?)", (doc_no, title))
        doc_id, rev_no = cur.lastrowid, 0
    else:
        doc_id = doc["id"]
        rev_no = conn.execute("SELECT MAX(rev_no) FROM revisions WHERE document_id=?", (doc_id,)).fetchone()[0] + 1
    stored = f"{uuid.uuid4().hex}.pdf"
    (db.DATA_DIR / "files" / stored).write_bytes(data)
    conn.execute(
        """INSERT INTO revisions(document_id,rev_no,file_name,file_path,sha256,change_summary,change_reason,
           effective_date,status,submitted_by,submitted_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (doc_id, rev_no, Path(file.filename or "document.pdf").name, stored, hashlib.sha256(data).hexdigest(),
         change_summary.strip(), change_reason.strip(), effective_date, "申請中", user["id"], db.now()),
    )
    db.log(conn, user["login_id"], "申請", f"{doc_no} Rev.{rev_no}", change_reason.strip())
    flash(request, f"{doc_no} Rev.{rev_no} を申請しました")
    return RedirectResponse(f"/documents/{doc_no}", status_code=303)


# ---------- 承認 ----------
@app.get("/approvals")
def approvals(request: Request, user=Depends(require("admin", "approver")), conn=Depends(get_conn)):
    items = conn.execute(
        """SELECT r.*, d.doc_no, d.title, s.name AS submitter FROM revisions r
           JOIN documents d ON d.id=r.document_id JOIN users s ON s.id=r.submitted_by
           WHERE r.status='申請中' ORDER BY r.submitted_at"""
    ).fetchall()
    return render(request, "approvals.html", user, items=items)


@app.post("/approvals/{rev_id}", dependencies=[Depends(check_csrf)])
def decide(
    rev_id: int,
    request: Request,
    decision: str = Form(...),
    comment: str = Form(""),
    user=Depends(require("approver")),
    conn=Depends(get_conn),
):
    r = conn.execute(
        "SELECT r.*, d.doc_no FROM revisions r JOIN documents d ON d.id=r.document_id WHERE r.id=?", (rev_id,)
    ).fetchone()
    if not r or r["status"] != "申請中":
        raise HTTPException(404, "承認待ちの申請ではありません")
    if r["submitted_by"] == user["id"]:
        flash(request, "自分の申請は承認できません")
        return RedirectResponse("/approvals", status_code=303)
    if decision not in ("approve", "reject"):
        raise HTTPException(400)
    if decision == "reject" and not comment.strip():
        flash(request, "差戻しにはコメントが必要です")
        return RedirectResponse("/approvals", status_code=303)
    status = "承認済" if decision == "approve" else "差戻し"
    conn.execute(
        "UPDATE revisions SET status=?, decided_by=?, decided_at=?, decision_comment=? WHERE id=?",
        (status, user["id"], db.now(), comment.strip(), rev_id),
    )
    db.log(conn, user["login_id"], status, f"{r['doc_no']} Rev.{r['rev_no']}", comment.strip())
    flash(request, f"{r['doc_no']} Rev.{r['rev_no']} を{status}にしました")
    return RedirectResponse("/approvals", status_code=303)


# ---------- アカウント管理 ----------
@app.get("/users")
def users(request: Request, user=Depends(require("admin")), conn=Depends(get_conn)):
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return render(request, "users.html", user, rows=rows)


@app.post("/users", dependencies=[Depends(check_csrf)])
def user_create(
    request: Request,
    login_id: str = Form(...),
    name: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    user=Depends(require("admin")),
    conn=Depends(get_conn),
):
    login_id, name = login_id.strip(), name.strip()
    if not login_id or not name or role not in ROLES:
        flash(request, "入力内容が正しくありません")
    elif len(password) < MIN_PASSWORD:
        flash(request, f"パスワードは{MIN_PASSWORD}文字以上にしてください")
    elif conn.execute("SELECT 1 FROM users WHERE login_id=?", (login_id,)).fetchone():
        flash(request, "そのIDは既に使われています")
    else:
        conn.execute(
            "INSERT INTO users(login_id,name,role,password_hash,created_at) VALUES(?,?,?,?,?)",
            (login_id, name, role, db.hash_password(password), db.now()),
        )
        db.log(conn, user["login_id"], "アカウント作成", login_id, f"role={role}")
        flash(request, f"{login_id} を作成しました")
    return RedirectResponse("/users", status_code=303)


@app.post("/users/{uid}/toggle", dependencies=[Depends(check_csrf)])
def user_toggle(uid: int, request: Request, user=Depends(require("admin")), conn=Depends(get_conn)):
    target = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not target:
        raise HTTPException(404)
    if target["id"] == user["id"]:
        flash(request, "自分自身は無効化できません")
    else:
        new = 0 if target["active"] else 1
        conn.execute("UPDATE users SET active=? WHERE id=?", (new, uid))
        db.log(conn, user["login_id"], "アカウント有効化" if new else "アカウント無効化", target["login_id"])
    return RedirectResponse("/users", status_code=303)


@app.post("/users/{uid}/reset", dependencies=[Depends(check_csrf)])
def user_reset(
    uid: int, request: Request, password: str = Form(...), user=Depends(require("admin")), conn=Depends(get_conn)
):
    target = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not target:
        raise HTTPException(404)
    if len(password) < MIN_PASSWORD:
        flash(request, f"パスワードは{MIN_PASSWORD}文字以上にしてください")
    else:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (db.hash_password(password), uid))
        db.log(conn, user["login_id"], "パスワード再設定", target["login_id"])
        flash(request, f"{target['login_id']} のパスワードを再設定しました")
    return RedirectResponse("/users", status_code=303)


# ---------- 操作ログ ----------
@app.get("/audit")
def audit(request: Request, user=Depends(require("admin")), conn=Depends(get_conn)):
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 500").fetchall()
    return render(request, "audit.html", user, rows=rows, chain_ok=db.verify_audit_chain(conn))
