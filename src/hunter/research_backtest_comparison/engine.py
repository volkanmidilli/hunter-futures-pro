"""Top-level orchestrator for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

from datetime import datetime, timezone

from hunter.research_backtest_comparison.comparison import compare_backtest_results
from hunter.research_backtest_comparison.config_builder import write_freqtrade_config
from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonConfigError,
    ResearchBacktestComparisonValidationError,
)
from hunter.research_backtest_comparison.executable import (
    validate_executable,
    verify_executable_supports_backtesting,
)
from hunter.research_backtest_comparison.fairness import build_fairness_manifest, verify_fairness
from hunter.research_backtest_comparison.fingerprint import (
    comparison_fingerprint_from_result,
    config_fingerprint,
    data_fingerprint,
    fairness_fingerprint,
    pairlist_fingerprint,
    report_fingerprint,
    run_result_fingerprint,
    safety_flags_fingerprint,
    strategy_fingerprint,
)
from hunter.research_backtest_comparison.models import (
    RESEARCH_BACKTEST_COMPARISON_VERSION,
    SPEC_VERSION,
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
    BacktestComparisonManifest,
    BacktestComparisonReport,
    BacktestComparisonResult,
    BacktestFairnessManifest,
    BacktestRunResult,
    ResearchBacktestSafetyFlags,
)
from hunter.research_backtest_comparison.parser import parse_backtest_result
from hunter.research_backtest_comparison.runner import _run_single_backtest
from hunter.research_backtest_comparison.validator import validate_config, validate_pairlist
from hunter.research_backtest_comparison.workspace import BacktestWorkspace


def _run_arm_sequentially(
    config: BacktestComparisonConfig,
    arm: BacktestArmInput,
    workspace: BacktestWorkspace,
) -> BacktestRunResult:
    """Run a single backtest arm in the provided workspace."""
    return _run_single_backtest(config, arm, workspace)


def _validate_inputs(
    config: BacktestComparisonConfig | None,
    candidate: BacktestArmInput | None,
    baseline: BacktestArmInput | None,
) -> None:
    """Structural validation of required inputs."""
    if config is None:
        raise ResearchBacktestComparisonConfigError("config is required")
    validate_config(config)
    validate_pairlist(candidate)
    validate_pairlist(baseline)
    if candidate is not None and candidate.label != BacktestArmLabel.CANDIDATE:
        raise ResearchBacktestComparisonValidationError(
            "candidate arm must have label CANDIDATE"
        )
    if baseline is not None and baseline.label != BacktestArmLabel.BASELINE:
        raise ResearchBacktestComparisonValidationError(
            "baseline arm must have label BASELINE"
        )


def _build_workspace(
    arm: BacktestArmInput,
    config: BacktestComparisonConfig,
) -> BacktestWorkspace:
    """Create an ephemeral workspace and write the Freqtrade config for the arm."""
    workspace = BacktestWorkspace(
        prefix=f"hunter_backtest_{arm.label.value.lower()}_",
        retain_on_failure=config.retain_workspace_on_failure,
    )
    workspace.create()
    write_freqtrade_config(config, arm, workspace)
    return workspace


def _parse_and_enrich(
    result: BacktestRunResult,
) -> BacktestRunResult:
    """Parse the result file and return a new run result with populated metrics."""
    if result.result_file is None or not result.result_file.exists():
        return result
    metrics = parse_backtest_result(result.result_file)
    return BacktestRunResult(
        label=result.label,
        success=result.success,
        metrics=metrics,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        workspace=result.workspace,
        result_file=result.result_file,
        command=result.command,
        command_fingerprint=result.command_fingerprint,
        strategy_sha_before=result.strategy_sha_before,
        strategy_sha_after=result.strategy_sha_after,
        fingerprint=run_result_fingerprint(result),
        reason_codes=result.reason_codes,
        metadata=result.metadata,
    )


def run_research_backtest_comparison(
    *,
    config: BacktestComparisonConfig,
    candidate: BacktestArmInput,
    baseline: BacktestArmInput,
) -> BacktestComparisonReport:
    """Orchestrate the full research backtest comparison.

    Validates inputs, checks fairness, builds workspaces, runs candidate and baseline
    sequentially, parses results, compares metrics, and produces a deterministic report.

    Raises:
        ResearchBacktestComparisonConfigError: on invalid configuration.
        ResearchBacktestComparisonValidationError: on validation failure.
        ResearchBacktestComparisonExecutableError: on executable validation failure.
        ResearchBacktestComparisonFairnessError: on fairness violation.
        ResearchBacktestComparisonRunnerError: on runner failure.
    """
    _validate_inputs(config, candidate, baseline)

    executable_info = validate_executable(config.executable_path)
    verify_executable_supports_backtesting(executable_info)

    fairness = build_fairness_manifest(config, candidate, baseline)
    verify_fairness(fairness)

    candidate_workspace = _build_workspace(candidate, config)
    baseline_workspace = _build_workspace(baseline, config)

    success = False
    try:
        candidate_result = _run_arm_sequentially(config, candidate, candidate_workspace)
        baseline_result = _run_arm_sequentially(config, baseline, baseline_workspace)

        # Parse result files if runs succeeded.
        candidate_result = _parse_and_enrich(candidate_result)
        baseline_result = _parse_and_enrich(baseline_result)

        comparison = compare_backtest_results(candidate_result, baseline_result)

        safety_flags = ResearchBacktestSafetyFlags()

        manifest = BacktestComparisonManifest(
            version=RESEARCH_BACKTEST_COMPARISON_VERSION,
            spec_version=SPEC_VERSION,
            research_backtest_comparison_version=RESEARCH_BACKTEST_COMPARISON_VERSION,
            generated_at=datetime.now(timezone.utc),
            config_fingerprint=config_fingerprint(config),
            strategy_fingerprint=strategy_fingerprint(config.strategy_path),
            candidate_pairlist_fingerprint=pairlist_fingerprint(candidate),
            baseline_pairlist_fingerprint=pairlist_fingerprint(baseline),
            candidate_result_fingerprint=run_result_fingerprint(candidate_result),
            baseline_result_fingerprint=run_result_fingerprint(baseline_result),
            comparison_fingerprint=comparison.comparison_fingerprint,
            safety_flags=safety_flags,
            reason_codes=comparison.reason_codes,
            metadata={
                "executable_version": executable_info.version,
                "data_fingerprint": data_fingerprint(config.data_path),
            },
        )

        report_payload = {
            "version": manifest.version,
            "spec_version": manifest.spec_version,
            "research_backtest_comparison_version": manifest.research_backtest_comparison_version,
            "config": config,
            "manifest": manifest,
            "candidate": candidate_result,
            "baseline": baseline_result,
            "comparison": comparison,
            "fairness": fairness,
            "safety_flags": safety_flags,
            "metadata": {
                "generated_at": manifest.generated_at.isoformat(),
                "executable_version": executable_info.version,
            },
        }
        fingerprint_payload = {
            "version": manifest.version,
            "spec_version": manifest.spec_version,
            "research_backtest_comparison_version": manifest.research_backtest_comparison_version,
            "config_fingerprint": manifest.config_fingerprint,
            "strategy_fingerprint": manifest.strategy_fingerprint,
            "candidate_pairlist_fingerprint": manifest.candidate_pairlist_fingerprint,
            "baseline_pairlist_fingerprint": manifest.baseline_pairlist_fingerprint,
            "candidate_result_fingerprint": run_result_fingerprint(candidate_result),
            "baseline_result_fingerprint": run_result_fingerprint(baseline_result),
            "comparison_fingerprint": comparison_fingerprint_from_result(comparison),
            "fairness_fingerprint": fairness_fingerprint(fairness),
            "safety_flags_fingerprint": safety_flags_fingerprint(safety_flags),
        }
        fingerprint = report_fingerprint(fingerprint_payload)

        report = BacktestComparisonReport(
            version=manifest.version,
            spec_version=manifest.spec_version,
            research_backtest_comparison_version=manifest.research_backtest_comparison_version,
            config=config,
            manifest=manifest,
            candidate=candidate_result,
            baseline=baseline_result,
            comparison=comparison,
            fairness=fairness,
            safety_flags=safety_flags,
            fingerprint=fingerprint,
            human_approval_required=True,
            research_only=True,
            reason_codes=comparison.reason_codes,
            metadata=report_payload["metadata"],
        )
        success = True
        return report
    finally:
        if success or not config.retain_workspace_on_failure:
            candidate_workspace.cleanup(force=True)
            baseline_workspace.cleanup(force=True)


# Public alias.
build_backtest_comparison_report = run_research_backtest_comparison
