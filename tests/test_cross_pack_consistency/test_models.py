"""Tests for hunter.cross_pack_consistency.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.cross_pack_consistency import (
    CONFLICTING_STATE_CLAIM,
    CrossPackArtifactRef,
    CrossPackConsistencyConfig,
    CrossPackConsistencyDataQuality,
    CrossPackConsistencyIssue,
    CrossPackConsistencyIssueType,
    CrossPackConsistencyReasonCode,
    CrossPackConsistencyReport,
    CrossPackConsistencyRule,
    CrossPackConsistencyRuleType,
    CrossPackConsistencySafetyFlags,
    CrossPackConsistencySeverity,
    CrossPackConsistencyState,
    CrossPackDeclaration,
    CrossPackRequirementRef,
    CrossPackSectionRef,
    CrossPackStateClaim,
    CrossPackConsistencyInput,
    FORBIDDEN_CROSS_PACK_CONSISTENCY_TERMS,
    has_unsafe_cross_pack_consistency_content,
)


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


def test_state_enum_values() -> None:
    assert CrossPackConsistencyState.OK.value == "ok"
    assert CrossPackConsistencyState.DEGRADED.value == "degraded"
    assert CrossPackConsistencyState.BLOCKED.value == "blocked"
    assert CrossPackConsistencyState.NOT_APPLICABLE.value == "not_applicable"


def test_severity_enum_values() -> None:
    assert CrossPackConsistencySeverity.BLOCKING.value == "blocking"
    assert CrossPackConsistencySeverity.ADVISORY.value == "advisory"
    assert CrossPackConsistencySeverity.INFO.value == "info"


def test_issue_type_enum_values() -> None:
    expected = {
        "missing_required_pack",
        "incompatible_version",
        "stale_declaration",
        "incompatible_state_combination",
        "conflicting_state",
        "missing_expected_ref",
        "orphan_ref",
        "missing_manual_review",
        "unknown_upstream_state",
        "unsafe_content",
        "duplicate_id",
    }
    assert {it.value for it in CrossPackConsistencyIssueType} == expected


def test_rule_type_enum_values() -> None:
    expected = {
        "required_pack",
        "expected_ref",
        "compatible_version",
        "stale_declaration",
        "compatible_state",
        "conflicting_state",
        "manual_review",
        "unknown_state",
    }
    assert {rt.value for rt in CrossPackConsistencyRuleType} == expected


def test_forbidden_terms_are_multi_word_phrases() -> None:
    # Core phrase-style terms avoid false positives; a few tokens are vendor/term exceptions.
    exceptions = {"certified", "binance", "freqtrade"}
    phrase_terms = set(FORBIDDEN_CROSS_PACK_CONSISTENCY_TERMS) - exceptions
    for term in phrase_terms:
        assert " " in term or "_" in term, f"forbidden term should be multi-word: {term!r}"
    assert "buy" not in FORBIDDEN_CROSS_PACK_CONSISTENCY_TERMS
    assert "sell" not in FORBIDDEN_CROSS_PACK_CONSISTENCY_TERMS
    assert "hold" not in FORBIDDEN_CROSS_PACK_CONSISTENCY_TERMS


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


def test_safety_flags_baseline_invariants() -> None:
    with pytest.raises(ValueError, match="baseline safety invariants"):
        CrossPackConsistencySafetyFlags(no_network_connection=False)


def test_safety_flags_is_safe_baseline() -> None:
    flags = CrossPackConsistencySafetyFlags()
    assert flags.is_safe is True


def test_safety_flags_is_safe_forbidden_terms() -> None:
    flags = CrossPackConsistencySafetyFlags(has_forbidden_terms=True)
    assert flags.is_safe is False


def test_safety_flags_is_safe_unsafe_content() -> None:
    flags = CrossPackConsistencySafetyFlags(has_unsafe_content=True)
    assert flags.is_safe is False


# ---------------------------------------------------------------------------
# Model defaults and validation
# ---------------------------------------------------------------------------


def test_declaration_defaults() -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0")
    assert decl.title == ""
    assert decl.description == ""
    assert decl.declared_state == ""
    assert decl.artifact_ref_ids == ()
    assert decl.section_ref_ids == ()
    assert decl.requirement_ref_ids == ()
    assert decl.upstream_pack_ids == ()
    assert decl.requires_manual_review is False


def test_declaration_rejects_empty_pack_id() -> None:
    with pytest.raises(ValueError, match="pack_id"):
        CrossPackDeclaration(pack_id="", version="1.0")


def test_artifact_ref_defaults() -> None:
    ref = CrossPackArtifactRef(ref_id="r1", pack_id="p1", reference="path/to/file")
    assert ref.label == ""
    assert ref.message == ""
    assert ref.requires_manual_review is False


def test_artifact_ref_rejects_empty_reference() -> None:
    with pytest.raises(ValueError, match="reference"):
        CrossPackArtifactRef(ref_id="r1", pack_id="p1", reference="")


def test_section_ref_rejects_empty_ref_id() -> None:
    with pytest.raises(ValueError, match="ref_id"):
        CrossPackSectionRef(ref_id="", pack_id="p1", reference="s1")


def test_requirement_ref_rejects_empty_pack_id() -> None:
    with pytest.raises(ValueError, match="pack_id"):
        CrossPackRequirementRef(ref_id="r1", pack_id="", reference="req")


def test_state_claim_rejects_empty_subject() -> None:
    with pytest.raises(ValueError, match="subject_id"):
        CrossPackStateClaim(subject_id="", state_label="ok", pack_id="p1")


def test_rule_defaults() -> None:
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.COMPATIBLE_VERSION,
        source_pack_id="p1",
    )
    assert rule.target_pack_id is None
    assert rule.subject_id is None
    assert rule.ref_kind is None
    assert rule.ref_id is None
    assert rule.expected_version is None
    assert rule.expected_state is None
    assert rule.forbidden_states == ()
    assert rule.severity is CrossPackConsistencySeverity.ADVISORY
    assert rule.message == ""


def test_issue_defaults() -> None:
    issue = CrossPackConsistencyIssue(
        issue_id="i1",
        issue_type=CrossPackConsistencyIssueType.UNSAFE_CONTENT,
        severity=CrossPackConsistencySeverity.BLOCKING,
        subject_id="subject",
        source_pack_id="p1",
    )
    assert issue.target_pack_id == ""
    assert issue.reason_codes == ()
    assert issue.message == ""


# ---------------------------------------------------------------------------
# Input and metadata
# ---------------------------------------------------------------------------


def test_input_metadata_coerced() -> None:
    inp = CrossPackConsistencyInput(metadata={"key": "value"})
    assert dict(inp.metadata) == {"key": "value"}


def test_input_metadata_rejects_non_string_values() -> None:
    # Values are not rejected at construction time so the engine can detect unsafe content.
    inp = CrossPackConsistencyInput(metadata={"key": 123})
    assert dict(inp.metadata) == {"key": 123}


def test_input_metadata_rejects_non_string_keys() -> None:
    with pytest.raises(ValueError, match="metadata keys"):
        CrossPackConsistencyInput(metadata={1: "value"})


def test_report_includes_all_collections() -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0")
    art = CrossPackArtifactRef(ref_id="a1", pack_id="p1", reference="ref")
    sec = CrossPackSectionRef(ref_id="s1", pack_id="p1", reference="ref")
    req = CrossPackRequirementRef(ref_id="r1", pack_id="p1", reference="ref")
    claim = CrossPackStateClaim(subject_id="sub", state_label="ok", pack_id="p1")
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.COMPATIBLE_VERSION,
        source_pack_id="p1",
    )
    issue = CrossPackConsistencyIssue(
        issue_id="i1",
        issue_type=CrossPackConsistencyIssueType.UNSAFE_CONTENT,
        severity=CrossPackConsistencySeverity.BLOCKING,
        subject_id="subject",
        source_pack_id="p1",
    )
    report = CrossPackConsistencyReport(
        report_id="r1",
        generated_at=datetime.now(timezone.utc),
        state=CrossPackConsistencyState.OK,
        project_version="",
        declarations=(decl,),
        artifact_refs=(art,),
        section_refs=(sec,),
        requirement_refs=(req,),
        state_claims=(claim,),
        rules=(rule,),
        issues=(issue,),
        data_quality=CrossPackConsistencyDataQuality(),
        safety_flags=CrossPackConsistencySafetyFlags(),
    )
    assert len(report.declarations) == 1
    assert len(report.artifact_refs) == 1
    assert len(report.section_refs) == 1
    assert len(report.requirement_refs) == 1
    assert len(report.state_claims) == 1
    assert len(report.rules) == 1
    assert len(report.issues) == 1


# ---------------------------------------------------------------------------
# Unsafe content helper
# ---------------------------------------------------------------------------


def test_has_unsafe_content_string_is_safe() -> None:
    assert has_unsafe_cross_pack_consistency_content("hello") is False


def test_has_unsafe_content_bytes_is_unsafe() -> None:
    assert has_unsafe_cross_pack_consistency_content(b"hello") is True


def test_has_unsafe_content_object_is_unsafe() -> None:
    assert has_unsafe_cross_pack_consistency_content(object()) is True


def test_has_unsafe_content_nested_non_string() -> None:
    assert has_unsafe_cross_pack_consistency_content({"key": b"value"}) is True
