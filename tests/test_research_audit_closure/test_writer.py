"""Tests for hunter.research_audit_closure.writer."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter.research_audit_closure import (
    DEFAULT_RESEARCH_AUDIT_CLOSURE_JSON_PATH,
    DEFAULT_RESEARCH_AUDIT_CLOSURE_MARKDOWN_PATH,
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
    audit_closure_config_to_dict,
    audit_closure_data_quality_to_dict,
    audit_closure_finding_to_dict,
    audit_closure_safety_flags_to_dict,
    audit_closure_section_to_dict,
    audit_closure_summary_to_dict,
    build_audit_closure_finding,
    build_audit_closure_section,
    build_research_audit_closure_report,
    research_audit_closure_report_to_dict,
    research_audit_closure_report_to_markdown,
    write_research_audit_closure_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_finding() -> AuditClosureFinding:
    return build_audit_closure_finding(
        finding_id="F-001",
        title="Missing metadata",
        severity="high",
        description="One artifact lacks metadata.",
        related_mvp="MVP-11",
        spec_reference="SPEC-011",
        related_references=("data/observation/latest_observation_report.json",),
        metadata={"artifact_id": "obs-001"},
    )


@pytest.fixture
def sample_report(now: datetime, sample_finding: AuditClosureFinding) -> ResearchAuditClosureReport:
    summaries = (
        {
            "artifact_id": "obs-001",
            "artifact_kind": "OBSERVATION_REPORT",
            "state": "ready",
            "source_version": "1.0",
            "generated_at": now,
            "spec_reference": "SPEC-011",
            "local_reference": "data/observation/latest_observation_report.json",
        },
        {
            "artifact_id": "rev-001",
            "artifact_kind": "OPERATOR_REVIEW",
            "state": "ready",
            "source_version": "1.0",
            "generated_at": now,
            "spec_reference": "SPEC-012",
            "local_reference": "data/review/latest_review_audit_record.json",
        },
    )
    return build_research_audit_closure_report(
        summaries,
        findings=(sample_finding,),
        backlog_notes=("Review backlog item 1",),
        references=("docs/audit/README.md",),
        closure_id="closure-test-001",
        generated_at=now,
    )


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


class TestAuditClosureConfigToDict:
    def test_round_trip_values(self) -> None:
        config = AuditClosureConfig()
        data = audit_closure_config_to_dict(config)
        assert data["version"] == "1.0"
        assert data["output_format"] == "both"
        assert data["dry_run"] is True
        assert data["block_on_unknown"] is True
        assert data["expected_artifact_count"] == 12


class TestAuditClosureSafetyFlagsToDict:
    def test_all_flags_present(self) -> None:
        flags = AuditClosureSafetyFlags()
        data = audit_closure_safety_flags_to_dict(flags)
        assert data["closure_output_is_human_audit_only"] is True
        assert data["closure_output_not_trade_approval"] is True
        assert data["closure_output_not_release_approval"] is True
        assert data["closure_output_not_deployment_approval"] is True
        assert data["closure_output_not_execution_readiness"] is True
        assert data["live_trading_enabled"] is False
        assert data["database_persistence_enabled"] is False
        assert data["runtime_registry_enabled"] is False
        assert data["indexer_crawler_enabled"] is False


class TestAuditClosureFindingToDict:
    def test_enum_values_are_strings(self, sample_finding: AuditClosureFinding) -> None:
        data = audit_closure_finding_to_dict(sample_finding)
        assert data["finding_id"] == "F-001"
        assert data["severity"] == "HIGH"

    def test_metadata_passthrough(self, sample_finding: AuditClosureFinding) -> None:
        data = audit_closure_finding_to_dict(sample_finding)
        assert data["metadata"] == {"artifact_id": "obs-001"}
        assert isinstance(data["metadata"], dict)

    def test_reference_strings_remain_strings(self, sample_finding: AuditClosureFinding) -> None:
        data = audit_closure_finding_to_dict(sample_finding)
        assert data["spec_reference"] == "SPEC-011"
        assert data["related_references"] == [
            "data/observation/latest_observation_report.json"
        ]


class TestAuditClosureSectionToDict:
    def test_section_kind_is_string(self, sample_finding: AuditClosureFinding) -> None:
        section = build_audit_closure_section(
            AuditClosureSectionKind.OPEN_FINDINGS,
            "Open Findings",
            findings=(sample_finding,),
            references=("ref-1",),
        )
        data = audit_closure_section_to_dict(section)
        assert data["section_kind"] == "open_findings"
        assert isinstance(data["findings"], list)
        assert data["findings"][0]["finding_id"] == "F-001"


class TestAuditClosureSummaryToDict:
    def test_closure_state_string(self) -> None:
        summary = AuditClosureSummary(
            total_sections=8,
            total_findings=1,
            high_count=1,
            closure_state="READY",
            reason_code_counts={"OPEN_FINDINGS_REMAIN": 1},
        )
        data = audit_closure_summary_to_dict(summary)
        assert data["closure_state"] == "READY"
        assert data["reason_code_counts"] == {"OPEN_FINDINGS_REMAIN": 1}


class TestAuditClosureDataQualityToDict:
    def test_coverage_fields(self) -> None:
        dq = AuditClosureDataQuality(
            total_artifacts_expected=12,
            artifacts_present=10,
            artifacts_missing=2,
            sections_present=8,
            sections_missing=0,
            completeness_pct=83.33,
            coverage_pct=100.0,
        )
        data = audit_closure_data_quality_to_dict(dq)
        assert data["completeness_pct"] == 83.33
        assert data["coverage_pct"] == 100.0


class TestResearchAuditClosureReportToDict:
    def test_top_level_keys(self, sample_report: ResearchAuditClosureReport) -> None:
        data = research_audit_closure_report_to_dict(sample_report)
        assert data["closure_id"] == "closure-test-001"
        assert data["closure_kind"] == "research_audit_closure"
        assert data["closure_state"] == "ready"
        assert data["version"] == "1.0"
        assert "document_notes" in data

    def test_sections_are_list_of_dicts(self, sample_report: ResearchAuditClosureReport) -> None:
        data = research_audit_closure_report_to_dict(sample_report)
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) == 8
        kinds = {s["section_kind"] for s in data["sections"]}
        assert "overview" in kinds
        assert "open_findings" in kinds

    def test_metadata_in_sections_is_plain_dict(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        data = research_audit_closure_report_to_dict(sample_report)
        finding_metadata = data["sections"][3]["findings"][0]["metadata"]
        assert isinstance(finding_metadata, dict)
        assert finding_metadata["artifact_id"] == "obs-001"

    def test_no_mutation(self, sample_report: ResearchAuditClosureReport) -> None:
        original_sections = sample_report.sections
        original_metadata = sample_report.sections[3].findings[0].metadata
        research_audit_closure_report_to_dict(sample_report)
        assert sample_report.sections is original_sections
        assert sample_report.sections[3].findings[0].metadata is original_metadata

    def test_blocked_report_serializes(self, now: datetime) -> None:
        report = ResearchAuditClosureReport.blocked(
            closure_id="blocked-test",
            generated_at=now,
            reason_code="DEFAULT_BLOCKED",
        )
        data = research_audit_closure_report_to_dict(report)
        assert data["closure_state"] == "block"
        assert data["reason_codes"] == ["DEFAULT_BLOCKED"]

    def test_unknown_state_serializes(self, now: datetime) -> None:
        report = ResearchAuditClosureReport(
            closure_id="unknown-test",
            generated_at=now,
            closure_state=AuditClosureState.UNKNOWN,
            reason_codes=("UNKNOWN_CLOSURE_STATE",),
        )
        data = research_audit_closure_report_to_dict(report)
        assert data["closure_state"] == "unknown"
        assert data["reason_codes"] == ["UNKNOWN_CLOSURE_STATE"]


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_json_determinism(self, sample_report: ResearchAuditClosureReport) -> None:
        data1 = research_audit_closure_report_to_dict(sample_report)
        data2 = research_audit_closure_report_to_dict(sample_report)
        assert json.dumps(data1, sort_keys=True) == json.dumps(data2, sort_keys=True)

    def test_markdown_determinism(self, sample_report: ResearchAuditClosureReport) -> None:
        md1 = research_audit_closure_report_to_markdown(sample_report)
        md2 = research_audit_closure_report_to_markdown(sample_report)
        assert md1 == md2


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


class TestMarkdownOutput:
    def test_safety_notice_before_sections(self, sample_report: ResearchAuditClosureReport) -> None:
        md = research_audit_closure_report_to_markdown(sample_report)
        notice_pos = md.find("## Safety Notice")
        sections_pos = md.find("## Sections")
        assert notice_pos != -1
        assert sections_pos != -1
        assert notice_pos < sections_pos

    def test_safety_notice_contains_required_statements(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        md = research_audit_closure_report_to_markdown(sample_report)
        assert "human-audit / contractor-handoff artifact only" in md
        assert "not release approval" in md
        assert "not deployment approval" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "not execution approval" in md
        assert "not strategy approval" in md
        assert "not transaction permission" in md
        assert "not a runtime registry" in md
        assert "not traversed, opened, followed, validated, or executed" in md
        assert "Referenced artifact files are not read" in md
        assert "Human archival guide entries are advisory only" in md
        assert "not gating criteria" in md

    def test_markdown_section_ordering(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        md = research_audit_closure_report_to_markdown(sample_report)
        overview_pos = md.find("### Overview")
        cycle_pos = md.find("### Cycle Scope")
        completed_pos = md.find("### Completed Artifacts")
        open_pos = md.find("### Open Findings")
        backlog_pos = md.find("### Backlog Notes")
        safety_pos = md.find("### Safety Boundaries")
        guide_pos = md.find("### Human Archival Guide")
        appendix_pos = md.find("### Appendix References")
        assert overview_pos != -1
        assert cycle_pos != -1
        assert completed_pos != -1
        assert open_pos != -1
        assert backlog_pos != -1
        assert safety_pos != -1
        assert guide_pos != -1
        assert appendix_pos != -1
        assert overview_pos < cycle_pos < completed_pos < open_pos
        assert open_pos < backlog_pos < safety_pos < guide_pos < appendix_pos

    def test_markdown_finding_ordering(self, now: datetime) -> None:
        findings = (
            build_audit_closure_finding(
                finding_id="F-info",
                title="Info finding",
                severity="info",
                related_mvp="MVP-20",
            ),
            build_audit_closure_finding(
                finding_id="F-critical",
                title="Critical finding",
                severity="critical",
                related_mvp="MVP-10",
            ),
            build_audit_closure_finding(
                finding_id="F-high",
                title="High finding",
                severity="high",
                related_mvp="MVP-11",
            ),
        )
        section = build_audit_closure_section(
            AuditClosureSectionKind.OPEN_FINDINGS,
            "Open Findings",
            findings=findings,
        )
        report = ResearchAuditClosureReport(
            closure_id="order-test",
            generated_at=now,
            closure_state=AuditClosureState.BLOCK,
            sections=(section,),
            summary=AuditClosureSummary(
                total_sections=1,
                total_findings=3,
                critical_count=1,
                high_count=1,
                info_count=1,
                closure_state="BLOCK",
                reason_code_counts={"UNRESOLVED_BLOCKERS": 1},
            ),
            data_quality=AuditClosureDataQuality(
                total_artifacts_expected=12,
                artifacts_present=0,
                artifacts_missing=12,
                sections_present=1,
                sections_missing=7,
            ),
            reason_codes=("UNRESOLVED_BLOCKERS",),
        )
        md = research_audit_closure_report_to_markdown(report)
        critical_pos = md.find("#### F-critical")
        high_pos = md.find("#### F-high")
        info_pos = md.find("#### F-info")
        assert critical_pos != -1
        assert high_pos != -1
        assert info_pos != -1
        assert critical_pos < high_pos < info_pos

    def test_markdown_includes_closure_notes(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        md = research_audit_closure_report_to_markdown(sample_report)
        assert "## Closure Notes" in md
        assert "static snapshot" in md
        assert "does not scan directories" in md

    def test_markdown_includes_human_archival_guide_advisory(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        md = research_audit_closure_report_to_markdown(sample_report)
        assert "### Human Archival Guide" in md

    def test_markdown_no_action_commands(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        md = research_audit_closure_report_to_markdown(sample_report)
        assert "run(" not in md
        assert "execute(" not in md
        assert "deploy(" not in md

    def test_reference_strings_plain_text(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        md = research_audit_closure_report_to_markdown(sample_report)
        assert "data/observation/latest_observation_report.json" in md
        assert "[data/observation" not in md

    def test_metadata_strings_plain_text(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        md = research_audit_closure_report_to_markdown(sample_report)
        assert "obs-001" in md

    def test_closure_id_and_state_present(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        md = research_audit_closure_report_to_markdown(sample_report)
        assert "closure-test-001" in md
        assert "block" in md.lower()


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


class TestAtomicWrites:
    def test_atomic_json_write(self, tmp_path: Path, sample_report: ResearchAuditClosureReport) -> None:
        target = tmp_path / "closure.json"
        result = atomic_write_json_research_audit_closure_report(
            sample_report, target_path=target
        )
        assert result == target
        assert target.exists()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["closure_id"] == "closure-test-001"
        assert data["closure_state"] == "ready"

    def test_atomic_markdown_write(
        self, tmp_path: Path, sample_report: ResearchAuditClosureReport
    ) -> None:
        target = tmp_path / "closure.md"
        result = atomic_write_markdown_research_audit_closure_report(
            sample_report, target_path=target
        )
        assert result == target
        assert target.exists()
        md = target.read_text(encoding="utf-8")
        assert "# Local Research Audit Closure Report" in md
        assert "## Safety Notice" in md

    def test_dual_write(self, tmp_path: Path, sample_report: ResearchAuditClosureReport) -> None:
        json_path = tmp_path / "dual.json"
        md_path = tmp_path / "dual.md"
        json_out, md_out = write_research_audit_closure_report(
            sample_report,
            json_path=json_path,
            markdown_path=md_path,
        )
        assert json_out == json_path
        assert md_out == md_path
        assert json_path.exists()
        assert md_path.exists()

    def test_parent_directories_created(
        self, tmp_path: Path, sample_report: ResearchAuditClosureReport
    ) -> None:
        target = tmp_path / "nested" / "dir" / "closure.json"
        atomic_write_json_research_audit_closure_report(
            sample_report, target_path=target
        )
        assert target.exists()

    def test_default_paths_are_research_audit_closure(self) -> None:
        assert DEFAULT_RESEARCH_AUDIT_CLOSURE_JSON_PATH == Path(
            "data/research_audit_closure/latest_research_audit_closure_report.json"
        )
        assert DEFAULT_RESEARCH_AUDIT_CLOSURE_MARKDOWN_PATH == Path(
            "reports/research_audit_closure/latest_research_audit_closure_report.md"
        )


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


class TestWriterSafety:
    def test_no_production_default_path_writes(
        self, tmp_path: Path, sample_report: ResearchAuditClosureReport
    ) -> None:
        target = tmp_path / "explicit.json"
        atomic_write_json_research_audit_closure_report(
            sample_report, target_path=target
        )
        assert not DEFAULT_RESEARCH_AUDIT_CLOSURE_JSON_PATH.exists()
        assert not DEFAULT_RESEARCH_AUDIT_CLOSURE_MARKDOWN_PATH.exists()

    def test_metadata_strings_not_traversed(
        self, tmp_path: Path, now: datetime
    ) -> None:
        finding = build_audit_closure_finding(
            finding_id="F-002",
            title="Path note",
            severity="info",
            related_references=("/tmp/missing_file.json",),
            metadata={"path": "/tmp/missing_file.json"},
        )
        section = build_audit_closure_section(
            AuditClosureSectionKind.OPEN_FINDINGS,
            "Open Findings",
            findings=(finding,),
        )
        report = ResearchAuditClosureReport(
            closure_id="path-test",
            generated_at=now,
            closure_state=AuditClosureState.BLOCK,
            sections=(section,),
            summary=AuditClosureSummary(
                total_sections=1,
                total_findings=1,
                info_count=1,
                closure_state="BLOCK",
            ),
            data_quality=AuditClosureDataQuality(
                total_artifacts_expected=12,
                artifacts_present=0,
                artifacts_missing=12,
                sections_present=1,
                sections_missing=7,
            ),
            reason_codes=("OPEN_FINDINGS_REMAIN",),
        )
        md = research_audit_closure_report_to_markdown(report)
        assert "/tmp/missing_file.json" in md
        assert "No such file" not in md

    def test_markdown_contains_no_release_ready_language(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        md = research_audit_closure_report_to_markdown(sample_report)
        assert "release ready" not in md.lower()
        assert "deployment ready" not in md.lower()
        assert "execution ready" not in md.lower()
        assert "strategy ready" not in md.lower()
        assert "go live" not in md.lower()

    def test_json_sort_keys(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        data = research_audit_closure_report_to_dict(sample_report)
        json_text = json.dumps(data, sort_keys=True)
        reparsed = json.loads(json_text)
        assert json.dumps(reparsed, sort_keys=True) == json_text

    def test_writer_does_not_mutate_metadata_type(
        self, sample_report: ResearchAuditClosureReport
    ) -> None:
        original = sample_report.sections[3].findings[0].metadata
        research_audit_closure_report_to_dict(sample_report)
        assert sample_report.sections[3].findings[0].metadata is original

    def test_mapping_proxy_type_converted_to_dict(
        self, now: datetime
    ) -> None:
        report = ResearchAuditClosureReport.blocked(
            closure_id="proxy-test",
            generated_at=now,
            reason_code="DEFAULT_BLOCKED",
        )
        data = research_audit_closure_report_to_dict(report)
        assert isinstance(data["summary"]["reason_code_counts"], dict)

    def test_invalid_output_path_type_raises(self, sample_report: ResearchAuditClosureReport) -> None:
        with pytest.raises(TypeError):
            atomic_write_json_research_audit_closure_report(
                sample_report, target_path=123  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# Frozen imports
# ---------------------------------------------------------------------------


def test_frozen_report_cannot_be_mutated(sample_report: ResearchAuditClosureReport) -> None:
    with pytest.raises(FrozenInstanceError):
        sample_report.closure_id = "mutated"
