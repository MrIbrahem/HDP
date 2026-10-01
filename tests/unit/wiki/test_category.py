# ruff: noqa: F401
"""
Unit tests for src/wiki/category.py module.

Classes to test: CategoryService

TODO: write tests
"""
import pytest
from unittest.mock import MagicMock
from src.wiki.category import CategoryService


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.wiki.category.time.sleep", MagicMock())
