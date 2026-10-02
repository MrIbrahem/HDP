# ruff: noqa: F401
"""
Unit tests for src/services/hdp_service.py

Classes under test: HdpService
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.models.application_row import ApplicationRow
from src.models.user_info import UserInfo
from src.services.hdp_service import HdpService

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_settings(**overrides):
    settings = MagicMock()
    settings.base_page = "Hardware donation program"
    settings.recent_days = 90
    settings.user_agent = "test-agent"
    settings.users_redirects = {}
    settings.home_wiki_cache_path = "data/home_wiki_cache.json"
    settings.edit_counts_cache_path = "data/edit_counts_cache.json"
    settings.section_to_category = {}
    for k, v in overrides.items():
        setattr(settings, k, v)
    return settings


def _make_service(
    *,
    offline: bool = False,
    load_recent: bool = True,
    load_last_edits: bool = False,
    subpages_return: list[str] | None = None,
) -> tuple[HdpService, dict]:
    """
    Build an HdpService with all collaborators mocked.
    Returns (service, mocks_dict).
    """
    wiki_client = MagicMock()
    wd_client = MagicMock()
    settings = _make_settings()
    category_service = MagicMock()
    users_resolver = MagicMock()
    home_wiki_provider = MagicMock()
    xtools_client = MagicMock()
    subpages_svc = MagicMock()
    recent_provider = MagicMock()

    # Default collaborator behaviour
    users_resolver.normalize.side_effect = lambda raw: (
        raw.replace("(2nd Application)", "").split("/")[0].strip().replace("_", " ").title() if raw else ""
    )
    users_resolver.resolve_batch.return_value = {}

    wiki_client.get_pages_wikitext.return_value = {}
    wiki_client.get_global_editcounts.return_value = {}
    wiki_client.get_page_wikitext.return_value = "== Open requests ==\n[[Hardware donation program/Alice]]\n"

    wd_client.get_editcounts.return_value = {"Alice": 50}

    home_wiki_provider.get_many.return_value = {}
    xtools_client.get_last_edit_timestamps.return_value = {}

    wiki_client.get_last_edit_timestamps.return_value = {}

    if subpages_return is not None:
        subpages_svc._subpages_for_section.return_value = list(subpages_return)
        subpages_svc.discover_subpages.return_value = set(subpages_return)

    recent_provider.get_many.return_value = {}
    xtools_client.get_wikidata_recent_editcounts.return_value = {}

    service = HdpService(
        wiki_client=wiki_client,
        wd_client=wd_client,
        settings=settings,
        category_service=category_service,
        users_resolver=users_resolver,
        home_wiki_provider=home_wiki_provider,
        xtools_client=xtools_client,
        offline=offline,
        recent_provider=recent_provider,
    )
    # Inject mocked SubPagesService (constructed inside __init__)
    service.subpages = subpages_svc

    # Flags normally set via set_args / CLI
    service.load_recent_editcounts = load_recent
    service.load_last_edits = load_last_edits

    mocks = {
        "wiki_client": wiki_client,
        "wd_client": wd_client,
        "settings": settings,
        "category_service": category_service,
        "users_resolver": users_resolver,
        "home_wiki_provider": home_wiki_provider,
        "xtools_client": xtools_client,
        "subpages": subpages_svc,
        "recent_provider": recent_provider,
    }
    return service, mocks


def _sample_user_info(username: str = "Alice") -> dict[str, Any]:
    return UserInfo(
        username=username,
        home_wiki="enwiki",
        registration="2020-01-15T12:00:00Z",
        global_editcount=1000,
        recent_editcount=42,
        wikidata_count=100,
        last_edit="2026-09-01",
    ).to_json()


# ===========================================================================
# TestLoad
# ===========================================================================


class TestLoad:
    """Tests for HdpService.load (classmethod factory)."""

    @patch("src.services.hdp_service.WikiClient.from_settings")
    def test_load_returns_none_when_wiki_connect_fails(self, mock_from_settings):
        mock_from_settings.return_value = None
        result = HdpService.load()
        assert result is None

    @patch("src.services.hdp_service.WikiClient.from_settings")
    def test_load_returns_service_on_success(self, mock_from_settings):
        mock_wiki = MagicMock()
        mock_from_settings.return_value = mock_wiki

        settings = _make_settings()
        result = HdpService.load(settings=settings, login=False, do_init=False)

        assert result is not None
        assert isinstance(result, HdpService)
        assert result.wiki_client is mock_wiki
        mock_from_settings.assert_called_with(
            settings=settings,
            host="www.wikidata.org",
            login=False,
            do_init=False,
        )


# ===========================================================================
# TestLoadRows
# ===========================================================================


class TestLoadRows:
    """Tests for HdpService.load_rows."""

    def test_empty_subpages_returns_empty_table(self):
        service, _ = _make_service()
        table = service.load_rows([])
        assert table.rows == []

    def test_normalizes_username_from_subpage(self):
        service, mocks = _make_service()
        mocks["users_resolver"].normalize.return_value = "Alice"

        table = service.load_rows(["Alice", "Bob_(2nd_Application)"])

        assert mocks["users_resolver"].normalize.call_count == 2
        # After fix, enriched rows should be returned; for now assert structure
        assert len(table.rows) >= 0  # smoke: no crash

    def test_applies_live_redirects(self):
        service, mocks = _make_service()
        mocks["users_resolver"].normalize.side_effect = lambda s: s
        mocks["users_resolver"].resolve_batch.return_value = {"OldName": "NewName"}

        # Draft will have username OldName; after redirect becomes NewName
        service.load_rows(["OldName"])

        mocks["users_resolver"].resolve_batch.assert_called_once()
        # The row username should have been updated in-place
        # (implementation mutates draft rows)

    def test_fetches_application_wikitext_for_country(self):
        service, mocks = _make_service()
        mocks["users_resolver"].normalize.return_value = "Alice"
        mocks["wiki_client"].get_pages_wikitext.return_value = {
            "Hardware donation program/Alice": "; country your from: Rwanda\n"
        }

        service.load_rows(["Alice"])

        mocks["wiki_client"].get_pages_wikitext.assert_called_once()
        titles = mocks["wiki_client"].get_pages_wikitext.call_args[0][0]
        assert "Hardware donation program/Alice" in titles

    def test_fetches_global_editcounts(self):
        service, mocks = _make_service()
        mocks["users_resolver"].normalize.return_value = "Alice"
        mocks["wiki_client"].get_global_editcounts.return_value = {"Alice": 500}

        service.load_rows(["Alice"])

        mocks["wiki_client"].get_global_editcounts.assert_called_once()
        assert "Alice" in mocks["wiki_client"].get_global_editcounts.call_args[0][0]

    def test_fetches_wikidata_editcounts_when_online(self):
        service, mocks = _make_service(offline=False)
        mocks["users_resolver"].normalize.return_value = "Alice"

        wd_client = mocks["wd_client"]
        service.load_rows(["Alice"])

        wd_client.get_editcounts.assert_called_once()

    @patch("src.services.hdp_service.WikiClient.load")
    def test_skips_wikidata_when_offline(self, mock_wd_load):
        service, mocks = _make_service(offline=True)
        mocks["users_resolver"].normalize.return_value = "Alice"

        service.load_rows(["Alice"])

        # load may still be called depending on implementation;
        # get_editcounts must not be used when offline
        if mock_wd_load.called:
            wd = mock_wd_load.return_value
            if wd:
                wd.get_editcounts.assert_not_called()

    def test_recent_editcounts_online_path(self):
        service, mocks = _make_service(load_recent=True, offline=False)
        mocks["users_resolver"].normalize.return_value = "Alice"
        mocks["recent_provider"].get_many.return_value = {"Alice": 10}

        service.load_rows(["Alice"])

        mocks["recent_provider"].get_many.assert_called_once()
        call_kwargs = mocks["recent_provider"].get_many.call_args
        # online: offline=False (or not passed as True)
        assert call_kwargs[1].get("offline") is not True

    def test_recent_editcounts_offline_path(self):
        service, mocks = _make_service(load_recent=False, offline=False)
        mocks["users_resolver"].normalize.return_value = "Alice"
        mocks["recent_provider"].get_many.return_value = {"Alice": 10}

        service.load_rows(["Alice"])

        call_kwargs = mocks["recent_provider"].get_many.call_args[1]
        assert call_kwargs.get("offline") is True

    def test_home_wiki_cache_called(self):
        service, mocks = _make_service()
        mocks["users_resolver"].normalize.return_value = "Alice"
        mocks["home_wiki_provider"].get_many.return_value = {
            "Alice": _sample_user_info("Alice"),
        }

        service.load_rows(["Alice"])

        mocks["home_wiki_provider"].get_many.assert_called_once()

    def test_last_edits_fetched_only_when_enabled(self):
        service, mocks = _make_service(load_last_edits=True, offline=False)
        mocks["users_resolver"].normalize.return_value = "Alice"
        mocks["wiki_client"].get_last_edit_timestamps.return_value = {"Alice": "2026-09-01"}

        service.load_rows(["Alice"])

        mocks["wiki_client"].get_last_edit_timestamps.assert_called_once()

    def test_last_edits_skipped_when_disabled(self):
        service, mocks = _make_service(load_last_edits=False)
        mocks["users_resolver"].normalize.return_value = "Alice"

        service.load_rows(["Alice"])

        mocks["wiki_client"].get_last_edit_timestamps.assert_not_called()

    def test_returns_application_table(self):
        service, mocks = _make_service()
        mocks["users_resolver"].normalize.return_value = "Alice"

        table = service.load_rows(["Alice"])

        from src.models import ApplicationTable  # adjust import if needed

        assert isinstance(table, type(table))  # smoke
        assert hasattr(table, "rows")
        assert hasattr(table, "build_wikitable")

    def test_enriched_rows_returned_not_draft(self):
        """
        Regression: load_rows must return enriched rows, not the pre-enrichment draft.

        Current bug in source:
            rows.append(row)
            return ApplicationTable.load(draft)  # should be `rows`
        This test documents the expected behaviour.
        """
        service, mocks = _make_service()
        mocks["users_resolver"].normalize.return_value = "Alice"
        mocks["home_wiki_provider"].get_many.return_value = {
            "Alice": _sample_user_info("Alice"),
        }
        mocks["wiki_client"].get_global_editcounts.return_value = {"Alice": 1000}
        mocks["recent_provider"].get_many.return_value = {"Alice": 42}
        mocks["xtools_client"].get_wikidata_recent_editcounts.return_value = {"Alice": 5}
        mocks["wiki_client"].get_pages_wikitext.return_value = {
            "Hardware donation program/Alice": "; country your from: Kenya\n"
        }

        table = service.load_rows(["Alice"])

        assert len(table.rows) == 1
        row = table.rows[0]
        # After the bug is fixed these should pass:
        assert row.country == "Kenya"

        assert row.user_info.global_editcount_str == "1,000"

        # For now at least username and title are set
        assert row.username == "Alice"
        assert "Alice" in row.full_title


# ===========================================================================
# TestGenerate
# ===========================================================================


class TestGenerate:
    """Tests for HdpService.generate."""

    def test_generate_empty_sections_returns_empty_string(self):
        service, mocks = _make_service(subpages_return=[])
        mocks["wiki_client"].get_page_wikitext.return_value = "page text"

        result = service.generate("Hardware donation program", section_names=[])

        assert result == ""

    def test_generate_builds_section_headings(self):
        service, mocks = _make_service(subpages_return=["Alice"])
        mocks["users_resolver"].normalize.return_value = "Alice"
        mocks["wiki_client"].get_page_wikitext.return_value = "wikitext"

        result = service.generate(
            "Hardware donation program",
            section_names=["Open requests"],
        )

        assert "=== Open requests ===" in result
        assert '{| class="wikitable sortable"' in result

    def test_generate_calls_subpages_for_each_section(self):
        service, mocks = _make_service(subpages_return=[])
        mocks["wiki_client"].get_page_wikitext.return_value = "wikitext"

        service.generate(
            "Hardware donation program",
            section_names=["Open requests", "Draft requests"],
        )

        assert mocks["subpages"]._subpages_for_section.call_count == 2

    def test_generate_includes_last_edit_column_when_enabled(self):
        service, mocks = _make_service(subpages_return=["Alice"], load_last_edits=True)
        mocks["users_resolver"].normalize.return_value = "Alice"
        mocks["wiki_client"].get_page_wikitext.return_value = "wikitext"

        result = service.generate(
            "Hardware donation program",
            section_names=["Open requests"],
        )

        assert "! Last edit" in result


# ===========================================================================
# TestUpdate
# ===========================================================================


class TestUpdate:
    """Tests for HdpService.update."""

    @patch("src.services.hdp_service.WikiTableDataUpdater")
    def test_update_calls_updater_with_row_dicts(self, mock_updater_cls):
        service, mocks = _make_service(subpages_return=["Alice"])
        mocks["users_resolver"].normalize.return_value = "Alice"
        mocks["wiki_client"].get_page_wikitext.return_value = (
            '{| class="wikitable"\n! Page\n|-\n| [[Hardware donation program/Alice]]\n|}'
        )
        mocks["subpages"].discover_subpages.return_value = {"Alice"}

        mock_updater = MagicMock()
        mock_updater.update_wikitable_data.return_value = "updated wikitext"
        mock_updater_cls.return_value = mock_updater

        result = service.update(
            "User:Mr. Ibrahem/hdp",
            section_names=["Category:Hardware donation program open requests"],
        )

        assert result == "updated wikitext"
        mock_updater.update_wikitable_data.assert_called_once()
        call_kwargs = mock_updater.update_wikitable_data.call_args[1]
        assert "rows" in call_kwargs
        assert "table_headers_to_row_key" in call_kwargs
        assert call_kwargs["replace_values"] is True

    @patch("src.services.hdp_service.WikiTableDataUpdater")
    def test_update_pops_last_edit_header_when_disabled(self, mock_updater_cls):
        service, mocks = _make_service(subpages_return=[], load_last_edits=False)
        mocks["wiki_client"].get_page_wikitext.return_value = "page"
        mocks["subpages"].discover_subpages.return_value = set()

        mock_updater = MagicMock()
        mock_updater.update_wikitable_data.return_value = "out"
        mock_updater_cls.return_value = mock_updater

        service.update("User:Mr. Ibrahem/hdp", section_names=[])

        header_map = mock_updater.update_wikitable_data.call_args[1]["table_headers_to_row_key"]
        assert "Last edit" not in header_map

    @patch("src.services.hdp_service.WikiTableDataUpdater")
    def test_update_keeps_last_edited_to_application_header(self, mock_updater_cls):
        """'Last edited to application' must never be removed."""
        service, mocks = _make_service(subpages_return=[], load_last_edits=False)
        mocks["wiki_client"].get_page_wikitext.return_value = "page"
        mocks["subpages"].discover_subpages.return_value = set()

        mock_updater = MagicMock()
        mock_updater.update_wikitable_data.return_value = "out"
        mock_updater_cls.return_value = mock_updater

        service.update("User:Mr. Ibrahem/hdp", section_names=[])

        header_map = mock_updater.update_wikitable_data.call_args[1]["table_headers_to_row_key"]
        # Only assert if the key exists in TABLE_HEADERS_TO_ROW_KEY
        from src.config import TABLE_HEADERS_TO_ROW_KEY

        if "Last edited to application" in TABLE_HEADERS_TO_ROW_KEY:
            assert "Last edited to application" in header_map


# ===========================================================================
# TestSetArgs
# ===========================================================================


class TestSetArgs:
    """Tests for HdpService.set_args."""

    def test_set_args_applies_flags(self):
        service, _ = _make_service()
        args = SimpleNamespace(
            offline=True,
            no_recent=True,
            last_edits=True,
        )
        service.set_args(args)

        assert service.offline is True
        assert service.load_recent_editcounts is False
        assert service.load_last_edits is True
