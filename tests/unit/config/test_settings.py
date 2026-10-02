"""
Unit tests for src/config/settings.py module.

Classes to test: Settings
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Adjust imports based on your actual module structure
from src.config.settings import Settings, _load_users_redirects

# ---------------------------------------------------------------------------
# Fixtures (Applying patch-to-fixture pattern)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_load_dotenv(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """
    Mock dotenv.load_dotenv to prevent reading actual .env files during tests.
    Replaces @patch("src.config.settings.load_dotenv").
    """
    _mock = MagicMock()
    monkeypatch.setattr("src.config.settings.load_dotenv", _mock)
    return _mock


@pytest.fixture
def mock_logger(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """
    Mock the module logger to verify warnings and infos without cluttering stdout.
    Replaces @patch("src.config.settings.logger").
    """
    _mock = MagicMock()
    monkeypatch.setattr("src.config.settings.logger", _mock)
    return _mock


# ---------------------------------------------------------------------------
# Tests for Helper Functions
# ---------------------------------------------------------------------------


class TestLoadUsersRedirects:
    def test_loads_valid_json_and_lowercases_keys(self, tmp_path: Path) -> None:
        """Test that a valid JSON dictionary is loaded and keys are lowercased."""
        json_file = tmp_path / "redirects.json"
        json_file.write_text('{"UserA": "UserB", "USER_C": "UserD"}', encoding="utf-8")

        result = _load_users_redirects(json_file)

        assert result == {"usera": "UserB", "user_c": "UserD"}

    def test_invalid_json_returns_empty_dict_and_logs(self, tmp_path: Path, mock_logger: MagicMock) -> None:
        """Test that malformed JSON is caught, logged, and returns an empty dict."""
        json_file = tmp_path / "redirects.json"
        json_file.write_text("invalid,json: format", encoding="utf-8")

        result = _load_users_redirects(json_file)

        assert result == {}
        mock_logger.warning.assert_called_once()

    def test_non_dict_json_returns_empty_dict_and_logs(self, tmp_path: Path, mock_logger: MagicMock) -> None:
        """Test that valid JSON containing a list instead of a dict returns empty dict."""
        json_file = tmp_path / "redirects.json"
        json_file.write_text('["just", "a", "list"]', encoding="utf-8")

        result = _load_users_redirects(json_file)

        assert result == {}
        mock_logger.warning.assert_called_once()

    def test_missing_file_returns_empty_dict_and_logs(self, tmp_path: Path, mock_logger: MagicMock) -> None:
        """Test that a non-existent file path gracefully returns an empty dict."""
        json_file = tmp_path / "missing_file.json"

        result = _load_users_redirects(json_file)

        assert result == {}
        mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for Settings Class
# ---------------------------------------------------------------------------


class TestSettingsProperties:
    def test_cache_paths_are_correctly_derived(self, tmp_path: Path) -> None:
        """Test that dynamic path properties build correctly on top of cache_dir."""
        settings = Settings.load(cache_dir=tmp_path)

        assert settings.home_wiki_cache_path == tmp_path / "home_wiki_cache.json"
        assert settings.edit_counts_cache_path == tmp_path / "edit_counts_cache.json"
        assert settings.users_redirects_path == tmp_path / "users_redirects.json"


class TestSettingsWriteToCacheDir:
    def test_creates_directories_and_writes_text(self, tmp_path: Path, mock_logger: MagicMock) -> None:
        """Test that writing to cache safely creates parent dirs and saves utf-8 text."""
        settings = Settings.load(cache_dir=tmp_path)
        relative_path = "subfolder/deep/test_file.txt"
        content = "Hello, Wiki!"

        settings.write_to_cache_dir(relative_path, content)

        output_file = tmp_path / relative_path
        assert output_file.exists()
        assert output_file.read_text(encoding="utf-8") == content
        mock_logger.info.assert_called_once()


class TestSettingsFromEnv:
    def test_from_env_uses_defaults_when_vars_missing(
        self, mock_load_dotenv: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that Settings initialize with defaults when env vars are unset."""
        # Ensure target env vars are completely stripped out
        monkeypatch.delenv("HDP_CACHE_DIR", raising=False)
        monkeypatch.delenv("HDP_RECENT_DAYS", raising=False)
        monkeypatch.delenv("HDP_USER_AGENT", raising=False)
        monkeypatch.delenv("HDP_BASE_PAGE", raising=False)

        settings = Settings.from_env()

        # Verify load_dotenv was called without args
        mock_load_dotenv.assert_called_once_with()
        # Fallback cache_dir is 'data' per DEFAULT_CACHE_DIR
        assert settings.cache_dir.name == "data"
        assert settings.recent_days > 0  # Reverts to RECENT_DAYS constant

    def test_from_env_loads_custom_env_vars(self, mock_load_dotenv: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that Settings dynamically picks up available environment variables."""
        monkeypatch.setenv("HDP_CACHE_DIR", "/custom/cache")
        monkeypatch.setenv("HDP_RECENT_DAYS", "15")
        monkeypatch.setenv("HDP_USER_AGENT", "TestBot/1.0")
        monkeypatch.setenv("HDP_BASE_PAGE", "Project:Hardware")

        settings = Settings.from_env()

        assert settings.cache_dir == Path("/custom/cache")
        assert settings.recent_days == 15
        assert settings.user_agent == "TestBot/1.0"
        assert settings.base_page == "Project:Hardware"

    def test_from_env_with_custom_env_file_path(self, mock_load_dotenv: MagicMock) -> None:
        """Test that providing an env_file forwards the path to load_dotenv."""
        custom_env_path = Path("/mock/dir/.env.test")
        Settings.from_env(env_file=custom_env_path)

        mock_load_dotenv.assert_called_once_with(custom_env_path)

    def test_from_env_merges_users_redirects_json_if_present(
        self, mock_load_dotenv: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that local users_redirects.json values merge into settings.users_redirects."""
        monkeypatch.setenv("HDP_CACHE_DIR", str(tmp_path))

        # Create a mock redirects file in the mocked cache directory
        redirects_file = tmp_path / "users_redirects.json"
        redirects_file.write_text('{"LegacyUser": "ModernUser"}', encoding="utf-8")

        settings = Settings.from_env()

        # The key should be lowercased automatically by _load_users_redirects
        assert "legacyuser" in settings.users_redirects
        assert settings.users_redirects["legacyuser"] == "ModernUser"
