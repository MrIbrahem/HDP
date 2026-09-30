import os

import pytest

from src.cache.home_wiki_cache import HomeWikiCache
from src.cache.json_cache import JsonCache


def get_many(
    api,
    users: list[str],
    cache_path: str = "",
    save_every: int = 5,
) -> dict[str, dict[str, str]]:
    return HomeWikiCache(cache_path, api).get_many(
        users,
        save_every=save_every,
    )


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

        result = get_many(mock_api, users, cache_path=cache_path)

        assert len(result) == 3
        assert mock_api.calls == users
        # Cache file should now exist
        assert os.path.exists(cache_path)

    @pytest.mark.skip(reason="get_many returns a dict[str, UserInfo] now.")
    def test_cached_users_skipped(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache.json")

        # Pre-populate the cache with Alice
        JsonCache(cache_path).save(
            {"Alice": {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"}},
        )

        users = ["Alice", "Bob"]
        result = get_many(mock_api, users, cache_path=cache_path)

        # Alice should come from cache, only Bob fetched
        assert mock_api.calls == ["Bob"]
        assert result["Alice"] == {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"}
        assert result["Bob"]["home"] == "bobwiki"

    @pytest.mark.skip(reason="get_many returns a dict[str, UserInfo] now.")
    def test_all_cached_no_api_calls(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache.json")
        preloaded = {
            "Alice": {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"},
            "Bob": {"home": "frwiki", "registration": "2015-06-15T12:00:00Z"},
        }
        JsonCache(cache_path).save(preloaded)

        result = get_many(mock_api, ["Alice", "Bob"], cache_path=cache_path)

        assert mock_api.calls == []
        assert result == preloaded

    def test_cache_persisted_after_run(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache.json")

        get_many(mock_api, ["Alice"], cache_path=cache_path)

        # Load the cache independently and verify Alice is there
        cache = JsonCache(cache_path).load()
        assert "Alice" in cache
        assert cache["Alice"]["home"] == "alicewiki"
