"""Top-level orchestrator for statistical confidence evaluation (MVP-67 / SPEC-068)."""

from __future__ import annotations

import hashlib
import json as _json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from hunter.research_statistical_confidence.bootstrap import (
    compute_bootstrap_confidence_intervals,
)
from hunter.research_statistical_confidence.classification import (
    classify_metric_confidence,
)
from hunter.research_statistical_confidence.descriptive import (
    compute_metric_descriptive,
)
from hunter.research_statistical_confidence.fingerprint import (
    config_fingerprint,
    manifest_fingerprint,
    metric_results_fingerprint,
    regime_results_fingerprint,
    report_fingerprint,
    safety_flags_fingerprint,
)
from hunter.research_statistical_confidence.models import (
    INSUFFICIENT_DATA,
    SPEC_VERSION,
    STATISTICAL_CONFIDENCE_VERSION,
    BootstrapInterval,
    ConfidenceState,
    ExperimentConfidenceReport,
    LeaveOneOutResult,
    MetricConfidenceResult,
    RegimeConfidenceResult,
    StatisticalConfidenceConfig,
    StatisticalConfidenceManifest,
    StatisticalConfidenceSafetyFlags,
)
from hunter.research_statistical_confidence.regime import (
    compute_regime_results,
)
from hunter.research_statistical_confidence.sensitivity import (
    compute_leave_one_out,
)
from hunter.research_statistical_confidence.validator import (
    validate_config,
    validate_source_report,
)
from hunter.research_walk_forward.models import (
    WalkForwardExperimentReport,
    WalkForwardWindowResult,
    WindowStatus,
)


def _get_window_indices(
    windows: tuple[WalkForwardWindowResult, ...],
) -> list[int]:
    """Return the config-level window indices for the given windows."""
    return [w.window_index for w in windows]


_MANDATORY_NOTICE = (
    "This artifact is research-only and summarizes statistical stability "
    "of historical walk-forward comparisons.\n"
    "Bootstrap intervals, sensitivity results, regime summaries, "
    "and confidence classifications are descriptive research evidence only. "
    "They do not prove profitability and do not authorize execution, "
    "production deployment, live trading, automatic execution, "
    "strategy selection, universe selection, order placement, "
    "signal generation, strategy mutation, universe mutation, "
    "or position changes.\n"
    "Human review remains required."
)


