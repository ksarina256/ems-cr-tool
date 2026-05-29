"""
Validator
---------
Post-migration validation engine.

Compares the ClearCase source file list against the resulting
Git repository to detect missing files and count mismatches.

Optional: MD5 checksum comparison (stretch goal).
"""

import os
import hashlib
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class Validator:
    def __init__(self, config: dict):
        self.config = config
        self.enable_checksums = config.get("migration", {}).get("checksums", False)

    def validate(
        self,
        cc_files: List[str],
        git_repo_path: str,
        git_file_count: int,
    ) -> dict:
        """
        Run validation checks and return a result dict.

        Args:
            cc_files:       List of full ClearCase file paths
            git_repo_path:  Path to the migrated Git working tree
            git_file_count: Number of tracked files in the Git repo

        Returns:
            {
                "passed": bool,
                "cc_count": int,
                "git_count": int,
                "missing": int,
                "missing_files": List[str],
                "checksum_passed": bool | None
            }
        """
        logger.info("Starting validation...")

        cc_count = len(cc_files)
        result = {
            "passed": False,
            "cc_count": cc_count,
            "git_count": git_file_count,
            "missing": 0,
            "missing_files": [],
            "checksum_passed": None,
        }

        # ── File count check ────────────────────────────────────────
        missing_files = self._find_missing_files(cc_files, git_repo_path)
        result["missing"] = len(missing_files)
        result["missing_files"] = missing_files[:50]  # cap logged list

        if missing_files:
            logger.warning(f"Validation: {len(missing_files)} file(s) missing in Git repo")
            for f in missing_files[:10]:
                logger.warning(f"  MISSING: {f}")
            if len(missing_files) > 10:
                logger.warning(f"  ... and {len(missing_files) - 10} more")
        else:
            logger.info("Validation: all CC files present in Git repo")

        # ── Checksum check (optional) ───────────────────────────────
        if self.enable_checksums:
            logger.info("Running checksum validation (sample)...")
            checksum_ok = self._sample_checksum_check(cc_files, git_repo_path)
            result["checksum_passed"] = checksum_ok
            logger.info(f"Checksum validation: {'PASSED' if checksum_ok else 'FAILED'}")

        # ── Final verdict ───────────────────────────────────────────
        result["passed"] = (result["missing"] == 0)
        logger.info(
            f"Validation complete — "
            f"CC files: {cc_count}, Git files: {git_file_count}, "
            f"Missing: {result['missing']}, "
            f"Result: {'PASSED' if result['passed'] else 'FAILED'}"
        )

        return result

    # ── Internal ──────────────────────────────────────────────────────

    def _find_missing_files(self, cc_files: List[str], git_repo_path: str) -> List[str]:
        """
        Walk the CC file list and check each expected relative path
        exists in the Git working tree.
        """
        missing = []
        vob_path = self.config.get("clearcase", {}).get("vob_path", "")

        for cc_path in cc_files:
            clean = cc_path.split("@@")[0]
            rel = clean
            if vob_path and clean.startswith(vob_path):
                rel = clean[len(vob_path):].lstrip("/\\")

            expected = os.path.join(git_repo_path, rel)
            if not os.path.isfile(expected):
                missing.append(rel)

        return missing

    def _sample_checksum_check(
        self, cc_files: List[str], git_repo_path: str, sample_size: int = 20
    ) -> bool:
        """
        MD5 checksum comparison on a random sample of migrated files.
        Returns True if all sampled files match.
        NOTE: Requires cc_files to be locally accessible (not remote).
        """
        import random
        sample = random.sample(cc_files, min(sample_size, len(cc_files)))
        vob_path = self.config.get("clearcase", {}).get("vob_path", "")
        all_match = True

        for cc_path in sample:
            clean = cc_path.split("@@")[0]
            rel = clean
            if vob_path and clean.startswith(vob_path):
                rel = clean[len(vob_path):].lstrip("/\\")

            src = clean
            dst = os.path.join(git_repo_path, rel)

            if not os.path.isfile(src) or not os.path.isfile(dst):
                continue

            src_md5 = self._md5(src)
            dst_md5 = self._md5(dst)

            if src_md5 != dst_md5:
                logger.warning(f"Checksum mismatch: {rel}")
                all_match = False

        return all_match

    @staticmethod
    def _md5(filepath: str) -> str:
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
