"""
Unit tests for src/xtools/client.py module.

Classes to test: XToolsClient
"""

from unittest.mock import MagicMock

import pytest

from src.xtools.client import XToolsClient


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.xtools.client.time.sleep", MagicMock())


@pytest.mark.network
def test_get_recent_editcount() -> None:
    start_s, end_s = XToolsClient.load_dates()
    result = XToolsClient().recent_editcount_by_day("Arpitha05", start_s, end_s)
    assert result == {}


@pytest.mark.network
def test_get_recent_editcount_m() -> None:
    result = XToolsClient().recent_editcount_by_day("Mr. Ibrahem", "2026-05-10", "2026-05-12")
    assert result == {"2026-05-10": 6}
