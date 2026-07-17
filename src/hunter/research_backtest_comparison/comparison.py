"""Paired metric comparison for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from hunter.research_backtest_comparison.models import (
    INSUFFICIENT_TRADES,
    MISSING_METRIC,
    UNAVAILABLE,
    BacktestComparisonResult,
    BacktestMetrics,
    BacktestRunResult,
    MetricInterpretation,
)


# Minimum trades considered sufficient evidence for comparison.
_MIN_TRADES_FOR_SUFFICIENCY = 1

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
    "avg_trade_duration",
    "fees_paid",
)


def _interpret_delta(
    name: str,
    delta: Decimal | None,
    candidate: Decimal | None,
    baseline: Decimal | None,
) -> MetricInterpretation:
    """Return a descriptive interpretation of a metric delta."""
    if delta is None or candidate is None or baseline is None:
        return MetricInterpretation.UNAVAILABLE
    if name == "max_drawdown_pct":
        # Lower drawdown is better; interpretation is still numeric delta.
        if delta == 0:
            return MetricInterpretation.EQUAL
        if delta > 0:
            return MetricInterpretation.CANDIDATE_HIGHER
        return MetricInterpretation.BASELINE_HIGHER
    if delta == 0:
        return MetricInterpretation.EQUAL
    if delta > 0:
        return MetricInterpretation.CANDIDATE_HIGHER
    return MetricInterpretation.BASELINE_HIGHER


def compare_backtest_metrics(
    candidate: BacktestMetrics,
    baseline: BacktestMetrics,
) -> tuple[dict[str, Decimal | None], dict[str, MetricInterpretation]]:
    """Compute paired deltas and interpretations.

    Deltas are candidate - baseline. Missing metrics produce UNAVAILABLE.
    """
    deltas: dict[str, Decimal | None] = {}
    interpretations: dict[str, MetricInterpretation] = {}
    for name in _CANONICAL_METRIC_NAMES:
        c_value = getattr(candidate, name)
        b_value = getattr(baseline, name)
        if c_value is None or b_value is None:
            deltas[name] = None
            interpretations[name] = MetricInterpretation.UNAVAILABLE
        else:
            deltas[name] = c_value - b_value
            interpretations[name] = _interpret_delta(name, deltas[name], c_value, b_value)
    return deltas, interpretations


def _comparison_fingerprint_payload(
    candidate: BacktestMetrics,
    baseline: BacktestMetrics,
    deltas: dict[str, Decimal | None],
    interpretations: dict[str, MetricInterpretation],
    trade_sufficiency: bool,
) -> dict[str, object]:
    """Return a deterministic payload for the comparison fingerprint."""
    def serialize(value: object) -> object:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, MetricInterpretation):
            return value.value
        return value

    return {
        "candidate": {name: serialize(getattr(candidate, name)) for name in _CANONICAL_METRIC_NAMES},
        "baseline": {name: serialize(getattr(baseline, name)) for name in _CANONICAL_METRIC_NAMES},
        "deltas": {name: serialize(deltas[name]) for name in _CANONICAL_METRIC_NAMES},
        "interpretations": {name: interpretations[name].value for name in _CANONICAL_METRIC_NAMES},
        "trade_sufficiency": trade_sufficiency,
    }


def comparison_fingerprint(
    candidate: BacktestMetrics,
    baseline: BacktestMetrics,
    deltas: dict[str, Decimal | None],
    interpretations: dict[str, MetricInterpretation],
    trade_sufficiency: bool,
) -> str:
    """Return a deterministic SHA-256 fingerprint of the comparison."""
    payload = _comparison_fingerprint_payload(
        candidate, baseline, deltas, interpretations, trade_sufficiency
    )
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compare_backtest_results(
    candidate: BacktestRunResult,
    baseline: BacktestRunResult,
) -> BacktestComparisonResult:
    """Compare candidate and baseline backtest results.

    Zero-trade results are valid but marked as insufficient evidence.
    """
    deltas, interpretations = compare_backtest_metrics(candidate.metrics, baseline.metrics)
    trade_sufficiency = (
        candidate.metrics.trade_count >= _MIN_TRADES_FOR_SUFFICIENCY
        and baseline.metrics.trade_count >= _MIN_TRADES_FOR_SUFFICIENCY
    )
    reason_codes: list[str] = []
    if not trade_sufficiency:
        reason_codes.append(INSUFFICIENT_TRADES)
    if any(v is None for v in deltas.values()):
        reason_codes.append(MISSING_METRIC)

    fingerprint = comparison_fingerprint(
        candidate.metrics,
        baseline.metrics,
        deltas,
        interpretations,
        trade_sufficiency,
    )

    return BacktestComparisonResult(
        candidate=candidate,
        baseline=baseline,
        metric_deltas=deltas,
        interpretations=interpretations,
        comparison_fingerprint=fingerprint,
        trade_sufficiency=trade_sufficiency,
        reason_codes=tuple(reason_codes),
    )
