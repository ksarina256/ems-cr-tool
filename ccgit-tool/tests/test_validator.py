"""
Tests for Validator
"""

import os
import pytest
import tempfile
from migration.validator import Validator


MOCK_CONFIG = {
    "clearcase": {"vob_path": "/vobs/test_vob"},
    "migration": {"checksums": False},
}


@pytest.fixture
def validator():
    return Validator(MOCK_CONFIG)


def test_validate_all_files_present(validator):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the expected files in the temp git repo
        os.makedirs(os.path.join(tmpdir, "src"))
        open(os.path.join(tmpdir, "src", "main.py"), "w").close()
        open(os.path.join(tmpdir, "src", "utils.py"), "w").close()

        cc_files = [
            "/vobs/test_vob/src/main.py@@/main/1",
            "/vobs/test_vob/src/utils.py@@/main/2",
        ]

        result = validator.validate(
            cc_files=cc_files,
            git_repo_path=tmpdir,
            git_file_count=2,
        )

    assert result["passed"] is True
    assert result["missing"] == 0
    assert result["cc_count"] == 2


def test_validate_detects_missing_file(validator):
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "src"))
        # Only create one of the two expected files
        open(os.path.join(tmpdir, "src", "main.py"), "w").close()

        cc_files = [
            "/vobs/test_vob/src/main.py@@/main/1",
            "/vobs/test_vob/src/utils.py@@/main/2",
        ]

        result = validator.validate(
            cc_files=cc_files,
            git_repo_path=tmpdir,
            git_file_count=1,
        )

    assert result["passed"] is False
    assert result["missing"] == 1
    assert "src/utils.py" in result["missing_files"]


def test_validate_empty_file_list(validator):
    with tempfile.TemporaryDirectory() as tmpdir:
        result = validator.validate(
            cc_files=[],
            git_repo_path=tmpdir,
            git_file_count=0,
        )
    assert result["passed"] is True
    assert result["missing"] == 0
