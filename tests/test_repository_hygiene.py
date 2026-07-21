"""Repository-hygiene regression test (remediation of the validated-and-fixed
test-suite pollution finding).

A prior validation pass discovered that several packages' tests, when run
from the repository root, silently wrote real files into the repository's
``data/`` and ``reports/`` trees, and into a repository-root
``backtest_result.json`` -- via production-code relative default output
paths (``coin_discovery_pipeline``, ``run_orchestrator``, ``final_audit_pack``,
``portfolio_construction``, ``controlled_universe_export_adapter``) and a
subprocess boundary that did not set ``cwd`` (``research_backtest_comparison``).
Both the producing tests and the subprocess boundary were fixed.

This test proves the fix and guards against regression: it snapshots the
repository's ``data/``/``reports/`` file listing and root-level file listing
(names only -- content under ``data/``/``reports/`` is never read), re-runs
the previously-offending test packages as an isolated subprocess, and asserts
the snapshots are unchanged afterward.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

# The packages whose tests were found, during the validation pass, to write
# into forbidden repository paths when run from the repository root.
_PREVIOUSLY_OFFENDING_TEST_PATHS = (
    "tests/test_coin_discovery_pipeline",
    "tests/test_run_orchestrator",
    "tests/test_final_audit_pack",
    "tests/test_controlled_universe_export_adapter",
    "tests/test_portfolio_construction",
    "tests/test_research_backtest_comparison",
)


def _snapshot_forbidden_and_root_paths() -> tuple[frozenset[str], frozenset[str]]:
    """Return (data/reports file paths, root-level file names) -- names only.

    Never reads file contents. If data/ or reports/ do not exist, treats
    them as having no files (they are pre-existing, opaque local artifact
    areas that may or may not be present in a given checkout).
    """
    forbidden_paths: set[str] = set()
    for forbidden_root in ("data", "reports"):
        root = _REPO_ROOT / forbidden_root
        if root.is_dir():
            for f in root.rglob("*"):
                if f.is_file():
                    forbidden_paths.add(str(f.relative_to(_REPO_ROOT)))
    root_files = {
        p.name
        for p in _REPO_ROOT.iterdir()
        if p.is_file()
    }
    return frozenset(forbidden_paths), frozenset(root_files)


def test_previously_offending_suites_do_not_pollute_repository() -> None:
    """Re-running the fixed suites from the repo root must create zero new
    paths under data/, reports/, or the repository root."""
    before_forbidden, before_root = _snapshot_forbidden_and_root_paths()

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *_PREVIOUSLY_OFFENDING_TEST_PATHS],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        shell=False,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, (
        f"affected suites failed to run cleanly:\n"
        f"stdout: {result.stdout[-4000:]}\nstderr: {result.stderr[-4000:]}"
    )

    after_forbidden, after_root = _snapshot_forbidden_and_root_paths()

    new_forbidden_paths = after_forbidden - before_forbidden
    new_root_files = after_root - before_root

    assert not new_forbidden_paths, (
        "re-running previously-offending suites created new paths under "
        f"data/ or reports/: {sorted(new_forbidden_paths)}"
    )
    assert not new_root_files, (
        "re-running previously-offending suites created new repository-root "
        f"files: {sorted(new_root_files)}"
    )


def test_research_backtest_comparison_subprocess_boundary_sets_cwd() -> None:
    """The sole subprocess boundary (MVP-65) must run the child process with
    cwd pinned to the ephemeral workspace, so any relative-path behavior in
    the child (real freqtrade or a test double) cannot escape into the
    caller's cwd -- this is the source-level fix for the backtest_result.json
    repository-root pollution finding."""
    runner_source = (
        _REPO_ROOT / "src" / "hunter" / "research_backtest_comparison" / "runner.py"
    ).read_text(encoding="utf-8")
    assert "cwd=str(workspace.path)" in runner_source, (
        "research_backtest_comparison/runner.py must pin the backtest "
        "subprocess's cwd to the isolated workspace path"
    )
