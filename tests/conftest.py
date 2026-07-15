"""Shared pytest fixtures."""

import pytest

from src.database import F1Database


@pytest.fixture
def test_db_path(tmp_path):
    return tmp_path / "test_f1.db"


@pytest.fixture
def test_db(test_db_path):
    db = F1Database(test_db_path)
    db.initialize()
    return db
