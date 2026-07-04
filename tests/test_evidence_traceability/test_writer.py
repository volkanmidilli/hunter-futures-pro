"""Tests for hunter.evidence_traceability.writer."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.evidence_traceability.engine import build_evidence_traceability_report
from hunter.evidence_traceability.models import (
    EvidenceArtifactRef,
    EvidenceCheck,
    EvidenceLink,
    EvidenceRequirement,
    EvidenceSectionRef,
    EvidenceTraceabilityConfig,
    EvidenceTraceabilityCoverageState,
    EvidenceTraceabilityInput,
    EvidenceTraceabilityLinkType,
    EvidenceTraceabilityReasonCode,
    EvidenceTraceabilitySeverity,
    EvidenceTraceabilityState,
)
from hunter.evidence_traceability.writer import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    atomic_write_csv_evidence_traceability_report,
    atomic_write_json_evidence_traceability_report,
    atomic_write_markdown_evidence_traceability_report,
    evidence_traceability_report_to_csv_text,
    evidence_traceability_report_to_dict,
    evidence_traceability_report_to_json_text,
    evidence_traceability_report_to_markdown_text,
    write_evidence_traceability_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def generated_at() -> datetime:
    return datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def good_matrix(generated_at: datetime) -> object:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="System must persist evidence",
        title="Evidence persistence",
    )
    check = EvidenceCheck(
        check_id="check_1",
        description="Verify evidence persistence",
        title="Evidence check",
        covers_requirement_ids=("req_1",),
    )
    art = EvidenceArtifactRef(
        artifact_id="art_1",
        reference="data/evidence.json",
        label="Evidence JSON",
    )
    link = EvidenceLink(
        link_id="link_1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    art_link = EvidenceLink(
        link_id="link_2",
        source_id="art_1",
        target_id="check_1",
        link_type=EvidenceTraceabilityLinkType.SUPPORTS,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        artifacts=(art,),
        links=(link, art_link),
        generated_at=generated_at,
    )
    return build_evidence_traceability_report(inp)


@pytest.fixture
def degraded_matrix(generated_at: datetime) -> object:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Requirement",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    check = EvidenceCheck(check_id="check_1", description="C")
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        generated_at=generated_at,
    )
    return build_evidence_traceability_report(inp)


@pytest.fixture
def blocked_matrix(generated_at: datetime) -> object:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Requirement",
    )
    check = EvidenceCheck(check_id="check_1", description="C")
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        metadata={"note": "production ready"},
        generated_at=generated_at,
    )
    return build_evidence_traceability_report(inp)


# ---------------------------------------------------------------------------
# Dict conversion
# ---------------------------------------------------------------------------


def test_dict_conversion_includes_report_fields(good_matrix: object) -> None:
    data = evidence_traceability_report_to_dict(good_matrix)
    assert data["state"] == good_matrix.state.value
    assert data["generated_at"] == "2026-07-04T12:00:00+00:00"
    assert "links" in data
    assert "results" in data
    assert "data_quality" in data
    assert "safety_flags" in data


def test_dict_conversion_safety_flags_include_is_safe(good_matrix: object) -> None:
    data = evidence_traceability_report_to_dict(good_matrix)
    assert data["safety_flags"]["is_safe"] is True


def test_dict_conversion_no_report_mutation(good_matrix: object) -> None:
    before = good_matrix.results
    evidence_traceability_report_to_dict(good_matrix)
    assert good_matrix.results is before


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


def test_json_parseable(good_matrix: object) -> None:
    text = evidence_traceability_report_to_json_text(good_matrix)
    parsed = json.loads(text)
    assert parsed["state"] == good_matrix.state.value
    assert parsed["safety_notice"] is not None


def test_json_deterministic(good_matrix: object) -> None:
    t1 = evidence_traceability_report_to_json_text(good_matrix)
    t2 = evidence_traceability_report_to_json_text(good_matrix)
    assert t1 == t2


def test_json_blocked_report(blocked_matrix: object) -> None:
    text = evidence_traceability_report_to_json_text(blocked_matrix)
    parsed = json.loads(text)
    assert parsed["state"] == "blocked"
    assert parsed["data_quality"]["total_items"] == 0


def test_json_degraded_report(degraded_matrix: object) -> None:
    text = evidence_traceability_report_to_json_text(degraded_matrix)
    parsed = json.loads(text)
    assert parsed["state"] == "degraded"
    assert parsed["data_quality"]["degraded_count"] > 0


def test_json_includes_links(good_matrix: object) -> None:
    text = evidence_traceability_report_to_json_text(good_matrix)
    parsed = json.loads(text)
    assert len(parsed["links"]) == 2
    assert parsed["links"][0]["link_id"]


def test_json_enums_are_string_values(good_matrix: object) -> None:
    text = evidence_traceability_report_to_json_text(good_matrix)
    parsed = json.loads(text)
    assert isinstance(parsed["state"], str)
    assert isinstance(parsed["links"][0]["link_type"], str)


def test_json_safety_notice_first(good_matrix: object) -> None:
    text = evidence_traceability_report_to_json_text(good_matrix)
    assert text.index('"safety_notice"') < text.index('"generated_at"')


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


def test_csv_header(good_matrix: object) -> None:
    text = evidence_traceability_report_to_csv_text(good_matrix)
    lines = text.strip().split("\n")
    header = lines[0].split(",")
    assert header == [
        "report_id",
        "generated_at",
        "source_id",
        "target_id",
        "link_type",
        "coverage_state",
        "severity",
        "reason_codes",
        "message",
    ]


def test_csv_edge_rows_from_links(good_matrix: object) -> None:
    text = evidence_traceability_report_to_csv_text(good_matrix)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 2
    assert {rows[0]["source_id"], rows[1]["source_id"]} == {"check_1", "art_1"}


def test_csv_coverage_state_for_covered_link(good_matrix: object) -> None:
    text = evidence_traceability_report_to_csv_text(good_matrix)
    rows = list(csv.DictReader(io.StringIO(text)))
    covered = [r for r in rows if r["link_type"] == "covered_by"][0]
    assert covered["coverage_state"] == "covered"


def test_csv_fallback_when_no_result(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Requirement",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    art = EvidenceArtifactRef(
        artifact_id="art_1",
        reference="data/evidence.json",
        label="Evidence JSON",
    )
    link = EvidenceLink(
        link_id="link_1",
        source_id="art_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.SUPPORTS,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        artifacts=(art,),
        links=(link,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    text = evidence_traceability_report_to_csv_text(report)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows[0]["coverage_state"] == "not_applicable"
    assert rows[0]["severity"] in {"advisory", "blocking"}
    assert rows[0]["reason_codes"] == ""


def test_csv_deterministic(good_matrix: object) -> None:
    t1 = evidence_traceability_report_to_csv_text(good_matrix)
    t2 = evidence_traceability_report_to_csv_text(good_matrix)
    assert t1 == t2


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def test_markdown_starts_with_h1_and_safety_notice(good_matrix: object) -> None:
    text = evidence_traceability_report_to_markdown_text(good_matrix)
    first = text.splitlines()[0]
    assert first == "# Evidence Traceability Matrix"
    assert "human-audit" in text.lower()
    assert "research artifact" in text.lower()


def test_markdown_not_approval_or_signal(good_matrix: object) -> None:
    text = evidence_traceability_report_to_markdown_text(good_matrix).lower()
    assert "not a certification of trading readiness" in text
    assert "not a trading signal" in text


def test_markdown_sections_present(good_matrix: object) -> None:
    text = evidence_traceability_report_to_markdown_text(good_matrix).lower()
    assert "## summary" in text
    assert "## coverage matrix" in text
    assert "## traceability edges" in text
    assert "## data quality" in text
    assert "## safety flags" in text
    assert "## manual review" in text


def test_markdown_no_actionable_language(good_matrix: object) -> None:
    text = evidence_traceability_report_to_markdown_text(good_matrix).lower()
    assert "buy signal" not in text
    assert "sell signal" not in text
    assert "buy now" not in text
    assert "sell now" not in text
    assert "place orders" not in text
    assert "execute orders" not in text


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


def test_atomic_write_json(good_matrix: object, tmp_path: Path) -> None:
    target = tmp_path / "matrix.json"
    atomic_write_json_evidence_traceability_report(good_matrix, target)
    assert target.exists()
    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert parsed["state"] == good_matrix.state.value


def test_atomic_write_csv(good_matrix: object, tmp_path: Path) -> None:
    target = tmp_path / "matrix.csv"
    atomic_write_csv_evidence_traceability_report(good_matrix, target)
    assert target.exists()
    rows = list(csv.DictReader(io.StringIO(target.read_text(encoding="utf-8"))))
    assert len(rows) == 2


def test_atomic_write_markdown(good_matrix: object, tmp_path: Path) -> None:
    target = tmp_path / "matrix.md"
    atomic_write_markdown_evidence_traceability_report(good_matrix, target)
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert text.startswith("# Evidence Traceability Matrix")


def test_parent_directories_created(good_matrix: object, tmp_path: Path) -> None:
    target = tmp_path / "nested" / "matrix.json"
    atomic_write_json_evidence_traceability_report(good_matrix, target)
    assert target.exists()


def test_write_all_three_formats(good_matrix: object, tmp_path: Path) -> None:
    json_path = tmp_path / "m.json"
    csv_path = tmp_path / "m.csv"
    md_path = tmp_path / "m.md"
    write_evidence_traceability_report(
        good_matrix,
        json_path=json_path,
        csv_path=csv_path,
        md_path=md_path,
    )
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()


def test_write_skip_format(good_matrix: object, tmp_path: Path) -> None:
    json_path = tmp_path / "m.json"
    write_evidence_traceability_report(
        good_matrix,
        json_path=json_path,
        csv_path=None,
        md_path=None,
    )
    assert json_path.exists()
    assert not (tmp_path / "m.csv").exists()
    assert not (tmp_path / "m.md").exists()


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


def test_default_paths_exported() -> None:
    from hunter.evidence_traceability import (
        DEFAULT_CSV_PATH,
        DEFAULT_JSON_PATH,
        DEFAULT_MD_PATH,
    )

    assert str(DEFAULT_JSON_PATH) == "data/evidence_traceability/evidence_traceability.json"
    assert str(DEFAULT_CSV_PATH) == "data/evidence_traceability/evidence_traceability_edges.csv"
    assert str(DEFAULT_MD_PATH) == "reports/evidence_traceability/evidence_traceability.md"


def test_writer_functions_exported() -> None:
    from hunter.evidence_traceability import (
        evidence_traceability_report_to_csv_text,
        evidence_traceability_report_to_dict,
        evidence_traceability_report_to_json_text,
        evidence_traceability_report_to_markdown_text,
        write_evidence_traceability_report,
    )

    assert callable(evidence_traceability_report_to_dict)
    assert callable(evidence_traceability_report_to_json_text)
    assert callable(evidence_traceability_report_to_csv_text)
    assert callable(evidence_traceability_report_to_markdown_text)
    assert callable(write_evidence_traceability_report)


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


def test_writer_does_not_open_references(good_matrix: object, tmp_path: Path) -> None:
    # The writer serializes the reference as a string; it must never attempt to open it.
    target = tmp_path / "matrix.json"
    atomic_write_json_evidence_traceability_report(good_matrix, target)
    parsed = json.loads(target.read_text(encoding="utf-8"))
    sources = {link["source_id"] for link in parsed["links"]}
    assert "art_1" in sources
    assert not (tmp_path / "data").exists()
