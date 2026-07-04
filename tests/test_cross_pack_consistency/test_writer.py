"""Tests for hunter.cross_pack_consistency.writer."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.cross_pack_consistency import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    CrossPackArtifactRef,
    CrossPackConsistencyConfig,
    CrossPackConsistencyIssueType,
    CrossPackConsistencyReasonCode,
    CrossPackConsistencyRule,
    CrossPackConsistencyRuleType,
    CrossPackConsistencySeverity,
    CrossPackConsistencyState,
    CrossPackDeclaration,
    CrossPackRequirementRef,
    CrossPackSectionRef,
    CrossPackStateClaim,
    CrossPackConsistencyInput,
    atomic_write_csv_cross_pack_consistency_report,
    atomic_write_json_cross_pack_consistency_report,
    atomic_write_markdown_cross_pack_consistency_report,
    build_cross_pack_consistency_report,
    cross_pack_consistency_report_to_csv_text,
    cross_pack_consistency_report_to_dict,
    cross_pack_consistency_report_to_json_text,
    cross_pack_consistency_report_to_markdown_text,
    write_cross_pack_consistency_report,
)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_input(now: datetime) -> CrossPackConsistencyInput:
    decl1 = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        title="Pack One",
        description="First pack",
        declared_state="ok",
        artifact_ref_ids=("a1",),
        section_ref_ids=("s1",),
        requirement_ref_ids=("r1",),
        upstream_pack_ids=("p2",),
        generated_at=now,
        requires_manual_review=True,
    )
    decl2 = CrossPackDeclaration(
        pack_id="p2",
        version="2.0",
        title="Pack Two",
        description="Second pack",
        declared_state="ok",
        generated_at=now,
    )
    artifact_ref = CrossPackArtifactRef(
        ref_id="a1",
        pack_id="p1",
        reference="data/audit_scorecard/audit_scorecard.json",
        label="Scorecard",
        message="Artifact reference",
        generated_at=now,
    )
    section_ref = CrossPackSectionRef(
        ref_id="s1",
        pack_id="p1",
        reference="section-1",
        label="Section",
        message="Section reference",
        generated_at=now,
    )
    requirement_ref = CrossPackRequirementRef(
        ref_id="r1",
        pack_id="p1",
        reference="req-1",
        label="Requirement",
        message="Requirement reference",
        generated_at=now,
    )
    state_claim = CrossPackStateClaim(
        subject_id="sub",
        state_label="ok",
        pack_id="p1",
        message="State claim",
    )
    rule = CrossPackConsistencyRule(
        rule_type=CrossPackConsistencyRuleType.COMPATIBLE_VERSION,
        source_pack_id="p1",
        target_pack_id="p2",
        expected_version="2.0",
        severity=CrossPackConsistencySeverity.BLOCKING,
        message="Version rule",
    )
    return CrossPackConsistencyInput(
        declarations=(decl1, decl2),
        artifact_refs=(artifact_ref,),
        section_refs=(section_ref,),
        requirement_refs=(requirement_ref,),
        state_claims=(state_claim,),
        rules=(rule,),
        metadata={"key": "value"},
        generated_at=now,
        project_version="0.36.0-dev",
        config=CrossPackConsistencyConfig(
            required_pack_ids=("p1", "p2"),
            allowed_state_labels=("ok",),
        ),
    )


@pytest.fixture
def sample_report(sample_input: CrossPackConsistencyInput) -> CrossPackConsistencyReport:
    return build_cross_pack_consistency_report(sample_input)


# ---------------------------------------------------------------------------
# Dict conversion
# ---------------------------------------------------------------------------


def test_dict_includes_report_fields(sample_report: CrossPackConsistencyReport) -> None:
    data = cross_pack_consistency_report_to_dict(sample_report)
    assert data["safety_notice"]
    assert data["report_id"] == sample_report.report_id
    assert data["state"] == sample_report.state.value
    assert data["project_version"] == sample_report.project_version
    assert "generated_at" in data
    assert isinstance(data["declarations"], list)
    assert isinstance(data["artifact_refs"], list)
    assert isinstance(data["section_refs"], list)
    assert isinstance(data["requirement_refs"], list)
    assert isinstance(data["state_claims"], list)
    assert isinstance(data["rules"], list)
    assert isinstance(data["issues"], list)
    assert isinstance(data["data_quality"], dict)
    assert isinstance(data["safety_flags"], dict)


def test_dict_nested_dataclass_serialization(sample_report: CrossPackConsistencyReport) -> None:
    data = cross_pack_consistency_report_to_dict(sample_report)
    assert data["data_quality"]["total_packs"] == len(sample_report.declarations)
    assert "is_safe" in data["safety_flags"]
    # Nested dataclass inside declarations
    first_decl = data["declarations"][0]
    assert "pack_id" in first_decl
    assert first_decl["version"] == sample_report.declarations[0].version


def test_dict_enum_serialization(sample_report: CrossPackConsistencyReport) -> None:
    data = cross_pack_consistency_report_to_dict(sample_report)
    assert data["state"] == sample_report.state.value
    if data["issues"]:
        first_issue = data["issues"][0]
        assert first_issue["issue_type"] == sample_report.issues[0].issue_type.value
        assert first_issue["severity"] == sample_report.issues[0].severity.value


def test_dict_metadata_mapping_serialization(sample_report: CrossPackConsistencyReport) -> None:
    data = cross_pack_consistency_report_to_dict(sample_report)
    assert data["metadata"] == {"key": "value"}


# ---------------------------------------------------------------------------
# JSON conversion
# ---------------------------------------------------------------------------


def test_json_parseable(sample_report: CrossPackConsistencyReport) -> None:
    text = cross_pack_consistency_report_to_json_text(sample_report)
    parsed = json.loads(text)
    assert parsed["report_id"] == sample_report.report_id
    assert parsed["state"] == sample_report.state.value


def test_json_deterministic(sample_report: CrossPackConsistencyReport) -> None:
    text1 = cross_pack_consistency_report_to_json_text(sample_report)
    text2 = cross_pack_consistency_report_to_json_text(sample_report)
    assert text1 == text2


def test_json_safe_for_sequences_and_mappings(sample_report: CrossPackConsistencyReport) -> None:
    text = cross_pack_consistency_report_to_json_text(sample_report)
    parsed = json.loads(text)
    assert isinstance(parsed["declarations"], list)
    assert isinstance(parsed["metadata"], dict)


# ---------------------------------------------------------------------------
# CSV conversion
# ---------------------------------------------------------------------------


def test_csv_header_and_rows_from_issues(sample_report: CrossPackConsistencyReport) -> None:
    text = cross_pack_consistency_report_to_csv_text(sample_report)
    lines = text.strip().split("\n")
    assert lines
    reader = csv.reader(lines)
    rows = list(reader)
    header = rows[0]
    expected_header = [
        "report_id",
        "generated_at",
        "issue_id",
        "issue_type",
        "severity",
        "subject_id",
        "source_pack_id",
        "target_pack_id",
        "reason_codes",
        "message",
    ]
    assert header == expected_header
    data_rows = rows[1:]
    assert len(data_rows) == len(sample_report.issues)


def test_csv_uses_existing_issue_id(sample_report: CrossPackConsistencyReport) -> None:
    text = cross_pack_consistency_report_to_csv_text(sample_report)
    lines = text.strip().split("\n")
    reader = csv.reader(lines)
    rows = list(reader)
    data_rows = rows[1:]
    issue_ids = {row[2] for row in data_rows}
    expected_ids = {issue.issue_id for issue in sample_report.issues}
    assert issue_ids == expected_ids


def test_csv_deterministic_sorting(sample_report: CrossPackConsistencyReport) -> None:
    text1 = cross_pack_consistency_report_to_csv_text(sample_report)
    text2 = cross_pack_consistency_report_to_csv_text(sample_report)
    assert text1 == text2


def test_csv_no_recomputation_of_issues(sample_report: CrossPackConsistencyReport) -> None:
    # Ensure writer uses existing issues; count should match exactly.
    text = cross_pack_consistency_report_to_csv_text(sample_report)
    lines = text.strip().split("\n")
    data_rows = lines[1:]
    assert len(data_rows) == sample_report.data_quality.total_issues


# ---------------------------------------------------------------------------
# Markdown conversion
# ---------------------------------------------------------------------------


def test_markdown_starts_with_h1_and_safety_notice(sample_report: CrossPackConsistencyReport) -> None:
    text = cross_pack_consistency_report_to_markdown_text(sample_report)
    lines = text.splitlines()
    assert lines[0].startswith("# ")
    # Immediate safety notice should appear near the top.
    assert any("research-only" in line.lower() or "audit-only" in line.lower() for line in lines[:5])


def test_markdown_disclaims_approval_and_trading(sample_report: CrossPackConsistencyReport) -> None:
    text = cross_pack_consistency_report_to_markdown_text(sample_report).lower()
    assert "not an approval" in text or "is not an approval" in text
    assert "certification" in text
    assert "production readiness" in text
    assert "trading readiness" in text
    assert "recommendation" in text
    assert "suitability assessment" in text
    assert "signal" in text


def test_markdown_contains_all_sections(sample_report: CrossPackConsistencyReport) -> None:
    text = cross_pack_consistency_report_to_markdown_text(sample_report).lower()
    assert "## summary" in text
    assert "## consistency issues" in text
    assert "## pack declarations" in text
    assert "## artifact references" in text
    assert "## section references" in text
    assert "## requirement references" in text
    assert "## state claims" in text
    assert "## rules" in text
    assert "## data quality" in text
    assert "## safety flags" in text
    assert "## manual review" in text


def test_markdown_no_actionable_recommendation_language(sample_report: CrossPackConsistencyReport) -> None:
    text = cross_pack_consistency_report_to_markdown_text(sample_report).lower()
    forbidden = [
        "buy signal",
        "sell signal",
        "go long",
        "go short",
        "place orders",
        "execute orders",
        "live trading",
    ]
    for phrase in forbidden:
        assert phrase not in text, f"Forbidden actionable phrase: {phrase}"


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


def test_atomic_write_creates_json_csv_markdown(tmp_path: Path, sample_report: CrossPackConsistencyReport) -> None:
    json_path = tmp_path / "out.json"
    csv_path = tmp_path / "out.csv"
    markdown_path = tmp_path / "out.md"
    write_cross_pack_consistency_report(
        sample_report,
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
    )
    assert json_path.exists()
    assert csv_path.exists()
    assert markdown_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["report_id"] == sample_report.report_id
    assert csv_path.read_text(encoding="utf-8").startswith("report_id,generated_at")
    assert markdown_path.read_text(encoding="utf-8").startswith("# ")


def test_omitted_path_writes_default(tmp_path: Path, sample_report: CrossPackConsistencyReport) -> None:
    original_cwd = Path.cwd()
    try:
        # Change cwd to tmp_path so default relative paths land there.
        import os
        os.chdir(tmp_path)
        write_cross_pack_consistency_report(sample_report)
        assert (tmp_path / DEFAULT_JSON_PATH).exists()
        assert (tmp_path / DEFAULT_CSV_PATH).exists()
        assert (tmp_path / DEFAULT_MD_PATH).exists()
    finally:
        os.chdir(original_cwd)


def test_none_skips_artifact(tmp_path: Path, sample_report: CrossPackConsistencyReport) -> None:
    json_path = tmp_path / "out.json"
    csv_path = tmp_path / "out.csv"
    markdown_path = tmp_path / "out.md"
    write_cross_pack_consistency_report(
        sample_report,
        json_path=json_path,
        csv_path=None,
        markdown_path=markdown_path,
    )
    assert json_path.exists()
    assert not csv_path.exists()
    assert markdown_path.exists()


def test_parent_directories_created(tmp_path: Path, sample_report: CrossPackConsistencyReport) -> None:
    json_path = tmp_path / "deep" / "nested" / "out.json"
    atomic_write_json_cross_pack_consistency_report(sample_report, json_path)
    assert json_path.exists()


# ---------------------------------------------------------------------------
# State coverage
# ---------------------------------------------------------------------------


def test_blocked_report_serialization(now: datetime) -> None:
    decl = CrossPackDeclaration(
        pack_id="p1",
        version="1.0",
        description="This pack is production ready",
    )
    inp = CrossPackConsistencyInput(declarations=(decl,), generated_at=now)
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.BLOCKED
    data = cross_pack_consistency_report_to_dict(report)
    assert data["state"] == "blocked"
    assert data["safety_flags"]["has_forbidden_terms"] is True


def test_degraded_report_serialization(now: datetime) -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", requires_manual_review=True)
    inp = CrossPackConsistencyInput(declarations=(decl,), generated_at=now)
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.DEGRADED
    text = cross_pack_consistency_report_to_markdown_text(report)
    assert "## Manual Review" in text


def test_not_applicable_report_serialization(now: datetime) -> None:
    inp = CrossPackConsistencyInput(generated_at=now)
    report = build_cross_pack_consistency_report(inp)
    assert report.state is CrossPackConsistencyState.NOT_APPLICABLE
    data = cross_pack_consistency_report_to_dict(report)
    assert data["state"] == "not_applicable"


# ---------------------------------------------------------------------------
# Immutability / safety
# ---------------------------------------------------------------------------


def test_no_mutation_of_report(sample_report: CrossPackConsistencyReport) -> None:
    original = cross_pack_consistency_report_to_dict(sample_report)
    cross_pack_consistency_report_to_json_text(sample_report)
    cross_pack_consistency_report_to_csv_text(sample_report)
    cross_pack_consistency_report_to_markdown_text(sample_report)
    assert cross_pack_consistency_report_to_dict(sample_report) == original


def test_no_path_traversal_or_opening(tmp_path: Path, sample_report: CrossPackConsistencyReport) -> None:
    # Writer should not read/validate the reference strings.
    text = cross_pack_consistency_report_to_markdown_text(sample_report)
    assert "data/audit_scorecard/audit_scorecard.json" in text
    # Just verifying no exception is raised when serializing path-like strings.
    json_text = cross_pack_consistency_report_to_json_text(sample_report)
    parsed = json.loads(json_text)
    assert parsed["artifact_refs"][0]["reference"] == "data/audit_scorecard/audit_scorecard.json"


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


def test_public_writer_exports() -> None:
    from hunter import cross_pack_consistency as cpc

    assert hasattr(cpc, "cross_pack_consistency_report_to_dict")
    assert hasattr(cpc, "cross_pack_consistency_report_to_json_text")
    assert hasattr(cpc, "cross_pack_consistency_report_to_csv_text")
    assert hasattr(cpc, "cross_pack_consistency_report_to_markdown_text")
    assert hasattr(cpc, "write_cross_pack_consistency_report")
    assert hasattr(cpc, "atomic_write_json_cross_pack_consistency_report")
    assert hasattr(cpc, "atomic_write_csv_cross_pack_consistency_report")
    assert hasattr(cpc, "atomic_write_markdown_cross_pack_consistency_report")
    assert hasattr(cpc, "DEFAULT_JSON_PATH")
    assert hasattr(cpc, "DEFAULT_CSV_PATH")
    assert hasattr(cpc, "DEFAULT_MD_PATH")


# ---------------------------------------------------------------------------
# Default path sentinel behavior
# ---------------------------------------------------------------------------


def test_default_path_sentinel_uses_defaults(tmp_path: Path, sample_report: CrossPackConsistencyReport) -> None:
    import os
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        # call with no path args
        json_out, csv_out, md_out = write_cross_pack_consistency_report(sample_report)
        assert json_out == DEFAULT_JSON_PATH
        assert csv_out == DEFAULT_CSV_PATH
        assert md_out == DEFAULT_MD_PATH
    finally:
        os.chdir(original_cwd)


def test_default_path_sentinel_explicit_path(tmp_path: Path, sample_report: CrossPackConsistencyReport) -> None:
    json_path = tmp_path / "explicit.json"
    json_out, csv_out, md_out = write_cross_pack_consistency_report(
        sample_report,
        json_path=json_path,
        csv_path=None,
        markdown_path=None,
    )
    assert json_out == json_path
    assert csv_out is None
    assert md_out is None


# ---------------------------------------------------------------------------
# Nested mapping serialization if needed
# ---------------------------------------------------------------------------


def test_nested_mapping_serialized_safely(sample_report: CrossPackConsistencyReport) -> None:
    data = cross_pack_consistency_report_to_dict(sample_report)
    assert isinstance(data["metadata"], dict)
    assert data["metadata"] == {"key": "value"}


# ---------------------------------------------------------------------------
# CSV deterministic sorting
# ---------------------------------------------------------------------------


def test_csv_deterministic_by_issue_sorting(now: datetime) -> None:
    decl = CrossPackDeclaration(pack_id="p1", version="1.0", requires_manual_review=True)
    inp = CrossPackConsistencyInput(declarations=(decl,), generated_at=now)
    report = build_cross_pack_consistency_report(inp)
    text = cross_pack_consistency_report_to_csv_text(report)
    lines = text.strip().split("\n")
    data_rows = lines[1:]
    if data_rows:
        issue_ids = [row.split(",")[2] for row in data_rows]
        assert issue_ids == sorted(issue_ids)
