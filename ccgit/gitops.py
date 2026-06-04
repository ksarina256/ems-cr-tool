"""Git operations used by the snapshot mirror."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .runner import CommandRunner


@dataclass(frozen=True)
class CommitResult:
    changed: bool
    commit_sha: Optional[str]
    message: str


class GitRepo:
    def __init__(self, path: Path, runner: Optional[CommandRunner] = None):
        self.path = path
        self.runner = runner or CommandRunner()

    def run(self, *args: str, check: bool = True) -> str:
        result = self.runner.run(["git", *args], cwd=self.path, check=check)
        return result.stdout.strip()

    def ensure(self, remote_url: Optional[str] = None) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        if not (self.path / ".git").exists():
            self.runner.run(["git", "init"], cwd=self.path)
            self.run("config", "core.autocrlf", "false")
            self.run("config", "user.name", "ClearCase Mirror")
            self.run("config", "user.email", "clearcase-mirror@example.invalid")
        self.ensure_local_exclude(".ccgit/")
        if remote_url:
            self.ensure_remote(remote_url)

    def ensure_remote(self, remote_url: str, name: str = "origin") -> None:
        existing = self.runner.run(["git", "remote"], cwd=self.path).stdout.splitlines()
        if name in existing:
            self.run("remote", "set-url", name, remote_url)
        else:
            self.run("remote", "add", name, remote_url)

    def checkout_branch(self, branch: str) -> None:
        self.run("checkout", "-B", branch)

    def add_all(self) -> None:
        self.run("add", "-A")

    def ensure_local_exclude(self, pattern: str) -> None:
        exclude_path = self.path / ".git" / "info" / "exclude"
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
        if pattern not in existing.splitlines():
            with exclude_path.open("a", encoding="utf-8") as handle:
                if existing and not existing.endswith("\n"):
                    handle.write("\n")
                handle.write(pattern + "\n")

    def has_changes(self) -> bool:
        return bool(self.run("status", "--porcelain"))

    def commit(self, message: str) -> CommitResult:
        self.add_all()
        if not self.has_changes():
            sha = self.head_sha()
            return CommitResult(changed=False, commit_sha=sha, message="No changes to commit")
        self.run("commit", "-m", message)
        return CommitResult(changed=True, commit_sha=self.head_sha(), message="Committed snapshot")

    def head_sha(self) -> Optional[str]:
        result = self.runner.run(["git", "rev-parse", "HEAD"], cwd=self.path, check=False)
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def push(self, branch: str, remote: str = "origin") -> None:
        self.run("push", "-u", remote, branch)

    def diff_name_status(self, base: str, target: str, *, exclude_path: Optional[str] = None) -> str:
        cmd = ["git", "diff", "--name-status", "-M", base, target]
        if exclude_path:
            cmd.extend(["--", ".", f":(exclude){exclude_path}"])
        result = self.runner.run(cmd, cwd=self.path)
        return result.stdout

    def diff_stat(self, base: str, target: str, *, exclude_path: Optional[str] = None) -> str:
        cmd = ["git", "diff", "--stat", base, target]
        if exclude_path:
            cmd.extend(["--", ".", f":(exclude){exclude_path}"])
        result = self.runner.run(cmd, cwd=self.path)
        return result.stdout

    def branch_exists(self, branch: str) -> bool:
        result = self.runner.run(["git", "rev-parse", "--verify", branch], cwd=self.path, check=False)
        return result.returncode == 0
