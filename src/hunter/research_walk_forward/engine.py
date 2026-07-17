"""Top-level orchestrator for the walk-forward experiment harness (MVP-66 / SPEC-067)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from hunter.research_backtest_comparison import (
    BacktestComparisonReport,
    run_research_backtest_comparison,
)
from hunter.research_walk_forward.aggregation import aggregate_metrics
from hunter.research_walk_forward.fingerprint import (
    manifest_fingerprint,
    overall_aggregate_fingerprint,
    plan_fingerprint,
    regime_aggregate_fingerprint,
    regime_overall_fingerprint,
    report_fingerprint,
    safety_flags_fingerprint,
    window_result_fingerprint,
)
from hunter.research_walk_forward.leakage import validate_no_leakage
from hunter.research_walk_forward.models import (
    SAFETY_INVARIANT_VIOLATION,
    WALK_FORWARD_VERSION,
    SPEC_VERSION,
    ConsistencyState,
    ExperimentExecutionPolicy,
    MarketRegimeLabel,
    RegimeAggregate,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WalkForwardManifest,
    WalkForwardSafetyFlags,
    WalkForwardWindowResult,
)
from hunter.research_walk_forward.regime import build_regime_aggregate, group_results_by_regime
from hunter.research_walk_forward.runner import run_walk_forward_windows
from hunter.research_walk_forward.validator import validate_plan


_MANDATORY_NOTICE = (
    "This artifact is research-only and is based on historical walk-forward backtesting.\n"
    "Past performance does not guarantee future results.\n"
    "Window consistency, regime summaries, and metric deltas are descriptive evidence only.\n"
    "They do not authorize execution, production deployment, live trading,\n"
    "automatic execution, order placement, signal generation,\n"
    "strategy mutation, universe mutation, or position changes.\n"
    "Human review remains required."
)


def _validate_safety_flags(safety_flags: WalkForwardSafetyFlags) -> None:
    """Ensure safety flags match the mandatory invariants."""
    if (
        safety_flags.research_only is not True
        or safety_flags.execution_approval_granted is not False
        or safety_flags.production_approval_granted is not False
        or safety_flags.live_trading_allowed is not False
        or safety_flags.automatic_execution_allowed is not False
        or safety_flags.human_approval_required is not True
    ):
        raise ValueError(
            "Safety invariant violation: research-only flags are mandatory",
        ) from None


def run_walk_forward_experiment(
    plan: WalkForwardExperimentPlan,
    candidate_pairlist: tuple[str, ...],
    baseline_pairlist: tuple[str, ...],
    candidate_universe_fingerprint: str,
    baseline_universe_fingerprint: str,
    execution_policy: ExperimentExecutionPolicy = ExperimentExecutionPolicy.COLLECT_ALL,
    run_backtest_fn: Callable[..., BacktestComparisonReport] = run_research_backtest_comparison,
) -> WalkForwardExperimentReport:
    """Orchestrate a full walk-forward experiment.

    Validates the plan, enforces leakage rules, runs windows sequentially, aggregates
    metrics, groups by regime, and produces a deterministic report.
    """
    validate_plan(plan)
    validate_no_leakage(plan.windows)
    _validate_safety_flags(plan.safety_flags)

    plan_with_fingerprint = WalkForwardExperimentPlan(
        mode=plan.mode,
        windows=plan.windows,
        common=plan.common,
        contiguous=plan.contiguous,
        safety_flags=plan.safety_flags,
        fingerprint=plan_fingerprint(plan),
        reason_codes=plan.reason_codes,
        metadata=plan.metadata,
    )

    window_results = run_walk_forward_windows(
        plan=plan_with_fingerprint,
        candidate_pairlist=candidate_pairlist,
        baseline_pairlist=baseline_pairlist,
        candidate_universe_fingerprint=candidate_universe_fingerprint,
        baseline_universe_fingerprint=baseline_universe_fingerprint,
        execution_policy=execution_policy,
        run_backtest_fn=run_backtest_fn,
    )

    # Recompute fingerprints for window results now that the plan fingerprint is known.
    window_results_with_fp: list[WalkForwardWindowResult] = []
    for window in window_results:
        window_results_with_fp.append(
            WalkForwardWindowResult(
                window=window.window,
                window_index=window.window_index,
                status=window.status,
                candidate_metrics=window.candidate_metrics,
                baseline_metrics=window.baseline_metrics,
                metric_deltas=window.metric_deltas,
                metric_directions=window.metric_directions,
                comparison_fingerprint=window.comparison_fingerprint,
                candidate_fingerprint=window.candidate_fingerprint,
                baseline_fingerprint=window.baseline_fingerprint,
                fingerprint=window_result_fingerprint(window),
                reason_codes=window.reason_codes,
                metadata=window.metadata,
            )
        )
    window_results = tuple(window_results_with_fp)

    metric_aggregates = aggregate_metrics(window_results)
    overall_fp = overall_aggregate_fingerprint(metric_aggregates)

    regime_groups = group_results_by_regime(window_results)
    # Deterministic regime ordering by label value.
    regime_aggregates: list[RegimeAggregate] = []
    for label in sorted(regime_groups.keys(), key=lambda x: x.value):
        windows = regime_groups[label]
        # Compute metric aggregates first, then fingerprint the full regime payload.
        temp_regime = build_regime_aggregate(label, windows, fingerprint="regime-fingerprint-placeholder")
        regime_fp = regime_aggregate_fingerprint(temp_regime)
        regime_aggregates.append(
            build_regime_aggregate(label, windows, fingerprint=regime_fp)
        )
    regime_aggregates = tuple(regime_aggregates)
    regime_overall_fp = regime_overall_fingerprint(regime_aggregates)

    safety_flags = WalkForwardSafetyFlags()
    generated_at = datetime.now(timezone.utc)

    manifest = WalkForwardManifest(
        version=WALK_FORWARD_VERSION,
        spec_version=SPEC_VERSION,
        walk_forward_version=WALK_FORWARD_VERSION,
        generated_at=generated_at,
        plan_fingerprint=plan_with_fingerprint.fingerprint,
        overall_aggregate_fingerprint=overall_fp,
        regime_aggregate_fingerprint=regime_overall_fp,
        safety_flags=safety_flags,
        reason_codes=(),
        metadata={
            "safety_flags_fingerprint": safety_flags_fingerprint(safety_flags),
            "mandatory_notice": _MANDATORY_NOTICE,
        },
    )
    manifest = WalkForwardManifest(
        version=manifest.version,
        spec_version=manifest.spec_version,
        walk_forward_version=manifest.walk_forward_version,
        generated_at=manifest.generated_at,
        plan_fingerprint=manifest.plan_fingerprint,
        overall_aggregate_fingerprint=manifest.overall_aggregate_fingerprint,
        regime_aggregate_fingerprint=manifest.regime_aggregate_fingerprint,
        safety_flags=manifest.safety_flags,
        reason_codes=manifest.reason_codes,
        metadata={
            **dict(manifest.metadata),
            "manifest_fingerprint": manifest_fingerprint(manifest),
        },
    )

    report = WalkForwardExperimentReport(
        version=WALK_FORWARD_VERSION,
        spec_version=SPEC_VERSION,
        walk_forward_version=WALK_FORWARD_VERSION,
        plan=plan_with_fingerprint,
        window_results=window_results,
        metric_aggregates=metric_aggregates,
        regime_aggregates=regime_aggregates,
        manifest=manifest,
        safety_flags=safety_flags,
        fingerprint="report-fingerprint-placeholder",
        human_approval_required=True,
        research_only=True,
        reason_codes=(),
        metadata={
            "generated_at": generated_at.isoformat(),
            "mandatory_notice": _MANDATORY_NOTICE,
        },
    )
    fp = report_fingerprint(report)
    report = WalkForwardExperimentReport(
        version=report.version,
        spec_version=report.spec_version,
        walk_forward_version=report.walk_forward_version,
        plan=report.plan,
        window_results=report.window_results,
        metric_aggregates=report.metric_aggregates,
        regime_aggregates=report.regime_aggregates,
        manifest=report.manifest,
        safety_flags=report.safety_flags,
        fingerprint=fp,
        human_approval_required=report.human_approval_required,
        research_only=report.research_only,
        reason_codes=report.reason_codes,
        metadata=report.metadata,
    )
    return report


# Public alias.
build_walk_forward_report = run_walk_forward_experiment
