"""Provenance and input validation for the Governance Handoff Package Builder (MVP-62).

Validation is pure: no file/network access, no clock reads. It checks the
presence, type, and mutual consistency of the upstream governance summary, gate
report, and latest accepted review record.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from hunter.governance_handoff.models import (
    CANONICAL_SAFETY_FLAGS,
    GATE_FINGERPRINT_MISMATCH,
    GOVERNANCE_FINGERPRINT_MISMATCH,
    INVALID_GATE_REPORT,
    INVALID_GOVERNANCE_SUMMARY,
    INVALID_REVIEW_RECORD,
    INVALID_TIMESTAMP,
    MISSING_GATE_REPORT,
    MISSING_GOVERNANCE_SUMMARY,
    MISSING_LATEST_ACCEPTED_REVIEW,
    MISSING_REQUIRED_FINGERPRINT,
    REVIEW_FINGERPRINT_MISMATCH,
    SOURCE_VERSION_MISMATCH,
    UNSAFE_HANDOFF_FLAG,
    GovernanceHandoffConfig,
)

if TYPE_CHECKING:
    from hunter.governance_summary.models import GovernanceDecisionSummary
    from hunter.human_review_registry.models import HumanReviewRecord
    from hunter.research_decision_gate.models import ResearchDecisionGateReport


def _is_governance_summary(obj: object) -> bool:
    """Return True if ``obj`` looks like a GovernanceDecisionSummary."""
    return (
        hasattr(obj, "governance_fingerprint")
        and hasattr(obj, "gate_decision_fingerprint")
        and hasattr(obj, "review_summary")
    )


def _is_gate_report(obj: object) -> bool:
    """Return True if ``obj`` looks like a ResearchDecisionGateReport."""
    return hasattr(obj, "decision") and hasattr(obj, "decision_fingerprint")


def _is_review_record(obj: object) -> bool:
    """Return True if ``obj`` looks like a HumanReviewRecord."""
    return hasattr(obj, "record_fingerprint") and hasattr(obj, "accepted")


def validate_built_at(built_at: datetime) -> tuple[str, ...]:
    """Validate the injected package-build timestamp."""
    if not isinstance(built_at, datetime) or built_at.tzinfo is None:
        return (INVALID_TIMESTAMP,)
    return ()


def validate_governance_summary(
    governance_summary: GovernanceDecisionSummary | None,
) -> tuple[str, ...]:
    """Validate the upstream governance decision summary.

    Returns blocking reason codes.
    """
    if governance_summary is None:
        return (MISSING_GOVERNANCE_SUMMARY,)

    if not _is_governance_summary(governance_summary):
        return (INVALID_GOVERNANCE_SUMMARY,)

    reasons: list[str] = []

    fingerprint = getattr(governance_summary, "governance_fingerprint", "") or ""
    if not fingerprint:
        reasons.append(MISSING_REQUIRED_FINGERPRINT)

    gate_fp = getattr(governance_summary, "gate_decision_fingerprint", "") or ""
    if not gate_fp:
        reasons.append(MISSING_REQUIRED_FINGERPRINT)

    status = getattr(governance_summary, "governance_status", None)
    if status not in {"READY_FOR_RESEARCH_HANDOFF", "REVIEW_REQUIRED", "BLOCKED"}:
        reasons.append(INVALID_GOVERNANCE_SUMMARY)

    review_summary = getattr(governance_summary, "review_summary", None)
    if review_summary is None:
        reasons.append(INVALID_GOVERNANCE_SUMMARY)

    if not getattr(governance_summary, "research_only", True):
        reasons.append(UNSAFE_HANDOFF_FLAG)
    if getattr(governance_summary, "execution_approval_granted", False):
        reasons.append(UNSAFE_HANDOFF_FLAG)

    return tuple(reasons)


def validate_gate_report(
    gate_report: ResearchDecisionGateReport | None,
) -> tuple[str, ...]:
    """Validate the upstream research decision gate report.

    Returns blocking reason codes.
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
    if decision not in {"GO", "NO_GO", "NEEDS_REVIEW"}:
        reasons.append(INVALID_GATE_REPORT)

    if not getattr(gate_report, "research_only", True):
        reasons.append(UNSAFE_HANDOFF_FLAG)
    if not getattr(gate_report, "human_approval_required", True):
        reasons.append(UNSAFE_HANDOFF_FLAG)
    if getattr(gate_report, "execution_approval_granted", False):
        reasons.append(UNSAFE_HANDOFF_FLAG)

    return tuple(reasons)


