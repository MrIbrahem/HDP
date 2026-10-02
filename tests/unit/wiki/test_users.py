"""
Unit tests for src/wiki/users.py module.

Classes to test: UserResolver
"""

import logging
from unittest.mock import MagicMock

import pytest

from src.wiki.users import UserResolver


@pytest.fixture
def wiki_client() -> MagicMock:
    client = MagicMock(name="wiki_client")
    client.solve_pages_redirects.return_value = {}
    return client


@pytest.fixture
def resolver(wiki_client) -> UserResolver:
    return UserResolver(wiki_client)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_stores_wiki_client(self, wiki_client):
        assert UserResolver(wiki_client).wiki_client is wiki_client

    def test_static_redirects_default_empty(self, wiki_client):
        assert UserResolver(wiki_client)._static == {}

    def test_static_redirects_none_is_empty(self, wiki_client):
        assert UserResolver(wiki_client, static_redirects=None)._static == {}

    def test_static_keys_are_lowercased(self, wiki_client):
        r = UserResolver(wiki_client, {"Old Name": "New Name", "UPPER": "Lower"})
        assert r._static == {"old name": "New Name", "upper": "Lower"}

    def test_values_are_kept_as_is(self, wiki_client):
        r = UserResolver(wiki_client, {"a": "MiXeD Case"})
        assert r._static["a"] == "MiXeD Case"

    def test_input_mapping_is_not_mutated(self, wiki_client):
        original = {"Old": "New"}
        UserResolver(wiki_client, original)
        assert original == {"Old": "New"}

    def test_does_not_call_wiki(self, wiki_client):
        UserResolver(wiki_client, {"a": "b"})
        assert wiki_client.mock_calls == []


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_empty_string(self, resolver):
        assert resolver.normalize("") == ""

    def test_none_returns_empty(self, resolver):
        assert resolver.normalize(None) == ""  # type: ignore[arg-type]

    def test_capitalises_first_letter(self, resolver):
        assert resolver.normalize("alice") == "Alice"

    def test_only_first_letter_is_changed(self, resolver):
        assert resolver.normalize("mR. iBrahem") == "MR. iBrahem"

    def test_already_capitalised(self, resolver):
        assert resolver.normalize("Alice") == "Alice"

    def test_single_character(self, resolver):
        assert resolver.normalize("a") == "A"

    def test_non_ascii_first_letter(self, resolver):
        assert resolver.normalize("élise") == "Élise"

    def test_non_cased_first_letter_unchanged(self, resolver):
        assert resolver.normalize("مستخدم") == "مستخدم"

    def test_digit_first_character(self, resolver):
        assert resolver.normalize("1user") == "1user"

    def test_underscores_become_spaces(self, resolver):
        assert resolver.normalize("Mr._Ibrahem") == "Mr. Ibrahem"

    def test_removes_second_application_suffix(self, resolver):
        assert resolver.normalize("Alice (2nd Application)") == "Alice"

    def test_suffix_with_underscores(self, resolver):
        assert resolver.normalize("Alice_(2nd_Application)") == "Alice"

    def test_suffix_removal_is_case_sensitive(self, resolver):
        assert resolver.normalize("Alice (2nd application)") == "Alice (2nd application)"

    def test_takes_part_before_first_slash(self, resolver):
        assert resolver.normalize("Alice/Sandbox/Extra") == "Alice"

    def test_suffix_and_slash_together(self, resolver):
        assert resolver.normalize("Alice (2nd Application)/Page") == "Alice"

    def test_strips_surrounding_whitespace(self, resolver):
        assert resolver.normalize("  Alice  ") == "Alice"

    def test_whitespace_only_returns_empty(self, resolver):
        assert resolver.normalize("   ") == ""

    def test_only_suffix_returns_empty(self, resolver):
        assert resolver.normalize("(2nd Application)") == ""

    def test_leading_slash_returns_empty(self, resolver):
        assert resolver.normalize("/Alice") == ""

    def test_internal_spaces_preserved(self, resolver):
        assert resolver.normalize("Mary Jane") == "Mary Jane"

    # -- static redirects --------------------------------------------------

    def test_static_redirect_applied(self, wiki_client):
        r = UserResolver(wiki_client, {"Oldname": "Newname"})
        assert r.normalize("Oldname") == "Newname"

    def test_static_redirect_case_insensitive_lookup(self, wiki_client):
        r = UserResolver(wiki_client, {"Oldname": "Newname"})
        assert r.normalize("oLDNAME") == "Newname"

    def test_static_redirect_after_cleaning(self, wiki_client):
        r = UserResolver(wiki_client, {"old name": "New Name"})
        assert r.normalize("Old_Name (2nd Application)/Page") == "New Name"

    def test_static_redirect_value_first_letter_capitalised(self, wiki_client):
        r = UserResolver(wiki_client, {"old": "new name"})
        assert r.normalize("old") == "New name"

    def test_static_redirect_not_applied_when_no_match(self, wiki_client):
        r = UserResolver(wiki_client, {"old": "new"})
        assert r.normalize("other") == "Other"

    def test_static_redirect_with_empty_value_falls_back(self, wiki_client):
        r = UserResolver(wiki_client, {"old": ""})
        assert r.normalize("old") == "Old"

    def test_static_redirect_is_not_applied_twice(self, wiki_client):
        r = UserResolver(wiki_client, {"a": "b", "b": "c"})
        assert r.normalize("a") == "B"

    def test_does_not_call_wiki(self, resolver, wiki_client):
        resolver.normalize("Alice")
        assert wiki_client.mock_calls == []

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("alice", "Alice"),
            ("Alice_Smith", "Alice Smith"),
            ("Bob/Application", "Bob"),
            ("carol (2nd Application)", "Carol"),
            ("", ""),
        ],
    )
    def test_parametrised_examples(self, resolver, raw, expected):
        assert resolver.normalize(raw) == expected


