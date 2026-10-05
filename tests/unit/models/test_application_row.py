"""
Unit tests for src/models/application_row.py module.
"""

from types import SimpleNamespace

import pytest

from src.models.application_row import (
    ApplicationRow,
    extract_country,
)
from src.models.user_info import UserInfo

BASE = "Wikipedia:Hardware donation program"


def make_user_info_stub(**overrides):
    """A light stand-in for UserInfo exposing only what ApplicationRow reads."""
    data = {
        "username": "Alice",
        "last_edit": "2026-09-01",
        "user_link": "[[User:Alice|Alice]]",
        "global_editcount_str": "1,000",
        "global_without_wikidata_str": "800",
        "wikidata_editcount_str": "200",
        "recent_editcount_str": "50",
        "recent_wikidata_editcount_str": "10",
        "extended_rights": "",
        "age": "5 years",
        "home_wiki": "enwiki",
    }
    data.update(overrides)
    stub = SimpleNamespace(**data)
    stub.to_table_dict = lambda unknown="unknown": {
        "user_link": stub.user_link,
        "unknown_used": unknown,
    }
    return stub


@pytest.fixture
def row():
    return ApplicationRow(
        user_info=make_user_info_stub(),
        full_title=f"{BASE}/Alice",
        sub="Alice",
        country="Rwanda",
    )


class TestApplicationRow:
    # -- construction ------------------------------------------------------

    def test_country_defaults_to_empty(self):
        r = ApplicationRow(user_info=make_user_info_stub(), full_title="T", sub="S")
        assert r.country == ""

    # -- properties --------------------------------------------------------

    def test_username_comes_from_user_info(self, row):
        assert row.username == "Alice"

    def test_username_none(self):
        r = ApplicationRow(
            user_info=make_user_info_stub(username=None),
            full_title="T",
            sub="S",
        )
        assert r.username is None

    def test_last_edit_comes_from_user_info(self, row):
        assert row.last_edit == "2026-09-01"

    def test_last_edit_none(self):
        r = ApplicationRow(
            user_info=make_user_info_stub(last_edit=None),
            full_title="T",
            sub="S",
        )
        assert r.last_edit is None

    def test_page_link(self, row):
        assert row.page_link == f"[[{BASE}/Alice]]"

    def test_page_link_empty_title(self):
        r = ApplicationRow(user_info=make_user_info_stub(), full_title="", sub="")
        assert r.page_link == ""

    def test_last_update(self, row):
        expected = f"{{{{#time:Y-m-d|{{{{REVISIONTIMESTAMP:{BASE}/Alice}}}}}}}}"
        assert row.last_update == expected
        assert row.last_update == "{{#time:Y-m-d|{{REVISIONTIMESTAMP:" + f"{BASE}/Alice" + "}}}}"

    def test_last_update_empty_title(self):
        r = ApplicationRow(user_info=make_user_info_stub(), full_title="", sub="")
        assert r.last_update == ""

    # -- from_subpage ------------------------------------------------------

    def test_from_subpage_builds_full_title(self):
        r = ApplicationRow.from_subpage("Alice", base_page=BASE)
        assert r.full_title == f"{BASE}/Alice"
        assert r.sub == "Alice"

    def test_from_subpage_replaces_underscores(self):
        r = ApplicationRow.from_subpage("Mr._Ibrahem", base_page=BASE)
        assert r.sub == "Mr. Ibrahem"
        assert r.full_title == f"{BASE}/Mr. Ibrahem"

    def test_from_subpage_default_username_empty(self):
        r = ApplicationRow.from_subpage("Alice", base_page=BASE)
        assert isinstance(r.user_info, UserInfo)
        assert r.username == ""

    def test_from_subpage_with_username(self):
        r = ApplicationRow.from_subpage("Alice", base_page=BASE, username="Alice")
        assert r.username == "Alice"

    def test_from_subpage_country_empty(self):
        r = ApplicationRow.from_subpage("Alice", base_page=BASE)
        assert r.country == ""

    def test_from_subpage_requires_keyword_base_page(self):
        with pytest.raises(TypeError):
            ApplicationRow.from_subpage("Alice", BASE)  # type: ignore[misc]

    def test_from_subpage_returns_instance_of_cls(self):
        class Child(ApplicationRow):
            pass

        assert isinstance(Child.from_subpage("A", base_page=BASE), Child)

    # -- apply_user_info ---------------------------------------------------

    def test_apply_user_info_replaces_user_info(self, row):
        new_info = make_user_info_stub(username="Bob")
        row.apply_user_info(new_info)
        assert row.user_info is new_info
        assert row.username == "Bob"

    def test_apply_user_info_returns_self(self, row):
        assert row.apply_user_info(make_user_info_stub()) is row

    def test_apply_user_info_keeps_other_fields(self, row):
        row.apply_user_info(make_user_info_stub(username="Bob"))
        assert row.full_title == f"{BASE}/Alice"
        assert row.sub == "Alice"
        assert row.country == "Rwanda"

    # -- apply_country -----------------------------------------------------

    def test_apply_country_sets_country(self, row):
        row.apply_country("; country your from: Germany\n")
        assert row.country == "Germany"

    def test_apply_country_returns_self(self, row):
        assert row.apply_country("; country your from: Germany") is row

    def test_apply_country_missing_field_clears_country(self, row):
        row.apply_country("no country here")
        assert row.country == ""

    def test_apply_country_empty_text_clears_country(self, row):
        row.apply_country("")
        assert row.country == ""

    # -- to_table_dict -----------------------------------------------------

    def test_to_table_dict_contains_row_fields(self, row):
        data = row.to_table_dict()
        assert data["page_link"] == row.page_link
        assert data["last_update"] == row.last_update
        assert data["country"] == "Rwanda"

    def test_to_table_dict_merges_user_info_dict(self, row):
        data = row.to_table_dict()
        assert data["user_link"] == "[[User:Alice|Alice]]"

    def test_to_table_dict_passes_unknown_default(self, row):
        assert row.to_table_dict()["unknown_used"] == "unknown"

    def test_to_table_dict_passes_custom_unknown(self, row):
        assert row.to_table_dict(unknown="?")["unknown_used"] == "?"

    def test_to_table_dict_user_info_overrides_on_key_clash(self):
        info = make_user_info_stub()
        info.to_table_dict = lambda unknown="unknown": {"country": "from user_info"}
        r = ApplicationRow(user_info=info, full_title="T", sub="S", country="Rwanda")
        assert r.to_table_dict()["country"] == "from user_info"

    # -- to_json -----------------------------------------------------------

    def test_to_json_keys_and_values(self):
        r = ApplicationRow.from_subpage("Alice", base_page=BASE, username="Alice")
        r.country = "Rwanda"
        data = r.to_json()
        assert set(data) == {"approved", "user_info", "full_title", "sub", "country"}
        assert data["full_title"] == f"{BASE}/Alice"
        assert data["sub"] == "Alice"
        assert data["country"] == "Rwanda"
        assert isinstance(data["user_info"], dict)
        assert data["user_info"]["username"] == "Alice"

    def test_to_json_is_a_copy(self):
        r = ApplicationRow.from_subpage("Alice", base_page=BASE)
        data = r.to_json()
        data["sub"] = "changed"
        assert r.sub == "Alice"

    # -- build_row ---------------------------------------------------------

    def test_build_row_default(self, row):
        assert row.build_row() == [
            "|-",
            f"| [[{BASE}/Alice]]",
            f"| {row.last_update}",
            "| [[User:Alice|Alice]]",
            "| Rwanda",
            "| ",
            "| 1,000",
            "| 800",
            "| 200",
            "| 50",
            "| 10",
            "| 5 years",
            "| enwiki",
            "| ",
        ]

    def test_build_row_with_last_edit(self, row: ApplicationRow):
        lines = row.build_row(add_last_edit=True)
        assert lines[-1] == "| 2026-09-01"
        assert lines[-2] == "| "
        assert len(lines) == 15

    def test_build_row_without_last_edit_has_no_date(self, row):
        assert "| 2026-09-01" not in row.build_row()
        assert len(row.build_row()) == 14

    def test_build_row_starts_with_row_separator(self, row):
        assert row.build_row()[0] == "|-"

    def test_build_row_ends_with_empty_notes_cell(self, row):
        assert row.build_row()[-1] == "| "

    def test_build_row_empty_country(self):
        r = ApplicationRow(user_info=make_user_info_stub(), full_title="T", sub="S")
        assert r.build_row()[4] == "| "

    def test_build_row_empty_title(self):
        r = ApplicationRow(user_info=make_user_info_stub(), full_title="", sub="")
        lines = r.build_row()
        assert lines[1] == "| "
        assert lines[2] == "| "


