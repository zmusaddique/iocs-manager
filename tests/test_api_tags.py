"""Tests for GET /api/tags, powering the home-page tag suggestion popup."""

from helpers import post_ioc


def tag_names_of(client, q=None):
    url = "/api/tags" + (f"?q={q}" if q is not None else "")
    return client.get(url).json()["tags"]


class TestTagListing:
    def test_no_tags_yet(self, client):
        assert tag_names_of(client) == []

    def test_returns_sorted_existing_tags(self, client):
        post_ioc(client, "8.8.8.8", ["phishing", "dns"])
        post_ioc(client, "evil.com", ["malware", "dns", "apt"])
        assert tag_names_of(client) == ["apt", "dns", "malware", "phishing"]

    def test_tag_shared_by_iocs_listed_once(self, client):
        post_ioc(client, "8.8.8.8", ["shared"])
        post_ioc(client, "evil.com", ["Shared "])
        assert tag_names_of(client) == ["shared"]

    def test_unknown_ioc_filters_do_not_leak_tag_names(self, client):
        post_ioc(client, "evil.com", ["hidden"])
        # the endpoint is pure tag listing; unrelated params are just ignored
        assert tag_names_of(client) == ["hidden"]


class TestTagSuggestionFilter:
    def test_substring_match(self, client):
        post_ioc(client, "8.8.8.8", ["malware", "apt-2024"])
        assert tag_names_of(client, "ware") == ["malware"]  # mid-word match
        assert tag_names_of(client, "apt") == ["apt-2024"]

    def test_filter_case_insensitive(self, client):
        post_ioc(client, "8.8.8.8", ["malware"])
        assert tag_names_of(client, "WARE") == ["malware"]
        assert tag_names_of(client, "MaL") == ["malware"]

    def test_filter_no_match(self, client):
        post_ioc(client, "8.8.8.8", ["malware"])
        assert tag_names_of(client, "ransom") == []

    def test_filter_results_stay_sorted_and_filtered(self, client):
        post_ioc(client, "8.8.8.8", ["malware", "maldoc", "apt"])
        assert tag_names_of(client, "mal") == ["maldoc", "malware"]

    def test_whitespace_q_treated_as_no_filter(self, client):
        post_ioc(client, "8.8.8.8", ["malware"])
        assert tag_names_of(client, "   ") == ["malware"]
