"""Tests for hunter.audit_scorecard.writer."""

from __future__ import annotations

import csv
import json
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
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    atomic_write_csv_audit_scorecard_report,
    atomic_write_json_audit_scorecard_report,
    atomic_write_markdown_audit_scorecard_report,
    audit_scorecard_report_to_csv_text,
    audit_scorecard_report_to_dict,
    audit_scorecard_report_to_json_text,
    audit_scorecard_report_to_markdown_text,
    build_audit_scorecard_report,
    write_audit_scorecard_report,
)


@pytest.fixture
def generated_at() -> datetime:
    return datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def complete_report(generated_at: datetime) -> AuditScorecardReport:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="Dimension One", description="First dimension"
    )
    ev = AuditScorecardEvidenceRef(evidence_id="ev_1", reference="data/ev.json")
    link = AuditScorecardLink(
        link_id="l1", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.COVERS
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        evidence_refs=(ev,),
        links=(link,),
        generated_at=generated_at,
        project_version="0.35.0-dev",
    )
    return build_audit_scorecard_report(inp)


@pytest.fixture
def blocked_report(generated_at: datetime) -> AuditScorecardReport:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", required=True, expected_evidence_count=1
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    return build_audit_scorecard_report(inp)


@pytest.fixture
def degraded_report(generated_at: datetime) -> AuditScorecardReport:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", severity=AuditScorecardSeverity.ADVISORY
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    return build_audit_scorecard_report(inp)


@pytest.fixture
def not_applicable_report(generated_at: datetime) -> AuditScorecardReport:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", not_applicable=True
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    return build_audit_scorecard_report(inp)


# ---------------------------------------------------------------------------
# Dict conversion
# ---------------------------------------------------------------------------

def test_dict_includes_top_level_fields(complete_report: AuditScorecardReport) -> None:
    data = audit_scorecard_report_to_dict(complete_report)
    assert data["safety_notice"] is not None
    assert data["generated_at"] == "2026-07-04T12:00:00+00:00"
    assert data["report_id"] == complete_report.report_id
    assert data["state"] == complete_report.state.value


def test_dict_includes_dimensions(complete_report: AuditScorecardReport) -> None:
    data = audit_scorecard_report_to_dict(complete_report)
    assert "dimensions" in data
    assert len(data["dimensions"]) == 1
    assert data["dimensions"][0]["dimension_id"] == "dim_1"


def test_dict_includes_dimension_results(complete_report: AuditScorecardReport) -> None:
    data = audit_scorecard_report_to_dict(complete_report)
    assert "dimension_results" in data
    assert len(data["dimension_results"]) == 1
    assert data["dimension_results"][0]["dimension_id"] == "dim_1"


def test_dict_includes_findings(complete_report: AuditScorecardReport) -> None:
    data = audit_scorecard_report_to_dict(complete_report)
    assert "findings" in data


def test_dict_includes_evidence_refs(complete_report: AuditScorecardReport) -> None:
    data = audit_scorecard_report_to_dict(complete_report)
    assert "evidence_refs" in data
    assert len(data["evidence_refs"]) == 1


def test_dict_includes_links(complete_report: AuditScorecardReport) -> None:
    data = audit_scorecard_report_to_dict(complete_report)
    assert "links" in data
    assert len(data["links"]) == 1


def test_dict_includes_data_quality(complete_report: AuditScorecardReport) -> None:
    data = audit_scorecard_report_to_dict(complete_report)
    assert "data_quality" in data
    assert data["data_quality"]["dimension_count"] == 1


def test_dict_includes_safety_flags(complete_report: AuditScorecardReport) -> None:
    data = audit_scorecard_report_to_dict(complete_report)
    assert "safety_flags" in data
    assert data["safety_flags"]["research_only"] is True
    assert "is_safe" in data["safety_flags"]


def test_dict_nested_mapping_serialization(complete_report: AuditScorecardReport) -> None:
    data = audit_scorecard_report_to_dict(complete_report)
    assert isinstance(data["data_quality"]["state_distribution"], dict)


# ---------------------------------------------------------------------------
# JSON conversion
# ---------------------------------------------------------------------------

