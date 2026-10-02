"""
Unit tests for src/wiki/category.py module.

Classes tested: CategoryService
"""

import logging
from unittest.mock import MagicMock

import mwclient.errors
import pytest

from src.wiki.category import CategoryService


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    sleep = MagicMock()
    monkeypatch.setattr("src.wiki.category.time.sleep", sleep)
    return sleep


@pytest.fixture(autouse=True)
def no_tqdm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.wiki.category.TQDM_DISABLE", True)


@pytest.fixture
def site() -> MagicMock:
    return MagicMock(name="site")


@pytest.fixture
def service(site) -> CategoryService:
    return CategoryService(site)


def members_response(titles, cmcontinue=None):
    data = {"query": {"categorymembers": [{"title": t} for t in titles]}}
    if cmcontinue is not None:
        data["continue"] = {"cmcontinue": cmcontinue}
    return data


def api_error(code="internal_api_error"):
    return mwclient.errors.APIError(code, "info", {})


def sleep_values(mock_sleep) -> list[float]:
    return [c.args[0] for c in mock_sleep.call_args_list]


# ---------------------------------------------------------------------------
# _ensure_prefix
# ---------------------------------------------------------------------------


class TestEnsurePrefix:
    def test_adds_prefix(self):
        assert CategoryService._ensure_prefix("Yemen") == "Category:Yemen"

    def test_keeps_existing_prefix(self):
        assert CategoryService._ensure_prefix("Category:Yemen") == "Category:Yemen"

    def test_empty_string(self):
        assert CategoryService._ensure_prefix("") == "Category:"

    def test_prefix_is_case_sensitive(self):
        assert CategoryService._ensure_prefix("category:Yemen") == "Category:category:Yemen"

    def test_name_with_spaces_and_unicode(self):
        assert CategoryService._ensure_prefix("اليمن الجنوبي") == "Category:اليمن الجنوبي"


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_stores_site(self, site):
        assert CategoryService(site)._site is site


# ---------------------------------------------------------------------------
# count
# ---------------------------------------------------------------------------


class TestCount:
    @staticmethod
    def _response(info):
        page = {"pageid": 1, "ns": 14, "title": "Category:X"}
        if info is not None:
            page["categoryinfo"] = info
        return {"query": {"pages": [page]}}

    def test_returns_size(self, service, site):
        site.get.return_value = self._response({"size": 19, "pages": 3, "files": 0, "subcats": 16})
        assert service.count("Yemen") == 19

    def test_calls_api_with_prefixed_title(self, service, site):
        site.get.return_value = self._response({"size": 1})
        service.count("Yemen")
        site.get.assert_called_once_with(
            "query",
            format="json",
            prop="categoryinfo",
            titles="Category:Yemen",
            utf8=1,
            formatversion="2",
        )

    def test_does_not_double_prefix(self, service, site):
        site.get.return_value = self._response({"size": 1})
        service.count("Category:Yemen")
        assert site.get.call_args.kwargs["titles"] == "Category:Yemen"

    def test_api_exception_returns_zero(self, service, site):
        site.get.side_effect = RuntimeError("boom")
        assert service.count("Yemen") == 0

    def test_api_exception_is_logged(self, service, site, caplog):
        site.get.side_effect = RuntimeError("boom")
        with caplog.at_level(logging.ERROR):
            service.count("Yemen")
        assert "Category:Yemen" in caplog.text
        assert "boom" in caplog.text

    def test_empty_response_returns_zero(self, service, site):
        site.get.return_value = {}
        assert service.count("Yemen") == 0

    def test_no_pages_returns_zero(self, service, site):
        site.get.return_value = {"query": {"pages": []}}
        assert service.count("Yemen") == 0

    def test_pages_none_returns_zero(self, service, site):
        site.get.return_value = {"query": {"pages": None}}
        assert service.count("Yemen") == 0

    def test_missing_categoryinfo_returns_zero(self, service, site):
        site.get.return_value = self._response(None)
        assert service.count("Missing") == 0

    def test_categoryinfo_none_returns_zero(self, service, site):
        site.get.return_value = self._response(None)
        site.get.return_value["query"]["pages"][0]["categoryinfo"] = None
        assert service.count("X") == 0

    def test_missing_size_returns_zero(self, service, site):
        site.get.return_value = self._response({"pages": 3})
        assert service.count("X") == 0

    def test_size_none_returns_zero(self, service, site):
        site.get.return_value = self._response({"size": None})
        assert service.count("X") == 0

    def test_size_zero(self, service, site):
        site.get.return_value = self._response({"size": 0})
        assert service.count("X") == 0

    def test_size_string_is_converted_to_int(self, service, site):
        site.get.return_value = self._response({"size": "42"})
        result = service.count("X")
        assert result == 42
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# member_titles: request parameters
# ---------------------------------------------------------------------------


