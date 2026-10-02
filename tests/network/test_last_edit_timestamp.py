"""
Unit tests for src/xtools/client.py

Class under test: XToolsClient
"""

from __future__ import annotations
from datetime import datetime

import pytest

from src.config import Settings
from src.xtools.client import XToolsClient
from src.wiki.client import WikiClient

@pytest.mark.network
def test_last_edit_timestamp_xtoolsclient() -> None:
    result = XToolsClient().last_edit_timestamp("Mr. Ibrahem")
    assert result == "2026-10-02"


@pytest.mark.network
def test_last_edit_timestamp_wikiclient():
    settings = Settings.from_env(".env")
    assert settings.credentials is not None
    assert settings.credentials.username != "WIKIPEDIA_BOT_USERNAME"

    site = WikiClient.load(settings=settings, host="meta.wikimedia.org", login=True)
    assert site is not None

    result = site.last_edit_timestamp("Mr. Ibrahem")
    assert result == "2026-10-02"

def test_timestamp_format():
    assert datetime.strptime("20261002", "%Y%m%d").strftime("%Y-%m-%d") == "2026-10-02"
