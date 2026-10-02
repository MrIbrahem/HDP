"""
Unit tests for src/cache/xtools_cache.py module.

Classes to test: XtoolsRecentEditCache
"""

import json

import pytest

from src.cache.xtools_cache import XtoolsRecentEditCache


@pytest.fixture
def cache_path(tmp_path):
    return tmp_path / "xtools_cache.json"


@pytest.fixture
def cache(cache_path):
    c = XtoolsRecentEditCache(cache_path)
    c.load()
    return c


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_starts_empty_without_load(self, cache_path):
        c = XtoolsRecentEditCache(cache_path)
        assert c.get_counts("Any") == {}
        assert c.get_coverage("Any") is None
        assert c.has_coverage("Any") is False

    def test_accepts_str_path(self, cache_path):
        c = XtoolsRecentEditCache(str(cache_path))
        c.merge("User", {"2026-01-01": 1}, "2026-01-01", "2026-01-01")
        c.save()
        assert cache_path.exists()

    def test_does_not_create_file(self, cache_path):
        XtoolsRecentEditCache(cache_path)
        assert not cache_path.exists()


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------


class TestLoad:
    def test_missing_file_gives_empty_state(self, cache_path):
        c = XtoolsRecentEditCache(cache_path)
        c.load()
        assert c.get_counts("User") == {}
        assert c.has_coverage("User") is False

    def test_loads_existing_data(self, cache_path):
        write_json(cache_path, {"User": {"2026-01-01": 3, "2026-01-02": 4}})
        c = XtoolsRecentEditCache(cache_path)
        c.load()
        assert c.get_counts("User") == {"2026-01-01": 3, "2026-01-02": 4}

    def test_drops_legacy_meta_key(self, cache_path):
        write_json(
            cache_path,
            {
                "User": {"2026-01-01": 3},
                "_meta": {"User": {"start": "2026-01-01", "end": "2026-06-01"}},
            },
        )
        c = XtoolsRecentEditCache(cache_path)
        c.load()
        # coverage comes from stored dates only, not from the old _meta table
        assert c.get_coverage("User") == {"start": "2026-01-01", "end": "2026-01-01"}
        assert c.get_counts("_meta") == {}
        assert c.has_coverage("_meta") is False

    def test_load_replaces_in_memory_state(self, cache_path):
        write_json(cache_path, {"Disk": {"2026-01-01": 1}})
        c = XtoolsRecentEditCache(cache_path)
        c.merge("Memory", {"2026-02-01": 2}, "2026-02-01", "2026-02-01")
        c.load()
        assert c.has_coverage("Memory") is False
        assert c.has_coverage("Disk") is True


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


class TestSave:
    def test_writes_data_to_disk(self, cache, cache_path):
        cache.merge("User", {"2026-01-02": 5}, "2026-01-01", "2026-01-03")
        cache.save()
        assert read_json(cache_path) == {
            "User": {"2026-01-01": 0, "2026-01-02": 5, "2026-01-03": 0}
        }

    def test_roundtrip(self, cache, cache_path):
        cache.merge("User", {"2026-01-02": 5}, "2026-01-01", "2026-01-03")
        cache.save()

        other = XtoolsRecentEditCache(cache_path)
        other.load()
        assert other.get_counts("User") == cache.get_counts("User")
        assert other.get_coverage("User") == cache.get_coverage("User")

    def test_legacy_meta_not_written_back(self, cache_path):
        write_json(
            cache_path,
            {"User": {"2026-01-01": 1}, "_meta": {"User": {"start": "a", "end": "b"}}},
        )
        c = XtoolsRecentEditCache(cache_path)
        c.load()
        c.save()
        assert "_meta" not in read_json(cache_path)

    def test_save_empty_cache(self, cache, cache_path):
        cache.save()
        assert read_json(cache_path) == {}


# ---------------------------------------------------------------------------
# get_coverage
# ---------------------------------------------------------------------------


