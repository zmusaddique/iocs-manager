"""End-to-end business workflows crossing the routes, plus persistence."""

from helpers import VALID_MD5, post_ioc, tag_names


def _json_url_item(resp):
    return resp.json()["items"][0]["value"]


class TestAnalystWorkflows:
    def test_triage_flow_create_filter_delete_recreate(self, client):
        # 1. Analyst adds a batch of IOCs with tags
        ids = {
            post_ioc(client, "203.0.113.66", ["c2", "apt"]).json()["id"],
            post_ioc(client, "phish[.]example[.]net", ["phishing"]).json()["id"],
            post_ioc(client, "hxxp://203.0.113.66:8080/gate.php", ["c2"]).json()["id"],
            post_ioc(client, VALID_MD5, ["malware"]).json()["id"],
        }
        assert len(ids) == 4

        # 2. List page shows everything, newest first
        data = client.get("/api/iocs").json()
        assert data["total"] == 4
        values = [i["value"] for i in data["items"]]
        assert "phish[.]example[.]net" in values  # re-defanged from canonical
        # hyphen-chunked hash display: 8 hex chars per block
        assert any(v.count("-") == 3 for v in values)  # the md5
        assert "hxxp://203[.]0[.]113[.]66:8080/gate[.]php" in values

        # 3. Filter by tag + type for a campaign search
        c2_urls = client.get("/api/iocs?type=url&tags=c2").json()
        assert c2_urls["total"] == 1
        assert "gate[.]php" in c2_urls["items"][0]["value"]

        # 4. Delete the phished domain after takedown
        phish = client.get("/api/iocs?type=domain").json()["items"][0]
        assert client.delete(f"/api/iocs/{phish['id']}").status_code == 204
        assert client.get("/api/iocs").json()["total"] == 3

        # 5. IOC returns in the wild -> re-enter it successfully
        again = post_ioc(client, "phish.example.net", ["phishing"])
        assert again.status_code == 201
        assert again.json()["id"] > max(ids)

    def test_tags_act_as_many_to_many(self, client):
        # One tag, two IOCs -> single tag row shared by both links
        a = post_ioc(client, "8.8.8.8", ["campaign-x"]).json()
        b = post_ioc(client, "evil.com", ["campaign-x", "y"]).json()
        assert a["tags"][0]["id"] == b["tags"][0]["id"]

        # Filter finds each IOC independently
        assert client.get("/api/iocs?tags=campaign-x").json()["total"] == 2

        # Deleting one IOC doesn't break the other
        client.delete(f"/api/iocs/{a['id']}")
        assert client.get("/api/iocs?tags=campaign-x").json()["total"] == 1
        assert _json_url_item(
            client.get("/api/iocs?tags=campaign-x")
        ) == "evil[.]com"

    def test_invalid_input_never_pollutes_the_list(self, client):
        post_ioc(client, "8.8.8.8", ["good"])
        for bad in ("nope", "999.1.2.3", "http://", "", "   ", "g" * 64):
            assert post_ioc(client, bad).status_code in (400, 422)
        data = client.get("/api/iocs").json()
        assert data["total"] == 1

    def test_tag_normalization_consistent_everywhere(self, client):
        post_ioc(client, "8.8.8.8", ["  DNS  "])
        post_ioc(client, "evil.com", ["dns"])
        data = client.get("/api/iocs?tags=DNS").json()
        assert data["total"] == 2
        item = data["items"][0]
        assert tag_names(item) == ["dns"]


class TestPersistenceAcrossRestart:
    def plant(self, client):
        assert post_ioc(client, "8.8.8.8", ["dns", "MAL"]).status_code == 201

    def test_data_survives_new_client_on_same_db(self, client, second_client):
        self.plant(client)
        # `second_client` starts its own lifespan on the client fixture's
        # DB file: schema init must be idempotent and the data must persist.
        data = second_client.get("/api/iocs").json()
        assert data["total"] == 1
        assert data["items"][0]["value"] == "8[.]8[.]8[.]8"  # re-defanged
        assert tag_names(data["items"][0]) == ["dns", "mal"]

        followup = post_ioc(second_client, "evil.com")
        assert followup.status_code == 201  # write path still works

    def test_schema_reinit_does_not_duplicate_data(self, client, second_client):
        self.plant(client)
        assert second_client.get("/api/iocs").json()["total"] == 1
        assert second_client.get("/api/iocs").json()["items"][0][
            "type"
        ] == "ipv4"
