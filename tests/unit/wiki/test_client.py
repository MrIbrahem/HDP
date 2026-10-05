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
from src.wiki.client import WikiClient, WikiClientLoader


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    m = MagicMock()
    monkeypatch.setattr("src.wiki.client.time.sleep", m)
    return m


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
# WikiClientLoader — batch_size
# ===========================================================================


@pytest.fixture
def mock_site():
    """
    Create a mock Site object with default basic rights.
    """
    site = MagicMock()
    site.rights = ["read", "edit"]
    return site


class TestBatchSize:
    """Tests for WikiClientLoader _batch_size/batch_size/_detect_batch_size"""

    def test_explicit_batch_size(self, mock_site):
        """
        Test that an explicitly provided batch size overrides auto-detection.
        """
        loader = WikiClientLoader(mock_site, batch_size=42)

        # Should return the exact number passed during initialization
        assert loader.batch_size == 42

    def test_detect_batch_size_with_high_limits(self, mock_site):
        """
        Test auto-detection when the user has the 'apihighlimits' right.
        """
        # Inject the required right into the mock site
        mock_site.rights = ["apihighlimits", "read", "edit"]
        loader = WikiClientLoader(mock_site)

        # Should detect and use HIGH_LIMIT_BATCH_SIZE (100)
        assert loader.batch_size == WikiClientLoader.HIGH_LIMIT_BATCH_SIZE
        assert loader.batch_size == 100

    def test_detect_batch_size_without_high_limits(self, mock_site):
        """
        Test auto-detection when the user lacks the 'apihighlimits' right.
        """
        # Ensure the required right is missing
        mock_site.rights = ["read", "edit"]
        loader = WikiClientLoader(mock_site)

        # Should fallback to DEFAULT_BATCH_SIZE (50)
        assert loader.batch_size == WikiClientLoader.DEFAULT_BATCH_SIZE
        assert loader.batch_size == 50

    def test_batch_size_property_is_cached(self, mock_site):
        """
        Test that _detect_batch_size is only called once and the result is cached.
        """
        loader = WikiClientLoader(mock_site)

        # Patch the internal detection method to track its calls
        with patch.object(loader, "_detect_batch_size", return_value=99) as mock_detect:
            # First access should trigger the detection method
            first_call_result = loader.batch_size
            assert first_call_result == 99
            mock_detect.assert_called_once()

            # Second access should return the cached value directly
            second_call_result = loader.batch_size
            assert second_call_result == 99
            # The call count should remain 1, proving it was cached
            assert mock_detect.call_count == 1


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

        result = loader.get_pages_wikitext(["Page A", "Page B"])

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

        titles = [f"P{i}" for i in range(150)]
        loader.get_pages_wikitext(titles)

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
            result = loader.get_global_users_info(["Alice", "Bob"])

        assert result["Alice"]["home"] == "alicewiki"
        assert result["Bob"]["registration"] == "2020-06-01T00:00:00Z"

    def test_empty_users(self):
        loader, _ = _loader()
        assert loader.get_global_users_info([]) == {}


class TestSolvePagesRedirects:
    def test_empty_pages(self):
        loader, _ = _loader()
        assert loader.solve_pages_info([]) == ({}, set())

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

        result, _ = loader.solve_pages_info(["User:OldName"])
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

        assert loader.solve_pages_info(["User:Stable"]) == ({}, set())

    def test_api_error_skips_batch(self):
        loader, site = _loader()
        site.get.side_effect = RuntimeError("fail")

        assert loader.solve_pages_info(["User:A"]) == ({}, set())

    def test_batches(self):
        loader, site = _loader()
        site.get.return_value = {"query": {"pages": []}}

        pages = [f"User:U{i}" for i in range(120)]
        loader.solve_pages_info(pages)

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


# ===========================================================================
# last_edit_timestamp
# ===========================================================================


