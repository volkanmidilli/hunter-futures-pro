"""Tests for hunter.evidence_traceability.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.evidence_traceability.engine import (
    has_unsafe_evidence_traceability_content,
)
from hunter.evidence_traceability.models import (
    UNSAFE_CONTENT,
    EVIDENCE_TRACEABILITY_BLOCKING_REASON_CODES,
    EVIDENCE_TRACEABILITY_REASON_CODES,
    EvidenceArtifactRef,
    EvidenceCheck,
    EvidenceLink,
    EvidenceRequirement,
    EvidenceSectionRef,
    EvidenceTraceabilityConfig,
    EvidenceTraceabilityCoverageState,
    EvidenceTraceabilityDataQuality,
    EvidenceTraceabilityInput,
    EvidenceTraceabilityLinkType,
    EvidenceTraceabilityReasonCode,
    EvidenceTraceabilityReport,
    EvidenceTraceabilitySafetyFlags,
    EvidenceTraceabilitySeverity,
    EvidenceTraceabilityState,
    FORBIDDEN_EVIDENCE_TRACEABILITY_TERMS,
)


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


def test_state_enum_values() -> None:
    assert EvidenceTraceabilityState.OK.value == "ok"
    assert EvidenceTraceabilityState.DEGRADED.value == "degraded"
    assert EvidenceTraceabilityState.BLOCKED.value == "blocked"
    assert EvidenceTraceabilityState.NOT_APPLICABLE.value == "not_applicable"


def test_reason_code_enum_values() -> None:
    assert EvidenceTraceabilityReasonCode.OK.value == "ok"
    assert EvidenceTraceabilityReasonCode.NOT_APPLICABLE.value == "not_applicable"
    assert EvidenceTraceabilityReasonCode.CONSISTENCY_DEGRADED.value == "consistency_degraded"
    assert EvidenceTraceabilityReasonCode.SAFETY_BLOCKED.value == "safety_blocked"


def test_severity_enum_values() -> None:
    assert EvidenceTraceabilitySeverity.ADVISORY.value == "advisory"
    assert EvidenceTraceabilitySeverity.BLOCKING.value == "blocking"


def test_link_type_enum_values() -> None:
    expected = {
        "covered_by",
        "supports",
        "contradicts",
        "manually_reviewed",
        "derived_from",
    }
    assert {lt.value for lt in EvidenceTraceabilityLinkType} == expected


def test_coverage_state_enum_values() -> None:
    expected = {"covered", "partial", "missing", "not_applicable"}
    assert {cs.value for cs in EvidenceTraceabilityCoverageState} == expected


def test_blocking_reason_codes_are_subset() -> None:
    assert EVIDENCE_TRACEABILITY_BLOCKING_REASON_CODES <= set(EVIDENCE_TRACEABILITY_REASON_CODES)
    assert UNSAFE_CONTENT in EVIDENCE_TRACEABILITY_BLOCKING_REASON_CODES


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


def test_safety_flags_baseline_invariants() -> None:
    with pytest.raises(ValueError, match="baseline safety invariants"):
        EvidenceTraceabilitySafetyFlags(research_only=False)


def test_safety_flags_is_safe_reflects_negative_states() -> None:
    safe = EvidenceTraceabilitySafetyFlags()
    assert safe.is_safe is True
    degraded = EvidenceTraceabilitySafetyFlags(has_degraded=True)
    assert degraded.is_safe is False


# ---------------------------------------------------------------------------
# Requirement
# ---------------------------------------------------------------------------


def test_requirement_defaults() -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    assert req.title == ""
    assert req.required_link_types == ()
    assert req.severity is EvidenceTraceabilitySeverity.BLOCKING


def test_requirement_normalizes_lists() -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Desc",
        required_link_types=["covered_by"],
    )
    assert isinstance(req.required_link_types, tuple)
    assert req.required_link_types == ("covered_by",)


def test_requirement_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="requirement_id"):
        EvidenceRequirement(requirement_id="", description="Desc")


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------


def test_check_defaults() -> None:
    check = EvidenceCheck(check_id="check_1", description="Desc")
    assert check.title == ""
    assert check.covers_requirement_ids == ()


def test_check_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="check_id"):
        EvidenceCheck(check_id="", description="Desc")


# ---------------------------------------------------------------------------
# Artifact and section refs
# ---------------------------------------------------------------------------


def test_artifact_ref_defaults() -> None:
    art = EvidenceArtifactRef(artifact_id="art_1", reference="data/art.json")
    assert art.label == ""
    assert art.message == ""
    assert art.requires_manual_review is False


def test_artifact_ref_rejects_empty_reference() -> None:
    with pytest.raises(ValueError, match="reference"):
        EvidenceArtifactRef(artifact_id="art_1", reference="")


def test_section_ref_defaults() -> None:
    sec = EvidenceSectionRef(section_id="sec_1", reference="reports/sec.md")
    assert sec.label == ""
    assert sec.message == ""


# ---------------------------------------------------------------------------
# Link
# ---------------------------------------------------------------------------


def test_link_defaults() -> None:
    link = EvidenceLink(
        link_id="link_1",
        source_id="req_1",
        target_id="check_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    assert link.label == ""
    assert link.message == ""
    assert link.severity is EvidenceTraceabilitySeverity.BLOCKING


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------


def test_data_quality_counts_must_sum() -> None:
    with pytest.raises(ValueError, match="state counts must sum"):
        EvidenceTraceabilityDataQuality(
            total_items=3,
            ok_count=2,
            degraded_count=0,
            blocked_count=0,
            not_applicable_count=0,
            requirement_count=1,
            check_count=0,
            artifact_count=0,
            section_count=0,
            link_count=0,
        )


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


def test_input_validates_naive_datetime() -> None:
    naive = datetime.now()
    with pytest.raises(ValueError, match="timezone-aware"):
        EvidenceTraceabilityInput(
            requirements=(EvidenceRequirement(requirement_id="a", description="d"),),
            generated_at=naive,
        )


def test_input_normalizes_lists() -> None:
    inp = EvidenceTraceabilityInput(
        requirements=[EvidenceRequirement(requirement_id="a", description="d")],
        generated_at=datetime.now(timezone.utc),
    )
    assert isinstance(inp.requirements, tuple)


# ---------------------------------------------------------------------------
# Forbidden term helper
# ---------------------------------------------------------------------------


def test_has_unsafe_content_detects_forbidden_term() -> None:
    assert has_unsafe_evidence_traceability_content(text="This is production ready.") is True


def test_has_unsafe_content_allows_safe_text() -> None:
    assert (
        has_unsafe_evidence_traceability_content(text="This is research-only output, not trading advice.")
        is False
    )


def test_has_unsafe_content_detects_metadata() -> None:
    assert (
        has_unsafe_evidence_traceability_content(metadata={"note": "This is production ready"})
        is True
    )


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


def test_frozen_dataclasses_reject_mutation() -> None:
    req = EvidenceRequirement(requirement_id="a", description="d")
    with pytest.raises(AttributeError):
        req.requirement_id = "b"


# ---------------------------------------------------------------------------
# Report blocked classmethod
# ---------------------------------------------------------------------------


def test_blocked_report_is_valid_minimal() -> None:
    inp = EvidenceTraceabilityInput(
        requirements=(EvidenceRequirement(requirement_id="a", description="d"),),
        generated_at=datetime.now(timezone.utc),
    )
    report = EvidenceTraceabilityReport.blocked(
        input=inp,
        reason_code=EvidenceTraceabilityReasonCode.DUPLICATE_REQUIREMENT_ID,
    )
    assert report.state is EvidenceTraceabilityState.BLOCKED
    assert EvidenceTraceabilityReasonCode.SAFETY_BLOCKED in report.reason_codes
    assert EvidenceTraceabilityReasonCode.DUPLICATE_REQUIREMENT_ID in report.reason_codes
    assert report.results == ()
    assert report.links == ()
    assert report.data_quality.total_items == 0
