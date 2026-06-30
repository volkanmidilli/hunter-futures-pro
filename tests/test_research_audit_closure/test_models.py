"""Tests for hunter.research_audit_closure.models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from hunter.research_audit_closure.models import (
    AUDIT_CLOSURE_BLOCKING_REASON_CODES,
    AUDIT_CLOSURE_INCOMPLETE_REASON_CODES,
    AUDIT_CLOSURE_NON_BLOCKING_REASON_CODES,
    AUDIT_CLOSURE_REASON_CODES,
    AUDIT_CLOSURE_SECTION_KINDS,
    BACKLOG_NOTES_REMAIN,
    CLOSURE_VERSION,
    DEFAULT_BLOCKED,
    EMPTY_COMPLETED_ARTIFACTS,
    FORBIDDEN_CLOSURE_TERMS,
    INCOMPLETE_ARTIFACT_CHAIN,
    INVALID_ARTIFACT_SUMMARY,
    INVALID_CLOSURE_CONFIG,
    MISSING_ARTIFACTS,
    MISSING_REQUIRED_SECTION,
    OPEN_FINDINGS_REMAIN,
    SECTION_BUILD_ERROR,
    SUMMARY_BUILD_ERROR,
    UNSAFE_CLOSURE_CONFIG,
    UNSAFE_CLOSURE_CONTENT,
    UNRESOLVED_BLOCKERS,
    UNKNOWN_CLOSURE_STATE,
    AuditClosureConfig,
    AuditClosureDataQuality,
    AuditClosureFinding,
    AuditClosureFindingSeverity,
    AuditClosureKind,
    AuditClosureSafetyFlags,
    AuditClosureSection,
    AuditClosureSectionKind,
    AuditClosureState,
    AuditClosureSummary,
    ResearchAuditClosureReport,
)


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestAuditClosureState:
    def test_enum_values(self) -> None:
        assert AuditClosureState.READY.value == "ready"
        assert AuditClosureState.INCOMPLETE.value == "incomplete"
        assert AuditClosureState.BLOCK.value == "block"
        assert AuditClosureState.UNKNOWN.value == "unknown"


class TestAuditClosureKind:
    def test_enum_values(self) -> None:
        assert AuditClosureKind.RESEARCH_AUDIT_CLOSURE.value == "research_audit_closure"


class TestAuditClosureSectionKind:
    def test_enum_values(self) -> None:
        assert AuditClosureSectionKind.OVERVIEW.value == "overview"
        assert AuditClosureSectionKind.CYCLE_SCOPE.value == "cycle_scope"
        assert AuditClosureSectionKind.COMPLETED_ARTIFACTS.value == "completed_artifacts"
        assert AuditClosureSectionKind.OPEN_FINDINGS.value == "open_findings"
        assert AuditClosureSectionKind.BACKLOG_NOTES.value == "backlog_notes"
        assert AuditClosureSectionKind.SAFETY_BOUNDARIES.value == "safety_boundaries"
        assert AuditClosureSectionKind.HUMAN_ARCHIVAL_GUIDE.value == "human_archival_guide"
        assert AuditClosureSectionKind.APPENDIX_REFERENCES.value == "appendix_references"

    def test_deterministic_order(self) -> None:
        values = [kind.value for kind in AUDIT_CLOSURE_SECTION_KINDS]
        assert values == [
            "overview",
            "cycle_scope",
            "completed_artifacts",
            "open_findings",
            "backlog_notes",
            "safety_boundaries",
            "human_archival_guide",
            "appendix_references",
        ]


class TestAuditClosureFindingSeverity:
    def test_enum_values(self) -> None:
        assert AuditClosureFindingSeverity.CRITICAL.value == "critical"
        assert AuditClosureFindingSeverity.HIGH.value == "high"
        assert AuditClosureFindingSeverity.MEDIUM.value == "medium"
        assert AuditClosureFindingSeverity.LOW.value == "low"
        assert AuditClosureFindingSeverity.INFO.value == "info"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

class TestAuditClosureReasonCodes:
    def test_reason_codes_complete(self) -> None:
        assert MISSING_ARTIFACTS in AUDIT_CLOSURE_REASON_CODES
        assert INVALID_ARTIFACT_SUMMARY in AUDIT_CLOSURE_REASON_CODES
        assert INVALID_CLOSURE_CONFIG in AUDIT_CLOSURE_REASON_CODES
        assert UNSAFE_CLOSURE_CONFIG in AUDIT_CLOSURE_REASON_CODES
        assert MISSING_REQUIRED_SECTION in AUDIT_CLOSURE_REASON_CODES
        assert EMPTY_COMPLETED_ARTIFACTS in AUDIT_CLOSURE_REASON_CODES
        assert UNRESOLVED_BLOCKERS in AUDIT_CLOSURE_REASON_CODES
        assert UNSAFE_CLOSURE_CONTENT in AUDIT_CLOSURE_REASON_CODES
        assert INCOMPLETE_ARTIFACT_CHAIN in AUDIT_CLOSURE_REASON_CODES
        assert OPEN_FINDINGS_REMAIN in AUDIT_CLOSURE_REASON_CODES
        assert BACKLOG_NOTES_REMAIN in AUDIT_CLOSURE_REASON_CODES
        assert SECTION_BUILD_ERROR in AUDIT_CLOSURE_REASON_CODES
        assert SUMMARY_BUILD_ERROR in AUDIT_CLOSURE_REASON_CODES
        assert UNKNOWN_CLOSURE_STATE in AUDIT_CLOSURE_REASON_CODES
        assert DEFAULT_BLOCKED in AUDIT_CLOSURE_REASON_CODES

    def test_blocking_set(self) -> None:
        for code in AUDIT_CLOSURE_BLOCKING_REASON_CODES:
            assert code in AUDIT_CLOSURE_REASON_CODES
        assert MISSING_ARTIFACTS in AUDIT_CLOSURE_BLOCKING_REASON_CODES
        assert UNSAFE_CLOSURE_CONTENT in AUDIT_CLOSURE_BLOCKING_REASON_CODES
        assert DEFAULT_BLOCKED in AUDIT_CLOSURE_BLOCKING_REASON_CODES

    def test_incomplete_set(self) -> None:
        for code in AUDIT_CLOSURE_INCOMPLETE_REASON_CODES:
            assert code in AUDIT_CLOSURE_REASON_CODES
        assert MISSING_REQUIRED_SECTION in AUDIT_CLOSURE_INCOMPLETE_REASON_CODES
        assert INCOMPLETE_ARTIFACT_CHAIN in AUDIT_CLOSURE_INCOMPLETE_REASON_CODES

    def test_non_blocking_set(self) -> None:
        for code in AUDIT_CLOSURE_NON_BLOCKING_REASON_CODES:
            assert code in AUDIT_CLOSURE_REASON_CODES
            assert code not in AUDIT_CLOSURE_BLOCKING_REASON_CODES
            assert code not in AUDIT_CLOSURE_INCOMPLETE_REASON_CODES
        assert OPEN_FINDINGS_REMAIN in AUDIT_CLOSURE_NON_BLOCKING_REASON_CODES
        assert BACKLOG_NOTES_REMAIN in AUDIT_CLOSURE_NON_BLOCKING_REASON_CODES


# ---------------------------------------------------------------------------
# AuditClosureConfig
# ---------------------------------------------------------------------------

class TestAuditClosureConfig:
    def test_default_config(self) -> None:
        config = AuditClosureConfig()
        assert config.version == CLOSURE_VERSION
        assert config.output_format == "both"
        assert config.dry_run is True
        assert config.live_trading_enabled is False
        assert config.block_on_unknown is True
        assert config.block_on_incomplete is False
        assert config.expected_artifact_count == 12
        assert len(config.required_sections) == 8

    def test_invalid_version(self) -> None:
        with pytest.raises(ValueError, match="version must be a non-empty string"):
            AuditClosureConfig(version="")

    def test_invalid_output_format(self) -> None:
        with pytest.raises(ValueError, match="output_format must be json, markdown, or both"):
            AuditClosureConfig(output_format="xml")

    def test_dry_run_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            AuditClosureConfig(dry_run=False)

    def test_unsafe_trading_flags_raise(self) -> None:
        with pytest.raises(ValueError, match="live trading flags must be False"):
            AuditClosureConfig(live_trading_enabled=True)
        with pytest.raises(ValueError, match="live trading flags must be False"):
            AuditClosureConfig(leverage_enabled=True)

    def test_invalid_expected_artifact_count(self) -> None:
        with pytest.raises(ValueError, match="expected_artifact_count must be a non-negative integer"):
            AuditClosureConfig(expected_artifact_count=-1)

    def test_invalid_required_sections(self) -> None:
        with pytest.raises(ValueError, match="required_sections must be AuditClosureSectionKind values"):
            AuditClosureConfig(required_sections=("overview",))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AuditClosureSafetyFlags
# ---------------------------------------------------------------------------

class TestAuditClosureSafetyFlags:
    def test_default_flags_are_safe(self) -> None:
        flags = AuditClosureSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.closure_output_is_human_audit_only is True
        assert flags.closure_output_not_trading_signal is True
        assert flags.closure_output_not_trade_approval is True
        assert flags.closure_output_not_release_approval is True
        assert flags.closure_output_not_deployment_approval is True
        assert flags.closure_output_not_execution_readiness is True
        assert flags.closure_output_not_strategy_readiness is True
        assert flags.closure_output_not_transaction_permission is True
        assert flags.closure_feedback_into_execution is False
        assert flags.cross_layer_feedback_into_execution is False
        assert flags.file_reference_traversal_enabled is False
        assert flags.database_persistence_enabled is False
        assert flags.web_ui_enabled is False
        assert flags.dashboard_enabled is False
        assert flags.runtime_registry_enabled is False
        assert flags.indexer_crawler_enabled is False
        assert flags.event_store_enabled is False
        assert flags.task_runner_enabled is False
        assert flags.file_refs_not_traversed is True
        assert flags.artifact_files_not_read is True
        assert flags.no_action_commands_emitted is True
        assert flags.human_archival_guide_is_non_gating is True

    def test_unsafe_flag_raises(self) -> None:
        with pytest.raises(ValueError, match="unsafe closure safety flags are enabled"):
            AuditClosureSafetyFlags(live_trading_enabled=True)
        with pytest.raises(ValueError, match="unsafe closure safety flags are enabled"):
            AuditClosureSafetyFlags(closure_feedback_into_execution=True)
        with pytest.raises(ValueError, match="unsafe closure safety flags are enabled"):
            AuditClosureSafetyFlags(file_reference_traversal_enabled=True)
        with pytest.raises(ValueError, match="unsafe closure safety flags are enabled"):
            AuditClosureSafetyFlags(runtime_registry_enabled=True)
        with pytest.raises(ValueError, match="unsafe closure safety flags are enabled"):
            AuditClosureSafetyFlags(event_store_enabled=True)
        with pytest.raises(ValueError, match="unsafe closure safety flags are enabled"):
            AuditClosureSafetyFlags(task_runner_enabled=True)

    def test_safe_flag_false_raises(self) -> None:
        with pytest.raises(ValueError, match="safe closure output flags must be True"):
            AuditClosureSafetyFlags(closure_output_is_human_audit_only=False)
        with pytest.raises(ValueError, match="safe closure output flags must be True"):
            AuditClosureSafetyFlags(closure_output_not_release_approval=False)
        with pytest.raises(ValueError, match="safe closure output flags must be True"):
            AuditClosureSafetyFlags(file_refs_not_traversed=False)
        with pytest.raises(ValueError, match="safe closure output flags must be True"):
            AuditClosureSafetyFlags(human_archival_guide_is_non_gating=False)


# ---------------------------------------------------------------------------
# AuditClosureFinding
# ---------------------------------------------------------------------------

class TestAuditClosureFinding:
    def test_valid_finding(self) -> None:
        finding = AuditClosureFinding(
            finding_id="f-1",
            title="Title",
            severity="high",
            related_mvp="MVP-22",
            spec_reference="SPEC-023",
        )
        assert finding.finding_id == "f-1"
        assert finding.title == "Title"
        assert finding.severity == "HIGH"
        assert finding.related_mvp == "MVP-22"

    def test_empty_finding_id_raises(self) -> None:
        with pytest.raises(ValueError, match="finding_id must be a non-empty string"):
            AuditClosureFinding(finding_id="", title="Title")

    def test_empty_title_raises(self) -> None:
        with pytest.raises(ValueError, match="title must be a non-empty string"):
            AuditClosureFinding(finding_id="f-1", title="")

    def test_invalid_severity_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported severity"):
            AuditClosureFinding(finding_id="f-1", title="Title", severity="urgent")

    def test_forbidden_term_in_title_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CLOSURE_CONTENT"):
            AuditClosureFinding(finding_id="f-1", title="Contains api_key here")

    def test_forbidden_term_in_description_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CLOSURE_CONTENT"):
            AuditClosureFinding(
                finding_id="f-1",
                title="Title",
                description="We should deploy now",
            )

    def test_forbidden_term_in_metadata_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CLOSURE_CONTENT"):
            AuditClosureFinding(
                finding_id="f-1",
                title="Title",
                metadata={"note": "execute_trade immediately"},
            )

    def test_metadata_is_frozen(self) -> None:
        finding = AuditClosureFinding(finding_id="f-1", title="Title")
        assert isinstance(finding.metadata, MappingProxyType)

    def test_finding_is_frozen(self) -> None:
        finding = AuditClosureFinding(finding_id="f-1", title="Title")
        with pytest.raises(FrozenInstanceError):
            finding.title = "New"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AuditClosureSection
# ---------------------------------------------------------------------------

class TestAuditClosureSection:
    def test_valid_section(self) -> None:
        section = AuditClosureSection(
            section_kind=AuditClosureSectionKind.OVERVIEW,
            title="Overview",
        )
        assert section.section_kind is AuditClosureSectionKind.OVERVIEW
        assert section.title == "Overview"

    def test_empty_title_raises(self) -> None:
        with pytest.raises(ValueError, match="title must be a non-empty string"):
            AuditClosureSection(
                section_kind=AuditClosureSectionKind.OVERVIEW,
                title="",
            )

    def test_invalid_section_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="section_kind must be AuditClosureSectionKind"):
            AuditClosureSection(section_kind="overview", title="Overview")  # type: ignore[arg-type]

    def test_findings_ordered(self) -> None:
        f1 = AuditClosureFinding(finding_id="f1", title="Low", severity="low")
        f2 = AuditClosureFinding(finding_id="f2", title="Critical", severity="critical")
        section = AuditClosureSection(
            section_kind=AuditClosureSectionKind.OPEN_FINDINGS,
            title="Findings",
            findings=(f1, f2),
        )
        assert section.findings[0].severity == "CRITICAL"
        assert section.findings[1].severity == "LOW"

    def test_forbidden_term_in_notes_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CLOSURE_CONTENT"):
            AuditClosureSection(
                section_kind=AuditClosureSectionKind.OVERVIEW,
                title="Overview",
                section_notes="release_approved",
            )

    def test_invalid_backlog_note_raises(self) -> None:
        with pytest.raises(ValueError, match="backlog_notes must contain non-empty strings"):
            AuditClosureSection(
                section_kind=AuditClosureSectionKind.BACKLOG_NOTES,
                title="Backlog",
                backlog_notes=[""],
            )

    def test_invalid_reference_raises(self) -> None:
        with pytest.raises(ValueError, match="references must contain non-empty strings"):
            AuditClosureSection(
                section_kind=AuditClosureSectionKind.APPENDIX_REFERENCES,
                title="Refs",
                references=[""],
            )


# ---------------------------------------------------------------------------
# AuditClosureSummary
# ---------------------------------------------------------------------------

class TestAuditClosureSummary:
    def test_default_summary(self) -> None:
        summary = AuditClosureSummary()
        assert summary.total_sections == 0
        assert summary.closure_state == "UNKNOWN"
        assert summary.total_findings == 0

    def test_severity_counts_must_sum(self) -> None:
        with pytest.raises(ValueError, match="severity counts must sum to total_findings"):
            AuditClosureSummary(
                total_findings=1,
                critical_count=0,
                high_count=0,
            )

    def test_invalid_closure_state(self) -> None:
        with pytest.raises(ValueError, match="closure_state must be READY, INCOMPLETE, BLOCK, or UNKNOWN"):
            AuditClosureSummary(closure_state="ready")  # lowercase invalid

    def test_forbidden_term_in_narrative(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CLOSURE_CONTENT"):
            AuditClosureSummary(closure_narrative="deploy now")


# ---------------------------------------------------------------------------
# AuditClosureDataQuality
# ---------------------------------------------------------------------------

class TestAuditClosureDataQuality:
    def test_default_values_are_fail_closed(self) -> None:
        dq = AuditClosureDataQuality()
        assert dq.total_artifacts_expected == 12
        assert dq.artifacts_present == 0
        assert dq.artifacts_missing == 12
        assert dq.sections_present == 0
        assert dq.sections_missing == 8
        assert dq.completeness_pct == 0.0
        assert dq.coverage_pct == 0.0

    def test_invariant_artifacts(self) -> None:
        with pytest.raises(ValueError, match=r"artifacts_present \+ artifacts_missing must equal total_artifacts_expected"):
            AuditClosureDataQuality(
                total_artifacts_expected=12,
                artifacts_present=1,
                artifacts_missing=1,
            )

    def test_invariant_sections(self) -> None:
        with pytest.raises(ValueError, match=r"sections_present \+ sections_missing must equal total section count"):
            AuditClosureDataQuality(
                sections_present=1,
                sections_missing=1,
            )

    def test_pct_bounds(self) -> None:
        with pytest.raises(ValueError, match="completeness_pct must be between 0.0 and 100.0"):
            AuditClosureDataQuality(completeness_pct=101.0)
        with pytest.raises(ValueError, match="coverage_pct must be between 0.0 and 100.0"):
            AuditClosureDataQuality(coverage_pct=-1.0)


# ---------------------------------------------------------------------------
# ResearchAuditClosureReport
# ---------------------------------------------------------------------------

class TestResearchAuditClosureReport:
    def test_default_construction_valid(self, now: datetime) -> None:
        report = ResearchAuditClosureReport(closure_id="r-1", generated_at=now)
        assert report.closure_id == "r-1"
        assert report.closure_state is AuditClosureState.UNKNOWN
        assert report.reason_codes == (UNKNOWN_CLOSURE_STATE,)
        assert report.sections == ()

    def test_empty_closure_id_raises(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="closure_id must be a non-empty string"):
            ResearchAuditClosureReport(closure_id="", generated_at=now)

    def test_naive_datetime_raises(self, now: datetime) -> None:
        naive = now.replace(tzinfo=None)
        with pytest.raises(ValueError, match="generated_at must be timezone-aware"):
            ResearchAuditClosureReport(closure_id="r-1", generated_at=naive)

    def test_block_requires_reason_codes(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="reason_codes must be non-empty when closure_state is BLOCK or UNKNOWN"):
            ResearchAuditClosureReport(
                closure_id="r-1",
                generated_at=now,
                closure_state=AuditClosureState.BLOCK,
                reason_codes=(),
            )

    def test_unknown_requires_reason_codes(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="reason_codes must be non-empty when closure_state is BLOCK or UNKNOWN"):
            ResearchAuditClosureReport(
                closure_id="r-1",
                generated_at=now,
                closure_state=AuditClosureState.UNKNOWN,
                reason_codes=(),
            )

    def test_unsupported_reason_code_raises(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            ResearchAuditClosureReport(
                closure_id="r-1",
                generated_at=now,
                reason_codes=("BOGUS",),
            )

    def test_blocked_factory(self, now: datetime) -> None:
        report = ResearchAuditClosureReport.blocked(
            closure_id="r-blocked",
            generated_at=now,
            reason_code=MISSING_ARTIFACTS,
        )
        assert report.closure_state is AuditClosureState.BLOCK
        assert report.reason_codes == (MISSING_ARTIFACTS,)
        assert report.sections == ()
        assert report.summary.closure_state == "BLOCK"
        assert report.data_quality.artifacts_missing == 12
        assert report.data_quality.sections_missing == 8

    def test_blocked_factory_default_reason(self, now: datetime) -> None:
        report = ResearchAuditClosureReport.blocked(generated_at=now)
        assert report.closure_state is AuditClosureState.BLOCK
        assert report.reason_codes == (DEFAULT_BLOCKED,)

    def test_blocked_factory_invalid_reason(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            ResearchAuditClosureReport.blocked(generated_at=now, reason_code="BOGUS")

    def test_ready_state_no_reason_codes(self, now: datetime) -> None:
        report = ResearchAuditClosureReport(
            closure_id="r-1",
            generated_at=now,
            closure_state=AuditClosureState.READY,
            reason_codes=(),
        )
        assert report.closure_state is AuditClosureState.READY

    def test_forbidden_term_in_narrative(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CLOSURE_CONTENT"):
            ResearchAuditClosureReport(
                closure_id="r-1",
                generated_at=now,
                closure_narrative="execute now",
            )

    def test_frozen(self, now: datetime) -> None:
        report = ResearchAuditClosureReport(closure_id="r-1", generated_at=now)
        with pytest.raises(FrozenInstanceError):
            report.closure_id = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Forbidden terms
# ---------------------------------------------------------------------------

class TestForbiddenClosureTerms:
    def test_forbidden_terms_present(self) -> None:
        assert "api_key" in FORBIDDEN_CLOSURE_TERMS
        assert "binance" in FORBIDDEN_CLOSURE_TERMS
        assert "leverage" in FORBIDDEN_CLOSURE_TERMS
        assert "shorting" in FORBIDDEN_CLOSURE_TERMS
        assert "deploy_now" in FORBIDDEN_CLOSURE_TERMS
        assert "release_approved" in FORBIDDEN_CLOSURE_TERMS
        assert "execute_trade" in FORBIDDEN_CLOSURE_TERMS

    def test_no_release_deployment_approval_terms(self) -> None:
        assert "release approval" not in FORBIDDEN_CLOSURE_TERMS
        # The spec intent is captured by compound terms like release_approved.
