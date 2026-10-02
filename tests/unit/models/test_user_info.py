"""
Unit tests for src/models/user_info.py module.

Classes to test: UserInfo
Functions to test: calculate_age
"""

from unittest.mock import MagicMock

import pytest

# Adjust this import based on your actual file name
from src.models.user_info import (
    UserInfo,
    _as_optional_int,
    calculate_age,
)

# ---------------------------------------------------------------------------
# Fixtures (Applying patch-to-fixture pattern)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_logger(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """
    Mock the module logger to verify error logging without printing to stdout.
    Replaces @patch("src.models.user_info.logger").
    """
    _mock = MagicMock()
    monkeypatch.setattr("src.models.user_info.logger", _mock)
    return _mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCalculateAge:
    def test_empty_registration_returns_empty_string(self) -> None:
        """Test that an empty string returns an empty result."""
        assert calculate_age("") == ""

    def test_valid_registration_returns_template(self) -> None:
        """Test that a valid ISO string returns the correct wiki template format."""
        result = calculate_age("2008-07-24T01:18:05Z")
        assert result == "{{age in years and months|2008|07|24}}"

    def test_invalid_registration_logs_error_and_returns_fallback(self, mock_logger: MagicMock) -> None:
        """Test that invalid date strings log an error and return the original raw string."""
        invalid_date = "invalid-date-format"
        result = calculate_age(invalid_date)

        # Verify fallback behavior
        assert result == invalid_date
        # Verify logger was called once
        mock_logger.error.assert_called_once()


class TestAsOptionalInt:
    def test_none_returns_none(self) -> None:
        """Test that passing None explicitly returns None."""
        assert _as_optional_int(None) is None

    def test_valid_int_returns_int(self) -> None:
        """Test that valid integers and integer-strings parse correctly."""
        assert _as_optional_int("123") == 123
        assert _as_optional_int(456) == 456

    def test_invalid_string_returns_none(self) -> None:
        """Test that non-numeric strings safely return None."""
        assert _as_optional_int("abc") is None

    def test_float_truncates_to_int(self) -> None:
        """Test that float inputs are truncated and returned as integers."""
        assert _as_optional_int(1.9) == 1


class TestUserInfo:
    def test_update_username(self) -> None:
        """Test that updating the username preserves the old one as a redirect."""
        user = UserInfo(username="OldName")
        user.update_username("NewName")

        assert user.username == "NewName"
        assert user.refirect_username == "OldName"

    def test_user_link(self) -> None:
        """Test that user_link dynamically formats as a wiki link."""
        user = UserInfo(username="TestUser")
        assert user.user_link == "[[User:TestUser]]"

        empty_user = UserInfo(username="")
        assert empty_user.user_link is None

    def test_global_without_wikidata_str(self) -> None:
        """Test the calculation of global edits excluding wikidata."""
        user = UserInfo(username="Test", global_editcount=1500, wikidata_count=500)
        assert user.global_without_wikidata_str == "1,000"

        # Ensure negative values (if wikidata > global) are floored to 0
        user.global_editcount = 100
        user.wikidata_count = 500
        assert user.global_without_wikidata_str == "0"

        # Missing values return empty string
        user.global_editcount = None
        assert user.global_without_wikidata_str == ""

    def test_editcount_strs_formatting(self) -> None:
        """Test that edit counts are properly formatted with thousand separators."""
        user = UserInfo(username="Test", global_editcount=1000000, recent_editcount=5000, wikidata_count=1234)
        assert user.global_editcount_str == "1,000,000"
        assert user.recent_editcount_str == "5,000"
        assert user.wikidata_editcount_str == "1,234"

    def test_update_factory(self) -> None:
        """Test updating a UserInfo instance with a dictionary of new metrics."""
        user = UserInfo(username="TestUser")

        globaluser_data = {"home": "frwiki", "registration": "2020-01-01T00:00:00Z", "editcount": "500"}

        user.update(globaluser_data=globaluser_data, recent_editcount=50, wikidata_count=10, last_edit="2023-10-01")

        assert user.home_wiki == "frwiki"
        assert user.registration == "2020-01-01T00:00:00Z"
        assert user.global_editcount == 500
        assert user.recent_editcount == 50
        assert user.wikidata_count == 10
        assert user.last_edit == "2023-10-01"

    def test_to_table_dict(self) -> None:
        """Test exporting user data to a dictionary mapped for wiki tables."""
        user = UserInfo(
            username="Alice",
            home_wiki="enwiki",
            registration="2008-07-24T01:18:05Z",
            global_editcount=2500,
            recent_editcount=10,
            wikidata_count=0,
            last_edit="2023-01-01",
        )

        table_dict = user.to_table_dict(unknown="N/A")

        assert table_dict["global_editcount_str"] == "2,500"
        assert table_dict["recent_editcount_str"] == "10"
        assert table_dict["wikidata_editcount_str"] == "0"
        assert table_dict["global_without_wikidata_str"] == "2,500"
        assert table_dict["user_link"] == "[[User:Alice]]"
        assert table_dict["age"] == "{{age in years and months|2008|07|24}}"
        assert table_dict["home_wiki"] == "enwiki"
        assert table_dict["last_edit"] == "2023-01-01"

    def test_to_table_dict_with_missing_values(self) -> None:
        """Test exporting falls back to the specified 'unknown' placeholder."""
        user = UserInfo(username="Bob")
        table_dict = user.to_table_dict(unknown="unknown_value")

        assert table_dict["global_editcount_str"] == "unknown_value"
        assert table_dict["recent_editcount_str"] == "unknown_value"
        assert table_dict["wikidata_editcount_str"] == "unknown_value"
        assert table_dict["home_wiki"] == "unknown_value"
        assert table_dict["last_edit"] == "unknown_value"

    def test_to_json(self) -> None:
        """Test exporting falls back to the specified 'unknown' placeholder."""
        user = UserInfo(username="Bob")
        table_dict = user.to_json()

        assert table_dict["global_editcount_str"] == ""
        assert table_dict["recent_editcount_str"] == ""
        assert table_dict["wikidata_editcount_str"] == ""
        assert table_dict["home_wiki"] == ""
        assert table_dict["last_edit"] is None
