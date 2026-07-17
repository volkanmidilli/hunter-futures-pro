"""Replication analysis for the research evidence ledger (MVP-68 / SPEC-069)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from hunter.research_evidence_ledger.fingerprint import replication_fingerprint
from hunter.research_evidence_ledger.models import (
    EvidenceLedgerEntry,
    EvidenceLedgerReplicationError,
    IndependenceClass,
    MetricDirection,
    ReplicationResult,
    ReplicationState,
    REPLICATION_INSUFFICIENT,
)


def _get_metric_direction(
    entry: EvidenceLedgerEntry,
    metric_name: str,
) -> MetricDirection | None:
    """Extract the metric direction from a ledger entry's evidence.

    Returns None if the direction cannot be determined.
    """
    if entry.evidence is None or entry.evidence.walk_forward_report is None:
        return None

    wf_report = entry.evidence.walk_forward_report
    if metric_name in wf_report.metric_aggregates:
        return wf_report.metric_aggregates[metric_name].consistency_state.value  # type: ignore[return-value]
    return None


def _classify_replication_state(
    candidate_count: int,
    baseline_count: int,
    independent_count: int,
    min_independent: int,
) -> ReplicationState:
    """Classify the replication state based on direction counts."""
    if independent_count < min_independent:
        return ReplicationState.INSUFFICIENT_EVIDENCE

    total = candidate_count + baseline_count
    if total == 0:
        return ReplicationState.NOT_REPLICATED

    # If most show candidate advantage
    if candidate_count >= total * 0.75 and candidate_count >= 2:
        return ReplicationState.REPLICATED_CANDIDATE
    if baseline_count >= total * 0.75 and baseline_count >= 2:
        return ReplicationState.REPLICATED_BASELINE

    # If both directions exist and neither dominates
    if candidate_count > 0 and baseline_count > 0:
        return ReplicationState.CONFLICTING

    # Some evidence but not enough
    if total < 2:
        return ReplicationState.PARTIALLY_REPLICATED

    return ReplicationState.INSUFFICIENT_EVIDENCE


def analyze_replication(
    entries: tuple[EvidenceLedgerEntry, ...],
    family_id: str,
    family_type: str,
    metric_name: str,
    min_independent: int = 1,
) -> list[ReplicationResult]:
    """Analyze replication for a specific metric within a family.

    Only considers experiments with IndependenceClass.INDEPENDENT
    by default.

    Args:
        entries: Ledger entries to analyze.
        family_id: The family ID for grouping.
        family_type: The family type (hypothesis/experiment/metric).
        metric_name: The metric name to analyze.
        min_independent: Minimum number of independent experiments required.

    Returns:
        List of ReplicationResult instances (one per experiment with evidence).
    """
    results: list[ReplicationResult] = []

    # Filter to experiments with evidence for this metric
    relevant_entries = [
        e for e in entries
        if e.evidence is not None
        and e.evidence.walk_forward_report is not None
        and metric_name in e.evidence.walk_forward_report.metric_aggregates
    ]

    if not relevant_entries:
        return results

    # Count independent experiments
    independent_entries = [
        e for e in relevant_entries
        if e.registration.independence == IndependenceClass.INDEPENDENT
    ]
    independent_count = len(independent_entries)

    # Count directions across all independent entries
    candidate_count = 0
    baseline_count = 0

    for entry in independent_entries:
        direction_code = _get_metric_direction(entry, metric_name)
        if direction_code is not None:
            direction_str = str(direction_code)
            if "CANDIDATE" in direction_str.upper() and "HIGHER" in direction_str.upper():
                candidate_count += 1
            elif "BASELINE" in direction_str.upper() and "HIGHER" in direction_str.upper():
                baseline_count += 1

    state = _classify_replication_state(
        candidate_count=candidate_count,
        baseline_count=baseline_count,
        independent_count=independent_count,
        min_independent=min_independent,
    )

    # Determine direction state
    direction: MetricDirection | None = None
    if state == ReplicationState.REPLICATED_CANDIDATE:
        direction = MetricDirection.CANDIDATE_HIGHER
    elif state == ReplicationState.REPLICATED_BASELINE:
        direction = MetricDirection.BASELINE_HIGHER
    elif state == ReplicationState.NOT_REPLICATED:
        if candidate_count > baseline_count:
            direction = MetricDirection.CANDIDATE_HIGHER
        elif baseline_count > candidate_count:
            direction = MetricDirection.BASELINE_HIGHER
        else:
            direction = MetricDirection.EQUAL

    # Create one result per experiment
    for entry in relevant_entries:
        result = ReplicationResult(
            experiment_id=entry.registration.experiment_id,
            metric_name=metric_name,
            family_id=family_id,
            family_type=family_type,
            state=state,
            candidate_count=candidate_count,
            baseline_count=baseline_count,
            independent_count=independent_count,
            direction=direction,
        )
        fp = replication_fingerprint(result)
        object.__setattr__(result, "fingerprint", fp)
        results.append(result)

    return results


def analyze_all_replications(
    entries: tuple[EvidenceLedgerEntry, ...],
    hypothesis_family_ids: dict[str, str],
    experiment_family_ids: dict[str, str],
    metric_names: tuple[str, ...],
    min_independent: int = 1,
) -> tuple[ReplicationResult, ...]:
    """Analyze replication for all metric/family combinations."""
    all_results: list[ReplicationResult] = []

    for metric_name in metric_names:
        # Analyze per hypothesis family
        for hypothesis, fam_id in hypothesis_family_ids.items():
            family_entries = tuple(
                e for e in entries
                if e.registration.hypothesis_family_id == fam_id
                or e.registration.hypothesis == hypothesis
            )
            if family_entries:
                results = analyze_replication(
                    entries=family_entries,
                    family_id=fam_id,
                    family_type="hypothesis",
                    metric_name=metric_name,
                    min_independent=min_independent,
                )
                all_results.extend(results)

        # Analyze per experiment family
        for strategy_key, fam_id in experiment_family_ids.items():
            family_entries = tuple(
                e for e in entries
                if e.registration.experiment_family_id == fam_id
            )
            if family_entries:
                results = analyze_replication(
                    entries=family_entries,
                    family_id=fam_id,
                    family_type="experiment",
                    metric_name=metric_name,
                    min_independent=min_independent,
                )
                all_results.extend(results)

    return tuple(all_results)