class TestLastEditTimestamp:
    """Unit tests for WikiClientLoader.last_edit_timestamp."""

    @pytest.fixture
    def client_loader(self):
        """Fixture providing a WikiClientLoader instance with a mocked Site."""
        mock_site = MagicMock()
        return WikiClientLoader(site=mock_site, batch_size=50)

    def test_last_edit_timestamp_success(self, client_loader):
        """Test fetching the last edit timestamp successfully when entries exist."""
        mock_api_response = {
            "query": {
                "globalcontributions": {
                    "entries": [
                        {"wikiid": "arwiki", "revid": "76823306", "timestamp": "20261001061625"},
                        {"wikiid": "metawiki", "revid": "31116293", "timestamp": "20261002001304"},
                    ]
                }
            }
        }
        client_loader._site.get.return_value = mock_api_response

        result = client_loader.last_edit_timestamp("TestUser")

        # Verify correct API parameters were passed
        client_loader._site.get.assert_called_once_with(
            "query",
            format="json",
            list="globalcontributions",
            utf8=1,
            formatversion=2,
            guctarget="TestUser",
            guclimit="1",
        )
        # Should pick the latest timestamp (20261002 -> 2026-10-02) regardless of response order
        assert result == "2026-10-02"

    def test_last_edit_timestamp_empty_entries(self, client_loader):
        """Test returning None when the user has no global contributions."""
        mock_api_response = {"query": {"globalcontributions": {"entries": []}}}
        client_loader._site.get.return_value = mock_api_response

        result = client_loader.last_edit_timestamp("InactiveUser")

        assert result is None

    def test_last_edit_timestamp_missing_query_key(self, client_loader):
        """Test returning None when the API response structure is missing expected keys."""
        client_loader._site.get.return_value = {}

        result = client_loader.last_edit_timestamp("UnknownUser")

        assert result is None

    def test_last_edit_timestamp_api_exception(self, client_loader):
        """Test returning None and catching exception when the API call fails."""
        client_loader._site.get.side_effect = Exception("Network Connection Error")

        result = client_loader.last_edit_timestamp("UserWithError")

        assert result is None


# ===========================================================================
# get_last_edit_timestamps (batch)
# ===========================================================================


class TestLastEditTimestamps:
    """Unit tests for WikiClientLoader.get_last_edit_timestamps."""

    @pytest.fixture
    def client_loader(self):
        """Fixture providing a WikiClientLoader instance with a mocked Site."""
        mock_site = MagicMock()
        return WikiClientLoader(site=mock_site, batch_size=50)

    def test_get_last_edit_timestamps_success(self, client_loader):
        """Test fetching last edit timestamps for multiple users."""
        users = ["User1", "User2", "User3"]
        timestamps = {
            "User1": "2026-10-01",
            "User2": "2026-09-15",
            "User3": None,  # User3 has no edits
        }

        with patch.object(
            client_loader, "last_edit_timestamp", side_effect=lambda u: timestamps.get(u)
        ) as mock_single_fetch:
            results = client_loader.get_last_edit_timestamps(users)

            # Check that last_edit_timestamp was called for each user
            assert mock_single_fetch.call_count == 3
            # Users with None values should be omitted from the result dict
            assert results == {
                "User1": "2026-10-01",
                "User2": "2026-09-15",
            }

    def test_get_last_edit_timestamps_empty_user_list(self, client_loader):
        """Test passing an empty user list returns an empty dictionary."""
        with patch.object(client_loader, "last_edit_timestamp") as mock_single_fetch:
            results = client_loader.get_last_edit_timestamps([])

            mock_single_fetch.assert_not_called()
            assert results == {}

    def test_get_last_edit_timestamps_all_users_none(self, client_loader):
        """Test when none of the users have edit timestamps."""
        users = ["UserA", "UserB"]

        with patch.object(client_loader, "last_edit_timestamp", return_value=None):
            results = client_loader.get_last_edit_timestamps(users)

            assert results == {}
