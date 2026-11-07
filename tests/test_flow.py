import sqlite3

import pytest
from fastapi.testclient import TestClient

from .conftest import PDF, act, approve_all, create_draft, csrf, make_user, session


def test_full_flow_and_visibility(team):
    t = team
    assert "下書きを作成しました" in create_draft(t["author"]).text
    assert "SOP-001" not in t["viewer"].get("/documents").text  # 未承認は見えない
    assert t["viewer"].get("/revisions/1").status_code == 404
    t["author"].post("/revisions/1/submit", data={"csrf": csrf(t["author"], "/revisions/1")})
    assert "SOP-001" in t["reviewer"].get("/tasks").text
    assert act(t["approver"], 1, "approve").status_code == 403  # 確認前に承認不可
    act(t["reviewer"], 1, "review")
    assert "SOP-001" in t["approver"].get("/tasks").text
    assert act(t["reviewer"], 1, "approve").status_code == 403  # 確認者は承認不可
    act(t["approver"], 1, "approve")
    assert "SOP-001" in t["viewer"].get("/documents").text
    assert t["viewer"].get("/revisions/1/file").content == PDF
    with t["db"].connect() as conn:
        assert t["db"].verify_audit_chain(conn)
        assert conn.execute("SELECT status FROM revisions WHERE id=1").fetchone()[0] == "承認済"


def test_reject_returns_to_draft_and_resubmit(team):
    t = team
    create_draft(t["author"])
    t["author"].post("/revisions/1/submit", data={"csrf": csrf(t["author"], "/revisions/1")})
    assert "コメントが必要" in act(t["reviewer"], 1, "review", "reject", "").text
    act(t["reviewer"], 1, "review", "reject", "写真不足")
    assert "写真不足" in t["author"].get("/tasks").text
    r = t["author"].post("/revisions/1/edit", data={"change_summary": "写真追加", "change_reason": "指摘対応",
                                                     "effective_date": "2020-02-05", "csrf": csrf(t["author"], "/revisions/1")})
    assert "更新しました" in r.text
    approve_all(t, 1)
    page = t["author"].get("/revisions/1").text
    assert "写真不足" in page and "承認済" in page  # 経過が残る


def test_new_revision_supersedes_old(team, monkeypatch):
    t = team
    create_draft(t["author"], effective="2020-01-01")
    approve_all(t, 1)
    assert "適用中の版なし" not in t["viewer"].get("/documents").text
    pass
    create_draft(t["author"], reason="酸欠計を追加", effective="2999-01-01")
    approve_all(t, 2)
    assert "Rev.0" in t["viewer"].get("/documents").text  # 未来の適用開始日までは旧版が現行
    import datetime
    monkeypatch.setattr(t["db"], "today", lambda: datetime.date(2999, 1, 2))
    assert "Rev.1" in t["viewer"].get("/documents").text
    with t["db"].connect() as conn:
        assert conn.execute("SELECT status FROM revisions WHERE id=1").fetchone()[0] == "廃版"


def test_one_open_revision_per_document_and_reason_required(team):
    t = team
    assert "必須" in create_draft(t["author"], reason=" ").text
    create_draft(t["author"])
    assert "未完了の申請" in create_draft(t["author"], reason="again").text
    t["author"].post("/revisions/1/withdraw", data={"comment": "誤り", "csrf": csrf(t["author"], "/revisions/1")})
    assert "下書きを作成しました" in create_draft(t["author"], reason="again").text


def test_submit_blocked_without_reviewer(env):
    app, db = env
    admin = session(app, "admin", "adminpass1")
    make_user(app, db, admin, "taro", "author")
    a = session(app, "taro")
    create_draft(a)
    r = a.post("/revisions/1/submit", data={"csrf": csrf(a, "/revisions/1")})
    assert "確認者がいません" in r.text


def test_db_immutability(team):
    t = team
    create_draft(t["author"])
    approve_all(t, 1)
    with t["db"].connect() as conn:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("UPDATE revisions SET change_reason='x' WHERE id=1")
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("UPDATE revisions SET status='下書き' WHERE id=1")
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM revisions")
        for tbl in ("audit_log", "approvals"):
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(f"DELETE FROM {tbl}")


def test_ack_training_and_checks(team):
    t = team
    create_draft(t["author"], effective="2020-01-01")
    approve_all(t, 1)
    checks = t["admin"].get("/checks").text
    assert "教育・周知の実施記録がありません" in checks and "未確認者" in checks
    assert "SOP-001" in t["viewer"].get("/acks").text
    t["viewer"].post("/revisions/1/ack", data={"csrf": csrf(t["viewer"], "/acks")})
    assert "あなたは確認済み" in t["viewer"].get("/revisions/1").text
    t["author"].post("/revisions/1/training", data={"held_on": "2021-02-01", "trainer": "安全担当", "attendees": "全員",
                                                    "csrf": csrf(t["author"], "/revisions/1")})
    assert "教育実施日が適用開始日より後" in t["admin"].get("/checks").text
    assert t["viewer"].post("/revisions/1/training", data={"held_on": "2020-01-01", "trainer": "a", "attendees": "b",
                                                           "csrf": csrf(t["viewer"], "/acks")}).status_code == 403


