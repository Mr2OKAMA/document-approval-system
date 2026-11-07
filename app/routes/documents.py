from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from .. import db, services
from ..core import STAFF, back, check_csrf, current_user, get_conn, render, require

router = APIRouter()
AUTHORING = ("admin", "author")


def _doc_or_404(conn, doc_no: str):
    doc = conn.execute("SELECT * FROM documents WHERE doc_no=?", (doc_no,)).fetchone()
    if not doc:
        raise HTTPException(404)
    return doc


def _rev_or_404(conn, rev_id: int):
    rev = conn.execute(
        "SELECT r.*, d.doc_no, d.title, d.abolished_at, u.name AS creator FROM revisions r "
        "JOIN documents d ON d.id=r.document_id JOIN users u ON u.id=r.created_by WHERE r.id=?",
        (rev_id,),
    ).fetchone()
    if not rev:
        raise HTTPException(404)
    return rev


def visible_to(user, rev) -> bool:
    role, st = user["role"], rev["status"]
    if role == "viewer":
        return st == "承認済" and rev["effective_date"] <= db.today().isoformat() and not rev["abolished_at"]
    if st in ("承認済", "廃版") or role == "admin" or rev["created_by"] == user["id"]:
        return True
    # 未承認版は、手続きに関わる役割にだけ見せる
    return (st == "確認待ち" and role == "reviewer") or (st == "承認待ち" and role in ("reviewer", "approver"))


def _flags(conn, user, rev) -> dict:
    owner = rev["created_by"] == user["id"] or user["role"] == "admin"
    st = rev["status"]
    acked = conn.execute(
        "SELECT 1 FROM acknowledgements WHERE revision_id=? AND user_id=?", (rev["id"], user["id"])
    ).fetchone()
    return {
        "edit": st == "下書き" and owner and user["role"] in AUTHORING,
        "withdraw": st in services.OPEN_STATUSES and owner and user["role"] in AUTHORING,
        "review": st == "確認待ち" and user["role"] == "reviewer" and rev["created_by"] != user["id"],
        "approve": st == "承認待ち" and user["role"] == "approver" and rev["created_by"] != user["id"]
        and not services.has_reviewed(conn, rev["id"], user["id"]),
        "ack": st == "承認済" and user["role"] != "admin" and not acked,
        "acked": bool(acked),
        "training": st == "承認済" and user["role"] in STAFF,
    }


# ---------- 文書一覧・検索 ----------
@router.get("/documents")
def documents(
    request: Request,
    q: str = "",
    category: str = "",
    department: str = "",
    show: str = "active",
    user=Depends(current_user),
    conn=Depends(get_conn),
):
    services.refresh_status(conn)
    where, args = [], [db.today().isoformat()]
    if q.strip():
        like = f"%{q.strip()}%"
        where.append("(d.doc_no LIKE ? OR d.title LIKE ? OR d.category LIKE ? OR d.department LIKE ? OR r.change_summary LIKE ?)")
        args += [like] * 5
    if category:
        where.append("d.category=?")
        args.append(category)
    if department:
        where.append("d.department=?")
        args.append(department)
    if user["role"] == "viewer" or show != "abolished":
        where.append("d.abolished_at IS NULL")
    else:
        where.append("d.abolished_at IS NOT NULL")
    if user["role"] == "viewer":
        where.append("r.id IS NOT NULL")
    sql = f"""SELECT d.*, r.id AS rev_id, r.rev_no, r.effective_date,
              (SELECT COUNT(*) FROM revisions o WHERE o.document_id=d.id AND o.status IN ('下書き','確認待ち','承認待ち')) AS open_count
              FROM documents d LEFT JOIN revisions r ON r.id=(
                SELECT id FROM revisions WHERE document_id=d.id AND status='承認済' AND effective_date<=?
                ORDER BY rev_no DESC LIMIT 1)
              WHERE {' AND '.join(where)} ORDER BY d.doc_no"""
    rows = []
    for d in conn.execute(sql, args).fetchall():
        due = services.next_review_date(conn, d)
        rows.append({"d": d, "due": due, "due_state": services.due_state(due)})
    cats = [r[0] for r in conn.execute("SELECT DISTINCT category FROM documents WHERE category<>'' ORDER BY 1")]
    deps = [r[0] for r in conn.execute("SELECT DISTINCT department FROM documents WHERE department<>'' ORDER BY 1")]
    return render(request, "documents.html", user, rows=rows, cats=cats, deps=deps,
                  q=q, category=category, department=department, show=show)


