"""Quota ledger.

Tracks what each backend has consumed in the current quota window so the router
never starts a job it cannot finish. Kaggle's GPU and TPU quotas reset weekly at
Saturday 00:00 UTC; Modal's credit resets monthly.

In-flight runs are counted at their *estimated* cost, so two concurrent
schedulers can't both decide there's room for the same last hour.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from typing import Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    backend       TEXT    NOT NULL,
    accelerator   TEXT    NOT NULL,          -- gpu | tpu | cpu
    job_kind      TEXT    NOT NULL,
    job_key       TEXT,                      -- idempotency key
    external_id   TEXT,                      -- e.g. user/kernel-slug
    status        TEXT    NOT NULL,           -- running | complete | error | cancelled
    est_hours     REAL    NOT NULL DEFAULT 0,
    actual_hours  REAL,
    cost_usd      REAL    NOT NULL DEFAULT 0,
    started_at    TEXT    NOT NULL,
    ended_at      TEXT,
    notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_window ON runs (backend, accelerator, started_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_job_key ON runs (job_key) WHERE job_key IS NOT NULL;
"""


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def kaggle_week_start(now: Optional[dt.datetime] = None) -> dt.datetime:
    """Most recent Saturday 00:00 UTC -- when Kaggle's weekly quota resets."""
    now = now or utcnow()
    days_since_saturday = (now.weekday() - 5) % 7  # Mon=0 .. Sat=5, Sun=6
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - dt.timedelta(days=days_since_saturday)


def month_start(now: Optional[dt.datetime] = None) -> dt.datetime:
    now = now or utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


@dataclass
class Usage:
    used_hours: float
    limit_hours: float

    @property
    def remaining_hours(self) -> float:
        return max(0.0, self.limit_hours - self.used_hours)


def _used_hours(conn, backend: str, accelerator: str, since: dt.datetime) -> float:
    """Finished runs count their real duration; running ones count their estimate."""
    row = conn.execute(
        """
        SELECT COALESCE(SUM(
            CASE WHEN status = 'running' THEN est_hours
                 ELSE COALESCE(actual_hours, est_hours) END
        ), 0) AS h
        FROM runs
        WHERE backend = ? AND accelerator = ?
          AND status != 'cancelled'
          AND started_at >= ?
        """,
        (backend, accelerator, since.isoformat()),
    ).fetchone()
    return float(row["h"])


def kaggle_usage(accelerator: str = "gpu", conn=None) -> Usage:
    own = conn is None
    conn = conn or connect()
    try:
        limit = (
            config.KAGGLE_GPU_WEEKLY_HOURS
            if accelerator == "gpu"
            else config.KAGGLE_TPU_WEEKLY_HOURS
        )
        return Usage(_used_hours(conn, "kaggle", accelerator, kaggle_week_start()), limit)
    finally:
        if own:
            conn.close()


def modal_spend_usd(conn=None) -> float:
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(cost_usd), 0) AS c FROM runs
            WHERE backend = 'modal' AND status != 'cancelled' AND started_at >= ?
            """,
            (month_start().isoformat(),),
        ).fetchone()
        return float(row["c"])
    finally:
        if own:
            conn.close()


def modal_remaining_usd(conn=None) -> float:
    return max(0.0, config.MODAL_MONTHLY_CREDIT_USD - modal_spend_usd(conn))


def start_run(
    backend: str,
    accelerator: str,
    job_kind: str,
    est_hours: float,
    job_key: Optional[str] = None,
    external_id: Optional[str] = None,
) -> int:
    """Reserve quota. Returns the run id, or raises if job_key was already used."""
    conn = connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO runs (backend, accelerator, job_kind, job_key, external_id,
                              status, est_hours, started_at)
            VALUES (?, ?, ?, ?, ?, 'running', ?, ?)
            """,
            (backend, accelerator, job_kind, job_key, external_id,
             est_hours, utcnow().isoformat()),
        )
        return int(cur.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise DuplicateJob(f"job_key {job_key!r} already recorded") from exc
    finally:
        conn.close()


def finish_run(
    run_id: int,
    status: str = "complete",
    actual_hours: Optional[float] = None,
    cost_usd: float = 0.0,
    notes: Optional[str] = None,
) -> None:
    conn = connect()
    try:
        if actual_hours is None:
            row = conn.execute("SELECT started_at FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row:
                started = dt.datetime.fromisoformat(row["started_at"])
                actual_hours = (utcnow() - started).total_seconds() / 3600.0
        conn.execute(
            """
            UPDATE runs SET status = ?, actual_hours = ?, cost_usd = ?,
                            ended_at = ?, notes = COALESCE(?, notes)
            WHERE id = ?
            """,
            (status, actual_hours, cost_usd, utcnow().isoformat(), notes, run_id),
        )
    finally:
        conn.close()


def set_external_id(run_id: int, external_id: str) -> None:
    conn = connect()
    try:
        conn.execute("UPDATE runs SET external_id = ? WHERE id = ?", (external_id, run_id))
    finally:
        conn.close()


def reap_stale(max_hours: float = config.KAGGLE_MAX_GPU_SESSION_HOURS + 1) -> int:
    """Close out runs that outlived any possible session, so they stop holding quota."""
    conn = connect()
    try:
        cutoff = (utcnow() - dt.timedelta(hours=max_hours)).isoformat()
        cur = conn.execute(
            """
            UPDATE runs SET status = 'error', ended_at = ?,
                            notes = COALESCE(notes, '') || ' [reaped: exceeded session limit]'
            WHERE status = 'running' AND started_at < ?
            """,
            (utcnow().isoformat(), cutoff),
        )
        return cur.rowcount
    finally:
        conn.close()


def report() -> str:
    gpu, tpu = kaggle_usage("gpu"), kaggle_usage("tpu")
    lines = [
        f"Kaggle GPU : {gpu.used_hours:5.2f} / {gpu.limit_hours:.0f} h used"
        f"  ({gpu.remaining_hours:.2f} left, resets {kaggle_week_start() + dt.timedelta(days=7):%a %d %b %H:%M} UTC)",
        f"Kaggle TPU : {tpu.used_hours:5.2f} / {tpu.limit_hours:.0f} h used"
        f"  ({tpu.remaining_hours:.2f} left)",
        f"Modal      : ${modal_spend_usd():5.2f} / ${config.MODAL_MONTHLY_CREDIT_USD:.0f} credit used"
        f"  (${modal_remaining_usd():.2f} left this month)",
    ]
    return "\n".join(lines)


class DuplicateJob(RuntimeError):
    """Raised when a job_key has already been recorded -- the idempotency guard."""
