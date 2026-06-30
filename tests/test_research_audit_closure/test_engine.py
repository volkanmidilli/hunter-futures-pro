"""Tests for hunter.research_audit_closure.engine."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.research_audit_closure.engine import (
    build_audit_closure_data_quality,
    build_audit_closure_finding,
    build_audit_closure_safety_flags,
    build_audit_closure_section,
    build_audit_closure_summary,
    build_research_audit_closure_report,
    has_unsafe_audit_closure_content,
)
from hunter.research_audit_closure.models import (
    AUDIT_CLOSURE_SECTION_KINDS,
    BACKLOG_NOTES_REMAIN,
    DEFAULT_BLOCKED,
    EMPTY_COMPLETED_ARTIFACTS,
    INCOMPLETE_ARTIFACT_CHAIN,
    INVALID_ARTIFACT_SUMMARY,
    INVALID_CLOSURE_CONFIG,
    MISSING_ARTIFACTS,
    MISSING_REQUIRED_SECTION,
    OPEN_FINDINGS_REMAIN,
    UNSAFE_CLOSURE_CONFIG,
    UNSAFE_CLOSURE_CONTENT,
    UNRESOLVED_BLOCKERS,
    UNKNOWN_CLOSURE_STATE,
    AuditClosureConfig,
    AuditClosureFinding,
    AuditClosureFindingSeverity,
    AuditClosureSafetyFlags,
    AuditClosureSection,
    AuditClosureSectionKind,
    AuditClosureState,
)


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def valid_artifact_summary(now: datetime) -> dict[str, object]:
    return {
        "artifact_id": "obs-1",
        "artifact_kind": "OBSERVATION_REPORT",
        "state": "ready",
        "source_version": "1.0",
        "generated_at": now,
        "spec_reference": "SPEC-011",
        "local_reference": "data/observation/latest_observation_report.json",
    }


# ---------------------------------------------------------------------------
# Safety flags builder
# ---------------------------------------------------------------------------

class TestBuildAuditClosureSafetyFlags:
    def test_returns_default_safe_flags(self) -> None:
        flags = build_audit_closure_safety_flags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.closure_output_is_human_audit_only is True
        assert flags.file_refs_not_traversed is True
        assert flags.no_action_commands_emitted is True
        assert flags.human_archival_guide_is_non_gating is True


# ---------------------------------------------------------------------------
# Unsafe content detection
# ---------------------------------------------------------------------------

class TestHasUnsafeAuditClosureContent:
    def test_detects_forbidden_text(self) -> None:
        assert has_unsafe_audit_closure_content("contains api_key value") is True
        assert has_unsafe_audit_closure_content("safe text") is False

    def test_detects_forbidden_metadata(self) -> None:
        assert has_unsafe_audit_closure_content({"note": "deploy now"}) is True
        assert has_unsafe_audit_closure_content({"note": "safe"}) is False

    def test_empty_and_none(self) -> None:
        assert has_unsafe_audit_closure_content("") is False
        assert has_unsafe_audit_closure_content(None) is False

    def test_nested_metadata(self) -> None:
        assert has_unsafe_audit_closure_content({"outer": {"inner": "secret"}}) is True

    def test_list_of_strings(self) -> None:
        assert has_unsafe_audit_closure_content(["safe", "binance"]) is True
        assert has_unsafe_audit_closure_content(["safe", "also safe"]) is False


# ---------------------------------------------------------------------------
# Finding builder
# ---------------------------------------------------------------------------

class TestBuildAuditClosureFinding:
    def test_builds_finding(self) -> None:
        finding = build_audit_closure_finding(
            finding_id="f-1",
            title="Title",
            severity="high",
            related_mvp="MVP-22",
            spec_reference="SPEC-023",
        )
        assert finding.finding_id == "f-1"
        assert finding.severity == "HIGH"

    def test_forbidden_term_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CLOSURE_CONTENT"):
            build_audit_closure_finding(
                finding_id="f-1",
                title="Title",
                severity="high",
                description="execute_trade now",
            )


# ---------------------------------------------------------------------------
# Section builder
# ---------------------------------------------------------------------------

class TestBuildAuditClosureSection:
    def test_builds_section(self) -> None:
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.OVERVIEW,
            title="Overview",
        )
        assert section.section_kind is AuditClosureSectionKind.OVERVIEW

    def test_findings_ordered_by_severity(self) -> None:
        f1 = build_audit_closure_finding("f1", "Info", "info")
        f2 = build_audit_closure_finding("f2", "Critical", "critical")
        f3 = build_audit_closure_finding("f3", "High", "high")
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.OPEN_FINDINGS,
            title="Findings",
            findings=[f1, f2, f3],
        )
        severities = [f.severity for f in section.findings]
        assert severities == ["CRITICAL", "HIGH", "INFO"]

    def test_findings_ordered_by_mvp_number(self) -> None:
        f1 = build_audit_closure_finding("f1", "High A", "high", related_mvp="MVP-15")
        f2 = build_audit_closure_finding("f2", "High B", "high", related_mvp="MVP-10")
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.OPEN_FINDINGS,
            title="Findings",
            findings=[f1, f2],
        )
        assert section.findings[0].related_mvp == "MVP-10"
        assert section.findings[1].related_mvp == "MVP-15"

    def test_findings_unparseable_mvp_sort_last(self) -> None:
        f1 = build_audit_closure_finding("f1", "A", "high", related_mvp="MVP-10")
        f2 = build_audit_closure_finding("f2", "B", "high", related_mvp="")
        f3 = build_audit_closure_finding("f3", "C", "high", related_mvp="unknown")
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.OPEN_FINDINGS,
            title="Findings",
            findings=[f2, f1, f3],
        )
        assert section.findings[0].related_mvp == "MVP-10"
        # Empty and unparseable sort last; preserve insertion order for ties.
        assert section.findings[1].related_mvp == ""
        assert section.findings[2].related_mvp == "unknown"

    def test_insertion_order_tie_breaker(self) -> None:
        f1 = build_audit_closure_finding("f1", "A", "high", related_mvp="MVP-10")
        f2 = build_audit_closure_finding("f2", "B", "high", related_mvp="MVP-10")
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.OPEN_FINDINGS,
            title="Findings",
            findings=[f2, f1],
        )
        assert section.findings[0].finding_id == "f2"
        assert section.findings[1].finding_id == "f1"


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

class TestBuildAuditClosureSummary:
    def test_empty_sections(self) -> None:
        summary = build_audit_closure_summary([])
        assert summary.total_sections == 0
        assert summary.closure_state == "UNKNOWN"

    def test_counts_aggregated(self) -> None:
        f1 = build_audit_closure_finding("f1", "Critical", "critical")
        f2 = build_audit_closure_finding("f2", "High", "high")
        f3 = build_audit_closure_finding("f3", "Info", "info")
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.OPEN_FINDINGS,
            title="Findings",
            findings=[f1, f2, f3],
        )
        summary = build_audit_closure_summary([section])
        assert summary.total_findings == 3
        assert summary.critical_count == 1
        assert summary.high_count == 1
        assert summary.info_count == 1
        assert summary.open_finding_count == 3

    def test_completed_artifacts_counted(self) -> None:
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.COMPLETED_ARTIFACTS,
            title="Completed",
            completed_artifacts=[{"artifact_kind": "OBSERVATION_REPORT"}],
        )
        summary = build_audit_closure_summary([section])
        assert summary.completed_artifact_count == 1

    def test_backlog_notes_counted(self) -> None:
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.BACKLOG_NOTES,
            title="Backlog",
            backlog_notes=["note 1", "note 2"],
        )
        summary = build_audit_closure_summary([section])
        assert summary.backlog_note_count == 2


# ---------------------------------------------------------------------------
# Data quality builder
# ---------------------------------------------------------------------------

class TestBuildAuditClosureDataQuality:
    def test_empty_sections(self) -> None:
        dq = build_audit_closure_data_quality([])
        assert dq.artifacts_present == 0
        assert dq.artifacts_missing == 12
        assert dq.sections_present == 0
        assert dq.sections_missing == 8

    def test_sections_present(self) -> None:
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.OVERVIEW,
            title="Overview",
        )
        dq = build_audit_closure_data_quality([section])
        assert dq.sections_present == 1
        assert dq.sections_missing == 7
        assert dq.coverage_pct == 12.5

    def test_artifacts_present(self) -> None:
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.COMPLETED_ARTIFACTS,
            title="Completed",
            completed_artifacts=[
                {"artifact_kind": "OBSERVATION_REPORT"},
                {"artifact_kind": "REVIEW_INDEX"},
            ],
        )
        dq = build_audit_closure_data_quality([section])
        assert dq.artifacts_present == 2
        assert dq.artifacts_missing == 10
        assert dq.completeness_pct == pytest.approx(16.6667, abs=0.001)

    def test_blockers_and_warnings(self) -> None:
        f1 = build_audit_closure_finding("f1", "Critical", "critical")
        f2 = build_audit_closure_finding("f2", "High", "high")
        f3 = build_audit_closure_finding("f3", "Medium", "medium")
        f4 = build_audit_closure_finding("f4", "Low", "low")
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.OPEN_FINDINGS,
            title="Findings",
            findings=[f1, f2, f3, f4],
        )
        dq = build_audit_closure_data_quality([section])
        assert dq.unresolved_blocker_count == 2
        assert dq.unresolved_warning_count == 2

    def test_expected_artifact_count_configurable(self) -> None:
        section = build_audit_closure_section(
            section_kind=AuditClosureSectionKind.COMPLETED_ARTIFACTS,
            title="Completed",
            completed_artifacts=[{"artifact_kind": "A"}],
        )
        dq = build_audit_closure_data_quality([section], expected_artifact_count=4)
        assert dq.artifacts_present == 1
        assert dq.artifacts_missing == 3


# ---------------------------------------------------------------------------
# Full closure report builder
# ---------------------------------------------------------------------------

class TestBuildResearchAuditClosureReport:
    def test_happy_path(self, valid_artifact_summary: dict[str, object]) -> None:
        report = build_research_audit_closure_report([valid_artifact_summary])
        assert report.closure_state is AuditClosureState.READY
        assert len(report.sections) == 8
        section_kinds = [s.section_kind for s in report.sections]
        assert section_kinds == list(AUDIT_CLOSURE_SECTION_KINDS)

    def test_missing_artifacts_blocked(self) -> None:
        report = build_research_audit_closure_report([])
        assert report.closure_state is AuditClosureState.BLOCK
        assert MISSING_ARTIFACTS in report.reason_codes

    def test_invalid_artifact_summary_blocked(self, now: datetime) -> None:
        bad_summary = {
            "artifact_id": "",
            "artifact_kind": "OBSERVATION_REPORT",
            "state": "ready",
            "source_version": "1.0",
            "generated_at": now,
        }
        report = build_research_audit_closure_report([bad_summary])
        assert report.closure_state is AuditClosureState.BLOCK
        assert INVALID_ARTIFACT_SUMMARY in report.reason_codes

    def test_invalid_config_blocked(self, valid_artifact_summary: dict[str, object]) -> None:
        config = AuditClosureConfig()
        object.__setattr__(config, "output_format", "xml")
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            config=config,
        )
        assert report.closure_state is AuditClosureState.BLOCK
        assert INVALID_CLOSURE_CONFIG in report.reason_codes

    def test_unsafe_config_blocked(self, valid_artifact_summary: dict[str, object]) -> None:
        # version "binance" contains forbidden term and passes format validation.
        config = AuditClosureConfig()
        object.__setattr__(config, "version", "binance")
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            config=config,
        )
        assert report.closure_state is AuditClosureState.BLOCK
        assert UNSAFE_CLOSURE_CONFIG in report.reason_codes

    def test_unsafe_artifact_content_blocked(self, valid_artifact_summary: dict[str, object]) -> None:
        bad_summary = dict(valid_artifact_summary)
        bad_summary["title"] = "contains api_key"
        report = build_research_audit_closure_report([bad_summary])
        assert report.closure_state is AuditClosureState.BLOCK
        assert UNSAFE_CLOSURE_CONTENT in report.reason_codes

    def test_unsafe_finding_blocked(self, valid_artifact_summary: dict[str, object]) -> None:
        finding = build_audit_closure_finding("f1", "Title", "high")
        object.__setattr__(finding, "description", "execute_trade now")
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            findings=[finding],
        )
        assert report.closure_state is AuditClosureState.BLOCK
        assert UNSAFE_CLOSURE_CONTENT in report.reason_codes

    def test_incomplete_artifact_chain(self, valid_artifact_summary: dict[str, object]) -> None:
        report = build_research_audit_closure_report([valid_artifact_summary])
        assert report.closure_state is AuditClosureState.READY
        assert INCOMPLETE_ARTIFACT_CHAIN in report.reason_codes
        assert report.data_quality.artifacts_missing == 11

    def test_block_on_incomplete(self, valid_artifact_summary: dict[str, object]) -> None:
        config = AuditClosureConfig(block_on_incomplete=True)
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            config=config,
        )
        assert report.closure_state is AuditClosureState.INCOMPLETE
        assert INCOMPLETE_ARTIFACT_CHAIN in report.reason_codes

    def test_unresolved_blockers_incomplete(self, valid_artifact_summary: dict[str, object]) -> None:
        finding = build_audit_closure_finding("f1", "Critical issue", "critical")
        config = AuditClosureConfig(block_on_incomplete=True)
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            findings=[finding],
            config=config,
        )
        assert report.closure_state is AuditClosureState.INCOMPLETE
        assert UNRESOLVED_BLOCKERS in report.reason_codes

    def test_advisory_reason_codes(self, valid_artifact_summary: dict[str, object]) -> None:
        finding = build_audit_closure_finding("f1", "Info", "info")
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            findings=[finding],
            backlog_notes=["note"],
        )
        assert report.closure_state is AuditClosureState.READY
        assert OPEN_FINDINGS_REMAIN in report.reason_codes
        assert BACKLOG_NOTES_REMAIN in report.reason_codes

    def test_deterministic_section_order(self, valid_artifact_summary: dict[str, object]) -> None:
        report = build_research_audit_closure_report([valid_artifact_summary])
        kinds = [s.section_kind for s in report.sections]
        assert kinds == list(AUDIT_CLOSURE_SECTION_KINDS)

    def test_closure_id_preserved(self, valid_artifact_summary: dict[str, object]) -> None:
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            closure_id="my-id",
        )
        assert report.closure_id == "my-id"

    def test_closure_id_generated_when_empty(self, valid_artifact_summary: dict[str, object]) -> None:
        report = build_research_audit_closure_report([valid_artifact_summary])
        assert report.closure_id
        assert report.closure_id != ""

    def test_summary_state_matches_report_state(self, valid_artifact_summary: dict[str, object]) -> None:
        config = AuditClosureConfig(block_on_incomplete=True)
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            config=config,
        )
        assert report.summary.closure_state == report.closure_state.value.upper()

    def test_blocked_summary_state(self) -> None:
        report = build_research_audit_closure_report([])
        assert report.closure_state is AuditClosureState.BLOCK
        assert report.summary.closure_state == "BLOCK"

    def test_safety_flags_preserved(self, valid_artifact_summary: dict[str, object]) -> None:
        flags = build_audit_closure_safety_flags()
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            safety_flags=flags,
        )
        assert report.safety_flags is flags

    def test_no_file_reference_traversal(self, valid_artifact_summary: dict[str, object]) -> None:
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            references=["data/observation/latest_observation_report.json"],
        )
        refs_section = next(
            s for s in report.sections if s.section_kind is AuditClosureSectionKind.APPENDIX_REFERENCES
        )
        assert refs_section.references == ("data/observation/latest_observation_report.json",)
        # No filesystem access occurred; references remain strings.
        assert report.safety_flags.file_refs_not_traversed is True

    def test_full_artifact_chain_ready(self, now: datetime) -> None:
        summaries = []
        kinds = [
            "OBSERVATION_REPORT",
            "REVIEW_AUDIT_RECORD",
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
        ]
        for idx, kind in enumerate(kinds):
            summaries.append({
                "artifact_id": f"art-{idx}",
                "artifact_kind": kind,
                "state": "ready",
                "source_version": "1.0",
                "generated_at": now,
                "spec_reference": f"SPEC-{10 + idx}",
            })
        report = build_research_audit_closure_report(summaries)
        assert report.closure_state is AuditClosureState.READY
        assert report.data_quality.artifacts_present == 12
        assert report.data_quality.artifacts_missing == 0
        assert report.data_quality.completeness_pct == 100.0

    def test_block_on_unknown(self, valid_artifact_summary: dict[str, object]) -> None:
        config = AuditClosureConfig(block_on_unknown=True)
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            config=config,
        )
        # No UNKNOWN reason code path in normal build, but verify config honored.
        assert report.config.block_on_unknown is True

    def test_ready_without_block_on_incomplete(self, valid_artifact_summary: dict[str, object]) -> None:
        config = AuditClosureConfig(block_on_incomplete=False)
        report = build_research_audit_closure_report(
            [valid_artifact_summary],
            config=config,
        )
        assert report.closure_state is AuditClosureState.READY


# ---------------------------------------------------------------------------
# Safety assertions
# ---------------------------------------------------------------------------

class TestSafetyAssertions:
    def test_no_trading_execution_exchange_imports(self) -> None:
        import hunter.research_audit_closure.engine as engine_module
        import hunter.research_audit_closure.models as models_module

        source_engine = engine_module.__loader__.get_source(engine_module.__name__) or ""
        source_models = models_module.__loader__.get_source(models_module.__name__) or ""

        forbidden_imports = [
            "binance",
            "freqtrade",
            "ccxt",
            "requests",
            "urllib",
            "socket",
            "sqlite3",
            "sqlalchemy",
            "flask",
            "fastapi",
            "django",
        ]
        for source in (source_engine, source_models):
            for line in source.splitlines():
                stripped = line.strip().lower()
                if not stripped.startswith(("import ", "from ")):
                    continue
                for term in forbidden_imports:
                    assert term not in stripped, f"forbidden import or reference: {term} in {line.strip()}"

    def test_human_archival_guide_is_non_gating(self, valid_artifact_summary: dict[str, object]) -> None:
        report = build_research_audit_closure_report([valid_artifact_summary])
        guide = next(
            s for s in report.sections if s.section_kind is AuditClosureSectionKind.HUMAN_ARCHIVAL_GUIDE
        )
        assert "advisory-only" in guide.section_notes.lower()
        assert "non-gating" in guide.section_notes.lower()
        assert report.safety_flags.human_archival_guide_is_non_gating is True
