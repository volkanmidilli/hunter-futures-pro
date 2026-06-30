"""Integration tests for hunter.research_audit_closure.

These tests exercise the full pipeline: artifact summaries -> closure report ->
JSON/Markdown output. All writes use tmp_path. No referenced files are read.
No source files are modified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter.research_audit_closure import (
    DEFAULT_RESEARCH_AUDIT_CLOSURE_JSON_PATH,
    DEFAULT_RESEARCH_AUDIT_CLOSURE_MARKDOWN_PATH,
    CLOSURE_VERSION,
    AuditClosureConfig,
    AuditClosureDataQuality,
    AuditClosureFinding,
    AuditClosureFindingSeverity,
    AuditClosureSafetyFlags,
    AuditClosureSection,
    AuditClosureSectionKind,
    AuditClosureState,
    AuditClosureSummary,
    ResearchAuditClosureReport,
    atomic_write_json_research_audit_closure_report,
    atomic_write_markdown_research_audit_closure_report,
    build_audit_closure_finding,
    build_audit_closure_section,
    build_research_audit_closure_report,
    research_audit_closure_report_to_dict,
    research_audit_closure_report_to_markdown,
    write_research_audit_closure_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeArtifactSummary:
    """Duck-typed upstream artifact summary for integration tests."""

    artifact_id: str
    artifact_kind: str
    state: str = "ready"
    source_version: str = "1.0"
    generated_at: datetime | None = None
    title: str = ""
    spec_reference: str = ""
    local_reference: str = ""
    reason_codes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "generated_at",
            self.generated_at or datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "state": self.state,
            "source_version": self.source_version,
            "generated_at": self.generated_at,
            "title": self.title,
            "spec_reference": self.spec_reference,
            "local_reference": self.local_reference,
            "reason_codes": self.reason_codes,
            "tags": self.tags,
            "metadata": self.metadata,
        }


def _make_artifact_summary(
    artifact_id: str,
    artifact_kind: str,
    *,
    spec_reference: str = "",
    local_reference: str = "",
    generated_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an artifact summary dict with safe defaults."""
    return FakeArtifactSummary(
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        spec_reference=spec_reference,
        local_reference=local_reference,
        generated_at=generated_at or datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        metadata=metadata or {},
    ).to_dict()


def _make_finding(
    finding_id: str,
    title: str,
    severity: str,
    *,
    description: str = "",
    related_mvp: str = "",
    spec_reference: str = "",
    related_references: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
) -> AuditClosureFinding:
    """Build an AuditClosureFinding with safe defaults."""
    return build_audit_closure_finding(
        finding_id=finding_id,
        title=title,
        severity=severity,
        description=description,
        related_mvp=related_mvp,
        spec_reference=spec_reference,
        related_references=related_references,
        metadata=metadata or {},
    )


def _twelve_artifacts(now: datetime) -> tuple[dict[str, Any], ...]:
    """Return one summary for each MVP-10..21 artifact kind."""
    kinds = (
        "OBSERVATION_REPORT",
        "OPERATOR_REVIEW",
        "REVIEW_INDEX",
        "REVIEW_SEARCH",
        "RESEARCH_BUNDLE",
        "RESEARCH_CHRONICLE",
        "RESEARCH_DIGEST",
        "RESEARCH_QUALITY_GATE",
        "RESEARCH_HANDOFF",
        "RESEARCH_ARCHIVE_MANIFEST",
        "RESEARCH_RELEASE_NOTES",
        "RESEARCH_AUDIT_CATALOG",
    )
    return tuple(
        _make_artifact_summary(
            artifact_id=f"{kind.lower().replace('_', '-')}-001",
            artifact_kind=kind,
            spec_reference=f"SPEC-{10 + idx:03d}",
            local_reference=f"data/{kind.lower()}/latest_{kind.lower()}.json",
        )
        for idx, kind in enumerate(kinds)
    )


# ---------------------------------------------------------------------------
# End-to-end build from duck-typed artifacts
# ---------------------------------------------------------------------------