def test_equipment_and_checks(team):
    t = team
    c = t["author"]
    c.post("/equipment", data={"name": "酸欠計A", "model": "X1", "in_use_since": "2024-04-01",
                               "calibration_cycle_months": "12", "csrf": csrf(c, "/equipment")})
    assert "校正記録がありません" in t["admin"].get("/checks").text
    c.post("/equipment/1/calibration", data={"done_on": "2020-01-01", "result": "合格", "csrf": csrf(c, "/equipment")})
    assert "校正期限(2021-01-01)を超過" in t["admin"].get("/checks").text
    create_draft(c)
    c.post("/documents/SOP-001/equipment", data={"equipment_id": "1", "csrf": csrf(c, "/documents/SOP-001")})
    assert "酸欠計A" in c.get("/documents/SOP-001").text
    assert t["viewer"].get("/equipment").status_code == 403


def test_links_review_and_abolish(team):
    t = team
    create_draft(t["author"], effective="2020-01-01")
    approve_all(t, 1)
    create_draft(t["author"], doc_no="FRM-001")
    a = t["author"]
    a.post("/documents/SOP-001/links", data={"to_doc_no": "FRM-001", "note": "様式", "csrf": csrf(a, "/documents/SOP-001")})
    assert "FRM-001" in a.get("/documents/SOP-001").text
    r = t["approver"].post("/documents/SOP-001/reviews", data={"reviewed_on": "2021-03-01", "result": "変更なし",
                                                              "csrf": csrf(t["approver"], "/documents/SOP-001")})
    assert "見直し結果を記録" in r.text
    assert "廃止理由" in t["approver"].post("/documents/SOP-001/abolish", data={"reason": "", "csrf": csrf(t["approver"], "/documents/SOP-001")}).text
    t["approver"].post("/documents/SOP-001/abolish", data={"reason": "作業廃止", "csrf": csrf(t["approver"], "/documents/SOP-001")})
    assert "SOP-001" not in t["viewer"].get("/documents").text
    assert t["viewer"].get("/documents/SOP-001").status_code == 404
    assert "廃止" in t["approver"].get("/documents?show=abolished").text


def test_exports_and_formula_escape(team):
    t = team
    create_draft(t["author"], reason="=cmd|' /C calc'!A0")
    for kind in ("register", "revisions", "approvals", "acks", "trainings", "equipment"):
        for fmt in ("csv", "xlsx"):
            assert t["approver"].get(f"/export/{kind}.{fmt}").status_code == 200
    csv_text = t["approver"].get("/export/revisions.csv").content.decode("utf-8-sig")
    assert "'=cmd" in csv_text
    assert t["approver"].get("/export/audit.csv").status_code == 403
    assert t["admin"].get("/export/audit.csv").status_code == 200
    assert t["viewer"].get("/export/register.csv").status_code == 403


def test_accounts_must_change_password_and_lockout(env):
    app, db = env
    admin = session(app, "admin", "adminpass1")
    admin.post("/users", data={"login_id": "new1", "name": "新人", "role": "viewer", "password": "initpass1",
                               "csrf": csrf(admin, "/users")})
    c = session(app, "new1", "initpass1")
    assert "パスワードの変更が必要" in c.get("/").text
    c.post("/password", data={"current": "initpass1", "new": "mynewpass9", "csrf": csrf(c, "/password")})
    assert "ホーム" in c.get("/").text
    for _ in range(5):
        session(app, "new1", "wrong")
    assert "ホーム" not in session(app, "new1", "mynewpass9").get("/").text  # 正しいパスワードでもロック中は不可
    admin.post("/users/2/unlock", data={"csrf": csrf(admin, "/users")})
    assert "ホーム" in session(app, "new1", "mynewpass9").get("/").text


def test_access_control_and_csrf(team):
    t = team
    anon = TestClient(t["app"], follow_redirects=False)
    assert anon.get("/").status_code == 303
    assert t["admin"].post("/users", data={"login_id": "x", "name": "x", "role": "viewer", "password": "password123",
                                           "csrf": "bad"}).status_code == 403
    for path in ("/users", "/audit"):
        assert t["author"].get(path).status_code == 403
    assert t["viewer"].get("/submit").status_code == 403
    assert t["admin"].post("/users/1/role", data={"role": "viewer", "csrf": csrf(t["admin"], "/users")}).status_code == 200
    with t["db"].connect() as conn:
        assert conn.execute("SELECT role FROM users WHERE id=1").fetchone()[0] == "admin"  # 自分の役割は変更不可


def test_tamper_detection(team):
    t = team
    create_draft(t["author"], effective="2020-01-01")
    approve_all(t, 1)
    next(t["db"].DATA_DIR.joinpath("files").glob("*.pdf")).write_bytes(b"%PDF tampered")
    assert t["viewer"].get("/revisions/1/file").status_code == 500
    assert "ハッシュ不一致" in t["admin"].get("/checks").text
