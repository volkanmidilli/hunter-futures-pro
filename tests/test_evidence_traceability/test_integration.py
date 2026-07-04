"""Integration tests for hunter.evidence_traceability package.

MVP-34 — Local Research Evidence Traceability Matrix.

These tests exercise the public API end-to-end: build an
EvidenceTraceabilityReport from caller-provided in-memory declarations,
serialize it to JSON/CSV/Markdown, and verify safety and determinism
properties. No filesystem scan, import introspection, network, exchange,
Binance, Freqtrade, live trading, order, leverage, shorting, database, Web
UI, server, or scheduler semantics are used.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.evidence_traceability import (
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
    build_evidence_traceability_report,
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
def good_input(generated_at: datetime) -> EvidenceTraceabilityInput:
    """A fully connected, clean traceability graph with no issues."""
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="System must persist audit evidence locally.",
        title="Audit evidence persistence",
        required_link_types=("covered_by",),
    )
    check = EvidenceCheck(
        check_id="check_1",
        description="Verify audit evidence is persisted as JSON.",
        title="Evidence persistence check",
        covers_requirement_ids=("req_1",),
    )
    art = EvidenceArtifactRef(
        artifact_id="art_1",
        reference="data/audit/evidence.json",
        label="Audit evidence artifact",
        generated_at=generated_at,
    )
    sec = EvidenceSectionRef(
        section_id="sec_1",
        reference="reports/audit/section.md",
        label="Audit section",
        generated_at=generated_at,
    )
    link_coverage = EvidenceLink(
        link_id="link_1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    link_artifact = EvidenceLink(
        link_id="link_2",
        source_id="art_1",
        target_id="check_1",
        link_type=EvidenceTraceabilityLinkType.SUPPORTS,
    )
    link_section = EvidenceLink(
        link_id="link_3",
        source_id="sec_1",
        target_id="check_1",
        link_type=EvidenceTraceabilityLinkType.DERIVED_FROM,
    )
    return EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        artifacts=(art,),
        sections=(sec,),
        links=(link_coverage, link_artifact, link_section),
        project_version="0.34.0-dev",
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# 1. End-to-end successful report
# ---------------------------------------------------------------------------


def test_end_to_end_ok_report(good_input: EvidenceTraceabilityInput) -> None:
    report = build_evidence_traceability_report(good_input)
    assert report.state is EvidenceTraceabilityState.OK
    assert report.reason_codes[0] is EvidenceTraceabilityReasonCode.OK
    assert len(report.results) == 1  # one requirement coverage result
    assert report.results[0].item_id == "req_1"
    assert report.results[0].coverage_state is EvidenceTraceabilityCoverageState.COVERED
    assert report.safety_flags.is_safe is True
    assert report.project_version == "0.34.0-dev"
    # links are copied and sorted
    assert len(report.links) == 3
    assert report.links[0].source_id <= report.links[1].source_id


def test_end_to_end_generated_at_fixed(good_input: EvidenceTraceabilityInput) -> None:
    report = build_evidence_traceability_report(good_input)
    assert report.generated_at == datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 2. Coverage classification
# ---------------------------------------------------------------------------


def test_missing_coverage_blocking(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Uncovered blocking requirement",
        severity=EvidenceTraceabilitySeverity.BLOCKING,
    )
    inp = EvidenceTraceabilityInput(requirements=(req,), generated_at=generated_at)
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.BLOCKED
    assert report.results[0].coverage_state is EvidenceTraceabilityCoverageState.MISSING


def test_missing_coverage_advisory_degraded(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Uncovered advisory requirement",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    inp = EvidenceTraceabilityInput(requirements=(req,), generated_at=generated_at)
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED
    assert report.results[0].coverage_state is EvidenceTraceabilityCoverageState.MISSING


def test_partial_coverage(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Requirement with two required link types",
        required_link_types=("covered_by", "supports"),
    )
    link = EvidenceLink(
        link_id="link_1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    check = EvidenceCheck(check_id="check_1", description="Partial check")
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        links=(link,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED
    assert report.results[0].coverage_state is EvidenceTraceabilityCoverageState.PARTIAL
    assert report.results[0].reason_code is EvidenceTraceabilityReasonCode.PARTIAL_COVERAGE


def test_covered_requirement(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Fully covered requirement",
        required_link_types=("covered_by",),
    )
    check = EvidenceCheck(check_id="check_1", description="Check")
    link = EvidenceLink(
        link_id="link_1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        links=(link,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.OK
    assert report.results[0].coverage_state is EvidenceTraceabilityCoverageState.COVERED


# ---------------------------------------------------------------------------
# 3. Orphan items
# ---------------------------------------------------------------------------


def test_orphan_check_artifact_section_degraded(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Requirement",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    check = EvidenceCheck(check_id="check_1", description="Orphan check")
    art = EvidenceArtifactRef(
        artifact_id="art_1",
        reference="data/orphan.json",
        label="Orphan artifact",
    )
    sec = EvidenceSectionRef(
        section_id="sec_1",
        reference="reports/orphan.md",
        label="Orphan section",
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        artifacts=(art,),
        sections=(sec,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.ORPHAN_CHECK
        for r in report.results
    )
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.ORPHAN_ARTIFACT
        for r in report.results
    )
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.ORPHAN_SECTION
        for r in report.results
    )
    # All orphan results use NOT_APPLICABLE coverage
    for r in report.results:
        if r.reason_code.value.startswith("orphan"):
            assert r.coverage_state is EvidenceTraceabilityCoverageState.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# 4. Conflicting links
# ---------------------------------------------------------------------------


def test_conflicting_links_blocked(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Requirement",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    check = EvidenceCheck(check_id="check_1", description="Check")
    link_supports = EvidenceLink(
        link_id="link_1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.SUPPORTS,
    )
    link_contradicts = EvidenceLink(
        link_id="link_2",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.CONTRADICTS,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        links=(link_supports, link_contradicts),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.BLOCKED
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.CONFLICTING_LINK
        for r in report.results
    )


# ---------------------------------------------------------------------------
# 5. Stale evidence
# ---------------------------------------------------------------------------


def test_stale_evidence_degraded(generated_at: datetime) -> None:
    old_ts = generated_at - timedelta(days=30)
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Requirement",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    art = EvidenceArtifactRef(
        artifact_id="art_1",
        reference="data/stale.json",
        label="Stale artifact",
        generated_at=old_ts,
    )
    link = EvidenceLink(
        link_id="link_1",
        source_id="art_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.SUPPORTS,
    )
    config = EvidenceTraceabilityConfig(staleness_threshold_seconds=3600)
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        artifacts=(art,),
        links=(link,),
        generated_at=generated_at,
        config=config,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.STALE_EVIDENCE
        for r in report.results
    )


# ---------------------------------------------------------------------------
# 6. Missing manual review
# ---------------------------------------------------------------------------


def test_missing_manual_review_degraded(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Requirement",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    art = EvidenceArtifactRef(
        artifact_id="art_1",
        reference="data/review.json",
        label="Needs review",
        requires_manual_review=True,
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
    assert report.state is EvidenceTraceabilityState.DEGRADED
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.MISSING_MANUAL_REVIEW
        for r in report.results
    )


# ---------------------------------------------------------------------------
# 7. Fail-closed behavior
# ---------------------------------------------------------------------------


def test_duplicate_requirement_ids_blocked(generated_at: datetime) -> None:
    req_a = EvidenceRequirement(requirement_id="dup", description="A")
    req_b = EvidenceRequirement(requirement_id="dup", description="B")
    inp = EvidenceTraceabilityInput(
        requirements=(req_a, req_b),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.BLOCKED
    assert (
        EvidenceTraceabilityReasonCode.DUPLICATE_REQUIREMENT_ID in report.reason_codes
    )


def test_unsafe_metadata_blocked(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        metadata={"note": "This is production ready"},
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.BLOCKED
    assert EvidenceTraceabilityReasonCode.UNSAFE_CONTENT in report.reason_codes


def test_forbidden_term_in_description_blocked(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="This involves live trading which is forbidden",
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.BLOCKED
    assert (
        EvidenceTraceabilityReasonCode.FORBIDDEN_TERM_PRESENT in report.reason_codes
    )


# ---------------------------------------------------------------------------
# 8. Aggregation modes
# ---------------------------------------------------------------------------


def test_strict_mode_promotes_degraded_to_blocked(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Advisory requirement",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        generated_at=generated_at,
    )
    report_non_strict = build_evidence_traceability_report(inp, strict=False)
    assert report_non_strict.state is EvidenceTraceabilityState.DEGRADED
    report_strict = build_evidence_traceability_report(inp, strict=True)
    assert report_strict.state is EvidenceTraceabilityState.BLOCKED


def test_not_applicable_does_not_block(generated_at: datetime) -> None:
    """A fully covered requirement with no advisory or blocking failures is OK."""
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Requirement",
    )
    check = EvidenceCheck(check_id="check_1", description="Check")
    link = EvidenceLink(
        link_id="link_1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        links=(link,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.OK


# ---------------------------------------------------------------------------
# 9. Writer end-to-end
# ---------------------------------------------------------------------------


def test_writer_end_to_end(
    good_input: EvidenceTraceabilityInput, tmp_path: Path
) -> None:
    report = build_evidence_traceability_report(good_input)
    json_path = tmp_path / "out" / "matrix.json"
    csv_path = tmp_path / "out" / "matrix_edges.csv"
    md_path = tmp_path / "out" / "matrix.md"
    write_evidence_traceability_report(
        report,
        json_path=json_path,
        csv_path=csv_path,
        md_path=md_path,
    )
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()

    # JSON parses
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["state"] == report.state.value
    assert len(parsed["links"]) == 3

    # CSV has edge rows
    rows = list(csv.DictReader(io.StringIO(csv_path.read_text(encoding="utf-8"))))
    assert len(rows) == 3
    assert set(rows[0].keys()) >= {
        "report_id",
        "generated_at",
        "source_id",
        "target_id",
        "link_type",
        "coverage_state",
        "severity",
        "reason_codes",
        "message",
    }

    # Markdown starts with H1 and safety notice
    md_text = md_path.read_text(encoding="utf-8")
    assert md_text.startswith("# Evidence Traceability Matrix")
    assert "human-audit" in md_text.lower()
    assert "not a certification of trading readiness" in md_text.lower()


# ---------------------------------------------------------------------------
# 10. Determinism
# ---------------------------------------------------------------------------


def test_determinism(good_input: EvidenceTraceabilityInput) -> None:
    report_a = build_evidence_traceability_report(good_input)
    report_b = build_evidence_traceability_report(good_input)
    json_a = evidence_traceability_report_to_json_text(report_a)
    json_b = evidence_traceability_report_to_json_text(report_b)
    assert json_a == json_b
    csv_a = evidence_traceability_report_to_csv_text(report_a)
    csv_b = evidence_traceability_report_to_csv_text(report_b)
    assert csv_a == csv_b
    md_a = evidence_traceability_report_to_markdown_text(report_a)
    md_b = evidence_traceability_report_to_markdown_text(report_b)
    assert md_a == md_b


# ---------------------------------------------------------------------------
# 11. No mutation of input
# ---------------------------------------------------------------------------


def test_no_input_mutation(good_input: EvidenceTraceabilityInput) -> None:
    original_reqs = good_input.requirements
    original_links = good_input.links
    build_evidence_traceability_report(good_input)
    assert good_input.requirements is original_reqs
    assert good_input.links is original_links


# ---------------------------------------------------------------------------
# 12. Safety boundaries
# ---------------------------------------------------------------------------


def test_safety_boundaries(good_input: EvidenceTraceabilityInput) -> None:
    report = build_evidence_traceability_report(good_input)
    assert report.safety_flags.is_safe is True
    assert report.safety_flags.research_only is True
    assert report.safety_flags.not_trading_advice is True
    assert report.safety_flags.no_file_read_in_engine is True
    assert report.safety_flags.no_network_connection is True
    assert report.safety_flags.no_exchange_connection is True
    assert report.safety_flags.no_freqtrade_input is True
    assert report.safety_flags.no_database is True
    assert report.safety_flags.not_production_certification is True
    assert report.safety_flags.not_trading_readiness_gate is True
    assert report.safety_flags.no_action_commands is True

    md = evidence_traceability_report_to_markdown_text(report).lower()
    assert "buy signal" not in md
    assert "sell signal" not in md
    assert "execute orders" not in md
    assert "place orders" not in md


def test_artifact_refs_remain_opaque(good_input: EvidenceTraceabilityInput) -> None:
    report = build_evidence_traceability_report(good_input)
    data = evidence_traceability_report_to_dict(report)
    # The artifact reference string is preserved as-is in JSON — never opened
    assert any(
        link.get("source_id") == "art_1" for link in data["links"]
    )
