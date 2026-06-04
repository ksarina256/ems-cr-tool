import json
import tempfile
import unittest
from pathlib import Path

from ccgit.report import CompareReport, DiffEntry, count_entries, parse_name_status


class ReportTest(unittest.TestCase):
    def test_parse_name_status_handles_rename_copy_and_common_statuses(self):
        entries = parse_name_status(
            "M\tsrc/app.c\n"
            "A\tsrc/new.c\n"
            "D\tsrc/old.c\n"
            "R100\tsrc/name-old.c\tsrc/name-new.c\n"
            "C075\tsrc/template.c\tsrc/copy.c\n"
        )

        self.assertEqual(
            [(entry.label, entry.old_path, entry.path) for entry in entries],
            [
                ("modified", None, "src/app.c"),
                ("added", None, "src/new.c"),
                ("deleted", None, "src/old.c"),
                ("renamed", "src/name-old.c", "src/name-new.c"),
                ("copied", "src/template.c", "src/copy.c"),
            ],
        )
        self.assertEqual(
            count_entries(entries),
            {"added": 1, "copied": 1, "deleted": 1, "modified": 1, "renamed": 1},
        )

    def test_report_writes_json_and_escaped_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = CompareReport(
                base="cc-master",
                target="cc-dev",
                entries=[DiffEntry(status="M", path="src/<unsafe>.c")],
                stat="1 file changed",
                gitea_url="https://gitea/team/repo/compare/cc-master...cc-dev",
                counts={"modified": 1},
            )

            json_path = root / "report.json"
            html_path = root / "report.html"
            report.write_json(json_path)
            report.write_html(html_path)

            data = json.loads(json_path.read_text(encoding="utf-8"))
            html = html_path.read_text(encoding="utf-8")
            self.assertEqual(data["counts"], {"modified": 1})
            self.assertIn("src/&lt;unsafe&gt;.c", html)
            self.assertIn("Open full diff in Gitea", html)


if __name__ == "__main__":
    unittest.main()
