# ruff: noqa: F401
"""
Unit tests for src/xtools/client.py

Class under test: XToolsClient
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.xtools.client import XToolsClient

@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    m = MagicMock()
    monkeypatch.setattr("src.xtools.client.time.sleep", m)
    return m

class TestRealNetwork:
    @pytest.mark.network
    def test_get_recent_editcount(self) -> None:
        start_s, end_s = XToolsClient.load_dates()
        result = XToolsClient().recent_editcount_by_day("Arpitha05", start_s, end_s)
        assert result == {}


    @pytest.mark.network
    def test_get_recent_editcount_m(self) -> None:
        result = XToolsClient().recent_editcount_by_day("Mr. Ibrahem", "2026-05-10", "2026-05-12")
        assert result == {"2026-05-10": 6}


    @pytest.mark.network
    def test_last_edit_timestamp(self) -> None:
        result = XToolsClient().last_edit_timestamp("Mr. Ibrahem")
        assert result == "2026-10-02"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client() -> XToolsClient:
    return XToolsClient(user_agent="test-agent", timeout=5)


def _contrib(ts: str) -> dict:
    """Minimal globalcontribs entry."""
    return {"timestamp": ts}


def _ok_response(payload: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = str(payload)
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return resp


def _error_response(text: str = "error", status: int = 500) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.raise_for_status.side_effect = requests.HTTPError(text)
    return resp


# ===========================================================================
# load_dates
# ===========================================================================


class TestLoadDates:
    def test_returns_iso_strings(self):
        start, end = XToolsClient.load_dates(recent_days=90)
        date.fromisoformat(start)
        date.fromisoformat(end)

    def test_end_is_yesterday(self):
        fixed_today = date(2026, 9, 30)

        start, end = XToolsClient.load_dates(recent_days=90, today=fixed_today)

        assert end == "2026-09-29"
        assert start == "2026-07-01"  # 2026-09-29 - 90 days

    def test_custom_recent_days(self):
        fixed_today = date(2026, 10, 1)  # date, not datetime

        start, end = XToolsClient.load_dates(recent_days=7, today=fixed_today)

        assert end == "2026-09-30"
        assert start == "2026-09-23"  # 2026-09-30 - 7 days

    def test_accepts_datetime_and_normalises_to_date(self):
        """Optional: only if load_dates coerces datetime → date."""
        fixed_today = datetime(2026, 10, 1, 15, 30, 0, tzinfo=UTC)

        start, end = XToolsClient.load_dates(recent_days=7, today=fixed_today.date())

        assert end == "2026-09-30"
        assert start == "2026-09-23"
        assert "T" not in start and "T" not in end


# ===========================================================================
# recent_editcount_by_day
# ===========================================================================


class TestRecentEditcountByDay:
    @patch("src.xtools.client.requests.get")
    def test_aggregates_per_day(self, mock_get):
        mock_get.return_value = _ok_response(
            {
                "globalcontribs": [
                    _contrib("2026-05-10T09:00:00Z"),
                    _contrib("2026-05-10T11:00:00Z"),
                    _contrib("2026-05-11T08:00:00Z"),
                ]
            }
        )
        client = _client()
        result = client.recent_editcount_by_day("Alice", "2026-05-10", "2026-05-12")

        assert result == {"2026-05-10": 2, "2026-05-11": 1}

    @patch("src.xtools.client.requests.get")
    def test_empty_contribs_returns_empty_dict(self, mock_get):
        mock_get.return_value = _ok_response({"globalcontribs": []})
        client = _client()

        assert client.recent_editcount_by_day("Alice", "2026-01-01", "2026-01-31") == {}

    @patch("src.xtools.client.requests.get")
    def test_user_not_exists_appends_and_returns_empty(self, mock_get):
        resp = MagicMock()
        resp.status_code = 404
        resp.text = '{"detail":"The requested user does not exist","status":404}'
        resp.raise_for_status.side_effect = requests.HTTPError("404")
        # Code checks text BEFORE raise_for_status
        mock_get.return_value = resp

        client = _client()
        result = client.recent_editcount_by_day("NoSuchUser", "2026-01-01", "2026-01-31")

        assert result == {}
        assert "NoSuchUser" in client.users_not_exists

    @patch("src.xtools.client.requests.get")
    def test_rfc7807_error_returns_partial_or_empty(self, mock_get):
        mock_get.return_value = _ok_response({"status": 400, "title": "Bad Request", "detail": "invalid"})
        client = _client()

        assert client.recent_editcount_by_day("Alice", "2026-01-01", "2026-01-02") == {}

    @patch("src.xtools.client.requests.get")
    def test_pagination_follows_continue(self, mock_get):
        page1 = _ok_response(
            {
                "globalcontribs": [_contrib("2026-05-10T09:00:00Z")],
                "continue": "2026-05-10T10:00:00Z",
            }
        )
        page2 = _ok_response(
            {
                "globalcontribs": [_contrib("2026-05-10T12:00:00Z")],
            }
        )
        mock_get.side_effect = [page1, page2]

        client = _client()
        result = client.recent_editcount_by_day("Alice", "2026-05-10", "2026-05-11")

        assert result == {"2026-05-10": 2}
        assert mock_get.call_count == 2
        # Second request should pass offset
        second_params = mock_get.call_args_list[1][1].get("params") or {}
        assert second_params.get("offset") == "2026-05-10T10:00:00Z"

    @patch("src.xtools.client.requests.get")
    def test_request_exception_retries_then_returns_partial(self, mock_get):
        # First call succeeds with one edit, subsequent calls raise -> return partial
        ok = _ok_response(
            {
                "globalcontribs": [_contrib("2026-05-10T09:00:00Z")],
                "continue": "next",
            }
        )

        # Provide the 'ok' response first, then enough exceptions to exhaust the retry loop
        # (The retry loop makes around 5 attempts before giving up)
        mock_get.side_effect = [ok] + [requests.ConnectionError("down")] * 10

        client = _client()
        result = client.recent_editcount_by_day("Alice", "2026-05-10", "2026-05-11")

        # Partial data preserved
        assert result == {"2026-05-10": 1}

        # Ensure that retries actually happened
        assert mock_get.call_count > 2

    @patch("src.xtools.client.requests.get")
    def test_request_exception_with_no_data_returns_empty_after_backoff(self, mock_get, mock_sleep):
        mock_get.side_effect = requests.ConnectionError("down")

        client = _client()
        # max_delay path: keep failing until delay >= max_delay
        result = client.recent_editcount_by_day("Alice", "2026-05-10", "2026-05-11")

        assert result == {}
        assert mock_sleep.called

    @patch("src.xtools.client.requests.get")
    def test_url_contains_encoded_username_and_date_range(self, mock_get):
        mock_get.return_value = _ok_response({"globalcontribs": []})
        client = _client()

        client.recent_editcount_by_day("Mr. Ibrahem", "2026-05-10", "2026-05-12")

        url = mock_get.call_args[0][0]
        assert "Mr.%20Ibrahem" in url or "Mr. Ibrahem" in url
        assert "2026-05-10" in url
        assert "2026-05-12" in url
        assert "/all/" in url


# ===========================================================================
# get_recent_editcount (sum helper)
# ===========================================================================


class TestRecentEditcount:
    @patch.object(XToolsClient, "recent_editcount_by_day")
    def test_sums_days(self, mock_by_day):
        mock_by_day.return_value = {"2026-05-10": 3, "2026-05-11": 2}
        client = _client()

        assert client.get_recent_editcount("Alice", "2026-05-10", "2026-05-12") == 5

    @patch.object(XToolsClient, "recent_editcount_by_day")
    def test_returns_none_when_no_data(self, mock_by_day):
        mock_by_day.return_value = {}
        client = _client()

        assert client.get_recent_editcount("Alice", "2026-05-10", "2026-05-12") is None


# ===========================================================================
# recent_editcounts (batch)
# ===========================================================================


class TestRecentEditcounts:
    @patch.object(XToolsClient, "get_recent_editcount")
    @patch.object(XToolsClient, "load_dates", return_value=("2026-01-01", "2026-03-31"))
    def test_collects_per_user(self, mock_dates, mock_count, mock_sleep):
        mock_count.side_effect = [10, None, 5]
        client = _client()

        result = client.recent_editcounts(["Alice", "Bob", "Carol"], recent_days=90)

        assert result == {"Alice": 10, "Carol": 5}
        assert "Bob" not in result
        assert mock_count.call_count == 3
        assert mock_sleep.call_count == 3

    @patch.object(XToolsClient, "get_recent_editcount")
    @patch.object(XToolsClient, "load_dates", return_value=("2026-01-01", "2026-03-31"))
    def test_empty_users(self, mock_dates, mock_count):
        client = _client()
        assert client.recent_editcounts([]) == {}
        mock_count.assert_not_called()


# ===========================================================================
# last_edit_timestamp
# ===========================================================================


class TestLastEditTimestamp:
    @patch("src.xtools.client.requests.get")
    def test_returns_date_portion(self, mock_get):
        mock_get.return_value = _ok_response(
            {
                "globalcontribs": [
                    _contrib("2024-08-16T13:18:02Z"),
                ]
            }
        )
        client = _client()

        assert client.last_edit_timestamp("Alice") == "2024-08-16"

    @patch("src.xtools.client.requests.get")
    def test_returns_none_when_no_contribs(self, mock_get):
        mock_get.return_value = _ok_response({"globalcontribs": []})
        client = _client()

        assert client.last_edit_timestamp("Alice") is None

    @patch("src.xtools.client.requests.get")
    def test_returns_none_on_error_payload(self, mock_get):
        mock_get.return_value = _ok_response({"status": 404, "title": "Not Found", "detail": "gone"})
        client = _client()

        assert client.last_edit_timestamp("Alice") is None

    @patch("src.xtools.client.requests.get")
    def test_returns_none_on_request_exception(self, mock_get):
        mock_get.side_effect = requests.Timeout("slow")
        client = _client()

        assert client.last_edit_timestamp("Alice") is None

    @patch("src.xtools.client.requests.get")
    def test_limit_one_param(self, mock_get):
        mock_get.return_value = _ok_response({"globalcontribs": []})
        client = _client()

        client.last_edit_timestamp("Alice")

        params = mock_get.call_args[1]["params"]
        assert params["limit"] == 1


# ===========================================================================
# get_last_edit_timestamps (batch)
# ===========================================================================


class TestLastEditTimestamps:
    @patch.object(XToolsClient, "last_edit_timestamp")
    def test_collects_only_successful(self, mock_ts):
        mock_ts.side_effect = ["2026-01-01", None, "2026-02-01"]
        client = _client()

        result = client.get_last_edit_timestamps(["Alice", "Bob", "Carol"])

        assert result == {"Alice": "2026-01-01", "Carol": "2026-02-01"}
        assert "Bob" not in result

    @patch.object(XToolsClient, "last_edit_timestamp")
    def test_empty_users(self, mock_ts):
        client = _client()
        assert client.get_last_edit_timestamps([]) == {}
        mock_ts.assert_not_called()


# ===========================================================================
# Construction / headers
# ===========================================================================


class TestClientInit:
    def test_custom_user_agent_in_headers(self):
        client = XToolsClient(user_agent="MyBot/9.9", timeout=3)
        assert client._headers["User-Agent"] == "MyBot/9.9"
        assert client._timeout == 3

    def test_users_not_exists_starts_empty(self):
        client = _client()
        assert client.users_not_exists == []
