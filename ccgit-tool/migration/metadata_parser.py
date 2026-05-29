"""
Metadata Parser
---------------
Parses and normalises ClearCase metadata (authors, timestamps)
for use in Git commit authorship and tag messages.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class MetadataParser:
    def __init__(self, config: dict):
        self.config = config
        self.author_map = config.get("author_map", {})

    def parse_author(self, cc_user: str) -> tuple[str, str]:
        """
        Convert a ClearCase username to a Git-style author string.
        Looks up author_map in config; falls back to username@sce.com.

        Returns: (display_name, email)
        """
        if not cc_user:
            return ("CCGit Migration", "ccgit@sce.com")

        if cc_user in self.author_map:
            entry = self.author_map[cc_user]
            return (entry.get("name", cc_user), entry.get("email", f"{cc_user}@sce.com"))

        # Default: use the CC username as name + @sce.com domain
        clean = cc_user.strip().lower().replace(" ", ".")
        return (cc_user, f"{clean}@sce.com")

    def parse_timestamp(self, cc_timestamp: str) -> Optional[str]:
        """
        Convert a ClearCase timestamp string to ISO 8601 format for Git.
        CC format example: '20240315.143022' or '2024-03-15T14:30:22'
        Returns None if parsing fails.
        """
        if not cc_timestamp:
            return None

        # Try ClearCase compact format: YYYYMMDD.HHMMSS
        match = re.match(r"(\d{4})(\d{2})(\d{2})\.(\d{2})(\d{2})(\d{2})", cc_timestamp)
        if match:
            y, mo, d, h, mi, s = match.groups()
            return f"{y}-{mo}-{d}T{h}:{mi}:{s}"

        # Try ISO format passthrough
        if re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", cc_timestamp):
            return cc_timestamp

        logger.debug(f"Could not parse timestamp: {cc_timestamp}")
        return None

    def build_commit_message(
        self,
        file_path: str,
        version: str = "",
        author: str = "",
        timestamp: str = "",
        label: str = "",
    ) -> str:
        """
        Build a Git commit message for a specific ClearCase version.
        Used during history migration (stretch goal).
        """
        lines = [f"migrate: {file_path}"]
        if version:
            lines.append(f"\nClearCase version : {version}")
        if author:
            lines.append(f"Author            : {author}")
        if timestamp:
            lines.append(f"CC Timestamp      : {timestamp}")
        if label:
            lines.append(f"Label             : {label}")
        lines.append("\nMigrated by CCGit Tool (EMS Apps, SCE)")
        return "\n".join(lines)
