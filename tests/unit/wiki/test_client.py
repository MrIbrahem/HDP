# ruff: noqa: F401
"""
Unit tests for src/wiki/client.py

Classes under test:
  - WikiClientLoader  (page content + user helpers)
  - WikiClient        (connection factories)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import mwclient.errors
import pytest

from src.config import Credentials, Settings
from src.wiki.client import METAWIKI_HOST, WikiClient, WikiClientLoader


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.wiki.client.time.sleep", MagicMock())


@pytest.fixture
def mock_site_cls(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    _mock_class = MagicMock()
    _mock_instance = MagicMock()
    _mock_class.return_value = _mock_instance
    monkeypatch.setattr("src.wiki.client.Site", _mock_class)
    return _mock_class


class TestRealNetwork:
    @pytest.mark.network
    def test_get_editcounts(self) -> None:
        site = WikiClient.load(host="www.wikidata.org", login=False)
        assert site is not None

        res = site.get_editcounts(["Mr. Ibrahem"])
        assert res["Mr. Ibrahem"] > 1_711_570

    @pytest.mark.network
    def test_get_global_editcounts(self):
        site = WikiClient.load(host="meta.wikimedia.org", login=False)
        assert site is not None

        res = site.get_global_editcounts(["Mr. Ibrahem"])
        assert res["Mr. Ibrahem"] > 1_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_site() -> MagicMock:
    site = MagicMock()
    site.get = MagicMock()
    site.pages = MagicMock()
    return site


def _loader(site: MagicMock | None = None) -> tuple[WikiClientLoader, MagicMock]:
    site = site or _mock_site()
    return WikiClientLoader(site), site


def _client(site: MagicMock | None = None) -> tuple[WikiClient, MagicMock]:
    site = site or _mock_site()
    return WikiClient(site), site


# ===========================================================================
# WikiClientLoader — page content
# ===========================================================================


class TestGetPageWikitext:
    def test_returns_text_on_success(self):
        loader, site = _loader()
        page = MagicMock()
        page.text.return_value = "== Hello ==\nWorld"
        site.pages.__getitem__.return_value = page

        assert loader.get_page_wikitext("Foo") == "== Hello ==\nWorld"
        site.pages.__getitem__.assert_called_once_with("Foo")

    def test_returns_empty_string_when_text_is_none(self):
        loader, site = _loader()
        page = MagicMock()
        page.text.return_value = None
        site.pages.__getitem__.return_value = page

        assert loader.get_page_wikitext("Foo") == ""

    def test_returns_empty_string_on_exception(self):
        loader, site = _loader()
        site.pages.__getitem__.side_effect = RuntimeError("network")

        assert loader.get_page_wikitext("Foo") == ""


class TestGetPagesWikitext:
    def test_empty_titles_returns_empty_dict(self):
        loader, _ = _loader()
        assert loader.get_pages_wikitext([]) == {}

    def test_single_batch_parses_content(self):
        loader, site = _loader()
        site.get.return_value = {
            "query": {
                "pages": [
                    {
                        "title": "Page A",
                        "revisions": [
                            {"slots": {"main": {"content": "text-a"}}},
                        ],
                    },
                    {
                        "title": "Page B",
                        "revisions": [
                            {"slots": {"main": {"content": "text-b"}}},
                        ],
                    },
                ]
            }
        }

        result = loader.get_pages_wikitext(["Page A", "Page B"], batch_size=50)

        assert result == {"Page A": "text-a", "Page B": "text-b"}
        site.get.assert_called_once()
        params = site.get.call_args[1]
        assert params["titles"] == "Page A|Page B"
        assert params["prop"] == "revisions"

    def test_missing_pages_are_omitted(self):
        loader, site = _loader()
        site.get.return_value = {
            "query": {
                "pages": [
                    {"title": "Missing", "missing": True},
                    {
                        "title": "Present",
                        "revisions": [{"slots": {"main": {"content": "ok"}}}],
                    },
                ]
            }
        }

        result = loader.get_pages_wikitext(["Missing", "Present"])
        assert "Missing" not in result
        assert result["Present"] == "ok"

    def test_pages_without_revisions_are_omitted(self):
        loader, site = _loader()
        site.get.return_value = {
            "query": {
                "pages": [
                    {"title": "NoRev", "revisions": []},
                ]
            }
        }

        assert loader.get_pages_wikitext(["NoRev"]) == {}

    def test_api_exception_skips_batch_and_continues(self):
        loader, site = _loader()
        site.get.side_effect = RuntimeError("boom")

        # Should not raise
        result = loader.get_pages_wikitext(["A", "B"])
        assert result == {}

    def test_batches_respect_batch_size(self):
        loader, site = _loader()
        site.get.return_value = {"query": {"pages": []}}

        titles = [f"P{i}" for i in range(5)]
        loader.get_pages_wikitext(titles, batch_size=2)

        # 5 titles / batch_size 2 → 3 batches
        assert site.get.call_count == 3


class TestPageLastEditTimestamp:
    def test_returns_timestamp(self):
        loader, site = _loader()
        site.get.return_value = {
            "query": {
                "pages": [
                    {"revisions": [{"timestamp": "2026-09-01T12:00:00Z"}]},
                ]
            }
        }

        assert loader.page_last_edit_timestamp("Foo") == "2026-09-01T12:00:00Z"

    def test_returns_none_when_no_revisions(self):
        loader, site = _loader()
        site.get.return_value = {"query": {"pages": [{"title": "Foo"}]}}

        assert loader.page_last_edit_timestamp("Foo") is None

    def test_returns_none_on_api_error(self):
        loader, site = _loader()
        site.get.side_effect = RuntimeError("fail")

        assert loader.page_last_edit_timestamp("Foo") is None

    def test_query_params(self):
        loader, site = _loader()
        site.get.return_value = {"query": {"pages": []}}

        loader.page_last_edit_timestamp("Bar")

        params = site.get.call_args[1]
        assert params["prop"] == "revisions"
        assert params["titles"] == "Bar"
        assert params["rvlimit"] == 1
        assert params["rvprop"] == "timestamp"


class TestGetPageCreator:
    def test_returns_username(self):
        loader, site = _loader()
        site.get.return_value = {
            "query": {
                "pages": [
                    {"revisions": [{"user": "Alice"}]},
                ]
            }
        }

        assert loader.get_page_creator("Foo") == "Alice"

    def test_returns_none_when_no_revisions(self):
        loader, site = _loader()
        site.get.return_value = {"query": {"pages": [{"title": "Foo"}]}}

        assert loader.get_page_creator("Foo") is None

    def test_returns_none_on_api_error(self):
        loader, site = _loader()
        site.get.side_effect = RuntimeError("fail")

        assert loader.get_page_creator("Foo") is None

    def test_uses_rvdir_newer(self):
        loader, site = _loader()
        site.get.return_value = {"query": {"pages": []}}

        loader.get_page_creator("Foo")

        params = site.get.call_args[1]
        assert params["rvdir"] == "newer"
        assert params["rvprop"] == "user"


# ===========================================================================
# WikiClientLoader — users
# ===========================================================================


class TestGetEditCount:
    def test_get_editcounts_empty(self):
        res = WikiClient({}).get_editcounts([])
        assert res == {}

    def test_get_editcounts_mocked_site(self):
        mock_site = MagicMock()
        mock_site.get.return_value = {
            "query": {
                "users": [
                    {"name": "UserA", "editcount": 1500},
                    {"name": "UserB", "editcount": 42},
                ]
            }
        }

        users = ["UserA", "UserB"]
        res = WikiClient(mock_site).get_editcounts(users)

        assert res == {"UserA": 1500, "UserB": 42}
        mock_site.get.assert_called_once_with(
            "query",
            list="users",
            usprop="editcount",
            ususers="UserA|UserB",
            formatversion=2,
            format="json",
        )

    def test_get_editcounts_batching(self):
        mock_site = MagicMock()
        # Batch size is 50. Provide 55 users.
        users = [f"User{i}" for i in range(55)]

        def side_effect(action, **kwargs):
            ususers = kwargs.get("ususers", "").split("|")
            return {"query": {"users": [{"name": u, "editcount": 10} for u in ususers]}}

        mock_site.get.side_effect = side_effect

        res = WikiClient(mock_site).get_editcounts(users)
        assert len(res) == 55
        assert res["User0"] == 10
        assert res["User54"] == 10
        assert mock_site.get.call_count == 2


class TestGetEditcounts:
    def test_empty_users_returns_empty(self):
        loader, _ = _loader()
        assert loader.get_editcounts([]) == {}

    def test_parses_editcounts(self):
        loader, site = _loader()
        site.get.return_value = {
            "query": {
                "users": [
                    {"name": "Alice", "editcount": 100},
                    {"name": "Bob", "editcount": 200},
                ]
            }
        }

        result = loader.get_editcounts(["Alice", "Bob"])
        assert result == {"Alice": 100, "Bob": 200}

    def test_defaults_missing_users_to_zero(self):
        loader, site = _loader()
        site.get.return_value = {
            "query": {
                "users": [
                    {"name": "Alice", "editcount": 50},
                ]
            }
        }

        result = loader.get_editcounts(["Alice", "Unknown"])
        assert result["Alice"] == 50
        assert result["Unknown"] == 0

    def test_api_error_keeps_zeros(self):
        loader, site = _loader()
        site.get.side_effect = RuntimeError("fail")

        result = loader.get_editcounts(["Alice"])
        assert result == {"Alice": 0}

    def test_batches(self):
        loader, site = _loader()
        site.get.return_value = {"query": {"users": []}}

        users = [f"U{i}" for i in range(120)]
        loader.get_editcounts(users)

        # batch_size = 50 → 3 batches
        assert site.get.call_count == 3


class TestGetGlobalEditcounts:
    def test_empty_users_returns_empty(self):
        loader, _ = _loader()
        assert loader.get_global_editcounts([]) == {}

    def test_parses_globalusers(self):
        loader, site = _loader()
        site.get.return_value = {
            "query": {
                "globalusers": [
                    {"name": "Alice", "editcount": 1000, "centralid": 1},
                    {"name": "Bob", "editcount": 2000, "centralid": 2},
                ]
            }
        }

        result = loader.get_global_editcounts(["Alice", "Bob"])
        assert result["Alice"] == 1000
        assert result["Bob"] == 2000

    def test_defaults_to_zero_for_missing(self):
        loader, site = _loader()
        site.get.return_value = {"query": {"globalusers": []}}

        result = loader.get_global_editcounts(["Ghost"])
        assert result == {"Ghost": 0}

    def test_api_error_keeps_zeros(self):
        loader, site = _loader()
        site.get.side_effect = RuntimeError("fail")

        result = loader.get_global_editcounts(["Alice"])
        assert result == {"Alice": 0}

    def test_uses_globalusers_list(self):
        loader, site = _loader()
        site.get.return_value = {"query": {"globalusers": []}}

        loader.get_global_editcounts(["Alice"])

        params = site.get.call_args[1]
        assert params["list"] == "globalusers"
        assert "editcount" in params["gusprop"]


class TestGetGlobalUserinfo:
    def test_returns_globaluserinfo_dict(self):
        loader, site = _loader()
        site.get.return_value = {
            "query": {
                "globaluserinfo": {
                    "home": "enwiki",
                    "id": 42,
                    "registration": "2020-01-01T00:00:00Z",
                    "name": "Alice",
                    "editcount": 999,
                }
            }
        }

        info = loader.get_global_userinfo("Alice")
        assert info["home"] == "enwiki"
        assert info["registration"] == "2020-01-01T00:00:00Z"
        assert info["editcount"] == 999

    def test_returns_empty_dict_on_error(self):
        loader, site = _loader()
        site.get.side_effect = RuntimeError("fail")

        assert loader.get_global_userinfo("Alice") == {}

    def test_returns_empty_dict_when_missing_key(self):
        loader, site = _loader()
        site.get.return_value = {"query": {}}

        assert loader.get_global_userinfo("Alice") == {}

    def test_query_params(self):
        loader, site = _loader()
        site.get.return_value = {"query": {"globaluserinfo": {}}}

        loader.get_global_userinfo("Bob")

        params = site.get.call_args[1]
        assert params["meta"] == "globaluserinfo"
        assert params["guiuser"] == "Bob"


class TestGetHomeWikisAndRegistration:
    def test_builds_home_and_registration_map(self):
        loader, site = _loader()

        def side_effect(*args, **kwargs):
            user = kwargs.get("guiuser") or ""
            return {
                "query": {
                    "globaluserinfo": {
                        "home": f"{user.lower()}wiki",
                        "registration": "2020-06-01T00:00:00Z",
                    }
                }
            }

        site.get.side_effect = side_effect

        with patch("src.wiki.client.time.sleep"):  # avoid real sleep
            result = loader.get_home_wikis_and_registration(["Alice", "Bob"])

        assert result["Alice"]["home"] == "alicewiki"
        assert result["Bob"]["registration"] == "2020-06-01T00:00:00Z"

    def test_empty_users(self):
        loader, _ = _loader()
        assert loader.get_home_wikis_and_registration([]) == {}


class TestSolvePagesRedirects:
    def test_empty_pages(self):
        loader, _ = _loader()
        assert loader.solve_pages_redirects([]) == {}

    def test_maps_redirect_to_target(self):
        loader, site = _loader()
        site.get.return_value = {
            "query": {
                "pages": [
                    {
                        "title": "User:NewName",
                        "redirects": [
                            {"title": "User:OldName"},
                        ],
                    }
                ]
            }
        }

        result = loader.solve_pages_redirects(["User:OldName"])
        assert result == {"User:OldName": "User:NewName"}

    def test_pages_without_redirects_omitted(self):
        loader, site = _loader()
        site.get.return_value = {
            "query": {
                "pages": [
                    {"title": "User:Stable", "redirects": []},
                ]
            }
        }

        assert loader.solve_pages_redirects(["User:Stable"]) == {}

    def test_api_error_skips_batch(self):
        loader, site = _loader()
        site.get.side_effect = RuntimeError("fail")

        assert loader.solve_pages_redirects(["User:A"]) == {}

    def test_batches(self):
        loader, site = _loader()
        site.get.return_value = {"query": {"pages": []}}

        pages = [f"User:U{i}" for i in range(120)]
        loader.solve_pages_redirects(pages, batch_size=50)

        assert site.get.call_count == 3


# ===========================================================================
# WikiClient — construction & factories
# ===========================================================================


class TestWikiClientInit:
    def test_site_property(self):
        client, site = _client()
        assert client.site is site

    def test_inherits_loader_methods(self):
        client, site = _client()
        page = MagicMock()
        page.text.return_value = "hi"
        site.pages.__getitem__.return_value = page

        assert client.get_page_wikitext("X") == "hi"


class TestConnect:
    def test_connect_success_with_login(self, mock_site_cls):
        mock_site = mock_site_cls.return_value
        creds = Credentials(username="bot", password="secret")

        client = WikiClient.connect(creds, host="meta.wikimedia.org", login=True)

        assert isinstance(client, WikiClient)
        mock_site_cls.assert_called_once()
        mock_site.login.assert_called_once_with("bot", "secret")

    def test_connect_without_login_sets_credentials(self, mock_site_cls):
        mock_site = mock_site_cls.return_value
        creds = Credentials(username="bot", password="secret")

        client = WikiClient.connect(creds, login=False)

        assert client is not None
        mock_site.login.assert_not_called()
        assert mock_site.credentials == ("bot", "secret", None)

    def test_connect_login_error_returns_none(self, mock_site_cls):
        mock_site_cls.return_value.login.side_effect = mwclient.errors.LoginError("", "", "Failed")
        creds = Credentials(username="bot", password="bad")

        assert WikiClient.connect(creds) is None

    def test_connect_generic_exception_returns_none(self, mock_site_cls):
        mock_site_cls.side_effect = OSError("dns fail")
        creds = Credentials(username="bot", password="secret")

        assert WikiClient.connect(creds) is None

    def test_connect_passes_user_agent_and_host(self, mock_site_cls):
        creds = Credentials(username="bot", password="secret")

        WikiClient.connect(
            creds,
            user_agent="MyBot/1.0",
            host="www.wikidata.org",
            do_init=False,
        )

        mock_site_cls.assert_called_once_with(
            "www.wikidata.org",
            clients_useragent="MyBot/1.0",
            do_init=False,
        )


class TestLoad:
    @patch.object(WikiClient, "connect")
    @patch.object(Credentials, "from_env")
    def test_load_returns_none_when_no_credentials_and_login_required(self, mock_creds, mock_connect):
        mock_creds.return_value = None

        result = WikiClient.load(login=True)

        assert result is None
        mock_connect.assert_not_called()

    @patch.object(WikiClient, "connect")
    @patch.object(Credentials, "from_env")
    @patch.object(Settings, "from_env")
    def test_load_calls_connect_with_credentials(self, mock_settings_env, mock_creds, mock_connect):
        creds = Credentials(username="bot", password="secret")
        mock_creds.return_value = creds
        settings = MagicMock()
        settings.user_agent = "UA"
        mock_settings_env.return_value = settings
        mock_connect.return_value = MagicMock(spec=WikiClient)

        result = WikiClient.load(host="www.wikidata.org", login=True)

        mock_connect.assert_called_once()
        kwargs = mock_connect.call_args[1]
        assert kwargs["credentials"] == creds
        assert kwargs["host"] == "www.wikidata.org"
        assert kwargs["user_agent"] == "UA"
        assert result is mock_connect.return_value

    @patch.object(WikiClient, "connect")
    @patch.object(Credentials, "from_env")
    def test_load_without_login_allows_missing_credentials(self, mock_creds, mock_connect):
        mock_creds.return_value = None
        settings = MagicMock()
        settings.user_agent = "UA"
        mock_connect.return_value = MagicMock(spec=WikiClient)

        # login=False should not bail on missing credentials
        result = WikiClient.load(settings=settings, login=False)

        mock_connect.assert_called_once()
        assert result is mock_connect.return_value


class TestFromSettings:
    @patch.object(WikiClient, "load")
    def test_from_settings_delegates_to_load(self, mock_load):
        settings = MagicMock()
        mock_load.return_value = MagicMock(spec=WikiClient)

        result = WikiClient.from_settings(
            settings,
            host="www.wikidata.org",
            login=False,
            do_init=False,
        )

        mock_load.assert_called_once_with(
            settings=settings,
            host="www.wikidata.org",
            login=False,
            do_init=False,
        )
        assert result is mock_load.return_value
