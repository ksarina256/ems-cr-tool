import tempfile
import unittest
from pathlib import Path

from ccgit.sync import build_manifest, is_excluded, sync_tree


class SyncTest(unittest.TestCase):
    def test_excludes_directory_and_glob_patterns(self):
        self.assertTrue(is_excluded("bin/tool", ["bin/"]))
        self.assertTrue(is_excluded("obj/main.o", ["*.o"]))
        self.assertFalse(is_excluded("src/main.c", ["bin/", "*.o"]))

    def test_sync_tree_copies_updates_and_removes_stale_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "source"
            dest = root / "dest"
            (source / "src").mkdir(parents=True)
            (source / "bin").mkdir()
            (dest / "old").mkdir(parents=True)
            (source / "src" / "main.c").write_text("int main() {}\n", encoding="utf-8")
            (source / "bin" / "generated").write_text("skip\n", encoding="utf-8")
            (dest / "old" / "stale.txt").write_text("remove me\n", encoding="utf-8")
            (dest / ".git").mkdir(parents=True)
            (dest / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

            summary = sync_tree(source, dest, ["bin/"])
            manifest = build_manifest(dest, [])

            self.assertEqual(summary.copied, 1)
            self.assertEqual(summary.removed, 1)
            self.assertTrue((dest / "src" / "main.c").exists())
            self.assertFalse((dest / "bin" / "generated").exists())
            self.assertFalse((dest / "old" / "stale.txt").exists())
            self.assertTrue((dest / ".git" / "HEAD").exists())
            self.assertEqual([item.path for item in manifest], ["src/main.c"])

    def test_newly_excluded_stale_files_are_removed_from_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "source"
            dest = root / "dest"
            (source / "src").mkdir(parents=True)
            (dest / "bin").mkdir(parents=True)
            (dest / ".git").mkdir(parents=True)
            (source / "src" / "main.c").write_text("source\n", encoding="utf-8")
            (dest / "bin" / "old-generated").write_text("old\n", encoding="utf-8")
            (dest / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

            summary = sync_tree(source, dest, ["bin/"])

            self.assertEqual(summary.removed, 1)
            self.assertFalse((dest / "bin" / "old-generated").exists())
            self.assertTrue((dest / ".git" / "HEAD").exists())


if __name__ == "__main__":
    unittest.main()
