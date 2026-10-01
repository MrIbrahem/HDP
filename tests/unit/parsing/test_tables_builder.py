"""
Unit tests for src/parsing/tables_builder.py module.

Classes to test: TableRow, TableObject
"""

import wikitextparser as wtp

from src.parsing.tables_builder import TableRow, TableObject

class TestCreateTable:
    def test_create(self):
        table = wtp.Table("")
        result = table.string

        assert result == ""

class TestTableRow:
    """Tests for TableRow class methods."""
    def test_build(self):
        """Test build method."""
        row = TableRow([])
        result = row.build()

        assert result == ""

class TestTableObject:
    """Tests for TableObject class methods."""
    def test_create(self):
        """Test create method."""
        table = TableObject.load()
        result = table.build()

        assert result == ""
