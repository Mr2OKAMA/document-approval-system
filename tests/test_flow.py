import re

import pytest
from fastapi.testclient import TestClient

PDF = b"%PDF-1.4\n%dummy test data\n"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    from app import db

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    from app.main import app

    db.init_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO users(login_id,name,role,password_hash,created_at) VALUES(?,?,?,?,?)",
            ("admin", "管理者", "admin", db.hash_password("adminpass1"), db.now()),
        )
    return app, db


def session(app, login_id, password):
    c = TestClient(app, follow_redirects=True)
    token = re.search(r'name="csrf" value="(\w+)"', c.get("/login").text).group(1)
    c.post("/login", data={"login_id": login_id, "password": password, "csrf": token})
    return c


def csrf(c, path="/"):
    return re.search(r'name="csrf" value="(\w+)"', c.get(path).text).group(1)


def make_user(admin, login_id, role):
    admin.post("/users", data={"login_id": login_id, "name": login_id, "role": role,
                               "password": "password123", "csrf": csrf(admin, "/users")})


def submit(c, doc_no="SOP-001", reason="酸欠計の携行を追加"):
    return c.post("/submit", data={"doc_no": doc_no, "title": "酸欠作業手順書", "change_summary": "追加",
                                   "change_reason": reason, "effective_date": "2026-12-01",
                                   "csrf": csrf(c, "/submit")},
                  files={"file": ("a.pdf", PDF, "application/pdf")})


def test_account_submit_approve(env):
    app, db = env
    admin = session(app, "admin", "adminpass1")
    make_user(admin, "taro", "author")
    make_user(admin, "hanako", "approver")
    make_user(admin, "viewer1", "viewer")

    author = session(app, "taro", "password123")
    r = submit(author)
    assert "SOP-001 Rev.0 を申請しました" in r.text

    viewer = session(app, "viewer1", "password123")
    assert "SOP-001" not in viewer.get("/").text  # 未承認は見えない

    appr = session(app, "hanako", "password123")
    assert "SOP-001" in appr.get("/approvals").text
    appr.post("/approvals/1", data={"decision": "approve", "csrf": csrf(appr, "/approvals")})
    assert "SOP-001" in viewer.get("/").text
    assert viewer.get("/revisions/1/file").content == PDF

    with db.connect() as conn:
        assert db.verify_audit_chain(conn)


def test_self_approval_blocked(env):
    app, db = env
    admin = session(app, "admin", "adminpass1")
    make_user(admin, "both", "approver")
    with db.connect() as conn:
        conn.execute("UPDATE users SET role='approver' WHERE login_id='both'")
    # 承認者は申請できない
    c = session(app, "both", "password123")
    assert c.get("/submit").status_code == 403


def test_reason_required_and_reject(env):
    app, db = env
    admin = session(app, "admin", "adminpass1")
    make_user(admin, "taro", "author")
    make_user(admin, "hanako", "approver")
    author = session(app, "taro", "password123")
    assert "必須" in submit(author, reason=" ").text or "入力" in submit(author, reason=" ").text
    submit(author)
    appr = session(app, "hanako", "password123")
    r = appr.post("/approvals/1", data={"decision": "reject", "comment": "", "csrf": csrf(appr, "/approvals")})
    assert "コメントが必要" in r.text
    appr.post("/approvals/1", data={"decision": "reject", "comment": "写真不足", "csrf": csrf(appr, "/approvals")})
    assert "差戻し" in author.get("/documents/SOP-001").text


def test_approved_revision_immutable_and_log_append_only(env):
    import sqlite3

    app, db = env
    admin = session(app, "admin", "adminpass1")
    make_user(admin, "taro", "author")
    make_user(admin, "hanako", "approver")
    author = session(app, "taro", "password123")
    submit(author)
    appr = session(app, "hanako", "password123")
    appr.post("/approvals/1", data={"decision": "approve", "csrf": csrf(appr, "/approvals")})
    with db.connect() as conn:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("UPDATE revisions SET change_reason='x' WHERE id=1")
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM audit_log")


def test_csrf_and_login_required(env):
    app, _ = env
    c = TestClient(app, follow_redirects=False)
    assert c.get("/").status_code == 303
    admin = session(app, "admin", "adminpass1")
    assert admin.post("/users", data={"login_id": "x", "name": "x", "role": "viewer",
                                      "password": "password123", "csrf": "bad"}).status_code == 403


def test_non_admin_cannot_manage_users(env):
    app, _ = env
    admin = session(app, "admin", "adminpass1")
    make_user(admin, "taro", "author")
    assert session(app, "taro", "password123").get("/users").status_code == 403
