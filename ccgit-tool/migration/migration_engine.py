"""
Migration Engine
----------------
Orchestrates the full ClearCase → Git migration pipeline.

Pipeline stages:
  1. Validate config
  2. Connect to ClearCase, optionally set baseline
  3. List all VOB files
  4. Export files to temp staging area
  5. Copy staged files into Git working tree
  6. Write .gitignore
  7. Stage and commit
  8. Optionally create Git tags from CC labels
  9. Run validation
  10. Save report

All operations are logged. Dry-run mode skips all writes.
"""

import os
import shutil
import logging
import tempfile
import json
from datetime import datetime
from typing import Optional

from migration.clearcase_adapter import ClearCaseAdapter, ClearCaseError
from migration.git_adapter import GitAdapter, GitError
from migration.metadata_parser import MetadataParser
from migration.validator import Validator

logger = logging.getLogger(__name__)


class MigrationEngine:
    def __init__(self, config: dict):
        self.config = config
        self.migration_cfg = config.get("migration", {})
        self.dry_run = self.migration_cfg.get("dry_run", False)
        self.preserve_tags = self.migration_cfg.get("preserve_tags", False)
        self.run_validation = self.migration_cfg.get("validate", True)
        self.repo_name = self.migration_cfg.get("repo_name", "migrated_repo")
        self.baseline = config.get("clearcase", {}).get("baseline", None)

        self._setup_logging()

    def run(self) -> dict:
        """
        Execute the full migration pipeline.
        Returns a result dict with status, counts, paths, and any errors.
        """
        result = {
            "success": False,
            "repo_name": self.repo_name,
            "baseline": self.baseline or "latest",
            "dry_run": self.dry_run,
            "files_migrated": 0,
            "files_skipped": 0,
            "warnings": 0,
            "errors": [],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "log_path": self.log_path,
            "report_path": None,
            "output_path": None,
            "validation": None,
        }

        try:
            logger.info("=" * 60)
            logger.info(f"CCGit Migration Started")
            logger.info(f"  Repo     : {self.repo_name}")
            logger.info(f"  Baseline : {self.baseline or 'latest snapshot'}")
            logger.info(f"  Dry Run  : {self.dry_run}")
            logger.info("=" * 60)

            # ── Stage 1: Init adapters ──────────────────────────────
            logger.info("[1/7] Initialising ClearCase adapter...")
            cc = ClearCaseAdapter(self.config)

            if self.baseline:
                logger.info(f"[1/7] Setting baseline: {self.baseline}")
                if not self.dry_run:
                    cc.set_baseline(self.baseline)

            # ── Stage 2: List files ─────────────────────────────────
            logger.info("[2/7] Listing files in VOB...")
            cc_files = cc.list_files()
            logger.info(f"[2/7] Found {len(cc_files)} files to migrate")

            # ── Stage 3: Init Git repo ──────────────────────────────
            logger.info("[3/7] Initialising Git repository...")
            git = GitAdapter(self.config)

            if not self.dry_run:
                repo_path = git.init_repo(self.repo_name)
                git.write_gitignore()
                result["output_path"] = repo_path
            else:
                logger.info("[DRY RUN] Skipping Git repo creation")
                result["output_path"] = "(dry run - no output written)"

            # ── Stage 4: Export and copy files ─────────────────────
            logger.info("[4/7] Exporting files from ClearCase...")
            metadata_parser = MetadataParser(self.config)
            vob_path = self.config.get("clearcase", {}).get("vob_path", "")
            migrated = 0
            skipped = 0

            with tempfile.TemporaryDirectory() as staging:
                for cc_path in cc_files:
                    rel_path = self._relative_path(cc_path, vob_path)
                    staging_dest = os.path.join(staging, rel_path)

                    if not self.dry_run:
                        success = cc.export_file(cc_path, staging_dest)
                        if success:
                            final_dest = os.path.join(repo_path, rel_path)
                            os.makedirs(os.path.dirname(final_dest), exist_ok=True)
                            shutil.copy2(staging_dest, final_dest)
                            migrated += 1
                        else:
                            skipped += 1
                            result["warnings"] += 1
                            logger.warning(f"SKIP: {cc_path}")
                    else:
                        logger.debug(f"[DRY RUN] Would migrate: {rel_path}")
                        migrated += 1

            result["files_migrated"] = migrated
            result["files_skipped"] = skipped
            logger.info(f"[4/7] Migrated: {migrated}  Skipped: {skipped}")

            # ── Stage 5: Commit ─────────────────────────────────────
            logger.info("[5/7] Committing to Git...")
            if not self.dry_run:
                commit_msg = (
                    f"chore: migrate from ClearCase\n\n"
                    f"Repository : {self.repo_name}\n"
                    f"Baseline   : {self.baseline or 'latest snapshot'}\n"
                    f"Files      : {migrated}\n"
                    f"Tool       : CCGit v1.0 (EMS Apps, SCE)"
                )
                git.stage_all()
                git.commit(message=commit_msg)
            else:
                logger.info("[DRY RUN] Skipping commit")

            # ── Stage 6: Tags ───────────────────────────────────────
            if self.preserve_tags:
                logger.info("[6/7] Creating Git tags from ClearCase labels...")
                labels = cc.get_labels()
                if not self.dry_run:
                    for label in labels:
                        git.create_tag(label)
                logger.info(f"[6/7] Processed {len(labels)} label(s)")
            else:
                logger.info("[6/7] Tag preservation skipped (not requested)")

            # ── Stage 7: Validation ─────────────────────────────────
            if self.run_validation and not self.dry_run:
                logger.info("[7/7] Running validation...")
                validator = Validator(self.config)
                val_result = validator.validate(
                    cc_files=cc_files,
                    git_repo_path=repo_path,
                    git_file_count=git.count_files(),
                )
                result["validation"] = val_result
                logger.info(
                    f"[7/7] Validation {'PASSED' if val_result['passed'] else 'FAILED'} "
                    f"— CC: {val_result['cc_count']}, Git: {val_result['git_count']}, "
                    f"Missing: {val_result['missing']}"
                )
            else:
                logger.info("[7/7] Validation skipped")

            result["success"] = True
            logger.info("Migration completed successfully.")

        except ClearCaseError as e:
            msg = f"ClearCase error: {e}"
            logger.error(msg)
            result["errors"].append(msg)
        except GitError as e:
            msg = f"Git error: {e}"
            logger.error(msg)
            result["errors"].append(msg)
        except Exception as e:
            msg = f"Unexpected error: {e}"
            logger.exception(msg)
            result["errors"].append(msg)
        finally:
            report_path = self._save_report(result)
            result["report_path"] = report_path
            logger.info(f"Report saved: {report_path}")

        return result

    # ── Helpers ───────────────────────────────────────────────────────

    def _relative_path(self, cc_path: str, vob_path: str) -> str:
        """Strip the VOB root from a ClearCase file path."""
        cc_path = cc_path.split("@@")[0]
        if vob_path and cc_path.startswith(vob_path):
            rel = cc_path[len(vob_path):]
            return rel.lstrip("/\\")
        return os.path.basename(cc_path)

    def _setup_logging(self):
        """Configure file + console logging for this migration run."""
        logs_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "logs"
        )
        os.makedirs(logs_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(logs_dir, f"migration_{self.repo_name}_{ts}.log")

        file_handler = logging.FileHandler(self.log_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        if not root.handlers:
            root.addHandler(file_handler)
            root.addHandler(console_handler)
        else:
            root.addHandler(file_handler)

    def _save_report(self, result: dict) -> str:
        """Save the migration result as a JSON report file."""
        reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "reports"
        )
        os.makedirs(reports_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(
            reports_dir, f"report_{self.repo_name}_{ts}.json"
        )
        with open(report_path, "w") as f:
            json.dump(result, f, indent=2)
        return report_path
