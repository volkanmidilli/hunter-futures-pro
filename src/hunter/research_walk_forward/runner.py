"""Sequential window runner for the walk-forward harness (MVP-66 / SPEC-067)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from hunter.research_backtest_comparison import (
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
    BacktestComparisonReport,
    run_research_backtest_comparison,
)
from hunter.research_walk_forward.models import (
    INSUFFICIENT_TRADES,
    RUNNER_ERROR,
    TIMEOUT,
    WindowStatus,
    ExperimentExecutionPolicy,
    MetricDirection,
    WalkForwardExperimentPlan,
    WalkForwardWindow,
    WalkForwardWindowResult,
)
from hunter.research_walk_forward.fingerprint import window_result_fingerprint
from hunter.research_walk_forward.validator import validate_plan


_CANONICAL_METRIC_NAMES: tuple[str, ...] = (
    "total_return_pct",
    "absolute_profit",
    "final_balance",
    "max_drawdown_pct",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "profit_factor",
    "win_rate_pct",
    "trade_count",
    "average_trade_duration_seconds",
    "fees_paid",
)

_MVP65_TO_CANONICAL: dict[str, str] = {
    "total_return_pct": "total_return_pct",
    "absolute_profit": "absolute_profit",
    "final_balance": "final_balance",
    "max_drawdown_pct": "max_drawdown_pct",
    "sharpe_ratio": "sharpe_ratio",
    "sortino_ratio": "sortino_ratio",
    "calmar_ratio": "calmar_ratio",
    "profit_factor": "profit_factor",
    "win_rate_pct": "win_rate_pct",
    "trade_count": "trade_count",
    "avg_trade_duration": "average_trade_duration_seconds",
    "fees_paid": "fees_paid",
}


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _map_mvp65_metrics(metrics: Any) -> dict[str, Decimal | None]:
    result: dict[str, Decimal | None] = {}
    for mvp65_name, canonical_name in _MVP65_TO_CANONICAL.items():
        value = getattr(metrics, mvp65_name, None)
        if canonical_name == "average_trade_duration_seconds" and value is not None:
            result[canonical_name] = _to_decimal(value) * Decimal("60")
        else:
            result[canonical_name] = _to_decimal(value)
    return result


def _map_mvp65_deltas(deltas: dict[str, Decimal | None]) -> dict[str, Decimal | None]:
    result: dict[str, Decimal | None] = {}
    for mvp65_name, value in deltas.items():
        canonical_name = _MVP65_TO_CANONICAL.get(mvp65_name, mvp65_name)
        if canonical_name == "average_trade_duration_seconds" and value is not None:
            result[canonical_name] = value * Decimal("60")
        else:
            result[canonical_name] = value
    return result


def _interpret_delta(
    name: str,
    delta: Decimal | None,
    candidate: Decimal | None,
    baseline: Decimal | None,
) -> MetricDirection:
    if delta is None or candidate is None or baseline is None:
        return MetricDirection.UNAVAILABLE
    if delta == 0:
        return MetricDirection.EQUAL
    if delta > 0:
        return MetricDirection.CANDIDATE_HIGHER
    return MetricDirection.BASELINE_HIGHER


def _determine_status(comparison: BacktestComparisonReport) -> tuple[WindowStatus, tuple[str, ...]]:
    reason_codes = list(comparison.comparison.reason_codes)
    candidate_codes = list(comparison.candidate.reason_codes)
    baseline_codes = list(comparison.baseline.reason_codes)
    all_codes = reason_codes + candidate_codes + baseline_codes

    if TIMEOUT in all_codes:
        return (WindowStatus.TIMED_OUT, tuple(all_codes) or (TIMEOUT,))
    if not (comparison.candidate.success and comparison.baseline.success):
        return (WindowStatus.FAILED, tuple(all_codes) or ("WINDOW_FAILED",))
    if INSUFFICIENT_TRADES in all_codes:
        return (WindowStatus.INSUFFICIENT, tuple(all_codes) or (INSUFFICIENT_TRADES,))
    return (WindowStatus.COMPLETED, tuple(all_codes))


def _build_mvp65_config(plan: WalkForwardExperimentPlan, window: WalkForwardWindow) -> BacktestComparisonConfig:
    common = plan.common
    return BacktestComparisonConfig(
        strategy_name=common.strategy_name,
        strategy_path=common.strategy_path,
        data_path=common.data_path,
        timeframe=common.timeframe,
        timerange=f"{window.evaluation_start}-{window.evaluation_end}",
        balance=common.balance,
        stake=common.stake,
        max_open_trades=common.max_open_trades,
        fee=common.fee,
        executable_path=common.executable_path,
        timeout_seconds=common.timeout_seconds,
        protections=common.protections,
        env_allowlist=common.env_allowlist,
        extra_env=common.extra_env,
        metadata=dict(common.metadata),
    )


def _empty_window_result(
    window: WalkForwardWindow,
    window_index: int,
    status: WindowStatus,
    reason_codes: tuple[str, ...],
    metadata: dict[str, Any] | None = None,
) -> WalkForwardWindowResult:
    metadata = metadata or {}
    result = WalkForwardWindowResult(
        window=window,
        window_index=window_index,
        status=status,
        candidate_metrics={name: None for name in _CANONICAL_METRIC_NAMES},
        baseline_metrics={name: None for name in _CANONICAL_METRIC_NAMES},
        metric_deltas={name: None for name in _CANONICAL_METRIC_NAMES},
        metric_directions={name: MetricDirection.UNAVAILABLE for name in _CANONICAL_METRIC_NAMES},
        comparison_fingerprint="",
        candidate_fingerprint="",
        baseline_fingerprint="",
        fingerprint="placeholder",
        reason_codes=reason_codes,
        metadata=metadata,
    )
    return WalkForwardWindowResult(
        window=result.window,
        window_index=result.window_index,
        status=result.status,
        candidate_metrics=result.candidate_metrics,
        baseline_metrics=result.baseline_metrics,
        metric_deltas=result.metric_deltas,
        metric_directions=result.metric_directions,
        comparison_fingerprint=result.comparison_fingerprint,
        candidate_fingerprint=result.candidate_fingerprint,
        baseline_fingerprint=result.baseline_fingerprint,
        fingerprint=window_result_fingerprint(result),
        reason_codes=result.reason_codes,
        metadata=result.metadata,
    )


def run_walk_forward_window(
    plan: WalkForwardExperimentPlan,
    window: WalkForwardWindow,
    window_index: int,
    candidate_pairlist: tuple[str, ...],
    baseline_pairlist: tuple[str, ...],
    candidate_universe_fingerprint: str,
    baseline_universe_fingerprint: str,
    run_backtest_fn: Callable[..., BacktestComparisonReport] = run_research_backtest_comparison,
) -> WalkForwardWindowResult:
    """Run a single walk-forward window by calling the MVP-65 engine."""
    mvp65_config = _build_mvp65_config(plan, window)
    candidate_arm = BacktestArmInput(
        pairlist=candidate_pairlist,
        label=BacktestArmLabel.CANDIDATE,
        universe_fingerprint=candidate_universe_fingerprint,
    )
    baseline_arm = BacktestArmInput(
        pairlist=baseline_pairlist,
        label=BacktestArmLabel.BASELINE,
        universe_fingerprint=baseline_universe_fingerprint,
    )

    try:
        comparison = run_backtest_fn(
            config=mvp65_config,
            candidate=candidate_arm,
            baseline=baseline_arm,
        )
    except Exception as exc:
        return _empty_window_result(
            window=window,
            window_index=window_index,
            status=WindowStatus.FAILED,
            reason_codes=(RUNNER_ERROR,),
            metadata={"error": str(exc)},
        )

    status, reason_codes = _determine_status(comparison)
    candidate_metrics = _map_mvp65_metrics(comparison.candidate.metrics)
    baseline_metrics = _map_mvp65_metrics(comparison.baseline.metrics)
    metric_deltas = _map_mvp65_deltas(comparison.comparison.metric_deltas)

    metric_directions: dict[str, MetricDirection] = {}
    for name in _CANONICAL_METRIC_NAMES:
        delta = metric_deltas.get(name)
        cand = candidate_metrics.get(name)
        base = baseline_metrics.get(name)
        metric_directions[name] = _interpret_delta(name, delta, cand, base)

    result = WalkForwardWindowResult(
        window=window,
        window_index=window_index,
        status=status,
        candidate_metrics=candidate_metrics,
        baseline_metrics=baseline_metrics,
        metric_deltas=metric_deltas,
        metric_directions=metric_directions,
        comparison_fingerprint=comparison.comparison.comparison_fingerprint,
        candidate_fingerprint=comparison.candidate.fingerprint,
        baseline_fingerprint=comparison.baseline.fingerprint,
        fingerprint="placeholder",
        reason_codes=reason_codes,
        metadata={"timerange": mvp65_config.timerange},
    )
    return WalkForwardWindowResult(
        window=result.window,
        window_index=result.window_index,
        status=result.status,
        candidate_metrics=result.candidate_metrics,
        baseline_metrics=result.baseline_metrics,
        metric_deltas=result.metric_deltas,
        metric_directions=result.metric_directions,
        comparison_fingerprint=result.comparison_fingerprint,
        candidate_fingerprint=result.candidate_fingerprint,
        baseline_fingerprint=result.baseline_fingerprint,
        fingerprint=window_result_fingerprint(result),
        reason_codes=result.reason_codes,
        metadata=result.metadata,
    )


def run_walk_forward_windows(
    plan: WalkForwardExperimentPlan,
    candidate_pairlist: tuple[str, ...],
    baseline_pairlist: tuple[str, ...],
    candidate_universe_fingerprint: str,
    baseline_universe_fingerprint: str,
    execution_policy: ExperimentExecutionPolicy = ExperimentExecutionPolicy.COLLECT_ALL,
    run_backtest_fn: Callable[..., BacktestComparisonReport] = run_research_backtest_comparison,
) -> tuple[WalkForwardWindowResult, ...]:
    """Run windows sequentially according to the execution policy."""
    validate_plan(plan)

    results: list[WalkForwardWindowResult] = []
    for index, window in enumerate(plan.windows):
        result = run_walk_forward_window(
            plan=plan,
            window=window,
            window_index=index,
            candidate_pairlist=candidate_pairlist,
            baseline_pairlist=baseline_pairlist,
            candidate_universe_fingerprint=candidate_universe_fingerprint,
            baseline_universe_fingerprint=baseline_universe_fingerprint,
            run_backtest_fn=run_backtest_fn,
        )
        results.append(result)
        if execution_policy == ExperimentExecutionPolicy.FAIL_FAST and result.status != WindowStatus.COMPLETED:
            break

    return tuple(results)
