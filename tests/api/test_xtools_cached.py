""" """

import pytest

from src.api.xtools_cached import _get_recent_editcount, get_recent_editcount_cached, load_dates


@pytest.mark.network
def test_get_recent_editcount() -> None:
    start_s, end_s = load_dates()
    result = _get_recent_editcount("Arpitha05", start_s, end_s)
    assert result == {}


@pytest.mark.network
def test_get_recent_editcount_cached() -> None:
    start_s, end_s = load_dates()
    result = get_recent_editcount_cached("Arpitha05", start_s, end_s, {"_meta": {}})
    assert result is None


@pytest.mark.network
def test_get_recent_editcount_m() -> None:
    result = _get_recent_editcount("Mr. Ibrahem", "2026-05-10", "2026-05-12")
    assert result == {"2026-05-10": 6}
