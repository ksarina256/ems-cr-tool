"""
Git Adapter
-----------
Handles all Git repository operations using GitPython.
Wraps repo init, file staging, committing, and tag creation.
"""

import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class GitError(Exception):
    pass


class GitAdapter:
    def __init__(self, config: dict):
        git_cfg = config.get("git", {})
        self.output_dir = git_cfg.get("output_dir", "/tmp/ccgit_output")
        self.repo = None

    # ── Public API ────────────────────────────────────────────────────

    def init_repo(self, repo_name: str) -> str:
        """
        Initialise a new bare Git repository at output_dir/repo_name.
        Returns the full path to the new repo.
        Raises GitError if the directory already exists.
        """
        try:
            import git as gitpython
        except ImportError:
            raise GitError("GitPython not installed. Run: pip install gitpython")

        repo_path = os.path.join(self.output_dir, repo_name)

        if os.path.exists(repo_path):
            logger.warning(f"Repo path already exists, using existing: {repo_path}")
            self.repo = gitpython.Repo(repo_path)
        else:
            os.makedirs(repo_path, exist_ok=True)
            self.repo = gitpython.Repo.init(repo_path)
            logger.info(f"Initialised Git repo at: {repo_path}")

        return repo_path

    def get_repo_path(self) -> str:
        """Return the working tree path of the current repo."""
        if not self.repo:
            raise GitError("No repository initialised. Call init_repo() first.")
        return self.repo.working_tree_dir

    def stage_all(self):
        """Stage all files in the working tree."""
        if not self.repo:
            raise GitError("No repository initialised.")
        self.repo.git.add(A=True)
        logger.debug("Staged all files")

    def commit(
        self,
        message: str = "chore: initial migration from ClearCase",
        author_name: str = "CCGit Tool",
        author_email: str = "ccgit@sce.com",
        timestamp: Optional[str] = None,
    ):
        """
        Create a commit with the staged files.
        Optionally override author and timestamp for metadata preservation.
        """
        if not self.repo:
            raise GitError("No repository initialised.")

        if self.repo.is_dirty(untracked_files=True) or len(self.repo.untracked_files) > 0:
            author_str = f"{author_name} <{author_email}>"
            env = {}
            if timestamp:
                env["GIT_AUTHOR_DATE"] = timestamp
                env["GIT_COMMITTER_DATE"] = timestamp

            self.repo.index.commit(
                message,
                author=self._make_actor(author_name, author_email),
                committer=self._make_actor("CCGit Tool", "ccgit@sce.com"),
            )
            logger.info(f"Committed: {message}")
        else:
            logger.warning("Nothing to commit — working tree is clean")

    def create_tag(self, tag_name: str, message: str = ""):
        """Create a Git tag from a ClearCase label."""
        if not self.repo:
            raise GitError("No repository initialised.")
        safe_tag = tag_name.replace(" ", "_")
        try:
            self.repo.create_tag(safe_tag, message=message or f"Migrated from CC label: {tag_name}")
            logger.info(f"Created tag: {safe_tag}")
        except Exception as e:
            logger.warning(f"Could not create tag {safe_tag}: {e}")

    def count_files(self) -> int:
        """Return the number of tracked files in the repo."""
        if not self.repo:
            return 0
        try:
            result = self.repo.git.ls_files()
            lines = [l for l in result.splitlines() if l.strip()]
            return len(lines)
        except Exception:
            return 0

    def write_gitignore(self, extra_patterns: Optional[List[str]] = None):
        """
        Write a .gitignore tuned for ClearCase migration artifacts.
        """
        default_patterns = [
            "# ClearCase artifacts",
            "*.keep",
            "lost+found/",
            ".copyarea.db",
            "*.contrib",
            "*.unloaded",
            "",
            "# Build artifacts",
            "*.class",
            "*.pyc",
            "__pycache__/",
            "*.o",
            "*.so",
            "*.a",
            "*.lib",
            "*.dll",
            "*.exe",
            "",
            "# IDE files",
            ".idea/",
            ".vscode/",
            "*.swp",
            "*.swo",
            "",
            "# OS files",
            ".DS_Store",
            "Thumbs.db",
        ]

        if extra_patterns:
            default_patterns += ["", "# Custom exclusions"] + extra_patterns

        repo_path = self.get_repo_path()
        gitignore_path = os.path.join(repo_path, ".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("\n".join(default_patterns) + "\n")
        logger.info("Wrote .gitignore")

    # ── Helpers ───────────────────────────────────────────────────────

    def _make_actor(self, name: str, email: str):
        try:
            from git import Actor
            return Actor(name, email)
        except ImportError:
            return None
