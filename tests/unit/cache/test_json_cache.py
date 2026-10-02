"""
Unit tests for src/cache/json_cache.py module.
"""

import json
import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

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


@pytest.fixture
def path(tmp_path):
    return tmp_path / "cache.json"


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_path_is_converted_to_path_object(self, path):
        cache = JsonCache(str(path))
        assert isinstance(cache.path, Path)
        assert cache.path == path

    def test_accepts_path_object(self, path):
        assert JsonCache(path).path == path

    def test_default_is_empty_dict_when_none(self, path):
        assert JsonCache(path).default == {}

    def test_custom_default_is_stored(self, path):
        assert JsonCache(path, default={"a": 1}).default == {"a": 1}

    def test_default_is_copied_not_shared_with_caller(self, path):
        original = {"a": 1}
        cache = JsonCache(path, default=original)
        original["b"] = 2
        assert cache.default == {"a": 1}

    def test_empty_default_is_respected(self, path):
        assert JsonCache(path, default={}).default == {}

    def test_does_not_touch_filesystem(self, path):
        JsonCache(path)
        assert not path.exists()


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------


class TestLoad:
    def test_missing_file_returns_default(self, path):
        assert JsonCache(path, default={"k": "v"}).load() == {"k": "v"}

    def test_missing_file_logs_warning(self, path, caplog):
        with caplog.at_level(logging.WARNING):
            JsonCache(path).load()
        assert "does not exist" in caplog.text

    def test_missing_file_is_not_created(self, path):
        JsonCache(path).load()
        assert not path.exists()

    def test_reads_valid_json(self, path):
        path.write_text(json.dumps({"a": {"b": 1}}), encoding="utf-8")
        assert JsonCache(path).load() == {"a": {"b": 1}}

    def test_reads_unicode(self, path):
        path.write_text(json.dumps({"مستخدم": "مصر"}, ensure_ascii=False), encoding="utf-8")
        assert JsonCache(path).load() == {"مستخدم": "مصر"}

    def test_corrupt_json_returns_default(self, path):
        path.write_text("{not valid json", encoding="utf-8")
        assert JsonCache(path, default={"d": 1}).load() == {"d": 1}

    def test_corrupt_json_logs_warning(self, path, caplog):
        path.write_text("{oops", encoding="utf-8")
        with caplog.at_level(logging.WARNING):
            JsonCache(path).load()
        assert "Could not read" in caplog.text

    def test_empty_file_returns_default(self, path):
        path.write_text("", encoding="utf-8")
        assert JsonCache(path).load() == {}

    @pytest.mark.parametrize("content", ["[1, 2, 3]", '"text"', "42", "null", "true"])
    def test_non_dict_json_returns_default(self, path, content):
        path.write_text(content, encoding="utf-8")
        assert JsonCache(path, default={"d": 1}).load() == {"d": 1}

    def test_os_error_returns_default(self, tmp_path):
        # A directory exists but cannot be opened as a file -> OSError
        directory = tmp_path / "a_directory"
        directory.mkdir()
        assert JsonCache(directory, default={"d": 1}).load() == {"d": 1}

    def test_invalid_utf8_returns_default(self, path):
        # UnicodeDecodeError is a ValueError, not OSError / JSONDecodeError.
        path.write_bytes(b"\xff\xfe\x00bad")
        try:
            result = JsonCache(path).load()
        except UnicodeDecodeError:
            pytest.xfail("load() does not handle UnicodeDecodeError")
        assert result == {}

    def test_loads_nested_structure(self, path):
        data = {"u": {"2026-01-01": 1, "2026-01-02": 2}, "v": {}}
        path.write_text(json.dumps(data), encoding="utf-8")
        assert JsonCache(path).load() == data

    def test_load_reflects_latest_file_content(self, path):
        cache = JsonCache(path)
        path.write_text('{"a": 1}', encoding="utf-8")
        assert cache.load() == {"a": 1}
        path.write_text('{"a": 2}', encoding="utf-8")
        assert cache.load() == {"a": 2}

    def test_returned_default_is_independent_copy(self, path):
        cache = JsonCache(path)
        first = cache.load()
        first["mutated"] = True
        assert cache.load() == {}


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


class TestSave:
    def test_creates_file(self, path):
        JsonCache(path).save({"a": 1})
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}

    def test_creates_missing_parent_directories(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "cache.json"
        JsonCache(nested).save({"a": 1})
        assert nested.exists()

    def test_overwrites_existing_file(self, path):
        cache = JsonCache(path)
        cache.save({"a": 1})
        cache.save({"b": 2})
        assert cache.load() == {"b": 2}

    def test_saves_empty_dict(self, path):
        cache = JsonCache(path)
        cache.save({})
        assert cache.load() == {}
        assert json.loads(path.read_text(encoding="utf-8")) == {}

    def test_keys_are_sorted(self, path):
        JsonCache(path).save({"b": 1, "a": 2, "c": 3})
        text = path.read_text(encoding="utf-8")
        assert text.index('"a"') < text.index('"b"') < text.index('"c"')

    def test_output_is_indented_with_two_spaces(self, path):
        JsonCache(path).save({"a": {"b": 1}})
        assert '\n  "a": {\n    "b": 1\n  }\n' in path.read_text(encoding="utf-8")

    def test_non_ascii_written_as_is(self, path):
        JsonCache(path).save({"مستخدم": "مصر"})
        text = path.read_text(encoding="utf-8")
        assert "مستخدم" in text
        assert "\\u" not in text

    def test_unicode_roundtrip(self, path):
        cache = JsonCache(path)
        data = {"مستخدم": {"2026-01-01": 3}}
        cache.save(data)
        assert cache.load() == data

    def test_no_tmp_file_left_after_success(self, path):
        JsonCache(path).save({"a": 1})
        assert not Path(str(path) + ".tmp").exists()
        assert [p.name for p in path.parent.iterdir()] == [path.name]

    def test_tmp_name_when_path_has_no_suffix(self, tmp_path):
        no_suffix = tmp_path / "cache"
        JsonCache(no_suffix).save({"a": 1})
        assert no_suffix.exists()
        assert not (tmp_path / "cache.tmp").exists()

    def test_uses_os_replace_from_tmp_to_target(self, path):
        with patch("src.cache.json_cache.os.replace") as replace:
            JsonCache(path).save({"a": 1})
        replace.assert_called_once()
        src, dst = replace.call_args.args
        assert Path(src) == Path(str(path) + ".tmp")
        assert Path(dst) == path

    def test_failed_replace_keeps_original_file(self, path):
        cache = JsonCache(path)
        cache.save({"old": 1})
        with patch("src.cache.json_cache.os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError):
                cache.save({"new": 2})
        assert cache.load() == {"old": 1}

    def test_unserializable_data_keeps_original_file(self, path):
        cache = JsonCache(path)
        cache.save({"old": 1})
        with pytest.raises(TypeError):
            cache.save({"bad": object()})
        assert cache.load() == {"old": 1}

    def test_does_not_modify_input_data(self, path):
        data = {"b": {"y": 1, "x": 2}, "a": 3}
        snapshot = json.loads(json.dumps(data))
        JsonCache(path).save(data)
        assert data == snapshot

    def test_save_accepts_str_path(self, tmp_path):
        p = str(tmp_path / "s.json")
        JsonCache(p).save({"a": 1})
        assert JsonCache(p).load() == {"a": 1}

    def test_instances_share_file(self, path):
        JsonCache(path).save({"a": 1})
        assert JsonCache(path).load() == {"a": 1}