# ---------------------------------------------------------------------------
# resolve_batch
# ---------------------------------------------------------------------------


class TestResolveBatch:
    def test_empty_list_returns_empty_without_calling_wiki(self, resolver, wiki_client):
        assert resolver.resolve_batch([]) == {}
        wiki_client.solve_pages_redirects.assert_not_called()

    def test_only_empty_names_returns_empty_without_calling_wiki(self, resolver, wiki_client):
        assert resolver.resolve_batch(["", ""]) == {}
        wiki_client.solve_pages_redirects.assert_not_called()

    def test_builds_user_titles(self, resolver, wiki_client):
        resolver.resolve_batch(["Alice", "Bob"])
        wiki_client.solve_pages_redirects.assert_called_once_with(["User:Alice", "User:Bob"])

    def test_skips_empty_names_in_titles(self, resolver, wiki_client):
        resolver.resolve_batch(["Alice", "", "Bob"])
        wiki_client.solve_pages_redirects.assert_called_once_with(["User:Alice", "User:Bob"])

    def test_accepts_tuple(self, resolver, wiki_client):
        resolver.resolve_batch(("Alice",))
        wiki_client.solve_pages_redirects.assert_called_once_with(["User:Alice"])

    def test_no_redirects_returns_empty(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {}
        assert resolver.resolve_batch(["Alice"]) == {}

    def test_maps_source_to_destination_without_prefix(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {"User:Old": "User:New"}
        assert resolver.resolve_batch(["Old"]) == {"Old": "New"}

    def test_multiple_redirects(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {
            "User:A": "User:B",
            "User:C": "User:D",
        }
        assert resolver.resolve_batch(["A", "C"]) == {"A": "B", "C": "D"}

    def test_identical_source_and_destination_omitted(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {
            "User:Same": "User:Same",
            "User:Old": "User:New",
        }
        assert resolver.resolve_batch(["Same", "Old"]) == {"Old": "New"}

    def test_destination_without_prefix_is_kept(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {"User:Old": "New"}
        assert resolver.resolve_batch(["Old"]) == {"Old": "New"}

    def test_destination_with_spaces_and_unicode(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {"User:Old": "User:مستخدم جديد"}
        assert resolver.resolve_batch(["Old"]) == {"Old": "مستخدم جديد"}

    def test_only_leading_prefix_is_removed(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {"User:A": "User:B User:C"}
        assert resolver.resolve_batch(["A"]) == {"A": "B User:C"}

    def test_returns_new_dict(self, resolver, wiki_client):
        result = resolver.resolve_batch(["Alice"])
        assert isinstance(result, dict)

    def test_johnjoy12_redirect_is_logged(self, resolver, wiki_client, caplog):
        wiki_client.solve_pages_redirects.return_value = {"User:Johnjoy12": "User:Other"}
        with caplog.at_level(logging.INFO):
            result = resolver.resolve_batch(["Johnjoy12"])
        assert result == {"Johnjoy12": "Other"}
        assert "Johnjoy12 is a redirect to Other" in caplog.text

    def test_other_redirects_not_logged_at_info(self, resolver, wiki_client, caplog):
        wiki_client.solve_pages_redirects.return_value = {"User:Old": "User:New"}
        with caplog.at_level(logging.INFO):
            resolver.resolve_batch(["Old"])
        assert "is a redirect to" not in caplog.text

    def test_empty_input_logs_debug(self, resolver, caplog):
        with caplog.at_level(logging.DEBUG):
            resolver.resolve_batch([])
        assert "No usernames provided" in caplog.text


# ---------------------------------------------------------------------------
# normalize_and_resolve
# ---------------------------------------------------------------------------


class TestNormalizeAndResolve:
    def test_empty_input(self, resolver, wiki_client):
        assert resolver.normalize_and_resolve([]) == []
        wiki_client.solve_pages_redirects.assert_not_called()

    def test_all_empty_names_preserved_without_calling_wiki(self, resolver, wiki_client):
        assert resolver.normalize_and_resolve(["", "  ", "(2nd Application)"]) == ["", "", ""]
        wiki_client.solve_pages_redirects.assert_not_called()

    def test_normalises_without_redirects(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {}
        result = resolver.normalize_and_resolve(["alice", "Bob_Smith", "carol/Page"])
        assert result == ["Alice", "Bob Smith", "Carol"]

    def test_empty_names_are_not_sent_to_wiki(self, resolver, wiki_client):
        resolver.normalize_and_resolve(["alice", "", "bob"])
        wiki_client.solve_pages_redirects.assert_called_once_with(["User:Alice", "User:Bob"])

    def test_applies_live_redirects(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {"User:Old": "User:New"}
        assert resolver.normalize_and_resolve(["old", "other"]) == ["New", "Other"]

    def test_preserves_order_and_empties(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {"User:B": "User:Z"}
        result = resolver.normalize_and_resolve(["a", "", "b", " ", "c"])
        assert result == ["A", "", "Z", "", "C"]

    def test_duplicates_are_preserved(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {"User:A": "User:B"}
        assert resolver.normalize_and_resolve(["a", "A", "a"]) == ["B", "B", "B"]

    def test_static_redirect_then_live_redirect(self, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {"User:New": "User:Newer"}
        r = UserResolver(wiki_client, {"old": "new"})
        assert r.normalize_and_resolve(["old"]) == ["Newer"]
        wiki_client.solve_pages_redirects.assert_called_once_with(["User:New"])

    def test_live_redirect_applies_only_to_exact_normalised_name(self, resolver, wiki_client):
        wiki_client.solve_pages_redirects.return_value = {"User:alice": "User:Z"}
        # "alice" is normalised to "Alice" before lookup, so the key doesn't match
        assert resolver.normalize_and_resolve(["alice"]) == ["Alice"]

    def test_returns_list_of_same_length(self, resolver):
        names = ["a", "", "b", "c", ""]
        assert len(resolver.normalize_and_resolve(names)) == len(names)

    def test_accepts_tuple(self, resolver):
        assert resolver.normalize_and_resolve(("alice",)) == ["Alice"]

    def test_sends_normalised_names_to_wiki(self, resolver: UserResolver, wiki_client):
        resolver.normalize_and_resolve(["alice", "bob_smith"])
        wiki_client.solve_pages_redirects.assert_called_once_with(["User:Alice", "User:Bob smith"])
