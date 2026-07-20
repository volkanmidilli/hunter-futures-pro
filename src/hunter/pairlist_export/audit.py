"""Audit/explain artifact builder for daily pairlist publishes (SPEC-074).

Builds a machine-readable :class:`AuditRecord` from ranked pairs, kept as a
JSON contract fully separate from the native RemotePairList JSON payload.
Every considered pair is recorded as selected or rejected with its
deterministic reason codes.
"""

from __future__ import annotations

from collections import Counter

from hunter.pairlist_export.fingerprint import (
    compute_audit_fingerprint,
    compute_pair_fingerprint,
)
from hunter.pairlist_export.models import AuditRecord, RankedPair


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
    return {
        "pair": pair.pair,
        "rank": pair.rank,
        "selected": pair.selected,
        "rs_score": str(pair.rs_score) if pair.rs_score is not None else None,
        "oi_score": str(pair.oi_score) if pair.oi_score is not None else None,
        "reason_codes": list(pair.reason_codes),
        "fingerprint": pair.fingerprint,
    }


def audit_record_to_dict(audit: AuditRecord) -> dict:
    """Serialize an :class:`AuditRecord` to a JSON-ready dict."""
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
    }


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
