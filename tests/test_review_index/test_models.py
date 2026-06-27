"""Tests for hunter.review_index.models."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.review_index.models import (
    DEFAULT_BLOCKED,
    EMPTY_INDEX,
    FORBIDDEN_INDEX_TERMS,
    INDEX_ERROR,
    INVALID_REPORT,
    INVALID_REVIEW,
    MISSING_REPORTS,
    MISSING_REVIEWS,
    REASON_CODES,
    UNSAFE_INDEX_CONTENT,
    UNSAFE_REPORT_STATE,
    UNSAFE_REVIEW_STATE,
    UNSAFE_SAFETY_FLAGS,
    UNSUPPORTED_REPORT_VERSION,
    UNSUPPORTED_REVIEW_VERSION,
    IndexConfig,
    IndexDataQuality,
    IndexEntry,
    IndexEntryKind,
    IndexOutputFormat,
    IndexSafetyFlags,
    IndexState,
    IndexSummary,
    ReviewIndex,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestIndexState:
    def test_all_values(self) -> None:
        assert IndexState.DISABLED.value == "DISABLED"
        assert IndexState.READY.value == "READY"
        assert IndexState.BLOCKED.value == "BLOCKED"
        assert IndexState.UNKNOWN.value == "UNKNOWN"


class TestIndexEntryKind:
    def test_all_values(self) -> None:
        assert IndexEntryKind.OBSERVATION_REPORT.value == "OBSERVATION_REPORT"
        assert IndexEntryKind.REVIEW_AUDIT_RECORD.value == "REVIEW_AUDIT_RECORD"
        assert IndexEntryKind.LINKED_REPORT_REVIEW.value == "LINKED_REPORT_REVIEW"


class TestIndexOutputFormat:
    def test_all_values(self) -> None:
        assert IndexOutputFormat.JSON.value == "JSON"
        assert IndexOutputFormat.MARKDOWN.value == "MARKDOWN"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

class TestReasonCodes:
    def test_all_reason_codes_present(self) -> None:
        assert MISSING_REPORTS in REASON_CODES
        assert MISSING_REVIEWS in REASON_CODES
        assert INVALID_REPORT in REASON_CODES
        assert INVALID_REVIEW in REASON_CODES
        assert UNSUPPORTED_REPORT_VERSION in REASON_CODES
        assert UNSUPPORTED_REVIEW_VERSION in REASON_CODES
        assert UNSAFE_REPORT_STATE in REASON_CODES
        assert UNSAFE_REVIEW_STATE in REASON_CODES
        assert UNSAFE_SAFETY_FLAGS in REASON_CODES
        assert UNSAFE_INDEX_CONTENT in REASON_CODES
        assert EMPTY_INDEX in REASON_CODES
        assert INDEX_ERROR in REASON_CODES
        assert DEFAULT_BLOCKED in REASON_CODES

    def test_reason_codes_is_tuple(self) -> None:
        assert isinstance(REASON_CODES, tuple)
        assert len(REASON_CODES) == 13


# ---------------------------------------------------------------------------
# Forbidden terms
# ---------------------------------------------------------------------------

class TestForbiddenTerms:
    def test_minimum_terms_present(self) -> None:
        assert "api_key" in FORBIDDEN_INDEX_TERMS
        assert "secret" in FORBIDDEN_INDEX_TERMS
        assert "exchange_credentials" in FORBIDDEN_INDEX_TERMS
        assert "executable_instructions" in FORBIDDEN_INDEX_TERMS
        assert "operational_instructions" in FORBIDDEN_INDEX_TERMS
        assert "enter_long" in FORBIDDEN_INDEX_TERMS
        assert "enter_short" in FORBIDDEN_INDEX_TERMS
        assert "exit_long" in FORBIDDEN_INDEX_TERMS
        assert "exit_short" in FORBIDDEN_INDEX_TERMS
        assert "order" in FORBIDDEN_INDEX_TERMS
        assert "leverage" in FORBIDDEN_INDEX_TERMS
        assert "shorting" in FORBIDDEN_INDEX_TERMS
        assert "binance" in FORBIDDEN_INDEX_TERMS
        assert "exchange" in FORBIDDEN_INDEX_TERMS


# ---------------------------------------------------------------------------
# IndexConfig tests
# ---------------------------------------------------------------------------

class TestIndexConfig:
    def test_safe_defaults(self) -> None:
        config = IndexConfig()
        assert config.observation_report_version == "1.0"
        assert config.review_audit_version == "1.0"
        assert config.enable_json_output is True
        assert config.enable_markdown_output is True
        assert config.dry_run is True
        assert config.live_trading_enabled is False
        assert config.real_orders_enabled is False
        assert config.leverage_enabled is False
        assert config.shorting_enabled is False
        assert config.allow_report_feedback_into_execution is False
        assert config.allow_operator_feedback_into_execution is False
        assert config.allow_index_feedback_into_execution is False
        assert config.allow_file_reference_traversal is False
        assert config.allow_database_persistence is False
        assert config.allow_web_ui is False
        assert config.allow_dashboard is False

    def test_rejects_empty_versions(self) -> None:
        with pytest.raises(ValueError, match="observation_report_version"):
            IndexConfig(observation_report_version="")
        with pytest.raises(ValueError, match="review_audit_version"):
            IndexConfig(review_audit_version="")

    def test_rejects_no_output_enabled(self) -> None:
        with pytest.raises(ValueError, match="at least one output format"):
            IndexConfig(enable_json_output=False, enable_markdown_output=False)

    def test_rejects_dry_run_false(self) -> None:
        with pytest.raises(ValueError, match="dry_run"):
            IndexConfig(dry_run=False)

    def test_rejects_live_trading_enabled(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled"):
            IndexConfig(live_trading_enabled=True)

    def test_rejects_real_orders_enabled(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled"):
            IndexConfig(real_orders_enabled=True)

    def test_rejects_leverage_enabled(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled"):
            IndexConfig(leverage_enabled=True)

    def test_rejects_shorting_enabled(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled"):
            IndexConfig(shorting_enabled=True)

    def test_rejects_report_feedback(self) -> None:
        with pytest.raises(ValueError, match="allow_report_feedback"):
            IndexConfig(allow_report_feedback_into_execution=True)

    def test_rejects_operator_feedback(self) -> None:
        with pytest.raises(ValueError, match="allow_operator_feedback"):
            IndexConfig(allow_operator_feedback_into_execution=True)

    def test_rejects_index_feedback(self) -> None:
        with pytest.raises(ValueError, match="allow_index_feedback"):
            IndexConfig(allow_index_feedback_into_execution=True)

    def test_rejects_file_traversal(self) -> None:
        with pytest.raises(ValueError, match="allow_file_reference_traversal"):
            IndexConfig(allow_file_reference_traversal=True)

    def test_rejects_database_persistence(self) -> None:
        with pytest.raises(ValueError, match="allow_database_persistence"):
            IndexConfig(allow_database_persistence=True)

    def test_rejects_web_ui(self) -> None:
        with pytest.raises(ValueError, match="allow_web_ui"):
            IndexConfig(allow_web_ui=True)

    def test_rejects_dashboard(self) -> None:
        with pytest.raises(ValueError, match="allow_dashboard"):
            IndexConfig(allow_dashboard=True)


# ---------------------------------------------------------------------------
# IndexSafetyFlags tests
# ---------------------------------------------------------------------------

class TestIndexSafetyFlags:
    def test_safe_defaults(self) -> None:
        flags = IndexSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.report_feedback_into_execution is False
        assert flags.operator_feedback_into_execution is False
        assert flags.index_feedback_into_execution is False
        assert flags.file_reference_traversal_enabled is False
        assert flags.database_persistence_enabled is False
        assert flags.web_ui_enabled is False
        assert flags.dashboard_enabled is False

    def test_rejects_dry_run_false(self) -> None:
        with pytest.raises(ValueError, match="dry_run"):
            IndexSafetyFlags(dry_run=False)

    def test_rejects_live_trading(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled"):
            IndexSafetyFlags(live_trading_enabled=True)

    def test_rejects_real_orders(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled"):
            IndexSafetyFlags(real_orders_enabled=True)

    def test_rejects_leverage(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled"):
            IndexSafetyFlags(leverage_enabled=True)

    def test_rejects_shorting(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled"):
            IndexSafetyFlags(shorting_enabled=True)

    def test_rejects_report_feedback(self) -> None:
        with pytest.raises(ValueError, match="report_feedback_into_execution"):
            IndexSafetyFlags(report_feedback_into_execution=True)

    def test_rejects_operator_feedback(self) -> None:
        with pytest.raises(ValueError, match="operator_feedback_into_execution"):
            IndexSafetyFlags(operator_feedback_into_execution=True)

    def test_rejects_index_feedback(self) -> None:
        with pytest.raises(ValueError, match="index_feedback_into_execution"):
            IndexSafetyFlags(index_feedback_into_execution=True)

    def test_rejects_file_traversal(self) -> None:
        with pytest.raises(ValueError, match="file_reference_traversal_enabled"):
            IndexSafetyFlags(file_reference_traversal_enabled=True)

    def test_rejects_database_persistence(self) -> None:
        with pytest.raises(ValueError, match="database_persistence_enabled"):
            IndexSafetyFlags(database_persistence_enabled=True)

    def test_rejects_web_ui(self) -> None:
        with pytest.raises(ValueError, match="web_ui_enabled"):
            IndexSafetyFlags(web_ui_enabled=True)

    def test_rejects_dashboard(self) -> None:
        with pytest.raises(ValueError, match="dashboard_enabled"):
            IndexSafetyFlags(dashboard_enabled=True)


# ---------------------------------------------------------------------------
# IndexEntry tests
# ---------------------------------------------------------------------------

class TestIndexEntry:
    def test_valid_observation_entry(self) -> None:
        now = datetime.now(timezone.utc)
        entry = IndexEntry(
            entry_id="r1",
            entry_kind=IndexEntryKind.OBSERVATION_REPORT,
            index_state=IndexState.READY,
            report_id="report-1",
            report_generated_at=now,
            review_status="NOT_REVIEWED",
            review_state="UNKNOWN",
            source_report_version="1.0",
        )
        assert entry.entry_id == "r1"
        assert entry.entry_kind is IndexEntryKind.OBSERVATION_REPORT
        assert entry.index_state is IndexState.READY
        assert entry.report_id == "report-1"
        assert entry.report_generated_at == now

    def test_valid_linked_entry(self) -> None:
        now = datetime.now(timezone.utc)
        entry = IndexEntry(
            entry_id="r1-a1",
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW,
            index_state=IndexState.READY,
            report_id="report-1",
            audit_id="audit-1",
            report_generated_at=now,
            audit_generated_at=now,
            reviewed_at=now,
            review_status="ACCEPTED",
            review_state="READY",
            source_report_version="1.0",
            source_review_version="1.0",
            tags=("tag1",),
            reviewer="alice",
        )
        assert entry.entry_id == "r1-a1"
        assert entry.entry_kind is IndexEntryKind.LINKED_REPORT_REVIEW
        assert entry.review_status == "ACCEPTED"
        assert entry.reviewer == "alice"

    def test_blocked_factory(self) -> None:
        entry = IndexEntry.blocked()
        assert entry.index_state is IndexState.BLOCKED
        assert entry.reason_codes == (DEFAULT_BLOCKED,)
        assert entry.entry_id == "blocked"
        assert entry.report_id == "blocked"

    def test_blocked_factory_with_custom_reason(self) -> None:
        entry = IndexEntry.blocked(
            entry_id="custom",
            report_id="custom-report",
            reason_codes=(INVALID_REPORT,),
        )
        assert entry.index_state is IndexState.BLOCKED
        assert entry.reason_codes == (INVALID_REPORT,)
        assert entry.entry_id == "custom"
        assert entry.report_id == "custom-report"

    def test_rejects_empty_entry_id(self) -> None:
        with pytest.raises(ValueError, match="entry_id"):
            IndexEntry(
                entry_id="",
                entry_kind=IndexEntryKind.OBSERVATION_REPORT,
                index_state=IndexState.READY,
                report_id="r1",
            )

    def test_rejects_empty_report_id(self) -> None:
        with pytest.raises(ValueError, match="report_id"):
            IndexEntry(
                entry_id="e1",
                entry_kind=IndexEntryKind.OBSERVATION_REPORT,
                index_state=IndexState.READY,
                report_id="",
            )

    def test_rejects_invalid_entry_kind(self) -> None:
        with pytest.raises(ValueError, match="entry_kind"):
            IndexEntry(
                entry_id="e1",
                entry_kind="invalid",  # type: ignore[arg-type]
                index_state=IndexState.READY,
                report_id="r1",
            )

    def test_rejects_invalid_index_state(self) -> None:
        with pytest.raises(ValueError, match="index_state"):
            IndexEntry(
                entry_id="e1",
                entry_kind=IndexEntryKind.OBSERVATION_REPORT,
                index_state="invalid",  # type: ignore[arg-type]
                report_id="r1",
            )

    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            IndexEntry(
                entry_id="e1",
                entry_kind=IndexEntryKind.OBSERVATION_REPORT,
                index_state=IndexState.READY,
                report_id="r1",
                report_generated_at=datetime(2024, 1, 1),
            )

    def test_rejects_invalid_review_status(self) -> None:
        with pytest.raises(ValueError, match="review_status"):
            IndexEntry(
                entry_id="e1",
                entry_kind=IndexEntryKind.OBSERVATION_REPORT,
                index_state=IndexState.READY,
                report_id="r1",
                review_status="INVALID",
            )

    def test_rejects_invalid_review_state(self) -> None:
        with pytest.raises(ValueError, match="review_state"):
            IndexEntry(
                entry_id="e1",
                entry_kind=IndexEntryKind.OBSERVATION_REPORT,
                index_state=IndexState.READY,
                report_id="r1",
                review_state="INVALID",
            )

    def test_rejects_blocked_without_reason(self) -> None:
        with pytest.raises(ValueError, match="reason_codes"):
            IndexEntry(
                entry_id="e1",
                entry_kind=IndexEntryKind.OBSERVATION_REPORT,
                index_state=IndexState.BLOCKED,
                report_id="r1",
                reason_codes=(),
            )

    def test_rejects_unsafe_tag(self) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            IndexEntry(
                entry_id="e1",
                entry_kind=IndexEntryKind.OBSERVATION_REPORT,
                index_state=IndexState.READY,
                report_id="r1",
                tags=("contains_api_key",),
            )

    def test_rejects_unsafe_reviewer(self) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            IndexEntry(
                entry_id="e1",
                entry_kind=IndexEntryKind.OBSERVATION_REPORT,
                index_state=IndexState.READY,
                report_id="r1",
                reviewer="has_secret",
            )

    def test_rejects_unsafe_reference(self) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            IndexEntry(
                entry_id="e1",
                entry_kind=IndexEntryKind.OBSERVATION_REPORT,
                index_state=IndexState.READY,
                report_id="r1",
                local_report_reference="path_with_binance",
            )

    def test_rejects_unsafe_metadata_key(self) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            IndexEntry(
                entry_id="e1",
                entry_kind=IndexEntryKind.OBSERVATION_REPORT,
                index_state=IndexState.READY,
                report_id="r1",
                metadata={"api_key": "value"},
            )

    def test_rejects_mutation(self) -> None:
        entry = IndexEntry.blocked()
        with pytest.raises(AttributeError):
            entry.entry_id = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# IndexSummary tests
# ---------------------------------------------------------------------------

class TestIndexSummary:
    def test_defaults(self) -> None:
        summary = IndexSummary()
        assert summary.total_entries == 0
        assert summary.observation_report_count == 0
        assert summary.reason_counts == {}

    def test_valid_counts(self) -> None:
        summary = IndexSummary(
            total_entries=3,
            observation_report_count=1,
            review_audit_count=1,
            linked_entry_count=1,
            ready_count=2,
            blocked_count=1,
            accepted_count=1,
            rejected_count=1,
            not_reviewed_count=1,
            reason_counts={INVALID_REPORT: 1},
        )
        assert summary.total_entries == 3
        assert summary.reason_counts[INVALID_REPORT] == 1

    def test_rejects_negative_total(self) -> None:
        with pytest.raises(ValueError, match="total_entries"):
            IndexSummary(total_entries=-1)

    def test_rejects_category_exceeds_total(self) -> None:
        with pytest.raises(ValueError, match="category counts"):
            IndexSummary(
                total_entries=1,
                observation_report_count=2,
            )

    def test_rejects_status_exceeds_total(self) -> None:
        with pytest.raises(ValueError, match="status counts"):
            IndexSummary(
                total_entries=1,
                accepted_count=2,
            )

    def test_rejects_state_exceeds_total(self) -> None:
        with pytest.raises(ValueError, match="state counts"):
            IndexSummary(
                total_entries=1,
                ready_count=2,
            )

    def test_rejects_negative_reason_count(self) -> None:
        with pytest.raises(ValueError, match="reason_counts"):
            IndexSummary(reason_counts={INVALID_REPORT: -1})


# ---------------------------------------------------------------------------
# IndexDataQuality tests
# ---------------------------------------------------------------------------

class TestIndexDataQuality:
    def test_defaults(self) -> None:
        dq = IndexDataQuality()
        assert dq.total_reports == 0
        assert dq.valid_reports == 0

    def test_valid_counts(self) -> None:
        dq = IndexDataQuality(
            total_reports=5,
            valid_reports=3,
            invalid_reports=1,
            unsafe_reports=1,
            total_reviews=4,
            valid_reviews=2,
            invalid_reviews=1,
            unsafe_reviews=1,
            linked_records=2,
            unlinked_reports=1,
            unlinked_reviews=1,
        )
        assert dq.total_reports == 5
        assert dq.valid_reports == 3

    def test_rejects_negative_total_reports(self) -> None:
        with pytest.raises(ValueError, match="total_reports"):
            IndexDataQuality(total_reports=-1)

    def test_rejects_report_category_exceeds_total(self) -> None:
        with pytest.raises(ValueError, match="report category"):
            IndexDataQuality(
                total_reports=1,
                valid_reports=1,
                invalid_reports=1,
            )

    def test_rejects_review_category_exceeds_total(self) -> None:
        with pytest.raises(ValueError, match="review category"):
            IndexDataQuality(
                total_reviews=1,
                valid_reviews=1,
                invalid_reviews=1,
            )


# ---------------------------------------------------------------------------
# ReviewIndex tests
# ---------------------------------------------------------------------------

class TestReviewIndex:
    def test_valid_index(self) -> None:
        now = datetime.now(timezone.utc)
        entry = IndexEntry.blocked()
        index = ReviewIndex(
            index_id="idx-1",
            generated_at=now,
            index_state=IndexState.BLOCKED,
            entries=(entry,),
            summary=IndexSummary(total_entries=1, blocked_count=1),
            data_quality=IndexDataQuality(),
            safety_flags=IndexSafetyFlags(),
            reason_codes=(DEFAULT_BLOCKED,),
        )
        assert index.index_id == "idx-1"
        assert index.generated_at == now

    def test_blocked_factory(self) -> None:
        index = ReviewIndex.blocked()
        assert index.index_state is IndexState.BLOCKED
        assert index.reason_codes == (DEFAULT_BLOCKED,)
        assert index.index_id == "blocked"
        assert index.entries == ()

    def test_blocked_factory_with_custom(self) -> None:
        now = datetime.now(timezone.utc)
        index = ReviewIndex.blocked(
            index_id="custom",
            generated_at=now,
            reason_codes=(EMPTY_INDEX,),
        )
        assert index.index_state is IndexState.BLOCKED
        assert index.reason_codes == (EMPTY_INDEX,)
        assert index.index_id == "custom"
        assert index.generated_at == now

    def test_rejects_empty_index_id(self) -> None:
        with pytest.raises(ValueError, match="index_id"):
            ReviewIndex(
                index_id="",
                generated_at=datetime.now(timezone.utc),
                index_state=IndexState.READY,
                entries=(),
                summary=IndexSummary(),
                data_quality=IndexDataQuality(),
                safety_flags=IndexSafetyFlags(),
                reason_codes=(),
            )

    def test_rejects_naive_generated_at(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            ReviewIndex(
                index_id="idx-1",
                generated_at=datetime(2024, 1, 1),
                index_state=IndexState.READY,
                entries=(),
                summary=IndexSummary(),
                data_quality=IndexDataQuality(),
                safety_flags=IndexSafetyFlags(),
                reason_codes=(),
            )

    def test_rejects_invalid_index_state(self) -> None:
        with pytest.raises(ValueError, match="index_state"):
            ReviewIndex(
                index_id="idx-1",
                generated_at=datetime.now(timezone.utc),
                index_state="invalid",  # type: ignore[arg-type]
                entries=(),
                summary=IndexSummary(),
                data_quality=IndexDataQuality(),
                safety_flags=IndexSafetyFlags(),
                reason_codes=(),
            )

    def test_rejects_blocked_without_reason(self) -> None:
        with pytest.raises(ValueError, match="reason_codes"):
            ReviewIndex(
                index_id="idx-1",
                generated_at=datetime.now(timezone.utc),
                index_state=IndexState.BLOCKED,
                entries=(),
                summary=IndexSummary(),
                data_quality=IndexDataQuality(),
                safety_flags=IndexSafetyFlags(),
                reason_codes=(),
            )
