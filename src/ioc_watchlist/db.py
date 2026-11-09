import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("IOC_WATCHLIST_DB", "ioc_watchlist.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS iocs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    value      TEXT NOT NULL UNIQUE,
    raw_value  TEXT NOT NULL,
    type       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS ioc_tags (
    ioc_id INTEGER NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (ioc_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_iocs_type ON iocs(type);
CREATE INDEX IF NOT EXISTS idx_ioc_tags_tag_id ON ioc_tags(tag_id);
"""


def connect(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(db_path: str | None = None) -> None:
    conn = sqlite3.connect(db_path or DB_PATH)
    try:
        conn.executescript(SCHEMA)
        # Legacy DBs (created before raw_value existed): add the column and
        # backfill it from the canonical value so old rows keep working.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(iocs)")}
        if "raw_value" not in columns:
            conn.execute("ALTER TABLE iocs ADD COLUMN raw_value TEXT")
            conn.execute(
                "UPDATE iocs SET raw_value = value WHERE raw_value IS NULL"
            )
            conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
