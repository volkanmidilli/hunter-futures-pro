"""Deterministic SHA-256 fingerprints for the walk-forward harness (MVP-66 / SPEC-067)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.research_walk_forward.models import (
    ConsistencyState,
    ExperimentExecutionPolicy,
    MarketRegimeLabel,
    MetricAggregate,
    RegimeAggregate,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WalkForwardManifest,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
    WalkForwardWindowResult,
    WindowStatus,
)


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


def _serialize_value(value: Any) -> Any:
    """Serialize a value into a deterministic JSON-safe structure."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone().isoformat()
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if is_dataclass(value) and not isinstance(value, type):
        return _serialize_value(value.__dict__)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _hash_payload(payload: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 hash of a JSON payload."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan_fingerprint(plan: WalkForwardExperimentPlan) -> str:
    """Return a deterministic fingerprint of the experiment plan."""
    payload = {
        "mode": plan.mode.value,
        "contiguous": plan.contiguous,
        "windows": [
            {
                "selection_start": window.selection_start,
                "selection_end": window.selection_end,
                "evaluation_start": window.evaluation_start,
                "evaluation_end": window.evaluation_end,
                "regime_label": window.regime_label.value,
            }
            for window in plan.windows
        ],
        "common": {
            "strategy_name": plan.common.strategy_name,
            "timeframe": plan.common.timeframe,
            "balance": _serialize_value(plan.common.balance),
            "stake": _serialize_value(plan.common.stake),
            "max_open_trades": plan.common.max_open_trades,
            "fee": _serialize_value(plan.common.fee),
            "protections": sorted(plan.common.protections),
            "timeout_seconds": plan.common.timeout_seconds,
        },
    }
    return _hash_payload(payload)


def window_result_fingerprint(window: WalkForwardWindowResult) -> str:
    """Return a deterministic fingerprint of a single window result.

    Excludes paths, stdout, stderr, runtime durations, and timestamps.
    """
    payload = {
        "window": {
            "selection_start": window.window.selection_start,
            "selection_end": window.window.selection_end,
            "evaluation_start": window.window.evaluation_start,
            "evaluation_end": window.window.evaluation_end,
            "regime_label": window.window.regime_label.value,
        },
        "window_index": window.window_index,
        "status": window.status.value,
        "candidate_metrics": {name: _serialize_value(window.candidate_metrics.get(name)) for name in _CANONICAL_METRIC_NAMES},
        "baseline_metrics": {name: _serialize_value(window.baseline_metrics.get(name)) for name in _CANONICAL_METRIC_NAMES},
        "metric_deltas": {name: _serialize_value(window.metric_deltas.get(name)) for name in _CANONICAL_METRIC_NAMES},
        "metric_directions": {name: _serialize_value(window.metric_directions.get(name)) for name in _CANONICAL_METRIC_NAMES},
        "comparison_fingerprint": window.comparison_fingerprint,
        "candidate_fingerprint": window.candidate_fingerprint,
        "baseline_fingerprint": window.baseline_fingerprint,
        "reason_codes": sorted(window.reason_codes),
    }
    return _hash_payload(payload)


def metric_aggregate_fingerprint(aggregate: MetricAggregate) -> str:
    """Return a deterministic fingerprint of a metric aggregate."""
    payload = {
        "metric_name": aggregate.metric_name,
        "available_count": aggregate.available_count,
        "unavailable_count": aggregate.unavailable_count,
        "candidate_higher_count": aggregate.candidate_higher_count,
        "baseline_higher_count": aggregate.baseline_higher_count,
        "equal_count": aggregate.equal_count,
        "mean": _serialize_value(aggregate.mean),
        "median": _serialize_value(aggregate.median),
        "min": _serialize_value(aggregate.min),
        "max": _serialize_value(aggregate.max),
        "q1": _serialize_value(aggregate.q1),
        "q3": _serialize_value(aggregate.q3),
        "iqr": _serialize_value(aggregate.iqr),
        "positive_delta_share": _serialize_value(aggregate.positive_delta_share),
        "negative_delta_share": _serialize_value(aggregate.negative_delta_share),
        "zero_delta_share": _serialize_value(aggregate.zero_delta_share),
        "consistency_state": aggregate.consistency_state.value,
        "reason_codes": sorted(aggregate.reason_codes),
    }
    return _hash_payload(payload)


def regime_aggregate_fingerprint(aggregate: RegimeAggregate) -> str:
    """Return a deterministic fingerprint of a regime aggregate."""
    payload = {
        "regime_label": aggregate.regime_label.value,
        "window_count": aggregate.window_count,
        "completed_count": aggregate.completed_count,
        "failed_count": aggregate.failed_count,
        "blocked_count": aggregate.blocked_count,
        "timed_out_count": aggregate.timed_out_count,
        "unsupported_count": aggregate.unsupported_count,
        "insufficient_count": aggregate.insufficient_count,
        "metric_aggregates": {
            name: metric_aggregate_fingerprint(agg)
            for name, agg in sorted(aggregate.metric_aggregates.items())
        },
    }
    return _hash_payload(payload)


def overall_aggregate_fingerprint(
    metric_aggregates: dict[str, MetricAggregate],
) -> str:
    """Return a deterministic fingerprint of the overall metric aggregates."""
    payload = {
        "metric_aggregates": {
            name: metric_aggregate_fingerprint(agg)
            for name, agg in sorted(metric_aggregates.items())
        },
    }
    return _hash_payload(payload)


def regime_overall_fingerprint(
    regime_aggregates: tuple[RegimeAggregate, ...],
) -> str:
    """Return a deterministic fingerprint of regime aggregates."""
    payload = {
        "regime_aggregates": [
            regime_aggregate_fingerprint(agg) for agg in regime_aggregates
        ],
    }
    return _hash_payload(payload)


def manifest_fingerprint(manifest: WalkForwardManifest) -> str:
    """Return a deterministic fingerprint of the manifest."""
    payload = {
        "version": manifest.version,
        "spec_version": manifest.spec_version,
        "walk_forward_version": manifest.walk_forward_version,
        "plan_fingerprint": manifest.plan_fingerprint,
        "overall_aggregate_fingerprint": manifest.overall_aggregate_fingerprint,
        "regime_aggregate_fingerprint": manifest.regime_aggregate_fingerprint,
    }
    return _hash_payload(payload)


def report_fingerprint(report: WalkForwardExperimentReport) -> str:
    """Return a deterministic fingerprint of the top-level report."""
    payload = {
        "version": report.version,
        "spec_version": report.spec_version,
        "walk_forward_version": report.walk_forward_version,
        "plan_fingerprint": report.plan.fingerprint,
        "overall_aggregate_fingerprint": overall_aggregate_fingerprint(report.metric_aggregates),
        "regime_aggregate_fingerprint": regime_overall_fingerprint(report.regime_aggregates),
        "window_result_fingerprints": [
            window_result_fingerprint(w) for w in report.window_results
        ],
    }
    return _hash_payload(payload)


def safety_flags_fingerprint(flags: WalkForwardSafetyFlags) -> str:
    """Return a deterministic fingerprint of safety flags."""
    payload = {
        "research_only": flags.research_only,
        "execution_approval_granted": flags.execution_approval_granted,
        "production_approval_granted": flags.production_approval_granted,
        "live_trading_allowed": flags.live_trading_allowed,
        "automatic_execution_allowed": flags.automatic_execution_allowed,
        "human_approval_required": flags.human_approval_required,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
        "no_network_connection": flags.no_network_connection,
        "no_database_connection": flags.no_database_connection,
        "no_exchange_connection": flags.no_exchange_connection,
        "no_remote_changes": flags.no_remote_changes,
        "no_parallel_execution": flags.no_parallel_execution,
        "no_direct_subprocess": flags.no_direct_subprocess,
        "human_research_only": flags.human_research_only,
    }
    return _hash_payload(payload)
