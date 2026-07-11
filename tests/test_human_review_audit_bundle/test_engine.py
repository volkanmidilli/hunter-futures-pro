"""Unit tests for hunter.human_review_audit_bundle engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.human_review_audit_bundle.engine import build_human_review_audit_bundle
from hunter.human_review_audit_bundle.models import (
    HumanReviewAuditBundleConfig,
    HumanReviewAuditBundleInput,
    HumanReviewAuditBundleReasonCode,
    HumanReviewAuditBundleReport,
    HumanReviewAuditBundleState,
)
from hunter.human_review_decision_log.models import (
    HumanReviewDecisionIssue,
    HumanReviewDecisionLogDataQuality,
    HumanReviewDecisionLogReport,
    HumanReviewDecisionLogState,
    HumanReviewDecisionReasonCode,
)
from hunter.human_review_decision_log_consistency.models import (
    HumanReviewDecisionLogConsistencyDataQuality,
    HumanReviewDecisionLogConsistencyIssue,
    HumanReviewDecisionLogConsistencyReport,
    HumanReviewDecisionLogConsistencyState,
)
from hunter.human_review_queue.models import (
    HumanReviewQueueDataQuality,
    HumanReviewQueueIssue,
    HumanReviewQueueReasonCode,
    HumanReviewQueueReport,
    HumanReviewQueueState,
)


NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)


def _queue_report_ok() -> HumanReviewQueueReport:
    return HumanReviewQueueReport(
        report_id="queue-ok-1",
        state=HumanReviewQueueState.OK,
        generated_at=NOW,
        data_quality=HumanReviewQueueDataQuality(
            total_source_records=1,
            total_queue_entries=1,
            total_issues=0,
            sections_present=1,
        ),
    )


def _decision_log_report_ok() -> HumanReviewDecisionLogReport:
    return HumanReviewDecisionLogReport(
        report_id="decision-log-ok-1",
        state=HumanReviewDecisionLogState.OK,
        generated_at=NOW,
        data_quality=HumanReviewDecisionLogDataQuality(
            total_queue_entry_refs=1,
            total_decision_records=1,
            total_decision_results=1,
            total_issues=0,
        ),
    )


def _consistency_report_ok() -> HumanReviewDecisionLogConsistencyReport:
    return HumanReviewDecisionLogConsistencyReport(
        report_id="consistency-ok-1",
        state=HumanReviewDecisionLogConsistencyState.OK,
        generated_at=NOW,
        data_quality=HumanReviewDecisionLogConsistencyDataQuality(
            total_queue_entries=1,
            total_decision_log_refs=1,
            matched_refs=1,
        ),
    )


def _bundle_report_ok() -> HumanReviewAuditBundleReport:
    return build_human_review_audit_bundle(
        HumanReviewAuditBundleInput(
            queue_report=_queue_report_ok(),
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            generated_at=NOW,
        )
    )


class TestEmptyInputs:
    def test_all_empty_inputs_returns_not_applicable(self) -> None:
        input_ = HumanReviewAuditBundleInput(generated_at=NOW)
        report = build_human_review_audit_bundle(input_)
        assert report.state == HumanReviewAuditBundleState.NOT_APPLICABLE
        assert report.sections == ()
        assert report.issues == ()
        assert HumanReviewAuditBundleReasonCode.NOT_APPLICABLE in report.reason_codes
        assert HumanReviewAuditBundleReasonCode.EMPTY_INPUT_NOT_APPLICABLE in report.reason_codes
        assert report.data_quality.section_count == 0

    def test_all_empty_inputs_with_disabled_empty_flag_returns_not_applicable(self) -> None:
        input_ = HumanReviewAuditBundleInput(
            config=HumanReviewAuditBundleConfig(empty_input_is_not_applicable=False),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        # With empty inputs, all upstream states are NOT_APPLICABLE, so the
        # aggregate state is NOT_APPLICABLE regardless of the early-exit flag.
        # The flag only disables the early-exit path; state precedence still
        # governs.
        assert report.state == HumanReviewAuditBundleState.NOT_APPLICABLE
        assert HumanReviewAuditBundleReasonCode.NOT_APPLICABLE in report.reason_codes
        assert HumanReviewAuditBundleReasonCode.EMPTY_INPUT_NOT_APPLICABLE in report.reason_codes


class TestOkPath:
    def test_ok_bundle_state(self) -> None:
        report = _bundle_report_ok()
        assert report.state == HumanReviewAuditBundleState.OK
        assert HumanReviewAuditBundleReasonCode.OK in report.reason_codes

    def test_ok_bundle_sections(self) -> None:
        report = _bundle_report_ok()
        assert len(report.sections) == 3
        kinds = [s.section_kind for s in report.sections]
        assert kinds == ["consistency", "decision_log", "queue"]
        for section in report.sections:
            assert section.upstream_state == "ok"
            assert section.upstream_report_id

    def test_ok_bundle_safety_flags(self) -> None:
        report = _bundle_report_ok()
        assert report.safety_flags.is_safe is True
        assert report.safety_flags.audit_only is True
        assert report.safety_flags.no_executable_actions is True
        assert report.safety_flags.references_opaque is True

    def test_ok_bundle_data_quality(self) -> None:
        report = _bundle_report_ok()
        assert report.data_quality.section_count == 3
        assert report.data_quality.queue_entry_count == 1
        assert report.data_quality.decision_result_count == 1
        assert report.data_quality.consistency_cross_reference_count == 1
        assert report.data_quality.blocking_issues == 0
        assert report.data_quality.advisory_issues == 0


class TestDegradedUpstreamCarryForward:
    def test_degraded_queue_state_degraded_bundle(self) -> None:
        queue = _queue_report_ok()
        queue = HumanReviewQueueReport(
            report_id="queue-degraded-1",
            state=HumanReviewQueueState.DEGRADED,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
            reason_codes=(HumanReviewQueueReasonCode.CONSISTENCY_DEGRADED,),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=queue,
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert report.state == HumanReviewAuditBundleState.DEGRADED
        assert HumanReviewAuditBundleReasonCode.UPSTREAM_DEGRADED in report.reason_codes
        assert HumanReviewAuditBundleReasonCode.BUNDLE_DEGRADED in report.reason_codes
        assert report.data_quality.advisory_issues >= 1

    def test_degraded_consistency_state_degraded_bundle(self) -> None:
        consistency = HumanReviewDecisionLogConsistencyReport(
            report_id="consistency-degraded-1",
            state=HumanReviewDecisionLogConsistencyState.DEGRADED,
            generated_at=NOW,
            data_quality=HumanReviewDecisionLogConsistencyDataQuality(
                total_queue_entries=1,
                orphan_queue_entries=1,
            ),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=_queue_report_ok(),
            decision_log_report=_decision_log_report_ok(),
            consistency_report=consistency,
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert report.state == HumanReviewAuditBundleState.DEGRADED


class TestBlockedUpstreamCarryForward:
    def test_blocked_decision_log_state_blocked_bundle(self) -> None:
        decision_log = HumanReviewDecisionLogReport(
            report_id="decision-log-blocked-1",
            state=HumanReviewDecisionLogState.BLOCKED,
            generated_at=NOW,
            data_quality=HumanReviewDecisionLogDataQuality(
                unsafe_content_count=1,
                total_decision_records=1,
            ),
            reason_codes=(HumanReviewDecisionReasonCode.UNSAFE_CONTENT,),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=_queue_report_ok(),
            decision_log_report=decision_log,
            consistency_report=_consistency_report_ok(),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert report.state == HumanReviewAuditBundleState.BLOCKED
        assert HumanReviewAuditBundleReasonCode.UPSTREAM_BLOCKED in report.reason_codes
        assert report.data_quality.unsafe_content_count == 1
        assert report.safety_flags.is_safe is False

    def test_blocked_consistency_state_blocked_bundle(self) -> None:
        consistency = HumanReviewDecisionLogConsistencyReport(
            report_id="consistency-blocked-1",
            state=HumanReviewDecisionLogConsistencyState.BLOCKED,
            generated_at=NOW,
            data_quality=HumanReviewDecisionLogConsistencyDataQuality(
                forbidden_term_count=1,
                total_queue_entries=1,
            ),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=_queue_report_ok(),
            decision_log_report=_decision_log_report_ok(),
            consistency_report=consistency,
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert report.state == HumanReviewAuditBundleState.BLOCKED
        assert HumanReviewAuditBundleReasonCode.FORBIDDEN_TERM_PRESENT in report.reason_codes


class TestStrictMode:
    def test_strict_promotes_degraded_to_blocked(self) -> None:
        queue = HumanReviewQueueReport(
            report_id="queue-degraded-2",
            state=HumanReviewQueueState.DEGRADED,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=queue,
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            config=HumanReviewAuditBundleConfig(strict=True),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert report.state == HumanReviewAuditBundleState.BLOCKED

    def test_strict_promotes_not_applicable_to_blocked(self) -> None:
        # One empty NA input plus one OK input with strict mode.
        input_ = HumanReviewAuditBundleInput(
            queue_report=_queue_report_ok(),
            decision_log_report=HumanReviewDecisionLogReport(
                report_id="decision-log-na", state=HumanReviewDecisionLogState.NOT_APPLICABLE, generated_at=NOW
            ),
            consistency_report=_consistency_report_ok(),
            config=HumanReviewAuditBundleConfig(
                empty_input_is_not_applicable=False, strict=True
            ),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert report.state == HumanReviewAuditBundleState.BLOCKED

    def test_non_strict_degraded_remains_degraded(self) -> None:
        queue = HumanReviewQueueReport(
            report_id="queue-degraded-3",
            state=HumanReviewQueueState.DEGRADED,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=queue,
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            config=HumanReviewAuditBundleConfig(strict=False),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert report.state == HumanReviewAuditBundleState.DEGRADED


class TestDeterminism:
    def test_bundle_id_is_deterministic(self) -> None:
        report1 = _bundle_report_ok()
        report2 = _bundle_report_ok()
        assert report1.bundle_id == report2.bundle_id
        assert report1.report_id == report2.report_id

    def test_sections_order_is_deterministic(self) -> None:
        report1 = _bundle_report_ok()
        report2 = _bundle_report_ok()
        assert [s.section_id for s in report1.sections] == [s.section_id for s in report2.sections]
        assert [s.section_kind for s in report1.sections] == [s.section_kind for s in report2.sections]

    def test_different_inputs_produce_different_ids(self) -> None:
        report1 = _bundle_report_ok()
        queue2 = HumanReviewQueueReport(
            report_id="queue-ok-2",
            state=HumanReviewQueueState.OK,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
        )
        input2 = HumanReviewAuditBundleInput(
            queue_report=queue2,
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            generated_at=NOW,
        )
        report2 = build_human_review_audit_bundle(input2)
        assert report1.bundle_id != report2.bundle_id


class TestUpstreamIssueAggregation:
    def test_upstream_issues_carried_forward(self) -> None:
        queue = HumanReviewQueueReport(
            report_id="queue-issues-1",
            state=HumanReviewQueueState.OK,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
            issues=(
                HumanReviewQueueIssue(
                    issue_id="q-iss-1",
                    issue_type="duplicate_source_id",
                    severity="advisory",
                    title="dup",
                    description="d",
                    generated_at=NOW,
                ),
            ),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=queue,
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert len(report.issues) == 1
        issue = report.issues[0]
        assert issue.source_section_kind == "queue"
        assert issue.source_id == "q-iss-1"
        assert issue.severity == "advisory"
        assert report.data_quality.advisory_issues == 1
        assert report.data_quality.upstream_issue_count == 1

    def test_upstream_blocking_issue_promotes_state(self) -> None:
        queue = HumanReviewQueueReport(
            report_id="queue-issues-2",
            state=HumanReviewQueueState.OK,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
            issues=(
                HumanReviewQueueIssue(
                    issue_id="q-iss-2",
                    issue_type="unsafe_content",
                    severity="blocking",
                    title="unsafe",
                    description="d",
                    generated_at=NOW,
                ),
            ),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=queue,
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert report.state == HumanReviewAuditBundleState.BLOCKED
        assert report.data_quality.blocking_issues == 1

    def test_disable_upstream_issues_excludes_them(self) -> None:
        queue = HumanReviewQueueReport(
            report_id="queue-issues-3",
            state=HumanReviewQueueState.OK,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
            issues=(
                HumanReviewQueueIssue(
                    issue_id="q-iss-3",
                    issue_type="advisory",
                    severity="advisory",
                    title="a",
                    description="d",
                    generated_at=NOW,
                ),
            ),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=queue,
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            config=HumanReviewAuditBundleConfig(include_upstream_issues=False),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert report.issues == ()
        assert report.state == HumanReviewAuditBundleState.OK


class TestOpaqueRefBoundary:
    def test_refs_preserved_as_strings_and_not_opened(self, monkeypatch: Any) -> None:
        path_ref = "/data/queue-2026-01-01.json"

        def _fake_open(*args: Any, **kwargs: Any) -> Any:
            pytest.fail("bundle engine opened a reference: open called")

        monkeypatch.setattr("builtins.open", _fake_open)
        queue = HumanReviewQueueReport(
            report_id=path_ref,
            state=HumanReviewQueueState.OK,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=queue,
            decision_log_report=HumanReviewDecisionLogReport(
                report_id="decision-log-with-path",
                state=HumanReviewDecisionLogState.OK,
                generated_at=NOW,
                data_quality=HumanReviewDecisionLogDataQuality(total_decision_records=1),
            ),
            consistency_report=HumanReviewDecisionLogConsistencyReport(
                report_id="consistency-with-path",
                state=HumanReviewDecisionLogConsistencyState.OK,
                generated_at=NOW,
                data_quality=HumanReviewDecisionLogConsistencyDataQuality(
                    total_queue_entries=1,
                    matched_refs=1,
                ),
            ),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert report.bundle_id.startswith("bundle-")
        # Sections are ordered deterministically by section_kind: consistency,
        # decision_log, queue.
        assert report.sections[0].upstream_report_id == "consistency-with-path"
        assert report.sections[1].upstream_report_id == "decision-log-with-path"
        assert report.sections[2].upstream_report_id == path_ref

    def test_bundle_id_does_not_contain_path_ref_content(self) -> None:
        # The ID must be a hash, not a raw report path.
        queue = HumanReviewQueueReport(
            report_id="/path/to/queue.json",
            state=HumanReviewQueueState.OK,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=queue,
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert "/path/to/queue.json" not in report.bundle_id
        assert report.bundle_id.startswith("bundle-")


class TestNoFilesystemOrNetwork:
    def test_no_runtime_filesystem_access(self, monkeypatch: Any, tmp_path: Any) -> None:
        def _fake_open(*args: Any, **kwargs: Any) -> Any:
            pytest.fail("open called unexpectedly")

        monkeypatch.setattr("builtins.open", _fake_open)
        report = _bundle_report_ok()
        assert report.state == HumanReviewAuditBundleState.OK


class TestBundleReasonCodes:
    def test_ok_reason_codes_include_safety_set(self) -> None:
        report = _bundle_report_ok()
        code_values = {rc.value for rc in report.reason_codes}
        assert "ok" in code_values
        assert "research_only" in code_values
        assert "human_audit_only" in code_values
        assert "no_executable_actions" in code_values
        assert "no_trading_instructions" in code_values
        assert "no_approval_claims" in code_values
        assert "references_opaque" in code_values
        assert "no_network" in code_values
        assert "no_server" in code_values
        assert "no_database" in code_values


class TestBundleNotes:
    def test_ok_notes(self) -> None:
        report = _bundle_report_ok()
        assert "OK" in report.notes

    def test_degraded_notes(self) -> None:
        queue = HumanReviewQueueReport(
            report_id="queue-degraded-notes",
            state=HumanReviewQueueState.DEGRADED,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
        )
        input_ = HumanReviewAuditBundleInput(
            queue_report=queue,
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            generated_at=NOW,
        )
        report = build_human_review_audit_bundle(input_)
        assert "degraded" in report.notes.lower()


class TestInvalidInput:
    def test_bundle_input_validates_upstream_types(self) -> None:
        with pytest.raises(TypeError, match="queue_report"):
            HumanReviewAuditBundleInput(queue_report="not-a-report")  # type: ignore[arg-type]

    def test_bundle_input_validates_decision_log_type(self) -> None:
        with pytest.raises(TypeError, match="decision_log_report"):
            HumanReviewAuditBundleInput(decision_log_report="not-a-report")  # type: ignore[arg-type]

    def test_bundle_input_validates_consistency_type(self) -> None:
        with pytest.raises(TypeError, match="consistency_report"):
            HumanReviewAuditBundleInput(consistency_report="not-a-report")  # type: ignore[arg-type]
