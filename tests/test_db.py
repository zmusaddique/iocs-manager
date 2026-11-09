"""Tests for the SQLite schema, constraints, and cascade behavior (db.py)."""

import sqlite3

import pytest

from ioc_watchlist import db as db_module
from ioc_watchlist.db import connect, init_schema


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
        cur = conn.execute(
            "INSERT INTO iocs (value, type) VALUES ('evil.com', 'domain')"
        )
        row = conn.execute(
            "SELECT created_at FROM iocs WHERE id = ?", (cur.lastrowid,)
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
        conn.execute("INSERT INTO iocs (value, type) VALUES ('a.com', 'domain')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO iocs (value, type) VALUES ('a.com', 'domain')"
            )
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
        cur = conn.execute(
            "INSERT INTO iocs (value, type) VALUES ('a.com', 'domain')"
        )
        conn.execute("INSERT INTO tags (name) VALUES ('x')")
        conn.execute(
            "INSERT INTO ioc_tags (ioc_id, tag_id) VALUES (?, 1)",
            (cur.lastrowid,),
        )
        conn.execute(
            "INSERT OR IGNORE INTO ioc_tags (ioc_id, tag_id) VALUES (?, 1)",
            (cur.lastrowid,),
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
        cur = conn.execute(
            "INSERT INTO iocs (value, type) VALUES ('a.com', 'domain')"
        )
        ioc_id = cur.lastrowid
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
        cur = conn.execute(
            "INSERT INTO iocs (value, type) VALUES ('a.com', 'domain')"
        )
        conn.execute("INSERT INTO tags (name) VALUES ('t1')")
        conn.execute(
            "INSERT INTO ioc_tags (ioc_id, tag_id) VALUES (?, 1)",
            (cur.lastrowid,),
        )
        conn.execute("DELETE FROM tags WHERE id = 1")
        (links,) = conn.execute("SELECT COUNT(*) FROM ioc_tags").fetchone()
        conn.close()
        assert links == 0


class TestModuleDbPath:
    def test_db_path_default_env(self, monkeypatch):
        monkeypatch.delenv("IOC_WATCHLIST_DB", raising=False)
        assert "/" not in db_module.DB_PATH
        assert db_module.DB_PATH.endswith(".db")
