"""Tests for the static HTML/JS pages and the /static mount."""

import pytest


class TestPages:
    def test_home_serves_create_form(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert 'id="ioc-form"' in response.text
        assert 'id="value"' in response.text
        assert 'id="add-tag-btn"' in response.text
        assert 'href="/iocs"' in response.text  # navbar to list page

    def test_home_has_tag_suggestion_markup(self, client):
        html = client.get("/").text
        assert 'id="tag-suggestions"' in html
        assert 'id="tag-input"' in html
        # shared suggester loads before the page script that uses it
        assert '<script src="/static/js/tag-suggest.js">' in html
        assert html.index("tag-suggest.js") < html.index("create.js")

    def test_tag_suggest_js_queries_tags_endpoint(self, client):
        js = client.get("/static/js/tag-suggest.js").text
        assert "/api/tags" in js  # suggestions come from the tags endpoint
        assert "listEl" in js  # reused, input-agnostic popup machinery

    def test_iocs_page_serves_list_with_filters_and_delete(self, client):
        response = client.get("/iocs")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert 'id="ioc-rows"' in response.text
        assert 'id="filter-type"' in response.text
        assert 'id="filter-tags"' in response.text
        assert 'href="/"' in response.text  # navbar back to home

    def test_iocs_page_has_tag_suggestion_markup(self, client):
        html = client.get("/iocs").text
        assert 'id="tag-suggestions"' in html
        assert '<script src="/static/js/tag-suggest.js">' in html
        assert html.index("tag-suggest.js") < html.index("list.js")

    def test_iocs_page_has_match_mode_toggle(self, client):
        html = client.get("/iocs").text
        assert 'id="filter-tag-mode"' in html
        assert '<option value="all" selected>all of the tags</option>' in html
        assert '<option value="any">any of the tags</option>' in html

    def test_list_js_sends_match_mode(self, client):
        js = client.get("/static/js/list.js").text
        assert "all_tags" in js
        assert 'filterTagMode.value === "any"' in js


class TestStaticMount:
    def test_create_js_served(self, client):
        response = client.get("/static/js/create.js")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/javascript")
        assert "/api/iocs" in response.text

    def test_list_js_served(self, client):
        response = client.get("/static/js/list.js")
        assert response.status_code == 200
        assert "DELETE" in response.text

    def test_missing_static_file_404(self, client):
        assert client.get("/static/nope.txt").status_code == 404

    def test_unknown_path_404(self, client):
        assert client.get("/totally/unrelated").status_code == 404


class TestCacheRevalidation:
    """Browsers must revalidate pages/assets so deploys can't be masked by
    stale cached files (that is exactly how the tag-suggestion feature
    appeared broken on already-visited pages)."""

    @pytest.mark.parametrize("path", ["/", "/iocs"])
    def test_pages_force_revalidation(self, client, path):
        response = client.get(path)
        assert response.headers["cache-control"] == "no-cache"

    @pytest.mark.parametrize("path", [
        "/static/js/tag-suggest.js",
        "/static/js/create.js",
        "/static/js/list.js",
    ])
    def test_static_assets_force_revalidation(self, client, path):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
