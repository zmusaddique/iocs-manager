"""Tests for DELETE /api/iocs/{id} (delete route business rules)."""

import sqlite3

import pytest

from ioc_watchlist.db import connect

from helpers import post_ioc, tag_names


class TestDelete:
    def test_returns_204_no_content(self, client):
        ioc_id = post_ioc(client, "evil.com").json()["id"]
        response = client.delete(f"/api/iocs/{ioc_id}")
        assert response.status_code == 204
        assert response.content == b""

    def test_deleted_ioc_gone_from_list(self, client):
        post_ioc(client, "8.8.8.8")
        evil_id = post_ioc(client, "evil.com").json()["id"]
        post_ioc(client, "1.2.3.4")

        assert client.delete(f"/api/iocs/{evil_id}").status_code == 204
        data = client.get("/api/iocs")
        assert data.json()["total"] == 2
        assert all(i["id"] != evil_id for i in data.json()["items"])

    def test_delete_missing_id_returns_404(self, client):
        response = client.delete("/api/iocs/9999")
        assert response.status_code == 404
        assert "9999" in response.json()["detail"]

    def test_delete_non_integer_id_returns_422(self, client):
        response = client.delete("/api/iocs/not-a-number")
        assert response.status_code == 422

    def test_second_delete_of_same_id_404(self, client):
        ioc_id = post_ioc(client, "evil.com").json()["id"]
        assert client.delete(f"/api/iocs/{ioc_id}").status_code == 204
        assert client.delete(f"/api/iocs/{ioc_id}").status_code == 404

    def test_recreate_same_value_after_delete(self, client):
        first = post_ioc(client, "evil.com", ["old"]).json()
        client.delete(f"/api/iocs/{first['id']}")
        response = post_ioc(client, "evil.com", ["new"])
        assert response.status_code == 201
        assert response.json()["id"] > first["id"]
        assert tag_names(response.json()) == ["new"]

    def test_delete_is_scoped_to_target(self, client):
        a = post_ioc(client, "8.8.8.8").json()
        b = post_ioc(client, "evil.com").json()
        client.delete(f"/api/iocs/{a['id']}")
        remaining = client.get("/api/iocs").json()["items"]
        assert [i["id"] for i in remaining] == [b["id"]]


class TestDeleteCascades:
    def test_junction_rows_removed_but_tag_rows_survive(self, client, tmp_db_path):
        ioc_id = post_ioc(client, "evil.com", ["tag-a"]).json()["id"]
        client.delete(f"/api/iocs/{ioc_id}")

        conn = sqlite3.connect(tmp_db_path)
        (links,) = conn.execute(
            "SELECT COUNT(*) FROM ioc_tags WHERE ioc_id = ?", (ioc_id,)
        ).fetchone()
        (tags,) = conn.execute("SELECT COUNT(*) FROM tags").fetchone()
        conn.close()
        assert links == 0
        assert tags == 1  # tag row deliberately retained

    def test_shared_tag_survives_on_sibling_ioc(self, client):
        post_ioc(client, "8.8.8.8", ["shared"])
        b = post_ioc(client, "evil.com", ["shared"]).json()
        client.delete(f"/api/iocs/{b['id']}")
        survivor = client.get("/api/iocs").json()["items"][0]
        assert tag_names(survivor) == ["shared"]

    def test_delete_keeps_others_with_same_tag_listable(
        self, client, tmp_db_path
    ):
        post_ioc(client, "8.8.8.8", ["keep"])
        doomed = post_ioc(client, "evil.com", ["keep"]).json()
        client.delete(f"/api/iocs/{doomed['id']}")
        data = client.get("/api/iocs?tags=keep").json()
        assert data["total"] == 1
        assert data["items"][0]["value"] == "8[.]8[.]8[.]8"

    def test_connect_helper_reads_patched_db(self, tmp_db_path, client):
        # sanity: connect() (used in other tests) reads the patched DB path,
        # i.e. this test also proves route writes land in tmp_db_path's file.
        post_ioc(client, "evil.com")
        conn = connect()
        rows = conn.execute("SELECT COUNT(*) FROM iocs").fetchone()
        conn.close()
        assert rows[0] == 1
