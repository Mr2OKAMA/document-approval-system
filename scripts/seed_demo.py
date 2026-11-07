"""動作確認用のダミーデータを投入する(開発・デモ専用。本番では実行しないこと)。

使い方: DOCMGMT_DATA=/tmp/demo DOCMGMT_SECRET=x python -m scripts.seed_demo
空のデータ領域にのみ投入する。全アカウントのパスワードは DEMO_PASSWORD(公開されているため本番利用不可)。
"""
import re
import sys
from datetime import timedelta

from fastapi.testclient import TestClient

from app import db

DEMO_PASSWORD = "demo-pass-1234"
USERS = [("admin", "管理者 山田", "admin"), ("sato", "申請者 佐藤", "author"), ("suzuki", "確認者 鈴木", "reviewer"),
         ("tanaka", "承認者 田中", "approver"), ("ito", "閲覧者 伊藤", "viewer")]


def make_pdf(title: str) -> bytes:
    stream = f"BT /F1 20 Tf 60 760 Td ({title}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)


def main() -> None:
    from app.main import app

    db.init_db()
    with db.connect() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            sys.exit("データが既にあるため中止します(空のDOCMGMT_DATAで実行してください)")
        for lid, name, role in USERS:
            conn.execute("INSERT INTO users(login_id,name,role,password_hash,created_at) VALUES(?,?,?,?,?)",
                         (lid, name, role, db.hash_password(DEMO_PASSWORD), db.now()))
        db.log(conn, "system", "デモデータ投入", "users")

    def login(lid):
        c = TestClient(app, follow_redirects=True)
        tok = re.search(r'name="csrf" value="(\w+)"', c.get("/login").text).group(1)
        c.post("/login", data={"login_id": lid, "password": DEMO_PASSWORD, "csrf": tok})
        return c

    def csrf(c, path):
        return re.search(r'name="csrf" value="(\w+)"', c.get(path).text).group(1)

    sato, suzuki, tanaka, ito, admin = (login(x) for x in ("sato", "suzuki", "tanaka", "ito", "admin"))
    t = db.today()

    def draft(doc_no, title, cat, dep, summary, reason, eff, rev_label):
        r = sato.post("/submit", data={"doc_no": doc_no, "title": title, "category": cat, "department": dep,
                                       "review_cycle_months": "12", "change_summary": summary, "change_reason": reason,
                                       "effective_date": eff.isoformat(), "csrf": csrf(sato, "/submit")},
                      files={"file": (f"{doc_no}.pdf", make_pdf(f"{doc_no} {rev_label} (DEMO)"), "application/pdf")})
        return int(str(r.url).rstrip("/").split("/")[-1])

    def go(rid, upto):
        sato.post(f"/revisions/{rid}/submit", data={"csrf": csrf(sato, f"/revisions/{rid}")})
        if upto == "review":
            return
        suzuki.post(f"/revisions/{rid}/review", data={"decision": "approve", "csrf": csrf(suzuki, f"/revisions/{rid}")})
        if upto == "approve":
            return
        tanaka.post(f"/revisions/{rid}/approve", data={"decision": "approve", "comment": "OK", "csrf": csrf(tanaka, f"/revisions/{rid}")})

    r1 = draft("SOP-001", "酸素欠乏危険作業 作業手順書", "安全作業", "製造部", "初版制定", "酸素欠乏症等防止規則に基づき新規制定",
               t - timedelta(days=400), "Rev.0")
    go(r1, "done")
    r2 = draft("SOP-001", "", "", "", "酸欠計の携行・連続測定と墜落制止用器具の使用を追加", "ヒヤリハット事例(槽内作業)の再発防止",
               t - timedelta(days=60), "Rev.1")
    go(r2, "done")
    r3 = draft("SOP-002", "高所作業 作業手順書", "安全作業", "施設部", "初版制定", "墜落制止用器具の新規格への対応",
               t - timedelta(days=10), "Rev.0")
    go(r3, "done")
    for rid in (r2, r3):
        ito.post(f"/revisions/{rid}/ack", data={"csrf": csrf(ito, "/acks"), "back_to": "acks"})
    sato.post(f"/revisions/{r2}/training", data={"held_on": (t - timedelta(days=62)).isoformat(), "trainer": "安全衛生担当",
                                                 "attendees": "製造部全員", "csrf": csrf(sato, f"/revisions/{r2}")})
    r4 = draft("FRM-001", "酸素濃度測定記録票", "様式", "製造部", "様式の新規制定", "SOP-001の記録様式として制定", t + timedelta(days=14), "Rev.0")
    go(r4, "approve")
    r5 = draft("SOP-003", "フォークリフト作業手順書", "安全作業", "物流部", "初版制定", "新規導入に伴う制定", t + timedelta(days=30), "Rev.0")
    go(r5, "review")
    draft("SOP-004", "玉掛け作業手順書(作成中)", "安全作業", "施設部", "初版制定", "クレーン作業の標準化", t + timedelta(days=45), "Rev.0")
    sato.post("/documents/SOP-001/links", data={"to_doc_no": "FRM-001", "note": "記録様式", "csrf": csrf(sato, "/documents/SOP-001")})
    sato.post("/equipment", data={"name": "酸素濃度計", "model": "OX-100", "serial_no": "A12345", "in_use_since": "2023-04-01",
                                  "calibration_cycle_months": "12", "csrf": csrf(sato, "/equipment")})
    sato.post("/equipment", data={"name": "フルハーネス型墜落制止用器具", "model": "FH-20", "in_use_since": "2024-06-01",
                                  "calibration_cycle_months": "12", "csrf": csrf(sato, "/equipment")})
    sato.post("/equipment/1/calibration", data={"done_on": (t - timedelta(days=340)).isoformat(), "result": "合格",
                                                "csrf": csrf(sato, "/equipment")})
    sato.post("/documents/SOP-001/equipment", data={"equipment_id": "1", "csrf": csrf(sato, "/documents/SOP-001")})
    print("デモデータを投入しました。ID: " + " / ".join(u[0] for u in USERS) + f"  パスワード: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
