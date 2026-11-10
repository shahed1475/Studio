"""The hub's one SQLite file (data/hub/hub.db, owner-only). Standard library only.

Every row that belongs to a person carries `account_id`, and the functions that read or write such rows (here and in the modules that use this one) take the account
id as a required argument taken from the session, never from a request body. Foreign keys are on; a deleted account removes its sessions and tasks."""
import contextlib
import os
import sqlite3
import threading

import config

PATH = config.ROOT / "data" / "hub" / "hub.db"
_LOCK = threading.Lock()
_READY: set[str] = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts(
  id TEXT PRIMARY KEY, email TEXT UNIQUE, google_sub TEXT UNIQUE, name TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS login_codes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, code_hash TEXT NOT NULL, expires_at REAL NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0, used INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_codes_email ON login_codes(email, id);
CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  created_at REAL NOT NULL, last_seen REAL NOT NULL, expires_at REAL NOT NULL, ip TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS rate_hits(key TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_rate ON rate_hits(key, at);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, account_id TEXT, event TEXT NOT NULL, outcome TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '', ip TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS tasks(
  id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, agent TEXT NOT NULL, context_id TEXT NOT NULL,
  state TEXT NOT NULL, status_text TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL,
  history TEXT NOT NULL DEFAULT '[]', artifacts TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS profiles(
  account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE, niche_id TEXT NOT NULL DEFAULT '', niche_text TEXT NOT NULL DEFAULT '',
  tier TEXT NOT NULL DEFAULT '', platforms TEXT NOT NULL DEFAULT '[]', updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_tasks_acc ON tasks(account_id, context_id, updated_at);
CREATE TABLE IF NOT EXISTS sources(
  id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, url TEXT NOT NULL, title TEXT NOT NULL,
  passage TEXT NOT NULL, revised TEXT NOT NULL DEFAULT '', fetched_at REAL NOT NULL, UNIQUE(account_id, url));
CREATE TABLE IF NOT EXISTS account_keys(
  account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE, token BLOB NOT NULL, model TEXT NOT NULL, added_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS topics(
  id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, title TEXT NOT NULL,
  source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL, label TEXT NOT NULL, created_at REAL NOT NULL, UNIQUE(account_id, title));
"""


def connect() -> sqlite3.Connection:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(PATH, timeout=10, isolation_level=None)  # autocommit; transactions are explicit (tx)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    with _LOCK:
        if str(PATH) not in _READY:
            con.executescript(SCHEMA)
            os.chmod(PATH, 0o600)
            _READY.add(str(PATH))
    return con


@contextlib.contextmanager
def tx():
    """One write transaction that takes the write lock at once (no half-done changes, no lost updates)."""
    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")
        yield con
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


@contextlib.contextmanager
def read():
    """A read-only look: opens a connection and always closes it (sqlite3's own `with` only commits)."""
    con = connect()
    try:
        yield con
    finally:
        con.close()
