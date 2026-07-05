"""Tests for hunter.remediation_backlog.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.remediation_backlog import (
    FORBIDDEN_REMEDIATION_BACKLOG_TERMS,
    RemediationAcknowledgement,
    RemediationBacklogConfig,
    RemediationBacklogDataQuality,
    RemediationDependencyType,
    RemediationFindingRef,
    RemediationBacklogInput,
    RemediationBacklogItem,
    RemediationBacklogItemState,
    RemediationBacklogItemType,
    RemediationBacklogPriority,
    RemediationBacklogReasonCode,
    RemediationBacklogReport,
    RemediationBacklogSafetyFlags,
    RemediationBacklogSeverity,
    RemediationSourceRef,
    RemediationBacklogState,
    RemediationDependency,
    has_unsafe_remediation_backlog_content,
)


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


def test_state_enum_values() -> None:
    assert RemediationBacklogState.OK.value == "ok"
    assert RemediationBacklogState.DEGRADED.value == "degraded"
    assert RemediationBacklogState.BLOCKED.value == "blocked"
    assert RemediationBacklogState.NOT_APPLICABLE.value == "not_applicable"


def test_severity_enum_values() -> None:
    assert RemediationBacklogSeverity.BLOCKING.value == "blocking"
    assert RemediationBacklogSeverity.ADVISORY.value == "advisory"
    assert RemediationBacklogSeverity.INFO.value == "info"


def test_priority_enum_values() -> None:
    assert RemediationBacklogPriority.P0.value == "p0"
    assert RemediationBacklogPriority.P1.value == "p1"
    assert RemediationBacklogPriority.P2.value == "p2"
    assert RemediationBacklogPriority.P3.value == "p3"
    assert RemediationBacklogPriority.NONE.value == "none"


def test_item_state_enum_values() -> None:
    expected = {
        "open",
        "acknowledged",
        "blocked",
        "deferred",
        "duplicate",
        "conflicting",
        "not_applicable",
    }
    assert {s.value for s in RemediationBacklogItemState} == expected


def test_item_type_enum_values() -> None:
    expected = {
        "manual_review",
        "missing_ref",
        "stale_ref",
        "orphan_ref",
        "conflicting_state",
        "incompatible_version",
        "incompatible_state",
        "unsafe_content",
        "duplicate_item",
        "duplicate_id",
        "dependency_cycle",
        "missing_owner",
        "missing_reviewer",
        "missing_manual_review",
        "required_source",
        "unknown_state",
        "acknowledged_item",
    }
    assert {t.value for t in RemediationBacklogItemType} == expected


def test_dependency_type_enum_values() -> None:
    expected = {"blocks", "depends_on", "related_to"}
    assert {t.value for t in RemediationDependencyType} == expected


def test_forbidden_terms_are_multi_word_phrases() -> None:
    for term in FORBIDDEN_REMEDIATION_BACKLOG_TERMS:
        assert " " in term, f"forbidden term must be multi-word phrase: {term!r}"
    assert "approval" not in FORBIDDEN_REMEDIATION_BACKLOG_TERMS
    assert "signal" not in FORBIDDEN_REMEDIATION_BACKLOG_TERMS
    assert "certified" not in FORBIDDEN_REMEDIATION_BACKLOG_TERMS


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


def test_safety_flags_baseline_invariants() -> None:
    with pytest.raises(ValueError, match="baseline safety invariants"):
        RemediationBacklogSafetyFlags(no_executable_actions=False)


def test_safety_flags_is_safe_baseline() -> None:
    flags = RemediationBacklogSafetyFlags()
    assert flags.is_safe is True


def test_safety_flags_is_safe_forbidden_terms() -> None:
    flags = RemediationBacklogSafetyFlags(has_forbidden_terms=True)
    assert flags.is_safe is False


def test_safety_flags_is_safe_unsafe_content() -> None:
    flags = RemediationBacklogSafetyFlags(has_unsafe_content=True)
    assert flags.is_safe is False


# ---------------------------------------------------------------------------
# Model defaults and validation
# ---------------------------------------------------------------------------


def test_source_ref_defaults() -> None:
    ref = RemediationSourceRef(source_id="s1")
    assert ref.source_type == ""
    assert ref.reference == ""
    assert ref.label == ""


def test_source_ref_rejects_empty_source_id() -> None:
    with pytest.raises(ValueError, match="source_id"):
        RemediationSourceRef(source_id="")


def test_finding_ref_rejects_empty_finding_id() -> None:
    with pytest.raises(ValueError, match="finding_id"):
        RemediationFindingRef(finding_id="")


def test_backlog_item_defaults() -> None:
    item = RemediationBacklogItem()
    assert item.item_state is RemediationBacklogItemState.OPEN
    assert item.severity is RemediationBacklogSeverity.ADVISORY
    assert item.priority is RemediationBacklogPriority.NONE
    assert item.title == ""
    assert item.description == ""


def test_backlog_item_accepts_none_ids() -> None:
    item = RemediationBacklogItem(item_id=None, subject_id=None, source_id=None, finding_id=None)
    assert item.item_id is None


def test_dependency_defaults() -> None:
    dep = RemediationDependency(dependency_id="d1", source_item_id="a", target_item_id="b")
    assert dep.dependency_type is RemediationDependencyType.RELATED_TO


def test_dependency_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="dependency_id"):
        RemediationDependency(dependency_id="", source_item_id="a", target_item_id="b")


def test_acknowledgement_defaults() -> None:
    ack = RemediationAcknowledgement(acknowledgement_id="a1", item_id="i1")
    assert ack.note == ""


def test_config_defaults() -> None:
    config = RemediationBacklogConfig()
    assert config.strict is False
    assert config.staleness_threshold_seconds == 86400


def test_config_rejects_negative_staleness() -> None:
    with pytest.raises(ValueError, match="staleness_threshold_seconds"):
        RemediationBacklogConfig(staleness_threshold_seconds=-1)


# ---------------------------------------------------------------------------
# Input and metadata
# ---------------------------------------------------------------------------


def test_input_metadata_coerced() -> None:
    inp = RemediationBacklogInput(metadata={"key": "value"})
    assert dict(inp.metadata) == {"key": "value"}


def test_input_metadata_rejects_non_string_keys() -> None:
    with pytest.raises(ValueError, match="metadata keys"):
        RemediationBacklogInput(metadata={1: "value"})


def test_input_metadata_allows_non_string_values() -> None:
    # Values are not rejected at construction time so the engine can detect unsafe content.
    inp = RemediationBacklogInput(metadata={"key": 123})
    assert dict(inp.metadata) == {"key": 123}


def test_report_includes_all_collections() -> None:
    now = datetime.now(timezone.utc)
    source = RemediationSourceRef(source_id="s1")
    finding = RemediationFindingRef(finding_id="f1")
    item = RemediationBacklogItem(item_id="i1")
    dep = RemediationDependency(dependency_id="d1", source_item_id="i1", target_item_id="i2")
    ack = RemediationAcknowledgement(acknowledgement_id="a1", item_id="i1")
    report = RemediationBacklogReport(
        report_id="r1",
        generated_at=now,
        state=RemediationBacklogState.OK,
        project_version="",
        source_refs=(source,),
        finding_refs=(finding,),
        backlog_items=(item,),
        dependencies=(dep,),
        acknowledgements=(ack,),
        issues=(),
        data_quality=RemediationBacklogDataQuality(),
        safety_flags=RemediationBacklogSafetyFlags(),
    )
    assert len(report.source_refs) == 1
    assert len(report.finding_refs) == 1
    assert len(report.backlog_items) == 1
    assert len(report.dependencies) == 1
    assert len(report.acknowledgements) == 1


# ---------------------------------------------------------------------------
# Unsafe content helper
# ---------------------------------------------------------------------------


def test_has_unsafe_content_string_is_safe() -> None:
    assert has_unsafe_remediation_backlog_content("hello") is False


def test_has_unsafe_content_bytes_is_unsafe() -> None:
    assert has_unsafe_remediation_backlog_content(b"hello") is True


def test_has_unsafe_content_object_is_unsafe() -> None:
    assert has_unsafe_remediation_backlog_content(object()) is True


def test_has_unsafe_content_nested_non_string() -> None:
    assert has_unsafe_remediation_backlog_content({"key": b"value"}) is True


# ---------------------------------------------------------------------------
# Data quality validation
# ---------------------------------------------------------------------------


def test_data_quality_rejects_negative_counter() -> None:
    with pytest.raises(ValueError, match="total_sources"):
        RemediationBacklogDataQuality(total_sources=-1)


def test_data_quality_is_frozen() -> None:
    dq = RemediationBacklogDataQuality(total_sources=1)
    with pytest.raises(AttributeError):
        dq.total_sources = 2
    with pytest.raises(AttributeError):
        dq.total_findings = 5
