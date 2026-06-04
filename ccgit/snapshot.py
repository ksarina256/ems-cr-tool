"""Snapshot and comparison services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Dict, Optional

from .clearcase import ClearCaseClient, ViewInfo
from .config import BranchConfig, ProjectConfig
from .gitops import CommitResult, GitRepo
from .report import CompareReport, count_entries, parse_name_status
from .runner import CommandRunner
from .sync import SyncSummary, build_manifest, manifest_to_dict, sync_tree


@dataclass(frozen=True)
class SnapshotResult:
    project: str
    branch_name: str
    git_branch: str
    source_path: str
    local_repo: str
    commit: CommitResult
    sync: SyncSummary
    manifest_count: int
    pushed: bool
    metadata_path: str
    view_info: ViewInfo

    def to_dict(self) -> Dict[str, object]:
        return {
            "project": self.project,
            "branch_name": self.branch_name,
            "git_branch": self.git_branch,
            "source_path": self.source_path,
            "local_repo": self.local_repo,
            "commit": {
                "changed": self.commit.changed,
                "commit_sha": self.commit.commit_sha,
                "message": self.commit.message,
            },
            "sync": {
                "copied": self.sync.copied,
                "removed": self.sync.removed,
                "unchanged": self.sync.unchanged,
                "skipped": self.sync.skipped,
            },
            "manifest_count": self.manifest_count,
            "pushed": self.pushed,
            "metadata_path": self.metadata_path,
            "view": self.view_info.view,
            "pwv": self.view_info.pwv,
        }


class SnapshotService:
    def __init__(
        self,
        config: ProjectConfig,
        *,
        runner: Optional[CommandRunner] = None,
        clearcase: Optional[ClearCaseClient] = None,
        git_repo: Optional[GitRepo] = None,
    ):
        self.config = config
        self.runner = runner or CommandRunner()
        self.clearcase = clearcase or ClearCaseClient(self.runner)
        self.git = git_repo or GitRepo(config.local_repo, self.runner)

    def validate(self) -> Dict[str, object]:
        results: Dict[str, object] = {
            "project": self.config.project,
            "local_repo": str(self.config.local_repo),
            "gitea_repo": self.config.gitea_repo,
            "branches": {},
        }
        for name, branch in self.config.branches.items():
            source_exists = branch.source_path.exists() if branch.copy_mode == "direct" else None
            results["branches"][name] = {
                "view": branch.view,
                "copy_mode": branch.copy_mode,
                "source_path": str(branch.source_path),
                "source_exists": source_exists,
                "git_branch": branch.git_branch,
            }
        return results

    def snapshot(self, branch_name: str, *, push: bool = False) -> SnapshotResult:
        branch = self.config.branch(branch_name)
        self.git.ensure(self.config.gitea_repo)
        self.git.checkout_branch(branch.git_branch)

        source = self._prepare_source(branch)
        sync = sync_tree(source, self.config.local_repo, self.config.exclude)
        view_info = self.clearcase.view_info(branch)
        metadata_path = self._write_metadata(branch, source, sync, view_info)
        commit = self.git.commit(f"Snapshot {self.config.project} {branch.name}")

        pushed = False
        if push:
            if not self.config.gitea_repo:
                raise ValueError("Cannot push: 'gitea_repo' is not configured")
            self.git.push(branch.git_branch)
            pushed = True

        return SnapshotResult(
            project=self.config.project,
            branch_name=branch.name,
            git_branch=branch.git_branch,
            source_path=str(source),
            local_repo=str(self.config.local_repo),
            commit=commit,
            sync=sync,
            manifest_count=len(build_manifest(source, self.config.exclude)),
            pushed=pushed,
            metadata_path=str(metadata_path),
            view_info=view_info,
        )

    def snapshot_all(self, *, push: bool = False) -> Dict[str, SnapshotResult]:
        return {name: self.snapshot(name, push=push) for name in self.config.branches}

    def compare(self, base: str, target: str) -> CompareReport:
        self.git.ensure(self.config.gitea_repo)
        base_ref = self.config.git_ref(base)
        target_ref = self.config.git_ref(target)
        raw = self.git.diff_name_status(base_ref, target_ref, exclude_path=self.config.metadata_dir)
        stat = self.git.diff_stat(base_ref, target_ref, exclude_path=self.config.metadata_dir)
        entries = parse_name_status(raw)
        return CompareReport(
            base=base_ref,
            target=target_ref,
            entries=entries,
            stat=stat,
            gitea_url=self.config.compare_url(base, target),
            counts=count_entries(entries),
        )

    def report_paths(self, base: str, target: str) -> Dict[str, Path]:
        reports = self.config.local_repo / self.config.metadata_dir / "reports"
        safe_name = f"{self.config.git_ref(base)}__{self.config.git_ref(target)}".replace("/", "_")
        return {
            "json": reports / f"{safe_name}.json",
            "html": reports / f"{safe_name}.html",
        }

    def write_compare_report(self, base: str, target: str, report: Optional[CompareReport] = None) -> Dict[str, str]:
        report = report or self.compare(base, target)
        paths = self.report_paths(base, target)
        report.write_json(paths["json"])
        report.write_html(paths["html"])
        return {key: str(path) for key, path in paths.items()}

    def _prepare_source(self, branch: BranchConfig) -> Path:
        if branch.copy_mode == "direct":
            if not branch.source_path.exists():
                raise FileNotFoundError(f"Source path does not exist: {branch.source_path}")
            return branch.source_path

        staging = self.config.local_repo.parent / "_staging" / branch.name
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True, exist_ok=True)
        self.clearcase.copy_view_to_staging(self.config, branch, staging)
        return staging

    def _write_metadata(
        self,
        branch: BranchConfig,
        source: Path,
        sync: SyncSummary,
        view_info: ViewInfo,
    ) -> Path:
        metadata_root = self.config.local_repo / self.config.metadata_dir
        metadata_root.mkdir(parents=True, exist_ok=True)
        manifest = build_manifest(source, self.config.exclude)
        payload = {
            "project": self.config.project,
            "branch": branch.name,
            "git_branch": branch.git_branch,
            "source_path": str(branch.source_path),
            "copy_mode": branch.copy_mode,
            "view": branch.view,
            "snapshot_utc": datetime.now(timezone.utc).isoformat(),
            "sync": {
                "copied": sync.copied,
                "removed": sync.removed,
                "unchanged": sync.unchanged,
                "skipped": sync.skipped,
            },
            "clearcase": {
                "pwv": view_info.pwv,
                "config_spec": view_info.config_spec,
            },
            "manifest": manifest_to_dict(manifest),
        }
        path = metadata_root / f"{branch.name}-snapshot.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path
