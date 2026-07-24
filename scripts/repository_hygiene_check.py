#!/usr/bin/env python3
"""Repository hygiene checker.

Default mode inspects tracked and staged paths only. ``--tree REF`` checks
every path in the tree of a commit, and ``--pre-push`` reads git pre-push
hook refs from stdin and checks the tree of every ref about to be pushed —
blocking the push when development-environment or runtime-artifact paths
would land on the remote.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Iterable

# Approved fixtures that are allowed to be tracked despite matching a general
# forbidden pattern. Keep this list small and explicit.
ALLOWED_EXACT_PATHS: frozenset[str] = frozenset({
    "examples/hunter-pairs.json",
    ".env.example",
    ".env.template",
    ".env.sample",
})

# Forbidden directory prefixes. Must match from the repository root.
FORBIDDEN_ROOT_DIRS: tuple[str, ...] = (
    ".ai/",
    ".dev/",
    ".local-workspace/",
    ".reviews/",
    ".prompts/",
    ".scratch/",
    ".wrongstack/",
    "data/",
    "logs/",
    "reports/",
)

# Forbidden path components anywhere in the path (e.g. nested __pycache__).
FORBIDDEN_PATH_COMPONENTS: tuple[str, ...] = (
    "__pycache__",
    ".venv",
    ".pytest_cache",
    ".claude",
    ".vscode",
    ".idea",
)

# Forbidden OS-generated basenames anywhere in the tree.
FORBIDDEN_BASENAMES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db"})

#: Git's all-zero object id, used to detect ref deletions in pre-push input.
ZERO_SHA = "0" * 40

# Forbidden exact file paths (from the repository root).
FORBIDDEN_EXACT_FILES: frozenset[str] = frozenset({
    "backtest_result.json",
    "configs/local.yaml",
})

# Forbidden filename suffixes. Suffix checks are exact to avoid vague keyword
# matches (e.g. "secret" inside a filename).
FORBIDDEN_SUFFIXES: tuple[str, ...] = (
    ".db",
    ".key",
    ".pem",
    ".secret",
    ".sqlite",
    ".sqlite3",
)

# Forbidden environment override patterns. Exception list above is honored.
_ENV_FORBIDDEN_RE = re.compile(r"^\.env\.[\w\-]+$")

# Forbidden generated pairlist pattern. Exception list above is honored.
_PAIRLIST_FORBIDDEN_RE = re.compile(r"^hunter-pairs[\w\-]*\.json$")


def _git_tracked_paths() -> list[str]:
    """Return paths currently tracked by Git."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _git_staged_paths() -> list[str]:
    """Return paths currently staged but not yet tracked."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _is_forbidden(path: str) -> str | None:
    """Return a violation reason if the path is forbidden, otherwise None."""
    if path in ALLOWED_EXACT_PATHS:
        return None

    for prefix in FORBIDDEN_ROOT_DIRS:
        if path.startswith(prefix) or path == prefix.rstrip("/"):
            return f"forbidden root directory: {prefix}"

    parts = path.split("/")
    for component in FORBIDDEN_PATH_COMPONENTS:
        if component in parts:
            return f"forbidden path component: {component}"

    if parts[-1] in FORBIDDEN_BASENAMES:
        return f"forbidden OS artifact: {parts[-1]}"

    if path in FORBIDDEN_EXACT_FILES:
        return "forbidden runtime artifact"

    for suffix in FORBIDDEN_SUFFIXES:
        if path.endswith(suffix):
            return f"forbidden suffix: {suffix}"

    if _ENV_FORBIDDEN_RE.match(path):
        return "forbidden environment override file"

    if _PAIRLIST_FORBIDDEN_RE.match(path):
        return "forbidden generated pairlist"

    return None


def _check_paths(paths: Iterable[str], label: str) -> list[tuple[str, str]]:
    """Check a collection of paths and return violations with their source label."""
    violations: list[tuple[str, str]] = []
    for path in sorted(set(paths)):
        reason = _is_forbidden(path)
        if reason:
            violations.append((label, path, reason))
    return violations


def forbidden_reason(path: str) -> str | None:
    """Public wrapper: return a violation reason if the path is forbidden."""
    return _is_forbidden(path)


def _git_tree_paths(ref: str) -> list[str]:
    """Return every path in the tree of the given git ref."""
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def check_ref_tree(ref: str) -> list[tuple[str, str, str]]:
    """Check every path in the tree of *ref*; return violations."""
    return _check_paths(_git_tree_paths(ref), f"tree:{ref}")


def parse_pre_push_refs(stdin_text: str) -> list[tuple[str, str, str, str]]:
    """Parse pre-push stdin into (local_ref, local_sha, remote_ref, remote_sha).

    Lines whose local sha is the zero SHA are ref deletions and are skipped —
    deleting a ref pushes no content.
    """
    refs: list[tuple[str, str, str, str]] = []
    for line in stdin_text.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        local_ref, local_sha, remote_ref, remote_sha = parts
        if local_sha == ZERO_SHA:
            continue
        refs.append((local_ref, local_sha, remote_ref, remote_sha))
    return refs


def check_pre_push(stdin_text: str) -> list[tuple[str, str, str]]:
    """Check the tree of every ref about to be pushed.

    Returns violations as ``(local_ref, path, reason)`` tuples. A forbidden
    path anywhere in a pushed tree blocks the push.
    """
    violations: list[tuple[str, str, str]] = []
    for local_ref, local_sha, _remote_ref, _remote_sha in parse_pre_push_refs(stdin_text):
        for _label, path, reason in _check_paths(_git_tree_paths(local_sha), local_ref):
            violations.append((local_ref, path, reason))
    return violations


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Repository hygiene checker: blocks development-environment and "
            "runtime-artifact paths from being tracked, staged, or pushed."
        )
    )
    parser.add_argument(
        "--tree",
        metavar="REF",
        help="Check every path in the tree of the given git ref.",
    )
    parser.add_argument(
        "--pre-push",
        action="store_true",
        help="Read git pre-push refs from stdin and check each pushed tree.",
    )
    return parser


def _report(violations: list[tuple[str, str, str]], *, fail_header: str) -> int:
    if not violations:
        print("HYGIENE_OK: no forbidden paths found")
        return 0
    print(fail_header)
    for source, path, reason in violations:
        print(f"  [{source}] {path}: {reason}")
    print(f"\nTotal violations: {len(violations)}")
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run the hygiene check and return the exit status."""
    args = _build_parser().parse_args(
        list(sys.argv[1:] if argv is None else argv)
    )

    if args.pre_push:
        try:
            violations = check_pre_push(sys.stdin.read())
        except subprocess.CalledProcessError as exc:
            print(f"HYGIENE_ERROR: failed to read git trees: {exc}", file=sys.stderr)
            return 2
        return _report(
            violations,
            fail_header="HYGIENE_FAIL: push blocked — forbidden paths in pushed tree",
        )

    if args.tree is not None:
        try:
            violations = check_ref_tree(args.tree)
        except subprocess.CalledProcessError as exc:
            print(f"HYGIENE_ERROR: failed to read git tree: {exc}", file=sys.stderr)
            return 2
        return _report(
            violations,
            fail_header="HYGIENE_FAIL: forbidden paths in tree",
        )

    try:
        tracked = _git_tracked_paths()
        staged = _git_staged_paths()
    except subprocess.CalledProcessError as exc:
        print(f"HYGIENE_ERROR: failed to read git paths: {exc}", file=sys.stderr)
        return 2

    violations = _check_paths(tracked, "tracked")
    violations.extend(_check_paths(staged, "staged"))

    if not violations:
        print("HYGIENE_OK: tracked and staged paths are clean")
        return 0

    print("HYGIENE_FAIL: forbidden tracked or staged paths found")
    for source, path, reason in violations:
        print(f"  [{source}] {path}: {reason}")
    print(f"\nTotal violations: {len(violations)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
