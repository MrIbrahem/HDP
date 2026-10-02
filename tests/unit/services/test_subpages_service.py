"""
Unit tests for src/services/subpages_service.py module.
"""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.parsing.links import LinkExtractor
from src.services.subpages_service import SubPagesService

BASE = "Wikipedia:WikiProject Medicine/Translation"


@pytest.fixture
def wiki_client():
    client = MagicMock(name="wiki_client")
    client.site = MagicMock(name="site")
    client.get_page_wikitext.return_value = "FETCHED WIKITEXT"
    return client


@pytest.fixture
def settings():
    return SimpleNamespace(
        base_page=BASE,
        section_to_category={"Mapped": "Category:Mapped cat"},
    )


@pytest.fixture
def category_service():
    return MagicMock(name="category_service")


@pytest.fixture
def service(wiki_client, settings, category_service):
    svc = SubPagesService(
        wiki_client=wiki_client,
        settings=settings,
        category_service=category_service,
    )
    svc.extractor = MagicMock(name="extractor")
    return svc


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_stores_dependencies(self, wiki_client, settings, category_service):
        svc = SubPagesService(
            wiki_client=wiki_client,
            settings=settings,
            category_service=category_service,
        )
        assert svc.wiki_client is wiki_client
        assert svc.settings is settings
        assert svc.category_service is category_service

    def test_creates_default_category_service_from_site(self, wiki_client, settings):
        with patch("src.services.subpages_service.CategoryService") as cs_cls:
            svc = SubPagesService(wiki_client=wiki_client, settings=settings)
        cs_cls.assert_called_once_with(wiki_client.site)
        assert svc.category_service is cs_cls.return_value

    def test_custom_category_service_skips_default(self, wiki_client, settings, category_service):
        with patch("src.services.subpages_service.CategoryService") as cs_cls:
            SubPagesService(
                wiki_client=wiki_client,
                settings=settings,
                category_service=category_service,
            )
        cs_cls.assert_not_called()

    def test_creates_link_extractor(self, wiki_client, settings, category_service):
        svc = SubPagesService(
            wiki_client=wiki_client,
            settings=settings,
            category_service=category_service,
        )
        assert isinstance(svc.extractor, LinkExtractor)

    def test_requires_keyword_arguments(self, wiki_client, settings):
        with pytest.raises(TypeError):
            SubPagesService(wiki_client, settings)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _subpages_from_category
# ---------------------------------------------------------------------------


class TestSubpagesFromCategory:
    def test_strips_base_prefix(self, service, category_service):
        category_service.count.return_value = 2
        category_service.member_titles.return_value = [f"{BASE}/Aspirin", f"{BASE}/Insulin"]
        result = service._subpages_from_category("Category:X")
        assert result == ["Aspirin", "Insulin"]

    def test_calls_category_service_with_expected_args(self, service, category_service):
        category_service.count.return_value = 7
        category_service.member_titles.return_value = []
        service._subpages_from_category("Category:X")
        category_service.count.assert_called_once_with("Category:X")
        category_service.member_titles.assert_called_once_with(
            "Category:X",
            namespace=0,
            total_pages=7,
        )

    def test_ignores_members_outside_base(self, service, category_service):
        category_service.count.return_value = 3
        category_service.member_titles.return_value = [
            f"{BASE}/Aspirin",
            "Other page/Aspirin",
            "Random",
        ]
        assert service._subpages_from_category("Category:X") == ["Aspirin"]

    def test_ignores_base_page_itself(self, service, category_service):
        category_service.count.return_value = 1
        category_service.member_titles.return_value = [BASE]
        assert service._subpages_from_category("Category:X") == []

    def test_ignores_title_sharing_prefix_without_slash(self, service, category_service):
        category_service.count.return_value = 1
        category_service.member_titles.return_value = [f"{BASE} extra/Page"]
        assert service._subpages_from_category("Category:X") == []

    def test_keeps_nested_subpage_path(self, service, category_service):
        category_service.count.return_value = 1
        category_service.member_titles.return_value = [f"{BASE}/A/B"]
        assert service._subpages_from_category("Category:X") == ["A/B"]

    def test_empty_category(self, service, category_service):
        category_service.count.return_value = 0
        category_service.member_titles.return_value = []
        assert service._subpages_from_category("Category:X") == []

    def test_preserves_member_order(self, service, category_service):
        category_service.count.return_value = 3
        category_service.member_titles.return_value = [f"{BASE}/C", f"{BASE}/A", f"{BASE}/B"]
        assert service._subpages_from_category("Category:X") == ["C", "A", "B"]


