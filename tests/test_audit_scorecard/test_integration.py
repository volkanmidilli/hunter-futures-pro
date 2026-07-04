"""Integration tests for hunter.audit_scorecard package.

MVP-35 — Local Research Audit Readiness Scorecard.

These tests exercise the public API end-to-end: build a report from caller-provided
in-memory declarations, serialize it through the writer, and verify safety,
determinism, and failure semantics. They do not touch the network, exchanges,
Freqtrade, databases, or Web UIs.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.audit_scorecard import (
    AuditScorecardConfig,
    AuditScorecardDimension,
    AuditScorecardDimensionState,
    AuditScorecardEvidenceRef,
    AuditScorecardFinding,
    AuditScorecardInput,
    AuditScorecardLink,
    AuditScorecardLinkType,
    AuditScorecardReasonCode,
    AuditScorecardReport,
    AuditScorecardSeverity,
    AuditScorecardState,
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


# ---------------------------------------------------------------------------
# 1. End-to-end successful report
# ---------------------------------------------------------------------------

def test_end_to_end_successful_report(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="release_hardening",
        title="Release Hardening Audit",
        description="Local research release consistency audit dimension.",
        required=True,
        expected_evidence_count=1,
    )
    ev = AuditScorecardEvidenceRef(
        evidence_id="ev_release",
        reference="reports/release_hardening/release_hardening.md",
        label="Release hardening report",
        generated_at=generated_at,
    )
    link = AuditScorecardLink(
        link_id="l_release_covers",
        source_id="ev_release",
        target_id="release_hardening",
        link_type=AuditScorecardLinkType.COVERS,
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        evidence_refs=(ev,),
        links=(link,),
        generated_at=generated_at,
        project_version="0.35.0-dev",
        metadata={"scope": "local-research"},
    )
    report = build_audit_scorecard_report(inp)

    assert isinstance(report, AuditScorecardReport)
    assert report.generated_at == generated_at
    assert report.state is AuditScorecardState.OK
    assert report.report_id.startswith("audit_scorecard_")
    assert len(report.dimension_results) == 1
    result = report.dimension_results[0]
    assert result.dimension_state is AuditScorecardDimensionState.COMPLETE
    assert result.completeness_percent == 100
    assert result.evidence_count == 1
    assert report.data_quality.dimension_count == 1
    assert report.data_quality.evidence_count == 1
    assert report.safety_flags.research_only is True
    assert report.safety_flags.no_exchange_connection is True
    assert report.safety_flags.is_safe is True


# ---------------------------------------------------------------------------
# 2. Writer end-to-end
# ---------------------------------------------------------------------------

def test_writer_end_to_end(generated_at: datetime, tmp_path: Path) -> None:
    dim = AuditScorecardDimension(
        dimension_id="evidence_traceability",
        title="Evidence Traceability",
        description="Traceability matrix coverage.",
    )
    ev = AuditScorecardEvidenceRef(
        evidence_id="ev_trace",
        reference="data/evidence_traceability/evidence_traceability.json",
        generated_at=generated_at,
    )
    link = AuditScorecardLink(
        link_id="l_trace_supports",
        source_id="ev_trace",
        target_id="evidence_traceability",
        link_type=AuditScorecardLinkType.SUPPORTS,
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        evidence_refs=(ev,),
        links=(link,),
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)

    json_path = tmp_path / "scorecard.json"
    csv_path = tmp_path / "scorecard.csv"
    md_path = tmp_path / "scorecard.md"
    write_audit_scorecard_report(
        report, json_path=json_path, csv_path=csv_path, md_path=md_path
    )

    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text())
    assert data["report_id"] == report.report_id
    assert len(data["dimensions"]) == 1
    assert len(data["dimension_results"]) == 1
    assert len(data["evidence_refs"]) == 1
    assert len(data["links"]) == 1

    rows = list(csv.DictReader(csv_path.read_text().splitlines()))
    assert len(rows) == 1
    assert rows[0]["dimension_id"] == "evidence_traceability"
    assert rows[0]["dimension_state"] == "complete"
    assert rows[0]["completeness_percent"] == "100"

    md_text = md_path.read_text()
    assert md_text.startswith("# Local Research Audit Readiness Scorecard")
    assert "> This scorecard is a human-audit" in md_text


# ---------------------------------------------------------------------------
# 3. Dimension classification
# ---------------------------------------------------------------------------

def test_dimension_classification_complete_and_partial(
    generated_at: datetime,
) -> None:
    complete_dim = AuditScorecardDimension(
        dimension_id="dim_complete",
        title="Complete",
        description="D",
        expected_evidence_count=1,
    )
    partial_dim = AuditScorecardDimension(
        dimension_id="dim_partial",
        title="Partial",
        description="D",
        expected_evidence_count=2,
    )
    ev = AuditScorecardEvidenceRef(
        evidence_id="ev_1", reference="data/ev.json", generated_at=generated_at
    )
    l_complete = AuditScorecardLink(
        link_id="l_complete",
        source_id="ev_1",
        target_id="dim_complete",
        link_type=AuditScorecardLinkType.COVERS,
    )
    l_partial = AuditScorecardLink(
        link_id="l_partial",
        source_id="ev_1",
        target_id="dim_partial",
        link_type=AuditScorecardLinkType.SUPPORTS,
    )
    inp = AuditScorecardInput(
        dimensions=(complete_dim, partial_dim),
        evidence_refs=(ev,),
        links=(l_complete, l_partial),
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    states = {r.dimension_id: r.dimension_state for r in report.dimension_results}
    assert states["dim_complete"] is AuditScorecardDimensionState.COMPLETE
    assert states["dim_partial"] is AuditScorecardDimensionState.PARTIAL


def test_dimension_classification_missing_blocked_degraded_not_applicable(
    generated_at: datetime,
) -> None:
    missing_dim = AuditScorecardDimension(
        dimension_id="dim_missing",
        title="Missing",
        description="D",
        required=True,
        expected_evidence_count=1,
    )
    blocked_dim = AuditScorecardDimension(
        dimension_id="dim_blocked",
        title="Blocked",
        description="D",
        upstream_package_ids=("pkg_1",),
    )
    degraded_dim = AuditScorecardDimension(
        dimension_id="dim_degraded",
        title="Degraded",
        description="D",
        upstream_report_ids=("report_1",),
    )
    na_dim = AuditScorecardDimension(
        dimension_id="dim_na",
        title="Not Applicable",
        description="D",
        not_applicable=True,
    )
    inp = AuditScorecardInput(
        dimensions=(missing_dim, blocked_dim, degraded_dim, na_dim),
        upstream_states={"pkg_1": "blocked", "report_1": "degraded"},
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    states = {r.dimension_id: r.dimension_state for r in report.dimension_results}
    assert states["dim_missing"] is AuditScorecardDimensionState.MISSING
    assert states["dim_blocked"] is AuditScorecardDimensionState.BLOCKED
    assert states["dim_degraded"] is AuditScorecardDimensionState.DEGRADED
    assert states["dim_na"] is AuditScorecardDimensionState.NOT_APPLICABLE


def test_optional_dimension_still_evaluated(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_optional", title="Optional", description="D", required=False
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    result = report.dimension_results[0]
    assert result.dimension_state is AuditScorecardDimensionState.COMPLETE


def test_not_applicable_does_not_block(generated_at: datetime) -> None:
    na_dim = AuditScorecardDimension(
        dimension_id="dim_na", title="NA", description="D", not_applicable=True
    )
    inp = AuditScorecardInput(dimensions=(na_dim,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.OK


# ---------------------------------------------------------------------------
# 4. Precedence
# ---------------------------------------------------------------------------

def test_precedence_upstream_blocked_beats_missing_evidence(
    generated_at: datetime,
) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_upstream_blocked",
        title="Upstream Blocked",
        description="D",
        required=True,
        expected_evidence_count=1,
        upstream_package_ids=("pkg_1",),
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        upstream_states={"pkg_1": "blocked"},
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    result = report.dimension_results[0]
    assert result.dimension_state is AuditScorecardDimensionState.BLOCKED


def test_precedence_upstream_degraded_beats_missing_evidence(
    generated_at: datetime,
) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_upstream_degraded",
        title="Upstream Degraded",
        description="D",
        required=True,
        expected_evidence_count=1,
        upstream_report_ids=("report_1",),
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        upstream_states={"report_1": "degraded"},
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    result = report.dimension_results[0]
    assert result.dimension_state is AuditScorecardDimensionState.DEGRADED


# ---------------------------------------------------------------------------
# 5. Failure semantics
# ---------------------------------------------------------------------------

def test_duplicate_dimension_ids_fail_closed(generated_at: datetime) -> None:
    dim1 = AuditScorecardDimension(dimension_id="dup", title="A", description="D")
    dim2 = AuditScorecardDimension(dimension_id="dup", title="B", description="D")
    inp = AuditScorecardInput(dimensions=(dim1, dim2), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED
    assert AuditScorecardReasonCode.DUPLICATE_DIMENSION_ID in report.reason_codes


def test_unknown_upstream_state_advisory_finding(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_unknown",
        title="Unknown Upstream",
        description="D",
        upstream_package_ids=("pkg_1",),
    )
    inp = AuditScorecardInput(
        dimensions=(dim,), upstream_states={"pkg_1": "weird"}, generated_at=generated_at
    )
    report = build_audit_scorecard_report(inp)
    assert any(
        f.reason_code is AuditScorecardReasonCode.UNKNOWN_UPSTREAM_STATE
        for f in report.findings
    )


def test_conflicting_links_detected(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_conflict", title="Conflict", description="D")
    ev = AuditScorecardEvidenceRef(evidence_id="ev_1", reference="data/ev.json")
    l_support = AuditScorecardLink(
        link_id="l_support",
        source_id="ev_1",
        target_id="dim_conflict",
        link_type=AuditScorecardLinkType.SUPPORTS,
    )
    l_contra = AuditScorecardLink(
        link_id="l_contra",
        source_id="ev_1",
        target_id="dim_conflict",
        link_type=AuditScorecardLinkType.CONTRADICTS,
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        evidence_refs=(ev,),
        links=(l_support, l_contra),
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED
    assert any(
        f.reason_code is AuditScorecardReasonCode.CONFLICTING_LINK
        for f in report.findings
    )


def test_orphan_evidence_and_links_detected(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_orphan", title="Orphan", description="D", expected_evidence_count=0
    )
    ev = AuditScorecardEvidenceRef(evidence_id="ev_orphan", reference="data/ev.json")
    link = AuditScorecardLink(
        link_id="l_orphan",
        source_id="ev_a",
        target_id="ev_b",
        link_type=AuditScorecardLinkType.COVERS,
    )
    inp = AuditScorecardInput(
        dimensions=(dim,), evidence_refs=(ev,), links=(link,), generated_at=generated_at
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.DEGRADED
    assert any(
        f.reason_code is AuditScorecardReasonCode.ORPHAN_EVIDENCE for f in report.findings
    )
    assert any(
        f.reason_code is AuditScorecardReasonCode.ORPHAN_LINK for f in report.findings
    )


def test_stale_evidence_based_on_caller_timestamps(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_stale", title="Stale", description="D")
    ev = AuditScorecardEvidenceRef(
        evidence_id="ev_stale",
        reference="data/ev.json",
        generated_at=generated_at - timedelta(seconds=7201),
    )
    link = AuditScorecardLink(
        link_id="l_stale",
        source_id="ev_stale",
        target_id="dim_stale",
        link_type=AuditScorecardLinkType.COVERS,
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        evidence_refs=(ev,),
        links=(link,),
        config=AuditScorecardConfig(staleness_threshold_seconds=3600),
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert any(
        f.reason_code is AuditScorecardReasonCode.STALE_EVIDENCE for f in report.findings
    )


def test_missing_manual_review_detected(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_manual",
        title="Manual Review",
        description="D",
        requires_manual_review=True,
    )
    ev = AuditScorecardEvidenceRef(evidence_id="ev_manual", reference="data/ev.json")
    link = AuditScorecardLink(
        link_id="l_manual",
        source_id="ev_manual",
        target_id="dim_manual",
        link_type=AuditScorecardLinkType.COVERS,
    )
    inp = AuditScorecardInput(
        dimensions=(dim,), evidence_refs=(ev,), links=(link,), generated_at=generated_at
    )
    report = build_audit_scorecard_report(inp)
    assert any(
        f.reason_code is AuditScorecardReasonCode.MISSING_MANUAL_REVIEW
        for f in report.findings
    )


# ---------------------------------------------------------------------------
# 6. Aggregation
# ---------------------------------------------------------------------------

def test_aggregation_non_strict_and_strict(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_advisory",
        title="Advisory",
        description="D",
        severity=AuditScorecardSeverity.ADVISORY,
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)

    non_strict = build_audit_scorecard_report(inp, strict=False)
    assert non_strict.state is AuditScorecardState.DEGRADED

    strict = build_audit_scorecard_report(inp, strict=True)
    assert strict.state is AuditScorecardState.BLOCKED


def test_blocked_over_degraded_in_aggregation(generated_at: datetime) -> None:
    blocked_dim = AuditScorecardDimension(
        dimension_id="dim_blocked",
        title="Blocked",
        description="D",
        upstream_package_ids=("pkg_1",),
    )
    degraded_dim = AuditScorecardDimension(
        dimension_id="dim_degraded",
        title="Degraded",
        description="D",
        severity=AuditScorecardSeverity.ADVISORY,
    )
    inp = AuditScorecardInput(
        dimensions=(blocked_dim, degraded_dim),
        upstream_states={"pkg_1": "blocked"},
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED


# ---------------------------------------------------------------------------
# 7. Unsafe content
# ---------------------------------------------------------------------------

def test_unsafe_metadata_blocks_fail_closed(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_safe", title="Safe", description="D")
    inp = AuditScorecardInput(
        dimensions=(dim,),
        metadata={"note": "This is production ready"},
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED
    assert AuditScorecardReasonCode.UNSAFE_CONTENT in report.reason_codes


def test_forbidden_term_in_description_blocks(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_forbidden", title="Forbidden", description="This is production ready"
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED
    assert AuditScorecardReasonCode.FORBIDDEN_TERM_PRESENT in report.reason_codes


# ---------------------------------------------------------------------------
# 8. Determinism
# ---------------------------------------------------------------------------

def test_determinism_across_serializations(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_det", title="Determinism", description="D")
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    r1 = build_audit_scorecard_report(inp)
    r2 = build_audit_scorecard_report(inp)
    assert r1 == r2
    assert audit_scorecard_report_to_dict(r1) == audit_scorecard_report_to_dict(r2)
    assert audit_scorecard_report_to_json_text(r1) == audit_scorecard_report_to_json_text(r2)
    assert audit_scorecard_report_to_csv_text(r1) == audit_scorecard_report_to_csv_text(r2)
    assert audit_scorecard_report_to_markdown_text(r1) == audit_scorecard_report_to_markdown_text(r2)


# ---------------------------------------------------------------------------
# 9. No mutation
# ---------------------------------------------------------------------------

def test_no_mutation_of_original_inputs(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_no_mut", title="No Mutation", description="D")
    ev = AuditScorecardEvidenceRef(evidence_id="ev_no_mut", reference="data/ev.json")
    link = AuditScorecardLink(
        link_id="l_no_mut",
        source_id="ev_no_mut",
        target_id="dim_no_mut",
        link_type=AuditScorecardLinkType.COVERS,
    )
    inp = AuditScorecardInput(
        dimensions=(dim,), evidence_refs=(ev,), links=(link,), generated_at=generated_at
    )
    original_dimensions = inp.dimensions
    original_links = inp.links
    original_evidence = inp.evidence_refs
    build_audit_scorecard_report(inp)
    audit_scorecard_report_to_dict(build_audit_scorecard_report(inp))
    assert inp.dimensions is original_dimensions
    assert inp.links is original_links
    assert inp.evidence_refs is original_evidence


# ---------------------------------------------------------------------------
# 10. Public exports
# ---------------------------------------------------------------------------

def test_public_exports() -> None:
    from hunter.audit_scorecard import (
        audit_scorecard_report_to_csv_text,
        audit_scorecard_report_to_dict,
        audit_scorecard_report_to_json_text,
        audit_scorecard_report_to_markdown_text,
        build_audit_scorecard_report,
        write_audit_scorecard_report,
    )

    assert build_audit_scorecard_report is not None
    assert audit_scorecard_report_to_dict is not None
    assert audit_scorecard_report_to_json_text is not None
    assert audit_scorecard_report_to_csv_text is not None
    assert audit_scorecard_report_to_markdown_text is not None
    assert write_audit_scorecard_report is not None


# ---------------------------------------------------------------------------
# 11. Safety boundaries
# ---------------------------------------------------------------------------

def test_safety_boundaries_in_outputs(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_safe", title="Safety", description="D")
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    md_text = audit_scorecard_report_to_markdown_text(report)
    json_text = audit_scorecard_report_to_json_text(report)

    assert "research-only" in md_text or "research only" in md_text.lower()
    assert "audit-only" in md_text or "audit only" in md_text.lower()
    assert "not an approval" in md_text
    assert "production readiness" in md_text
    assert "trading readiness" in md_text
    assert "not a recommendation" in md_text.lower() or "recommendation" in md_text
    assert "suitability assessment" in md_text
    assert "signal" in md_text
    assert "descriptive" in md_text and "not approval scores" in md_text

    assert "human-audit" in json_text or "research-only" in json_text

    # No actionable trading/execution language outside disclaimers.
    body = md_text.split("## Summary")[0].lower()
    for word in ("buy", "sell", "hold", "go long", "go short"):
        assert word not in body, f"unexpected actionable word: {word}"


# ---------------------------------------------------------------------------
# 12. Opaque references
# ---------------------------------------------------------------------------

def test_opaque_references_no_path_traversal(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_opaque",
        title="Opaque",
        description="D",
        upstream_package_ids=("pkg/../../etc",),
    )
    ev = AuditScorecardEvidenceRef(
        evidence_id="ev_opaque",
        reference="data/../../../etc/passwd",
        generated_at=generated_at,
    )
    inp = AuditScorecardInput(
        dimensions=(dim,), evidence_refs=(ev,), generated_at=generated_at
    )
    report = build_audit_scorecard_report(inp)
    data = audit_scorecard_report_to_dict(report)
    assert data["evidence_refs"][0]["reference"] == "data/../../../etc/passwd"
    assert data["dimensions"][0]["upstream_package_ids"] == ["pkg/../../etc"]
    # No exception implies the writer did not try to open or validate the path.
    audit_scorecard_report_to_markdown_text(report)
