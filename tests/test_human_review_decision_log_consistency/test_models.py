"""Tests for hunter.human_review_decision_log_consistency models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.human_review_decision_log_consistency.models import (
    FORBIDDEN_HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_TERMS,
    HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_VERSION,
    HumanReviewDecisionLogConsistencyConfig,
    HumanReviewDecisionLogConsistencyCrossReference,
    HumanReviewDecisionLogConsistencyDataQuality,
    HumanReviewDecisionLogConsistencyIssue,
    HumanReviewDecisionLogConsistencyLink,
    HumanReviewDecisionLogConsistencyReasonCode,
    HumanReviewDecisionLogConsistencyReport,
    HumanReviewDecisionLogConsistencySafetyFlags,
    HumanReviewDecisionLogConsistencySeverity,
    HumanReviewDecisionLogConsistencyState,
    has_unsafe_human_review_decision_log_consistency_content,
)


class TestConfig:
    def test_default_config(self) -> None:
        config = HumanReviewDecisionLogConsistencyConfig()
        assert config.require_decision_for_all_queue_entries is False
        assert config.queue_entry_states_that_expect_decision == ("open", "pending_review", "blocked")
        assert config.strict is False
        assert config.empty_input_is_not_applicable is True
        assert config.staleness_threshold_seconds == 7 * 24 * 60 * 60
        assert config.metadata == {}

    def test_expects_decision(self) -> None:
        config = HumanReviewDecisionLogConsistencyConfig()
        assert config.expects_decision("open") is True
        assert config.expects_decision("pending_review") is True
        assert config.expects_decision("blocked") is True
        assert config.expects_decision("closed") is False
        assert config.expects_decision("not_applicable") is False
        assert config.expects_decision("suppressed") is False

    def test_config_normalizes_states(self) -> None:
        config = HumanReviewDecisionLogConsistencyConfig()
        assert config.expects_decision("  OPEN  ") is True
        assert config.expects_decision("Pending_Review") is True

    def test_custom_states(self) -> None:
        config = HumanReviewDecisionLogConsistencyConfig(
            queue_entry_states_that_expect_decision=("review_needed",),
        )
        assert config.expects_decision("review_needed") is True
        assert config.expects_decision("open") is False

    def test_strict_config(self) -> None:
        config = HumanReviewDecisionLogConsistencyConfig(strict=True)
        assert config.strict is True

    def test_config_validates_metadata_keys(self) -> None:
        with pytest.raises(ValueError, match="metadata keys must be strings"):
            HumanReviewDecisionLogConsistencyConfig(metadata={1: "value"})

    def test_config_rejects_negative_staleness(self) -> None:
        with pytest.raises(ValueError, match="staleness_threshold_seconds"):
            HumanReviewDecisionLogConsistencyConfig(staleness_threshold_seconds=-1)


class TestSafetyFlags:
    def test_default_flags_are_safe(self) -> None:
        flags = HumanReviewDecisionLogConsistencySafetyFlags()
        assert flags.is_safe is True
        assert flags.audit_only is True
        assert flags.no_executable_actions is True
        assert flags.no_trading_instructions is True
        assert flags.no_approval_claims is True
        assert flags.references_opaque is True
        assert flags.has_unsafe_content is False
        assert flags.has_forbidden_terms is False

    def test_baseline_invariants_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="baseline safety invariants"):
            HumanReviewDecisionLogConsistencySafetyFlags(audit_only=False)

    def test_is_safe_when_unsafe(self) -> None:
        flags = HumanReviewDecisionLogConsistencySafetyFlags(
            is_safe=False, has_unsafe_content=True
        )
        assert flags.is_safe is False


class TestCrossReference:
    def test_default_cross_reference(self) -> None:
        cr = HumanReviewDecisionLogConsistencyCrossReference()
        assert cr.match_status == "matched"
        assert cr.severity == "info"
        assert cr.reason_codes == ()

    def test_cross_reference_normalizes_strings(self) -> None:
        cr = HumanReviewDecisionLogConsistencyCrossReference(
            queue_entry_id=None,
            decision_log_queue_entry_id=None,
            match_status=None,
        )
        assert cr.queue_entry_id == ""
        assert cr.decision_log_queue_entry_id == ""
        assert cr.match_status == ""

    def test_cross_reference_validates_reason_codes(self) -> None:
        cr = HumanReviewDecisionLogConsistencyCrossReference(reason_codes=[1, 2, 3])
        assert cr.reason_codes == ("1", "2", "3")


class TestIssue:
    def test_default_issue(self) -> None:
        issue = HumanReviewDecisionLogConsistencyIssue()
        assert issue.severity == "info"
        assert issue.issue_id == ""


class TestDataQuality:
    def test_default_counts_are_zero(self) -> None:
        dq = HumanReviewDecisionLogConsistencyDataQuality()
        assert dq.total_queue_entries == 0
        assert dq.total_decision_log_refs == 0
        assert dq.matched_refs == 0
        assert dq.orphan_queue_entries == 0
        assert dq.orphan_decision_log_refs == 0
        assert dq.mismatched_refs == 0

    def test_rejects_negative_counts(self) -> None:
        with pytest.raises(ValueError, match="total_queue_entries"):
            HumanReviewDecisionLogConsistencyDataQuality(total_queue_entries=-1)


class TestLink:
    def test_default_link(self) -> None:
        link = HumanReviewDecisionLogConsistencyLink()
        assert link.link_type == "unknown"

    def test_link_requires_aware_datetime(self) -> None:
        with pytest.raises(ValueError, match="generated_at"):
            HumanReviewDecisionLogConsistencyLink(
                generated_at=datetime(2024, 1, 1),
            )

    def test_link_accepts_aware_datetime(self) -> None:
        link = HumanReviewDecisionLogConsistencyLink(
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        assert link.generated_at is not None


class TestReport:
    def test_default_report(self) -> None:
        report = HumanReviewDecisionLogConsistencyReport()
        assert report.state == HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE
        assert report.cross_references == ()
        assert report.issues == ()
        assert report.queue_entry_to_decision_log_refs == ()
        assert report.orphan_queue_entries == ()
        assert report.orphan_decision_log_refs == ()
        assert report.mismatched_refs == ()

    def test_report_state_validation(self) -> None:
        with pytest.raises(ValueError, match="state must be"):
            HumanReviewDecisionLogConsistencyReport(state="ok")

    def test_report_derived_views(self) -> None:
        cr_matched = HumanReviewDecisionLogConsistencyCrossReference(match_status="matched")
        cr_orphan_queue = HumanReviewDecisionLogConsistencyCrossReference(match_status="orphan_queue")
        cr_orphan_dlog = HumanReviewDecisionLogConsistencyCrossReference(match_status="orphan_decision_log")
        cr_mismatched = HumanReviewDecisionLogConsistencyCrossReference(match_status="mismatched")
        report = HumanReviewDecisionLogConsistencyReport(
            cross_references=(cr_matched, cr_orphan_queue, cr_orphan_dlog, cr_mismatched),
        )
        assert len(report.queue_entry_to_decision_log_refs) == 1
        assert len(report.orphan_queue_entries) == 1
        assert len(report.orphan_decision_log_refs) == 1
        assert len(report.mismatched_refs) == 1


class TestVersionAndSafetyConstants:
    def test_version(self) -> None:
        assert HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_VERSION == "0.42.0-dev"

    def test_forbidden_terms_are_multi_word(self) -> None:
        for term in FORBIDDEN_HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_TERMS:
            assert " " in term, f"Forbidden term must be multi-word: {term!r}"

    def test_has_unsafe_content_detects_unsafe_types(self) -> None:
        assert has_unsafe_human_review_decision_log_consistency_content(123) is True
        assert has_unsafe_human_review_decision_log_consistency_content(b"bytes") is True
        assert has_unsafe_human_review_decision_log_consistency_content("safe") is False
        assert has_unsafe_human_review_decision_log_consistency_content(None) is False

    def test_reason_code_enum_values(self) -> None:
        assert HumanReviewDecisionLogConsistencyReasonCode.OK.value == "ok"
        assert HumanReviewDecisionLogConsistencyReasonCode.MISSING_DECISION_LOG_REF.value == "missing_decision_log_ref"
        assert HumanReviewDecisionLogConsistencySeverity.BLOCKING.value == "blocking"
