"""Sequential backtest runner for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from hunter.research_backtest_comparison.command_builder import (
    build_backtest_command,
    command_fingerprint,
)
from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonRunnerError,
)
from hunter.research_backtest_comparison.models import (
    NONZERO_EXIT,
    SECRET_IN_ENV,
    STRATEGY_MUTATION_DETECTED,
    TIMEOUT,
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
    BacktestMetrics,
    BacktestRunResult,
)
from hunter.research_backtest_comparison.redaction import redact_text
from hunter.research_backtest_comparison.result_locator import locate_latest_backtest_result
from hunter.research_backtest_comparison.validator import validate_pairlist
from hunter.research_backtest_comparison.workspace import BacktestWorkspace


# Default environment allowlist.
_DEFAULT_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "TZ",
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "LC_ALL",
        "PYTHONNOUSERSITE",
        "PYTHONPATH",
        "TERM",
        "COLORTERM",
    }
)

# Environment keys that look like secrets and must be stripped.
_SECRET_PATTERNS: tuple[str, ...] = (
    "API_KEY",
    "API_SECRET",
    "SECRET",
    "PASSWORD",
    "TOKEN",
    "PRIVATE_KEY",
    "ACCESS_KEY",
    "ACCESS_SECRET",
)

# Output bounds.
_MAX_OUTPUT_BYTES: int = 2 * 1024 * 1024  # 2 MiB


def _file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_env(
    config: BacktestComparisonConfig,
) -> dict[str, str]:
    """Return a filtered environment dict for the subprocess."""
    allowlist = config.env_allowlist
    if allowlist is None:
        allowlist = _DEFAULT_ENV_ALLOWLIST
    source = dict(config.extra_env or {})
    # Start with a minimal clean environment.
    filtered: dict[str, str] = {"TZ": "UTC"}
    for key, value in source.items():
        if key in allowlist and not any(p in key.upper() for p in _SECRET_PATTERNS):
            filtered[key] = value
    # Also pull from os.environ only allowed keys.
    import os

    for key, value in os.environ.items():
        if key in allowlist and key not in filtered and not any(p in key.upper() for p in _SECRET_PATTERNS):
            filtered[key] = value
    filtered["TZ"] = "UTC"
    # Defensive: if a secret-like key slipped through, strip it.
    for key in list(filtered.keys()):
        if any(p in key.upper() for p in _SECRET_PATTERNS):
            del filtered[key]
    return filtered


def _run_single_backtest(
    config: BacktestComparisonConfig,
    arm: BacktestArmInput,
    workspace: BacktestWorkspace,
) -> BacktestRunResult:
    """Run one backtest arm and return the result.

    No retries, no parallel subprocesses, bounded and redacted output.
    """
    validate_pairlist(arm)

    strategy_sha_before = _file_sha256(config.strategy_path)

    args = build_backtest_command(config, workspace)
    cmd_fingerprint = command_fingerprint(args)

    env = _build_env(config)
    # Detect secret leakage into env.
    reason_codes: list[str] = []
    for key in env:
        if any(p in key.upper() for p in _SECRET_PATTERNS):
            reason_codes.append(SECRET_IN_ENV)

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            shell=False,
            timeout=config.timeout_seconds,
            env=env,
            check=False,
            cwd=str(workspace.path),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = redact_text((exc.stdout or "")[:_MAX_OUTPUT_BYTES])
        stderr = redact_text((exc.stderr or "")[:_MAX_OUTPUT_BYTES])
        workspace_path = workspace.path
        if not workspace.retain_on_failure:
            workspace.cleanup(force=True)
        return BacktestRunResult(
            label=arm.label,
            success=False,
            metrics=BacktestMetrics(reason_codes=(TIMEOUT,)),
            stdout=stdout,
            stderr=stderr,
            exit_code=-1,
            workspace=workspace_path,
            result_file=None,
            command=tuple(args),
            command_fingerprint=cmd_fingerprint,
            strategy_sha_before=strategy_sha_before,
            strategy_sha_after=strategy_sha_before,
            fingerprint=cmd_fingerprint,
            reason_codes=(TIMEOUT,),
        )
    except OSError as exc:
        workspace_path = workspace.path
        if not workspace.retain_on_failure:
            workspace.cleanup(force=True)
        return BacktestRunResult(
            label=arm.label,
            success=False,
            metrics=BacktestMetrics(reason_codes=("RUNNER_ERROR",)),
            stdout="",
            stderr=redact_text(str(exc)),
            exit_code=-1,
            workspace=workspace_path,
            result_file=None,
            command=tuple(args),
            command_fingerprint=cmd_fingerprint,
            strategy_sha_before=strategy_sha_before,
            strategy_sha_after=strategy_sha_before,
            fingerprint=cmd_fingerprint,
            reason_codes=("RUNNER_ERROR",),
        )

    stdout = redact_text((result.stdout or "")[:_MAX_OUTPUT_BYTES])
    stderr = redact_text((result.stderr or "")[:_MAX_OUTPUT_BYTES])

    if result.returncode != 0:
        workspace_path = workspace.path
        if not workspace.retain_on_failure:
            workspace.cleanup(force=True)
        return BacktestRunResult(
            label=arm.label,
            success=False,
            metrics=BacktestMetrics(reason_codes=(NONZERO_EXIT,)),
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            workspace=workspace_path,
            result_file=None,
            command=tuple(args),
            command_fingerprint=cmd_fingerprint,
            strategy_sha_before=strategy_sha_before,
            strategy_sha_after=strategy_sha_before,
            fingerprint=cmd_fingerprint,
            reason_codes=(NONZERO_EXIT,),
        )

    # Verify strategy file did not change during the run.
    strategy_sha_after = _file_sha256(config.strategy_path)
    if strategy_sha_after != strategy_sha_before:
        workspace_path = workspace.path
        if not workspace.retain_on_failure:
            workspace.cleanup(force=True)
        return BacktestRunResult(
            label=arm.label,
            success=False,
            metrics=BacktestMetrics(reason_codes=(STRATEGY_MUTATION_DETECTED,)),
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            workspace=workspace_path,
            result_file=None,
            command=tuple(args),
            command_fingerprint=cmd_fingerprint,
            strategy_sha_before=strategy_sha_before,
            strategy_sha_after=strategy_sha_after,
            fingerprint=cmd_fingerprint,
            reason_codes=(STRATEGY_MUTATION_DETECTED,),
        )

    # Locate and validate result file.
    try:
        result_file = locate_latest_backtest_result(workspace.backtest_results_dir, workspace.path)
    except Exception as exc:
        workspace_path = workspace.path
        if not workspace.retain_on_failure:
            workspace.cleanup(force=True)
        return BacktestRunResult(
            label=arm.label,
            success=False,
            metrics=BacktestMetrics(reason_codes=("RESULT_CONTAINMENT_FAILURE",)),
            stdout=stdout,
            stderr=redact_text(str(exc)),
            exit_code=result.returncode,
            workspace=workspace_path,
            result_file=None,
            command=tuple(args),
            command_fingerprint=cmd_fingerprint,
            strategy_sha_before=strategy_sha_before,
            strategy_sha_after=strategy_sha_after,
            fingerprint=cmd_fingerprint,
            reason_codes=("RESULT_CONTAINMENT_FAILURE",),
        )

    return BacktestRunResult(
        label=arm.label,
        success=True,
        metrics=BacktestMetrics(),  # placeholder; parser will populate
        stdout=stdout,
        stderr=stderr,
        exit_code=result.returncode,
        workspace=workspace.path,
        result_file=result_file,
        command=tuple(args),
        command_fingerprint=cmd_fingerprint,
        strategy_sha_before=strategy_sha_before,
        strategy_sha_after=strategy_sha_after,
        fingerprint=cmd_fingerprint,
        pairlist=arm.pairlist,
        reason_codes=tuple(reason_codes) or (),
    )


def run_backtest_arm(
    config: BacktestComparisonConfig,
    arm: BacktestArmInput,
    workspace: BacktestWorkspace | None = None,
    cleanup_on_success: bool = False,
) -> BacktestRunResult:
    """Run a single backtest arm in an isolated workspace.

    If workspace is None, a fresh workspace is created. By default the workspace
    is retained on success so the caller can parse ``result.result_file`` before
    calling ``workspace.cleanup()``. Pass ``cleanup_on_success=True`` to let the
    runner dispose of the workspace immediately after a successful run.
    """
    own_workspace = workspace is None
    if workspace is None:
        workspace = BacktestWorkspace(retain_on_failure=config.retain_workspace_on_failure)
        workspace.create()

    result: BacktestRunResult | None = None
    try:
        result = _run_single_backtest(config, arm, workspace)
        return result
    finally:
        if own_workspace and cleanup_on_success and result is not None and result.success:
            workspace.cleanup(force=True)


def run_candidate_and_baseline(
    config: BacktestComparisonConfig,
    candidate: BacktestArmInput,
    baseline: BacktestArmInput,
    *,
    cleanup_on_success: bool = False,
) -> tuple[BacktestRunResult, BacktestRunResult]:
    """Run candidate and baseline sequentially.

    Candidate runs first, then baseline. Only one subprocess is active at a time.
    Workspaces are retained on success by default so callers can parse the result
    files. Pass ``cleanup_on_success=True`` to dispose of them immediately.
    """
    candidate_result: BacktestRunResult | None = None
    baseline_result: BacktestRunResult | None = None

    candidate_workspace = BacktestWorkspace(
        prefix="hunter_backtest_candidate_",
        retain_on_failure=config.retain_workspace_on_failure,
    )
    candidate_workspace.create()
    try:
        candidate_result = _run_single_backtest(config, candidate, candidate_workspace)
    finally:
        if (
            cleanup_on_success
            and candidate_result is not None
            and candidate_result.success
            and not config.retain_workspace_on_failure
        ):
            candidate_workspace.cleanup(force=True)

    baseline_workspace = BacktestWorkspace(
        prefix="hunter_backtest_baseline_",
        retain_on_failure=config.retain_workspace_on_failure,
    )
    baseline_workspace.create()
    try:
        baseline_result = _run_single_backtest(config, baseline, baseline_workspace)
    finally:
        if (
            cleanup_on_success
            and baseline_result is not None
            and baseline_result.success
            and not config.retain_workspace_on_failure
        ):
            baseline_workspace.cleanup(force=True)

    assert candidate_result is not None
    assert baseline_result is not None
    return candidate_result, baseline_result
