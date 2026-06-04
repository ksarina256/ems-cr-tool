"""Dependency-free web UI for the ClearCase snapshot mirror."""

from __future__ import annotations

from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

from .config import ProjectConfig
from .jobs import Job, JobStore
from .snapshot import SnapshotService


class CcGitHandler(BaseHTTPRequestHandler):
    config: ProjectConfig
    jobs: JobStore

    server_version = "ccgit/0.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.html(HTTPStatus.OK, render_dashboard(self.config, self.jobs))
            return
        if parsed.path.startswith("/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            job = self.jobs.get(job_id)
            if not job:
                self.html(HTTPStatus.NOT_FOUND, render_page("Job Not Found", "<p>Unknown job.</p>"))
                return
            self.html(HTTPStatus.OK, render_job(self.config, job))
            return
        if parsed.path.startswith("/reports/"):
            self.serve_report(parsed.path.rsplit("/", 1)[-1])
            return
        self.html(HTTPStatus.NOT_FOUND, render_page("Not Found", "<p>Page not found.</p>"))

    def do_POST(self) -> None:  # noqa: N802 - stdlib method name
        parsed = urlparse(self.path)
        form = self.read_form()
        if parsed.path == "/jobs/snapshot":
            branch = form.get("branch", [""])[0]
            push = form.get("push", [""])[0] == "on"
            if branch != "all" and branch not in self.config.branches:
                self.html(HTTPStatus.BAD_REQUEST, render_page("Bad Request", "<p>Unknown branch.</p>"))
                return

            job = self.jobs.create("snapshot", {"branch": branch, "push": push})

            def work() -> Dict[str, Any]:
                service = SnapshotService(self.config)
                if branch == "all":
                    results = service.snapshot_all(push=push)
                    return {name: result.to_dict() for name, result in results.items()}
                return service.snapshot(branch, push=push).to_dict()

            self.jobs.start_background(job, work)
            self.redirect(f"/jobs/{job.id}")
            return

        if parsed.path == "/jobs/compare":
            base = form.get("base", [""])[0]
            target = form.get("target", [""])[0]
            if base not in self.config.branches or target not in self.config.branches:
                self.html(HTTPStatus.BAD_REQUEST, render_page("Bad Request", "<p>Unknown compare branch.</p>"))
                return

            job = self.jobs.create("compare", {"base": base, "target": target})

            def work() -> Dict[str, Any]:
                service = SnapshotService(self.config)
                report = service.compare(base, target)
                paths = service.write_compare_report(base, target, report=report)
                payload = report.to_dict()
                payload["report_paths"] = paths
                return payload

            self.jobs.start_background(job, work)
            self.redirect(f"/jobs/{job.id}")
            return

        self.html(HTTPStatus.NOT_FOUND, render_page("Not Found", "<p>Page not found.</p>"))

    def read_form(self) -> Dict[str, list]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return parse_qs(body)

    def redirect(self, path: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", path)
        self.end_headers()

    def html(self, status: HTTPStatus, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def serve_report(self, raw_name: str) -> None:
        name = Path(unquote(raw_name)).name
        report_path = self.config.local_repo / self.config.metadata_dir / "reports" / name
        if not report_path.exists() or report_path.suffix != ".html":
            self.html(HTTPStatus.NOT_FOUND, render_page("Report Not Found", "<p>Report not found.</p>"))
            return
        encoded = report_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_server(config: ProjectConfig, *, host: str = "127.0.0.1", port: int = 8080) -> None:
    jobs_path = config.local_repo / config.metadata_dir / "jobs.json"
    CcGitHandler.config = config
    CcGitHandler.jobs = JobStore(jobs_path)
    server = ThreadingHTTPServer((host, port), CcGitHandler)
    url = f"http://{host}:{port}"
    print(f"ccgit web UI running at {url}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


def render_dashboard(config: ProjectConfig, jobs: JobStore) -> str:
    branch_options = "\n".join(
        f'<option value="{escape(name)}">{escape(name)} ({escape(branch.git_branch)})</option>'
        for name, branch in config.branches.items()
    )
    rows = "\n".join(
        "<tr>"
        f'<td><a href="/jobs/{escape(job.id)}">{escape(job.id[:8])}</a></td>'
        f"<td>{escape(job.kind)}</td>"
        f"<td>{status_badge(job.status)}</td>"
        f"<td>{escape(job.created_utc)}</td>"
        f"<td>{escape(details_text(job.details))}</td>"
        "</tr>"
        for job in jobs.list()
    )
    compare_link = ""
    if config.gitea_web_url and config.default_base and config.default_target:
        url = config.compare_url(config.default_base, config.default_target)
        compare_link = f'<p><a class="button secondary" href="{escape(url or "#")}">Open Default Gitea Compare</a></p>'

    content = f"""
<section class="grid">
  <div class="panel">
    <h2>Refresh Snapshots</h2>
    <form method="post" action="/jobs/snapshot">
      <label>Branch</label>
      <select name="branch">
        <option value="all">all configured branches</option>
        {branch_options}
      </select>
      <label class="check"><input type="checkbox" name="push" {"checked" if config.gitea_repo else ""}> Push to Gitea</label>
      <button type="submit">Refresh Snapshot</button>
    </form>
  </div>
  <div class="panel">
    <h2>Compare</h2>
    <form method="post" action="/jobs/compare">
      <label>Base</label>
      <select name="base">{branch_options}</select>
      <label>Target</label>
      <select name="target">{branch_options}</select>
      <button type="submit">Run Compare</button>
    </form>
    {compare_link}
  </div>
</section>
<section class="panel">
  <h2>Project</h2>
  <dl>
    <dt>Name</dt><dd>{escape(config.project)}</dd>
    <dt>Local repo</dt><dd><code>{escape(str(config.local_repo))}</code></dd>
    <dt>Gitea repo</dt><dd><code>{escape(config.gitea_repo or "not configured")}</code></dd>
  </dl>
</section>
<section class="panel">
  <h2>Recent Jobs</h2>
  <table>
    <thead><tr><th>Job</th><th>Type</th><th>Status</th><th>Created</th><th>Details</th></tr></thead>
    <tbody>{rows or '<tr><td colspan="5">No jobs yet.</td></tr>'}</tbody>
  </table>
</section>
"""
    return render_page("ClearCase Git Mirror", content)


def render_job(config: ProjectConfig, job: Job) -> str:
    refresh = '<meta http-equiv="refresh" content="4">' if job.status in {"queued", "running"} else ""
    result_html = ""
    if job.result:
        result_html = render_result(job.result)
    error_html = ""
    if job.error:
        error_html = f"<h2>Error</h2><pre>{escape(job.error)}</pre>"
        if job.traceback:
            error_html += f"<details><summary>Traceback</summary><pre>{escape(job.traceback)}</pre></details>"

    report_link = report_link_for_result(config, job.result)
    content = f"""
{refresh}
<p><a href="/">Back to dashboard</a></p>
<section class="panel">
  <h2>Job {escape(job.id[:8])}</h2>
  <dl>
    <dt>Type</dt><dd>{escape(job.kind)}</dd>
    <dt>Status</dt><dd>{status_badge(job.status)}</dd>
    <dt>Created</dt><dd>{escape(job.created_utc)}</dd>
    <dt>Started</dt><dd>{escape(job.started_utc or "")}</dd>
    <dt>Finished</dt><dd>{escape(job.finished_utc or "")}</dd>
    <dt>Details</dt><dd>{escape(details_text(job.details))}</dd>
  </dl>
  {report_link}
</section>
{error_html}
{result_html}
"""
    return render_page("Job Status", content)


def render_result(result: Dict[str, Any]) -> str:
    if "entries" in result:
        rows = "\n".join(
            "<tr>"
            f"<td>{escape(str(item.get('label') or item.get('status') or ''))}</td>"
            f"<td>{escape(str(item.get('path') or ''))}</td>"
            "</tr>"
            for item in result.get("entries", [])
        )
        counts = ", ".join(f"{escape(str(key))}: {value}" for key, value in sorted((result.get("counts") or {}).items()))
        gitea = result.get("gitea_url")
        gitea_link = f'<p><a class="button secondary" href="{escape(gitea)}">Open in Gitea</a></p>' if gitea else ""
        return f"""
<section class="panel">
  <h2>Compare Result</h2>
  <p>{escape(counts or "No file changes")}</p>
  {gitea_link}
  <table>
    <thead><tr><th>Status</th><th>Path</th></tr></thead>
    <tbody>{rows or '<tr><td colspan="2">No file changes.</td></tr>'}</tbody>
  </table>
</section>
"""
    return f"<section class=\"panel\"><h2>Raw Result</h2><pre>{escape(json_text(result))}</pre></section>"


def report_link_for_result(config: ProjectConfig, result: Optional[Dict[str, Any]]) -> str:
    if not result:
        return ""
    report_paths = result.get("report_paths")
    if not isinstance(report_paths, dict):
        return ""
    html_path = report_paths.get("html")
    if not html_path:
        return ""
    name = Path(str(html_path)).name
    return f'<p><a class="button secondary" href="/reports/{escape(name)}">Open HTML Report</a></p>'


def render_page(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #596579;
      --line: #d8dee8;
      --panel: #ffffff;
      --page: #f3f6f8;
      --accent: #176b87;
      --accent-dark: #0f4f63;
      --ok: #287d4f;
      --warn: #9a6612;
      --bad: #a63a3a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--page);
      color: var(--ink);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      background: #15232d;
      color: white;
      padding: 1rem 1.25rem;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 1.25rem;
    }}
    h1, h2 {{ margin: 0 0 0.8rem; }}
    h1 {{ font-size: 1.35rem; }}
    h2 {{ font-size: 1rem; }}
    a {{ color: var(--accent-dark); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1rem;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 1rem;
      margin-bottom: 1rem;
    }}
    label {{
      display: block;
      font-weight: 650;
      margin: 0.75rem 0 0.3rem;
    }}
    label.check {{
      display: flex;
      gap: 0.45rem;
      align-items: center;
      font-weight: 500;
    }}
    select, button {{
      width: 100%;
      min-height: 2.35rem;
      border-radius: 6px;
      border: 1px solid var(--line);
      padding: 0.45rem 0.55rem;
      font: inherit;
    }}
    button, .button {{
      display: inline-block;
      text-align: center;
      background: var(--accent);
      color: white;
      border: 0;
      text-decoration: none;
      padding: 0.55rem 0.8rem;
      border-radius: 6px;
      cursor: pointer;
      margin-top: 0.8rem;
    }}
    .button.secondary {{
      background: #e7eef2;
      color: var(--accent-dark);
      border: 1px solid #bfd2dd;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      overflow-wrap: anywhere;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 0.55rem;
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-size: 0.82rem; }}
    dl {{
      display: grid;
      grid-template-columns: minmax(120px, 180px) 1fr;
      gap: 0.4rem 0.75rem;
      margin: 0;
    }}
    dt {{ color: var(--muted); font-weight: 650; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    code, pre {{
      background: #eef2f5;
      border-radius: 6px;
    }}
    code {{ padding: 0.1rem 0.25rem; }}
    pre {{
      padding: 0.85rem;
      overflow: auto;
      max-height: 520px;
    }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 0.16rem 0.55rem;
      font-weight: 700;
      font-size: 0.78rem;
    }}
    .queued, .running {{ background: #fff4d6; color: var(--warn); }}
    .succeeded {{ background: #dff3e7; color: var(--ok); }}
    .failed {{ background: #fde2e2; color: var(--bad); }}
  </style>
</head>
<body>
  <header><h1>{escape(title)}</h1></header>
  <main>{content}</main>
</body>
</html>
"""


def status_badge(status: str) -> str:
    safe = escape(status)
    return f'<span class="badge {safe}">{safe}</span>'


def details_text(details: Dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(details.items()))


def json_text(value: Any) -> str:
    import json

    return json.dumps(value, indent=2, sort_keys=True)
