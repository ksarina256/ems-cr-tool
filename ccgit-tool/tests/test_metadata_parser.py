"""
Tests for MetadataParser
"""

import pytest
from migration.metadata_parser import MetadataParser


MOCK_CONFIG = {
    "author_map": {
        "jsmith": {"name": "John Smith", "email": "john.smith@sce.com"},
    }
}


@pytest.fixture
def parser():
    return MetadataParser(MOCK_CONFIG)


def test_parse_author_known_user(parser):
    name, email = parser.parse_author("jsmith")
    assert name == "John Smith"
    assert email == "john.smith@sce.com"


def test_parse_author_unknown_user_falls_back(parser):
    name, email = parser.parse_author("bdavis")
    assert name == "bdavis"
    assert "sce.com" in email


def test_parse_author_empty_string(parser):
    name, email = parser.parse_author("")
    assert name == "CCGit Migration"
    assert email == "ccgit@sce.com"


def test_parse_timestamp_compact_format(parser):
    result = parser.parse_timestamp("20240315.143022")
    assert result == "2024-03-15T14:30:22"


def test_parse_timestamp_iso_passthrough(parser):
    result = parser.parse_timestamp("2024-03-15T14:30:22")
    assert result == "2024-03-15T14:30:22"


def test_parse_timestamp_invalid_returns_none(parser):
    result = parser.parse_timestamp("not-a-date")
    assert result is None


def test_parse_timestamp_empty_returns_none(parser):
    result = parser.parse_timestamp("")
    assert result is None


def test_build_commit_message_includes_fields(parser):
    msg = parser.build_commit_message(
        file_path="src/main.py",
        version="/main/3",
        author="jsmith",
        timestamp="2024-03-15T14:30:22",
        label="REL_1",
    )
    assert "src/main.py" in msg
    assert "REL_1" in msg
    assert "jsmith" in msg
