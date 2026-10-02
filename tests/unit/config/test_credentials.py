"""
Unit tests for src/config/credentials.py module.

Classes to test: Credentials
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.config.credentials import Credentials

# ---------------------------------------------------------------------------
# Fixtures (Applying patch-to-fixture pattern)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_load_dotenv(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """
    Mock dotenv.load_dotenv to prevent reading actual .env files during tests.
    Replaces @patch("src.config.credentials.load_dotenv").
    """
    _mock = MagicMock()
    monkeypatch.setattr("src.config.credentials.load_dotenv", _mock)
    return _mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCredentialsBool:
    def test_bool_true_when_both_present(self) -> None:
        """Test that Credentials evaluates to True when both fields are populated."""
        creds = Credentials(username="bot_user", password="secret_password")
        assert bool(creds) is True

    def test_bool_false_when_username_empty(self) -> None:
        """Test that Credentials evaluates to False when username is empty."""
        creds = Credentials(username="", password="secret_password")
        assert bool(creds) is False

    def test_bool_false_when_password_empty(self) -> None:
        """Test that Credentials evaluates to False when password is empty."""
        creds = Credentials(username="bot_user", password="")
        assert bool(creds) is False

    def test_bool_false_when_both_empty(self) -> None:
        """Test that Credentials evaluates to False when both fields are empty."""
        creds = Credentials(username="", password="")
        assert bool(creds) is False


class TestCredentialsFromEnv:
    def test_from_env_success_without_file(
        self, mock_load_dotenv: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test successful credential loading when environment variables are set."""
        monkeypatch.setenv("WIKIPEDIA_BOT_USERNAME", "test_user")
        monkeypatch.setenv("WIKIPEDIA_BOT_PASSWORD", "test_pass")

        creds = Credentials.from_env()

        assert creds is not None
        assert creds.username == "test_user"
        assert creds.password == "test_pass"
        # Ensure load_dotenv was called without arguments
        mock_load_dotenv.assert_called_once_with()

    def test_from_env_with_custom_env_file(
        self, mock_load_dotenv: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a custom env_file path is correctly passed to load_dotenv."""
        monkeypatch.setenv("WIKIPEDIA_BOT_USERNAME", "test_user")
        monkeypatch.setenv("WIKIPEDIA_BOT_PASSWORD", "test_pass")

        custom_path = Path("/mock/path/to/.env")
        Credentials.from_env(env_file=custom_path)

        # Ensure load_dotenv was called with the custom path
        mock_load_dotenv.assert_called_once_with(custom_path)

    def test_from_env_missing_username_returns_none(
        self, mock_load_dotenv: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that from_env returns None if the username variable is missing."""
        monkeypatch.delenv("WIKIPEDIA_BOT_USERNAME", raising=False)
        monkeypatch.setenv("WIKIPEDIA_BOT_PASSWORD", "test_pass")

        assert Credentials.from_env() is None

    def test_from_env_missing_password_returns_none(
        self, mock_load_dotenv: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that from_env returns None if the password variable is missing."""
        monkeypatch.setenv("WIKIPEDIA_BOT_USERNAME", "test_user")
        monkeypatch.delenv("WIKIPEDIA_BOT_PASSWORD", raising=False)

        assert Credentials.from_env() is None

    def test_from_env_strips_whitespace(
        self, mock_load_dotenv: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that whitespace is correctly stripped from the environment variables."""
        monkeypatch.setenv("WIKIPEDIA_BOT_USERNAME", "  test_user  ")
        monkeypatch.setenv("WIKIPEDIA_BOT_PASSWORD", " test_pass\n ")

        creds = Credentials.from_env()

        assert creds is not None
        assert creds.username == "test_user"
        assert creds.password == "test_pass"
