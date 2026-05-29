"""
ClearCase Adapter
-----------------
Wraps all cleartool CLI interactions.
Requires cleartool to be installed and the ClearCase view to be set.

All methods return structured data or raise ClearCaseError on failure.
"""

import subprocess
import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class ClearCaseError(Exception):
    pass


class ClearCaseAdapter:
    def __init__(self, config: dict):
        cc_cfg = config.get("clearcase", {})
        self.view_path = cc_cfg.get("view_path", "")
        self.vob_path = cc_cfg.get("vob_path", "")
        self.baseline = cc_cfg.get("baseline", None)
        self._verify_cleartool()

    # ── Public API ────────────────────────────────────────────────────

    def list_files(self) -> List[str]:
        """
        Return a list of all versioned file paths in the VOB.
        Filters out directories and view-private files.
        """
        logger.info(f"Listing files in VOB: {self.vob_path}")
        raw = self._run(["ls", "-r", "-short", self.vob_path])
        files = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            # Skip view-private files (no @@ version suffix means view-private)
            if "@@" not in line and not os.path.isfile(line):
                continue
            # Strip the version suffix from the path
            clean = line.split("@@")[0] if "@@" in line else line
            if os.path.isfile(clean):
                files.append(clean)
        logger.info(f"Found {len(files)} files")
        return files

    def export_file(self, cc_path: str, dest_path: str) -> bool:
        """
        Export a specific file version from ClearCase to dest_path.
        Creates the destination directory if it does not exist.
        Returns True on success.
        """
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        try:
            self._run(["get", "-to", dest_path, cc_path])
            return True
        except ClearCaseError as e:
            logger.warning(f"Failed to export {cc_path}: {e}")
            return False

    def get_labels(self) -> List[str]:
        """
        Return a list of ClearCase labels/baselines attached to the VOB.
        """
        logger.info("Fetching ClearCase labels")
        try:
            raw = self._run(["lstype", "-kind", "lbtype", "-short", f"vob:{self.vob_path}"])
            return [line.strip() for line in raw.splitlines() if line.strip()]
        except ClearCaseError:
            logger.warning("Could not retrieve labels — skipping")
            return []

    def get_file_metadata(self, cc_path: str) -> dict:
        """
        Return metadata (author, timestamp) for a given file path.
        Returns empty dict if metadata cannot be retrieved.
        """
        try:
            raw = self._run(["describe", "-fmt", "%u|%d", cc_path])
            parts = raw.strip().split("|")
            return {
                "author": parts[0].strip() if len(parts) > 0 else "",
                "timestamp": parts[1].strip() if len(parts) > 1 else "",
            }
        except ClearCaseError:
            return {}

    def set_baseline(self, baseline: str):
        """Set the config spec to a specific baseline/label."""
        logger.info(f"Setting config spec to baseline: {baseline}")
        config_spec = f"element * {baseline}\n"
        # Write config spec to a temp file and apply
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cs", delete=False) as tf:
            tf.write(config_spec)
            tf_path = tf.name
        try:
            self._run(["setcs", tf_path])
        finally:
            os.unlink(tf_path)

    # ── Internal helpers ───────────────────────────────────────────────

    def _verify_cleartool(self):
        """Confirm cleartool is available on PATH."""
        try:
            result = subprocess.run(
                ["cleartool", "-version"],
                capture_output=True, text=True, timeout=10
            )
            logger.debug(f"cleartool version: {result.stdout.strip()}")
        except FileNotFoundError:
            raise ClearCaseError(
                "cleartool not found. Ensure ClearCase client is installed "
                "and cleartool is on your PATH."
            )

    def _run(self, args: List[str], timeout: int = 120) -> str:
        """
        Run a cleartool command and return stdout.
        Raises ClearCaseError on non-zero exit or timeout.
        """
        cmd = ["cleartool"] + args
        logger.debug(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.view_path or None,
            )
            if result.returncode != 0:
                raise ClearCaseError(
                    f"cleartool error (rc={result.returncode}): {result.stderr.strip()}"
                )
            return result.stdout
        except subprocess.TimeoutExpired:
            raise ClearCaseError(f"cleartool command timed out: {' '.join(args)}")
