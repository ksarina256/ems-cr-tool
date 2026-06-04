import tempfile
import unittest
from pathlib import Path
import subprocess

from ccgit.clearcase import ViewInfo
from ccgit.config import BranchConfig, ProjectConfig
from ccgit.snapshot import SnapshotService


class FakeClearCase:
    def view_info(self, branch):
        return ViewInfo(
            view=branch.view,
            pwv=f"Set view: {branch.view or 'NONE'}",
            config_spec=f"element * /main/{branch.name}/LATEST",
        )

    def copy_view_to_staging(self, config, branch, staging_dir):
        raise AssertionError("setview copy is not used by these tests")


class SnapshotTest(unittest.TestCase):
    def test_snapshots_two_branches_and_compares_source_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master = root / "master"
            dev = root / "dev"
            mirror = root / "mirror"
            (master / "src").mkdir(parents=True)
            (dev / "src").mkdir(parents=True)
            (master / "src" / "app.c").write_text("version one\n", encoding="utf-8")
            (dev / "src" / "app.c").write_text("version two\n", encoding="utf-8")
            (dev / "src" / "new.c").write_text("new file\n", encoding="utf-8")

            config = ProjectConfig(
                project="sce",
                local_repo=mirror,
                branches={
                    "master": BranchConfig(name="master", git_branch="cc-master", source_path=master),
                    "dev": BranchConfig(name="dev", git_branch="cc-dev", source_path=dev),
                },
                default_base="master",
                default_target="dev",
            )
            service = SnapshotService(config, clearcase=FakeClearCase())

            master_result = service.snapshot("master")
            dev_result = service.snapshot("dev")
            report = service.compare("master", "dev")

            self.assertTrue(master_result.commit.changed)
            self.assertTrue(dev_result.commit.changed)
            self.assertEqual(report.counts, {"added": 1, "modified": 1})
            self.assertEqual(
                [(entry.label, entry.path) for entry in report.entries],
                [("modified", "src/app.c"), ("added", "src/new.c")],
            )
            self.assertTrue((mirror / ".ccgit" / "master-snapshot.json").exists())
            self.assertTrue((mirror / ".ccgit" / "dev-snapshot.json").exists())

    def test_second_snapshot_without_changes_does_not_create_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "master"
            mirror = root / "mirror"
            source.mkdir()
            (source / "file.txt").write_text("same\n", encoding="utf-8")
            config = ProjectConfig(
                project="sce",
                local_repo=mirror,
                branches={"master": BranchConfig(name="master", git_branch="cc-master", source_path=source)},
            )
            service = SnapshotService(config, clearcase=FakeClearCase())

            first = service.snapshot("master")
            second = service.snapshot("master")

            self.assertTrue(first.commit.changed)
            self.assertFalse(second.commit.changed)
            self.assertEqual(first.commit.commit_sha, second.commit.commit_sha)

    def test_snapshot_pushes_to_local_bare_remote(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "master"
            mirror = root / "mirror"
            remote = root / "remote.git"
            source.mkdir()
            (source / "file.txt").write_text("push me\n", encoding="utf-8")
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            config = ProjectConfig(
                project="sce",
                local_repo=mirror,
                gitea_repo=str(remote),
                branches={"master": BranchConfig(name="master", git_branch="cc-master", source_path=source)},
            )
            service = SnapshotService(config, clearcase=FakeClearCase())

            result = service.snapshot("master", push=True)
            pushed_sha = subprocess.run(
                ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/cc-master"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout.strip()

            self.assertTrue(result.pushed)
            self.assertEqual(result.commit.commit_sha, pushed_sha)


if __name__ == "__main__":
    unittest.main()
