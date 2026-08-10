import json
import os
import tempfile

import pytest

from src.api.home_wiki_cached import get_home_wikis_cached, load_cache, save_cache


class TestCacheIO:
    def test_load_nonexistent_returns_empty_dict(self, tmp_path):
        cache_path = str(tmp_path / "nonexistent.json")
        assert load_cache(cache_path) == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        cache_path = str(tmp_path / "cache.json")
        data = {
            "Alice": {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"},
            "Bob": {"home": "frwiki", "registration": "2015-06-15T12:00:00Z"},
        }
        save_cache(data, cache_path)
        loaded = load_cache(cache_path)
        assert loaded == data

    def test_load_corrupt_file_returns_empty(self, tmp_path):
        cache_path = str(tmp_path / "bad.json")
        with open(cache_path, "w") as f:
            f.write("{not valid json")
        assert load_cache(cache_path) == {}

    def test_save_is_atomic(self, tmp_path):
        cache_path = str(tmp_path / "cache.json")
        save_cache({"x": {"home": "enwiki", "registration": ""}}, cache_path)
        # No .tmp file should remain after a successful save
        assert not os.path.exists(cache_path + ".tmp")


class TestGetHomeWikisCached:
    @pytest.fixture
    def mock_api(self):
        """A mock MwclientApi that records which users it was asked about."""

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

        result = get_home_wikis_cached(mock_api, users, cache_path=cache_path)

        assert len(result) == 3
        assert mock_api.calls == users
        # Cache file should now exist
        assert os.path.exists(cache_path)

    def test_cached_users_skipped(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache.json")

        # Pre-populate the cache with Alice
        save_cache(
            {"Alice": {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"}},
            cache_path,
        )

        users = ["Alice", "Bob"]
        result = get_home_wikis_cached(mock_api, users, cache_path=cache_path)

        # Alice should come from cache, only Bob fetched
        assert mock_api.calls == ["Bob"]
        assert result["Alice"] == {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"}
        assert result["Bob"]["home"] == "bobwiki"

    def test_all_cached_no_api_calls(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache.json")
        preloaded = {
            "Alice": {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"},
            "Bob": {"home": "frwiki", "registration": "2015-06-15T12:00:00Z"},
        }
        save_cache(preloaded, cache_path)

        result = get_home_wikis_cached(mock_api, ["Alice", "Bob"], cache_path=cache_path)

        assert mock_api.calls == []
        assert result == preloaded

    def test_cache_persisted_after_run(self, tmp_path, mock_api):
        cache_path = str(tmp_path / "cache.json")

        get_home_wikis_cached(mock_api, ["Alice"], cache_path=cache_path)

        # Load the cache independently and verify Alice is there
        cache = load_cache(cache_path)
        assert "Alice" in cache
        assert cache["Alice"]["home"] == "alicewiki"
