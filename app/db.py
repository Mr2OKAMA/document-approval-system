import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("DOCMGMT_DATA", "data"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY,
  login_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','author','approver','viewer')),
  password_hash TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents(
  id INTEGER PRIMARY KEY,
  doc_no TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions(
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id),
  rev_no INTEGER NOT NULL,
  file_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  change_summary TEXT NOT NULL,
  change_reason TEXT NOT NULL,
  effective_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('申請中','承認済','差戻し')),
  submitted_by INTEGER NOT NULL REFERENCES users(id),
  submitted_at TEXT NOT NULL,
  decided_by INTEGER REFERENCES users(id),
  decided_at TEXT,
  decision_comment TEXT,
  UNIQUE(document_id, rev_no)
);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT NOT NULL,
  detail TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS rev_no_delete BEFORE DELETE ON revisions
BEGIN SELECT RAISE(ABORT, 'revisions cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS rev_decided_immutable BEFORE UPDATE ON revisions
WHEN OLD.status <> '申請中'
BEGIN SELECT RAISE(ABORT, 'decided revisions are immutable'); END;
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "files").mkdir(exist_ok=True)
    conn = sqlite3.connect(DATA_DIR / "app.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, dk = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
    except ValueError:
        return False
    return hmac.compare_digest(calc.hex(), dk)


def _entry_hash(prev: str, ts: str, actor: str, action: str, target: str, detail: str) -> str:
    return hashlib.sha256("|".join([prev, ts, actor, action, target, detail]).encode()).hexdigest()


def log(conn: sqlite3.Connection, actor: str, action: str, target: str, detail: str = "") -> None:
    """Append to the hash-chained audit log (caller commits)."""
    row = conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev = row["hash"] if row else "0" * 64
    ts = now()
    conn.execute(
        "INSERT INTO audit_log(ts,actor,action,target,detail,prev_hash,hash) VALUES(?,?,?,?,?,?,?)",
        (ts, actor, action, target, detail, prev, _entry_hash(prev, ts, actor, action, target, detail)),
    )


def verify_audit_chain(conn: sqlite3.Connection) -> bool:
    prev = "0" * 64
    for r in conn.execute("SELECT * FROM audit_log ORDER BY id"):
        if r["prev_hash"] != prev:
            return False
        if r["hash"] != _entry_hash(prev, r["ts"], r["actor"], r["action"], r["target"], r["detail"]):
            return False
        prev = r["hash"]
    return True
