"""Contract tests: raw echo on create, re-defanged values on list.

Business rules under test:
- POST /api/iocs echoes the raw input exactly as the user submitted it.
- GET /api/iocs serves values re-defanged from the canonical value/hash;
  neither the raw input nor the canonical value is exposed in listings.
- Uniqueness is enforced on the canonical value across every raw spelling,
  and raw_value keeps the first submission's spelling.
"""

import sqlite3

import pytest

from helpers import VALID_MD5, post_ioc, tag_names


class TestCreateEchoesRaw:
    def test_raw_echo_verbatim_all_types(self, client):
        raw_inputs = [
            "8.8.8.8",
            "1.2.3[.]4",
            "  evil.com  ",
            "hxxps://bad[.]site/gate[.]php",
            "d41d-8cd9-8f00-b204-e980-0998-ecf8-427e",  # chunked md5 input
        ]
        for raw in raw_inputs:
            response = post_ioc(client, raw)
            assert response.status_code == 201
            # value in the POST response is the raw submission, untouched
            assert response.json()["value"] == raw

    def test_post_response_never_takes_the_canonical_value(self, client):
        body = post_ioc(client, "1[.]2[.]3[.]4", ["aux"]).json()
        assert body["value"] == "1[.]2[.]3[.]4"
        assert body["value"] != "1.2.3.4"  # canonical never echoed
        assert tag_names(body) == ["aux"]


class TestListServesRedefanged:
    @pytest.mark.parametrize(("submitted", "displayed"), [
        ("8.8.8.8", "8[.]8[.]8[.]8"),
        ("evil.com", "evil[.]com"),
        ("1[.]2[.]3[.]4", "1[.]2[.]3[.]4"),  # defang-stable round trip
        ("1.2.3[.]4", "1[.]2[.]3[.]4"),  # mixed raw forms -> single display
        ("http://c2.example.org/a", "hxxp://c2[.]example[.]org/a"),
        ("https://c2.example.org:8443/p?a=1#b",
         "hxxps://c2[.]example[.]org:8443/p?a=1#b"),
        ("ftp://files.example.com/pub/f.csv",
         "ftp://files[.]example[.]com/pub/f[.]csv"),
        (VALID_MD5,
         "d41d8cd9-8f00b204-e9800998-ecf8427e"),  # re-chunked with hyphens
    ])
    def test_listing_redefangs_from_canonical(self, client, submitted,
                                              displayed):
        assert post_ioc(client, submitted).status_code == 201
        data = client.get("/api/iocs").json()
        assert data["total"] == 1
        assert data["items"][0]["value"] == displayed

    def test_listing_exposes_neither_raw_nor_canonical_field(self, client):
        post_ioc(client, "1.2.3[.]4", ["mal"])
        item = client.get("/api/iocs").json()["items"][0]
        assert set(item.keys()) == {"id", "value", "type", "tags",
                                    "created_at"}
        assert item["value"] == "1[.]2[.]3[.]4"

    def test_url_query_and_fragment_dots_are_defanged(self, client):
        post_ioc(client, "http://c2.com/p?x.y=1#f.rag")
        item = client.get("/api/iocs").json()["items"][0]
        assert item["value"] == "hxxp://c2[.]com/p?x[.]y=1#f[.]rag"

    def test_listing_tags_and_types_unchanged(self, client):
        post_ioc(client, "evil.com", ["Phishing"])
        item = client.get("/api/iocs").json()["items"][0]
        assert item["type"] == "domain"
        assert tag_names(item) == ["phishing"]


class TestRawWinsFirstEntry:
    def test_single_canonical_row_across_raw_spellings(self, client,
                                                       tmp_db_path):
        assert post_ioc(client, "8.8.8.8").status_code == 201
        assert post_ioc(client, "8.8.8[.]8").status_code == 409
        assert post_ioc(client, "8[.]8[.]8[.]8").status_code == 409
        assert client.get("/api/iocs").json()["total"] == 1

        conn = sqlite3.connect(tmp_db_path)
        raws = conn.execute("SELECT raw_value FROM iocs").fetchall()
        conn.close()
        assert len(raws) == 1
        assert raws[0][0] == "8.8.8.8"  # first submission wins

    def test_first_entry_raw_survives_defangle_duplicates(self, client,
                                                          tmp_db_path):
        chunked = "d41d8cd9 8f00b204 e9800998 ecf8427e"
        assert post_ioc(client, chunked).status_code == 201
        assert post_ioc(client, VALID_MD5).status_code == 409

        conn = sqlite3.connect(tmp_db_path)
        raws = conn.execute("SELECT raw_value FROM iocs").fetchall()
        conn.close()
        assert len(raws) == 1
        assert raws[0][0] == chunked