class TestMemberTitlesParams:
    def test_base_params(self, service, site):
        site.get.return_value = members_response([])
        service.member_titles("Yemen")
        site.get.assert_called_once_with(
            "query",
            format="json",
            list="categorymembers",
            cmtitle="Category:Yemen",
            cmlimit="max",
        )

    def test_does_not_double_prefix(self, service, site):
        site.get.return_value = members_response([])
        service.member_titles("Category:Yemen")
        assert site.get.call_args.kwargs["cmtitle"] == "Category:Yemen"

    def test_no_namespace_filter_by_default(self, service, site):
        site.get.return_value = members_response([])
        service.member_titles("Yemen")
        kwargs = site.get.call_args.kwargs
        assert "cmtype" not in kwargs
        assert "cmnamespace" not in kwargs

    def test_namespace_14_uses_subcat_type(self, service, site):
        site.get.return_value = members_response([])
        service.member_titles("Yemen", namespace=14)
        kwargs = site.get.call_args.kwargs
        assert kwargs["cmtype"] == "subcat"
        assert "cmnamespace" not in kwargs

    def test_namespace_6_uses_file_type(self, service, site):
        site.get.return_value = members_response([])
        service.member_titles("Yemen", namespace=6)
        kwargs = site.get.call_args.kwargs
        assert kwargs["cmtype"] == "file"
        assert "cmnamespace" not in kwargs

    def test_namespace_0_uses_cmnamespace(self, service, site):
        site.get.return_value = members_response([])
        service.member_titles("Yemen", namespace=0)
        kwargs = site.get.call_args.kwargs
        assert kwargs["cmnamespace"] == "0"
        assert "cmtype" not in kwargs

    def test_other_namespace_uses_cmnamespace_as_string(self, service, site):
        site.get.return_value = members_response([])
        service.member_titles("Yemen", namespace=10)
        assert site.get.call_args.kwargs["cmnamespace"] == "10"


# ---------------------------------------------------------------------------
# member_titles: results and pagination
# ---------------------------------------------------------------------------


