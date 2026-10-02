"""
Unit tests for src/services/recent_edits_provider.py module.

Classes to test: RecentEditCountsProvider
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

import src.services.recent_edits_provider as provider_module
from src.services.recent_edits_provider import (
    RecentEditCountsProvider,
)
from src.cache import XtoolsRecentEditCache
from src.xtools import XToolsClient

START = "2024-06-01"
END = "2024-06-30"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings():
    return SimpleNamespace(
        recent_days=30,
        user_agent="test-agent",
        edit_counts_cache_path="/tmp/edit_counts.json",
    )


@pytest.fixture
def xtools_client():
    client = MagicMock(spec=XToolsClient)
    client.users_not_exists = set()
    client.recent_editcount_by_day.return_value = {}
    return client


@pytest.fixture
def cache_client():
    cache = MagicMock(spec=XtoolsRecentEditCache)
    cache.has_coverage.return_value = False
    cache.get_coverage.return_value = None
    cache.get_counts.return_value = {}
    cache.sum_in_range.return_value = 0
    return cache


@pytest.fixture(autouse=True)
def fixed_dates(monkeypatch):
    """Make ``XToolsClient.load_dates`` deterministic."""
    monkeypatch.setattr(
        provider_module.XToolsClient,
        "load_dates",
        staticmethod(lambda days: (START, END)),
    )


@pytest.fixture
def sleep_mock(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(provider_module.time, "sleep", mock)
    return mock


@pytest.fixture
def provider(settings, xtools_client, cache_client, sleep_mock):
    return RecentEditCountsProvider(
        xtools_client=xtools_client,
        cache_client=cache_client,
        settings=settings,
        request_delay=0.3,
    )


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    """Tests for RecentEditCountsProvider.__init__."""

    def test_uses_injected_dependencies(self, provider: RecentEditCountsProvider, settings, xtools_client, cache_client):
        assert provider.settings is settings
        assert provider.xtools_client is xtools_client
        assert provider.cache_client is cache_client
        assert provider._recent_days == 30
        assert provider._request_delay == 0.3

    def test_builds_defaults_from_settings(self, monkeypatch, settings):
        settings_cls = MagicMock()
        settings_cls.from_env.return_value = settings
        client_cls = MagicMock()
        cache_cls = MagicMock()
        monkeypatch.setattr(provider_module, "Settings", settings_cls)
        monkeypatch.setattr(provider_module, "XToolsClient", client_cls)
        monkeypatch.setattr(provider_module, "XtoolsRecentEditCache", cache_cls)

        p = RecentEditCountsProvider()

        settings_cls.from_env.assert_called_once_with()
        client_cls.assert_called_once_with(user_agent="test-agent")
        cache_cls.assert_called_once_with("/tmp/edit_counts.json")
        assert p.xtools_client is client_cls.return_value
        assert p.cache_client is cache_cls.return_value
        assert p._request_delay == 0.3

    def test_does_not_load_env_settings_when_provided(self, monkeypatch, settings, xtools_client, cache_client):
        settings_cls = MagicMock()
        monkeypatch.setattr(provider_module, "Settings", settings_cls)

        RecentEditCountsProvider(
            xtools_client=xtools_client,
            cache_client=cache_client,
            settings=settings,
        )

        settings_cls.from_env.assert_not_called()


# ---------------------------------------------------------------------------
# get_many
# ---------------------------------------------------------------------------


class TestGetMany:
    """Tests for RecentEditCountsProvider.get_many."""

    def test_loads_cache_then_goes_online_by_default(self, provider: RecentEditCountsProvider, cache_client, monkeypatch):
        order = []
        cache_client.load.side_effect = lambda: order.append("load")
        online = MagicMock(side_effect=lambda **kw: order.append("online") or {"a": 1})
        offline = MagicMock()
        monkeypatch.setattr(provider, "_get_online", online)
        monkeypatch.setattr(provider, "_get_offline", offline)

        result = provider.get_many(["a"])

        assert result == {"a": 1}
        assert order == ["load", "online"]
        offline.assert_not_called()

    def test_online_receives_arguments(self, provider: RecentEditCountsProvider, monkeypatch):
        online = MagicMock(return_value={})
        monkeypatch.setattr(provider, "_get_online", online)

        provider.get_many(["a", "b"], set_zero=True, save_every=2)

        online.assert_called_once_with(users=["a", "b"], set_zero=True, save_every=2)

    def test_online_default_arguments(self, provider: RecentEditCountsProvider, monkeypatch):
        online = MagicMock(return_value={})
        monkeypatch.setattr(provider, "_get_online", online)

        provider.get_many(["a"])

        online.assert_called_once_with(users=["a"], set_zero=False, save_every=5)

    def test_offline_dispatch(self, provider: RecentEditCountsProvider, cache_client, monkeypatch):
        online = MagicMock()
        offline = MagicMock(return_value={"a": 3})
        monkeypatch.setattr(provider, "_get_online", online)
        monkeypatch.setattr(provider, "_get_offline", offline)

        result = provider.get_many(["a"], offline=True, set_zero=True)

        assert result == {"a": 3}
        cache_client.load.assert_called_once_with()
        offline.assert_called_once_with(["a"], set_zero=True)
        online.assert_not_called()

    def test_offline_never_touches_network_client(self, provider: RecentEditCountsProvider, xtools_client, cache_client):
        cache_client.get_counts.return_value = {"2024-06-02": 4}
        cache_client.sum_in_range.return_value = 4

        result = provider.get_many(["a"], offline=True)

        assert result == {"a": 4}
        xtools_client.recent_editcount_by_day.assert_not_called()

    def test_empty_users_online(self, provider: RecentEditCountsProvider, cache_client):
        assert provider.get_many([]) == {}
        cache_client.load.assert_called_once_with()


# ---------------------------------------------------------------------------
# _get_online
# ---------------------------------------------------------------------------


class TestGetOnline:
    """Tests for RecentEditCountsProvider._get_online."""

    @pytest.fixture
    def get_one(self, provider: RecentEditCountsProvider, monkeypatch):
        mock = MagicMock(return_value=5)
        monkeypatch.setattr(provider, "_get_one", mock)
        return mock

    def test_collects_counts_for_each_user(self, provider: RecentEditCountsProvider, get_one):
        get_one.side_effect = [1, 2, 3]

        result = provider._get_online(["a", "b", "c"])

        assert result == {"a": 1, "b": 2, "c": 3}

    def test_passes_date_range_to_get_one(self, provider: RecentEditCountsProvider, get_one):
        provider._get_online(["a", "b"])

        assert get_one.call_args_list == [
            call("a", START, END),
            call("b", START, END),
        ]

    def test_none_counts_are_omitted(self, provider: RecentEditCountsProvider, get_one):
        get_one.side_effect = [None, 7]

        result = provider._get_online(["a", "b"])

        assert result == {"b": 7}

    def test_set_zero_fills_none_with_zero(self, provider: RecentEditCountsProvider, get_one):
        get_one.side_effect = [None, 7]

        result = provider._get_online(["a", "b"], set_zero=True)

        assert result == {"a": 0, "b": 7}

    def test_set_zero_keeps_real_counts(self, provider: RecentEditCountsProvider, get_one):
        get_one.return_value = 9

        assert provider._get_online(["a"], set_zero=True) == {"a": 9}

    def test_nonexistent_users_get_zero_even_without_set_zero(self, provider: RecentEditCountsProvider, xtools_client, get_one):
        xtools_client.users_not_exists = {"ghost"}
        get_one.side_effect = [None, 4]

        result = provider._get_online(["ghost", "real"])

        assert result == {"ghost": 0, "real": 4}

    def test_nonexistent_user_with_count_keeps_count(self, provider: RecentEditCountsProvider, xtools_client, get_one):
        xtools_client.users_not_exists = {"ghost"}
        get_one.return_value = 3

        assert provider._get_online(["ghost"]) == {"ghost": 3}

    def test_throttles_only_uncached_users(self, provider: RecentEditCountsProvider, cache_client, sleep_mock, get_one):
        cache_client.has_coverage.side_effect = [True, False, False, True]

        provider._get_online(["a", "b", "c", "d"])

        assert sleep_mock.call_count == 2
        sleep_mock.assert_called_with(0.3)

    def test_no_throttle_when_all_cached(self, provider: RecentEditCountsProvider, cache_client, sleep_mock, get_one):
        cache_client.has_coverage.return_value = True

        provider._get_online(["a", "b"])

        sleep_mock.assert_not_called()

    def test_custom_request_delay_is_used(self, settings, xtools_client, cache_client, sleep_mock, monkeypatch):
        p = RecentEditCountsProvider(
            xtools_client=xtools_client,
            cache_client=cache_client,
            settings=settings,
            request_delay=1.5,
        )
        monkeypatch.setattr(p, "_get_one", MagicMock(return_value=1))

        p._get_online(["a"])

        sleep_mock.assert_called_once_with(1.5)

    def test_coverage_checked_before_fetch(self, provider: RecentEditCountsProvider, cache_client, get_one):
        """``has_coverage`` must be evaluated before ``_get_one`` mutates the cache."""
        order = []
        cache_client.has_coverage.side_effect = lambda u: order.append("has_coverage") or False
        get_one.side_effect = lambda *a: order.append("get_one") or 1

        provider._get_online(["a"])

        assert order == ["has_coverage", "get_one"]

    def test_saves_periodically_and_at_end(self, provider: RecentEditCountsProvider, cache_client, get_one):
        provider._get_online(["a", "b", "c", "d", "e"], save_every=2)

        # after user 2, after user 4, and the final flush
        assert cache_client.save.call_count == 3

    def test_default_save_every_five(self, provider: RecentEditCountsProvider, cache_client, get_one):
        provider._get_online([f"u{i}" for i in range(10)])

        # after user 5, after user 10, and the final flush
        assert cache_client.save.call_count == 3

    def test_final_save_when_fewer_users_than_interval(self, provider: RecentEditCountsProvider, cache_client, get_one):
        provider._get_online(["a", "b"], save_every=5)

        cache_client.save.assert_called_once_with()

    def test_empty_users(self, provider: RecentEditCountsProvider, cache_client, get_one, sleep_mock):
        assert provider._get_online([]) == {}
        get_one.assert_not_called()
        sleep_mock.assert_not_called()
        cache_client.save.assert_called_once_with()

    def test_save_called_even_if_fetch_returns_nothing(self, provider: RecentEditCountsProvider, cache_client, get_one):
        get_one.return_value = None

        assert provider._get_online(["a"]) == {}
        cache_client.save.assert_called_once_with()

    def test_exception_propagates(self, provider: RecentEditCountsProvider, get_one):
        get_one.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            provider._get_online(["a"])


# ---------------------------------------------------------------------------
# _get_offline
# ---------------------------------------------------------------------------


class TestGetOffline:
    """Tests for RecentEditCountsProvider._get_offline."""

    def test_returns_sum_for_cached_users(self, provider: RecentEditCountsProvider, cache_client):
        cache_client.get_counts.return_value = {"2024-06-02": 2}
        cache_client.sum_in_range.side_effect = [11, 22]

        result = provider._get_offline(["a", "b"], set_zero=False)

        assert result == {"a": 11, "b": 22}
        assert cache_client.sum_in_range.call_args_list == [
            call("a", START, END),
            call("b", START, END),
        ]

    def test_uncached_users_skipped(self, provider: RecentEditCountsProvider, cache_client):
        cache_client.get_counts.return_value = {}

        assert provider._get_offline(["a"], set_zero=False) == {}
        cache_client.sum_in_range.assert_not_called()

    def test_uncached_users_zero_with_set_zero(self, provider: RecentEditCountsProvider, cache_client):
        cache_client.get_counts.return_value = {}

        assert provider._get_offline(["a", "b"], set_zero=True) == {"a": 0, "b": 0}
        cache_client.sum_in_range.assert_not_called()

    def test_mixed_cached_and_uncached(self, provider: RecentEditCountsProvider, cache_client):
        cache_client.get_counts.side_effect = lambda u: {"d": 1} if u == "cached" else {}
        cache_client.sum_in_range.return_value = 8

        result = provider._get_offline(["cached", "missing"], set_zero=True)

        assert result == {"cached": 8, "missing": 0}

    def test_cached_zero_sum_is_preserved(self, provider: RecentEditCountsProvider, cache_client):
        cache_client.get_counts.return_value = {"2024-06-02": 0}
        cache_client.sum_in_range.return_value = 0

        assert provider._get_offline(["a"], set_zero=False) == {"a": 0}

    def test_never_calls_network_client_or_sleeps(self, provider: RecentEditCountsProvider, xtools_client, cache_client, sleep_mock):
        cache_client.get_counts.return_value = {}

        provider._get_offline(["a", "b"], set_zero=True)

        xtools_client.recent_editcount_by_day.assert_not_called()
        sleep_mock.assert_not_called()

    def test_does_not_save_cache(self, provider: RecentEditCountsProvider, cache_client):
        provider._get_offline(["a"], set_zero=False)

        cache_client.save.assert_not_called()

    def test_empty_users(self, provider):
        assert provider._get_offline([], set_zero=True) == {}


# ---------------------------------------------------------------------------
# _get_one
# ---------------------------------------------------------------------------


class TestGetOne:
    """Tests for RecentEditCountsProvider._get_one."""

    # -- fully covered ---------------------------------------------------

    @pytest.mark.parametrize(
        ("cached_start", "cached_end"),
        [
            ("2024-06-01", "2024-06-30"),  # exact match
            ("2024-05-15", "2024-07-15"),  # superset
            ("2024-06-01", "2024-07-01"),  # same start, later end
            ("2024-05-31", "2024-06-30"),  # earlier start, same end
        ],
    )
    def test_fully_covered_makes_no_api_call(
        self, provider: RecentEditCountsProvider, xtools_client, cache_client, cached_start, cached_end
    ):
        cache_client.get_coverage.return_value = {"start": cached_start, "end": cached_end}
        cache_client.sum_in_range.return_value = 42

        result = provider._get_one("alice", START, END)

        assert result == 42
        xtools_client.recent_editcount_by_day.assert_not_called()
        cache_client.merge.assert_not_called()
        cache_client.sum_in_range.assert_called_once_with("alice", START, END)

    # -- overlapping / adjacent: only the missing parts are fetched ------

    def test_fetches_only_tail_when_end_moved_forward(self, provider: RecentEditCountsProvider, xtools_client, cache_client):
        cache_client.get_coverage.return_value = {"start": "2024-06-01", "end": "2024-06-20"}
        xtools_client.recent_editcount_by_day.return_value = {"2024-06-25": 3}
        cache_client.sum_in_range.return_value = 10

        result = provider._get_one("alice", START, END)

        assert result == 10
        xtools_client.recent_editcount_by_day.assert_called_once_with("alice", "2024-06-21", END)
        cache_client.merge.assert_called_once_with(
            "alice", {"2024-06-25": 3}, "2024-06-01", "2024-06-30"
        )
        cache_client.sum_in_range.assert_called_once_with("alice", START, END)

    def test_fetches_only_front_when_start_moved_back(self, provider: RecentEditCountsProvider, xtools_client, cache_client):
        cache_client.get_coverage.return_value = {"start": "2024-06-10", "end": "2024-06-30"}
        xtools_client.recent_editcount_by_day.return_value = {"2024-06-02": 5}
        cache_client.sum_in_range.return_value = 12

        result = provider._get_one("alice", START, END)

        assert result == 12
        xtools_client.recent_editcount_by_day.assert_called_once_with("alice", START, "2024-06-09")
        cache_client.merge.assert_called_once_with(
            "alice", {"2024-06-02": 5}, "2024-06-01", "2024-06-30"
        )

    def test_fetches_both_front_and_tail(self, provider: RecentEditCountsProvider, xtools_client, cache_client):
        cache_client.get_coverage.return_value = {"start": "2024-06-10", "end": "2024-06-20"}
        xtools_client.recent_editcount_by_day.side_effect = [
            {"2024-06-02": 1},  # front
            {"2024-06-25": 2},  # tail
        ]
        cache_client.sum_in_range.return_value = 3

        result = provider._get_one("alice", START, END)

        assert result == 3
        assert xtools_client.recent_editcount_by_day.call_args_list == [
            call("alice", START, "2024-06-09"),
            call("alice", "2024-06-21", END),
        ]
        cache_client.merge.assert_called_once_with(
            "alice",
            {"2024-06-02": 1, "2024-06-25": 2},
            "2024-06-01",
            "2024-06-30",
        )

    def test_adjacent_range_after_cache_fetches_tail(self, provider: RecentEditCountsProvider, xtools_client, cache_client):
        cache_client.get_coverage.return_value = {"start": "2024-06-01", "end": "2024-06-20"}
        xtools_client.recent_editcount_by_day.return_value = {}

        # Request starts the day right after the cached end -> adjacent, not a gap.
        provider._get_one("alice", "2024-06-21", END)

        xtools_client.recent_editcount_by_day.assert_called_once_with("alice", "2024-06-21", END)
        cache_client.merge.assert_called_once_with("alice", {}, "2024-06-01", "2024-06-30")

    def test_adjacent_range_before_cache_fetches_front(self, provider: RecentEditCountsProvider, xtools_client, cache_client):
        cache_client.get_coverage.return_value = {"start": "2024-06-20", "end": "2024-06-30"}
        xtools_client.recent_editcount_by_day.return_value = {}

        # Request ends the day right before the cached start -> adjacent, not a gap.
        provider._get_one("alice", START, "2024-06-19")

        xtools_client.recent_editcount_by_day.assert_called_once_with("alice", START, "2024-06-19")
        cache_client.merge.assert_called_once_with("alice", {}, "2024-06-01", "2024-06-30")

    def test_partial_fetch_with_empty_result_still_extends_coverage(
        self, provider: RecentEditCountsProvider, xtools_client, cache_client
    ):
        cache_client.get_coverage.return_value = {"start": "2024-06-01", "end": "2024-06-20"}
        xtools_client.recent_editcount_by_day.return_value = {}
        cache_client.sum_in_range.return_value = 6

        result = provider._get_one("alice", START, END)

        assert result == 6
        cache_client.merge.assert_called_once_with("alice", {}, "2024-06-01", "2024-06-30")

    def test_merge_uses_union_of_cached_and_requested_range(self, provider: RecentEditCountsProvider, xtools_client, cache_client):
        """Request starts later than cache, ends later: union is cache.start..req.end."""
        cache_client.get_coverage.return_value = {"start": "2024-05-20", "end": "2024-06-20"}
        xtools_client.recent_editcount_by_day.return_value = {"2024-06-25": 1}

        provider._get_one("alice", START, END)

        xtools_client.recent_editcount_by_day.assert_called_once_with("alice", "2024-06-21", END)
        cache_client.merge.assert_called_once_with(
            "alice", {"2024-06-25": 1}, "2024-05-20", "2024-06-30"
        )

    # -- real gap: fetch whole range ------------------------------------

    @pytest.mark.parametrize(
        ("cached_start", "cached_end"),
        [
            ("2024-05-01", "2024-05-20"),  # gap_after: cache ends well before request
            ("2024-07-10", "2024-07-31"),  # gap_before: cache starts well after request
        ],
    )
    def test_real_gap_fetches_full_range(
        self, provider: RecentEditCountsProvider, xtools_client, cache_client, cached_start, cached_end
    ):
        cache_client.get_coverage.return_value = {"start": cached_start, "end": cached_end}
        xtools_client.recent_editcount_by_day.return_value = {"2024-06-10": 4}
        cache_client.sum_in_range.return_value = 4

        result = provider._get_one("alice", START, END)

        assert result == 4
        xtools_client.recent_editcount_by_day.assert_called_once_with("alice", START, END)
        cache_client.merge.assert_called_once_with("alice", {"2024-06-10": 4}, START, END)

    def test_gap_with_empty_fetch_and_existing_coverage_still_merges(
        self, provider: RecentEditCountsProvider, xtools_client, cache_client
    ):
        cache_client.get_coverage.return_value = {"start": "2024-05-01", "end": "2024-05-20"}
        xtools_client.recent_editcount_by_day.return_value = {}
        cache_client.sum_in_range.return_value = 0

        result = provider._get_one("alice", START, END)

        assert result == 0
        cache_client.merge.assert_called_once_with("alice", {}, START, END)

    # -- no cache entry --------------------------------------------------

    def test_no_coverage_fetches_full_range_and_merges(self, provider: RecentEditCountsProvider, xtools_client, cache_client):
        cache_client.get_coverage.return_value = None
        xtools_client.recent_editcount_by_day.return_value = {"2024-06-05": 2, "2024-06-06": 3}
        cache_client.sum_in_range.return_value = 5

        result = provider._get_one("alice", START, END)

        assert result == 5
        xtools_client.recent_editcount_by_day.assert_called_once_with("alice", START, END)
        cache_client.merge.assert_called_once_with(
            "alice", {"2024-06-05": 2, "2024-06-06": 3}, START, END
        )
        cache_client.sum_in_range.assert_called_once_with("alice", START, END)

    def test_no_coverage_and_empty_fetch_returns_none(self, provider: RecentEditCountsProvider, xtools_client, cache_client):
        cache_client.get_coverage.return_value = None
        xtools_client.recent_editcount_by_day.return_value = {}

        result = provider._get_one("alice", START, END)

        assert result is None
        cache_client.merge.assert_not_called()
        cache_client.sum_in_range.assert_not_called()

    def test_no_coverage_and_none_fetch_returns_none(self, provider: RecentEditCountsProvider, xtools_client, cache_client):
        cache_client.get_coverage.return_value = None
        xtools_client.recent_editcount_by_day.return_value = None

        assert provider._get_one("alice", START, END) is None
        cache_client.merge.assert_not_called()

    def test_client_exception_propagates_without_merge(self, provider: RecentEditCountsProvider, xtools_client, cache_client):
        cache_client.get_coverage.return_value = None
        xtools_client.recent_editcount_by_day.side_effect = RuntimeError("api down")

        with pytest.raises(RuntimeError, match="api down"):
            provider._get_one("alice", START, END)

        cache_client.merge.assert_not_called()

    def test_coverage_looked_up_by_username(self, provider: RecentEditCountsProvider, cache_client):
        cache_client.get_coverage.return_value = {"start": START, "end": END}

        provider._get_one("bob", START, END)

        cache_client.get_coverage.assert_called_once_with("bob")
