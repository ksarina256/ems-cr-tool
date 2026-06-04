"""ClearCase view helpers."""

from __future__ import annotations

from dataclasses import dataclass
import shlex
from pathlib import Path
from typing import Optional, Sequence

from .config import BranchConfig, ProjectConfig
from .runner import CommandRunner


@dataclass(frozen=True)
class ViewInfo:
    view: Optional[str]
    pwv: str
    config_spec: str


class ClearCaseClient:
    def __init__(self, runner: Optional[CommandRunner] = None):
        self.runner = runner or CommandRunner()

    def validate_available(self) -> bool:
        result = self.runner.run(["cleartool", "-version"], check=False)
        return result.returncode == 0

    def view_info(self, branch: BranchConfig) -> ViewInfo:
        if branch.copy_mode == "setview":
            pwv = self.run_in_view(branch, ["cleartool", "pwv"], check=False)
            catcs = self.run_in_view(branch, ["cleartool", "catcs"], check=False)
            return ViewInfo(view=branch.view, pwv=pwv, config_spec=catcs)

        pwv_result = self.runner.run(["cleartool", "pwv"], check=False)
        catcs_result = self.runner.run(["cleartool", "catcs"], check=False)
        return ViewInfo(
            view=branch.view,
            pwv=pwv_result.stdout.strip() if pwv_result.returncode == 0 else pwv_result.stderr.strip(),
            config_spec=catcs_result.stdout if catcs_result.returncode == 0 else catcs_result.stderr,
        )

    def copy_view_to_staging(self, config: ProjectConfig, branch: BranchConfig, staging_dir: Path) -> None:
        staging_dir.mkdir(parents=True, exist_ok=True)
        if branch.copy_mode == "direct":
            return

        if not branch.view:
            raise ValueError(f"Branch '{branch.name}' uses setview but has no view configured")

        command = self._rsync_command(config, branch.source_path, staging_dir, config.exclude)
        self.runner.run(["cleartool", "setview", "-exec", command, branch.view])

    def run_in_view(self, branch: BranchConfig, args: Sequence[str], *, check: bool = True) -> str:
        if not branch.view:
            raise ValueError(f"Branch '{branch.name}' has no ClearCase view configured")
        command = " ".join(shlex.quote(str(arg)) for arg in args)
        result = self.runner.run(["cleartool", "setview", "-exec", command, branch.view], check=check)
        return result.stdout.strip()

    @staticmethod
    def _rsync_command(config: ProjectConfig, source: Path, destination: Path, excludes: Sequence[str]) -> str:
        source_text = str(source)
        if not source_text.endswith("/"):
            source_text += "/"
        destination_text = str(destination)
        if not destination_text.endswith("/"):
            destination_text += "/"

        parts = [config.rsync_path, "-a", "--delete"]
        for pattern in excludes:
            parts.extend(["--exclude", pattern])
        parts.extend([source_text, destination_text])
        return " ".join(shlex.quote(str(part)) for part in parts)