class TestGetCoverage:
    def test_unknown_user_returns_none(self, cache):
        assert cache.get_coverage("Nobody") is None

    def test_returns_min_and_max_dates(self, cache):
        cache.merge(
            "User",
            {"2026-03-05": 1, "2026-01-10": 2, "2026-02-20": 3},
            "2026-01-10",
            "2026-03-05",
        )
        assert cache.get_coverage("User") == {"start": "2026-01-10", "end": "2026-03-05"}

    def test_boundaries_extend_coverage(self, cache):
        cache.merge("User", {"2026-01-06": 4, "2026-09-26": 6}, "2026-01-02", "2026-09-30")
        assert cache.get_coverage("User") == {"start": "2026-01-02", "end": "2026-09-30"}

    def test_single_day(self, cache):
        cache.merge("User", {"2026-05-05": 2}, "2026-05-05", "2026-05-05")
        assert cache.get_coverage("User") == {"start": "2026-05-05", "end": "2026-05-05"}

    def test_user_with_empty_dict_returns_none(self, cache_path):
        write_json(cache_path, {"User": {}})
        c = XtoolsRecentEditCache(cache_path)
        c.load()
        assert c.get_coverage("User") is None

    def test_users_are_independent(self, cache):
        cache.merge("A", {}, "2026-01-01", "2026-01-31")
        cache.merge("B", {}, "2026-02-01", "2026-02-28")
        assert cache.get_coverage("A") == {"start": "2026-01-01", "end": "2026-01-31"}
        assert cache.get_coverage("B") == {"start": "2026-02-01", "end": "2026-02-28"}


# ---------------------------------------------------------------------------
# has_coverage
# ---------------------------------------------------------------------------


class TestHasCoverage:
    def test_false_for_unknown_user(self, cache):
        assert cache.has_coverage("Nobody") is False

    def test_true_after_merge(self, cache):
        cache.merge("User", {"2026-01-02": 1}, "2026-01-01", "2026-01-03")
        assert cache.has_coverage("User") is True

    def test_true_after_merge_with_empty_counts(self, cache):
        cache.merge("User", {}, "2026-01-01", "2026-01-03")
        assert cache.has_coverage("User") is True

    def test_false_for_user_with_empty_dict(self, cache_path):
        write_json(cache_path, {"User": {}})
        c = XtoolsRecentEditCache(cache_path)
        c.load()
        assert c.has_coverage("User") is False

    def test_false_for_user_with_null_value(self, cache_path):
        write_json(cache_path, {"User": None})
        c = XtoolsRecentEditCache(cache_path)
        c.load()
        assert c.has_coverage("User") is False


# ---------------------------------------------------------------------------
# get_counts
# ---------------------------------------------------------------------------


class TestGetCounts:
    def test_unknown_user_returns_empty_dict(self, cache):
        assert cache.get_counts("Nobody") == {}

    def test_returns_stored_counts(self, cache):
        cache.merge("User", {"2026-01-02": 7}, "2026-01-02", "2026-01-02")
        assert cache.get_counts("User") == {"2026-01-02": 7}

    def test_null_value_returns_empty_dict(self, cache_path):
        write_json(cache_path, {"User": None})
        c = XtoolsRecentEditCache(cache_path)
        c.load()
        assert c.get_counts("User") == {}

    def test_includes_boundary_zeros(self, cache):
        cache.merge("User", {"2026-01-02": 7}, "2026-01-01", "2026-01-03")
        assert cache.get_counts("User") == {
            "2026-01-01": 0,
            "2026-01-02": 7,
            "2026-01-03": 0,
        }


# ---------------------------------------------------------------------------
# sum_in_range
# ---------------------------------------------------------------------------


class TestSumInRange:
    @pytest.fixture
    def filled(self, cache):
        cache.merge(
            "User",
            {"2026-01-01": 1, "2026-01-05": 2, "2026-01-10": 3, "2026-01-20": 4},
            "2026-01-01",
            "2026-01-20",
        )
        return cache

    def test_unknown_user_is_zero(self, cache):
        assert cache.sum_in_range("Nobody", "2026-01-01", "2026-12-31") == 0

    def test_full_range(self, filled):
        assert filled.sum_in_range("User", "2026-01-01", "2026-01-20") == 10

    def test_bounds_are_inclusive(self, filled):
        assert filled.sum_in_range("User", "2026-01-05", "2026-01-10") == 5

    def test_partial_range(self, filled):
        assert filled.sum_in_range("User", "2026-01-02", "2026-01-09") == 2

    def test_range_without_data_is_zero(self, filled):
        assert filled.sum_in_range("User", "2026-02-01", "2026-02-28") == 0

    def test_start_after_end_is_zero(self, filled):
        assert filled.sum_in_range("User", "2026-01-20", "2026-01-01") == 0

    def test_single_day_range(self, filled):
        assert filled.sum_in_range("User", "2026-01-10", "2026-01-10") == 3

    def test_boundary_zeros_do_not_change_sum(self, cache):
        cache.merge("User", {"2026-01-05": 5}, "2026-01-01", "2026-01-31")
        assert cache.sum_in_range("User", "2026-01-01", "2026-01-31") == 5

    def test_other_users_not_counted(self, filled):
        filled.merge("Other", {"2026-01-05": 100}, "2026-01-05", "2026-01-05")
        assert filled.sum_in_range("User", "2026-01-01", "2026-01-20") == 10