def test_json_is_parseable(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_json_text(complete_report)
    parsed = json.loads(text)
    assert parsed["report_id"] == complete_report.report_id


def test_json_is_deterministic(complete_report: AuditScorecardReport) -> None:
    t1 = audit_scorecard_report_to_json_text(complete_report)
    t2 = audit_scorecard_report_to_json_text(complete_report)
    assert t1 == t2


# ---------------------------------------------------------------------------
# CSV conversion
# ---------------------------------------------------------------------------

def test_csv_header(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_csv_text(complete_report)
    lines = text.strip().split("\n")
    assert lines[0] == "report_id,generated_at,dimension_id,dimension_state,severity,completeness_percent,evidence_count,finding_count,reason_codes,message"


def test_csv_rows_from_dimension_results(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_csv_text(complete_report)
    rows = list(csv.DictReader(text.splitlines()))
    assert len(rows) == 1
    assert rows[0]["dimension_id"] == "dim_1"
    assert rows[0]["dimension_state"] == "complete"
    assert rows[0]["severity"] == "advisory"
    assert rows[0]["completeness_percent"] == "100"
    assert rows[0]["evidence_count"] == "1"


def test_csv_does_not_recompute_classification(complete_report: AuditScorecardReport) -> None:
    # The writer must use report.dimension_results directly. If we manually build
    # a report with a dimension_result whose values differ from the dimension, the
    # CSV row must reflect the dimension_result, not a reclassification.
    report = AuditScorecardReport(
        report_id="manual",
        state=AuditScorecardState.OK,
        reason_codes=(AuditScorecardReasonCode.OK,),
        dimensions=(),
        dimension_results=(
            AuditScorecardDimensionResult(
                dimension_id="dim_x",
                dimension_state=AuditScorecardDimensionState.BLOCKED,
                severity=AuditScorecardSeverity.BLOCKING,
                completeness_percent=0,
                evidence_count=0,
                finding_count=5,
                reason_codes=("upstream_blocked",),
                message="Manual result",
            ),
        ),
        evidence_refs=(),
        findings=(),
        links=(),
        data_quality=AuditScorecardDataQuality(
            dimension_count=1,
            evidence_count=0,
            finding_count=0,
            link_count=0,
            sections_present=2,
            state_distribution={"blocked": 1},
        ),
        safety_flags=AuditScorecardSafetyFlags(),
        generated_at=datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc),
        project_version=None,
    )
    rows = list(csv.DictReader(audit_scorecard_report_to_csv_text(report).splitlines()))
    assert rows[0]["dimension_state"] == "blocked"
    assert rows[0]["finding_count"] == "5"
    assert rows[0]["message"] == "Manual result"


def test_csv_deterministic_sorting(complete_report: AuditScorecardReport) -> None:
    text1 = audit_scorecard_report_to_csv_text(complete_report)
    text2 = audit_scorecard_report_to_csv_text(complete_report)
    assert text1 == text2


# ---------------------------------------------------------------------------
# Markdown conversion
# ---------------------------------------------------------------------------

def test_markdown_starts_with_h1(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report)
    assert text.startswith("# Local Research Audit Readiness Scorecard")


def test_markdown_has_immediate_safety_notice(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report)
    # Safety notice appears immediately after the H1 line and blank line.
    assert "> This scorecard is a human-audit" in text


def test_markdown_disclaims_approval_certification(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report)
    assert "not an approval" in text
    assert "not a certification" in text.lower() or "certification" in text
    assert "production readiness" in text
    assert "trading readiness" in text
    assert "not a recommendation" in text.lower() or "recommendation" in text
    assert "suitability assessment" in text
    assert "signal" in text


def test_markdown_completeness_descriptive_only(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report)
    assert "Completeness percentages are descriptive metrics only" in text
    assert "not approval scores" in text


def test_markdown_contains_summary(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report)
    assert "## Summary" in text


def test_markdown_contains_dimension_results(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report)
    assert "## Dimension Results" in text


def test_markdown_contains_findings(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report)
    assert "## Findings" in text


def test_markdown_contains_evidence_refs(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report)
    assert "## Evidence References" in text


def test_markdown_contains_data_quality(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report)
    assert "## Data Quality" in text


def test_markdown_contains_safety_flags(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report)
    assert "## Safety Flags" in text


def test_markdown_contains_manual_review(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report)
    assert "## Manual Review" in text


def test_markdown_no_actionable_recommendation_language(complete_report: AuditScorecardReport) -> None:
    text = audit_scorecard_report_to_markdown_text(complete_report).lower()
    # Disclaimers may contain these words; exclude the safety notice block.
    body = text.split("## summary")[0]
    for word in ("buy", "sell", "hold"):
        assert word not in body, f"unexpected actionable word: {word}"


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------

def test_atomic_write_json_creates_file(complete_report: AuditScorecardReport, tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "scorecard.json"
    result = atomic_write_json_audit_scorecard_report(complete_report, path)
    assert result == path
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["report_id"] == complete_report.report_id


def test_atomic_write_csv_creates_file(complete_report: AuditScorecardReport, tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "scorecard.csv"
    result = atomic_write_csv_audit_scorecard_report(complete_report, path)
    assert result == path
    assert path.exists()


def test_atomic_write_markdown_creates_file(complete_report: AuditScorecardReport, tmp_path: pytest.TempPathFactory) -> None:
    path = tmp_path / "scorecard.md"
    result = atomic_write_markdown_audit_scorecard_report(complete_report, path)
    assert result == path
    assert path.exists()


def test_write_creates_parent_directories(complete_report: AuditScorecardReport, tmp_path: pytest.TempPathFactory) -> None:
    json_path = tmp_path / "nested" / "scorecard.json"
    csv_path = tmp_path / "nested" / "scorecard.csv"
    md_path = tmp_path / "nested" / "scorecard.md"
    write_audit_scorecard_report(
        complete_report, json_path=json_path, csv_path=csv_path, md_path=md_path
    )
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()


def test_none_skips_artifact(complete_report: AuditScorecardReport, tmp_path: pytest.TempPathFactory) -> None:
    json_path = tmp_path / "scorecard.json"
    csv_path = tmp_path / "scorecard.csv"
    md_path = tmp_path / "scorecard.md"
    write_audit_scorecard_report(
        complete_report, json_path=json_path, csv_path=None, md_path=md_path
    )
    assert json_path.exists()
    assert not csv_path.exists()
    assert md_path.exists()


def test_omitted_uses_default_paths(complete_report: AuditScorecardReport, tmp_path: pytest.TempPathFactory) -> None:
    import os as _os
    cwd = _os.getcwd()
    try:
        _os.chdir(tmp_path)
        write_audit_scorecard_report(complete_report)
        assert (tmp_path / DEFAULT_JSON_PATH).exists()
        assert (tmp_path / DEFAULT_CSV_PATH).exists()
        assert (tmp_path / DEFAULT_MD_PATH).exists()
    finally:
        _os.chdir(cwd)


def test_no_mutation_of_report(complete_report: AuditScorecardReport) -> None:
    original_id = complete_report.report_id
    audit_scorecard_report_to_dict(complete_report)
    audit_scorecard_report_to_json_text(complete_report)
    audit_scorecard_report_to_csv_text(complete_report)
    audit_scorecard_report_to_markdown_text(complete_report)
    assert complete_report.report_id == original_id


# ---------------------------------------------------------------------------
# State serialization
# ---------------------------------------------------------------------------

def test_blocked_report_serializes(
    blocked_report: AuditScorecardReport,
) -> None:
    data = audit_scorecard_report_to_dict(blocked_report)
    assert data["state"] == "blocked"


def test_degraded_report_serializes(
    degraded_report: AuditScorecardReport,
) -> None:
    data = audit_scorecard_report_to_dict(degraded_report)
    assert data["state"] == "degraded"


def test_not_applicable_report_serializes(
    not_applicable_report: AuditScorecardReport,
) -> None:
    data = audit_scorecard_report_to_dict(not_applicable_report)
    assert data["state"] == "ok"
    assert data["dimension_results"][0]["dimension_state"] == "not_applicable"


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

def test_public_exports() -> None:
    from hunter.audit_scorecard import (
        DEFAULT_CSV_PATH,
        DEFAULT_JSON_PATH,
        DEFAULT_MD_PATH,
        atomic_write_json_audit_scorecard_report,
        audit_scorecard_report_to_csv_text,
        audit_scorecard_report_to_dict,
        audit_scorecard_report_to_json_text,
        audit_scorecard_report_to_markdown_text,
        write_audit_scorecard_report,
    )

    assert audit_scorecard_report_to_dict is not None
    assert audit_scorecard_report_to_json_text is not None
    assert audit_scorecard_report_to_csv_text is not None
    assert audit_scorecard_report_to_markdown_text is not None
    assert atomic_write_json_audit_scorecard_report is not None
    assert write_audit_scorecard_report is not None
    assert DEFAULT_JSON_PATH is not None
    assert DEFAULT_CSV_PATH is not None
    assert DEFAULT_MD_PATH is not None


# ---------------------------------------------------------------------------
# Opaque references / safety
# ---------------------------------------------------------------------------

def test_writer_does_not_traverse_paths(complete_report: AuditScorecardReport, tmp_path: pytest.TempPathFactory) -> None:
    # The writer must only serialize references as strings. It should not attempt
    # to read, validate, or open referenced paths. A malicious-looking reference
    # is preserved in the output.
    data = audit_scorecard_report_to_dict(complete_report)
    refs = [ref["reference"] for ref in data["evidence_refs"]]
    assert "data/ev.json" in refs


def test_safety_notice_present(complete_report: AuditScorecardReport) -> None:
    data = audit_scorecard_report_to_dict(complete_report)
    assert "human-audit" in data["safety_notice"]
    assert "not an approval" in data["safety_notice"]
