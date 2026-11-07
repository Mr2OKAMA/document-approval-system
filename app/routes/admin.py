import csv
import io

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import Response
from openpyxl import Workbook

from .. import db, services
from ..core import MIN_PASSWORD, ROLES, STAFF, back, check_csrf, get_conn, render, require

router = APIRouter()


# ---------- アカウント ----------
@router.get("/users")
def users(request: Request, user=Depends(require("admin")), conn=Depends(get_conn)):
    return render(request, "users.html", user, rows=conn.execute("SELECT * FROM users ORDER BY id").fetchall(),
                  now=db.now())


@router.post("/users", dependencies=[Depends(check_csrf)])
def user_create(request: Request, login_id: str = Form(...), name: str = Form(...), role: str = Form(...),
                password: str = Form(...), user=Depends(require("admin")), conn=Depends(get_conn)):
    login_id, name = login_id.strip(), name.strip()
    if not login_id or not name or role not in ROLES:
        return back(request, "/users", "入力内容が正しくありません")
    if len(password) < MIN_PASSWORD or password == login_id:
        return back(request, "/users", f"初期パスワードは{MIN_PASSWORD}文字以上で、IDと異なるものにしてください")
    if conn.execute("SELECT 1 FROM users WHERE login_id=?", (login_id,)).fetchone():
        return back(request, "/users", "そのIDは既に使われています")
    conn.execute(
        "INSERT INTO users(login_id,name,role,password_hash,must_change_pw,created_at) VALUES(?,?,?,?,1,?)",
        (login_id, name, role, db.hash_password(password), db.now()))
    db.log(conn, user["login_id"], "アカウント作成", login_id, f"role={role}")
    return back(request, "/users", f"{login_id} を作成しました(初回ログイン時にパスワード変更が必要です)")


def _target(conn, uid):
    t = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not t:
        raise HTTPException(404)
    return t


@router.post("/users/{uid}/toggle", dependencies=[Depends(check_csrf)])
def user_toggle(uid: int, request: Request, user=Depends(require("admin")), conn=Depends(get_conn)):
    t = _target(conn, uid)
    if t["id"] == user["id"]:
        return back(request, "/users", "自分自身は無効化できません")
    new = 0 if t["active"] else 1
    conn.execute("UPDATE users SET active=? WHERE id=?", (new, uid))
    db.log(conn, user["login_id"], "アカウント有効化" if new else "アカウント無効化", t["login_id"])
    return back(request, "/users")


@router.post("/users/{uid}/reset", dependencies=[Depends(check_csrf)])
def user_reset(uid: int, request: Request, password: str = Form(...), user=Depends(require("admin")),
               conn=Depends(get_conn)):
    t = _target(conn, uid)
    if len(password) < MIN_PASSWORD or password == t["login_id"]:
        return back(request, "/users", f"パスワードは{MIN_PASSWORD}文字以上で、IDと異なるものにしてください")
    conn.execute("UPDATE users SET password_hash=?, must_change_pw=1, failed_count=0, locked_until=NULL WHERE id=?",
                 (db.hash_password(password), uid))
    db.log(conn, user["login_id"], "パスワード再設定", t["login_id"])
    return back(request, "/users", f"{t['login_id']} のパスワードを再設定しました(次回ログイン時に変更が必要です)")


@router.post("/users/{uid}/role", dependencies=[Depends(check_csrf)])
def user_role(uid: int, request: Request, role: str = Form(...), user=Depends(require("admin")), conn=Depends(get_conn)):
    t = _target(conn, uid)
    if role not in ROLES:
        raise HTTPException(400)
    if t["id"] == user["id"]:
        return back(request, "/users", "自分自身の役割は変更できません")
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
    db.log(conn, user["login_id"], "役割変更", t["login_id"], f"{t['role']} → {role}")
    return back(request, "/users", "役割を変更しました")


@router.post("/users/{uid}/unlock", dependencies=[Depends(check_csrf)])
def user_unlock(uid: int, request: Request, user=Depends(require("admin")), conn=Depends(get_conn)):
    t = _target(conn, uid)
    conn.execute("UPDATE users SET failed_count=0, locked_until=NULL WHERE id=?", (uid,))
    db.log(conn, user["login_id"], "ロック解除", t["login_id"])
    return back(request, "/users", "ロックを解除しました")


# ---------- ログ・整合性 ----------
@router.get("/audit")
def audit(request: Request, q: str = "", user=Depends(require("admin")), conn=Depends(get_conn)):
    like = f"%{q.strip()}%"
    rows = conn.execute(
        "SELECT * FROM audit_log WHERE (?='' OR actor LIKE ? OR action LIKE ? OR target LIKE ? OR detail LIKE ?) "
        "ORDER BY id DESC LIMIT 500", (q.strip(), like, like, like, like)).fetchall()
    return render(request, "audit.html", user, rows=rows, q=q, chain_ok=db.verify_audit_chain(conn))


@router.get("/checks")
def checks(request: Request, user=Depends(require("admin", "approver", "reviewer")), conn=Depends(get_conn)):
    services.refresh_status(conn)
    return render(request, "checks.html", user, items=services.integrity_checks(conn))


# ---------- 監査出力 ----------
def _safe(v):
    """CSV/Excelの数式インジェクション対策。"""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return "" if v is None else v


