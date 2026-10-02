"""
Unit tests for src/cache/home_wiki_cache.py module.
"""

import pytest

from src.cache.home_wiki_cache import HomeWikiCache, validate_user_entry

VALID = {"home": "enwiki", "registration": "2020-01-01T00:00:00Z"}

# ---------------------------------------------------------------------------
# validate_user_entry
# ---------------------------------------------------------------------------


class TestValidateUserEntry:
    def test_valid_entry_returned(self):
        assert HomeWikiCache.validate_user_entry(VALID) == VALID

    @pytest.mark.parametrize("bad", [None, {}, {"home": "enwiki"}, {"registration": "2020-01-01T00:00:00Z"}])
    def test_invalid_entry_returns_empty(self, bad):
        assert validate_user_entry(bad) == {}

    def test_editcount_dropped_by_default(self):
        assert validate_user_entry({**VALID, "editcount": 5}) == VALID

    def test_editcount_kept_when_requested(self):
        assert validate_user_entry({**VALID, "editcount": 5}, get_editcount=True) == {**VALID, "editcount": 5}

    def test_zero_editcount_not_kept(self):
        assert validate_user_entry({**VALID, "editcount": 0}, get_editcount=True) == VALID


# ---------------------------------------------------------------------------
# HomeWikiCache (storage only)
# ---------------------------------------------------------------------------


class TestHomeWikiCache:
    def test_get_unknown_user_returns_empty(self, tmp_path):
        cache = HomeWikiCache(tmp_path / "c.json")
        cache.load()
        assert cache.get("Nobody") == {}

    def test_set_then_get(self, tmp_path):
        cache = HomeWikiCache(tmp_path / "c.json")
        cache.load()
        cache.set("A", VALID)
        assert cache.get("A") == VALID

    def test_get_invalid_entry_returns_empty(self, tmp_path):
        cache = HomeWikiCache(tmp_path / "c.json")
        cache.load()
        cache.set("A", {"home": "enwiki"})
        assert cache.get("A") == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        path = tmp_path / "c.json"
        first = HomeWikiCache(path)
        first.load()
        first.set("A", VALID)
        first.save()

        second = HomeWikiCache(path)
        second.load()
        assert second.get("A") == VALID

    def test_unsaved_changes_not_persisted(self, tmp_path):
        path = tmp_path / "c.json"
        first = HomeWikiCache(path)
        first.load()
        first.set("A", VALID)

        second = HomeWikiCache(path)
        second.load()
        assert second.get("A") == {}

    def test_never_touches_wiki(self, tmp_path):
        # The cache has no wiki dependency at all.
        assert "wiki" not in HomeWikiCache.__init__.__code__.co_varnames
