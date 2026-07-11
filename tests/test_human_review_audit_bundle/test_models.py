"""Unit tests for hunter.human_review_audit_bundle models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.human_review_audit_bundle.models import (
    HUMAN_REVIEW_AUDIT_BUNDLE_VERSION,
    SAFETY_NOTICE,
    HumanReviewAuditBundleConfig,
    HumanReviewAuditBundleDataQuality,
    HumanReviewAuditBundleInput,
    HumanReviewAuditBundleIssue,
    HumanReviewAuditBundleReasonCode,
    HumanReviewAuditBundleReport,
    HumanReviewAuditBundleSafetyFlags,
    HumanReviewAuditBundleSection,
    HumanReviewAuditBundleSeverity,
    HumanReviewAuditBundleState,
)
from hunter.human_review_decision_log.models import HumanReviewDecisionLogReport
from hunter.human_review_decision_log_consistency.models import (
    HumanReviewDecisionLogConsistencyReport,
)
from hunter.human_review_queue.models import HumanReviewQueueReport


NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)


class TestConfig:
    def test_defaults(self) -> None:
        cfg = HumanReviewAuditBundleConfig()
        assert cfg.carry_forward_upstream_state is True
        assert cfg.empty_input_is_not_applicable is True
        assert cfg.strict is False
        assert cfg.include_upstream_issues is True
        assert cfg.include_derived_summary is True


class TestBundleStateAndSeverity:
    def test_state_enum_values(self) -> None:
        assert HumanReviewAuditBundleState.OK.value == "ok"
        assert HumanReviewAuditBundleState.DEGRADED.value == "degraded"
        assert HumanReviewAuditBundleState.BLOCKED.value == "blocked"
        assert HumanReviewAuditBundleState.NOT_APPLICABLE.value == "not_applicable"

    def test_severity_enum_values(self) -> None:
        assert HumanReviewAuditBundleSeverity.BLOCKING.value == "blocking"
        assert HumanReviewAuditBundleSeverity.ADVISORY.value == "advisory"
        assert HumanReviewAuditBundleSeverity.INFO.value == "info"

    def test_reason_codes(self) -> None:
        assert HumanReviewAuditBundleReasonCode.OK.value == "ok"
        assert HumanReviewAuditBundleReasonCode.NOT_APPLICABLE.value == "not_applicable"
        assert HumanReviewAuditBundleReasonCode.UPSTREAM_BLOCKED.value == "upstream_blocked"
        assert HumanReviewAuditBundleReasonCode.REFERENCES_OPAQUE.value == "references_opaque"


class TestBundleReport:
    def test_default_values(self) -> None:
        report = HumanReviewAuditBundleReport()
        assert report.bundle_id == ""
        assert report.report_id == ""
        assert report.state == HumanReviewAuditBundleState.NOT_APPLICABLE
        assert report.project_version == HUMAN_REVIEW_AUDIT_BUNDLE_VERSION
        assert report.sections == ()
        assert report.issues == ()
        assert report.reason_codes == ()
        assert report.safety_notice == SAFETY_NOTICE
        assert report.metadata == {}
        assert report.notes == ""

    def test_report_is_frozen(self) -> None:
        report = HumanReviewAuditBundleReport(bundle_id="b1")
        with pytest.raises(AttributeError):
            report.bundle_id = "b2"  # type: ignore[misc]


class TestBundleSection:
    def test_creation(self) -> None:
        section = HumanReviewAuditBundleSection(
            section_id="s1",
            section_kind="queue",
            upstream_report_id="queue-123",
            upstream_state="ok",
            upstream_reason_codes=("ok",),
            generated_at=NOW,
            summary={"total_queue_entries": 1},
            metadata={"k": "v"},
            notes="n",
        )
        assert section.section_id == "s1"
        assert section.section_kind == "queue"
        assert section.upstream_report_id == "queue-123"
        assert section.upstream_state == "ok"
        assert section.upstream_reason_codes == ("ok",)

    def test_section_is_frozen(self) -> None:
        section = HumanReviewAuditBundleSection(
            section_id="s1",
            section_kind="queue",
            upstream_report_id="q",
            upstream_state="ok",
            upstream_reason_codes=(),
            generated_at=NOW,
            summary={},
            metadata={},
            notes="",
        )
        with pytest.raises(AttributeError):
            section.section_id = "s2"  # type: ignore[misc]


class TestBundleIssue:
    def test_creation(self) -> None:
        issue = HumanReviewAuditBundleIssue(
            issue_id="i1",
            issue_type="upstream_blocked",
            severity="blocking",
            reason_codes=("upstream_blocked",),
            source_section_kind="queue",
            source_id="queue-123",
            title="blocked",
            description="d",
            generated_at=NOW,
        )
        assert issue.issue_id == "i1"
        assert issue.severity == "blocking"
        assert issue.source_section_kind == "queue"


class TestBundleInput:
    def test_default_inputs_are_empty_upstream_reports(self) -> None:
        input_ = HumanReviewAuditBundleInput()
        assert isinstance(input_.queue_report, HumanReviewQueueReport)
        assert isinstance(input_.decision_log_report, HumanReviewDecisionLogReport)
        assert isinstance(input_.consistency_report, HumanReviewDecisionLogConsistencyReport)
        assert input_.project_version == HUMAN_REVIEW_AUDIT_BUNDLE_VERSION
        assert input_.generated_at is None

    def test_input_is_frozen(self) -> None:
        input_ = HumanReviewAuditBundleInput()
        with pytest.raises(AttributeError):
            input_.project_version = "x"  # type: ignore[misc]

    def test_metadata_coerced_to_mapping(self) -> None:
        input_ = HumanReviewAuditBundleInput(metadata={"k": "v"})
        assert dict(input_.metadata) == {"k": "v"}

    def test_generated_at_must_be_timezone_aware(self) -> None:
        naive = datetime(2026, 1, 1)
        with pytest.raises(ValueError, match="must be timezone-aware"):
            HumanReviewAuditBundleInput(generated_at=naive)


class TestBundleDataQuality:
    def test_defaults(self) -> None:
        dq = HumanReviewAuditBundleDataQuality()
        assert dq.section_count == 0
        assert dq.upstream_issue_count == 0
        assert dq.blocking_issues == 0
        assert dq.advisory_issues == 0
        assert dq.info_findings == 0
        assert dq.queue_entry_count == 0
        assert dq.decision_result_count == 0
        assert dq.consistency_cross_reference_count == 0
        assert dq.unsafe_content_count == 0
        assert dq.forbidden_term_count == 0

    def test_non_negative_int_validation(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            HumanReviewAuditBundleDataQuality(section_count=-1)
        with pytest.raises(TypeError, match="int"):
            HumanReviewAuditBundleDataQuality(section_count="1")  # type: ignore[arg-type]


class TestBundleSafetyFlags:
    def test_defaults(self) -> None:
        flags = HumanReviewAuditBundleSafetyFlags()
        assert flags.is_safe is True
        assert flags.audit_only is True
        assert flags.no_executable_actions is True
        assert flags.no_trading_instructions is True
        assert flags.no_approval_claims is True
        assert flags.references_opaque is True
        assert flags.no_network is True
        assert flags.no_server is True


class TestReasonCodes:
    def test_safety_reason_codes_present(self) -> None:
        codes = {
            HumanReviewAuditBundleReasonCode.RESEARCH_ONLY,
            HumanReviewAuditBundleReasonCode.HUMAN_AUDIT_ONLY,
            HumanReviewAuditBundleReasonCode.NO_EXECUTABLE_ACTIONS,
            HumanReviewAuditBundleReasonCode.NO_TRADING_INSTRUCTIONS,
            HumanReviewAuditBundleReasonCode.NO_APPROVAL_CLAIMS,
            HumanReviewAuditBundleReasonCode.REFERENCES_OPAQUE,
            HumanReviewAuditBundleReasonCode.NO_NETWORK,
            HumanReviewAuditBundleReasonCode.NO_SERVER,
            HumanReviewAuditBundleReasonCode.NO_DATABASE,
        }
        assert all(code.value for code in codes)