class TestExtractCountry:
    def test_standard_format(self):
        wikitext = ";country your from:Rwanda\n"
        assert extract_country(wikitext) == "Rwanda"

    def test_space_before_value(self):
        wikitext = "; country your from: Rwanda\n"
        assert extract_country(wikitext) == "Rwanda"

    def test_no_space_after_semicolon(self):
        wikitext = ";country your from: Germany\n"
        assert extract_country(wikitext) == "Germany"

    def test_case_insensitive(self):
        wikitext = "; Country Your From: France\n"
        assert extract_country(wikitext) == "France"

    def test_multiline_takes_first_line(self):
        wikitext = "; country your from:Kenya\n== Explain your plan ==\nSome text"
        assert extract_country(wikitext) == "Kenya"

    def test_no_country_field(self):
        wikitext = "== Your contact information ==\n;your username: [[User]]\n"
        assert extract_country(wikitext) == ""

    def test_empty_string(self):
        assert extract_country("") == ""

    def test_full_application_example(self):
        wikitext = (
            "<!-- Please contact asaf@wikimedia.org if you have questions.-->\n"
            "\n"
            "== Your contact information ==\n"
            ";your username: [[username]]\n"
            ";a contact e-mail: username@gmail.com\n"
            "; country your from:Rwanda\n"
            "\n"
            "== Explain your plan ==\n"
            "I plan to use the laptop for...\n"
        )
        assert extract_country(wikitext) == "Rwanda"

    def test_country_with_trailing_whitespace(self):
        wikitext = "; country your from:  India  \n"
        assert extract_country(wikitext) == "India"

    def test_country_with_carriage_return(self):
        wikitext = "; country your from:Brazil\r\n"
        assert extract_country(wikitext) == "Brazil"