def _datasets(conn, kind: str):
    if kind == "register":
        head = ["文書番号", "名称", "分類", "部署", "現行版", "適用開始日", "承認日", "見直し期限", "状態"]
        rows = []
        for d in conn.execute("SELECT * FROM documents ORDER BY doc_no"):
            cur = services.current_rev(conn, d["id"])
            due = services.next_review_date(conn, d)
            status = "廃止" if d["abolished_at"] else ("適用中" if cur else "適用前/未承認")
            rows.append([d["doc_no"], d["title"], d["category"], d["department"],
                         f"Rev.{cur['rev_no']}" if cur else "", cur["effective_date"] if cur else "",
                         (cur["approved_at"] or "") if cur else "", due.isoformat() if due else "", status])
        return head, rows
    if kind == "revisions":
        head = ["文書番号", "名称", "版", "状態", "改訂内容", "改訂理由", "適用開始日", "作成者", "作成日時",
                "確認者", "承認者", "承認日時", "廃版日時", "SHA-256"]
        rows = []
        for r in conn.execute(
            "SELECT r.*, d.doc_no, d.title, u.name AS creator FROM revisions r JOIN documents d ON d.id=r.document_id "
            "JOIN users u ON u.id=r.created_by ORDER BY d.doc_no, r.rev_no"):
            def who(step):
                x = conn.execute("SELECT u.name FROM approvals a JOIN users u ON u.id=a.user_id WHERE a.revision_id=? "
                                 "AND a.step=? AND a.decision='承認' ORDER BY a.id DESC LIMIT 1", (r["id"], step)).fetchone()
                return x[0] if x else ""
            rows.append([r["doc_no"], r["title"], f"Rev.{r['rev_no']}", r["status"], r["change_summary"],
                         r["change_reason"], r["effective_date"], r["creator"], r["created_at"], who("確認"),
                         who("承認"), r["approved_at"], r["obsoleted_at"], r["sha256"]])
        return head, rows
    if kind == "approvals":
        head = ["文書番号", "版", "段階", "判断", "担当者", "コメント", "日時", "対象PDFのSHA-256"]
        return head, [[r["doc_no"], f"Rev.{r['rev_no']}", r["step"], r["decision"], r["name"], r["comment"],
                       r["decided_at"], r["sha256"]] for r in conn.execute(
            "SELECT a.*, u.name, d.doc_no, r.rev_no FROM approvals a JOIN users u ON u.id=a.user_id "
            "JOIN revisions r ON r.id=a.revision_id JOIN documents d ON d.id=r.document_id ORDER BY a.id")]
    if kind == "acks":
        head = ["文書番号", "版", "確認者", "確認日時"]
        return head, [[r["doc_no"], f"Rev.{r['rev_no']}", r["name"], r["acknowledged_at"]] for r in conn.execute(
            "SELECT a.acknowledged_at, u.name, d.doc_no, r.rev_no FROM acknowledgements a JOIN users u ON u.id=a.user_id "
            "JOIN revisions r ON r.id=a.revision_id JOIN documents d ON d.id=r.document_id ORDER BY d.doc_no, r.rev_no, a.id")]
    if kind == "trainings":
        head = ["文書番号", "版", "実施日", "講師", "受講者", "備考", "記録者", "記録日時"]
        return head, [[r["doc_no"], f"Rev.{r['rev_no']}", r["held_on"], r["trainer"], r["attendees"], r["note"],
                       r["name"], r["recorded_at"]] for r in conn.execute(
            "SELECT t.*, u.name, d.doc_no, r.rev_no FROM trainings t JOIN users u ON u.id=t.recorded_by "
            "JOIN revisions r ON r.id=t.revision_id JOIN documents d ON d.id=r.document_id ORDER BY d.doc_no, r.rev_no, t.held_on")]
    if kind == "equipment":
        head = ["名称", "型式", "製造番号", "使用開始日", "校正周期(月)", "校正期限", "状態", "備考"]
        return head, [[e["name"], e["model"], e["serial_no"], e["in_use_since"], e["calibration_cycle_months"],
                       e["calibration_due"], "使用中" if e["active"] else "使用停止", e["note"]]
                      for e in conn.execute("SELECT * FROM equipment ORDER BY name")]
    if kind == "audit":
        head = ["ID", "日時", "操作者", "操作", "対象", "詳細", "ハッシュ"]
        return head, [[r["id"], r["ts"], r["actor"], r["action"], r["target"], r["detail"], r["hash"]]
                      for r in conn.execute("SELECT * FROM audit_log ORDER BY id")]
    raise HTTPException(404)


EXPORTS = {"register": "文書台帳", "revisions": "改訂履歴", "approvals": "承認記録", "acks": "周知確認記録",
           "trainings": "教育実施記録", "equipment": "設備台帳", "audit": "操作ログ"}


@router.get("/export")
def export_page(request: Request, user=Depends(require(*STAFF)), conn=Depends(get_conn)):
    items = {k: v for k, v in EXPORTS.items() if k != "audit" or user["role"] == "admin"}
    return render(request, "export.html", user, items=items)


@router.get("/export/{kind}.{fmt}")
def export(kind: str, fmt: str, user=Depends(require(*STAFF)), conn=Depends(get_conn)):
    if kind == "audit" and user["role"] != "admin":
        raise HTTPException(403, "権限がありません")
    if fmt not in ("csv", "xlsx"):
        raise HTTPException(404)
    services.refresh_status(conn)
    head, rows = _datasets(conn, kind)
    rows = [[_safe(v) for v in r] for r in rows]
    db.log(conn, user["login_id"], "監査出力", EXPORTS[kind], fmt)
    stamp = db.today().strftime("%Y%m%d")
    name = f"{kind}_{stamp}.{fmt}"
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(head)
        w.writerows(rows)
        body, mime = buf.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = EXPORTS[kind]
        ws.append(head)
        for r in rows:
            ws.append(r)
        out = io.BytesIO()
        wb.save(out)
        body, mime = out.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(body, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})