@router.get("/documents/{doc_no}")
def document_detail(doc_no: str, request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    services.refresh_status(conn)
    doc = _doc_or_404(conn, doc_no)
    cur = services.current_rev(conn, doc["id"])
    if user["role"] == "viewer" and (doc["abolished_at"] or not cur):
        raise HTTPException(404)
    revs = conn.execute(
        "SELECT r.*, u.name AS creator FROM revisions r JOIN users u ON u.id=r.created_by "
        "WHERE r.document_id=? ORDER BY r.rev_no DESC", (doc["id"],)
    ).fetchall()
    if user["role"] == "viewer":
        revs = [r for r in revs if r["id"] == cur["id"]]
    else:
        revs = [r for r in revs if visible_to(user, {**dict(r), "abolished_at": doc["abolished_at"]})]
    due = services.next_review_date(conn, doc)
    reviews = conn.execute(
        "SELECT v.*, u.name AS reviewer FROM doc_reviews v JOIN users u ON u.id=v.reviewed_by "
        "WHERE v.document_id=? ORDER BY v.reviewed_on DESC, v.id DESC", (doc["id"],)
    ).fetchall()
    links = conn.execute(
        "SELECT d.id, d.doc_no, d.title, l.note FROM doc_links l JOIN documents d ON d.id=l.to_id "
        "WHERE l.from_id=? AND (?<>'viewer' OR d.abolished_at IS NULL) ORDER BY d.doc_no", (doc["id"], user["role"])
    ).fetchall()
    equipment = conn.execute(
        "SELECT e.* FROM doc_equipment x JOIN equipment e ON e.id=x.equipment_id WHERE x.document_id=? ORDER BY e.name",
        (doc["id"],),
    ).fetchall()
    all_equipment = conn.execute("SELECT id, name FROM equipment WHERE active=1 ORDER BY name").fetchall()
    return render(request, "document.html", user, doc=doc, cur=cur, revs=revs, due=due,
                  due_state=services.due_state(due), reviews=reviews, links=links, equipment=equipment,
                  all_equipment=all_equipment, today=db.today().isoformat())


@router.post("/documents/{doc_no}/settings", dependencies=[Depends(check_csrf)])
def document_settings(
    doc_no: str, request: Request, title: str = Form(...), category: str = Form(""), department: str = Form(""),
    review_cycle_months: int = Form(12), user=Depends(require("admin", "approver")), conn=Depends(get_conn),
):
    doc = _doc_or_404(conn, doc_no)
    if not title.strip() or not 1 <= review_cycle_months <= 120:
        return back(request, f"/documents/{doc_no}", "入力内容が正しくありません")
    conn.execute(
        "UPDATE documents SET title=?, category=?, department=?, review_cycle_months=? WHERE id=?",
        (title.strip(), category.strip(), department.strip(), review_cycle_months, doc["id"]),
    )
    db.log(conn, user["login_id"], "文書情報変更", doc_no,
           f"{doc['title']}/{doc['category']}/{doc['department']}/{doc['review_cycle_months']}月 → "
           f"{title.strip()}/{category.strip()}/{department.strip()}/{review_cycle_months}月")
    return back(request, f"/documents/{doc_no}", "文書情報を更新しました")


@router.post("/documents/{doc_no}/abolish", dependencies=[Depends(check_csrf)])
def abolish(doc_no: str, request: Request, reason: str = Form(""), user=Depends(require("admin", "approver")),
            conn=Depends(get_conn)):
    doc = _doc_or_404(conn, doc_no)
    if doc["abolished_at"]:
        return back(request, f"/documents/{doc_no}", "既に廃止されています")
    if not reason.strip():
        return back(request, f"/documents/{doc_no}", "廃止理由を入力してください")
    if conn.execute("SELECT 1 FROM revisions WHERE document_id=? AND status IN ('下書き','確認待ち','承認待ち')", (doc["id"],)).fetchone():
        return back(request, f"/documents/{doc_no}", "未完了の申請があるため廃止できません。先に取り下げてください")
    conn.execute("UPDATE documents SET abolished_at=?, abolished_by=?, abolished_reason=? WHERE id=?",
                 (db.now(), user["id"], reason.strip(), doc["id"]))
    db.log(conn, user["login_id"], "文書廃止", doc_no, reason.strip())
    return back(request, f"/documents/{doc_no}", "文書を廃止しました")


@router.post("/documents/{doc_no}/reinstate", dependencies=[Depends(check_csrf)])
def reinstate(doc_no: str, request: Request, user=Depends(require("admin")), conn=Depends(get_conn)):
    doc = _doc_or_404(conn, doc_no)
    conn.execute("UPDATE documents SET abolished_at=NULL, abolished_by=NULL, abolished_reason=NULL WHERE id=?", (doc["id"],))
    db.log(conn, user["login_id"], "文書廃止の取消", doc_no)
    return back(request, f"/documents/{doc_no}", "廃止を取り消しました")


@router.post("/documents/{doc_no}/reviews", dependencies=[Depends(check_csrf)])
def add_review(doc_no: str, request: Request, reviewed_on: str = Form(...), result: str = Form(...),
               comment: str = Form(""), user=Depends(require("admin", "approver", "reviewer")), conn=Depends(get_conn)):
    doc = _doc_or_404(conn, doc_no)
    d = services.parse_date(reviewed_on)
    if not d or d > db.today() or result not in ("変更なし", "改訂が必要"):
        return back(request, f"/documents/{doc_no}", "見直し日(未来日不可)と結果を正しく入力してください")
    conn.execute("INSERT INTO doc_reviews(document_id,reviewed_on,result,comment,reviewed_by,recorded_at) VALUES(?,?,?,?,?,?)",
                 (doc["id"], reviewed_on, result, comment.strip(), user["id"], db.now()))
    db.log(conn, user["login_id"], "定期見直し記録", doc_no, f"{reviewed_on} {result}")
    return back(request, f"/documents/{doc_no}", "見直し結果を記録しました")


@router.post("/documents/{doc_no}/links", dependencies=[Depends(check_csrf)])
def add_link(doc_no: str, request: Request, to_doc_no: str = Form(...), note: str = Form(""),
             user=Depends(require("admin", "author", "approver")), conn=Depends(get_conn)):
    doc = _doc_or_404(conn, doc_no)
    to = conn.execute("SELECT * FROM documents WHERE doc_no=?", (to_doc_no.strip(),)).fetchone()
    if not to or to["id"] == doc["id"]:
        return back(request, f"/documents/{doc_no}", "関連付ける文書番号が正しくありません")
    conn.execute("INSERT OR REPLACE INTO doc_links(from_id,to_id,note) VALUES(?,?,?)", (doc["id"], to["id"], note.strip()))
    db.log(conn, user["login_id"], "関連文書追加", doc_no, to["doc_no"])
    return back(request, f"/documents/{doc_no}", "関連文書を追加しました")


@router.post("/documents/{doc_no}/links/{to_id}/delete", dependencies=[Depends(check_csrf)])
def del_link(doc_no: str, to_id: int, request: Request, user=Depends(require("admin", "author", "approver")),
             conn=Depends(get_conn)):
    doc = _doc_or_404(conn, doc_no)
    conn.execute("DELETE FROM doc_links WHERE from_id=? AND to_id=?", (doc["id"], to_id))
    db.log(conn, user["login_id"], "関連文書削除", doc_no, str(to_id))
    return back(request, f"/documents/{doc_no}", "関連文書を外しました")


@router.post("/documents/{doc_no}/equipment", dependencies=[Depends(check_csrf)])
def add_equipment_link(doc_no: str, request: Request, equipment_id: int = Form(...),
                       user=Depends(require("admin", "author", "approver")), conn=Depends(get_conn)):
    doc = _doc_or_404(conn, doc_no)
    if not conn.execute("SELECT 1 FROM equipment WHERE id=?", (equipment_id,)).fetchone():
        raise HTTPException(404)
    conn.execute("INSERT OR IGNORE INTO doc_equipment(document_id,equipment_id) VALUES(?,?)", (doc["id"], equipment_id))
    db.log(conn, user["login_id"], "設備紐付け", doc_no, f"equipment:{equipment_id}")
    return back(request, f"/documents/{doc_no}", "設備を紐付けました")


@router.post("/documents/{doc_no}/equipment/{equipment_id}/delete", dependencies=[Depends(check_csrf)])
def del_equipment_link(doc_no: str, equipment_id: int, request: Request,
                       user=Depends(require("admin", "author", "approver")), conn=Depends(get_conn)):
    doc = _doc_or_404(conn, doc_no)
    conn.execute("DELETE FROM doc_equipment WHERE document_id=? AND equipment_id=?", (doc["id"], equipment_id))
    db.log(conn, user["login_id"], "設備紐付け解除", doc_no, f"equipment:{equipment_id}")
    return back(request, f"/documents/{doc_no}", "設備の紐付けを解除しました")


# ---------- 版(申請) ----------
@router.get("/submit")
def submit_form(request: Request, doc_no: str = "", user=Depends(require(*AUTHORING)), conn=Depends(get_conn)):
    docs = conn.execute("SELECT * FROM documents WHERE abolished_at IS NULL ORDER BY doc_no").fetchall()
    cats = [r[0] for r in conn.execute("SELECT DISTINCT category FROM documents WHERE category<>'' ORDER BY 1")]
    deps = [r[0] for r in conn.execute("SELECT DISTINCT department FROM documents WHERE department<>'' ORDER BY 1")]
    return render(request, "submit.html", user, docs=docs, cats=cats, deps=deps, doc_no=doc_no)


@router.post("/submit", dependencies=[Depends(check_csrf)])
def submit(
    request: Request,
    doc_no: str = Form(...),
    title: str = Form(""),
    category: str = Form(""),
    department: str = Form(""),
    review_cycle_months: int = Form(12),
    change_summary: str = Form(...),
    change_reason: str = Form(...),
    effective_date: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(require(*AUTHORING)),
    conn=Depends(get_conn),
):
    doc_no = doc_no.strip()
    doc = conn.execute("SELECT * FROM documents WHERE doc_no=?", (doc_no,)).fetchone()
    error = None
    if not (doc_no and change_summary.strip() and change_reason.strip()) or (not doc and not title.strip()):
        error = "文書番号・名称・改訂内容・改訂理由はすべて必須です"
    elif not services.parse_date(effective_date):
        error = "適用開始日の形式が正しくありません"
    elif not 1 <= review_cycle_months <= 120:
        error = "見直し周期は1〜120か月で指定してください"
    elif doc and doc["abolished_at"]:
        error = "この文書は廃止されています"
    elif doc and conn.execute(
        "SELECT 1 FROM revisions WHERE document_id=? AND status IN ('下書き','確認待ち','承認待ち')", (doc["id"],)
    ).fetchone():
        error = "この文書には未完了の申請(下書き・確認中・承認待ち)があります"
    if error:
        return back(request, "/submit", error)
    stored, fname, sha = services.save_pdf(file)
    if doc:
        doc_id = doc["id"]
        rev_no = conn.execute("SELECT MAX(rev_no) FROM revisions WHERE document_id=?", (doc_id,)).fetchone()[0] + 1
    else:
        doc_id = conn.execute(
            "INSERT INTO documents(doc_no,title,category,department,review_cycle_months,created_at) VALUES(?,?,?,?,?,?)",
            (doc_no, title.strip(), category.strip(), department.strip(), review_cycle_months, db.now()),
        ).lastrowid
        rev_no = 0
    rev_id = conn.execute(
        """INSERT INTO revisions(document_id,rev_no,file_name,file_path,sha256,change_summary,change_reason,
           effective_date,status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,'下書き',?,?)""",
        (doc_id, rev_no, fname, stored, sha, change_summary.strip(), change_reason.strip(), effective_date, user["id"], db.now()),
    ).lastrowid
    db.log(conn, user["login_id"], "下書き作成", f"{doc_no} Rev.{rev_no}", change_reason.strip())
    return back(request, f"/revisions/{rev_id}", "下書きを作成しました。内容を確認し「確認依頼」を押してください")


@router.get("/revisions/{rev_id}")
def revision_detail(rev_id: int, request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    services.refresh_status(conn)
    rev = _rev_or_404(conn, rev_id)
    if not visible_to(user, rev):
        raise HTTPException(404)
    trail = conn.execute(
        "SELECT a.*, u.name FROM approvals a JOIN users u ON u.id=a.user_id WHERE a.revision_id=? ORDER BY a.id", (rev_id,)
    ).fetchall()
    trainings = conn.execute("SELECT * FROM trainings WHERE revision_id=? ORDER BY held_on", (rev_id,)).fetchall()
    ack_rows = []
    if rev["status"] in ("承認済", "廃版"):
        acks = {r["user_id"]: r["acknowledged_at"] for r in conn.execute(
            "SELECT * FROM acknowledgements WHERE revision_id=?", (rev_id,))}
        ack_rows = [(u, acks.get(u["id"])) for u in services.ack_targets(conn)]
    return render(request, "revision.html", user, rev=rev, trail=trail, trainings=trainings, ack_rows=ack_rows,
                  f=_flags(conn, user, rev), hash_ok=services.file_ok(rev) if user["role"] != "viewer" else True,
                  today=db.today().isoformat())


@router.get("/revisions/{rev_id}/file")
def download(rev_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    rev = _rev_or_404(conn, rev_id)
    if not visible_to(user, rev):
        raise HTTPException(404)
    if not services.file_ok(rev):
        db.log(conn, user["login_id"], "改ざん検知", f"{rev['doc_no']} Rev.{rev['rev_no']}")
        conn.commit()
        raise HTTPException(500, "ファイルが無い、またはハッシュが一致しません(改ざんの可能性)")
    db.log(conn, user["login_id"], "閲覧", f"{rev['doc_no']} Rev.{rev['rev_no']}")
    return FileResponse(db.DATA_DIR / "files" / rev["file_path"], media_type="application/pdf",
                        filename=rev["file_name"], content_disposition_type="inline")


@router.post("/revisions/{rev_id}/edit", dependencies=[Depends(check_csrf)])
def edit(rev_id: int, request: Request, change_summary: str = Form(...), change_reason: str = Form(...),
         effective_date: str = Form(...), file: UploadFile | None = File(None),
         user=Depends(require(*AUTHORING)), conn=Depends(get_conn)):
    rev = _rev_or_404(conn, rev_id)
    if not _flags(conn, user, rev)["edit"]:
        raise HTTPException(403, "編集できません")
    url = f"/revisions/{rev_id}"
    if not change_summary.strip() or not change_reason.strip() or not services.parse_date(effective_date):
        return back(request, url, "改訂内容・改訂理由・適用開始日を正しく入力してください")
    stored, fname, sha = rev["file_path"], rev["file_name"], rev["sha256"]
    if file and file.filename:
        stored, fname, sha = services.save_pdf(file)
    conn.execute(
        "UPDATE revisions SET change_summary=?, change_reason=?, effective_date=?, file_path=?, file_name=?, sha256=? WHERE id=?",
        (change_summary.strip(), change_reason.strip(), effective_date, stored, fname, sha, rev_id),
    )
    db.log(conn, user["login_id"], "下書き編集", f"{rev['doc_no']} Rev.{rev['rev_no']}", change_reason.strip())
    return back(request, url, "下書きを更新しました")


@router.post("/revisions/{rev_id}/submit", dependencies=[Depends(check_csrf)])
def submit_for_review(rev_id: int, request: Request, user=Depends(require(*AUTHORING)), conn=Depends(get_conn)):
    rev = _rev_or_404(conn, rev_id)
    if not _flags(conn, user, rev)["edit"]:
        raise HTTPException(403, "提出できません")
    url = f"/revisions/{rev_id}"
    for role, label in (("reviewer", "確認者"), ("approver", "承認者")):
        if not conn.execute("SELECT 1 FROM users WHERE role=? AND active=1 AND id<>?", (role, user["id"])).fetchone():
            return back(request, url, f"提出できる{label}がいません。管理者に{label}アカウントの作成を依頼してください")
    if not _transition(conn, rev_id, "下書き", "確認待ち"):
        return back(request, url, "他の操作で状態が変わりました。画面を更新してください")
    services.record(conn, rev, user, "提出", "提出")
    db.log(conn, user["login_id"], "確認依頼", f"{rev['doc_no']} Rev.{rev['rev_no']}")
    return back(request, url, "確認者へ依頼しました")


@router.post("/revisions/{rev_id}/withdraw", dependencies=[Depends(check_csrf)])
def withdraw(rev_id: int, request: Request, comment: str = Form(""), user=Depends(require(*AUTHORING)),
             conn=Depends(get_conn)):
    rev = _rev_or_404(conn, rev_id)
    if not _flags(conn, user, rev)["withdraw"]:
        raise HTTPException(403, "取り下げできません")
    if not comment.strip():
        return back(request, f"/revisions/{rev_id}", "取下げ理由を入力してください")
    if not _transition(conn, rev_id, rev["status"], "取下げ"):
        return back(request, f"/revisions/{rev_id}", "他の操作で状態が変わりました。画面を更新してください")
    services.record(conn, rev, user, "取下げ", "取下げ", comment.strip())
    db.log(conn, user["login_id"], "取下げ", f"{rev['doc_no']} Rev.{rev['rev_no']}", comment.strip())
    return back(request, f"/documents/{rev['doc_no']}", "申請を取り下げました")


def _transition(conn, rev_id: int, expected: str, new: str, **extra) -> bool:
    """現在の状態が expected のときだけ遷移する(同時操作による二重処理の防止)。"""
    sets = ", ".join(["status=?"] + [f"{k}=?" for k in extra])
    cur = conn.execute(f"UPDATE revisions SET {sets} WHERE id=? AND status=?", (new, *extra.values(), rev_id, expected))
    return cur.rowcount == 1


def _decide(request, rev_id, step, decision, comment, user, conn, flag):
    rev = _rev_or_404(conn, rev_id)
    if not _flags(conn, user, rev)[flag]:
        raise HTTPException(403, "この操作はできません(自分の申請は確認・承認できません。確認者と承認者は別の人が行います)")
    if decision not in ("approve", "reject"):
        raise HTTPException(400)
    url = f"/revisions/{rev_id}"
    if decision == "reject" and not comment.strip():
        return back(request, url, "差戻しにはコメントが必要です")
    if not services.file_ok(rev):
        return back(request, url, "PDFのハッシュが一致しないため処理できません")
    label = f"{rev['doc_no']} Rev.{rev['rev_no']}"
    expected = rev["status"]
    stale = "他の操作で状態が変わりました。画面を更新してください"
    if decision == "reject":
        if not _transition(conn, rev_id, expected, "下書き"):
            return back(request, url, stale)
        services.record(conn, rev, user, step, "差戻し", comment.strip())
        db.log(conn, user["login_id"], f"{step}:差戻し", label, comment.strip())
        return back(request, "/tasks", f"{label} を差し戻しました")
    if step == "確認":
        ok = _transition(conn, rev_id, expected, "承認待ち")
    else:
        ok = _transition(conn, rev_id, expected, "承認済", approved_at=db.now())
    if not ok:
        return back(request, url, stale)
    services.record(conn, rev, user, step, "承認", comment.strip())
    db.log(conn, user["login_id"], f"{step}:承認", label, comment.strip())
    services.refresh_status(conn)
    return back(request, "/tasks", f"{label} を{step}しました")


@router.post("/revisions/{rev_id}/review", dependencies=[Depends(check_csrf)])
def review(rev_id: int, request: Request, decision: str = Form(...), comment: str = Form(""),
           user=Depends(require("reviewer")), conn=Depends(get_conn)):
    return _decide(request, rev_id, "確認", decision, comment, user, conn, "review")


@router.post("/revisions/{rev_id}/approve", dependencies=[Depends(check_csrf)])
def approve(rev_id: int, request: Request, decision: str = Form(...), comment: str = Form(""),
            user=Depends(require("approver")), conn=Depends(get_conn)):
    return _decide(request, rev_id, "承認", decision, comment, user, conn, "approve")
