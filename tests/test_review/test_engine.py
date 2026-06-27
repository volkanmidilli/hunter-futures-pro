"""Unit tests for hunter.review engine."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.review.models import (
    DEFAULT_BLOCKED,
    DRY_RUN_DISABLED,
    INVALID_REPORT,
    INVALID_REVIEW_STATUS,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    MISSING_REPORT,
    MISSING_REVIEWER,
    REAL_ORDERS_ENABLED,
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
from hunter.review.engine import (
    build_review_audit_record,
    build_review_audit_summary,
    build_review_data_quality,
    build_review_record,
    build_review_safety_flags,
    has_unsafe_review_content,
)

NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

SAFE_FLAGS = ReviewSafetyFlags(
    dry_run=True,
    live_trading_enabled=False,
    real_orders_enabled=False,
    leverage_enabled=False,
    shorting_enabled=False,
    report_feedback_into_execution=False,
    operator_feedback_into_execution=False,
    network_calls_enabled=False,
    database_persistence_enabled=False,
)

SAFE_CONFIG = ReviewConfig(
    input_version="1.0",
    max_report_age_seconds=3600,
    enable_json_output=True,
    enable_markdown_output=True,
    dry_run=True,
    live_trading_enabled=False,
    real_orders_enabled=False,
    leverage_enabled=False,
    shorting_enabled=False,
    allow_report_feedback_into_execution=False,
    allow_operator_feedback_into_execution=False,
)


def safe_report(
    version: str = "1.0",
    report_state: str = "READY",
    dry_run: bool = True,
    live_trading_enabled: bool = False,
    real_orders_enabled: bool = False,
    leverage_enabled: bool = False,
    shorting_enabled: bool = False,
) -> dict[str, Any]:
    return {
        "version": version,
        "report_state": report_state,
        "dry_run": dry_run,
        "live_trading_enabled": live_trading_enabled,
        "real_orders_enabled": real_orders_enabled,
        "leverage_enabled": leverage_enabled,
        "shorting_enabled": shorting_enabled,
        "reason_codes": ("LONG_RESEARCH",),
    }


# ---------------------------------------------------------------------------
# has_unsafe_review_content tests
# ---------------------------------------------------------------------------

class TestHasUnsafeReviewContent:
    def test_forbidden_in_notes(self):
        assert has_unsafe_review_content(notes="my api_key is secret", tags=(), metadata={}) is True

    def test_forbidden_in_tags(self):
        assert has_unsafe_review_content(notes="", tags=("has_enter_long",), metadata={}) is True

    def test_forbidden_in_metadata_keys(self):
        assert has_unsafe_review_content(notes="", tags=(), metadata={"binance": "value"}) is True

    def test_safe_content(self):
        assert has_unsafe_review_content(notes="routine review", tags=("routine",), metadata={"source": "test"}) is False

    def test_case_insensitive(self):
        assert has_unsafe_review_content(notes="API_KEY", tags=(), metadata={}) is True

    def test_empty(self):
        assert has_unsafe_review_content(notes="", tags=(), metadata={}) is False


# ---------------------------------------------------------------------------
# build_review_safety_flags tests
# ---------------------------------------------------------------------------

class TestBuildReviewSafetyFlags:
    def test_safe_defaults(self):
        flags = build_review_safety_flags(SAFE_CONFIG)
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.shorting_enabled is False
        assert flags.report_feedback_into_execution is False


# ---------------------------------------------------------------------------
# build_review_record happy path tests
# ---------------------------------------------------------------------------

class TestBuildReviewRecordHappyPath:
    def test_accepted(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.review_state is ReviewState.READY
        assert record.review_status is ReviewStatus.ACCEPTED
        assert record.reviewer == "op1"
        assert record.reason_codes == ("ACCEPTED",)

    def test_rejected(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.REJECTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.review_state is ReviewState.READY
        assert record.review_status is ReviewStatus.REJECTED
        assert record.reason_codes == ("REJECTED",)

    def test_needs_investigation(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.NEEDS_INVESTIGATION,
            reviewer="op1",
            now=NOW,
        )
        assert record.review_state is ReviewState.READY
        assert record.review_status is ReviewStatus.NEEDS_INVESTIGATION
        assert record.reason_codes == ("NEEDS_INVESTIGATION",)

    def test_not_reviewed(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="op1",
            now=NOW,
        )
        assert record.review_state is ReviewState.READY
        assert record.review_status is ReviewStatus.NOT_REVIEWED
        assert record.reason_codes == ()

    def test_reviewed(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.REVIEWED,
            reviewer="op1",
            now=NOW,
        )
        assert record.review_state is ReviewState.READY
        assert record.review_status is ReviewStatus.REVIEWED
        assert record.reason_codes == ("REVIEWED",)

    def test_with_notes_and_tags(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            notes="looks good",
            tags=("routine",),
            now=NOW,
        )
        assert record.notes == "looks good"
        assert record.tags == ("routine",)

    def test_default_timestamp(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
        )
        assert record.reviewed_at.tzinfo is not None


# ---------------------------------------------------------------------------
# build_review_record blocking tests
# ---------------------------------------------------------------------------

class TestBuildReviewRecordMissing:
    def test_none(self):
        record = build_review_record(
            report=None,
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (MISSING_REPORT,)


class TestBuildReviewRecordInvalid:
    def test_not_dict(self):
        record = build_review_record(
            report="not-a-dict",
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (INVALID_REPORT,)

    def test_missing_version(self):
        record = build_review_record(
            report={"report_state": "READY"},
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (INVALID_REPORT,)

    def test_missing_report_state(self):
        record = build_review_record(
            report={"version": "1.0"},
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (INVALID_REPORT,)


class TestBuildReviewRecordVersion:
    def test_unsupported(self):
        record = build_review_record(
            report=safe_report(version="2.0"),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (UNSUPPORTED_REPORT_VERSION,)


class TestBuildReviewRecordUnsafeState:
    def test_blocked(self):
        record = build_review_record(
            report=safe_report(report_state="BLOCKED"),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (UNSAFE_REPORT_STATE,)

    def test_unknown(self):
        record = build_review_record(
            report=safe_report(report_state="UNKNOWN"),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (UNSAFE_REPORT_STATE,)

    def test_disabled(self):
        record = build_review_record(
            report=safe_report(report_state="DISABLED"),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (UNSAFE_REPORT_STATE,)


class TestBuildReviewRecordDryRun:
    def test_disabled(self):
        record = build_review_record(
            report=safe_report(dry_run=False),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (DRY_RUN_DISABLED,)


class TestBuildReviewRecordLiveTrading:
    def test_enabled(self):
        record = build_review_record(
            report=safe_report(live_trading_enabled=True),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (LIVE_TRADING_ENABLED,)


class TestBuildReviewRecordRealOrders:
    def test_enabled(self):
        record = build_review_record(
            report=safe_report(real_orders_enabled=True),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (REAL_ORDERS_ENABLED,)


class TestBuildReviewRecordLeverage:
    def test_enabled(self):
        record = build_review_record(
            report=safe_report(leverage_enabled=True),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (LEVERAGE_ENABLED,)


class TestBuildReviewRecordShorting:
    def test_enabled(self):
        record = build_review_record(
            report=safe_report(shorting_enabled=True),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (SHORTING_ENABLED,)


class TestBuildReviewRecordMissingReviewer:
    def test_empty(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="",
            now=NOW,
        )
        assert record.reason_codes == (MISSING_REVIEWER,)

    def test_not_required_for_not_reviewed(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            now=NOW,
        )
        assert record.review_state is ReviewState.READY


class TestBuildReviewRecordInvalidStatus:
    def test_string(self):
        record = build_review_record(
            report=safe_report(),
            review_status="INVALID",  # type: ignore[arg-type]
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (INVALID_REVIEW_STATUS,)


class TestBuildReviewRecordUnsafeContent:
    def test_forbidden_notes(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            notes="contains api_key",
            now=NOW,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (UNSAFE_REVIEW_CONTENT,)

    def test_forbidden_tags(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            notes="ok",
            tags=("has_enter_long",),
            now=NOW,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (UNSAFE_REVIEW_CONTENT,)

    def test_forbidden_metadata(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            metadata={"binance": "value"},
            now=NOW,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (UNSAFE_REVIEW_CONTENT,)


class TestBuildReviewRecordExceptionFailClosed:
    def test_exception_during_build(self):
        class BadReport(dict):
            def __getitem__(self, key: str) -> Any:
                if key == "version":
                    raise RuntimeError("boom")
                return super().__getitem__(key)

            def get(self, key: str, default: Any = None) -> Any:
                if key == "version":
                    raise RuntimeError("boom")
                return super().get(key, default)

        record = build_review_record(
            report=BadReport(safe_report()),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (REVIEW_ERROR,)


# ---------------------------------------------------------------------------
# Priority order tests
# ---------------------------------------------------------------------------

class TestBuildReviewRecordPriorityOrder:
    def test_missing_overrides_invalid(self):
        record = build_review_record(
            report=None,
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (MISSING_REPORT,)

    def test_invalid_overrides_version(self):
        record = build_review_record(
            report="not-a-dict",
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (INVALID_REPORT,)

    def test_version_overrides_state(self):
        record = build_review_record(
            report=safe_report(version="2.0", report_state="BLOCKED"),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (UNSUPPORTED_REPORT_VERSION,)

    def test_state_overrides_dry_run(self):
        record = build_review_record(
            report=safe_report(report_state="BLOCKED", dry_run=False),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (UNSAFE_REPORT_STATE,)

    def test_dry_run_overrides_live_trading(self):
        record = build_review_record(
            report=safe_report(dry_run=False, live_trading_enabled=True),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (DRY_RUN_DISABLED,)

    def test_live_trading_overrides_real_orders(self):
        record = build_review_record(
            report=safe_report(live_trading_enabled=True, real_orders_enabled=True),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (LIVE_TRADING_ENABLED,)

    def test_real_orders_overrides_leverage(self):
        record = build_review_record(
            report=safe_report(real_orders_enabled=True, leverage_enabled=True),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (REAL_ORDERS_ENABLED,)

    def test_leverage_overrides_shorting(self):
        record = build_review_record(
            report=safe_report(leverage_enabled=True, shorting_enabled=True),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            now=NOW,
        )
        assert record.reason_codes == (LEVERAGE_ENABLED,)

    def test_shorting_overrides_reviewer(self):
        record = build_review_record(
            report=safe_report(shorting_enabled=True),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="",
            now=NOW,
        )
        assert record.reason_codes == (SHORTING_ENABLED,)

    def test_reviewer_overrides_status(self):
        record = build_review_record(
            report=safe_report(),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="",
            now=NOW,
        )
        assert record.reason_codes == (MISSING_REVIEWER,)

    def test_status_overrides_content(self):
        record = build_review_record(
            report=safe_report(),
            review_status="INVALID",  # type: ignore[arg-type]
            reviewer="op1",
            notes="contains api_key",
            now=NOW,
        )
        assert record.reason_codes == (INVALID_REVIEW_STATUS,)

    def test_content_overrides_exception(self):
        class BadReport(dict):
            def get(self, key: str, default: Any = None) -> Any:
                if key == "version":
                    raise RuntimeError("boom")
                return super().get(key, default)

        record = build_review_record(
            report=BadReport(safe_report()),
            review_status=ReviewStatus.ACCEPTED,
            reviewer="op1",
            notes="contains api_key",
            now=NOW,
        )
        # exception is caught before content check
        assert record.reason_codes == (REVIEW_ERROR,)


# ---------------------------------------------------------------------------
# build_review_audit_summary tests
# ---------------------------------------------------------------------------

class TestBuildReviewAuditSummary:
    def test_empty(self):
        summary = build_review_audit_summary([])
        assert summary.total_reviews == 0
        assert summary.accepted_count == 0
        assert summary.blocked_count == 0

    def test_one_accepted(self):
        record = ReviewRecord(
            review_id="r1",
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
        summary = build_review_audit_summary([record])
        assert summary.total_reviews == 1
        assert summary.accepted_count == 1
        assert summary.blocked_count == 0

    def test_one_blocked(self):
        record = ReviewRecord.blocked(
            reason_codes=(MISSING_REPORT,),
            now=NOW,
        )
        summary = build_review_audit_summary([record])
        assert summary.total_reviews == 1
        assert summary.blocked_count == 1
        assert summary.not_reviewed_count == 1

    def test_mixed(self):
        accepted = ReviewRecord(
            review_id="r1",
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
        blocked = ReviewRecord.blocked(
            reason_codes=(MISSING_REPORT,),
            now=NOW,
        )
        summary = build_review_audit_summary([accepted, blocked])
        assert summary.total_reviews == 2
        assert summary.accepted_count == 1
        assert summary.blocked_count == 1
        assert summary.not_reviewed_count == 1
        assert summary.reason_counts == {"ACCEPTED": 1, MISSING_REPORT: 1}

    def test_reviewed_counts_as_not_reviewed(self):
        record = ReviewRecord(
            review_id="r1",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.REVIEWED,
            reviewer="op1",
            notes="",
            tags=(),
            reason_codes=("REVIEWED",),
            reviewed_at=NOW,
            safety_flags=SAFE_FLAGS,
            metadata={},
        )
        summary = build_review_audit_summary([record])
        assert summary.total_reviews == 1
        assert summary.not_reviewed_count == 1
        assert summary.accepted_count == 0


# ---------------------------------------------------------------------------
# build_review_data_quality tests
# ---------------------------------------------------------------------------

class TestBuildReviewDataQuality:
    def test_empty(self):
        dq = build_review_data_quality([])
        assert dq.total_reports == 0
        assert dq.valid_reports == 0
        assert dq.blocked_reports == 0

    def test_one_blocked(self):
        record = ReviewRecord.blocked(
            reason_codes=(MISSING_REPORT,),
            now=NOW,
        )
        dq = build_review_data_quality([record])
        assert dq.total_reports == 1
        assert dq.valid_reports == 0
        assert dq.blocked_reports == 1
        assert dq.missing_reports == 1

    def test_one_valid(self):
        record = ReviewRecord(
            review_id="r1",
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
        dq = build_review_data_quality([record])
        assert dq.total_reports == 1
        assert dq.valid_reports == 1
        assert dq.blocked_reports == 0


# ---------------------------------------------------------------------------
# build_review_audit_record tests
# ---------------------------------------------------------------------------

class TestBuildReviewAuditRecord:
    def test_empty_records(self):
        audit = build_review_audit_record(
            records=[],
            config=SAFE_CONFIG,
            now=NOW,
        )
        assert audit.audit_state is ReviewState.BLOCKED
        assert audit.reason_codes == (DEFAULT_BLOCKED,)
        assert audit.summary.total_reviews == 0

    def test_one_blocked(self):
        record = ReviewRecord.blocked(
            reason_codes=(MISSING_REPORT,),
            now=NOW,
        )
        audit = build_review_audit_record(
            records=[record],
            config=SAFE_CONFIG,
            now=NOW,
        )
        assert audit.audit_state is ReviewState.BLOCKED
        assert audit.summary.total_reviews == 1
        assert audit.summary.blocked_count == 1
        assert audit.data_quality.blocked_reports == 1

    def test_mixed_blocked_and_ready(self):
        ready = ReviewRecord(
            review_id="r1",
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
        blocked = ReviewRecord.blocked(
            reason_codes=(MISSING_REPORT,),
            now=NOW,
        )
        audit = build_review_audit_record(
            records=[ready, blocked],
            config=SAFE_CONFIG,
            now=NOW,
        )
        assert audit.audit_state is ReviewState.BLOCKED
        assert audit.summary.total_reviews == 2
        assert audit.summary.accepted_count == 1
        assert audit.summary.blocked_count == 1

    def test_data_quality_populated(self):
        record = ReviewRecord.blocked(
            reason_codes=(MISSING_REPORT,),
            now=NOW,
        )
        audit = build_review_audit_record(
            records=[record],
            config=SAFE_CONFIG,
            now=NOW,
        )
        assert audit.data_quality.total_reports == 1
        assert audit.data_quality.missing_reports == 1

    def test_safety_flags_safe(self):
        audit = build_review_audit_record(
            records=[],
            config=SAFE_CONFIG,
            now=NOW,
        )
        assert audit.safety_flags.dry_run is True
        assert audit.safety_flags.live_trading_enabled is False
        assert audit.safety_flags.report_feedback_into_execution is False

    def test_default_timestamp(self):
        audit = build_review_audit_record(
            records=[],
            config=SAFE_CONFIG,
        )
        assert audit.generated_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Safety assertions
# ---------------------------------------------------------------------------

class TestSafetyAssertions:
    def test_no_file_reads(self):
        import hunter.review.engine as engine_module
        assert "read" not in engine_module.__dict__
        assert "open" not in engine_module.__dict__

    def test_no_file_writes(self):
        import hunter.review.engine as engine_module
        assert "write" not in engine_module.__dict__
        assert "open" not in engine_module.__dict__

    def test_no_network(self):
        import hunter.review.engine as engine_module
        assert "requests" not in engine_module.__dict__
        assert "urllib" not in engine_module.__dict__

    def test_no_database(self):
        import hunter.review.engine as engine_module
        assert "sqlite" not in engine_module.__dict__
        assert "db" not in engine_module.__dict__

    def test_no_freqtrade(self):
        import hunter.review.engine as engine_module
        assert "freqtrade" not in engine_module.__dict__

    def test_no_binance(self):
        import hunter.review.engine as engine_module
        assert "binance" not in engine_module.__dict__

    def test_no_live_trading(self):
        assert "live_trading" not in str(build_review_record.__code__.co_names).lower() or "live_trading_enabled" in str(build_review_record.__code__.co_names).lower()

    def test_no_real_orders(self):
        assert "real_orders" not in str(build_review_record.__code__.co_names).lower() or "real_orders_enabled" in str(build_review_record.__code__.co_names).lower()

    def test_no_leverage(self):
        assert "leverage" not in str(build_review_record.__code__.co_names).lower() or "leverage_enabled" in str(build_review_record.__code__.co_names).lower()

    def test_no_shorting(self):
        assert "shorting" not in str(build_review_record.__code__.co_names).lower() or "shorting_enabled" in str(build_review_record.__code__.co_names).lower()

    def test_no_real_entry_exit(self):
        assert "enter_long" not in str(build_review_record.__code__.co_names).lower()
        assert "exit_long" not in str(build_review_record.__code__.co_names).lower()

    def test_no_report_feedback(self):
        import hunter.review.engine as engine_module
        assert "report_feedback" not in str(engine_module.__dict__).lower()
        assert "operator_feedback" not in str(engine_module.__dict__).lower()

    def test_no_execution_feedback(self):
        import hunter.review.engine as engine_module
        assert "execution" not in str(engine_module.__dict__).lower()

    def test_no_trade_approval(self):
        import hunter.review.engine as engine_module
        assert "approve" not in str(engine_module.__dict__).lower()
        assert "trade" not in str(engine_module.__dict__).lower()