# ---------------------------------------------------------------------------
# _subpages_for_section
# ---------------------------------------------------------------------------


class TestSubpagesForSection:
    def test_category_prefix_uses_category_directly(self, service):
        with patch.object(service, "_subpages_from_category", return_value=["A"]) as m:
            result = service._subpages_for_section("text", "Category:Direct")
        m.assert_called_once_with("Category:Direct")
        assert result == ["A"]
        service.extractor.get_section.assert_not_called()

    def test_category_prefix_wins_over_mapping(self, service, settings):
        settings.section_to_category["Category:Direct"] = "Category:Other"
        with patch.object(service, "_subpages_from_category", return_value=[]) as m:
            service._subpages_for_section("text", "Category:Direct")
        m.assert_called_once_with("Category:Direct")

    def test_mapped_section_uses_mapped_category(self, service):
        with patch.object(service, "_subpages_from_category", return_value=["B"]) as m:
            result = service._subpages_for_section("text", "Mapped")
        m.assert_called_once_with("Category:Mapped cat")
        assert result == ["B"]
        service.extractor.get_section.assert_not_called()

    def test_unmapped_section_parses_wikitext(self, service):
        section = object()
        service.extractor.get_section.return_value = section
        service.extractor.extract_subpages.return_value = ["X", "Y"]

        result = service._subpages_for_section("full text", "Plain")

        service.extractor.get_section.assert_called_once_with("full text", "Plain")
        service.extractor.extract_subpages.assert_called_once_with(BASE, section)
        assert result == ["X", "Y"]

    def test_missing_section_returns_empty_and_warns(self, service, caplog):
        service.extractor.get_section.return_value = None
        with caplog.at_level(logging.WARNING):
            result = service._subpages_for_section("full text", "Missing")
        assert result == []
        service.extractor.extract_subpages.assert_not_called()
        assert "Missing" in caplog.text

    def test_does_not_call_category_for_plain_section(self, service):
        service.extractor.get_section.return_value = object()
        service.extractor.extract_subpages.return_value = []
        with patch.object(service, "_subpages_from_category") as m:
            service._subpages_for_section("text", "Plain")
        m.assert_not_called()


# ---------------------------------------------------------------------------
# _all_subpage_links
# ---------------------------------------------------------------------------


class TestAllSubpageLinks:
    def test_returns_set_from_extractor(self, service):
        service.extractor.extract_subpages.return_value = ["A", "B"]
        result = service._all_subpage_links("[[x]]")
        assert result == {"A", "B"}
        assert isinstance(result, set)

    def test_deduplicates(self, service):
        service.extractor.extract_subpages.return_value = ["A", "A", "B"]
        assert service._all_subpage_links("text") == {"A", "B"}

    def test_passes_base_page_and_parsed_text(self, service):
        service.extractor.extract_subpages.return_value = []
        service._all_subpage_links("some [[link]] text")
        args = service.extractor.extract_subpages.call_args.args
        assert args[0] == BASE
        assert args[1].string == "some [[link]] text"

    def test_empty_result(self, service):
        service.extractor.extract_subpages.return_value = []
        assert service._all_subpage_links("") == set()


# ---------------------------------------------------------------------------
# discover_subpages
# ---------------------------------------------------------------------------


