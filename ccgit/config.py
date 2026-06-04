"""Configuration loading for the ClearCase snapshot mirror."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CONFIG_FILES = ("ccgit.json", "ccgit.config.json")


class ConfigError(ValueError):
    """Raised when the project configuration is missing or invalid."""


@dataclass(frozen=True)
class BranchConfig:
    """A ClearCase view/path that maps to one Git branch."""

    name: str
    git_branch: str
    source_path: Path
    view: Optional[str] = None
    copy_mode: str = "direct"
    description: str = ""

    @staticmethod
    def from_dict(name: str, data: Dict[str, Any], base_dir: Path) -> "BranchConfig":
        if not isinstance(data, dict):
            raise ConfigError(f"branches.{name} must be an object")

        git_branch = str(data.get("git_branch") or f"cc-{name}")
        raw_source = data.get("source_path") or data.get("vob_path")
        if not raw_source:
            raise ConfigError(f"branches.{name}.source_path is required")

        source_path = Path(str(raw_source)).expanduser()
        if not source_path.is_absolute():
            source_path = (base_dir / source_path).resolve()

        view = data.get("view")
        view = str(view) if view else None
        copy_mode = str(data.get("copy_mode") or ("setview" if view else "direct"))
        if copy_mode not in {"direct", "setview"}:
            raise ConfigError(f"branches.{name}.copy_mode must be 'direct' or 'setview'")

        return BranchConfig(
            name=name,
            git_branch=git_branch,
            source_path=source_path,
            view=view,
            copy_mode=copy_mode,
            description=str(data.get("description") or ""),
        )


@dataclass(frozen=True)
class ProjectConfig:
    """Complete configuration for one mirrored ClearCase project."""

    project: str
    local_repo: Path
    branches: Dict[str, BranchConfig]
    gitea_repo: Optional[str] = None
    gitea_web_url: Optional[str] = None
    default_base: Optional[str] = None
    default_target: Optional[str] = None
    exclude: List[str] = field(default_factory=list)
    metadata_dir: str = ".ccgit"
    rsync_path: str = "rsync"

    @staticmethod
    def load(path: Optional[str] = None) -> "ProjectConfig":
        config_path = resolve_config_path(path)
        base_dir = config_path.parent
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in {config_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ConfigError("Top-level config must be a JSON object")

        project = str(data.get("project") or "").strip()
        if not project:
            raise ConfigError("'project' is required")

        local_repo_raw = data.get("local_repo") or f".ccgit-work/{project}-mirror"
        local_repo = Path(str(local_repo_raw)).expanduser()
        if not local_repo.is_absolute():
            local_repo = (base_dir / local_repo).resolve()

        raw_branches = data.get("branches")
        if not isinstance(raw_branches, dict) or not raw_branches:
            raise ConfigError("'branches' must define at least one branch")
        branches = {
            name: BranchConfig.from_dict(name, branch_data, base_dir)
            for name, branch_data in raw_branches.items()
        }

        default_base = data.get("default_base")
        default_target = data.get("default_target")
        branch_names = list(branches)
        if default_base is None and branch_names:
            default_base = branch_names[0]
        if default_target is None and len(branch_names) > 1:
            default_target = branch_names[1]

        exclude = data.get("exclude") or []
        if not isinstance(exclude, list):
            raise ConfigError("'exclude' must be a list")

        metadata_dir = str(data.get("metadata_dir") or ".ccgit")
        if metadata_dir in {"", ".", ".."} or "/" in metadata_dir or "\\" in metadata_dir:
            raise ConfigError("'metadata_dir' must be a simple directory name")

        return ProjectConfig(
            project=project,
            local_repo=local_repo,
            branches=branches,
            gitea_repo=data.get("gitea_repo"),
            gitea_web_url=data.get("gitea_web_url"),
            default_base=default_base,
            default_target=default_target,
            exclude=[str(item) for item in exclude],
            metadata_dir=metadata_dir,
            rsync_path=str(data.get("rsync_path") or "rsync"),
        )

    def branch(self, name: str) -> BranchConfig:
        try:
            return self.branches[name]
        except KeyError as exc:
            available = ", ".join(sorted(self.branches))
            raise ConfigError(f"Unknown branch '{name}'. Available: {available}") from exc

    def git_ref(self, name_or_ref: str) -> str:
        branch = self.branches.get(name_or_ref)
        return branch.git_branch if branch else name_or_ref

    def compare_url(self, base: str, target: str) -> Optional[str]:
        if not self.gitea_web_url:
            return None
        root = self.gitea_web_url.rstrip("/")
        return f"{root}/compare/{self.git_ref(base)}...{self.git_ref(target)}"


def resolve_config_path(path: Optional[str]) -> Path:
    if path:
        config_path = Path(path).expanduser()
        if not config_path.is_absolute():
            config_path = (Path.cwd() / config_path).resolve()
        if not config_path.exists():
            raise ConfigError(f"Config file not found: {config_path}")
        return config_path

    for candidate in DEFAULT_CONFIG_FILES:
        config_path = Path.cwd() / candidate
        if config_path.exists():
            return config_path.resolve()

    names = ", ".join(DEFAULT_CONFIG_FILES)
    raise ConfigError(f"No config file found. Expected one of: {names}")
