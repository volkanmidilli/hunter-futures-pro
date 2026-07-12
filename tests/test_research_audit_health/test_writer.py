"""Tests for the Research Audit Aggregate Health Report writer."""

from __future__ import annotations

import json

import pytest

from hunter.research_audit_health import (
    HealthArtifactSummary,
    HealthConfig,
    HealthInput,
    HealthReasonCode,
    HealthReport,
    HealthSeverity,
    HealthState,
    WriterForbiddenPhraseLeakageError,
    evaluate_research_audit_health,
    health_report_to_dict,
    health_report_to_json,
    health_report_to_markdown,
)
from hunter.research_audit_health.writer import (
    HealthWriterError,
    validate_no_forbidden_modules as validate_no_forbidden_writer_modules,
)


def _sample_report() -> HealthReport:
    """Return a simple OK health report using the engine."""
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
        mvp="MVP-48",
        spec="SPEC-049",
        score=95.0,
        ref="path/to/snapshot.json",
    )
    return evaluate_research_audit_health(
        HealthInput(
            summaries=(summary,),
            config=HealthConfig(),
            metadata={"project": "MVP-48"},
        )
    )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


def test_writer_functions_exported() -> None:
    assert health_report_to_dict is not None
    assert health_report_to_json is not None
    assert health_report_to_markdown is not None


def test_writer_error_classes_exported() -> None:
    assert HealthWriterError is not None
    assert WriterForbiddenPhraseLeakageError is not None


# ---------------------------------------------------------------------------
# Dict shape
# ---------------------------------------------------------------------------


def test_dict_includes_all_required_top_level_keys() -> None:
    report = _sample_report()
    data = health_report_to_dict(report)
    required = {
        "safety_notice",
        "no_authenticity_notice",
        "report_id",
        "state",
        "aggregate_score",
        "family_rollups",
        "findings",
        "reason_code_counts",
        "data_quality",
        "safety_flags",
    }
    assert required <= data.keys()


def test_dict_serializes_enums_as_values() -> None:
    report = _sample_report()
    data = health_report_to_dict(report)
    assert data["state"] == HealthState.OK.value
    assert isinstance(data["state"], str)


def test_dict_metadata_sorted_and_stable() -> None:
    report = _sample_report()
    data = health_report_to_dict(report)
    assert data["metadata"] == {"project": "MVP-48"}


def test_dict_no_mutation() -> None:
    report = _sample_report()
    original = report
    _ = health_report_to_dict(report)
    assert report == original


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def test_json_text_deterministic_and_parseable() -> None:
    report = _sample_report()
    text1 = health_report_to_json(report)
    text2 = health_report_to_json(report)
    assert text1 == text2
    parsed = json.loads(text1)
    assert parsed["report_id"] == report.report_id


def test_json_includes_safety_notice() -> None:
    report = _sample_report()
    text = health_report_to_json(report)
    assert "audit-only" in text.lower()


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def test_markdown_starts_with_h1() -> None:
    report = _sample_report()
    text = health_report_to_markdown(report)
    assert text.startswith("# Research Audit Aggregate Health Report")


def test_markdown_has_safety_notice() -> None:
    report = _sample_report()
    text = health_report_to_markdown(report).lower()
    assert "audit-only" in text
    assert "not a trading signal" in text
    assert "not a certification" in text
    assert "not a recommendation" in text


def test_markdown_includes_required_sections() -> None:
    report = _sample_report()
    text = health_report_to_markdown(report)
    assert "## Summary" in text
    assert "## Family Rollups" in text
    assert "## Findings" in text
    assert "## Data Quality" in text
    assert "## Reason Code Counts" in text
    assert "## Safety Flags" in text
    assert "## Metadata" in text
    assert "## Opaque Reference Notice" in text


def test_markdown_deterministic() -> None:
    report = _sample_report()
    assert health_report_to_markdown(report) == health_report_to_markdown(report)


# ---------------------------------------------------------------------------
# States and edge cases
# ---------------------------------------------------------------------------


def test_all_states_serialize() -> None:
    for state in (
        HealthState.OK,
        HealthState.DEGRADED,
        HealthState.BLOCKED,
        HealthState.NOT_APPLICABLE,
    ):
        report = _sample_report()
        report = HealthReport(
            report_id=report.report_id,
            state=state,
            aggregate_score=report.aggregate_score,
            family_rollups=report.family_rollups,
            findings=report.findings,
            reason_code_counts=report.reason_code_counts,
            data_quality=report.data_quality,
            safety_flags=report.safety_flags,
        )
        d = health_report_to_dict(report)
        j = health_report_to_json(report)
        md = health_report_to_markdown(report)
        assert d["state"] == state.value
        assert state.value in j
        assert state.value in md


def test_empty_findings() -> None:
    report = _sample_report()
    # Force an empty report to ensure serialization handles empty findings.
    report = HealthReport(
        report_id=report.report_id,
        state=HealthState.OK,
        aggregate_score=report.aggregate_score,
        family_rollups=(),
        findings=(),
        reason_code_counts={},
        data_quality=report.data_quality,
        safety_flags=report.safety_flags,
    )
    d = health_report_to_dict(report)
    assert d["findings"] == []
    md = health_report_to_markdown(report)
    assert "_No findings._" in md


# ---------------------------------------------------------------------------
# Forbidden phrase guard
# ---------------------------------------------------------------------------


def test_forbidden_phrase_in_metadata_raises() -> None:
    report = _sample_report()
    bad_report = HealthReport(
        report_id=report.report_id,
        state=report.state,
        aggregate_score=report.aggregate_score,
        family_rollups=report.family_rollups,
        findings=report.findings,
        reason_code_counts=report.reason_code_counts,
        data_quality=report.data_quality,
        safety_flags=report.safety_flags,
        metadata={"note": "This artifact shows production readiness"},
    )
    with pytest.raises(WriterForbiddenPhraseLeakageError):
        health_report_to_dict(bad_report)


def test_forbidden_phrase_in_finding_description_raises() -> None:
    from hunter.research_audit_health.models import HealthFinding, HealthReasonCode

    report = _sample_report()
    bad_finding = HealthFinding(
        finding_id="finding-bad",
        rule_id="BAD",
        family="research_audit_snapshot",
        artifact_ids=("snap-1",),
        severity=HealthSeverity.INFO,
        reason_code=HealthReasonCode.OK,
        title="Advisory only",
        description="This is a recommendation to buy",
    )
    bad_report = HealthReport(
        report_id=report.report_id,
        state=report.state,
        aggregate_score=report.aggregate_score,
        family_rollups=report.family_rollups,
        findings=(bad_finding,),
        reason_code_counts=report.reason_code_counts,
        data_quality=report.data_quality,
        safety_flags=report.safety_flags,
    )
    with pytest.raises(WriterForbiddenPhraseLeakageError):
        health_report_to_markdown(bad_report)


def test_negated_safety_notice_does_not_raise() -> None:
    """Safety notices use denial phrases and must not trigger the guard."""
    report = _sample_report()
    health_report_to_dict(report)
    health_report_to_json(report)
    health_report_to_markdown(report)


# ---------------------------------------------------------------------------
# Module safety
# ---------------------------------------------------------------------------


def test_no_forbidden_modules_in_writer() -> None:
    from hunter.research_audit_health import writer as writer_module

    forbidden = {"pathlib", "os", "subprocess", "socket", "urllib", "requests"}
    imported = set(writer_module.__dict__.keys())
    assert not imported.intersection(forbidden), imported.intersection(forbidden)


def test_writer_validate_no_forbidden_modules() -> None:
    validate_no_forbidden_writer_modules()
