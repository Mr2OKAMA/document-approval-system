"""業務ロジック(状態遷移、期限計算、整合性チェック)。"""
import calendar
import hashlib
import sqlite3
import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import HTTPException, UploadFile

from . import db
from .core import MAX_UPLOAD

OPEN_STATUSES = ("下書き", "確認待ち", "承認待ち")
WARN_DAYS = 30


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def save_pdf(file: UploadFile) -> tuple[str, str, str]:
    """PDFを保存し (保存名, 元ファイル名, sha256) を返す。"""
    data = file.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD or not data.startswith(b"%PDF"):
        raise HTTPException(400, "PDFファイル(20MB以下)を添付してください")
    stored = f"{uuid.uuid4().hex}.pdf"
    (db.DATA_DIR / "files" / stored).write_bytes(data)
    return stored, Path(file.filename or "document.pdf").name, hashlib.sha256(data).hexdigest()


def file_ok(rev: sqlite3.Row) -> bool:
    path = db.DATA_DIR / "files" / rev["file_path"]
    return path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == rev["sha256"]


def current_rev(conn: sqlite3.Connection, doc_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT * FROM revisions WHERE document_id=? AND status='承認済' AND effective_date<=?
           ORDER BY rev_no DESC LIMIT 1""",
        (doc_id, db.today().isoformat()),
    ).fetchone()


def refresh_status(conn: sqlite3.Connection) -> None:
    """より新しい版が適用開始された承認済みの版を廃版にする。"""
    rows = conn.execute(
        """SELECT r.id, r.rev_no, d.doc_no FROM revisions r JOIN documents d ON d.id=r.document_id
           WHERE r.status='承認済' AND EXISTS (
             SELECT 1 FROM revisions n WHERE n.document_id=r.document_id AND n.status='承認済'
             AND n.effective_date<=? AND n.rev_no>r.rev_no)""",
        (db.today().isoformat(),),
    ).fetchall()
    for r in rows:
        conn.execute("UPDATE revisions SET status='廃版', obsoleted_at=? WHERE id=?", (db.now(), r["id"]))
        db.log(conn, "system", "廃版(新版適用)", f"{r['doc_no']} Rev.{r['rev_no']}")


def next_review_date(conn: sqlite3.Connection, doc: sqlite3.Row) -> date | None:
    rev = current_rev(conn, doc["id"])
    if not rev or doc["abolished_at"]:
        return None
    last = conn.execute(
        "SELECT MAX(reviewed_on) FROM doc_reviews WHERE document_id=?", (doc["id"],)
    ).fetchone()[0]
    base = max(filter(None, [parse_date(rev["effective_date"]), parse_date(last) if last else None]))
    return add_months(base, doc["review_cycle_months"])


def due_state(due: date | None) -> str:
    if due is None:
        return ""
    t = db.today()
    if due < t:
        return "超過"
    if due <= t + timedelta(days=WARN_DAYS):
        return "間近"
    return "OK"


def ack_targets(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM users WHERE active=1 AND role<>'admin' ORDER BY login_id").fetchall()


def has_reviewed(conn: sqlite3.Connection, rev_id: int, user_id: int) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM approvals WHERE revision_id=? AND user_id=? AND step='確認' AND decision='承認'",
            (rev_id, user_id),
        ).fetchone()
    )


def record(conn, rev, user, step: str, decision: str, comment: str = "") -> None:
    conn.execute(
        "INSERT INTO approvals(revision_id,step,decision,user_id,comment,sha256,decided_at) VALUES(?,?,?,?,?,?,?)",
        (rev["id"], step, decision, user["id"], comment, rev["sha256"], db.now()),
    )


def integrity_checks(conn: sqlite3.Connection) -> list[dict]:
    """整合性チェック。level: エラー / 警告。"""
    out: list[dict] = []

    def add(level, kind, msg, link=""):
        out.append({"level": level, "kind": kind, "msg": msg, "link": link})

    if not db.verify_audit_chain(conn):
        add("エラー", "操作ログ", "操作ログのハッシュ連鎖が一致しません(改ざんの疑い)", "/audit")
    for r in conn.execute(
        """SELECT r.*, d.doc_no FROM revisions r JOIN documents d ON d.id=r.document_id
           WHERE r.status IN ('承認待ち','承認済','廃版','確認待ち')"""
    ):
        if not file_ok(r):
            add("エラー", "ファイル", f"{r['doc_no']} Rev.{r['rev_no']}: PDFが無い、またはハッシュ不一致", f"/revisions/{r['id']}")
    t = db.today()
    for doc in conn.execute("SELECT * FROM documents WHERE abolished_at IS NULL ORDER BY doc_no"):
        link = f"/documents/{doc['doc_no']}"
        rev = current_rev(conn, doc["id"])
        if not rev:
            if conn.execute("SELECT 1 FROM revisions WHERE document_id=? AND status='承認済'", (doc["id"],)).fetchone():
                add("警告", "適用", f"{doc['doc_no']}: 承認済みだが適用開始前です", link)
            continue
        label = f"{doc['doc_no']} Rev.{rev['rev_no']}"
        approved = (rev["approved_at"] or "")[:10]
        if approved and rev["effective_date"] < approved:
            add("警告", "適用日", f"{label}: 適用開始日({rev['effective_date']})が承認日({approved})より前です(遡及適用)", f"/revisions/{rev['id']}")
        trainings = conn.execute("SELECT held_on FROM trainings WHERE revision_id=?", (rev["id"],)).fetchall()
        if not trainings:
            add("警告", "教育", f"{label}: 教育・周知の実施記録がありません", f"/revisions/{rev['id']}")
        elif min(x["held_on"] for x in trainings) > rev["effective_date"]:
            add("警告", "教育", f"{label}: 教育実施日が適用開始日より後です", f"/revisions/{rev['id']}")
        missing = [
            u["name"] for u in ack_targets(conn)
            if not conn.execute("SELECT 1 FROM acknowledgements WHERE revision_id=? AND user_id=?", (rev["id"], u["id"])).fetchone()
        ]
        if missing:
            add("警告", "周知", f"{label}: 未確認者 {len(missing)}名({'、'.join(missing[:5])}{'…' if len(missing) > 5 else ''})", f"/revisions/{rev['id']}")
        due = next_review_date(conn, doc)
        if due and due < t:
            add("警告", "見直し", f"{doc['doc_no']}: 見直し期限({due})を超過しています", link)
    for r in conn.execute("SELECT r.*, d.doc_no FROM revisions r JOIN documents d ON d.id=r.document_id WHERE r.status IN ('確認待ち','承認待ち')"):
        last = conn.execute("SELECT MAX(decided_at) FROM approvals WHERE revision_id=?", (r["id"],)).fetchone()[0]
        if last and parse_date(last[:10]) and (t - parse_date(last[:10])).days > 7:
            add("警告", "滞留", f"{r['doc_no']} Rev.{r['rev_no']}: {r['status']}のまま7日以上経過しています", f"/revisions/{r['id']}")
    for e in conn.execute("SELECT * FROM equipment WHERE active=1 ORDER BY name"):
        due = parse_date(e["calibration_due"]) if e["calibration_due"] else None
        if due is None:
            add("警告", "校正", f"設備「{e['name']}」: 校正記録がありません", "/equipment")
        elif due < t:
            add("エラー", "校正", f"設備「{e['name']}」: 校正期限({due})を超過しています", "/equipment")
    return out