def validate_latest_review(
    latest_accepted_review: HumanReviewRecord | None,
    config: GovernanceHandoffConfig,
) -> tuple[str, ...]:
    """Validate the latest accepted human review record.

    Returns blocking reason codes.
    """
    if latest_accepted_review is None:
        if config.require_latest_accepted_review:
            return (MISSING_LATEST_ACCEPTED_REVIEW,)
        return ()

    if not _is_review_record(latest_accepted_review):
        return (INVALID_REVIEW_RECORD,)

    reasons: list[str] = []

    fingerprint = getattr(latest_accepted_review, "record_fingerprint", "") or ""
    if not fingerprint:
        reasons.append(MISSING_REQUIRED_FINGERPRINT)

    if not getattr(latest_accepted_review, "accepted", False):
        reasons.append(INVALID_REVIEW_RECORD)

    if not getattr(latest_accepted_review, "human_approval_recorded", False):
        reasons.append(INVALID_REVIEW_RECORD)

    if getattr(latest_accepted_review, "execution_approval_granted", False):
        reasons.append(UNSAFE_HANDOFF_FLAG)

    reviewer_decision = getattr(latest_accepted_review, "reviewer_decision", None)
    if reviewer_decision not in {
        "APPROVE_FOR_RESEARCH",
        "REJECT",
        "REQUEST_CHANGES",
    }:
        reasons.append(INVALID_REVIEW_RECORD)

    created_at = getattr(latest_accepted_review, "created_at", None)
    if not isinstance(created_at, datetime) or (
        isinstance(created_at, datetime) and created_at.tzinfo is None
    ):
        reasons.append(INVALID_TIMESTAMP)

    return tuple(reasons)


def validate_source_versions(source_versions: dict[str, str] | None) -> tuple[str, ...]:
    """Validate that source versions are non-empty strings."""
    if source_versions is None:
        return (SOURCE_VERSION_MISMATCH,)
    for name, version in source_versions.items():
        if not isinstance(name, str) or not name.strip():
            return (SOURCE_VERSION_MISMATCH,)
        if not isinstance(version, str) or not version.strip():
            return (SOURCE_VERSION_MISMATCH,)
    return ()


def validate_provenance_links(
    governance_summary: GovernanceDecisionSummary | None,
    gate_report: ResearchDecisionGateReport | None,
    latest_accepted_review: HumanReviewRecord | None,
) -> tuple[str, ...]:
    """Validate mutual consistency between upstream fingerprints.

    Returns blocking reason codes.
    """
    reasons: list[str] = []

    if governance_summary is not None and gate_report is not None:
        gov_gate_fp = (
            getattr(governance_summary, "gate_decision_fingerprint", "") or ""
        )
        gate_fp = getattr(gate_report, "decision_fingerprint", "") or ""
        if gov_gate_fp and gate_fp and gov_gate_fp != gate_fp:
            reasons.append(GATE_FINGERPRINT_MISMATCH)

    if governance_summary is not None and latest_accepted_review is not None:
        review_summary = getattr(governance_summary, "review_summary", None)
        gov_review_fp = None
        if review_summary is not None:
            gov_review_fp = (
                getattr(review_summary, "latest_accepted_record_fingerprint", "")
                or ""
            ) or None
        review_fp = getattr(latest_accepted_review, "record_fingerprint", "") or ""
        if gov_review_fp and review_fp and gov_review_fp != review_fp:
            reasons.append(REVIEW_FINGERPRINT_MISMATCH)

    if latest_accepted_review is not None and gate_report is not None:
        review_source_fp = (
            getattr(latest_accepted_review, "source_decision_fingerprint", "") or ""
        )
        gate_fp = getattr(gate_report, "decision_fingerprint", "") or ""
        if review_source_fp and gate_fp and review_source_fp != gate_fp:
            reasons.append(GOVERNANCE_FINGERPRINT_MISMATCH)

    return tuple(reasons)


def validate_safety_flags(
    safety_flags: dict[str, bool] | None,
) -> tuple[str, ...]:
    """Validate that safety flags match the canonical invariant set.

    Any contradiction yields ``UNSAFE_HANDOFF_FLAG``.
    """
    if safety_flags is None:
        return (UNSAFE_HANDOFF_FLAG,)
    for key, expected in CANONICAL_SAFETY_FLAGS.items():
        if safety_flags.get(key) != expected:
            return (UNSAFE_HANDOFF_FLAG,)
    return ()


def validate_all(
    governance_summary: GovernanceDecisionSummary | None,
    gate_report: ResearchDecisionGateReport | None,
    latest_accepted_review: HumanReviewRecord | None,
    config: GovernanceHandoffConfig,
    *,
    built_at: datetime,
    safety_flags: dict[str, bool] | None = None,
) -> tuple[str, ...]:
    """Run all validation steps and return a single tuple of blocking reasons.

    The result is sorted and deduplicated. If ``safety_flags`` is not provided,
    the canonical safety flags are assumed valid.
    """
    if safety_flags is None:
        safety_flags = dict(CANONICAL_SAFETY_FLAGS)
    reasons: list[str] = []
    reasons.extend(validate_built_at(built_at))
    reasons.extend(validate_governance_summary(governance_summary))
    reasons.extend(validate_gate_report(gate_report))
    reasons.extend(validate_latest_review(latest_accepted_review, config))
    reasons.extend(
        validate_provenance_links(governance_summary, gate_report, latest_accepted_review)
    )
    reasons.extend(validate_safety_flags(safety_flags))
    return tuple(sorted(set(reasons)))


__all__ = [
    "validate_all",
    "validate_built_at",
    "validate_governance_summary",
    "validate_gate_report",
    "validate_latest_review",
    "validate_source_versions",
    "validate_provenance_links",
    "validate_safety_flags",
]