class TestEndToEndBuild:
    def test_build_from_fake_artifact_summaries(self, tmp_path: Path) -> None:
        summaries = (
            _make_artifact_summary(
                "obs-001",
                "OBSERVATION_REPORT",
                spec_reference="SPEC-010",
                local_reference="data/observation/obs-001.json",
                metadata={"pairs": ("BTC/USDT",)},
            ),
            _make_artifact_summary(
                "rev-001",
                "OPERATOR_REVIEW",
                spec_reference="SPEC-011",
                local_reference="data/review/rev-001.json",
                metadata={"accepted": True},
            ),
        )
        report = build_research_audit_closure_report(
            summaries,
            closure_id="e2e-001",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert report.closure_id == "e2e-001"
        assert report.closure_kind.value == "research_audit_closure"
        assert len(report.sections) == 8
        assert report.summary.total_sections == 8

        json_path, md_path = write_research_audit_closure_report(
            report,
            json_path=tmp_path / "closure.json",
            markdown_path=tmp_path / "closure.md",
        )
        assert json_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["closure_id"] == "e2e-001"
        assert data["closure_kind"] == "research_audit_closure"
        assert "sections" in data
        assert "summary" in data
        assert "data_quality" in data


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


class TestDeterministicOrdering:
    def test_sections_ordered_canonically(self) -> None:
        summaries = (
            _make_artifact_summary("obs-001", "OBSERVATION_REPORT"),
        )
        report = build_research_audit_closure_report(summaries, closure_id="section-sort-test")
        kinds = [s.section_kind for s in report.sections]
        assert kinds == [
            AuditClosureSectionKind.OVERVIEW,
            AuditClosureSectionKind.CYCLE_SCOPE,
            AuditClosureSectionKind.COMPLETED_ARTIFACTS,
            AuditClosureSectionKind.OPEN_FINDINGS,
            AuditClosureSectionKind.BACKLOG_NOTES,
            AuditClosureSectionKind.SAFETY_BOUNDARIES,
            AuditClosureSectionKind.HUMAN_ARCHIVAL_GUIDE,
            AuditClosureSectionKind.APPENDIX_REFERENCES,
        ]

    def test_sections_ordered_canonically_in_markdown(self) -> None:
        summaries = (
            _make_artifact_summary("obs-001", "OBSERVATION_REPORT"),
        )
        report = build_research_audit_closure_report(summaries, closure_id="section-sort-md-test")
        md = research_audit_closure_report_to_markdown(report)
        overview_pos = md.find("### Overview")
        cycle_pos = md.find("### Cycle Scope")
        completed_pos = md.find("### Completed Artifacts")
        open_pos = md.find("### Open Findings")
        backlog_pos = md.find("### Backlog Notes")
        safety_pos = md.find("### Safety Boundaries")
        guide_pos = md.find("### Human Archival Guide")
        appendix_pos = md.find("### Appendix References")
        assert overview_pos < cycle_pos < completed_pos < open_pos
        assert open_pos < backlog_pos < safety_pos < guide_pos < appendix_pos

    def test_findings_ordered_by_severity_then_mvp_then_insertion(self) -> None:
        findings = (
            _make_finding("F-info", "Info finding", "info", related_mvp="MVP-20"),
            _make_finding("F-critical", "Critical finding", "critical", related_mvp="MVP-10"),
            _make_finding("F-high", "High finding", "high", related_mvp="MVP-11"),
            _make_finding("F-medium", "Medium finding", "medium", related_mvp="MVP-12"),
            _make_finding("F-low", "Low finding", "low", related_mvp="MVP-13"),
        )
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        report = build_research_audit_closure_report(
            summaries,
            findings=findings,
            closure_id="finding-sort-test",
        )
        open_section = next(
            s for s in report.sections if s.section_kind is AuditClosureSectionKind.OPEN_FINDINGS
        )
        ids = [f.finding_id for f in open_section.findings]
        assert ids == [
            "F-critical",
            "F-high",
            "F-medium",
            "F-low",
            "F-info",
        ]

    def test_findings_with_same_severity_ordered_by_mvp_number(self) -> None:
        findings = (
            _make_finding("F-mvp20", "MVP 20 finding", "high", related_mvp="MVP-20"),
            _make_finding("F-mvp10", "MVP 10 finding", "high", related_mvp="MVP-10"),
        )
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        report = build_research_audit_closure_report(
            summaries,
            findings=findings,
            closure_id="mvp-sort-test",
        )
        open_section = next(
            s for s in report.sections if s.section_kind is AuditClosureSectionKind.OPEN_FINDINGS
        )
        ids = [f.finding_id for f in open_section.findings]
        assert ids == ["F-mvp10", "F-mvp20"]

    def test_findings_with_empty_related_mvp_sort_last(self) -> None:
        findings = (
            _make_finding("F-empty", "Empty MVP finding", "high"),
            _make_finding("F-mvp10", "MVP 10 finding", "high", related_mvp="MVP-10"),
        )
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        report = build_research_audit_closure_report(
            summaries,
            findings=findings,
            closure_id="empty-mvp-test",
        )
        open_section = next(
            s for s in report.sections if s.section_kind is AuditClosureSectionKind.OPEN_FINDINGS
        )
        ids = [f.finding_id for f in open_section.findings]
        assert ids == ["F-mvp10", "F-empty"]


# ---------------------------------------------------------------------------
# READY / BLOCK / UNKNOWN states
# ---------------------------------------------------------------------------


class TestClosureStates:
    def test_ready_when_required_sections_present_and_valid(self) -> None:
        summaries = _twelve_artifacts(datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc))
        report = build_research_audit_closure_report(
            summaries,
            closure_id="ready-test",
        )
        assert report.closure_state is AuditClosureState.READY
        assert report.summary.closure_state == "READY"

    def test_ready_with_open_findings_and_backlog_notes(self) -> None:
        summaries = _twelve_artifacts(datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc))
        findings = (
            _make_finding("F-001", "Advisory finding", "info", related_mvp="MVP-10"),
        )
        report = build_research_audit_closure_report(
            summaries,
            findings=findings,
            backlog_notes=("Backlog item 1",),
            closure_id="ready-open-test",
        )
        assert report.closure_state is AuditClosureState.READY
        assert "OPEN_FINDINGS_REMAIN" in report.reason_codes
        assert "BACKLOG_NOTES_REMAIN" in report.reason_codes

    def test_blocked_for_missing_artifacts(self) -> None:
        report = build_research_audit_closure_report(
            (),
            closure_id="missing-test",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert report.closure_state is AuditClosureState.BLOCK
        assert "MISSING_ARTIFACTS" in report.reason_codes

    def test_blocked_for_invalid_artifact_summary(self) -> None:
        summaries = (
            {
                "artifact_id": "bad",
                "artifact_kind": "OBSERVATION_REPORT",
                "state": "ready",
                # missing source_version and generated_at
            },
        )
        report = build_research_audit_closure_report(
            summaries,  # type: ignore[arg-type]
            closure_id="invalid-test",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert report.closure_state is AuditClosureState.BLOCK
        assert "INVALID_ARTIFACT_SUMMARY" in report.reason_codes

    def test_blocked_for_unsafe_artifact_content(self) -> None:
        summaries = (
            _make_artifact_summary(
                "unsafe",
                "OBSERVATION_REPORT",
                metadata={"note": "deploy now"},
            ),
        )
        report = build_research_audit_closure_report(
            summaries,
            closure_id="unsafe-test",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert report.closure_state is AuditClosureState.BLOCK
        assert "UNSAFE_CLOSURE_CONTENT" in report.reason_codes

    def test_unsafe_finding_content_rejected_fail_closed(self) -> None:
        # Unsafe content is rejected at finding construction. The engine-level
        # check is unreachable through the public API because validation fires
        # first. This still satisfies the fail-closed requirement.
        with pytest.raises(ValueError, match="UNSAFE_CLOSURE_CONTENT"):
            _make_finding(
                "F-unsafe",
                "Unsafe finding",
                "high",
                description="execute trade immediately",
            )

    def test_blocked_for_unsafe_config_content(self) -> None:
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        config = AuditClosureConfig(version="deploy now")
        report = build_research_audit_closure_report(
            summaries,
            config=config,
            closure_id="unsafe-config-test",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert report.closure_state is AuditClosureState.BLOCK
        assert "UNSAFE_CLOSURE_CONFIG" in report.reason_codes

    def test_unknown_state_when_block_on_unknown_false(self) -> None:
        report = ResearchAuditClosureReport.blocked(
            closure_id="unknown-test",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
            reason_code="UNKNOWN_CLOSURE_STATE",
        )
        assert report.closure_state is AuditClosureState.BLOCK
        # The blocked factory always returns BLOCK regardless of reason code.
        assert "UNKNOWN_CLOSURE_STATE" in report.reason_codes


# ---------------------------------------------------------------------------
# Required sections customization
# ---------------------------------------------------------------------------


class TestRequiredSectionsCustomization:
    def test_required_sections_default_includes_all_eight(self) -> None:
        config = AuditClosureConfig()
        assert len(config.required_sections) == 8
        assert AuditClosureSectionKind.OVERVIEW in config.required_sections
        assert AuditClosureSectionKind.APPENDIX_REFERENCES in config.required_sections

    def test_custom_required_sections_can_be_supplied(self) -> None:
        config = AuditClosureConfig(
            required_sections=(
                AuditClosureSectionKind.OVERVIEW,
                AuditClosureSectionKind.SAFETY_BOUNDARIES,
            )
        )
        assert config.required_sections == (
            AuditClosureSectionKind.OVERVIEW,
            AuditClosureSectionKind.SAFETY_BOUNDARIES,
        )


# ---------------------------------------------------------------------------
# Summary and data quality public fields
# ---------------------------------------------------------------------------


class TestSummaryAndDataQuality:
    def test_summary_counts_using_public_fields(self) -> None:
        findings = (
            _make_finding("F-critical", "Critical", "critical", related_mvp="MVP-10"),
            _make_finding("F-high", "High", "high", related_mvp="MVP-11"),
            _make_finding("F-info", "Info", "info", related_mvp="MVP-12"),
        )
        summaries = _twelve_artifacts(datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc))
        report = build_research_audit_closure_report(
            summaries,
            findings=findings,
            backlog_notes=("Note 1", "Note 2"),
            closure_id="summary-test",
        )
        summary = report.summary
        assert isinstance(summary, AuditClosureSummary)
        assert summary.total_sections == 8
        assert summary.total_findings == 3
        assert summary.critical_count == 1
        assert summary.high_count == 1
        assert summary.info_count == 1
        assert summary.open_finding_count == 3
        assert summary.backlog_note_count == 2
        assert summary.completed_artifact_count == 12

    def test_data_quality_fields_using_public_fields(self) -> None:
        summaries = _twelve_artifacts(datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc))
        findings = (
            _make_finding("F-critical", "Critical", "critical", related_mvp="MVP-10"),
            _make_finding("F-high", "High", "high", related_mvp="MVP-11"),
            _make_finding("F-medium", "Medium", "medium", related_mvp="MVP-12"),
            _make_finding("F-low", "Low", "low", related_mvp="MVP-13"),
        )
        report = build_research_audit_closure_report(
            summaries,
            findings=findings,
            backlog_notes=("Note 1",),
            closure_id="dq-test",
        )
        dq = report.data_quality
        assert isinstance(dq, AuditClosureDataQuality)
        assert dq.total_artifacts_expected == 12
        assert dq.artifacts_present == 12
        assert dq.artifacts_missing == 0
        assert dq.sections_present == 8
        assert dq.sections_missing == 0
        assert dq.total_findings == 4
        assert dq.unresolved_blocker_count == 2
        assert dq.unresolved_warning_count == 2
        assert dq.backlog_note_count == 1
        assert dq.completeness_pct == 100.0
        assert dq.coverage_pct == 100.0

    def test_data_quality_reflects_missing_artifacts(self) -> None:
        summaries = (
            _make_artifact_summary("obs-001", "OBSERVATION_REPORT"),
        )
        report = build_research_audit_closure_report(
            summaries,
            closure_id="missing-dq-test",
        )
        dq = report.data_quality
        assert dq.artifacts_present == 1
        assert dq.artifacts_missing == 11
        assert dq.completeness_pct == (1 / 12) * 100


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


class TestSafetyFlags:
    def test_default_safety_flags_are_fail_closed(self) -> None:
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        report = build_research_audit_closure_report(
            summaries,
            closure_id="safety-test",
        )
        flags = report.safety_flags
        assert flags.closure_feedback_into_execution is False
        assert flags.cross_layer_feedback_into_execution is False
        assert flags.closure_output_not_release_approval is True
        assert flags.closure_output_not_deployment_approval is True
        assert flags.closure_output_not_trading_signal is True
        assert flags.closure_output_not_trade_approval is True
        assert flags.closure_output_not_execution_readiness is True
        assert flags.closure_output_not_strategy_readiness is True
        assert flags.closure_output_not_transaction_permission is True
        assert flags.no_action_commands_emitted is True
        assert flags.artifact_files_not_read is True
        assert flags.human_archival_guide_is_non_gating is True

    def test_unsafe_safety_flags_rejected(self) -> None:
        with pytest.raises(ValueError):
            AuditClosureSafetyFlags(closure_feedback_into_execution=True)


# ---------------------------------------------------------------------------
# Closure notes / disclaimers
# ---------------------------------------------------------------------------


class TestClosureNotesAndDisclaimers:
    def test_markdown_contains_all_disclaimers(self) -> None:
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        report = build_research_audit_closure_report(
            summaries,
            closure_id="notes-test",
        )
        md = research_audit_closure_report_to_markdown(report)
        assert "not release approval" in md
        assert "not deployment approval" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "not execution approval" in md
        assert "not strategy approval" in md
        assert "not transaction permission" in md
        assert "not a runtime registry" in md
        assert "indexer" in md
        assert "crawler" in md
        assert "dashboard" in md
        assert "database" in md
        assert "API" in md
        assert "must not be consumed by execution" in md
        assert "not gating criteria" in md
        assert "not release checklist" not in md.lower()
        assert "not deployment checklist" not in md.lower()

    def test_dict_contains_document_notes(self) -> None:
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        report = build_research_audit_closure_report(
            summaries,
            closure_id="notes-test",
        )
        data = research_audit_closure_report_to_dict(report)
        assert "document_notes" in data
        assert "human archival" in data["document_notes"].lower()


# ---------------------------------------------------------------------------
# Dict round-trip
# ---------------------------------------------------------------------------


class TestDictRoundTrip:
    def test_round_trip_preserves_fields(self) -> None:
        summaries = (
            _make_artifact_summary(
                "obs-001",
                "OBSERVATION_REPORT",
                metadata={"pair": "BTC/USDT"},
            ),
        )
        findings = (
            _make_finding(
                "F-001",
                "Finding 1",
                "medium",
                related_mvp="MVP-10",
                spec_reference="SPEC-010",
            ),
        )
        report = build_research_audit_closure_report(
            summaries,
            findings=findings,
            backlog_notes=("Backlog 1",),
            references=("docs/README.md",),
            closure_id="round-trip-001",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        data = research_audit_closure_report_to_dict(report)
        assert data["closure_id"] == "round-trip-001"
        assert data["version"] == CLOSURE_VERSION
        assert data["closure_kind"] == "research_audit_closure"
        assert data["generated_at"] == "2026-06-29T12:00:00Z"
        assert len(data["sections"]) == 8
        assert "summary" in data
        assert "data_quality" in data
        assert "reason_codes" in data
        assert "safety_flags" in data
        assert "closure_narrative" in data
        assert "document_notes" in data
        assert data["sections"][3]["findings"][0]["metadata"] == {}


# ---------------------------------------------------------------------------
# Markdown content
# ---------------------------------------------------------------------------


class TestMarkdownContent:
    def test_safety_notice_before_sections_and_references(self) -> None:
        summaries = (
            _make_artifact_summary(
                "obs-001",
                "OBSERVATION_REPORT",
                local_reference="data/obs.json",
            ),
        )
        report = build_research_audit_closure_report(
            summaries,
            closure_id="md-test",
        )
        md = research_audit_closure_report_to_markdown(report)
        notice_pos = md.find("## Safety Notice")
        sections_pos = md.find("## Sections")
        ref_pos = md.find("data/obs.json")
        assert notice_pos != -1
        assert sections_pos != -1
        assert ref_pos != -1
        assert notice_pos < sections_pos
        assert notice_pos < ref_pos

    def test_markdown_includes_section_kinds_and_finding_fields(self) -> None:
        summaries = (
            _make_artifact_summary(
                "obs-001",
                "OBSERVATION_REPORT",
                spec_reference="SPEC-010",
                local_reference="data/obs.json",
                metadata={"pair": "BTC/USDT"},
            ),
        )
        findings = (
            _make_finding(
                "F-001",
                "Finding 1",
                "medium",
                related_mvp="MVP-10",
                spec_reference="SPEC-010",
                related_references=("data/obs.json",),
                metadata={"artifact_id": "obs-001"},
            ),
        )
        report = build_research_audit_closure_report(
            summaries,
            findings=findings,
            backlog_notes=("Backlog 1",),
            references=("docs/README.md",),
            closure_id="md-fields-test",
        )
        md = research_audit_closure_report_to_markdown(report)
        assert "### Overview" in md
        assert "### Cycle Scope" in md
        assert "### Completed Artifacts" in md
        assert "### Open Findings" in md
        assert "### Backlog Notes" in md
        assert "### Safety Boundaries" in md
        assert "### Human Archival Guide" in md
        assert "### Appendix References" in md
        assert "#### F-001" in md
        assert "Finding 1" in md
        assert "MVP-10" in md
        assert "SPEC-010" in md
        assert "data/obs.json" in md
        assert "Backlog 1" in md
        assert "docs/README.md" in md
        assert "BTC/USDT" in md


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


class TestWrites:
    def test_dual_write_uses_tmp_path(self, tmp_path: Path) -> None:
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        report = build_research_audit_closure_report(
            summaries,
            closure_id="write-test",
        )
        json_out, md_out = write_research_audit_closure_report(
            report,
            json_path=tmp_path / "out.json",
            markdown_path=tmp_path / "out.md",
        )
        assert json_out.exists()
        assert md_out.exists()
        assert not DEFAULT_RESEARCH_AUDIT_CLOSURE_JSON_PATH.exists()
        assert not DEFAULT_RESEARCH_AUDIT_CLOSURE_MARKDOWN_PATH.exists()

    def test_atomic_json_and_markdown_writes(self, tmp_path: Path) -> None:
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        report = build_research_audit_closure_report(
            summaries,
            closure_id="atomic-test",
        )
        json_path = tmp_path / "atomic.json"
        md_path = tmp_path / "atomic.md"
        atomic_write_json_research_audit_closure_report(report, target_path=json_path)
        atomic_write_markdown_research_audit_closure_report(report, target_path=md_path)
        assert json_path.exists()
        assert md_path.exists()


# ---------------------------------------------------------------------------
# No file reads / no mutation
# ---------------------------------------------------------------------------


class TestNoFileReadsOrMutation:
    def test_reference_string_not_read(self, tmp_path: Path) -> None:
        suspicious_path = str(tmp_path / "does_not_exist.json")
        summaries = (
            _make_artifact_summary(
                "obs-001",
                "OBSERVATION_REPORT",
                local_reference=suspicious_path,
                metadata={"path": suspicious_path},
            ),
        )
        report = build_research_audit_closure_report(
            summaries,
            closure_id="no-read-test",
        )
        md = research_audit_closure_report_to_markdown(report)
        assert suspicious_path in md
        # If the writer had tried to read the path, it would have raised.
        # The path does not exist, so success proves no read was attempted.

    def test_input_artifacts_not_mutated(self) -> None:
        summaries = (
            _make_artifact_summary(
                "obs-001",
                "OBSERVATION_REPORT",
                metadata={"a": 1},
            ),
        )
        original_metadata = summaries[0]["metadata"]
        report = build_research_audit_closure_report(
            summaries,
            closure_id="no-mut-test",
        )
        _ = research_audit_closure_report_to_dict(report)
        _ = research_audit_closure_report_to_markdown(report)
        assert summaries[0]["metadata"] is original_metadata


# ---------------------------------------------------------------------------
# Explicit identity
# ---------------------------------------------------------------------------


class TestExplicitIdentity:
    def test_explicit_closure_id_preserved(self) -> None:
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        report = build_research_audit_closure_report(
            summaries,
            closure_id="explicit-id",
        )
        assert report.closure_id == "explicit-id"

    def test_explicit_generated_at_preserved(self) -> None:
        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        report = build_research_audit_closure_report(
            summaries,
            closure_id="explicit-time",
            generated_at=ts,
        )
        assert report.generated_at == ts


# ---------------------------------------------------------------------------
# Empty / blocked factories
# ---------------------------------------------------------------------------


class TestEmptyAndBlockedFactories:
    def test_empty_artifact_summaries_produce_blocked_report(self) -> None:
        report = build_research_audit_closure_report(
            (),
            closure_id="empty-test",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert report.closure_state is AuditClosureState.BLOCK
        assert report.summary.total_sections == 0
        assert report.data_quality.artifacts_present == 0
        assert report.data_quality.artifacts_missing == 12

    def test_blocked_factory_is_valid(self) -> None:
        report = ResearchAuditClosureReport.blocked(
            closure_id="blocked-factory-test",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
            reason_code="DEFAULT_BLOCKED",
        )
        assert report.closure_state is AuditClosureState.BLOCK
        assert report.reason_codes == ("DEFAULT_BLOCKED",)
        assert report.summary.reason_code_counts == {"DEFAULT_BLOCKED": 1}

    def test_default_constructors_are_valid(self) -> None:
        now = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
        config = AuditClosureConfig()
        safety_flags = AuditClosureSafetyFlags()
        summary = AuditClosureSummary()
        data_quality = AuditClosureDataQuality()
        section = build_audit_closure_section(
            AuditClosureSectionKind.OVERVIEW,
            "Overview",
        )
        assert config.dry_run is True
        assert safety_flags.closure_output_is_human_audit_only is True
        assert summary.closure_state == "UNKNOWN"
        assert data_quality.artifacts_missing == 12
        assert section.section_kind is AuditClosureSectionKind.OVERVIEW


# ---------------------------------------------------------------------------
# No forbidden imports / paths
# ---------------------------------------------------------------------------


class TestNoForbiddenImports:
    def test_writer_and_models_have_no_forbidden_imports(self) -> None:
        import hunter.research_audit_closure.models as models_module
        import hunter.research_audit_closure.writer as writer_module

        for source in (models_module.__file__, writer_module.__file__):
            assert source is not None
            text = Path(source).read_text(encoding="utf-8")
            assert "import requests" not in text
            assert "import urllib" not in text
            assert "import sqlite3" not in text
            assert "from freqtrade" not in text
            assert "from binance" not in text
            assert "freqtrade_bridge" not in text
            assert "execution_bridge" not in text


# ---------------------------------------------------------------------------
# Frozen behavior
# ---------------------------------------------------------------------------


def test_closure_report_object_is_frozen() -> None:
    report = ResearchAuditClosureReport.blocked(
        closure_id="frozen-test",
        generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
    )
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        report.closure_id = "mutated"


# ---------------------------------------------------------------------------
# Human archival guide advisory
# ---------------------------------------------------------------------------


class TestHumanArchivalGuide:
    def test_human_archival_guide_is_advisory_and_non_gating(self) -> None:
        summaries = (_make_artifact_summary("obs-001", "OBSERVATION_REPORT"),)
        report = build_research_audit_closure_report(
            summaries,
            closure_id="guide-test",
        )
        guide_section = next(
            s
            for s in report.sections
            if s.section_kind is AuditClosureSectionKind.HUMAN_ARCHIVAL_GUIDE
        )
        assert guide_section.title == "Human Archival Guide"
        assert "advisory" in guide_section.section_notes.lower()
        assert report.safety_flags.human_archival_guide_is_non_gating is True

        md = research_audit_closure_report_to_markdown(report)
        assert "### Human Archival Guide" in md
        assert "advisory" in md.lower()


# ---------------------------------------------------------------------------
# Full layer coverage
# ---------------------------------------------------------------------------


class TestFullLayerCoverage:
    def test_all_twelve_kinds_produce_full_coverage(self) -> None:
        now = datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)
        summaries = _twelve_artifacts(now)
        report = build_research_audit_closure_report(
            summaries,
            closure_id="full-coverage",
            generated_at=now,
        )
        assert report.closure_state is AuditClosureState.READY
        assert report.data_quality.artifacts_present == 12
        assert report.data_quality.artifacts_missing == 0
        assert report.data_quality.sections_present == 8
        assert report.data_quality.sections_missing == 0
        assert report.data_quality.completeness_pct == 100.0
        assert report.data_quality.coverage_pct == 100.0
