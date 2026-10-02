"""
Unit tests for src/cache/home_wiki_cache.py module.

Test: HomeWikiCache (storage), HomeWikiProvider (cache vs. wiki).
"""

import os
from unittest.mock import MagicMock

import pytest

from src.cache.home_wiki_cache import HomeWikiCache
from src.services.home_wiki_provider import HomeWikiProvider

VALID = {"home": "enwiki", "registration": "2020-01-01T00:00:00Z"}

def make_provider(path, wiki) -> tuple[HomeWikiProvider, HomeWikiCache]:
    """Build a provider together with the cache it uses."""
    cache = HomeWikiCache(path)
    return HomeWikiProvider(wiki_client=wiki, cache_client=cache), cache


# ---------------------------------------------------------------------------
# HomeWikiProvider
# ---------------------------------------------------------------------------


class TestGetHomeWikisCached:
    @pytest.fixture
    def mock_api(self):
        """A mock WikiClient that records which users it was asked about."""

        class MockApi:
            def __init__(self):
                self.calls: list[str] = []

            def get_global_userinfo(self, username: str):
                self.calls.append(username)
                return {
                    "home": f"{username.lower()}wiki",
                    "registration": "2020-01-01T00:00:00Z",
                    "editcount": 35,
                }
            def get_global_users_info(self, users: list[str]):
                return {user: self.get_global_userinfo(user) for user in users}

        return MockApi()

    def test_all_new_users_fetched(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache.json")
        users = ["Alice", "Bob", "Carol"]

        provider, _ = make_provider(cache_path, mock_api)
        result = provider.get_many(users)

        assert len(result) == 3
        assert mock_api.calls == users
        # Cache file should now exist
        assert os.path.exists(cache_path)

    def test_cached_users_skipped(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache1.json")
        provider, cache = make_provider(cache_path, mock_api)

        # Populate the cache file with Alice
        cache._store.save(
            {"Alice": {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"}},
        )
        result = provider.get_many(["Alice", "Bob"])

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

        provider, cache = make_provider(cache_path, mock_api)
        cache._store.save(preloaded)

        result = provider.get_many(["Alice", "Bob"])

        assert mock_api.calls == []
        assert result == preloaded

    def test_cache_persisted_after_run(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache3.json")

        provider, cache = make_provider(cache_path, mock_api)
        provider.get_many(["Alice"])

        # Load the file independently and verify Alice is there
        stored = cache._store.load()
        assert "Alice" in stored
        assert stored["Alice"]["home"] == "alicewiki"

    def test_second_run_uses_cache_from_new_instances(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache4.json")

        first, _ = make_provider(cache_path, mock_api)
        first.get_many(["Alice"])
        assert mock_api.calls == ["Alice"]

        # Fresh cache + provider instances reading the same file
        second, _ = make_provider(cache_path, mock_api)
        result = second.get_many(["Alice"])

        assert mock_api.calls == ["Alice"]  # no new API call
        assert result["Alice"]["home"] == "alicewiki"


class TestGetManyEdgeCases:
    @pytest.fixture
    def wiki(self):
        return MagicMock()

    def test_empty_users(self, tmp_path, wiki):
        provider, _ = make_provider(tmp_path / "c.json", wiki)
        result = provider.get_many([])
        assert result == {}
        wiki.get_global_users_info.assert_not_called()

    @pytest.mark.parametrize("bad", [None, {}, {"home": "enwiki"}, {"registration": "2020-01-01T00:00:00Z"}])
    def test_failed_fetch_skipped_and_not_cached(self, tmp_path, wiki, bad, caplog):
        wiki.get_global_users_info.return_value = {
            "Good": VALID,
            "Bad": bad
        }
        provider, cache = make_provider(tmp_path / "c.json", wiki)

        result = provider.get_many(["Good", "Bad"])

        assert set(result) == {"Good"}
        assert "Bad" not in cache._store.load()
        assert "Failed to fetch home wiki for Bad" in caplog.text

    def test_no_save_when_all_fail(self, tmp_path, wiki, monkeypatch):
        wiki.get_global_users_info.return_value = {}
        provider, cache = make_provider(tmp_path / "c.json", wiki)
        save = MagicMock()
        monkeypatch.setattr(cache, "save", save)

        provider.get_many(["A", "B"])

        save.assert_not_called()

    def test_no_save_when_all_cached(self, tmp_path, wiki, monkeypatch):
        provider, cache = make_provider(tmp_path / "c.json", wiki)
        cache._store.save({"A": VALID})
        save = MagicMock()
        monkeypatch.setattr(cache, "save", save)

        provider.get_many(["A"])

        save.assert_not_called()
        wiki.get_global_users_info.assert_not_called()

    def test_save_every_and_final_save(self, tmp_path, wiki, monkeypatch):
        wiki.get_global_users_info.return_value = dict.fromkeys(["A", "B", "C", "D", "E"], VALID)
        provider, cache = make_provider(tmp_path / "c.json", wiki)
        save = MagicMock()
        monkeypatch.setattr(cache, "save", save)

        provider.get_many(["A", "B", "C", "D", "E"])

        assert save.call_count == 1

    def test_existing_unrelated_entries_preserved(self, tmp_path, wiki):
        wiki.get_global_users_info.return_value = {"New": VALID}
        provider, cache = make_provider(tmp_path / "c.json", wiki)
        cache._store.save({"Other": {"home": "dewiki", "registration": "2011-01-01T00:00:00Z"}})

        provider.get_many(["New"])

        assert set(cache._store.load()) == {"Other", "New"}

    def test_result_values_for_new_user(self, tmp_path, wiki):
        wiki.get_global_users_info.return_value = {"A": VALID}
        provider, _ = make_provider(tmp_path / "c.json", wiki)
        result = provider.get_many(["A"])
        assert result["A"] == VALID

    def test_editcount_stored_on_fetch_but_not_returned_from_cache(self, tmp_path, wiki):
        wiki.get_global_users_info.return_value = {"A": {**VALID, "editcount": 42}}
        provider, cache = make_provider(tmp_path / "c.json", wiki)

        fresh = provider.get_many(["A"])
        assert fresh["A"]["editcount"] == 42

        cached = provider.get_many(["A"])
        assert cached["A"] == VALID  # editcount is stripped when read back from cache

    def test_invalid_cached_entry_is_refetched(self, tmp_path, wiki):
        wiki.get_global_users_info.return_value = {"A": VALID}
        provider, cache = make_provider(tmp_path / "c.json", wiki)
        cache._store.save({"A": {"home": "enwiki"}})  # missing registration

        result = provider.get_many(["A"])

        wiki.get_global_users_info.assert_called_once_with(["A"])
        assert result["A"] == VALID
        assert cache._store.load()["A"] == VALID  # invalid entry replaced
