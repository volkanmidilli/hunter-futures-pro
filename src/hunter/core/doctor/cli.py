"""CLI for SPEC-077: ``hunter doctor`` and ``hunter update check|plan``.

Follows the existing argparse command style used by ``hunter outcome``
and ``hunter pairlist``.  All commands are strictly read-only; ``doctor``
returns the SPEC-077 exit-code contract (0 clean, 1 warnings, 2
blockers) while ``update`` commands return 0 on success and degrade
gracefully to an ``UNKNOWN`` status on remote failure.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

from hunter.core.doctor.config import (
    ConfigKey,
    find_project_root,
    resolve_config,
)
from hunter.core.doctor.doctor import run_doctor
from hunter.core.doctor.gitutil import GitRunner
from hunter.core.doctor.models import DoctorContext
from hunter.core.doctor.report import (
    render_doctor_json,
    render_doctor_text,
    render_plan_json,
    render_plan_text,
    render_update_check_json,
    render_update_check_text,
)
from hunter.core.doctor.update import (
    build_update_plan,
    collect_tags,
    resolve_target_version,
    run_update_check,
)
from hunter.core.doctor.version import current_version, filter_release_tags

DOCTOR_CLI_HELP_TEXT = """Doctor and update commands (SPEC-077, read-only):
  doctor                        Run environment health checks (exit 0/1/2).
  doctor --verbose              Also show resolved path provenance.
  update check                  Check for newer released versions (git ls-remote).
  update check --offline        Check using local tags only (no network).
  update plan                   Print a deterministic, non-executing update plan.

Run `hunter doctor --help` or `hunter update <command> --help` for full options.
"""


def _add_config_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--snapshot-dir", dest="snapshot_dir", default=None)
    parser.add_argument("--data-dir", dest="data_dir", default=None)
    parser.add_argument("--store-dir", dest="store_dir", default=None)
    parser.add_argument(
        "--pairlist-output-dir", dest="pairlist_output_dir", default=None
    )


def _build_doctor_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hunter doctor",
        description=(
            "Run read-only environment health checks. Exit codes: "
            "0 clean, 1 warnings, 2 blockers."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show each resolved path with its provenance.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a deterministic JSON report.",
    )
    _add_config_flags(parser)
    return parser


def _build_update_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hunter update",
        description=(
            "Read-only update introspection. No fetch, checkout, or pull "
            "is ever performed; `hunter update apply` does not exist."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser(
        "check", help="Check for newer released versions (read-only)."
    )
    check.add_argument(
        "--offline",
        action="store_true",
        help="Use local tags only; no network access.",
    )
    check.add_argument("--remote", default="origin", help="Remote name (default: origin).")
    check.add_argument("--json", action="store_true", help="Emit deterministic JSON.")

    plan = sub.add_parser(
        "plan", help="Print a deterministic, non-executing update plan."
    )
    plan.add_argument(
        "--target",
        default=None,
        help="Explicit target version (must be a known release tag).",
    )
    plan.add_argument(
        "--offline",
        action="store_true",
        help="Use local tags only; no network access.",
    )
    plan.add_argument("--remote", default="origin", help="Remote name (default: origin).")
    plan.add_argument("--json", action="store_true", help="Emit deterministic JSON.")
    return parser


def _cli_overrides(args: argparse.Namespace) -> dict[ConfigKey, str | None]:
    return {
        ConfigKey.SNAPSHOT_DIR: args.snapshot_dir,
        ConfigKey.DATA_DIR: args.data_dir,
        ConfigKey.STORE_DIR: args.store_dir,
        ConfigKey.PAIRLIST_OUTPUT_DIR: args.pairlist_output_dir,
    }


def doctor_main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``hunter doctor``."""
    args = _build_doctor_parser().parse_args(list(argv) if argv is not None else None)
    project_root = find_project_root()
    git = GitRunner(cwd=project_root)
    config = resolve_config(project_root, os.environ, _cli_overrides(args))
    context = DoctorContext(project_root=project_root, config=config, git=git)
    report = run_doctor(context)
    if args.json:
        print(render_doctor_json(report))
    else:
        print(render_doctor_text(report, verbose=args.verbose))
    return report.exit_code


def _update_check_command(args: argparse.Namespace, git: GitRunner) -> int:
    result = run_update_check(git, offline=args.offline, remote=args.remote)
    if args.json:
        print(render_update_check_json(result))
    else:
        print(render_update_check_text(result))
    # UNKNOWN degrades gracefully: the check itself succeeded.
    return 0


def _update_plan_command(args: argparse.Namespace, git: GitRunner) -> int:
    collection = collect_tags(git, offline=args.offline, remote=args.remote)
    if collection.error is not None:
        print(
            f"Error: cannot build an update plan: {collection.error}",
            file=sys.stderr,
        )
        return 2

    current = current_version()
    if args.target is not None:
        target, problem = resolve_target_version(args.target, collection.tags)
        if problem is not None or target is None:
            print(f"Error: {problem}", file=sys.stderr)
            return 2
    else:
        parsed = filter_release_tags(collection.tags)
        if not parsed:
            print(
                "Error: no valid release tags found; cannot determine a target.",
                file=sys.stderr,
            )
            return 2
        target = parsed[-1][1]

    plan = build_update_plan(current, target, collection.tags)
    if args.json:
        print(render_plan_json(plan))
    else:
        print(render_plan_text(plan))
    return 0


def update_main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``hunter update check|plan``."""
    args = _build_update_parser().parse_args(list(argv) if argv is not None else None)
    project_root = find_project_root()
    git = GitRunner(cwd=project_root)
    if args.command == "check":
        return _update_check_command(args, git)
    return _update_plan_command(args, git)


__all__ = ["DOCTOR_CLI_HELP_TEXT", "doctor_main", "update_main"]
