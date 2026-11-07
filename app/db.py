import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("DOCMGMT_DATA", "data"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY,
  login_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','author','reviewer','approver','viewer')),
  password_hash TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  must_change_pw INTEGER NOT NULL DEFAULT 0,
  failed_count INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents(
  id INTEGER PRIMARY KEY,
  doc_no TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT '',
  department TEXT NOT NULL DEFAULT '',
  review_cycle_months INTEGER NOT NULL DEFAULT 12,
  created_at TEXT NOT NULL,
  abolished_at TEXT,
  abolished_by INTEGER REFERENCES users(id),
  abolished_reason TEXT
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
  status TEXT NOT NULL CHECK(status IN ('下書き','確認待ち','承認待ち','承認済','廃版','取下げ')),
  created_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  approved_at TEXT,
  obsoleted_at TEXT,
  UNIQUE(document_id, rev_no)
);
CREATE TABLE IF NOT EXISTS approvals(
  id INTEGER PRIMARY KEY,
  revision_id INTEGER NOT NULL REFERENCES revisions(id),
  step TEXT NOT NULL CHECK(step IN ('提出','確認','承認','取下げ')),
  decision TEXT NOT NULL CHECK(decision IN ('提出','承認','差戻し','取下げ')),
  user_id INTEGER NOT NULL REFERENCES users(id),
  comment TEXT NOT NULL DEFAULT '',
  sha256 TEXT NOT NULL,
  decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS acknowledgements(
  id INTEGER PRIMARY KEY,
  revision_id INTEGER NOT NULL REFERENCES revisions(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  acknowledged_at TEXT NOT NULL,
  UNIQUE(revision_id, user_id)
);
CREATE TABLE IF NOT EXISTS trainings(
  id INTEGER PRIMARY KEY,
  revision_id INTEGER NOT NULL REFERENCES revisions(id),
  held_on TEXT NOT NULL,
  trainer TEXT NOT NULL,
  attendees TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  recorded_by INTEGER NOT NULL REFERENCES users(id),
  recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS doc_reviews(
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id),
  reviewed_on TEXT NOT NULL,
  result TEXT NOT NULL CHECK(result IN ('変更なし','改訂が必要')),
  comment TEXT NOT NULL DEFAULT '',
  reviewed_by INTEGER NOT NULL REFERENCES users(id),
  recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS equipment(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  model TEXT NOT NULL DEFAULT '',
  serial_no TEXT NOT NULL DEFAULT '',
  in_use_since TEXT NOT NULL,
  calibration_cycle_months INTEGER NOT NULL DEFAULT 12,
  calibration_due TEXT,
  note TEXT NOT NULL DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calibrations(
  id INTEGER PRIMARY KEY,
  equipment_id INTEGER NOT NULL REFERENCES equipment(id),
  done_on TEXT NOT NULL,
  due_on TEXT NOT NULL,
  result TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  recorded_by INTEGER NOT NULL REFERENCES users(id),
  recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS doc_equipment(
  document_id INTEGER NOT NULL REFERENCES documents(id),
  equipment_id INTEGER NOT NULL REFERENCES equipment(id),
  PRIMARY KEY(document_id, equipment_id)
);
CREATE TABLE IF NOT EXISTS doc_links(
  from_id INTEGER NOT NULL REFERENCES documents(id),
  to_id INTEGER NOT NULL REFERENCES documents(id),
  note TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(from_id, to_id)
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
"""

APPEND_ONLY = ["audit_log", "approvals", "acknowledgements", "trainings", "doc_reviews", "calibrations"]


def _triggers() -> str:
    parts = []
    for t in APPEND_ONLY:
        for op in ("UPDATE", "DELETE"):
            parts.append(
                f"CREATE TRIGGER IF NOT EXISTS {t}_no_{op.lower()} BEFORE {op} ON {t} "
                f"BEGIN SELECT RAISE(ABORT, '{t} is append-only'); END;"
            )
    parts.append(
        "CREATE TRIGGER IF NOT EXISTS rev_no_delete BEFORE DELETE ON revisions "
        "BEGIN SELECT RAISE(ABORT, 'revisions cannot be deleted'); END;"
    )
    parts.append(
        "CREATE TRIGGER IF NOT EXISTS rev_final_lock BEFORE UPDATE ON revisions "
        "WHEN OLD.status IN ('廃版','取下げ') "
        "BEGIN SELECT RAISE(ABORT, 'finished revisions are immutable'); END;"
    )
    parts.append(
        "CREATE TRIGGER IF NOT EXISTS rev_approved_lock BEFORE UPDATE ON revisions "
        "WHEN OLD.status='承認済' AND NEW.status<>'廃版' "
        "BEGIN SELECT RAISE(ABORT, 'approved revisions are immutable'); END;"
    )
    parts.append(
        "CREATE TRIGGER IF NOT EXISTS rev_content_lock BEFORE UPDATE ON revisions "
        "WHEN OLD.status<>'下書き' AND (NEW.file_path<>OLD.file_path OR NEW.sha256<>OLD.sha256 "
        "OR NEW.change_summary<>OLD.change_summary OR NEW.change_reason<>OLD.change_reason "
        "OR NEW.effective_date<>OLD.effective_date OR NEW.rev_no<>OLD.rev_no "
        "OR NEW.document_id<>OLD.document_id) "
        "BEGIN SELECT RAISE(ABORT, 'revision content is locked after submission'); END;"
    )
    return "\n".join(parts)


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today() -> date:
    return date.today()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "files").mkdir(exist_ok=True)
    conn = sqlite3.connect(DATA_DIR / "app.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA + _triggers())
        conn.commit()
    finally:
        conn.close()


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
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")  # serialize writers so the hash chain stays linear
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
