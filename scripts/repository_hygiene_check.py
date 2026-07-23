#!/usr/bin/env python3
"""Repository hygiene checker.

Inspects tracked and staged paths only. Does not scan arbitrary file contents,
data/, or reports/. Fails on clearly forbidden tracked/staged paths, preserves
approved fixtures, and exits non-zero when violations are found.
"""

from __future__ import annotations

import re
import subprocess
import sys
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
    "data/",
    "logs/",
    "reports/",
)

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


def main() -> int:
    """Run the hygiene check and return the exit status."""
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
