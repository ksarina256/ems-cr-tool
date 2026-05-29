#!/usr/bin/env python3
"""
CCGit Tool - ClearCase to Git Migration Utility
EMS Apps | Southern California Edison

Entry point for both CLI and Flask web UI.

Usage:
    Web UI:   python run.py --web
    CLI:      python run.py --repo <repo_name> [options]
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_cli(args):
    from migration.migration_engine import MigrationEngine
    from migration.validator import Validator
    import yaml

    config_path = args.config or "configs/config.yaml"

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"[ERROR] Config file not found: {config_path}")
        sys.exit(1)

    if args.repo:
        config.setdefault("migration", {})["repo_name"] = args.repo
    if args.baseline:
        config.setdefault("clearcase", {})["baseline"] = args.baseline
    if args.dry_run:
        config.setdefault("migration", {})["dry_run"] = True
    if args.preserve_tags:
        config.setdefault("migration", {})["preserve_tags"] = True
    if args.validate:
        config.setdefault("migration", {})["validate"] = True

    engine = MigrationEngine(config)
    result = engine.run()

    if result.get("success"):
        print(f"\n[SUCCESS] Migration complete.")
        print(f"  Files migrated : {result.get('files_migrated', 0)}")
        print(f"  Warnings       : {result.get('warnings', 0)}")
        print(f"  Log            : {result.get('log_path', 'N/A')}")
        print(f"  Report         : {result.get('report_path', 'N/A')}")
    else:
        print(f"\n[FAILED] Migration failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


def run_web():
    from app import create_app
    app = create_app()
    print("[INFO] Starting CCGit web UI at http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)


def main():
    parser = argparse.ArgumentParser(
        description="CCGit Tool - ClearCase to Git Migration Utility"
    )

    parser.add_argument("--web", action="store_true", help="Launch the Flask web UI")
    parser.add_argument("--repo", type=str, help="ClearCase repository/VOB name")
    parser.add_argument("--baseline", type=str, help="Baseline or label to export (e.g. REL_1)")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without writing files")
    parser.add_argument("--validate", action="store_true", help="Run validation after migration")
    parser.add_argument("--preserve-tags", action="store_true", help="Convert CC labels to Git tags")
    parser.add_argument("--config", type=str, help="Path to config YAML (default: configs/config.yaml)")

    args = parser.parse_args()

    if args.web:
        run_web()
    elif args.repo:
        run_cli(args)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python run.py --web")
        print("  python run.py --repo billing_app")
        print("  python run.py --repo billing_app --baseline REL_1 --dry-run --validate")


if __name__ == "__main__":
    main()
