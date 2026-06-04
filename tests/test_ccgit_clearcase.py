import unittest
from pathlib import Path

from ccgit.clearcase import ClearCaseClient
from ccgit.config import BranchConfig, ProjectConfig
from ccgit.runner import CommandResult


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def run(self, args, *, cwd=None, env=None, check=True):
        self.calls.append([str(arg) for arg in args])
        return CommandResult(args=args, returncode=0, stdout="ok\n", stderr="")


class ClearCaseClientTest(unittest.TestCase):
    def test_setview_copy_uses_configured_view_and_rsync_excludes(self):
        runner = RecordingRunner()
        client = ClearCaseClient(runner)
        config = ProjectConfig(
            project="sce",
            local_repo=Path("/tmp/mirror"),
            branches={
                "dev": BranchConfig(
                    name="dev",
                    git_branch="cc-dev",
                    source_path=Path("/vobs/PROJ"),
                    view="sce_dts",
                    copy_mode="setview",
                )
            },
            exclude=["bin/", "*.o"],
        )

        client.copy_view_to_staging(config, config.branch("dev"), Path("/tmp/staging/dev"))

        self.assertEqual(runner.calls[0][0:3], ["cleartool", "setview", "-exec"])
        self.assertTrue(runner.calls[0][3].startswith("rsync "))
        self.assertIn("sce_dts", runner.calls[0])
        self.assertIn("--exclude bin/", runner.calls[0][3])
        self.assertIn("--exclude '*.o'", runner.calls[0][3])
        self.assertIn("/vobs/PROJ/", runner.calls[0][3])
        self.assertIn("/tmp/staging/dev/", runner.calls[0][3])


if __name__ == "__main__":
    unittest.main()
