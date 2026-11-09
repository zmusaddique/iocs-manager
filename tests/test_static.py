"""Tests for the static HTML/JS pages and the /static mount."""


class TestPages:
    def test_home_serves_create_form(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert 'id="ioc-form"' in response.text
        assert 'id="value"' in response.text
        assert 'id="add-tag-btn"' in response.text
        assert 'href="/iocs"' in response.text  # navbar to list page

    def test_iocs_page_serves_list_with_filters_and_delete(self, client):
        response = client.get("/iocs")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert 'id="ioc-rows"' in response.text
        assert 'id="filter-type"' in response.text
        assert 'id="filter-tags"' in response.text
        assert 'href="/"' in response.text  # navbar back to home


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