class TestMemberTitlesResults:
    def test_single_page(self, service, site):
        site.get.return_value = members_response(["A", "B", "C"])
        assert service.member_titles("X") == ["A", "B", "C"]
        assert site.get.call_count == 1

    def test_empty_category(self, service, site):
        site.get.return_value = members_response([])
        assert service.member_titles("X") == []

    def test_missing_categorymembers_key(self, service, site):
        site.get.return_value = {"query": {}}
        assert service.member_titles("X") == []

    def test_categorymembers_none(self, service, site):
        site.get.return_value = {"query": {"categorymembers": None}}
        assert service.member_titles("X") == []

    def test_member_without_title_becomes_empty_string(self, service, site):
        site.get.return_value = {"query": {"categorymembers": [{"title": "A"}, {"ns": 0}]}}
        assert service.member_titles("X") == ["A", ""]

    def test_follows_continue_token(self, service, site):
        site.get.side_effect = [
            members_response(["A", "B"], cmcontinue="tok1"),
            members_response(["C"]),
        ]
        assert service.member_titles("X") == ["A", "B", "C"]
        assert site.get.call_count == 2
        assert "cmcontinue" not in site.get.call_args_list[0].kwargs
        assert site.get.call_args_list[1].kwargs["cmcontinue"] == "tok1"

    def test_follows_multiple_continue_tokens(self, service, site):
        site.get.side_effect = [
            members_response(["A"], cmcontinue="t1"),
            members_response(["B"], cmcontinue="t2"),
            members_response(["C"]),
        ]
        assert service.member_titles("X") == ["A", "B", "C"]
        tokens = [c.kwargs.get("cmcontinue") for c in site.get.call_args_list]
        assert tokens == [None, "t1", "t2"]

    def test_sleeps_between_pages(self, service, site, mock_sleep):
        site.get.side_effect = [
            members_response(["A"], cmcontinue="t1"),
            members_response(["B"]),
        ]
        service.member_titles("X")
        assert sleep_values(mock_sleep) == [0.1]

    def test_no_sleep_for_single_page(self, service, site, mock_sleep):
        site.get.return_value = members_response(["A"])
        service.member_titles("X")
        mock_sleep.assert_not_called()

    def test_continue_without_cmcontinue_stops(self, service, site):
        site.get.return_value = {
            "query": {"categorymembers": [{"title": "A"}]},
            "continue": {"continue": "-||"},
        }
        assert service.member_titles("X") == ["A"]
        assert site.get.call_count == 1

    def test_total_pages_does_not_limit_results(self, service, site):
        site.get.return_value = members_response(["A", "B", "C"])
        assert service.member_titles("X", total_pages=1) == ["A", "B", "C"]

    def test_total_pages_does_not_stop_pagination(self, service, site):
        site.get.side_effect = [
            members_response(["A", "B"], cmcontinue="t1"),
            members_response(["C"]),
        ]
        assert service.member_titles("X", total_pages=2) == ["A", "B", "C"]

    def test_returns_list_of_str(self, service, site):
        site.get.return_value = members_response(["A"])
        result = service.member_titles("X")
        assert isinstance(result, list)
        assert all(isinstance(t, str) for t in result)

    def test_keyword_only_arguments(self, service):
        with pytest.raises(TypeError):
            service.member_titles("X", 0)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# member_titles: max_items
# ---------------------------------------------------------------------------


class TestMemberTitlesMaxItems:
    def test_stops_requesting_after_max_items_reached(self, service, site):
        site.get.side_effect = [
            members_response(["A", "B"], cmcontinue="t1"),
            members_response(["C"]),
        ]
        result = service.member_titles("X", max_items=2)
        assert site.get.call_count == 1
        assert result[:2] == ["A", "B"]

    def test_continues_until_max_items_reached(self, service, site):
        site.get.side_effect = [
            members_response(["A"], cmcontinue="t1"),
            members_response(["B"], cmcontinue="t2"),
            members_response(["C"]),
        ]
        result = service.member_titles("X", max_items=2)
        assert site.get.call_count == 2
        assert result == ["A", "B"]

    def test_max_items_larger_than_available(self, service, site):
        site.get.return_value = members_response(["A", "B"])
        assert service.member_titles("X", max_items=100) == ["A", "B"]

    def test_max_items_zero_makes_no_request(self, service, site):
        assert service.member_titles("X", max_items=0) == []
        site.get.assert_not_called()

# ---------------------------------------------------------------------------
# member_titles: error handling
# ---------------------------------------------------------------------------