def run_statistical_confidence(
    report: WalkForwardExperimentReport,
    config: StatisticalConfidenceConfig,
) -> ExperimentConfidenceReport:
    """Evaluate statistical confidence for a completed walk-forward experiment.

    Args:
        report: Immutable WalkForwardExperimentReport from MVP-66.
        config: Statistical confidence evaluation configuration.

    Returns:
        ExperimentConfidenceReport with all statistical confidence results.
    """
    # Validate inputs
    validate_config(config)
    validate_source_report(report)

    # Collect all metric names from window results
    all_metric_names: set[str] = set()
    for w in report.window_results:
        all_metric_names.update(w.metric_deltas.keys())
    sorted_metric_names = sorted(all_metric_names)

    # We need the world-level window indices for leave-one-out
    world_window_indices = _get_window_indices(report.window_results)

    # Compute per-metric results across ALL windows (world-level)
    metric_results: dict[str, MetricConfidenceResult] = {}
    for metric_name in sorted_metric_names:
        # Collect deltas from all windows (available and unavailable)
        deltas: list[Decimal | None] = []
        for w in report.window_results:
            deltas.append(w.metric_deltas.get(metric_name))

        desc = compute_metric_descriptive(deltas)

        # Bootstrap
        mean_ci, median_ci = compute_bootstrap_confidence_intervals(deltas, config)

        # Leave-one-out at world level
        loo = compute_leave_one_out(
            deltas,
            config_window_indices=world_window_indices,
            maximum_influence_ratio=config.robustness.maximum_influence_ratio,
        )

        # Stage 7 / SPEC-072: detect zero observed dispersion and
        # insufficient distinct values to block ROBUST_* classification
        # when the bootstrap CI is a non-zero point.
        available_count_for_policy = desc["available_count"]
        if available_count_for_policy > 0:
            distinct_count = len({d for d in deltas if d is not None})
            zero_observed_dispersion = (
                desc["std_dev"] is not None
                and desc["std_dev"] == Decimal("0")
            )
            insufficient_distinct_values = (
                distinct_count < config.bootstrap.min_distinct_values_for_bootstrap
            )
        else:
            zero_observed_dispersion = False
            insufficient_distinct_values = False

        # Classification
        confidence_state, cls_reason_codes = classify_metric_confidence(
            available_count=desc["available_count"],
            positive_share=desc["positive_share"],
            negative_share=desc["negative_share"],
            loo=loo,
            mean_ci=mean_ci,
            median_ci=median_ci,
            config=config,
            zero_observed_dispersion=zero_observed_dispersion,
            insufficient_distinct_values=insufficient_distinct_values,
        )

        reason_codes: list[str] = list(cls_reason_codes)
        if desc["available_count"] == 0:
            if INSUFFICIENT_DATA not in reason_codes:
                reason_codes.append(INSUFFICIENT_DATA)

        metric_result = MetricConfidenceResult(
            metric_name=metric_name,
            available_count=desc["available_count"],
            unavailable_count=desc["unavailable_count"],
            mean=desc["mean"],
            median=desc["median"],
            std_dev=desc["std_dev"],
            mad=desc["mad"],
            min=desc["min"],
            max=desc["max"],
            q1=desc["q1"],
            q3=desc["q3"],
            iqr=desc["iqr"],
            positive_share=desc["positive_share"],
            negative_share=desc["negative_share"],
            zero_share=desc["zero_share"],
            bootstrap_mean_ci=mean_ci,
            bootstrap_median_ci=median_ci,
            loo=loo,
            confidence_state=confidence_state,
            reason_codes=tuple(reason_codes),
        )
        metric_results[metric_name] = metric_result

    # Compute regime-stratified results
    regime_results = compute_regime_results(report, config)

    # Compute fingerprints
    config_fp = config_fingerprint(config)
    metric_results_fp = metric_results_fingerprint(metric_results)
    regime_results_fp = regime_results_fingerprint(regime_results)

    # Build fingerprints for each RegimeConfidenceResult
    from hunter.research_statistical_confidence.fingerprint import _serialize_value as _fp_serialize

    for regime_name, rr in regime_results.items():
        regime_payload = _fp_serialize(rr)
        regime_fp_text = _json.dumps(regime_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        regime_fp = hashlib.sha256(regime_fp_text.encode("utf-8")).hexdigest()
        regime_results[regime_name] = RegimeConfidenceResult(
            regime_label=rr.regime_label,
            available_count=rr.available_count,
            metric_results=rr.metric_results,
            status_counts=rr.status_counts,
            fingerprint=regime_fp,
            reason_codes=rr.reason_codes,
        )

    # Recompute regime fingerprint now that individual regime fingerprints are set
    regime_results_fp = regime_results_fingerprint(regime_results)

    # Combined overall fingerprint
    overall_payload = {
        "config_fingerprint": config_fp,
        "metric_results_fingerprint": metric_results_fp,
        "regime_results_fingerprint": regime_results_fp,
    }
    overall_fp = hashlib.sha256(
        _json.dumps(overall_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    safety_flags = StatisticalConfidenceSafetyFlags()
    generated_at = datetime.now(timezone.utc)

    # Build manifest
    manifest = StatisticalConfidenceManifest(
        version=STATISTICAL_CONFIDENCE_VERSION,
        spec_version=SPEC_VERSION,
        statistical_confidence_version=STATISTICAL_CONFIDENCE_VERSION,
        generated_at=generated_at,
        config_fingerprint=config_fp,
        metric_results_fingerprint=metric_results_fp,
        regime_results_fingerprint=regime_results_fp,
        overall_fingerprint=overall_fp,
        safety_flags=safety_flags,
        reason_codes=(),
    )

    manifest_with_fp = StatisticalConfidenceManifest(
        version=manifest.version,
        spec_version=manifest.spec_version,
        statistical_confidence_version=manifest.statistical_confidence_version,
        generated_at=manifest.generated_at,
        config_fingerprint=manifest.config_fingerprint,
        metric_results_fingerprint=manifest.metric_results_fingerprint,
        regime_results_fingerprint=manifest.regime_results_fingerprint,
        overall_fingerprint=manifest.overall_fingerprint,
        safety_flags=manifest.safety_flags,
        reason_codes=manifest.reason_codes,
    )

    # Build preliminary report for fingerprinting
    report_obj = ExperimentConfidenceReport(
        version=STATISTICAL_CONFIDENCE_VERSION,
        spec_version=SPEC_VERSION,
        statistical_confidence_version=STATISTICAL_CONFIDENCE_VERSION,
        source_report_fingerprint=report.fingerprint,
        config=config,
        metric_results=metric_results,
        regime_results=regime_results,
        manifest=manifest_with_fp,
        safety_flags=safety_flags,
        fingerprint="placeholder",
        human_approval_required=True,
        research_only=True,
        reason_codes=(),
        metadata={
            "generated_at": generated_at.isoformat(),
            "mandatory_notice": _MANDATORY_NOTICE,
        },
    )

    fp = report_fingerprint(report_obj)
    final_report = ExperimentConfidenceReport(
        version=report_obj.version,
        spec_version=report_obj.spec_version,
        statistical_confidence_version=report_obj.statistical_confidence_version,
        source_report_fingerprint=report_obj.source_report_fingerprint,
        config=report_obj.config,
        metric_results=report_obj.metric_results,
        regime_results=report_obj.regime_results,
        manifest=report_obj.manifest,
        safety_flags=report_obj.safety_flags,
        fingerprint=fp,
        human_approval_required=report_obj.human_approval_required,
        research_only=report_obj.research_only,
        reason_codes=report_obj.reason_codes,
        metadata=report_obj.metadata,
    )

    return final_report
