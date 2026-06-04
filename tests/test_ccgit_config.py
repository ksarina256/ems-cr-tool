import json
import tempfile
import unittest
from pathlib import Path

from ccgit.config import ConfigError, ProjectConfig


class ConfigTest(unittest.TestCase):
    def test_loads_project_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            config_path = root / "ccgit.json"
            config_path.write_text(
                json.dumps(
                    {
                        "project": "sce",
                        "local_repo": "work/mirror",
                        "gitea_repo": "git@gitea:team/sce.git",
                        "gitea_web_url": "https://gitea/team/sce",
                        "branches": {
                            "master": {
                                "source_path": "master-src",
                                "git_branch": "cc-master",
                            },
                            "dev": {
                                "source_path": "dev-src",
                                "view": "sce_dts",
                                "git_branch": "cc-dev",
                            },
                        },
                        "exclude": ["bin/"],
                    }
                ),
                encoding="utf-8",
            )

            config = ProjectConfig.load(str(config_path))

            self.assertEqual(config.project, "sce")
            self.assertEqual(config.local_repo, root / "work" / "mirror")
            self.assertEqual(config.branch("master").copy_mode, "direct")
            self.assertEqual(config.branch("dev").copy_mode, "setview")
            self.assertEqual(config.compare_url("master", "dev"), "https://gitea/team/sce/compare/cc-master...cc-dev")

    def test_rejects_missing_project_and_bad_metadata_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            missing_project = root / "missing-project.json"
            missing_project.write_text(json.dumps({"branches": {}}), encoding="utf-8")
            bad_metadata = root / "bad-metadata.json"
            bad_metadata.write_text(
                json.dumps(
                    {
                        "project": "sce",
                        "metadata_dir": "../bad",
                        "branches": {"master": {"source_path": "src"}},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "project"):
                ProjectConfig.load(str(missing_project))
            with self.assertRaisesRegex(ConfigError, "metadata_dir"):
                ProjectConfig.load(str(bad_metadata))

    def test_unknown_branch_error_lists_available_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            config_path = root / "ccgit.json"
            config_path.write_text(
                json.dumps({"project": "sce", "branches": {"master": {"source_path": "src"}}}),
                encoding="utf-8",
            )
            config = ProjectConfig.load(str(config_path))

            with self.assertRaisesRegex(ConfigError, "Available: master"):
                config.branch("dev")


if __name__ == "__main__":
    unittest.main()
