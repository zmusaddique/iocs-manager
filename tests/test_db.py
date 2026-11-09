"""Tests for the SQLite schema, constraints, and cascade behavior (db.py)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from ioc_watchlist import db as db_module
from ioc_watchlist.db import connect, init_schema


def insert_ioc(conn, value, ioc_type="domain", raw_value=None):
    """Insert an IOC row honoring the raw_value column; returns its id."""
    cur = conn.execute(
        "INSERT INTO iocs (value, raw_value, type) VALUES (?, ?, ?)",
        (value, raw_value if raw_value is not None else value, ioc_type),
    )
    return cur.lastrowid


class TestSchemaInit:
    def test_init_creates_tables(self, tmp_db_path):
        init_schema()
        conn = sqlite3.connect(tmp_db_path)
        names = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        conn.close()
        assert {"iocs", "tags", "ioc_tags"} <= names

    def test_init_is_idempotent(self, tmp_db_path):
        init_schema()
        init_schema()  # must not raise

    def test_created_at_default_populated(self, tmp_db_path):
        import re

        init_schema()
        conn = connect()
        cur = insert_ioc(conn, "evil.com")
        row = conn.execute(
            "SELECT created_at FROM iocs WHERE id = ?", (cur,)
        ).fetchone()
        conn.close()
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", row[0])


class TestConnection:
    def test_row_factory_is_sqlite_row(self, tmp_db_path):
        init_schema()
        conn = connect()
        row = conn.execute("SELECT 1 AS one").fetchone()
        conn.close()
        assert row["one"] == 1

    def test_foreign_keys_pragma_on(self, tmp_db_path):
        init_schema()
        conn = connect()
        (value,) = conn.execute("PRAGMA foreign_keys").fetchone()
        conn.close()
        assert value == 1


class TestConstraints:
    def test_ioc_value_unique(self, tmp_db_path):
        init_schema()
        conn = connect()
        insert_ioc(conn, "a.com")
        with pytest.raises(sqlite3.IntegrityError):
            insert_ioc(conn, "a.com")
        conn.close()

    def test_tag_name_unique_case_insensitive(self, tmp_db_path):
        init_schema()
        conn = connect()
        conn.execute("INSERT INTO tags (name) VALUES ('Malware')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO tags (name) VALUES ('MALWARE')")
        conn.close()

    def test_junction_rejects_unknown_ioc(self, tmp_db_path):
        init_schema()
        conn = connect()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO ioc_tags (ioc_id, tag_id) VALUES (999, 1)"
            )
        conn.close()

    def test_junction_primary_key_prevents_duplicate_links(self, tmp_db_path):
        init_schema()
        conn = connect()
        ioc_id = insert_ioc(conn, "a.com")
        conn.execute("INSERT INTO tags (name) VALUES ('x')")
        conn.execute(
            "INSERT INTO ioc_tags (ioc_id, tag_id) VALUES (?, 1)", (ioc_id,)
        )
        conn.execute(
            "INSERT OR IGNORE INTO ioc_tags (ioc_id, tag_id) VALUES (?, 1)",
            (ioc_id,),
        )
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM ioc_tags"
        ).fetchone()
        conn.close()
        assert count == 1


class TestCascade:
    def test_deleting_ioc_removes_junction_rows_only(self, tmp_db_path):
        init_schema()
        conn = connect()
        ioc_id = insert_ioc(conn, "a.com")
        conn.execute("INSERT INTO tags (name) VALUES ('t1')")
        conn.execute(
            "INSERT INTO ioc_tags (ioc_id, tag_id) VALUES (?, 1)", (ioc_id,)
        )

        conn.execute("DELETE FROM iocs WHERE id = ?", (ioc_id,))

        (links,) = conn.execute("SELECT COUNT(*) FROM ioc_tags").fetchone()
        (tags,) = conn.execute("SELECT COUNT(*) FROM tags").fetchone()
        conn.close()
        assert links == 0  # junction row cascaded away
        assert tags == 1  # tag row itself survives

    def test_deleting_tag_only_frees_links(self, tmp_db_path):
        init_schema()
        conn = connect()
        ioc_id = insert_ioc(conn, "a.com")
        conn.execute("INSERT INTO tags (name) VALUES ('t1')")
        conn.execute(
            "INSERT INTO ioc_tags (ioc_id, tag_id) VALUES (?, 1)",
            (ioc_id,),
        )
        conn.execute("DELETE FROM tags WHERE id = 1")
        (links,) = conn.execute("SELECT COUNT(*) FROM ioc_tags").fetchone()
        conn.close()
        assert links == 0


class TestRawValueColumn:
    """Business rule: raw input and canonical value are stored together."""

    def test_raw_and_canonical_stored_distinct(self, tmp_db_path):
        init_schema()
        conn = connect()
        ioc_id = insert_ioc(conn, "1.2.3.4", "ipv4", raw_value="1.2.3[.]4")
        row = conn.execute(
            "SELECT value, raw_value FROM iocs WHERE id = ?", (ioc_id,)
        ).fetchone()
        conn.close()
        assert row["value"] == "1.2.3.4"  # canonical (uniqueness key)
        assert row["raw_value"] == "1.2.3[.]4"  # raw as submitted

    def test_uniqueness_stays_on_canonical_not_raw(self, tmp_db_path):
        init_schema()
        conn = connect()
        insert_ioc(conn, "1.2.3.4", "ipv4", raw_value="clean")
        with pytest.raises(sqlite3.IntegrityError):
            insert_ioc(conn, "1.2.3.4", "ipv4", raw_value="1.2.3[.]4")
        conn.close()


LEGACY_SCHEMA = """
CREATE TABLE iocs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    value TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE ioc_tags (
    ioc_id INTEGER NOT NULL REFERENCES iocs(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (ioc_id, tag_id)
);
"""


def make_legacy_db(path: str) -> None:
    """Build a pre-raw_value database (the old app's schema) with data."""
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    conn.execute("INSERT INTO iocs (value, type) VALUES ('legacy.com', 'domain')")
    conn.execute("INSERT INTO iocs (value, type) VALUES ('8.8.8.8', 'ipv4')")
    conn.commit()
    conn.close()


class TestLegacyMigration:
    def test_migrate_adds_raw_value_and_backfills(self, tmp_db_path):
        make_legacy_db(tmp_db_path)
        init_schema()  # runs the migration
        conn = sqlite3.connect(tmp_db_path)
        raws = dict(conn.execute("SELECT value, raw_value FROM iocs"))
        conn.close()
        assert raws == {"legacy.com": "legacy.com", "8.8.8.8": "8.8.8.8"}

    def test_migrate_is_idempotent(self, tmp_db_path):
        make_legacy_db(tmp_db_path)
        init_schema()
        init_schema()  # second run must not duplicate or fail

    def test_migrated_db_serves_api_contract(self, monkeypatch, tmp_path):
        path = str(tmp_path / "test.db")
        monkeypatch.setattr(db_module, "DB_PATH", path)
        make_legacy_db(path)

        from ioc_watchlist.main import app

        with TestClient(app) as client:  # lifespan performs the migration
            data = client.get("/api/iocs").json()
            assert data["total"] == 2
            values = {i["value"] for i in data["items"]}
            # legacy rows get re-defanged like any other canonical value
            assert values == {"legacy[.]com", "8[.]8[.]8[.]8"}
            for item in data["items"]:
                assert set(item.keys()) == {
                    "id", "value", "type", "tags", "created_at"
                }  # no raw/canonical leakage

            # the write path works on the migrated schema
            resp = client.post(
                "/api/iocs", json={"value": "phish[.]example[.]net"}
            )
            assert resp.status_code == 201
            assert resp.json()["value"] == "phish[.]example[.]net"

        conn = sqlite3.connect(path)
        raws = dict(conn.execute("SELECT value, raw_value FROM iocs"))
        conn.close()
        assert raws["phish.example.net"] == "phish[.]example[.]net"
        assert raws["legacy.com"] == "legacy.com"  # backfill untouched


class TestModuleDbPath:
    def test_db_path_default_env(self, monkeypatch):
        monkeypatch.delenv("IOC_WATCHLIST_DB", raising=False)
        assert "/" not in db_module.DB_PATH
        assert db_module.DB_PATH.endswith(".db")