# ---------------------------------------------------------------------------
# _sum_in_range (static)
# ---------------------------------------------------------------------------


class TestSumInRangeStatic:
    def test_basic_sum(self):
        data = {"2026-01-01": 1, "2026-01-02": 2, "2026-01-03": 3}
        assert XtoolsRecentEditCache._sum_in_range(data, "2026-01-01", "2026-01-02") == 3

    def test_empty_dict(self):
        assert XtoolsRecentEditCache._sum_in_range({}, "2026-01-01", "2026-12-31") == 0

    def test_ignores_non_int_values(self):
        data = {
            "2026-01-01": 1,
            "2026-01-02": "5",
            "2026-01-03": None,
            "2026-01-04": 2.5,
            "2026-01-05": {"x": 1},
        }
        assert XtoolsRecentEditCache._sum_in_range(data, "2026-01-01", "2026-01-31") == 1

    def test_inclusive_bounds(self):
        data = {"2026-01-01": 1, "2026-01-31": 2}
        assert XtoolsRecentEditCache._sum_in_range(data, "2026-01-01", "2026-01-31") == 3

    def test_callable_on_instance_and_class(self, cache):
        data = {"2026-01-01": 4}
        assert cache._sum_in_range(data, "2026-01-01", "2026-01-01") == 4


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


class TestMerge:
    def test_creates_new_user(self, cache):
        cache.merge("User", {"2026-01-02": 3}, "2026-01-01", "2026-01-03")
        assert cache.get_counts("User") == {
            "2026-01-01": 0,
            "2026-01-02": 3,
            "2026-01-03": 0,
        }

    def test_writes_boundary_zeros_when_no_edits(self, cache):
        cache.merge("User", {}, "2026-01-01", "2026-01-31")
        assert cache.get_counts("User") == {"2026-01-01": 0, "2026-01-31": 0}

    def test_does_not_overwrite_real_counts_on_boundaries(self, cache):
        cache.merge(
            "User",
            {"2026-01-01": 9, "2026-01-31": 8},
            "2026-01-01",
            "2026-01-31",
        )
        assert cache.get_counts("User") == {"2026-01-01": 9, "2026-01-31": 8}

    def test_same_start_and_end(self, cache):
        cache.merge("User", {}, "2026-01-01", "2026-01-01")
        assert cache.get_counts("User") == {"2026-01-01": 0}

    def test_updates_existing_user(self, cache):
        cache.merge("User", {"2026-01-02": 3}, "2026-01-01", "2026-01-03")
        cache.merge("User", {"2026-01-05": 1}, "2026-01-04", "2026-01-06")
        assert cache.get_counts("User") == {
            "2026-01-01": 0,
            "2026-01-02": 3,
            "2026-01-03": 0,
            "2026-01-04": 0,
            "2026-01-05": 1,
            "2026-01-06": 0,
        }

    def test_new_counts_overwrite_old_for_same_day(self, cache):
        cache.merge("User", {"2026-01-02": 3}, "2026-01-01", "2026-01-03")
        cache.merge("User", {"2026-01-02": 10}, "2026-01-01", "2026-01-03")
        assert cache.get_counts("User")["2026-01-02"] == 10

    def test_real_count_replaces_boundary_zero(self, cache):
        cache.merge("User", {}, "2026-01-01", "2026-01-03")
        cache.merge("User", {"2026-01-03": 4}, "2026-01-03", "2026-01-05")
        assert cache.get_counts("User")["2026-01-03"] == 4

    def test_coverage_extends_after_second_merge(self, cache):
        cache.merge("User", {}, "2026-01-01", "2026-01-31")
        cache.merge("User", {}, "2026-02-01", "2026-02-28")
        assert cache.get_coverage("User") == {"start": "2026-01-01", "end": "2026-02-28"}

    def test_multiple_users_independent(self, cache):
        cache.merge("A", {"2026-01-02": 1}, "2026-01-01", "2026-01-03")
        cache.merge("B", {"2026-02-02": 2}, "2026-02-01", "2026-02-03")
        assert "2026-02-02" not in cache.get_counts("A")
        assert "2026-01-02" not in cache.get_counts("B")

    def test_username_with_spaces_and_dots(self, cache):
        cache.merge("Mr. Ibrahem", {"2026-07-02": 11}, "2026-07-02", "2026-07-03")
        assert cache.get_counts("Mr. Ibrahem")["2026-07-02"] == 11
        assert cache.has_coverage("Mr. Ibrahem") is True

    def test_does_not_save_automatically(self, cache, cache_path):
        cache.merge("User", {"2026-01-02": 3}, "2026-01-01", "2026-01-03")
        assert not cache_path.exists()
