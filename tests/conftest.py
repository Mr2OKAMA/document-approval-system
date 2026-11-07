import os
import re
import tempfile

os.environ["DOCMGMT_DEV"] = "1"
os.environ["DOCMGMT_DATA"] = tempfile.mkdtemp(prefix="docmgmt_test_")

import pytest
from fastapi.testclient import TestClient

PDF = b"%PDF-1.4\n%dummy test data\n"
PW = "password123"


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


def csrf(c, path="/"):
    return re.search(r'name="csrf" value="(\w+)"', c.get(path).text).group(1)


def session(app, login_id, password=PW):
    c = TestClient(app, follow_redirects=True)
    token = re.search(r'name="csrf" value="(\w+)"', c.get("/login").text).group(1)
    c.post("/login", data={"login_id": login_id, "password": password, "csrf": token})
    return c


def make_user(app, db, admin, login_id, role):
    admin.post("/users", data={"login_id": login_id, "name": login_id, "role": role,
                               "password": PW, "csrf": csrf(admin, "/users")})
    with db.connect() as conn:
        conn.execute("UPDATE users SET must_change_pw=0 WHERE login_id=?", (login_id,))


@pytest.fixture()
def team(env):
    app, db = env
    admin = session(app, "admin", "adminpass1")
    for lid, role in [("taro", "author"), ("rev1", "reviewer"), ("apr1", "approver"), ("view1", "viewer")]:
        make_user(app, db, admin, lid, role)
    return {
        "app": app, "db": db, "admin": admin,
        "author": session(app, "taro"), "reviewer": session(app, "rev1"),
        "approver": session(app, "apr1"), "viewer": session(app, "view1"),
    }


def create_draft(c, doc_no="SOP-001", reason="酸欠計の携行を追加", effective="2020-01-01", **kw):
    data = {"doc_no": doc_no, "title": "酸欠作業手順書", "category": "安全", "department": "製造",
            "review_cycle_months": "12", "change_summary": "追加", "change_reason": reason,
            "effective_date": effective, "csrf": csrf(c, "/submit")}
    data.update(kw)
    return c.post("/submit", data=data, files={"file": ("a.pdf", PDF, "application/pdf")})


def act(c, rev_id, action, decision="approve", comment=""):
    return c.post(f"/revisions/{rev_id}/{action}",
                  data={"decision": decision, "comment": comment, "csrf": csrf(c, "/tasks")})


def approve_all(t, rev_id):
    t["author"].post(f"/revisions/{rev_id}/submit", data={"csrf": csrf(t["author"], f"/revisions/{rev_id}")})
    act(t["reviewer"], rev_id, "review")
    act(t["approver"], rev_id, "approve")
