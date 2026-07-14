"""Engine for the Human Review Decision Registry (MVP-60). The engine consumes a ``ResearchDecisionGateReport`` (MVP-59) and a human review input, and produces an immutable, append-only ``HumanReviewRecord``."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Mapping, Sequence

from hunter.human_review_registry.chain import (
    compute_record_fingerprint,
    detect_duplicate_review,
    verify_chain,
)
from hunter.human_review_registry.models import (
    ACCEPTED_REASON_CODES,
    BLOCKING_REASON_CODES,
    GO,
    HUMAN_REVIEW_REGISTRY_VERSION,
    REJECT,
    HumanReviewInput,
    HumanReviewRecord,
    HumanReviewRegistryConfig,
    HumanReviewRegistryError,
)
from hunter.human_review_registry.policy import evaluate_review_policy
from hunter.human_review_registry.validator import (
    validate_created_at,
    validate_decision_report,
    validate_review_input,
)

if TYPE_CHECKING:
    from hunter.research_decision_gate.models import ResearchDecisionGateReport


def build_human_review_record(
    decision_report: ResearchDecisionGateReport | None,
    review_input: HumanReviewInput | None,
    config: HumanReviewRegistryConfig,
    *,
    previous_record: HumanReviewRecord | None = None,
    existing_records: Sequence[HumanReviewRecord] = (),
    created_at: datetime,
    metadata: Mapping[str, object] | None = None,
) -> HumanReviewRecord:
    """Build a deterministic, immutable human review record.

    The record is always research-only and never grants execution approval.
    Any validation, policy, or chain failure produces a rejected record with
    explicit blocking reason codes.
    """
    if not isinstance(config, HumanReviewRegistryConfig):
        raise HumanReviewRegistryError(
            "config must be a HumanReviewRegistryConfig",
            reason_code="INVALID_CONFIG",
        )
    if not isinstance(created_at, datetime) or created_at.tzinfo is None:
        raise ValueError(
            f"created_at must be a timezone-aware datetime, got {created_at!r}"
        )

    blocking_reasons: list[str] = []

    report_reasons = validate_decision_report(decision_report)
    blocking_reasons.extend(report_reasons)

    input_reasons = validate_review_input(review_input, config)
    blocking_reasons.extend(input_reasons)

    timestamp_reasons = validate_created_at(created_at, config)
    blocking_reasons.extend(timestamp_reasons)

    # Validate the existing chain before appending.
    chain_tuple = tuple(existing_records)
    chain_reasons = verify_chain(chain_tuple)
    blocking_reasons.extend(chain_reasons)

    source_decision_fingerprint = "MISSING"
    source_decision = GO
    if decision_report is not None:
        source_decision_fingerprint = getattr(decision_report, "decision_fingerprint", "") or "MISSING"
        source_decision = getattr(decision_report, "decision", GO) or GO

    accepted = False
    accepted_reasons: tuple[str, ...] = ()

    if not blocking_reasons and review_input is not None:
        if detect_duplicate_review(source_decision_fingerprint, review_input, chain_tuple):
            blocking_reasons.append("DUPLICATE_REVIEW")
        else:
            accepted, policy_blocking, accepted_reasons = evaluate_review_policy(
                source_decision, review_input, config
            )
            blocking_reasons.extend(policy_blocking)

    if blocking_reasons:
        accepted = False
        accepted_reasons = ()

    previous_record_fingerprint: str | None = None
    if accepted:
        if previous_record is not None:
            previous_record_fingerprint = previous_record.record_fingerprint
        elif existing_records:
            previous_record_fingerprint = existing_records[-1].record_fingerprint

    reviewer_identity = review_input.reviewer_identity if review_input else "MISSING"
    reviewer_decision = review_input.reviewer_decision if review_input else REJECT
    review_note = review_input.review_note if review_input else "Missing required review input."

    human_approval_recorded = accepted and review_input is not None
    record_fingerprint = compute_record_fingerprint(
        source_decision_fingerprint=source_decision_fingerprint,
        source_decision=source_decision,
        reviewer_identity=reviewer_identity,
        reviewer_decision=reviewer_decision,
        review_note=review_note,
        created_at=created_at,
        previous_record_fingerprint=previous_record_fingerprint,
        accepted=accepted,
        human_approval_recorded=human_approval_recorded,
        execution_approval_granted=False,
    )

    all_reason_codes: tuple[str, ...] = tuple(blocking_reasons) + accepted_reasons
    # Ensure every emitted reason code is known; unknown codes are replaced with
    # a safe blocker to keep the registry fail-closed.
    sanitized_reasons: list[str] = []
    for code in all_reason_codes:
        if code in BLOCKING_REASON_CODES or code in ACCEPTED_REASON_CODES:
            sanitized_reasons.append(code)
        else:
            sanitized_reasons.append("UNKNOWN_REASON_CODE")

    return HumanReviewRecord(
        version=HUMAN_REVIEW_REGISTRY_VERSION,
        source_decision_fingerprint=source_decision_fingerprint,
        source_decision=source_decision,  # type: ignore[arg-type]
        reviewer_identity=reviewer_identity,
        reviewer_decision=reviewer_decision,  # type: ignore[arg-type]
        review_note=review_note,
        created_at=created_at,
        previous_record_fingerprint=previous_record_fingerprint,
        record_fingerprint=record_fingerprint,
        accepted=accepted,
        human_approval_recorded=human_approval_recorded,
        execution_approval_granted=False,
        reason_codes=tuple(sanitized_reasons),
        metadata=metadata,
    )


__all__ = ["build_human_review_record"]
