"""
Unit tests for src/xtools/client.py module.

Classes to test: XToolsClient

TODO: write tests
"""

import pytest

from src.xtools.client import (
    XToolsClient,
)

@pytest.mark.network
def test_get_recent_editcount() -> None:
    start_s, end_s = XToolsClient.load_dates()
    result = XToolsClient().recent_editcount_by_day("Arpitha05", start_s, end_s)
    assert result == {}


@pytest.mark.network
def test_get_recent_editcount_m() -> None:
    result = XToolsClient().recent_editcount_by_day("Mr. Ibrahem", "2026-05-10", "2026-05-12")
    assert result == {"2026-05-10": 6}
