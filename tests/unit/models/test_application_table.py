"""
Unit tests for src/models/application_table.py module.

Classes to test: ApplicationTable
"""

from unittest.mock import MagicMock

import pytest

# Adjust imports based on your actual module structure
from src.models.application_table import ApplicationTable

# ---------------------------------------------------------------------------
# Fixtures for mocked ApplicationRow objects
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_row_1() -> MagicMock:
    """Fixture providing a mocked ApplicationRow for Alice."""
    row = MagicMock()
    row.full_title = "User:Alice/Application"
    row.build_row.return_value = ["|-", "| [[User:Alice/Application|Alice]]", "| 2026-05-30"]
    row.to_table_dict.return_value = {"Page": "User:Alice/Application", "User": "Alice", "Country": "Wonderland"}
    return row


@pytest.fixture
def mock_row_2() -> MagicMock:
    """Fixture providing a mocked ApplicationRow for Bob."""
    row = MagicMock()
    row.full_title = "User:Bob/Application"
    row.build_row.return_value = ["|-", "| [[User:Bob/Application|Bob]]", "| 2026-06-01"]
    row.to_table_dict.return_value = {"Page": "User:Bob/Application", "User": "Bob", "Country": "Builderland"}
    return row


# ---------------------------------------------------------------------------
# Tests for ApplicationTable
# ---------------------------------------------------------------------------


class TestApplicationTableLoad:
    def test_load_defaults(self) -> None:
        """Test the load classmethod initializes properly with no arguments."""
        table = ApplicationTable.load()

        assert table.rows == []
        assert table.unknown == ""

    def test_load_with_arguments(self, mock_row_1: MagicMock, mock_row_2: MagicMock) -> None:
        """Test the load classmethod correctly stores passed arguments."""
        rows = [mock_row_1, mock_row_2]
        table = ApplicationTable.load(rows=rows, unknown="N/A")

        assert table.rows == rows
        assert table.unknown == "N/A"


class TestApplicationTableBuildWikitable:
    def test_build_wikitable_without_last_edit(self, mock_row_1: MagicMock, mock_row_2: MagicMock) -> None:
        """Test rendering the MediaWiki table without the 'Last edit' column."""
        table = ApplicationTable(rows=[mock_row_1, mock_row_2])

        result = table.build_wikitable(add_last_edit=False)

        # Verify the structure of the rendered table
        assert result.startswith('{| class="wikitable sortable"')
        assert result.endswith("|}")

        # Verify default headers are present
        assert "! Application" in result
        assert "! Country" in result
        assert "! Approved" in result

        # Verify 'Last edit' column is omitted
        assert "! Last edit\n" not in result

        # Verify row content is appended
        assert "| [[User:Alice/Application|Alice]]" in result
        assert "| [[User:Bob/Application|Bob]]" in result

        # Verify row generation was called with the correct flag
        mock_row_1.build_row.assert_called_once_with(False)
        mock_row_2.build_row.assert_called_once_with(False)

    def test_build_wikitable_with_last_edit(self, mock_row_1: MagicMock) -> None:
        """Test rendering the MediaWiki table including the 'Last edit' column."""
        table = ApplicationTable(rows=[mock_row_1])

        result = table.build_wikitable(add_last_edit=True)

        # Verify 'Last edit' column is explicitly included
        assert "! Last edit\n" in result

        # Verify row generation was called with the correct flag
        mock_row_1.build_row.assert_called_once_with(True)


class TestApplicationTableAsRowDicts:
    def test_as_row_dicts(self, mock_row_1: MagicMock, mock_row_2: MagicMock) -> None:
        """Test that rows are converted to a mapping of full_title -> table_dict."""
        table = ApplicationTable(rows=[mock_row_1, mock_row_2], unknown="UnknownData")

        result = table.as_row_dicts()

        # Verify the resulting dictionary structure
        expected_result = {
            "User:Alice/Application": {"Page": "User:Alice/Application", "User": "Alice", "Country": "Wonderland"},
            "User:Bob/Application": {"Page": "User:Bob/Application", "User": "Bob", "Country": "Builderland"},
        }
        assert result == expected_result

        # Verify to_table_dict was called with the table's 'unknown' fallback string
        mock_row_1.to_table_dict.assert_called_once_with("UnknownData")
        mock_row_2.to_table_dict.assert_called_once_with("UnknownData")
