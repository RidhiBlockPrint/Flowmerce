"""SQLite storage. One shared connection guarded by a re-entrant lock, so the FastAPI worker threads
and the scheduler never interleave statements. Migrations are append-only: add a new entry to
MIGRATIONS, never edit an old one. The schema is identical to the earlier Node build, so an existing
data/blog-ops.sqlite keeps working."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import config

Row = dict[str, Any]

MIGRATIONS: list[str] = [
    # 1 — initial schema
    """
    CREATE TABLE users (
      id INTEGER PRIMARY KEY,
      email TEXT NOT NULL UNIQUE COLLATE NOCASE,
      name TEXT NOT NULL,
      role TEXT NOT NULL CHECK (role IN ('admin','seo_manager','reviewer')),
      password_hash TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL,
      last_login_at TEXT
    );
    CREATE TABLE sessions (
      id TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL
    );
    CREATE TABLE brand_settings (
      brand_id TEXT PRIMARY KEY,
      settings_json TEXT NOT NULL DEFAULT '{}',
      updated_at TEXT,
      updated_by INTEGER
    );
    CREATE TABLE topics (
      id INTEGER PRIMARY KEY,
      brand_id TEXT NOT NULL,
      title TEXT NOT NULL,
      primary_keyword TEXT NOT NULL,
      keyword_norm TEXT NOT NULL,
      secondary_keywords TEXT NOT NULL DEFAULT '',
      intent TEXT NOT NULL DEFAULT 'informational',
      search_volume INTEGER,
      keyword_difficulty INTEGER,
      volume_source TEXT,
      rationale TEXT NOT NULL DEFAULT '',
      notes TEXT NOT NULL DEFAULT '',
      validation_note TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'proposed',
      source TEXT NOT NULL DEFAULT 'manual',
      owner_id INTEGER,
      created_by INTEGER,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      source_updated_at TEXT,
      UNIQUE (brand_id, keyword_norm)
    );
    CREATE TABLE keywords (
      id INTEGER PRIMARY KEY,
      brand_id TEXT NOT NULL,
      keyword TEXT NOT NULL,
      keyword_norm TEXT NOT NULL,
      search_volume INTEGER,
      keyword_difficulty INTEGER,
      intent TEXT,
      source_tool TEXT NOT NULL DEFAULT 'manual',
      source_date TEXT,
      notes TEXT NOT NULL DEFAULT '',
      source TEXT NOT NULL DEFAULT 'manual',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      UNIQUE (brand_id, keyword_norm)
    );
    CREATE TABLE articles (
      id INTEGER PRIMARY KEY,
      brand_id TEXT NOT NULL,
      topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
      title TEXT NOT NULL,
      handle TEXT NOT NULL,
      primary_keyword TEXT NOT NULL DEFAULT '',
      meta_title TEXT NOT NULL DEFAULT '',
      meta_description TEXT NOT NULL DEFAULT '',
      summary_html TEXT NOT NULL DEFAULT '',
      body_html TEXT NOT NULL DEFAULT '',
      tags TEXT NOT NULL DEFAULT '',
      author TEXT NOT NULL DEFAULT '',
      image_url TEXT NOT NULL DEFAULT '',
      image_alt TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'draft',
      assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
      version INTEGER NOT NULL DEFAULT 1,
      content_hash TEXT NOT NULL DEFAULT '',
      approved_hash TEXT,
      approved_by INTEGER,
      approved_at TEXT,
      review_note TEXT NOT NULL DEFAULT '',
      shopify_blog_id TEXT,
      shopify_article_id TEXT,
      shopify_published INTEGER NOT NULL DEFAULT 0,
      live_hash TEXT,
      live_url TEXT,
      publish_at TEXT,
      published_at TEXT,
      shopify_synced_at TEXT,
      origin TEXT NOT NULL DEFAULT 'app',
      last_error TEXT,
      created_by INTEGER,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      UNIQUE (brand_id, handle)
    );
    CREATE INDEX articles_status ON articles(brand_id, status);
    CREATE TABLE article_revisions (
      id INTEGER PRIMARY KEY,
      article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
      version INTEGER NOT NULL,
      data_json TEXT NOT NULL,
      content_hash TEXT NOT NULL,
      user_id INTEGER,
      note TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL
    );
    CREATE INDEX revisions_article ON article_revisions(article_id, version);
    CREATE TABLE review_notes (
      id INTEGER PRIMARY KEY,
      article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
      user_id INTEGER,
      reviewer_name TEXT NOT NULL DEFAULT '',
      kind TEXT NOT NULL,
      note TEXT NOT NULL DEFAULT '',
      version INTEGER,
      source TEXT NOT NULL DEFAULT 'app',
      created_at TEXT NOT NULL
    );
    CREATE TABLE publish_requests (
      id INTEGER PRIMARY KEY,
      article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
      brand_id TEXT NOT NULL,
      mode TEXT NOT NULL CHECK (mode IN ('publish_now','schedule','update_live')),
      publish_at TEXT,
      content_hash TEXT NOT NULL,
      version INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      requested_by INTEGER,
      requested_at TEXT NOT NULL,
      note TEXT NOT NULL DEFAULT '',
      decided_by INTEGER,
      decided_at TEXT,
      decision_note TEXT NOT NULL DEFAULT '',
      executed_at TEXT,
      attempts INTEGER NOT NULL DEFAULT 0,
      error TEXT
    );
    CREATE TABLE workflow_runs (
      id INTEGER PRIMARY KEY,
      brand_id TEXT NOT NULL,
      stage TEXT NOT NULL,
      status TEXT NOT NULL,
      trigger_kind TEXT NOT NULL DEFAULT 'manual',
      message TEXT NOT NULL DEFAULT '',
      error TEXT,
      details_json TEXT NOT NULL DEFAULT '{}',
      user_id INTEGER,
      retry_of INTEGER,
      started_at TEXT NOT NULL,
      finished_at TEXT
    );
    CREATE INDEX runs_stage ON workflow_runs(brand_id, stage, started_at);
    CREATE TABLE automation_state (
      brand_id TEXT PRIMARY KEY,
      paused INTEGER NOT NULL DEFAULT 0,
      paused_by INTEGER,
      paused_at TEXT,
      reason TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE integration_status (
      key TEXT NOT NULL,
      brand_id TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL,
      mode TEXT NOT NULL DEFAULT '',
      last_attempt_at TEXT,
      last_success_at TEXT,
      last_error TEXT,
      details_json TEXT NOT NULL DEFAULT '{}',
      PRIMARY KEY (key, brand_id)
    );
    CREATE TABLE gsc_page_daily (
      brand_id TEXT NOT NULL,
      date TEXT NOT NULL,
      page TEXT NOT NULL,
      clicks INTEGER NOT NULL,
      impressions INTEGER NOT NULL,
      ctr REAL NOT NULL,
      position REAL NOT NULL,
      source TEXT NOT NULL,
      source_timestamp TEXT,
      imported_at TEXT NOT NULL,
      PRIMARY KEY (brand_id, source, date, page)
    );
    CREATE TABLE gsc_query_period (
      brand_id TEXT NOT NULL,
      start_date TEXT NOT NULL,
      end_date TEXT NOT NULL,
      page TEXT NOT NULL DEFAULT '',
      query TEXT NOT NULL,
      clicks INTEGER NOT NULL,
      impressions INTEGER NOT NULL,
      ctr REAL NOT NULL,
      position REAL NOT NULL,
      source TEXT NOT NULL,
      source_timestamp TEXT,
      imported_at TEXT NOT NULL,
      PRIMARY KEY (brand_id, source, start_date, end_date, page, query)
    );
    CREATE TABLE ga4_page_daily (
      brand_id TEXT NOT NULL,
      date TEXT NOT NULL,
      page_path TEXT NOT NULL,
      sessions INTEGER NOT NULL,
      engaged_sessions INTEGER NOT NULL,
      engagement_rate REAL NOT NULL,
      avg_engagement_seconds REAL NOT NULL,
      key_events REAL NOT NULL,
      source TEXT NOT NULL,
      source_timestamp TEXT,
      imported_at TEXT NOT NULL,
      PRIMARY KEY (brand_id, source, date, page_path)
    );
    CREATE TABLE products (
      brand_id TEXT NOT NULL,
      handle TEXT NOT NULL,
      title TEXT NOT NULL,
      url TEXT NOT NULL,
      image_url TEXT NOT NULL DEFAULT '',
      product_type TEXT NOT NULL DEFAULT '',
      synced_at TEXT NOT NULL,
      source TEXT NOT NULL,
      PRIMARY KEY (brand_id, handle)
    );
    CREATE TABLE audit_log (
      id INTEGER PRIMARY KEY,
      ts TEXT NOT NULL,
      user_id INTEGER,
      user_email TEXT,
      action TEXT NOT NULL,
      entity_type TEXT NOT NULL DEFAULT '',
      entity_id TEXT NOT NULL DEFAULT '',
      brand_id TEXT NOT NULL DEFAULT '',
      summary TEXT NOT NULL DEFAULT '',
      details_json TEXT NOT NULL DEFAULT '{}',
      ip TEXT
    );
    CREATE INDEX audit_ts ON audit_log(ts);
    CREATE TABLE imports (
      id INTEGER PRIMARY KEY,
      kind TEXT NOT NULL,
      filename TEXT NOT NULL,
      user_id INTEGER,
      created_at TEXT NOT NULL,
      rows_total INTEGER NOT NULL,
      inserted INTEGER NOT NULL,
      updated INTEGER NOT NULL,
      duplicates INTEGER NOT NULL,
      rejected INTEGER NOT NULL,
      errors_json TEXT NOT NULL DEFAULT '[]'
    );
    """,
]

_conn: sqlite3.Connection | None = None
_lock = threading.RLock()
_local = threading.local()


def open_db(file: str | None = None) -> sqlite3.Connection:
    global _conn
    target = file or str(config.data_dir / "blog-ops.sqlite")
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(target, check_same_thread=False, isolation_level=None)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode = WAL")
    _conn.execute("PRAGMA foreign_keys = ON")
    _conn.execute("PRAGMA busy_timeout = 5000")
    _migrate()
    return _conn


def _db() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Database is not open; call open_db() first.")
    return _conn


def _migrate() -> None:
    db = _db()
    current = db.execute("PRAGMA user_version").fetchone()[0]
    for v in range(current, len(MIGRATIONS)):
        db.execute("BEGIN")
        try:
            for stmt in [s.strip() for s in MIGRATIONS[v].split(";") if s.strip()]:
                db.execute(stmt)
            db.execute(f"PRAGMA user_version = {v + 1}")
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise


def all_rows(sql: str, *params: Any) -> list[Row]:
    with _lock:
        return [dict(r) for r in _db().execute(sql, params).fetchall()]


def get(sql: str, *params: Any) -> Row | None:
    with _lock:
        r = _db().execute(sql, params).fetchone()
        return dict(r) if r else None


class RunResult:
    __slots__ = ("changes", "last_id")

    def __init__(self, changes: int, last_id: int):
        self.changes = changes
        self.last_id = last_id


def run(sql: str, *params: Any) -> RunResult:
    with _lock:
        cur = _db().execute(sql, params)
        return RunResult(cur.rowcount, cur.lastrowid or 0)


@contextmanager
def tx() -> Iterator[None]:
    """One transaction; nested calls on the same thread join the outer one."""
    with _lock:
        depth = getattr(_local, "depth", 0)
        if depth:
            _local.depth = depth + 1
            try:
                yield
            finally:
                _local.depth = depth
            return
        _local.depth = 1
        _db().execute("BEGIN IMMEDIATE")
        try:
            yield
            _db().execute("COMMIT")
        except BaseException:
            _db().execute("ROLLBACK")
            raise
        finally:
            _local.depth = 0


def now() -> str:
    """ISO-8601 UTC with milliseconds and Z, the same format the earlier build stored."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
