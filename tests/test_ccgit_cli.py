import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ccgit.cli import main


class CliTest(unittest.TestCase):
    def test_validate_outputs_resolved_config_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "source"
            source.mkdir()
            config = self.write_config(root, source)

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["--config", str(config), "validate"])

            data = json.loads(out.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(data["branches"]["master"]["source_exists"])

    def test_snapshot_and_compare_commands_work_without_clearcase_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            master = root / "master"
            dev = root / "dev"
            master.mkdir()
            dev.mkdir()
            (master / "file.txt").write_text("master\n", encoding="utf-8")
            (dev / "file.txt").write_text("dev\n", encoding="utf-8")
            config = self.write_config(root, master, dev)

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--config", str(config), "snapshot", "master"]), 0)
                self.assertEqual(main(["--config", str(config), "snapshot", "dev"]), 0)

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["--config", str(config), "compare", "--base", "master", "--target", "dev"])

            data = json.loads(out.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(data["counts"], {"modified": 1})

    def test_missing_config_returns_error_code(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main(["--config", "/definitely/missing/ccgit.json", "validate"])

        self.assertEqual(code, 2)
        self.assertIn("Config file not found", err.getvalue())

    @staticmethod
    def write_config(root: Path, master: Path, dev: Path = None) -> Path:
        dev = dev or master
        config = root / "ccgit.json"
        config.write_text(
            json.dumps(
                {
                    "project": "sce",
                    "local_repo": str(root / "mirror"),
                    "branches": {
                        "master": {"source_path": str(master), "git_branch": "cc-master"},
                        "dev": {"source_path": str(dev), "git_branch": "cc-dev"},
                    },
                }
            ),
            encoding="utf-8",
        )
        return config


if __name__ == "__main__":
    unittest.main()
