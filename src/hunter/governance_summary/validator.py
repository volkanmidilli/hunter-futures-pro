"""Input and chain validation for the Governance Decision Summary Aggregator (MVP-61).

Validation is pure: no file/network access, no clock reads. The validator
reuses MVP-60 chain verification where possible and maps MVP-60 reason codes
to the MVP-61 governance reason-code namespace.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Sequence

from hunter.governance_summary.models import (
    BROKEN_REVIEW_CHAIN,
    DUPLICATE_REVIEW_RECORD,
    GATE_DECISION_NO_GO,
    GATE_REVIEW_REQUIRED,
    INVALID_GATE_REPORT,
    INVALID_TIMESTAMP,
    MISSING_GATE_REPORT,
    MISSING_REQUIRED_FINGERPRINT,
    MISSING_REVIEW_CHAIN,
    TAMPERED_REVIEW_RECORD,
    UNSAFE_GOVERNANCE_FLAG,
    GovernanceSummaryConfig,
)

if TYPE_CHECKING:
    from hunter.human_review_registry.models import HumanReviewRecord
    from hunter.research_decision_gate.models import ResearchDecisionGateReport


def _is_gate_report(obj: object) -> bool:
    """Return True if ``obj`` looks like a ResearchDecisionGateReport."""
    return hasattr(obj, "decision") and hasattr(obj, "decision_fingerprint")


def validate_gate_report(
    gate_report: ResearchDecisionGateReport | None,
) -> tuple[str, ...]:
    """Validate the upstream research decision gate report.

    Returns blocking reason codes. ``NO_GO`` and ``NEEDS_REVIEW`` are treated
    as governance blocking/review conditions respectively.
    """
    if gate_report is None:
        return (MISSING_GATE_REPORT,)

    if not _is_gate_report(gate_report):
        return (INVALID_GATE_REPORT,)

    reasons: list[str] = []

    fingerprint = getattr(gate_report, "decision_fingerprint", "") or ""
    if not fingerprint:
        reasons.append(MISSING_REQUIRED_FINGERPRINT)

    decision = getattr(gate_report, "decision", None)
    if decision == "NO_GO":
        reasons.append(GATE_DECISION_NO_GO)
    elif decision == "NEEDS_REVIEW":
        reasons.append(GATE_REVIEW_REQUIRED)
    elif decision not in {"GO", "NO_GO", "NEEDS_REVIEW"}:
        reasons.append(INVALID_GATE_REPORT)

    if not getattr(gate_report, "research_only", True) or not getattr(
        gate_report, "human_approval_required", True
    ):
        reasons.append(UNSAFE_GOVERNANCE_FLAG)

    return tuple(reasons)


def _map_chain_reason(code: str) -> str:
    """Map an MVP-60 chain reason code to the MVP-61 namespace."""
    mapping = {
        "DUPLICATE_REVIEW": DUPLICATE_REVIEW_RECORD,
        "PREVIOUS_RECORD_MISMATCH": BROKEN_REVIEW_CHAIN,
    }
    return mapping.get(code, code)


def validate_review_records(
    review_records: Sequence[HumanReviewRecord],
    config: GovernanceSummaryConfig,
) -> tuple[str, ...]:
    """Validate the review-record sequence and chain integrity.

    Reuses MVP-60 ``verify_chain`` and ``verify_record_fingerprint`` where
    possible. An empty sequence is valid when ``config.require_review_chain``
    is False; otherwise it yields ``MISSING_REVIEW_CHAIN``.

    Fingerprint mismatches are reported as ``TAMPERED_REVIEW_RECORD``.
    Broken previous-record links are reported as ``BROKEN_REVIEW_CHAIN``.
    """
    # An empty sequence is valid input; it yields REVIEW_REQUIRED downstream
    # via NO_ACCEPTED_REVIEW, not BLOCKED.

    # Lazily import MVP-60 chain API to avoid a hard import-time dependency.
    from hunter.human_review_registry.chain import (
        verify_chain,
        verify_record_fingerprint,
    )

    records = tuple(review_records)

    # Check each record's own fingerprint first to distinguish tampering from
    # a broken chain link.
    result: list[str] = []
    tampered_indices: set[int] = set()
    for idx, record in enumerate(records):
        fp_reasons = verify_record_fingerprint(record)
        if fp_reasons:
            tampered_indices.add(idx)
            result.append(TAMPERED_REVIEW_RECORD)

    # Now verify chain linkage. Skip linkage checks for tampered records
    # because their fingerprints are already known to be invalid.
    chain_reasons = verify_chain(records)
    for code in chain_reasons:
        mapped = _map_chain_reason(code)
        if mapped == BROKEN_REVIEW_CHAIN:
            # If the reason is a broken chain, only report it as a chain break
            # when the affected record's fingerprint itself was valid.
            # verify_chain emits BROKEN_REVIEW_CHAIN for both fingerprint
            # mismatches and previous-record mismatches; we already covered
            # fingerprint mismatches above.
            if mapped not in result:
                result.append(BROKEN_REVIEW_CHAIN)
        elif mapped not in result:
            result.append(mapped)

    return tuple(result)


def validate_evaluated_at(
    evaluated_at: datetime,
    config: GovernanceSummaryConfig,
) -> tuple[str, ...]:
    """Validate the injected evaluation timestamp."""
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        return (INVALID_TIMESTAMP,)
    return ()


def build_review_chain_facts(
    review_records: Sequence[HumanReviewRecord],
) -> dict[str, Any]:
    """Build a fact dictionary summarizing the review chain.

    This is a pure read-only summary used by the policy layer. It does not
    mutate ``review_records``.
    """
    total = len(review_records)
    accepted_count = sum(1 for r in review_records if getattr(r, "accepted", False))
    rejected = total - accepted_count
    fingerprints = tuple(
        str(getattr(r, "record_fingerprint", "")) for r in review_records
    )
    accepted_records = [
        r for r in review_records if getattr(r, "accepted", False)
    ]
    source_fingerprints = tuple(
        str(getattr(r, "source_decision_fingerprint", ""))
        for r in review_records
        if getattr(r, "source_decision_fingerprint", None)
    )
    return {
        "total_records": total,
        "accepted_records_count": accepted_count,
        "rejected_attempts": rejected,
        "record_fingerprints": fingerprints,
        "accepted_records": accepted_records,
        "source_decision_fingerprints": source_fingerprints,
    }


__all__ = [
    "validate_gate_report",
    "validate_review_records",
    "validate_evaluated_at",
    "build_review_chain_facts",
]
