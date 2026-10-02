"""
Unit tests for src/cache/home_wiki_cache.py module.

Classes to test: HomeWikiCache
"""

import os
from unittest.mock import MagicMock

import pytest

from src.cache.home_wiki_cache import HomeWikiCache

VALID = {"home": "enwiki", "registration": "2020-01-01T00:00:00Z"}


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    m = MagicMock()
    monkeypatch.setattr("src.cache.home_wiki_cache.time.sleep", m)
    return m


class TestGetHomeWikisCached:
    @pytest.fixture
    def mock_api(self):
        """A mock WikiClient that records which users it was asked about."""

        class MockApi:
            def __init__(self):
                self.calls: list[str] = []

            def get_global_userinfo(self, username):
                self.calls.append(username)
                return {
                    "home": f"{username.lower()}wiki",
                    "registration": "2020-01-01T00:00:00Z",
                }

        return MockApi()

    def test_all_new_users_fetched(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache.json")
        users = ["Alice", "Bob", "Carol"]

        client = HomeWikiCache(cache_path, mock_api)
        result = client.get_many(users)

        assert len(result) == 3
        assert mock_api.calls == users
        # Cache file should now exist
        assert os.path.exists(cache_path)

    def test_cached_users_skipped(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache1.json")

        users = ["Alice", "Bob"]
        client = HomeWikiCache(cache_path, mock_api)

        # Populate the cache with Alice
        client._store.save(
            {"Alice": {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"}},
        )
        result = client.get_many(users)

        # Alice should come from cache, only Bob fetched
        assert mock_api.calls == ["Bob"]
        assert result["Alice"] == {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"}
        assert result["Bob"]["home"] == "bobwiki"

    def test_all_cached_no_api_calls(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache2.json")
        preloaded = {
            "Alice": {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"},
            "Bob": {"home": "frwiki", "registration": "2015-06-15T12:00:00Z"},
        }

        client = HomeWikiCache(cache_path, mock_api)
        client._store.save(preloaded)

        result = client.get_many(["Alice", "Bob"])

        assert mock_api.calls == []
        assert result == preloaded

    def test_cache_persisted_after_run(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache3.json")

        client = HomeWikiCache(cache_path, mock_api)
        client.get_many(["Alice"])

        # Load the cache independently and verify Alice is there
        cache = client._store.load()
        assert "Alice" in cache
        assert cache["Alice"]["home"] == "alicewiki"


class TestGetManyEdgeCases:
    @pytest.fixture
    def wiki(self):
        return MagicMock()

    def test_empty_users(self, tmp_path, wiki):
        result = HomeWikiCache(tmp_path / "c.json", wiki).get_many([])
        assert result == {}
        wiki.get_global_userinfo.assert_not_called()

    @pytest.mark.parametrize("bad", [None, {}, {"home": "enwiki"}, {"registration": "2020-01-01T00:00:00Z"}])
    def test_failed_fetch_skipped_and_not_cached(self, tmp_path, wiki, bad, caplog):
        wiki.get_global_userinfo.side_effect = lambda u: bad if u == "Bad" else VALID
        cache = HomeWikiCache(tmp_path / "c.json", wiki)

        result = cache.get_many(["Good", "Bad"])

        assert set(result) == {"Good"}
        assert "Bad" not in cache._store.load()
        assert "Failed to fetch home wiki for Bad" in caplog.text

    def test_no_save_when_all_fail(self, tmp_path, wiki, monkeypatch):
        wiki.get_global_userinfo.return_value = None
        cache = HomeWikiCache(tmp_path / "c.json", wiki)
        save = MagicMock()
        monkeypatch.setattr(cache._store, "save", save)

        cache.get_many(["A", "B"])

        save.assert_not_called()

    def test_save_every_and_final_save(self, tmp_path, wiki, monkeypatch):
        wiki.get_global_userinfo.return_value = VALID
        cache = HomeWikiCache(tmp_path / "c.json", wiki)
        save = MagicMock()
        monkeypatch.setattr(cache._store, "save", save)

        cache.get_many(["A", "B", "C", "D", "E"], save_every=2)

        assert save.call_count == 3  # after 2nd, after 4th, final

    def test_sleep_called_per_fetched_user(self, tmp_path, wiki, mock_sleep):
        wiki.get_global_userinfo.return_value = VALID
        HomeWikiCache(tmp_path / "c.json", wiki).get_many(["A", "B", "C"])
        assert mock_sleep.call_count == 3

    def test_existing_unrelated_entries_preserved(self, tmp_path, wiki):
        wiki.get_global_userinfo.return_value = VALID
        cache = HomeWikiCache(tmp_path / "c.json", wiki)
        cache._store.save({"Other": {"home": "dewiki", "registration": "2011-01-01T00:00:00Z"}})

        cache.get_many(["New"])

        assert set(cache._store.load()) == {"Other", "New"}

    def test_result_values_for_new_user(self, tmp_path, wiki):
        wiki.get_global_userinfo.return_value = VALID
        result = HomeWikiCache(tmp_path / "c.json", wiki).get_many(["A"])
        assert result["A"] == VALID

    def test_invalid_cached_entry_is_refetched(self, tmp_path, wiki):
        # Documents intended behavior; currently FAILS (user is dropped).
        wiki.get_global_userinfo.return_value = VALID
        cache = HomeWikiCache(tmp_path / "c.json", wiki)
        cache._store.save({"A": {"home": "enwiki"}})  # missing registration

        result = cache.get_many(["A"])

        assert result["A"] == VALID
        assert set(cache._store.load()) == {"A"}  # user dropped
