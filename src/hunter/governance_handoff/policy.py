"""Handoff policy for the Governance Handoff Package Builder (MVP-62).

Policy functions are pure and deterministic. They decide whether a handoff is
allowed, classify reason codes, build source references, and enforce canonical
safety flags.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Mapping

from hunter.governance_handoff.models import (
    BLOCKED,
    CANONICAL_SAFETY_FLAGS,
    GOVERNANCE_REVIEW_REQUIRED,
    INCOMPLETE_PROVENANCE,
    MISSING_OPTIONAL_METADATA,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_REQUIRED,
    HandoffSourceReference,
    ResearchGovernanceHandoffManifest,
)

if TYPE_CHECKING:
    from hunter.governance_summary.models import GovernanceDecisionSummary
    from hunter.human_review_registry.models import HumanReviewRecord
    from hunter.research_decision_gate.models import ResearchDecisionGateReport


def build_handoff_safety_flags() -> Mapping[str, bool]:
    """Return the canonical, immutable safety flags for every handoff package."""
    return CANONICAL_SAFETY_FLAGS


def _upstream_version(obj: object) -> str:
    """Return the version attribute of an upstream object, if present."""
    version = getattr(obj, "version", "")
    if isinstance(version, str) and version.strip():
        return version
    return "unknown"


def _upstream_fingerprint(obj: object, attr: str) -> str:
    """Return a fingerprint attribute from an upstream object.

    Returns ``"MISSING"`` when the object is absent or the attribute is empty
    so that ``HandoffSourceReference`` remains valid.
    """
    if obj is None:
        return "MISSING"
    fp = getattr(obj, attr, "") or ""
    return fp if fp.strip() else "MISSING"


def _is_accepted_source(reasons: tuple[str, ...]) -> bool:
    """A source is accepted for the package when it has no blocking reasons."""
    return not bool(reasons)


def build_source_references(
    governance_summary: GovernanceDecisionSummary | None,
    gate_report: ResearchDecisionGateReport | None,
    latest_accepted_review: HumanReviewRecord | None,
    governance_reasons: tuple[str, ...],
    gate_reasons: tuple[str, ...],
    review_reasons: tuple[str, ...],
) -> tuple[HandoffSourceReference, HandoffSourceReference, HandoffSourceReference | None]:
    """Build immutable source references for the handoff package.

    Each reference carries the upstream source name, version, fingerprint,
    whether it was accepted for handoff, and any reason codes that explain its
    state.
    """
    governance_ref = HandoffSourceReference(
        source_name="governance_summary",
        source_version=_upstream_version(governance_summary),
        fingerprint=_upstream_fingerprint(
            governance_summary, "governance_fingerprint"
        ),
        accepted=_is_accepted_source(governance_reasons),
        reason_codes=governance_reasons,
    )

    gate_ref = HandoffSourceReference(
        source_name="research_decision_gate",
        source_version=_upstream_version(gate_report),
        fingerprint=_upstream_fingerprint(gate_report, "decision_fingerprint"),
        accepted=_is_accepted_source(gate_reasons),
        reason_codes=gate_reasons,
    )

    review_ref: HandoffSourceReference | None = None
    if latest_accepted_review is not None:
        review_ref = HandoffSourceReference(
            source_name="human_review_registry",
            source_version=_upstream_version(latest_accepted_review),
            fingerprint=_upstream_fingerprint(
                latest_accepted_review, "record_fingerprint"
            ),
            accepted=_is_accepted_source(review_reasons),
            reason_codes=review_reasons,
        )

    return governance_ref, gate_ref, review_ref


def classify_handoff_reasons(
    governance_summary: GovernanceDecisionSummary | None,
    blocking_validation_reasons: tuple[str, ...],
    metadata: Mapping[str, object] | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Classify package-level blocking and review-required reason codes.

    Returns ``(blocking_reason_codes, review_reason_codes)``.
    """
    blocking: list[str] = list(blocking_validation_reasons)
    review: list[str] = []

    if governance_summary is not None:
        status = getattr(governance_summary, "governance_status", None)
        if status == BLOCKED:
            if not blocking:
                # A blocked governance summary with no separate validation
                # reason still blocks handoff.
                pass
        elif status == REVIEW_REQUIRED:
            review.append(GOVERNANCE_REVIEW_REQUIRED)
        elif status == READY_FOR_RESEARCH_HANDOFF:
            pass
        else:
            # Unknown status is a blocking condition.
            from hunter.governance_handoff.models import INVALID_GOVERNANCE_SUMMARY

            if INVALID_GOVERNANCE_SUMMARY not in blocking:
                blocking.append(INVALID_GOVERNANCE_SUMMARY)

    if metadata is None or not isinstance(metadata, Mapping):
        review.append(INCOMPLETE_PROVENANCE)
    elif not metadata:
        # Empty metadata is allowed but noted as missing optional metadata.
        review.append(MISSING_OPTIONAL_METADATA)

    # Deduplicate while preserving order.
    seen: set[str] = set()
    blocking_unique: list[str] = []
    for code in blocking:
        if code not in seen:
            seen.add(code)
            blocking_unique.append(code)

    seen_review: set[str] = set()
    review_unique: list[str] = []
    for code in review:
        if code not in seen_review:
            seen_review.add(code)
            review_unique.append(code)

    return tuple(blocking_unique), tuple(review_unique)


def resolve_handoff_allowed(
    governance_status: str,
    blocking_reason_codes: tuple[str, ...],
    review_reason_codes: tuple[str, ...],
) -> bool:
    """Resolve whether research handoff is allowed.

    Only ``READY_FOR_RESEARCH_HANDOFF`` with no blocking and no review-required
    reasons yields ``True``.
    """
    if governance_status != READY_FOR_RESEARCH_HANDOFF:
        return False
    if blocking_reason_codes:
        return False
    if review_reason_codes:
        return False
    return True


def build_handoff_manifest(
    package_version: str,
    package_fingerprint: str,
    built_at: datetime,
    governance_source: HandoffSourceReference,
    gate_source: HandoffSourceReference,
    review_source: HandoffSourceReference | None,
    safety_flags: Mapping[str, bool],
    artifact_filenames: Mapping[str, str],
) -> ResearchGovernanceHandoffManifest:
    """Build the immutable handoff manifest."""
    source_versions = {
        governance_source.source_name: governance_source.source_version,
        gate_source.source_name: gate_source.source_version,
    }
    if review_source is not None:
        source_versions[review_source.source_name] = review_source.source_version

    return ResearchGovernanceHandoffManifest(
        package_version=package_version,
        package_fingerprint=package_fingerprint,
        built_at=built_at,
        governance_fingerprint=governance_source.fingerprint,
        gate_fingerprint=gate_source.fingerprint,
        review_record_fingerprint=review_source.fingerprint if review_source else None,
        source_versions=source_versions,
        artifact_filenames=artifact_filenames,
        safety_flags=safety_flags,
    )


__all__ = [
    "build_handoff_safety_flags",
    "build_source_references",
    "classify_handoff_reasons",
    "resolve_handoff_allowed",
    "build_handoff_manifest",
]
