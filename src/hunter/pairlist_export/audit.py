"""Audit/explain artifact builder for daily pairlist publishes (SPEC-074).

Builds a machine-readable :class:`AuditRecord` from ranked pairs, kept as a
JSON contract fully separate from the native RemotePairList JSON payload.
Every considered pair is recorded as selected or rejected with its
deterministic reason codes.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from hunter.pairlist_export.fingerprint import (
    compute_audit_fingerprint,
    compute_audit_fingerprint_v2,
    compute_pair_fingerprint,
)
from hunter.pairlist_export.models import AuditRecord, RankedPair
from hunter.pairlist_export.ranking_input_v2 import PROFILE_ACTIVE_DIMENSIONS, RankingProfile


def _with_fingerprint(pair: RankedPair) -> RankedPair:
    """Return ``pair`` unchanged if already fingerprinted, else fingerprint it.

    ``ranking_adapter.rank_pairs`` sets ``fingerprint`` on every
    :class:`RankedPair` it produces; this is a defensive fallback for
    callers that construct ``RankedPair`` directly.
    """
    if pair.fingerprint:
        return pair
    fingerprint = compute_pair_fingerprint(
        pair=pair.pair,
        rank=pair.rank,
        rs_score=pair.rs_score,
        oi_score=pair.oi_score,
        data_quality_pct=None,
        reason_codes=pair.reason_codes,
    )
    return RankedPair(
        pair=pair.pair,
        rank=pair.rank,
        selected=pair.selected,
        rs_score=pair.rs_score,
        oi_score=pair.oi_score,
        reason_codes=pair.reason_codes,
        fingerprint=fingerprint,
    )


def build_audit_record(
    as_of_date: str,
    universe_total: int,
    ranked_pairs: tuple[RankedPair, ...],
) -> AuditRecord:
    """Build the audit/explain record for a ranked pair set.

    Args:
        as_of_date: The ranking's as-of date, ``YYYY-MM-DD``.
        universe_total: Size of the full research universe considered
            before eligibility filtering.
        ranked_pairs: All ranked pairs (both selected and rejected).

    Returns:
        A frozen :class:`AuditRecord` with reason-code summary and
        fingerprint populated.
    """
    fingerprinted = tuple(_with_fingerprint(p) for p in ranked_pairs)
    selected = tuple(p for p in fingerprinted if p.selected)
    rejected = tuple(p for p in fingerprinted if not p.selected)

    reason_counter: Counter[str] = Counter()
    for pair in fingerprinted:
        for code in pair.reason_codes:
            reason_counter[code] += 1

    fingerprint = compute_audit_fingerprint(
        as_of_date=as_of_date,
        universe_total=universe_total,
        eligible_count=len(fingerprinted),
        selected_count=len(selected),
        rejected_count=len(rejected),
        selected_fingerprints=tuple(p.fingerprint for p in selected),
        rejected_fingerprints=tuple(p.fingerprint for p in rejected),
        reason_code_summary=dict(reason_counter),
    )

    return AuditRecord(
        as_of_date=as_of_date,
        universe_total=universe_total,
        eligible_count=len(fingerprinted),
        selected_count=len(selected),
        rejected_count=len(rejected),
        selected=selected,
        rejected=rejected,
        reason_code_summary=dict(reason_counter),
        fingerprint=fingerprint,
    )


def _pair_to_dict(pair: RankedPair) -> dict:
    payload = {
        "pair": pair.pair,
        "rank": pair.rank,
        "selected": pair.selected,
        "rs_score": str(pair.rs_score) if pair.rs_score is not None else None,
        "oi_score": str(pair.oi_score) if pair.oi_score is not None else None,
        "reason_codes": list(pair.reason_codes),
        "fingerprint": pair.fingerprint,
    }
    if pair.liquidity_score is not None:
        payload["liquidity_score"] = str(pair.liquidity_score)
    return payload


def audit_record_to_dict(audit: AuditRecord) -> dict:
    """Serialize an :class:`AuditRecord` to a JSON-ready dict.

    SPEC-075 v2 fields (``schema_version``, ``ranking_profile``,
    ``active_score_dimensions``, ...) are always present with their
    v1-safe defaults; no existing v1 test asserts an exact/closed key set,
    so this is fully backward compatible.
    """
    return {
        "as_of_date": audit.as_of_date,
        "universe_total": audit.universe_total,
        "eligible_count": audit.eligible_count,
        "selected_count": audit.selected_count,
        "rejected_count": audit.rejected_count,
        "selected": [_pair_to_dict(p) for p in audit.selected],
        "rejected": [_pair_to_dict(p) for p in audit.rejected],
        "reason_code_summary": dict(audit.reason_code_summary),
        "fingerprint": audit.fingerprint,
        "research_notice": audit.research_notice,
        "schema_version": audit.schema_version,
        "ranking_profile": audit.ranking_profile,
        "active_score_dimensions": list(audit.active_score_dimensions),
        "ignored_score_dimensions": list(audit.ignored_score_dimensions),
        "universe_size_at_scoring": audit.universe_size_at_scoring,
        "universe_fingerprint": audit.universe_fingerprint,
        "oi_available": audit.oi_available,
        "source_metadata": dict(audit.source_metadata),
        "per_pair_evidence": {k: list(v) for k, v in audit.per_pair_evidence.items()},
    }


def build_audit_record_v2(
    as_of_date: str,
    universe_total: int,
    ranked_pairs: tuple[RankedPair, ...],
    *,
    ranking_profile: RankingProfile,
    universe_size_at_scoring: int,
    universe_fingerprint: str,
    oi_available: bool,
    source_metadata: Mapping[str, Any] | None = None,
    per_pair_evidence: Mapping[str, tuple[str, ...]] | None = None,
) -> AuditRecord:
    """Build the SPEC-075 v2 audit/explain record for a ranked pair set.

    Identical selected/rejected/reason-code-summary construction to
    :func:`build_audit_record`, with the required v2 audit fields
    (``schema_version``, ``ranking_profile``, ``active_score_dimensions``,
    ``ignored_score_dimensions`` (always empty -- mismatches are rejected,
    never silently ignored), ``universe_size_at_scoring``,
    ``universe_fingerprint``, ``oi_available``, ``source_metadata``, and
    per-pair evidence) attached.
    """
    fingerprinted = tuple(_with_fingerprint(p) for p in ranked_pairs)
    selected = tuple(p for p in fingerprinted if p.selected)
    rejected = tuple(p for p in fingerprinted if not p.selected)

    reason_counter: Counter[str] = Counter()
    for pair in fingerprinted:
        for code in pair.reason_codes:
            reason_counter[code] += 1

    schema_version = "hunter-ranking-input-v2"
    active_dimensions = PROFILE_ACTIVE_DIMENSIONS[ranking_profile]

    fingerprint = compute_audit_fingerprint_v2(
        as_of_date=as_of_date,
        universe_total=universe_total,
        eligible_count=len(fingerprinted),
        selected_count=len(selected),
        rejected_count=len(rejected),
        selected_fingerprints=tuple(p.fingerprint for p in selected),
        rejected_fingerprints=tuple(p.fingerprint for p in rejected),
        reason_code_summary=dict(reason_counter),
        schema_version=schema_version,
        ranking_profile=ranking_profile.value,
        universe_fingerprint=universe_fingerprint,
    )

    return AuditRecord(
        as_of_date=as_of_date,
        universe_total=universe_total,
        eligible_count=len(fingerprinted),
        selected_count=len(selected),
        rejected_count=len(rejected),
        selected=selected,
        rejected=rejected,
        reason_code_summary=dict(reason_counter),
        fingerprint=fingerprint,
        schema_version=schema_version,
        ranking_profile=ranking_profile.value,
        active_score_dimensions=active_dimensions,
        ignored_score_dimensions=(),
        universe_size_at_scoring=universe_size_at_scoring,
        universe_fingerprint=universe_fingerprint,
        oi_available=oi_available,
        source_metadata=dict(source_metadata or {}),
        per_pair_evidence=dict(per_pair_evidence or {}),
    )


def explain_audit_record(audit: AuditRecord) -> str:
    """Render a human-readable explanation of an audit record."""
    lines = [
        f"Pairlist audit -- as-of {audit.as_of_date}",
        f"Universe: {audit.universe_total} total, {audit.eligible_count} eligible",
        f"Selected: {audit.selected_count}  Rejected: {audit.rejected_count}",
        "",
        "Reason code summary:",
    ]
    for code, count in sorted(audit.reason_code_summary.items()):
        lines.append(f"  {code}: {count}")

    lines.append("")
    lines.append("Selected pairs:")
    for pair in audit.selected:
        codes = ", ".join(pair.reason_codes)
        lines.append(f"  #{pair.rank:>3} {pair.pair}  [{codes}]")

    lines.append("")
    lines.append("Rejected pairs:")
    for pair in audit.rejected:
        codes = ", ".join(pair.reason_codes)
        lines.append(f"  #{pair.rank:>3} {pair.pair}  [{codes}]")

    lines.append("")
    lines.append(audit.research_notice)
    return "\n".join(lines)
