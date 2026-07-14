"""Engine for the Governance Decision Summary Aggregator (MVP-61).

The engine combines a ``ResearchDecisionGateReport`` (MVP-59), a sequence of
``HumanReviewRecord`` entries (MVP-60), and chain verification state into one
deterministic, immutable ``GovernanceDecisionSummary``.

The engine does not read/write files, read the clock internally, mutate caller
input, or import real Freqtrade runtime modules.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from hunter.governance_summary.models import (
    GOVERNANCE_SUMMARY_VERSION,
    GovernanceDecisionSummary,
    GovernanceReviewSummary,
    GovernanceSummaryConfig,
    GovernanceSummaryError,
)
from hunter.governance_summary.policy import (
    build_governance_safety_flags,
    classify_governance_reasons,
    detect_open_change_request,
    resolve_governance_status,
    select_latest_accepted_review,
)
from hunter.governance_summary.validator import (
    build_review_chain_facts,
    validate_evaluated_at,
    validate_gate_report,
    validate_review_records,
)

if TYPE_CHECKING:
    from hunter.human_review_registry.models import HumanReviewRecord
    from hunter.research_decision_gate.models import ResearchDecisionGateReport


def _canonical_json(payload: object) -> str:
    """Return deterministic compact JSON for hashing."""
    return json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


def _iso(value: datetime) -> str:
    """Return an ISO-8601 string for a timezone-aware datetime."""
    return value.astimezone().isoformat()


def _serialize_config(config: GovernanceSummaryConfig) -> dict[str, Any]:
    """Serialize config into a deterministic JSON-safe dict."""
    return {
        "require_review_chain": config.require_review_chain,
        "output_dir": str(config.output_dir),
        "report_output_dir": str(config.report_output_dir),
        "json_filename": config.json_filename,
        "markdown_filename": config.markdown_filename,
    }


def compute_governance_fingerprint(
    gate_decision: str,
    gate_decision_fingerprint: str,
    review_fingerprints: tuple[str, ...],
    latest_accepted_record_fingerprint: str | None,
    governance_status: str,
    blocking_reason_codes: tuple[str, ...],
    review_reason_codes: tuple[str, ...],
    safety_flags: Mapping[str, bool],
    config: GovernanceSummaryConfig,
    evaluated_at: datetime,
) -> str:
    """Compute a deterministic SHA-256 fingerprint for a governance summary."""
    payload = {
        "version": GOVERNANCE_SUMMARY_VERSION,
        "gate_decision": gate_decision,
        "gate_decision_fingerprint": gate_decision_fingerprint,
        "review_fingerprints": list(review_fingerprints),
        "latest_accepted_record_fingerprint": latest_accepted_record_fingerprint,
        "governance_status": governance_status,
        "blocking_reason_codes": list(blocking_reason_codes),
        "review_reason_codes": list(review_reason_codes),
        "safety_flags": dict(sorted(safety_flags.items())),
        "config": _serialize_config(config),
        "evaluated_at": _iso(evaluated_at),
    }
    canonical = _canonical_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_governance_decision_summary(
    gate_report: ResearchDecisionGateReport | None,
    review_records: Sequence[HumanReviewRecord],
    config: GovernanceSummaryConfig,
    *,
    evaluated_at: datetime,
    metadata: Mapping[str, object] | None = None,
) -> GovernanceDecisionSummary:
    """Build a deterministic, immutable governance decision summary.

    Pipeline:
      1. validate gate report
      2. validate review chain
      3. summarize records
      4. select latest accepted review
      5. detect open change request
      6. classify reasons
      7. resolve status
      8. compute fingerprint
      9. immutable summary
    """
    if not isinstance(config, GovernanceSummaryConfig):
        raise GovernanceSummaryError(
            "config must be a GovernanceSummaryConfig",
            reason_code="INVALID_CONFIG",
        )

    timestamp_reasons = validate_evaluated_at(evaluated_at, config)
    gate_reasons = validate_gate_report(gate_report)
    chain_reasons = validate_review_records(review_records, config)

    facts = build_review_chain_facts(review_records)
    latest_accepted = select_latest_accepted_review(review_records)
    open_change_request = detect_open_change_request(latest_accepted)

    # An open change request is a review-required condition.
    extra_review_reasons: list[str] = []
    if open_change_request:
        from hunter.governance_summary.models import OPEN_CHANGE_REQUEST

        extra_review_reasons.append(OPEN_CHANGE_REQUEST)

    blocking_reason_codes, review_reason_codes = classify_governance_reasons(
        gate_reasons,
        chain_reasons,
        latest_accepted,
    )

    # Merge extra review reasons without duplicates, preserving sort order.
    all_review_reasons = sorted(
        set(review_reason_codes) | set(extra_review_reasons)
    )

    governance_status = resolve_governance_status(
        blocking_reason_codes,
        tuple(all_review_reasons),
    )

    gate_decision = getattr(gate_report, "decision", "GO") or "GO"
    gate_decision_fingerprint = (
        getattr(gate_report, "decision_fingerprint", "MISSING") or "MISSING"
    )

    safety_flags = build_governance_safety_flags()

    review_summary = GovernanceReviewSummary(
        total_records=facts["total_records"],
        accepted_records=facts["accepted_records_count"],
        rejected_attempts=facts["rejected_attempts"],
        chain_valid=not chain_reasons,
        latest_accepted_record_fingerprint=getattr(
            latest_accepted, "record_fingerprint", None
        ),
        latest_reviewer_identity=getattr(latest_accepted, "reviewer_identity", None),
        latest_reviewer_decision=getattr(latest_accepted, "reviewer_decision", None),
        latest_review_created_at=getattr(latest_accepted, "created_at", None),
        open_change_request_count=1 if open_change_request else 0,
        source_decision_fingerprints=facts["source_decision_fingerprints"],
        reason_codes=chain_reasons,
    )

    governance_fingerprint = compute_governance_fingerprint(
        gate_decision=gate_decision,
        gate_decision_fingerprint=gate_decision_fingerprint,
        review_fingerprints=facts["record_fingerprints"],
        latest_accepted_record_fingerprint=getattr(
            latest_accepted, "record_fingerprint", None
        ),
        governance_status=governance_status,
        blocking_reason_codes=blocking_reason_codes,
        review_reason_codes=tuple(all_review_reasons),
        safety_flags=safety_flags,
        config=config,
        evaluated_at=evaluated_at,
    )

    return GovernanceDecisionSummary(
        version=GOVERNANCE_SUMMARY_VERSION,
        governance_status=governance_status,  # type: ignore[arg-type]
        governance_fingerprint=governance_fingerprint,
        evaluated_at=evaluated_at,
        gate_decision=gate_decision,  # type: ignore[arg-type]
        gate_decision_fingerprint=gate_decision_fingerprint,
        review_summary=review_summary,
        blocking_reason_codes=blocking_reason_codes,
        review_reason_codes=tuple(all_review_reasons),
        research_only=True,
        human_review_required=True,
        execution_approval_granted=False,
        metadata=metadata,
    )


__all__ = [
    "build_governance_decision_summary",
    "compute_governance_fingerprint",
]
