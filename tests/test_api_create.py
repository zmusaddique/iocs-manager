"""Tests for POST /api/iocs (create route business rules)."""

import pytest

from helpers import (
    VALID_MD5,
    VALID_SHA1,
    VALID_SHA256,
    assert_ioc_shape,
    post_ioc,
    tag_names,
)


class TestCreateSuccess:
    def test_returns_201_with_full_shape(self, client):
        response = post_ioc(client, "8.8.8.8", ["dns"])
        assert response.status_code == 201
        item = response.json()
        assert_ioc_shape(item)
        assert item["type"] == "ipv4"
        assert item["value"] == "8.8.8.8"

    def test_ids_increment_across_creates(self, client):
        first = post_ioc(client, "8.8.8.8").json()
        second = post_ioc(client, "evil.com").json()
        assert second["id"] == first["id"] + 1

    def test_each_supported_type_is_detected(self, client):
        expected = {
            "1.2.3.4": "ipv4",
            "evil.com": "domain",
            "http://evil.com/x": "url",
            VALID_MD5: "md5",
            VALID_SHA1: "sha1",
            VALID_SHA256: "sha256",
        }
        for value, wanted_type in expected.items():
            response = post_ioc(client, value)
            assert response.status_code == 201
            assert response.json()["type"] == wanted_type, value

    def test_defanged_value_is_echoed_raw_and_listed_defanged(self, client):
        item = post_ioc(client, "1.2.3[.]4").json()
        assert item["value"] == "1.2.3[.]4"  # raw, exactly as submitted
        assert item["type"] == "ipv4"
        # the listing never exposes the canonical value directly
        listed = client.get("/api/iocs").json()["items"][0]
        assert listed["value"] == "1[.]2[.]3[.]4"

    def test_hxxp_url_echoed_raw_and_listed_defanged(self, client):
        item = post_ioc(client, "hxxp://bad[.]site/x?p=1").json()
        assert item["value"] == "hxxp://bad[.]site/x?p=1"
        assert item["type"] == "url"
        listed = client.get("/api/iocs").json()["items"][0]
        assert listed["value"] == "hxxp://bad[.]site/x?p=1"

    def test_whitespace_stripped_for_canonical_but_echoed_verbatim(
        self, client
    ):
        item = post_ioc(client, "  evil.com  ").json()
        assert item["value"] == "  evil.com  "  # raw verbatim echo
        listed = client.get("/api/iocs").json()["items"][0]
        assert listed["value"] == "evil[.]com"  # canonical was trimmed

    def test_url_default_port_stripped_from_canonical_only(self, client):
        item = post_ioc(client, "HTTPS://EXAMPLE.com:443/").json()
        assert item["value"] == "HTTPS://EXAMPLE.com:443/"  # raw echo
        listed = client.get("/api/iocs").json()["items"][0]
        assert listed["value"] == "hxxps://example[.]com/"

    def test_uppercase_hash_raw_echo_lowercase_display(self, client):
        item = post_ioc(client, VALID_MD5.upper()).json()
        assert item["value"] == VALID_MD5.upper()  # raw echo keeps case
        assert item["type"] == "md5"
        listed = client.get("/api/iocs").json()["items"][0]
        assert item["type"] == listed["type"]
        # display comes from the lowercased canonical, re-chunked
        assert listed["value"] == (
            "d41d8cd9-8f00b204-e9800998-ecf8427e"
        )

    def test_created_with_no_tags(self, client):
        item = post_ioc(client, "evil.com").json()
        assert item["tags"] == []

    def test_created_with_empty_tags_list(self, client):
        item = post_ioc(client, "evil.com", []).json()
        assert item["tags"] == []

    def test_tags_normalized_lowercased_trimmed_sorted(self, client):
        item = post_ioc(
            client, "evil.com", ["Phishing", "  MALWARE  ", "malware"]
        ).json()
        assert tag_names(item) == ["malware", "phishing"]  # deduped + sorted

    def test_blank_and_overlong_tags_dropped(self, client):
        item = post_ioc(client, "evil.com", ["", "   ", "real", "x" * 65]).json()
        assert tag_names(item) == ["real"]

    def test_tags_max_length_boundary_kept(self, client):
        item = post_ioc(client, "evil.com", ["x" * 64]).json()
        assert tag_names(item) == ["x" * 64]

    def test_tags_shared_between_iocs_same_row(self, client):
        first = post_ioc(client, "8.8.8.8", ["shared"]).json()
        second = post_ioc(client, "evil.com", ["shared"]).json()
        assert first["tags"][0]["id"] == second["tags"][0]["id"]
        assert first["tags"][0]["name"] == second["tags"][0]["name"]


