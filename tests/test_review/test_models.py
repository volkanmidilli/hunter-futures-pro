"""Unit tests for hunter.review models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.review import (
    DEFAULT_BLOCKED,
    DRY_RUN_DISABLED,
    FORBIDDEN_REVIEW_TERMS,
    INVALID_REPORT,
    INVALID_REVIEW_STATUS,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    MISSING_REPORT,
    MISSING_REVIEWER,
    REAL_ORDERS_ENABLED,
    REASON_CODES,
    REVIEW_ERROR,
    ReviewAuditRecord,
    ReviewAuditSummary,
    ReviewConfig,
    ReviewDataQuality,
    ReviewOutputFormat,
    ReviewRecord,
    ReviewSafetyFlags,
    ReviewState,
    ReviewStatus,
    SHORTING_ENABLED,
    UNSAFE_REPORT_STATE,
    UNSAFE_REVIEW_CONTENT,
    UNSUPPORTED_REPORT_VERSION,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestReviewStatus:
    def test_all_values_present(self):
        assert ReviewStatus.NOT_REVIEWED == "NOT_REVIEWED"
        assert ReviewStatus.REVIEWED == "REVIEWED"
        assert ReviewStatus.ACCEPTED == "ACCEPTED"
        assert ReviewStatus.REJECTED == "REJECTED"
        assert ReviewStatus.NEEDS_INVESTIGATION == "NEEDS_INVESTIGATION"

    def test_membership(self):
        assert "NOT_REVIEWED" in [s.value for s in ReviewStatus]
        assert "ACCEPTED" in [s.value for s in ReviewStatus]


class TestReviewState:
    def test_all_values_present(self):
        assert ReviewState.DISABLED == "DISABLED"
        assert ReviewState.READY == "READY"
        assert ReviewState.BLOCKED == "BLOCKED"
        assert ReviewState.UNKNOWN == "UNKNOWN"


class TestReviewOutputFormat:
    def test_all_values_present(self):
        assert ReviewOutputFormat.JSON == "JSON"
        assert ReviewOutputFormat.MARKDOWN == "MARKDOWN"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

class TestReasonCodes:
    def test_all_present(self):
        assert MISSING_REPORT in REASON_CODES
        assert INVALID_REPORT in REASON_CODES
        assert UNSUPPORTED_REPORT_VERSION in REASON_CODES
        assert UNSAFE_REPORT_STATE in REASON_CODES
        assert DRY_RUN_DISABLED in REASON_CODES
        assert LIVE_TRADING_ENABLED in REASON_CODES
        assert REAL_ORDERS_ENABLED in REASON_CODES
        assert LEVERAGE_ENABLED in REASON_CODES
        assert SHORTING_ENABLED in REASON_CODES
        assert MISSING_REVIEWER in REASON_CODES
        assert INVALID_REVIEW_STATUS in REASON_CODES
        assert UNSAFE_REVIEW_CONTENT in REASON_CODES
        assert REVIEW_ERROR in REASON_CODES
        assert DEFAULT_BLOCKED in REASON_CODES

    def test_tuple_type(self):
        assert isinstance(REASON_CODES, tuple)
        assert len(REASON_CODES) == 14


# ---------------------------------------------------------------------------
# Forbidden terms
# ---------------------------------------------------------------------------

class TestForbiddenTerms:
    def test_all_present(self):
        assert "api_key" in FORBIDDEN_REVIEW_TERMS
        assert "secret" in FORBIDDEN_REVIEW_TERMS
        assert "exchange_credentials" in FORBIDDEN_REVIEW_TERMS
        assert "executable_instructions" in FORBIDDEN_REVIEW_TERMS
        assert "enter_long" in FORBIDDEN_REVIEW_TERMS
        assert "enter_short" in FORBIDDEN_REVIEW_TERMS
        assert "exit_long" in FORBIDDEN_REVIEW_TERMS
        assert "exit_short" in FORBIDDEN_REVIEW_TERMS
        assert "order" in FORBIDDEN_REVIEW_TERMS
        assert "leverage" in FORBIDDEN_REVIEW_TERMS
        assert "shorting" in FORBIDDEN_REVIEW_TERMS
        assert "binance" in FORBIDDEN_REVIEW_TERMS
        assert "exchange" in FORBIDDEN_REVIEW_TERMS


# ---------------------------------------------------------------------------
# ReviewConfig tests
# ---------------------------------------------------------------------------

class TestReviewConfigDefaults:
    def test_safe_defaults(self):
        config = ReviewConfig()
        assert config.input_version == "1.0"
        assert config.max_report_age_seconds == 3600
        assert config.enable_json_output is True
        assert config.enable_markdown_output is True
        assert config.dry_run is True
        assert config.live_trading_enabled is False
        assert config.real_orders_enabled is False
        assert config.leverage_enabled is False
        assert config.shorting_enabled is False
        assert config.allow_report_feedback_into_execution is False
        assert config.allow_operator_feedback_into_execution is False


class TestReviewConfigValidation:
    def test_empty_input_version(self):
        with pytest.raises(ValueError, match="input_version"):
            ReviewConfig(input_version="")

    def test_zero_max_age(self):
        with pytest.raises(ValueError, match="max_report_age_seconds"):
            ReviewConfig(max_report_age_seconds=0)

    def test_negative_max_age(self):
        with pytest.raises(ValueError, match="max_report_age_seconds"):
            ReviewConfig(max_report_age_seconds=-1)

    def test_no_output_enabled(self):
        with pytest.raises(ValueError, match="at least one output"):
            ReviewConfig(enable_json_output=False, enable_markdown_output=False)

    def test_dry_run_false(self):
        with pytest.raises(ValueError, match="dry_run"):
            ReviewConfig(dry_run=False)

    def test_live_trading_true(self):
        with pytest.raises(ValueError, match="live_trading_enabled"):
            ReviewConfig(live_trading_enabled=True)

    def test_real_orders_true(self):
        with pytest.raises(ValueError, match="real_orders_enabled"):
            ReviewConfig(real_orders_enabled=True)

    def test_leverage_true(self):
        with pytest.raises(ValueError, match="leverage_enabled"):
            ReviewConfig(leverage_enabled=True)

    def test_shorting_true(self):
        with pytest.raises(ValueError, match="shorting_enabled"):
            ReviewConfig(shorting_enabled=True)

    def test_report_feedback_true(self):
        with pytest.raises(ValueError, match="allow_report_feedback_into_execution"):
            ReviewConfig(allow_report_feedback_into_execution=True)

    def test_operator_feedback_true(self):
        with pytest.raises(ValueError, match="allow_operator_feedback_into_execution"):
            ReviewConfig(allow_operator_feedback_into_execution=True)


# ---------------------------------------------------------------------------
# ReviewSafetyFlags tests
# ---------------------------------------------------------------------------

class TestReviewSafetyFlagsDefaults:
    def test_safe_defaults(self):
        flags = ReviewSafetyFlags(
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            report_feedback_into_execution=False,
            operator_feedback_into_execution=False,
        )
        assert flags.dry_run is True
        assert flags.network_calls_enabled is False
        assert flags.database_persistence_enabled is False


class TestReviewSafetyFlagsValidation:
    def test_dry_run_false(self):
        with pytest.raises(ValueError, match="dry_run"):
            ReviewSafetyFlags(
                dry_run=False,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
            )

    def test_live_trading_true(self):
        with pytest.raises(ValueError, match="live_trading_enabled"):
            ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=True,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
            )

    def test_real_orders_true(self):
        with pytest.raises(ValueError, match="real_orders_enabled"):
            ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=True,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
            )

    def test_leverage_true(self):
        with pytest.raises(ValueError, match="leverage_enabled"):
            ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=True,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
            )

    def test_shorting_true(self):
        with pytest.raises(ValueError, match="shorting_enabled"):
            ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=True,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
            )

    def test_report_feedback_true(self):
        with pytest.raises(ValueError, match="report_feedback_into_execution"):
            ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=True,
                operator_feedback_into_execution=False,
            )

    def test_operator_feedback_true(self):
        with pytest.raises(ValueError, match="operator_feedback_into_execution"):
            ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=True,
            )

    def test_network_calls_true(self):
        with pytest.raises(ValueError, match="network_calls_enabled"):
            ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
                network_calls_enabled=True,
            )

    def test_database_persistence_true(self):
        with pytest.raises(ValueError, match="database_persistence_enabled"):
            ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
                database_persistence_enabled=True,
            )


# ---------------------------------------------------------------------------
# ReviewRecord tests
# ---------------------------------------------------------------------------

NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)
SAFE_FLAGS = ReviewSafetyFlags(
    dry_run=True,
    live_trading_enabled=False,
    real_orders_enabled=False,
    leverage_enabled=False,
    shorting_enabled=False,
    report_feedback_into_execution=False,
    operator_feedback_into_execution=False,
)


class TestReviewRecordValid:
    def test_accepted(self):
        record = ReviewRecord(
            review_id="r1",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            notes="looks good",
            tags=("routine",),
            reason_codes=("ACCEPTED",),
            reviewed_at=NOW,
            safety_flags=SAFE_FLAGS,
            metadata={},
        )
        assert record.review_id == "r1"
        assert record.review_status is ReviewStatus.ACCEPTED
        assert record.reviewer == "op1"

    def test_rejected(self):
        record = ReviewRecord(
            review_id="r2",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.REJECTED,
            reviewer="op1",
            notes="suspicious",
            tags=("suspicious",),
            reason_codes=("REJECTED",),
            reviewed_at=NOW,
            safety_flags=SAFE_FLAGS,
            metadata={},
        )
        assert record.review_status is ReviewStatus.REJECTED

    def test_needs_investigation(self):
        record = ReviewRecord(
            review_id="r3",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.NEEDS_INVESTIGATION,
            reviewer="op1",
            notes="needs check",
            tags=("check",),
            reason_codes=("NEEDS_INVESTIGATION",),
            reviewed_at=NOW,
            safety_flags=SAFE_FLAGS,
            metadata={},
        )
        assert record.review_status is ReviewStatus.NEEDS_INVESTIGATION

    def test_not_reviewed(self):
        record = ReviewRecord(
            review_id="r4",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            reason_codes=(),
            reviewed_at=NOW,
            safety_flags=SAFE_FLAGS,
            metadata={},
        )
        assert record.review_status is ReviewStatus.NOT_REVIEWED
        assert record.reviewer == ""

    def test_not_reviewed_with_reviewer(self):
        record = ReviewRecord(
            review_id="r4",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="op1",
            notes="",
            tags=(),
            reason_codes=(),
            reviewed_at=NOW,
            safety_flags=SAFE_FLAGS,
            metadata={},
        )
        assert record.reviewer == "op1"


class TestReviewRecordBlocked:
    def test_blocked_factory(self):
        record = ReviewRecord.blocked(
            reason_codes=(MISSING_REPORT,),
            now=NOW,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.review_status is ReviewStatus.NOT_REVIEWED
        assert record.reviewer == "SYSTEM"
        assert record.reason_codes == (MISSING_REPORT,)
        assert record.notes == "Fail-closed review record due to safety violation"

    def test_blocked_with_custom(self):
        record = ReviewRecord.blocked(
            reason_codes=(DRY_RUN_DISABLED,),
            review_id="custom-id",
            source_report_id="src1",
            reviewer="SYSTEM",
            notes="custom note",
            now=NOW,
        )
        assert record.review_id == "custom-id"
        assert record.source_report_id == "src1"
        assert record.notes == "custom note"


class TestReviewRecordValidation:
    def test_empty_review_id(self):
        with pytest.raises(ValueError, match="review_id"):
            ReviewRecord(
                review_id="",
                source_report_id="rep1",
                source_report_version="1.0",
                review_state=ReviewState.READY,
                review_status=ReviewStatus.ACCEPTED,
                reviewer="op1",
                notes="",
                tags=(),
                reason_codes=("ACCEPTED",),
                reviewed_at=NOW,
                safety_flags=SAFE_FLAGS,
                metadata={},
            )

    def test_empty_source_report_id(self):
        with pytest.raises(ValueError, match="source_report_id"):
            ReviewRecord(
                review_id="r1",
                source_report_id="",
                source_report_version="1.0",
                review_state=ReviewState.READY,
                review_status=ReviewStatus.ACCEPTED,
                reviewer="op1",
                notes="",
                tags=(),
                reason_codes=("ACCEPTED",),
                reviewed_at=NOW,
                safety_flags=SAFE_FLAGS,
                metadata={},
            )

    def test_empty_source_version(self):
        with pytest.raises(ValueError, match="source_report_version"):
            ReviewRecord(
                review_id="r1",
                source_report_id="rep1",
                source_report_version="",
                review_state=ReviewState.READY,
                review_status=ReviewStatus.ACCEPTED,
                reviewer="op1",
                notes="",
                tags=(),
                reason_codes=("ACCEPTED",),
                reviewed_at=NOW,
                safety_flags=SAFE_FLAGS,
                metadata={},
            )

    def test_naive_datetime(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            ReviewRecord(
                review_id="r1",
                source_report_id="rep1",
                source_report_version="1.0",
                review_state=ReviewState.READY,
                review_status=ReviewStatus.ACCEPTED,
                reviewer="op1",
                notes="",
                tags=(),
                reason_codes=("ACCEPTED",),
                reviewed_at=datetime(2026, 6, 27, 12, 0, 0),
                safety_flags=SAFE_FLAGS,
                metadata={},
            )

    def test_missing_reviewer_for_accepted(self):
        with pytest.raises(ValueError, match="reviewer"):
            ReviewRecord(
                review_id="r1",
                source_report_id="rep1",
                source_report_version="1.0",
                review_state=ReviewState.READY,
                review_status=ReviewStatus.ACCEPTED,
                reviewer="",
                notes="",
                tags=(),
                reason_codes=("ACCEPTED",),
                reviewed_at=NOW,
                safety_flags=SAFE_FLAGS,
                metadata={},
            )

    def test_invalid_state_status_combination(self):
        with pytest.raises(ValueError, match="NOT_REVIEWED or NEEDS_INVESTIGATION"):
            ReviewRecord(
                review_id="r1",
                source_report_id="rep1",
                source_report_version="1.0",
                review_state=ReviewState.BLOCKED,
                review_status=ReviewStatus.ACCEPTED,
                reviewer="op1",
                notes="",
                tags=(),
                reason_codes=("ACCEPTED",),
                reviewed_at=NOW,
                safety_flags=SAFE_FLAGS,
                metadata={},
            )

    def test_blocked_with_not_reviewed_ok(self):
        record = ReviewRecord(
            review_id="r1",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.BLOCKED,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="SYSTEM",
            notes="",
            tags=(),
            reason_codes=(MISSING_REPORT,),
            reviewed_at=NOW,
            safety_flags=SAFE_FLAGS,
            metadata={},
        )
        assert record.review_state is ReviewState.BLOCKED

    def test_empty_reason_codes_for_reviewed(self):
        with pytest.raises(ValueError, match="reason_codes"):
            ReviewRecord(
                review_id="r1",
                source_report_id="rep1",
                source_report_version="1.0",
                review_state=ReviewState.READY,
                review_status=ReviewStatus.ACCEPTED,
                reviewer="op1",
                notes="",
                tags=(),
                reason_codes=(),
                reviewed_at=NOW,
                safety_flags=SAFE_FLAGS,
                metadata={},
            )

    def test_not_reviewed_empty_reason_ok(self):
        record = ReviewRecord(
            review_id="r1",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="op1",
            notes="",
            tags=(),
            reason_codes=(),
            reviewed_at=NOW,
            safety_flags=SAFE_FLAGS,
            metadata={},
        )
        assert record.reason_codes == ()


class TestReviewRecordForbiddenContent:
    def test_forbidden_notes(self):
        with pytest.raises(ValueError, match="forbidden"):
            ReviewRecord(
                review_id="r1",
                source_report_id="rep1",
                source_report_version="1.0",
                review_state=ReviewState.READY,
                review_status=ReviewStatus.ACCEPTED,
                reviewer="op1",
                notes="contains api_key here",
                tags=(),
                reason_codes=("ACCEPTED",),
                reviewed_at=NOW,
                safety_flags=SAFE_FLAGS,
                metadata={},
            )

    def test_forbidden_tags(self):
        with pytest.raises(ValueError, match="forbidden"):
            ReviewRecord(
                review_id="r1",
                source_report_id="rep1",
                source_report_version="1.0",
                review_state=ReviewState.READY,
                review_status=ReviewStatus.ACCEPTED,
                reviewer="op1",
                notes="ok",
                tags=("has_enter_long",),
                reason_codes=("ACCEPTED",),
                reviewed_at=NOW,
                safety_flags=SAFE_FLAGS,
                metadata={},
            )

    def test_forbidden_metadata_key(self):
        with pytest.raises(ValueError, match="forbidden"):
            ReviewRecord(
                review_id="r1",
                source_report_id="rep1",
                source_report_version="1.0",
                review_state=ReviewState.READY,
                review_status=ReviewStatus.ACCEPTED,
                reviewer="op1",
                notes="ok",
                tags=(),
                reason_codes=("ACCEPTED",),
                reviewed_at=NOW,
                safety_flags=SAFE_FLAGS,
                metadata={"binance": "value"},
            )

    def test_safe_content(self):
        record = ReviewRecord(
            review_id="r1",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            notes="routine observation check",
            tags=("routine", "daily"),
            reason_codes=("ACCEPTED",),
            reviewed_at=NOW,
            safety_flags=SAFE_FLAGS,
            metadata={"source": "MVP-10"},
        )
        assert record.notes == "routine observation check"


class TestReviewRecordImmutability:
    def test_frozen(self):
        record = ReviewRecord.blocked(reason_codes=(MISSING_REPORT,), now=NOW)
        with pytest.raises(FrozenInstanceError):
            record.review_id = "new-id"


# ---------------------------------------------------------------------------
# ReviewAuditSummary tests
# ---------------------------------------------------------------------------

class TestReviewAuditSummary:
    def test_valid(self):
        summary = ReviewAuditSummary(
            total_reviews=3,
            accepted_count=1,
            rejected_count=1,
            needs_investigation_count=0,
            not_reviewed_count=1,
            blocked_count=0,
            unknown_count=0,
            reason_counts={"ACCEPTED": 1, "REJECTED": 1},
        )
        assert summary.total_reviews == 3

    def test_negative_total(self):
        with pytest.raises(ValueError, match="total_reviews"):
            ReviewAuditSummary(
                total_reviews=-1,
                accepted_count=0,
                rejected_count=0,
                needs_investigation_count=0,
                not_reviewed_count=0,
                blocked_count=0,
                unknown_count=0,
                reason_counts={},
            )

    def test_counts_exceed_total(self):
        with pytest.raises(ValueError, match="sum to total_reviews"):
            ReviewAuditSummary(
                total_reviews=1,
                accepted_count=1,
                rejected_count=1,
                needs_investigation_count=0,
                not_reviewed_count=0,
                blocked_count=0,
                unknown_count=0,
                reason_counts={},
            )

    def test_negative_reason_count(self):
        with pytest.raises(ValueError, match="reason_counts"):
            ReviewAuditSummary(
                total_reviews=1,
                accepted_count=1,
                rejected_count=0,
                needs_investigation_count=0,
                not_reviewed_count=0,
                blocked_count=0,
                unknown_count=0,
                reason_counts={"ACCEPTED": -1},
            )


# ---------------------------------------------------------------------------
# ReviewDataQuality tests
# ---------------------------------------------------------------------------

class TestReviewDataQuality:
    def test_valid(self):
        dq = ReviewDataQuality(
            total_reports=5,
            valid_reports=3,
            blocked_reports=1,
            unknown_reports=1,
            unsafe_reports=0,
            missing_reports=0,
            invalid_reports=0,
        )
        assert dq.total_reports == 5

    def test_negative_total(self):
        with pytest.raises(ValueError, match="total_reports"):
            ReviewDataQuality(
                total_reports=-1,
                valid_reports=0,
                blocked_reports=0,
                unknown_reports=0,
                unsafe_reports=0,
                missing_reports=0,
                invalid_reports=0,
            )

    def test_counts_exceed_total(self):
        with pytest.raises(ValueError, match="sum to total_reports"):
            ReviewDataQuality(
                total_reports=1,
                valid_reports=1,
                blocked_reports=1,
                unknown_reports=0,
                unsafe_reports=0,
                missing_reports=0,
                invalid_reports=0,
            )


# ---------------------------------------------------------------------------
# ReviewAuditRecord tests
# ---------------------------------------------------------------------------

class TestReviewAuditRecord:
    def test_valid(self):
        record = ReviewRecord.blocked(reason_codes=(MISSING_REPORT,), now=NOW)
        summary = ReviewAuditSummary(
            total_reviews=1,
            accepted_count=0,
            rejected_count=0,
            needs_investigation_count=0,
            not_reviewed_count=1,
            blocked_count=1,
            unknown_count=0,
            reason_counts={MISSING_REPORT: 1},
        )
        dq = ReviewDataQuality(
            total_reports=1,
            valid_reports=0,
            blocked_reports=1,
            unknown_reports=0,
            unsafe_reports=0,
            missing_reports=0,
            invalid_reports=0,
        )
        audit = ReviewAuditRecord(
            audit_id="a1",
            generated_at=NOW,
            audit_state=ReviewState.BLOCKED,
            records=(record,),
            summary=summary,
            data_quality=dq,
            reason_codes=(DEFAULT_BLOCKED,),
            safety_flags=SAFE_FLAGS,
        )
        assert audit.audit_id == "a1"
        assert audit.audit_state is ReviewState.BLOCKED

    def test_empty_audit_id(self):
        with pytest.raises(ValueError, match="audit_id"):
            ReviewAuditRecord(
                audit_id="",
                generated_at=NOW,
                audit_state=ReviewState.READY,
                records=(),
                summary=ReviewAuditSummary(
                    total_reviews=0,
                    accepted_count=0,
                    rejected_count=0,
                    needs_investigation_count=0,
                    not_reviewed_count=0,
                    blocked_count=0,
                    unknown_count=0,
                    reason_counts={},
                ),
                data_quality=ReviewDataQuality(
                    total_reports=0,
                    valid_reports=0,
                    blocked_reports=0,
                    unknown_reports=0,
                    unsafe_reports=0,
                    missing_reports=0,
                    invalid_reports=0,
                ),
                reason_codes=(),
                safety_flags=SAFE_FLAGS,
            )

    def test_naive_generated_at(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            ReviewAuditRecord(
                audit_id="a1",
                generated_at=datetime(2026, 6, 27, 12, 0, 0),
                audit_state=ReviewState.READY,
                records=(),
                summary=ReviewAuditSummary(
                    total_reviews=0,
                    accepted_count=0,
                    rejected_count=0,
                    needs_investigation_count=0,
                    not_reviewed_count=0,
                    blocked_count=0,
                    unknown_count=0,
                    reason_counts={},
                ),
                data_quality=ReviewDataQuality(
                    total_reports=0,
                    valid_reports=0,
                    blocked_reports=0,
                    unknown_reports=0,
                    unsafe_reports=0,
                    missing_reports=0,
                    invalid_reports=0,
                ),
                reason_codes=(),
                safety_flags=SAFE_FLAGS,
            )

    def test_non_ready_requires_reason_codes(self):
        with pytest.raises(ValueError, match="reason_codes"):
            ReviewAuditRecord(
                audit_id="a1",
                generated_at=NOW,
                audit_state=ReviewState.BLOCKED,
                records=(),
                summary=ReviewAuditSummary(
                    total_reviews=0,
                    accepted_count=0,
                    rejected_count=0,
                    needs_investigation_count=0,
                    not_reviewed_count=0,
                    blocked_count=0,
                    unknown_count=0,
                    reason_counts={},
                ),
                data_quality=ReviewDataQuality(
                    total_reports=0,
                    valid_reports=0,
                    blocked_reports=0,
                    unknown_reports=0,
                    unsafe_reports=0,
                    missing_reports=0,
                    invalid_reports=0,
                ),
                reason_codes=(),
                safety_flags=SAFE_FLAGS,
            )

    def test_blocked_factory(self):
        audit = ReviewAuditRecord.blocked(
            reason_codes=(DEFAULT_BLOCKED,),
            now=NOW,
        )
        assert audit.audit_state is ReviewState.BLOCKED
        assert audit.reason_codes == (DEFAULT_BLOCKED,)
        assert audit.records == ()
        assert audit.summary.total_reviews == 0

    def test_blocked_with_records(self):
        record = ReviewRecord.blocked(reason_codes=(MISSING_REPORT,), now=NOW)
        audit = ReviewAuditRecord.blocked(
            reason_codes=(DEFAULT_BLOCKED,),
            records=(record,),
            now=NOW,
        )
        assert audit.summary.blocked_count == 1

    def test_immutability(self):
        audit = ReviewAuditRecord.blocked(reason_codes=(DEFAULT_BLOCKED,), now=NOW)
        with pytest.raises(FrozenInstanceError):
            audit.audit_id = "new"
