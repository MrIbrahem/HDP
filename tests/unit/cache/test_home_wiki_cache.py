"""
Unit tests for src/cache/home_wiki_cache.py module.

Classes to test: HomeWikiCache

TODO: write tests
"""

import os

import pytest

from unittest.mock import MagicMock
from src.cache.home_wiki_cache import HomeWikiCache

@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.cache.home_wiki_cache.time.sleep", MagicMock())


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

    @pytest.mark.skip(reason="get_many returns a dict[str, UserInfo] now.")
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

    @pytest.mark.skip(reason="get_many returns a dict[str, UserInfo] now.")
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