class TestDiscoverSubpages:
    def test_fetches_wikitext_when_not_provided(self, service, wiki_client):
        with patch.object(service, "_subpages_for_section", return_value=["A"]) as m:
            service.discover_subpages("Page", ["S1"])
        wiki_client.get_page_wikitext.assert_called_once_with("Page")
        m.assert_called_once_with("FETCHED WIKITEXT", "S1")

    def test_empty_wikitext_triggers_fetch(self, service, wiki_client):
        with patch.object(service, "_subpages_for_section", return_value=["A"]):
            service.discover_subpages("Page", ["S1"], full_wikitext="")
        wiki_client.get_page_wikitext.assert_called_once_with("Page")

    def test_uses_provided_wikitext_without_fetching(self, service, wiki_client):
        with patch.object(service, "_subpages_for_section", return_value=["A"]) as m:
            service.discover_subpages("Page", ["S1"], full_wikitext="GIVEN")
        wiki_client.get_page_wikitext.assert_not_called()
        m.assert_called_once_with("GIVEN", "S1")

    def test_collects_union_across_sections(self, service):
        results = {"S1": ["A", "B"], "S2": ["B", "C"]}
        with patch.object(
            service,
            "_subpages_for_section",
            side_effect=lambda text, title: results[title],
        ):
            found = service.discover_subpages("Page", ["S1", "S2"], full_wikitext="T")
        assert found == {"A", "B", "C"}
        assert isinstance(found, set)

    def test_accepts_any_sequence(self, service):
        with patch.object(service, "_subpages_for_section", return_value=["A"]):
            found = service.discover_subpages("Page", ("S1",), full_wikitext="T")
        assert found == {"A"}

    def test_no_fallback_when_something_found(self, service):
        with (
            patch.object(service, "_subpages_for_section", return_value=["A"]),
            patch.object(service, "_all_subpage_links") as fallback,
        ):
            service.discover_subpages("Page", ["S1"], full_wikitext="T")
        fallback.assert_not_called()

    def test_fallback_when_nothing_found(self, service):
        with (
            patch.object(service, "_subpages_for_section", return_value=[]),
            patch.object(service, "_all_subpage_links", return_value={"Z"}) as fallback,
        ):
            found = service.discover_subpages("Page", ["S1", "S2"], full_wikitext="T")
        fallback.assert_called_once_with("T")
        assert found == {"Z"}

    def test_fallback_when_no_sections_given(self, service):
        with patch.object(service, "_all_subpage_links", return_value={"Z"}) as fallback:
            found = service.discover_subpages("Page", [], full_wikitext="T")
        fallback.assert_called_once_with("T")
        assert found == {"Z"}

    def test_fallback_receives_fetched_wikitext(self, service):
        with (
            patch.object(service, "_subpages_for_section", return_value=[]),
            patch.object(service, "_all_subpage_links", return_value=set()) as fallback,
        ):
            service.discover_subpages("Page", ["S1"])
        fallback.assert_called_once_with("FETCHED WIKITEXT")

    def test_empty_when_fallback_also_empty(self, service):
        with (
            patch.object(service, "_subpages_for_section", return_value=[]),
            patch.object(service, "_all_subpage_links", return_value=set()),
        ):
            assert service.discover_subpages("Page", ["S1"], full_wikitext="T") == set()

    def test_logs_total_count(self, service, caplog):
        with (
            patch.object(service, "_subpages_for_section", return_value=["A", "B"]),
            caplog.at_level(logging.INFO),
        ):
            service.discover_subpages("Page", ["S1"], full_wikitext="T")
        assert "Total subpages collected: 2" in caplog.text

    def test_integration_category_section_end_to_end(self, service, category_service):
        category_service.count.return_value = 2
        category_service.member_titles.return_value = [f"{BASE}/Aspirin", f"{BASE}/Insulin"]
        found = service.discover_subpages("Page", ["Mapped"], full_wikitext="T")
        assert found == {"Aspirin", "Insulin"}

    def test_integration_wikitext_section_end_to_end(self, service):
        section = object()
        service.extractor.get_section.return_value = section
        service.extractor.extract_subpages.return_value = ["Aspirin"]
        found = service.discover_subpages("Page", ["Plain"], full_wikitext="T")
        assert found == {"Aspirin"}
