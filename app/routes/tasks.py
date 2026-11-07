from fastapi import APIRouter, Depends, Form, HTTPException, Request

from .. import db, services
from ..core import STAFF, back, check_csrf, current_user, get_conn, render, require
from .documents import _rev_or_404, visible_to

router = APIRouter()


@router.get("/")
def dashboard(request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    services.refresh_status(conn)
    role, uid = user["role"], user["id"]
    cards = {}
    if role in ("admin", "author"):
        cards["drafts"] = conn.execute(
            "SELECT COUNT(*) FROM revisions WHERE status='下書き' AND (created_by=? OR ?='admin')", (uid, role)).fetchone()[0]
    if role == "reviewer":
        cards["to_review"] = conn.execute(
            "SELECT COUNT(*) FROM revisions WHERE status='確認待ち' AND created_by<>?", (uid,)).fetchone()[0]
    if role == "approver":
        cards["to_approve"] = len(_approvable(conn, uid))
    cards["to_ack"] = len(_pending_acks(conn, user))
    alerts = {}
    if role in STAFF:
        rv = [services.next_review_date(conn, d) for d in conn.execute("SELECT * FROM documents WHERE abolished_at IS NULL")]
        alerts["review_over"] = sum(1 for x in rv if services.due_state(x) == "超過")
        alerts["review_soon"] = sum(1 for x in rv if services.due_state(x) == "間近")
        eq = [services.parse_date(r[0]) for r in conn.execute("SELECT calibration_due FROM equipment WHERE active=1 AND calibration_due IS NOT NULL")]
        alerts["cal_over"] = sum(1 for x in eq if services.due_state(x) == "超過")
        alerts["cal_soon"] = sum(1 for x in eq if services.due_state(x) == "間近")
    if role in ("admin", "approver", "reviewer"):
        alerts["issues"] = len(services.integrity_checks(conn))
    recent = []
    if role != "viewer":
        recent = conn.execute(
            "SELECT r.id, r.rev_no, r.status, d.doc_no, d.title, r.approved_at FROM revisions r JOIN documents d ON d.id=r.document_id "
            "WHERE r.status IN ('承認済') ORDER BY r.approved_at DESC LIMIT 5").fetchall()
    return render(request, "dashboard.html", user, cards=cards, alerts=alerts, recent=recent)


def _approvable(conn, uid):
    return [r for r in conn.execute(
        "SELECT r.*, d.doc_no, d.title, u.name AS creator FROM revisions r JOIN documents d ON d.id=r.document_id "
        "JOIN users u ON u.id=r.created_by WHERE r.status='承認待ち' AND r.created_by<>? ORDER BY r.created_at", (uid,))
        if not services.has_reviewed(conn, r["id"], uid)]


def _pending_acks(conn, user):
    if user["role"] == "admin":
        return []
    rows = conn.execute(
        "SELECT r.*, d.doc_no, d.title, d.abolished_at FROM revisions r JOIN documents d ON d.id=r.document_id "
        "WHERE r.status='承認済' AND d.abolished_at IS NULL AND NOT EXISTS ("
        "SELECT 1 FROM acknowledgements a WHERE a.revision_id=r.id AND a.user_id=?) ORDER BY d.doc_no", (user["id"],)).fetchall()
    return [r for r in rows if visible_to(user, r)]


@router.get("/tasks")
def tasks(request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    role, uid = user["role"], user["id"]
    data = {"drafts": [], "review": [], "approve": [], "waiting": []}
    base = ("SELECT r.*, d.doc_no, d.title, u.name AS creator FROM revisions r JOIN documents d ON d.id=r.document_id "
            "JOIN users u ON u.id=r.created_by ")
    if role in ("admin", "author"):
        data["drafts"] = conn.execute(base + "WHERE r.status='下書き' AND (r.created_by=? OR ?='admin') ORDER BY r.created_at",
                                      (uid, role)).fetchall()
        data["waiting"] = conn.execute(base + "WHERE r.status IN ('確認待ち','承認待ち') AND (r.created_by=? OR ?='admin') ORDER BY r.created_at",
                                       (uid, role)).fetchall()
    if role == "reviewer":
        data["review"] = conn.execute(base + "WHERE r.status='確認待ち' AND r.created_by<>? ORDER BY r.created_at", (uid,)).fetchall()
    if role == "approver":
        data["approve"] = _approvable(conn, uid)
    rejected = {}
    for r in data["drafts"]:
        last = conn.execute("SELECT comment, decision FROM approvals WHERE revision_id=? ORDER BY id DESC LIMIT 1", (r["id"],)).fetchone()
        if last and last["decision"] == "差戻し":
            rejected[r["id"]] = last["comment"]
    return render(request, "tasks.html", user, rejected=rejected, **data)


# ---------- 周知・教育 ----------
@router.get("/acks")
def acks(request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    services.refresh_status(conn)
    mine = conn.execute(
        "SELECT a.acknowledged_at, r.id AS rev_id, r.rev_no, d.doc_no, d.title FROM acknowledgements a "
        "JOIN revisions r ON r.id=a.revision_id JOIN documents d ON d.id=r.document_id WHERE a.user_id=? "
        "ORDER BY a.acknowledged_at DESC LIMIT 50", (user["id"],)).fetchall()
    return render(request, "acks.html", user, pending=_pending_acks(conn, user), mine=mine)


@router.post("/revisions/{rev_id}/ack", dependencies=[Depends(check_csrf)])
def acknowledge(rev_id: int, request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    rev = _rev_or_404(conn, rev_id)
    if rev["status"] != "承認済" or not visible_to(user, rev) or user["role"] == "admin":
        raise HTTPException(403, "確認できません")
    if not conn.execute("SELECT 1 FROM acknowledgements WHERE revision_id=? AND user_id=?", (rev_id, user["id"])).fetchone():
        conn.execute("INSERT INTO acknowledgements(revision_id,user_id,acknowledged_at) VALUES(?,?,?)",
                     (rev_id, user["id"], db.now()))
        db.log(conn, user["login_id"], "周知確認", f"{rev['doc_no']} Rev.{rev['rev_no']}")
    return back(request, request.headers.get("referer") or "/acks", "確認を記録しました")


@router.post("/revisions/{rev_id}/training", dependencies=[Depends(check_csrf)])
def add_training(rev_id: int, request: Request, held_on: str = Form(...), trainer: str = Form(...),
                 attendees: str = Form(...), note: str = Form(""), user=Depends(require(*STAFF)), conn=Depends(get_conn)):
    rev = _rev_or_404(conn, rev_id)
    url = f"/revisions/{rev_id}"
    d = services.parse_date(held_on)
    if rev["status"] != "承認済":
        raise HTTPException(403, "承認済みの版のみ記録できます")
    if not d or d > db.today() or not trainer.strip() or not attendees.strip():
        return back(request, url, "実施日(未来日不可)・講師・受講者を入力してください")
    conn.execute(
        "INSERT INTO trainings(revision_id,held_on,trainer,attendees,note,recorded_by,recorded_at) VALUES(?,?,?,?,?,?,?)",
        (rev_id, held_on, trainer.strip(), attendees.strip(), note.strip(), user["id"], db.now()))
    db.log(conn, user["login_id"], "教育記録", f"{rev['doc_no']} Rev.{rev['rev_no']}", f"{held_on} {trainer.strip()}")
    return back(request, url, "教育実施記録を登録しました")
