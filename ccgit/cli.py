"""Command line interface for the ClearCase snapshot mirror."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable, Optional

from .config import ConfigError, ProjectConfig
from .runner import CommandError
from .snapshot import SnapshotService
from .web import run_server


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = ProjectConfig.load(args.config)
        service = SnapshotService(config)

        if args.command == "validate":
            print_json(service.validate())
            return 0

        if args.command == "snapshot":
            if args.branch == "all":
                results = service.snapshot_all(push=args.push)
                print_json({name: result.to_dict() for name, result in results.items()})
            else:
                print_json(service.snapshot(args.branch, push=args.push).to_dict())
            return 0

        if args.command == "compare":
            base = args.base or config.default_base
            target = args.target or config.default_target
            if not base or not target:
                raise ConfigError("compare requires --base and --target, or default_base/default_target in config")
            if args.write:
                print_json(service.write_compare_report(base, target))
            else:
                report = service.compare(base, target)
                print_json(report.to_dict())
            return 0

        if args.command == "web":
            run_server(config, host=args.host, port=args.port)
            return 0

        parser.print_help()
        return 2
    except (ConfigError, FileNotFoundError, ValueError, CommandError) as exc:
        print(f"ccgit: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ccgit: interrupted", file=sys.stderr)
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ccgit",
        description="Mirror ClearCase master/dev view snapshots into Git/Gitea and compare them.",
    )
    parser.add_argument("-c", "--config", help="Path to ccgit JSON config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="Validate config and show resolved paths")

    snapshot = subparsers.add_parser("snapshot", help="Refresh one configured ClearCase snapshot")
    snapshot.add_argument("branch", help="Configured branch name, or 'all'")
    snapshot.add_argument("--push", action="store_true", help="Push refreshed branch(es) to Gitea remote")

    compare = subparsers.add_parser("compare", help="Compare two Git refs or configured branch names")
    compare.add_argument("--base", help="Base branch/ref. Defaults to config.default_base")
    compare.add_argument("--target", help="Target branch/ref. Defaults to config.default_target")
    compare.add_argument("--write", action="store_true", help="Write JSON and HTML reports under .ccgit/reports")

    web = subparsers.add_parser("web", help="Run the built-in web UI")
    web.add_argument("--host", default="127.0.0.1", help="Host/interface to bind")
    web.add_argument("--port", type=int, default=8080, help="Port to bind")

    return parser


def print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