class TestCreateValidation:
    def test_empty_value_rejected_with_422(self, client):
        response = post_ioc(client, "")
        assert response.status_code == 422

    def test_whitespace_only_value_rejected_with_400(self, client):
        response = post_ioc(client, "   ")
        assert response.status_code == 400
        assert "Value is empty" in response.json()["detail"]

    def test_nonsense_value_rejected_with_clear_error(self, client):
        response = post_ioc(client, "not an ioc!!!")
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "Invalid IOC value" in detail
        assert "not a valid ipv4, domain, url, md5, sha1 or sha256" in detail

    def test_invalid_ipv4_rejected_with_clear_error(self, client):
        response = post_ioc(client, "999.1.2.3")
        assert response.status_code == 400
        assert "999.1.2.3" in response.json()["detail"]

    def test_breakpoint_url_rejected_with_clear_error(self, client):
        response = post_ioc(client, "http://")
        assert response.status_code == 400
        assert "no hostname" in response.json()["detail"]

    def test_too_long_value_rejected_with_400(self, client):
        response = post_ioc(client, "a" * 3000)
        assert response.status_code == 400
        assert "Value is too long" in response.json()["detail"]

    def test_huge_value_rejected_with_422(self, client):
        response = post_ioc(client, "a" * 5000)
        assert response.status_code == 422

    @pytest.mark.parametrize("body", [
        {},  # missing value
        {"value": 123},  # wrong type
        {"value": "evil.com", "tags": "notalist"},  # tags not a list
        {"value": "evil.com", "tags": [1, 2]},  # tags not strings
        {"value": "evil.com", "tags": {}},  # tags wrong container
    ])
    def test_malformed_payloads_rejected_with_422(self, client, body):
        response = client.post("/api/iocs", json=body)
        assert response.status_code == 422

    def test_missing_json_body_rejected_with_422(self, client):
        response = client.post("/api/iocs")
        assert response.status_code == 422

    def test_malformed_json_rejected_with_422(self, client):
        response = client.post(
            "/api/iocs",
            content=b"{not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestCreateDuplicates:
    def test_exact_duplicate_rejected_with_409(self, client):
        assert post_ioc(client, "evil.com").status_code == 201
        response = post_ioc(client, "evil.com")
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_duplicate_after_fanging_rejected(self, client):
        assert post_ioc(client, "1.2.3.4").status_code == 201
        response = post_ioc(client, "1.2.3[.]4")
        assert response.status_code == 409

    def test_duplicate_hash_case_insensitive(self, client):
        assert post_ioc(client, VALID_MD5).status_code == 201
        response = post_ioc(client, VALID_MD5.upper())
        assert response.status_code == 409

    def test_canonical_url_duplicate_rejected(self, client):
        assert post_ioc(client, "http://example.com:80/x").status_code == 201
        response = post_ioc(client, "HTTP://example.com/x")
        assert response.status_code == 409

    def test_duplicate_does_not_grow_the_list(self, client):
        for _ in range(3):
            post_ioc(client, "evil.com")
        assert client.get("/api/iocs").json()["total"] == 1

    def test_duplicate_tags_are_not_merged(self, client):
        post_ioc(client, "evil.com", ["one"])
        response = post_ioc(client, "evil.com", ["two"])
        assert response.status_code == 409
        listed = client.get("/api/iocs").json()["items"][0]
        assert tag_names(listed) == ["one"]


class TestMethodAndRouting:
    def test_get_single_ioc_not_supported_405(self, client):
        post_ioc(client, "evil.com")
        response = client.get("/api/iocs/1")
        assert response.status_code == 405

    def test_put_on_collection_405(self, client):
        response = client.put("/api/iocs", json={"value": "evil.com"})
        assert response.status_code == 405
