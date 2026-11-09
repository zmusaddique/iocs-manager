"""Shared fixtures for the ioc-watchlist test suite.

Reusable constants/helpers live in tests/helpers.py.
"""

import pytest
from fastapi.testclient import TestClient

from ioc_watchlist import db as db_module


@pytest.fixture
def tmp_db_path(monkeypatch, tmp_path) -> str:
    """Point the app's DB_PATH global at a per-test SQLite file."""
    path = str(tmp_path / "test.db")
    monkeypatch.setattr(db_module, "DB_PATH", path)
    return path


@pytest.fixture
def client(tmp_db_path):
    """FastAPI TestClient backed by a fresh, empty per-test DB.

    Used as a context manager so the app's lifespan (schema creation) runs.
    """
    from ioc_watchlist.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def second_client(tmp_db_path, client):
    """A second TestClient on the same DB file, simulating an app restart.

    Depends on `client` only so tmp_db_path and the initial schema exist.
    """
    from ioc_watchlist.main import app

    with TestClient(app) as test_client:
        yield test_client
