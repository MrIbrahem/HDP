"""
Unit tests for src/cache/json_cache.py module.

Classes to test: JsonCache
"""

import os

from src.cache.json_cache import JsonCache


class TestCacheIO:
    def test_load_nonexistent_returns_empty_dict(self, tmp_path):
        cache_path = str(tmp_path / "nonexistent.json")
        assert JsonCache(cache_path).load() == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        cache_path = str(tmp_path / "cache.json")
        data = {
            "Alice": {"home": "enwiki", "registration": "2010-01-01T00:00:00Z"},
            "Bob": {"home": "frwiki", "registration": "2015-06-15T12:00:00Z"},
        }

        JsonCache(cache_path).save(data)

        loaded = JsonCache(cache_path).load()
        assert loaded == data

    def test_load_corrupt_file_returns_empty(self, tmp_path):
        cache_path = str(tmp_path / "bad.json")
        with open(cache_path, "w") as f:
            f.write("{not valid json")
        assert JsonCache(cache_path).load() == {}

    def test_save_is_atomic(self, tmp_path):
        cache_path = str(tmp_path / "cache.json")

        JsonCache(cache_path).save({"x": {"home": "enwiki", "registration": ""}})

        # No .tmp file should remain after a successful save
        assert not os.path.exists(cache_path + ".tmp")
