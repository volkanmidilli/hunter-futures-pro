"""Tests for the SPEC-077 doctor engine, exit codes, and hygiene."""

from __future__ import annotations

import os
from pathlib import Path

from hunter.core.doctor.doctor import CHECK_FUNCTIONS, run_doctor
from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    compute_exit_code,
)

from .conftest import clean_worktree_responses, make_context, make_git


def _result(status: CheckStatus, check_id: str = "x.y") -> CheckResult:
    return CheckResult(
        check_id=check_id,
        category=CheckCategory.VENV,
        status=status,
        summary="s",
    )


def test_exit_code_contract() -> None:
    assert compute_exit_code([_result(CheckStatus.PASS)]) == 0
    assert compute_exit_code([_result(CheckStatus.PASS), _result(CheckStatus.SKIPPED)]) == 0
    assert compute_exit_code([_result(CheckStatus.WARNING)]) == 1
    assert compute_exit_code([_result(CheckStatus.WARNING), _result(CheckStatus.SKIPPED)]) == 1
    assert compute_exit_code([_result(CheckStatus.BLOCKER)]) == 2
    assert compute_exit_code([_result(CheckStatus.WARNING), _result(CheckStatus.BLOCKER)]) == 2
    assert compute_exit_code([_result(CheckStatus.SKIPPED)]) == 0
    assert compute_exit_code([]) == 0


def test_run_doctor_category_order_is_deterministic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    context = make_context(tmp_path, git=make_git(clean_worktree_responses()))
    report = run_doctor(context)
    categories = [result.category for result in report.results]
    order = list(CheckCategory)
    indices = [order.index(category) for category in categories]
    assert indices == sorted(indices)
    assert set(categories) == set(CheckCategory)
    assert report.exit_code == compute_exit_code(report.results)
    assert report.research_only is True
    assert report.human_approval_required is True


def test_check_functions_cover_all_nine_categories() -> None:
    assert len(CHECK_FUNCTIONS) == 9


def _tree_fingerprint(root: Path) -> dict[str, tuple[int, int]]:
    fingerprint: dict[str, tuple[int, int]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            stat = path.lstat()
            fingerprint[str(path.relative_to(root))] = (stat.st_size, stat.st_mtime_ns)
    return fingerprint


def test_doctor_run_performs_zero_filesystem_mutation(tmp_path: Path, monkeypatch) -> None:
    """Repository hygiene: a full doctor run changes nothing on disk."""
    (tmp_path / "data" / "snapshots").mkdir(parents=True)
    (tmp_path / "data" / "feather").mkdir(parents=True)
    (tmp_path / "data" / "outcome_store").mkdir(parents=True)
    (tmp_path / "data" / "feather" / "BTC_USDT_USDT-1h-futures.feather").write_bytes(b"x")
    monkeypatch.chdir(tmp_path)

    before = _tree_fingerprint(tmp_path)
    context = make_context(tmp_path, git=make_git(clean_worktree_responses()))
    run_doctor(context)
    after = _tree_fingerprint(tmp_path)

    assert before == after


def test_git_runner_rejects_mutating_subcommands(tmp_path: Path) -> None:
    """The allowlist rejects mutating subcommands and mutating flag forms."""
    import pytest

    from hunter.core.doctor.errors import DoctorError

    runner = make_git({})
    # Subcommands that are never allowed.
    for subcommand in ("fetch", "pull", "checkout", "commit", "push", "clone"):
        with pytest.raises(DoctorError):
            runner.run(subcommand)
    # Mutating forms of allowlisted subcommands.
    for args in (
        ("tag", "v9.9.9"),
        ("tag", "-d", "v0.1.0"),
        ("tag",),  # bare `git tag` lists, but only the explicit --list form is permitted
        ("branch", "-d", "feature"),
        ("branch", "new-branch"),
        ("config", "user.name", "x"),
        ("config", "--unset", "user.name"),
    ):
        with pytest.raises(DoctorError):
            runner.run(*args)


def test_git_runner_permits_read_only_flag_forms() -> None:
    """Read-only flag forms of branch/tag/config pass the allowlist."""
    from hunter.core.doctor.gitutil import GitResult

    calls = []

    def transport(argv, cwd, timeout):
        calls.append(tuple(argv[1:]))
        return GitResult(ok=True, stdout="")

    from hunter.core.doctor.gitutil import GitRunner

    runner = GitRunner(cwd=Path.cwd(), transport=transport)
    runner.run("tag", "--list")
    runner.run("branch", "--show-current")
    runner.run("branch", "--list")
    runner.run("config", "--get", "remote.origin.url")
    runner.run("rev-parse", "--is-inside-work-tree")
    runner.run("status", "--porcelain")
    runner.run("ls-remote", "--tags", "https://example.invalid/x.git")
    assert len(calls) == 7
