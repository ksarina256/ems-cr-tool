"""
Tests for ClearCaseAdapter
Uses mocking to avoid requiring a live ClearCase environment.
"""

import pytest
from unittest.mock import patch, MagicMock
from migration.clearcase_adapter import ClearCaseAdapter, ClearCaseError


MOCK_CONFIG = {
    "clearcase": {
        "view_path": "/views/test_view",
        "vob_path": "/vobs/test_vob",
        "baseline": "",
    }
}


@pytest.fixture
def adapter():
    with patch("migration.clearcase_adapter.ClearCaseAdapter._verify_cleartool"):
        return ClearCaseAdapter(MOCK_CONFIG)


def test_init_reads_config(adapter):
    assert adapter.vob_path == "/vobs/test_vob"
    assert adapter.view_path == "/views/test_view"


def test_run_raises_on_nonzero_returncode(adapter):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "element not found"

    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(ClearCaseError, match="cleartool error"):
            adapter._run(["ls", "/vobs/test_vob"])


def test_list_files_filters_directories(adapter):
    fake_output = (
        "/vobs/test_vob/src/main.py@@/main/1\n"
        "/vobs/test_vob/src/utils.py@@/main/2\n"
        "\n"
    )
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = fake_output

    with patch("subprocess.run", return_value=mock_result):
        with patch("os.path.isfile", return_value=True):
            files = adapter.list_files()

    # Both valid file lines should be returned
    assert len(files) == 2


def test_get_file_metadata_returns_empty_on_error(adapter):
    with patch.object(adapter, "_run", side_effect=ClearCaseError("fail")):
        meta = adapter.get_file_metadata("/vobs/test_vob/file.py")
    assert meta == {}


def test_verify_cleartool_raises_if_not_found():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(ClearCaseError, match="cleartool not found"):
            ClearCaseAdapter(MOCK_CONFIG)
