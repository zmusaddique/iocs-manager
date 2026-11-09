"""Shared constants and helpers for API tests (importable as `helpers`)."""

VALID_MD5 = "d41d8cd98f00b204e9800998ecf8427e"
VALID_SHA1 = "2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b"
VALID_SHA256 = (
    "308940cde82f58f21d3d80d0d16f23b8e5d1cb2ce9a6b0a5e64b3d13a58f2c19"
)


def post_ioc(client, value, tags=None):
    """POST an IOC, omitting `tags` entirely when not given."""
    body = {"value": value}
    if tags is not None:
        body["tags"] = tags
    return client.post("/api/iocs", json=body)


def assert_ioc_shape(item):
    """Assert the exact IOCRead response contract."""
    assert set(item.keys()) == {"id", "value", "type", "tags", "created_at"}
    assert isinstance(item["id"], int)
    assert isinstance(item["value"], str)
    assert isinstance(item["type"], str)
    assert isinstance(item["tags"], list)
    assert isinstance(item["created_at"], str)
    for tag in item["tags"]:
        assert set(tag.keys()) == {"id", "name"}


def tag_names(item):
    """The tag names of an IOCRead response item, in response order."""
    return [t["name"] for t in item["tags"]]
