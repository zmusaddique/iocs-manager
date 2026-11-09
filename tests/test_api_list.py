"""Tests for GET /api/iocs (list route with type and tag filters)."""

import pytest

from helpers import post_ioc, tag_names


@pytest.fixture
def populated(client):
    """Plants a known dataset and returns the plain list response items."""
    post_ioc(client, "8.8.8.8", ["malware", "dns"])
    post_ioc(client, "evil.com", ["phishing"])
    post_ioc(client, "d41d8cd98f00b204e9800998ecf8427e", ["malware"])
    post_ioc(client, "http://c2.example.org/a", ["phishing", "c2"])
    return client.get("/api/iocs").json()["items"]


class TestListAll:
    def test_empty_db_returns_empty_list(self, client):
        data = client.get("/api/iocs").json()
        assert data == {"items": [], "total": 0}

    def test_all_items_returned_with_total(self, client, populated):
        data = client.get("/api/iocs").json()
        assert data["total"] == 4
        assert len(data["items"]) == 4

    def test_newest_first_ordering(self, client, populated):
        ids = [item["id"] for item in populated]
        assert ids == sorted(ids, reverse=True)

    def test_items_carry_detected_type_and_tags(self, client, populated):
        by_type = {"ipv4", "domain", "md5", "url"}
        assert {item["type"] for item in populated} == by_type
        first_tags = tag_names(populated[-1])
        assert first_tags == ["dns", "malware"]

    def test_unknown_query_params_are_ignored(self, client, populated):
        data = client.get("/api/iocs?foo=bar").json()
        assert data["total"] == 4


class TestTypeFilter:
    @pytest.mark.parametrize(("wanted_type", "expected_value"), [
        ("ipv4", "8[.]8[.]8[.]8"),
        ("domain", "evil[.]com"),
        ("md5", "d41d8cd9-8f00b204-e9800998-ecf8427e"),
        ("url", "hxxp://c2[.]example[.]org/a"),
    ])
    def test_filter_by_type(self, populated, client, wanted_type, expected_value):
        data = client.get(f"/api/iocs?type={wanted_type}").json()
        assert data["total"] == 1
        assert data["items"][0]["value"] == expected_value
        assert data["items"][0]["type"] == wanted_type

    def test_filter_with_no_matches(self, client, populated):
        data = client.get("/api/iocs?type=sha256").json()
        assert data == {"items": [], "total": 0}

    def test_unknown_type_rejected_with_clear_error(self, client):
        response = client.get("/api/iocs?type=bogus")
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "Supported types" in detail
        for supported in ("ipv4", "domain", "url", "md5", "sha1", "sha256"):
            assert supported in detail


class TestTagsFilter:
    def test_single_tag(self, client, populated):
        data = client.get("/api/iocs?tags=phishing").json()
        assert data["total"] == 2

    def test_multiple_tags_require_all_and_semantics(self, client):
        # ioc1: [a, b]; ioc2: [a]; ioc3: [b] -> only ioc1 has both
        post_ioc(client, "8.8.8.8", ["a", "b"])
        post_ioc(client, "evil.com", ["a"])
        post_ioc(client, "1.1.1.1", ["b"])
        data = client.get("/api/iocs?tags=a,b").json()
        assert data["total"] == 1
        assert data["items"][0]["value"] == "8[.]8[.]8[.]8"

    def test_tag_filter_case_insensitive(self, client, populated):
        data = client.get("/api/iocs?tags=MALWARE").json()
        assert data["total"] == 2

    def test_tag_filter_tolerates_spaces(self, client, populated):
        data = client.get("/api/iocs?tags=%20malware%20").json()
        assert data["total"] == 2

    def test_unknown_tag_matches_nothing(self, client, populated):
        data = client.get("/api/iocs?tags=nonexistent").json()
        assert data == {"items": [], "total": 0}

    def test_empty_tags_param_is_not_a_filter(self, client, populated):
        assert client.get("/api/iocs?tags=").json()["total"] == 4
        assert client.get("/api/iocs?tags=,,,").json()["total"] == 4

    def test_type_and_tags_combined(self, client, populated):
        data = client.get("/api/iocs?type=ipv4&tags=malware,dns").json()
        assert data["total"] == 1
        assert data["items"][0]["value"] == "8[.]8[.]8[.]8"

    def test_type_and_tag_excluding_each_other(self, client, populated):
        data = client.get("/api/iocs?type=domain&tags=malware").json()
        assert data == {"items": [], "total": 0}
