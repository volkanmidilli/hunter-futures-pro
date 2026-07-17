"""Deterministic SHA-256 fingerprints for statistical confidence (MVP-67 / SPEC-068)."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from enum import Enum
from typing import Any

from hunter.research_statistical_confidence.models import (
    UNAVAILABLE,
    BootstrapConfig,
    BootstrapInterval,
    ConfidenceState,
    ExperimentConfidenceReport,
    LeaveOneOutResult,
    MetricConfidenceResult,
    RegimeConfidenceResult,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
    StatisticalConfidenceManifest,
    StatisticalConfidenceSafetyFlags,
)
from hunter.research_walk_forward.models import MetricDirection


def _serialize_value(value: Any) -> Any:
    """Serialize a value into a deterministic JSON-safe structure."""
    if value is None:
        return UNAVAILABLE
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if isinstance(value, bool):
        return value
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, BootstrapInterval):
        return {
            "lower": str(value.lower),
            "upper": str(value.upper),
            "confidence_level": str(value.confidence_level),
        }
    if isinstance(value, LeaveOneOutResult):
        return {
            "mean_range": str(value.mean_range),
            "median_range": str(value.median_range),
            "max_influence_window_index": value.max_influence_window_index,
            "max_influence_ratio": str(value.max_influence_ratio),
            "directions": [d.value for d in value.directions],
            "sign_stable": value.sign_stable,
            "reason_codes": sorted(value.reason_codes),
        }
    if isinstance(value, MetricConfidenceResult):
        return {
            "metric_name": value.metric_name,
            "available_count": value.available_count,
            "unavailable_count": value.unavailable_count,
            "mean": _serialize_value(value.mean),
            "median": _serialize_value(value.median),
            "std_dev": _serialize_value(value.std_dev),
            "mad": _serialize_value(value.mad),
            "min": _serialize_value(value.min),
            "max": _serialize_value(value.max),
            "q1": _serialize_value(value.q1),
            "q3": _serialize_value(value.q3),
            "iqr": _serialize_value(value.iqr),
            "positive_share": str(value.positive_share),
            "negative_share": str(value.negative_share),
            "zero_share": str(value.zero_share),
            "bootstrap_mean_ci": _serialize_value(value.bootstrap_mean_ci) if value.bootstrap_mean_ci else UNAVAILABLE,
            "bootstrap_median_ci": _serialize_value(value.bootstrap_median_ci) if value.bootstrap_median_ci else UNAVAILABLE,
            "loo": _serialize_value(value.loo) if value.loo else UNAVAILABLE,
            "confidence_state": value.confidence_state.value,
            "reason_codes": sorted(value.reason_codes),
        }
    if isinstance(value, RegimeConfidenceResult):
        return {
            "regime_label": value.regime_label.value,
            "available_count": value.available_count,
            "metric_results": {
                name: _serialize_value(mr)
                for name, mr in sorted(value.metric_results.items())
            },
            "status_counts": dict(sorted(value.status_counts.items())),
            "reason_codes": sorted(value.reason_codes),
        }
    return str(value)


def _hash_payload(payload: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 hash of a JSON payload."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def config_fingerprint(config: StatisticalConfidenceConfig) -> str:
    """Return a deterministic fingerprint of the statistical confidence config."""
    payload = {
        "minimum_available_window_count": config.minimum_available_window_count,
        "confidence_level": str(config.confidence_level),
        "bootstrap": {
            "seed": config.bootstrap.seed,
            "iterations": config.bootstrap.iterations,
        },
        "robustness": {
            "sign_share_threshold": str(config.robustness.sign_share_threshold),
            "maximum_influence_ratio": str(config.robustness.maximum_influence_ratio),
            "confidence_level": str(config.robustness.confidence_level),
        },
    }
    return _hash_payload(payload)


def metric_results_fingerprint(
    metric_results: dict[str, MetricConfidenceResult],
) -> str:
    """Return a deterministic fingerprint of all metric confidence results."""
    payload = {
        "metric_results": {
            name: _serialize_value(mr)
            for name, mr in sorted(metric_results.items())
        },
    }
    return _hash_payload(payload)


def regime_results_fingerprint(
    regime_results: dict[str, RegimeConfidenceResult],
) -> str:
    """Return a deterministic fingerprint of all regime confidence results."""
    payload = {
        "regime_results": {
            name: _serialize_value(rr)
            for name, rr in sorted(regime_results.items())
        },
    }
    return _hash_payload(payload)


def safety_flags_fingerprint(flags: StatisticalConfidenceSafetyFlags) -> str:
    """Return a deterministic fingerprint of safety flags."""
    payload = {
        "research_only": flags.research_only,
        "execution_approval_granted": flags.execution_approval_granted,
        "production_approval_granted": flags.production_approval_granted,
        "live_trading_allowed": flags.live_trading_allowed,
        "automatic_execution_allowed": flags.automatic_execution_allowed,
        "human_approval_required": flags.human_approval_required,
        "no_direct_subprocess": flags.no_direct_subprocess,
        "no_parallel_execution": flags.no_parallel_execution,
        "no_network_connection": flags.no_network_connection,
        "no_database_connection": flags.no_database_connection,
        "no_exchange_connection": flags.no_exchange_connection,
        "no_remote_changes": flags.no_remote_changes,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
    }
    return _hash_payload(payload)


def manifest_fingerprint(manifest: StatisticalConfidenceManifest) -> str:
    """Return a deterministic fingerprint of the manifest."""
    payload = {
        "version": manifest.version,
        "spec_version": manifest.spec_version,
        "statistical_confidence_version": manifest.statistical_confidence_version,
        "config_fingerprint": manifest.config_fingerprint,
        "metric_results_fingerprint": manifest.metric_results_fingerprint,
        "regime_results_fingerprint": manifest.regime_results_fingerprint,
        "overall_fingerprint": manifest.overall_fingerprint,
    }
    return _hash_payload(payload)


def report_fingerprint(report: ExperimentConfidenceReport) -> str:
    """Return a deterministic fingerprint of the confidence report.

    Excludes generated_at, paths, PID, hostname, timestamps, durations,
    and insertion order.
    """
    sorted_regime_results: dict[str, Any] = {}
    for regime_name, rr in sorted(report.regime_results.items()):
        sorted_regime_results[regime_name] = _serialize_value(rr)

    payload = {
        "version": report.version,
        "spec_version": report.spec_version,
        "statistical_confidence_version": report.statistical_confidence_version,
        "source_report_fingerprint": report.source_report_fingerprint,
        "config_fingerprint": config_fingerprint(report.config),
        "metric_results_fingerprint": metric_results_fingerprint(report.metric_results),
        "regime_results_fingerprint": regime_results_fingerprint(report.regime_results),
        "research_only": report.research_only,
        "human_approval_required": report.human_approval_required,
        "reason_codes": sorted(report.reason_codes),
    }
    return _hash_payload(payload)
