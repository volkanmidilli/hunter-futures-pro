"""Tests for hunter.audit_scorecard.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.audit_scorecard import (
    AuditScorecardConfig,
    AuditScorecardDataQuality,
    AuditScorecardDimension,
    AuditScorecardDimensionResult,
    AuditScorecardDimensionState,
    AuditScorecardEvidenceRef,
    AuditScorecardFinding,
    AuditScorecardInput,
    AuditScorecardLink,
    AuditScorecardLinkType,
    AuditScorecardReasonCode,
    AuditScorecardReport,
    AuditScorecardSafetyFlags,
    AuditScorecardSeverity,
    AuditScorecardState,
    FORBIDDEN_AUDIT_SCORECARD_TERMS,
    has_unsafe_audit_scorecard_content,
)


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


def test_state_enum_values() -> None:
    assert AuditScorecardState.OK.value == "ok"
    assert AuditScorecardState.DEGRADED.value == "degraded"
    assert AuditScorecardState.BLOCKED.value == "blocked"
    assert AuditScorecardState.NOT_APPLICABLE.value == "not_applicable"


def test_dimension_state_enum_values() -> None:
    expected = {"complete", "partial", "missing", "blocked", "degraded", "not_applicable"}
    assert {s.value for s in AuditScorecardDimensionState} == expected


def test_severity_enum_values() -> None:
    assert AuditScorecardSeverity.ADVISORY.value == "advisory"
    assert AuditScorecardSeverity.BLOCKING.value == "blocking"


def test_link_type_enum_values() -> None:
    expected = {"covers", "supports", "contradicts", "manually_reviewed", "derived_from"}
    assert {lt.value for lt in AuditScorecardLinkType} == expected


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


def test_safety_flags_baseline_invariants() -> None:
    with pytest.raises(ValueError, match="baseline safety invariants"):
        AuditScorecardSafetyFlags(research_only=False)


def test_safety_flags_is_safe_reflects_negative_states() -> None:
    safe = AuditScorecardSafetyFlags()
    assert safe.is_safe is True
    degraded = AuditScorecardSafetyFlags(has_degraded=True)
    assert degraded.is_safe is False


# ---------------------------------------------------------------------------
# Dimension
# ---------------------------------------------------------------------------


def test_dimension_defaults() -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D")
    assert dim.severity is AuditScorecardSeverity.BLOCKING
    assert dim.required is True
    assert dim.not_applicable is False
    assert dim.requires_manual_review is False
    assert dim.upstream_package_ids == ()
    assert dim.upstream_report_ids == ()
    assert dim.expected_evidence_count is None
    assert dim.required_link_types == ()


def test_dimension_not_applicable_field() -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D", not_applicable=True)
    assert dim.not_applicable is True


def test_dimension_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="dimension_id"):
        AuditScorecardDimension(dimension_id="", title="T", description="D")


# ---------------------------------------------------------------------------
# Dimension result
# ---------------------------------------------------------------------------


def test_dimension_result_validates_completeness_percent() -> None:
    with pytest.raises(ValueError, match="completeness_percent"):
        AuditScorecardDimensionResult(
            dimension_id="dim_1",
            dimension_state=AuditScorecardDimensionState.COMPLETE,
            severity=AuditScorecardSeverity.BLOCKING,
            completeness_percent=101,
            evidence_count=0,
            finding_count=0,
        )


# ---------------------------------------------------------------------------
# Evidence ref
# ---------------------------------------------------------------------------


def test_evidence_ref_defaults() -> None:
    ref = AuditScorecardEvidenceRef(evidence_id="ev_1", reference="data/ev.json")
    assert ref.label == ""
    assert ref.message == ""
    assert ref.requires_manual_review is False


def test_evidence_ref_rejects_empty_reference() -> None:
    with pytest.raises(ValueError, match="reference"):
        AuditScorecardEvidenceRef(evidence_id="ev_1", reference="")


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------


def test_finding_defaults() -> None:
    finding = AuditScorecardFinding(
        finding_id="f_1",
        dimension_id="dim_1",
        severity=AuditScorecardSeverity.ADVISORY,
        reason_code=AuditScorecardReasonCode.OK,
    )
    assert finding.message == ""
    assert finding.evidence == ()


# ---------------------------------------------------------------------------
# Link
# ---------------------------------------------------------------------------


def test_link_defaults() -> None:
    link = AuditScorecardLink(
        link_id="l1",
        source_id="ev_1",
        target_id="dim_1",
        link_type=AuditScorecardLinkType.COVERS,
    )
    assert link.label == ""
    assert link.message == ""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_config_path_order() -> None:
    cfg = AuditScorecardConfig()
    assert cfg.default_json_path == "data/audit_scorecard/audit_scorecard.json"
    assert cfg.default_csv_path == "data/audit_scorecard/audit_scorecard_dimensions.csv"
    assert cfg.default_markdown_path == "reports/audit_scorecard/audit_scorecard.md"


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


def test_input_validates_naive_datetime() -> None:
    naive = datetime.now()
    with pytest.raises(ValueError, match="timezone-aware"):
        AuditScorecardInput(
            dimensions=(AuditScorecardDimension(dimension_id="a", title="T", description="D"),),
            generated_at=naive,
        )


def test_input_normalizes_lists() -> None:
    inp = AuditScorecardInput(
        dimensions=[AuditScorecardDimension(dimension_id="a", title="T", description="D")],
        generated_at=datetime.now(timezone.utc),
    )
    assert isinstance(inp.dimensions, tuple)


def test_input_includes_metadata() -> None:
    inp = AuditScorecardInput(
        dimensions=(AuditScorecardDimension(dimension_id="a", title="T", description="D"),),
        metadata={"key": "value"},
        generated_at=datetime.now(timezone.utc),
    )
    assert dict(inp.metadata) == {"key": "value"}


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------


def test_data_quality_validates_counts() -> None:
    with pytest.raises(ValueError, match="dimension_count"):
        AuditScorecardDataQuality(
            dimension_count=-1,
            evidence_count=0,
            finding_count=0,
            link_count=0,
            sections_present=1,
            state_distribution={},
        )


# ---------------------------------------------------------------------------
# Forbidden term helper
# ---------------------------------------------------------------------------


def test_has_unsafe_content_detects_forbidden_term() -> None:
    assert has_unsafe_audit_scorecard_content(text="This is production ready.") is True


def test_has_unsafe_content_allows_safe_text() -> None:
    assert (
        has_unsafe_audit_scorecard_content(text="This is research-only output, not trading advice.")
        is False
    )


def test_has_unsafe_content_detects_metadata() -> None:
    assert has_unsafe_audit_scorecard_content(metadata={"note": "This is production ready"}) is True


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


def test_frozen_dataclasses_reject_mutation() -> None:
    dim = AuditScorecardDimension(dimension_id="a", title="T", description="D")
    with pytest.raises(AttributeError):
        dim.dimension_id = "b"


# ---------------------------------------------------------------------------
# Report blocked classmethod
# ---------------------------------------------------------------------------


def test_blocked_report_is_valid_minimal() -> None:
    inp = AuditScorecardInput(
        dimensions=(AuditScorecardDimension(dimension_id="a", title="T", description="D"),),
        generated_at=datetime.now(timezone.utc),
    )
    report = AuditScorecardReport.blocked(
        input=inp,
        reason_code=AuditScorecardReasonCode.DUPLICATE_DIMENSION_ID,
    )
    assert report.state is AuditScorecardState.BLOCKED
    assert AuditScorecardReasonCode.SAFETY_BLOCKED in report.reason_codes
    assert AuditScorecardReasonCode.DUPLICATE_DIMENSION_ID in report.reason_codes
    assert report.dimension_results == ()
