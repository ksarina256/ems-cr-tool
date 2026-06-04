import tempfile
import unittest
from pathlib import Path

from ccgit.config import BranchConfig, ProjectConfig
from ccgit.jobs import JobStore
from ccgit.web import render_dashboard, render_job, report_link_for_result


class WebRenderTest(unittest.TestCase):
    def test_dashboard_renders_configured_branches_and_gitea_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.config(Path(tmp).resolve())
            jobs = JobStore(config.local_repo / config.metadata_dir / "jobs.json")
            jobs.create("snapshot", {"branch": "master"})

            html = render_dashboard(config, jobs)

            self.assertIn("Refresh Snapshot", html)
            self.assertIn("master (cc-master)", html)
            self.assertIn("dev (cc-dev)", html)
            self.assertIn("https://gitea/team/repo/compare/cc-master...cc-dev", html)

    def test_job_page_renders_report_link_and_compare_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.config(Path(tmp).resolve())
            jobs = JobStore(config.local_repo / config.metadata_dir / "jobs.json")
            job = jobs.create("compare", {"base": "master", "target": "dev"})
            jobs.update(
                job.id,
                status="succeeded",
                result={
                    "counts": {"modified": 1},
                    "entries": [{"label": "modified", "path": "src/app.c"}],
                    "report_paths": {"html": str(config.local_repo / ".ccgit" / "reports" / "cc-master__cc-dev.html")},
                },
            )

            html = render_job(config, jobs.get(job.id))

            self.assertIn("Open HTML Report", html)
            self.assertIn("modified: 1", html)
            self.assertIn("src/app.c", html)

    def test_report_link_uses_only_file_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.config(Path(tmp).resolve())
            link = report_link_for_result(config, {"report_paths": {"html": "/tmp/outside/report.html"}})

            self.assertIn("/reports/report.html", link)
            self.assertNotIn("/tmp/outside", link)

    @staticmethod
    def config(root: Path) -> ProjectConfig:
        return ProjectConfig(
            project="sce",
            local_repo=root / "mirror",
            gitea_web_url="https://gitea/team/repo",
            default_base="master",
            default_target="dev",
            branches={
                "master": BranchConfig(name="master", git_branch="cc-master", source_path=root / "master"),
                "dev": BranchConfig(name="dev", git_branch="cc-dev", source_path=root / "dev"),
            },
        )


if __name__ == "__main__":
    unittest.main()