class TestMemberTitlesErrors:
    def test_invalidcategory_after_first_page_returns_collected(self, service: CategoryService, site, mock_sleep):
        site.get.side_effect = [
            members_response(["A"], cmcontinue="t1"),
            api_error("invalidcategory"),
        ]
        assert service.member_titles("X") == ["A"]
        assert site.get.call_count == 2
        # only the pagination sleep, no backoff sleep
        assert sleep_values(mock_sleep) == [0.1]

    def test_invalidcategory_on_first_request(self, service, site, mock_sleep):
        site.get.side_effect = api_error("invalidcategory")
        assert service.member_titles("X") == []
        assert site.get.call_count == 1
        mock_sleep.assert_not_called()

    def test_invalidcategory_logs_warning(self, service, site, caplog):
        site.get.side_effect = api_error("invalidcategory")
        with caplog.at_level(logging.WARNING):
            service.member_titles("X")
        assert "Invalid category" in caplog.text

    def test_api_error_is_retried_and_recovers(self, service, site, mock_sleep):
        site.get.side_effect = [
            members_response(["A"], cmcontinue="t1"),
            api_error(),
            members_response(["B"]),
        ]
        assert service.member_titles("X") == ["A", "B"]
        # pagination sleep, then one backoff sleep
        assert sleep_values(mock_sleep) == [0.1, 0.1]

    def test_retry_keeps_same_continue_token(self, service, site):
        site.get.side_effect = [
            members_response(["A"], cmcontinue="t1"),
            api_error(),
            members_response(["B"]),
        ]
        service.member_titles("X")
        calls = site.get.call_args_list
        assert calls[1].kwargs["cmcontinue"] == "t1"
        assert calls[2].kwargs["cmcontinue"] == "t1"

    def test_generic_exception_is_retried_and_recovers(self, service, site):
        site.get.side_effect = [
            members_response(["A"], cmcontinue="t1"),
            ConnectionError("net down"),
            members_response(["B"]),
        ]
        assert service.member_titles("X") == ["A", "B"]

    def test_api_error_backoff_doubles_up_to_max_then_gives_up(self, service, site, mock_sleep):
        site.get.side_effect = [members_response(["A"], cmcontinue="t1")] + [api_error()] * 20
        result = service.member_titles("X")
        assert result == ["A"]
        # 1 successful call + 8 failing calls (7 backoff sleeps, 8th gives up)
        assert site.get.call_count == 9
        assert sleep_values(mock_sleep) == pytest.approx([0.1, 0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4])

    def test_generic_exception_backoff_gives_up(self, service, site, mock_sleep):
        site.get.side_effect = [members_response(["A"], cmcontinue="t1")] + [OSError("x")] * 20
        assert service.member_titles("X") == ["A"]
        assert site.get.call_count == 9
        assert sleep_values(mock_sleep)[1:] == pytest.approx([0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4])

    def test_backoff_never_exceeds_max_delay(self, service, site, mock_sleep):
        site.get.side_effect = [members_response(["A"], cmcontinue="t1")] + [api_error()] * 20
        service.member_titles("X")
        assert max(sleep_values(mock_sleep)) <= 8.0

    def test_delay_resets_after_success(self, service, site, mock_sleep):
        site.get.side_effect = [
            members_response(["A"], cmcontinue="t1"),
            api_error(),
            api_error(),
            members_response(["B"], cmcontinue="t2"),
            api_error(),
            members_response(["C"]),
        ]
        assert service.member_titles("X") == ["A", "B", "C"]
        # continue-sleep, backoff 0.1, 0.2, continue-sleep (reset), backoff 0.1 (reset)
        assert sleep_values(mock_sleep) == pytest.approx([0.1, 0.1, 0.2, 0.1, 0.1])

    def test_errors_are_logged(self, service, site, caplog):
        site.get.side_effect = [
            members_response(["A"], cmcontinue="t1"),
            api_error("some_code"),
            members_response(["B"]),
        ]
        with caplog.at_level(logging.ERROR):
            service.member_titles("X")
        assert "some_code" in caplog.text

    def test_max_retries_is_logged(self, service, site, caplog):
        site.get.side_effect = [members_response(["A"], cmcontinue="t1")] + [api_error()] * 20
        with caplog.at_level(logging.ERROR):
            service.member_titles("X")
        assert "Max delay reached" in caplog.text

    def test_first_request_error_returns_empty_without_raising(self, service, site):
        site.get.side_effect = api_error()
        assert service.member_titles("X") == []

# ---------------------------------------------------------------------------
# EdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """@pytest.mark.xfail(
        reason="member_titles may return more than max_items when a page overshoots it",
        strict=False,
    )"""
    def test_result_is_truncated_to_max_items(self, service, site):
        site.get.return_value = members_response(["A", "B", "C"], cmcontinue="t1")
        assert service.member_titles("X", max_items=2) == ["A", "B"]


    """@pytest.mark.xfail(
        reason=(
            "The loop condition is `first or cmcontinue is not None`; after a failure on the "
            "very first request `first` is False and cmcontinue is None, so no retry happens"
        ),
        strict=False,
    )"""
    def test_first_request_error_is_retried(self, service, site):
        site.get.side_effect = [api_error(), members_response(["A"])]
        assert service.member_titles("X") == ["A"]

    def test_first_request_gives_up_after_max_backoff(self, service, site, mock_sleep):
        site.get.side_effect = api_error()
        assert service.member_titles("X") == []
        assert site.get.call_count == 8
        assert sleep_values(mock_sleep) == pytest.approx([0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4])
