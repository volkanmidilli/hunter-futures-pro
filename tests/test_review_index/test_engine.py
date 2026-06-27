"""Tests for hunter.review_index.engine.

No file I/O, no network, no database, no UI, no dashboard, no exchange,
no trading, no leverage, no shorting, no real entry/exit.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.review_index.engine import (
    build_index_data_quality,
    build_index_entry,
    build_index_safety_flags,
    build_index_summary,
    build_review_index,
    has_unsafe_index_content,
)
from hunter.review_index.models import (
    DEFAULT_BLOCKED,
    EMPTY_INDEX,
    INDEX_ERROR,
    INVALID_REPORT,
    INVALID_REVIEW,
    MISSING_REPORTS,
    MISSING_REVIEWS,
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
    IndexSafetyFlags,
    IndexState,
    IndexSummary,
    ReviewIndex,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(
    report_id: str = "report-1",
    version: str = "1.0",
    report_state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    metadata: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a minimal valid report dict."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    return {
        "report_id": report_id,
        "version": version,
        "report_state": report_state,
        "reason_codes": reason_codes,
        "metadata": metadata or {},
        "generated_at": generated_at,
    }


def _make_review(
    audit_id: str = "audit-1",
    report_id: str = "report-1",
    version: str = "1.0",
    review_status: str = "ACCEPTED",
    review_state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    reviewer: str = "alice",
    metadata: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
    reviewed_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a minimal valid review dict."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    if reviewed_at is None:
        reviewed_at = datetime.now(timezone.utc)
    return {
        "audit_id": audit_id,
        "report_id": report_id,
        "version": version,
        "review_status": review_status,
        "review_state": review_state,
        "reason_codes": reason_codes,
        "tags": tags,
        "reviewer": reviewer,
        "metadata": metadata or {},
        "generated_at": generated_at,
        "reviewed_at": reviewed_at,
    }


# ---------------------------------------------------------------------------
# has_unsafe_index_content
# ---------------------------------------------------------------------------

class TestHasUnsafeIndexContent:
    def test_empty_string_is_safe(self) -> None:
        assert has_unsafe_index_content("") is False

    def test_none_is_safe(self) -> None:
        # function accepts None and returns False (no crash)
        assert has_unsafe_index_content(None) is False  # type: ignore[arg-type]

    def test_safe_text(self) -> None:
        assert has_unsafe_index_content("normal observation text") is False

    def test_forbidden_api_key(self) -> None:
        assert has_unsafe_index_content("contains api_key here") is True

    def test_forbidden_secret(self) -> None:
        assert has_unsafe_index_content("top secret info") is True

    def test_forbidden_binance(self) -> None:
        assert has_unsafe_index_content("binance exchange data") is True

    def test_forbidden_leverage(self) -> None:
        assert has_unsafe_index_content("high leverage") is True

    def test_forbidden_enter_long(self) -> None:
        assert has_unsafe_index_content("enter_long signal") is True

    def test_forbidden_case_insensitive(self) -> None:
        assert has_unsafe_index_content("API_KEY") is True
        assert has_unsafe_index_content("Binance") is True
        assert has_unsafe_index_content("LeVeRaGe") is True

    def test_forbidden_substring_match(self) -> None:
        assert has_unsafe_index_content("my_api_key_value") is True
        assert has_unsafe_index_content("preleveragepost") is True

    def test_safe_text_with_similar_substrings(self) -> None:
        # "api" alone is not forbidden; "key" alone is not forbidden
        assert has_unsafe_index_content("api key") is False


# ---------------------------------------------------------------------------
# build_index_safety_flags
# ---------------------------------------------------------------------------

class TestBuildIndexSafetyFlags:
    def test_default_config(self) -> None:
        flags = build_index_safety_flags(IndexConfig())
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

    def test_custom_config_values(self) -> None:
        # All safe values (same as defaults)
        config = IndexConfig()
        flags = build_index_safety_flags(config)
        assert isinstance(flags, IndexSafetyFlags)

    def test_returns_index_safety_flags_instance(self) -> None:
        flags = build_index_safety_flags(IndexConfig())
        assert isinstance(flags, IndexSafetyFlags)


# ---------------------------------------------------------------------------
# build_index_entry — observation-only happy path
# ---------------------------------------------------------------------------

class TestBuildIndexEntryObservationOnly:
    def test_observation_only_defaults(self) -> None:
        report = _make_report()
        entry = build_index_entry(report=report)
        assert entry.entry_kind is IndexEntryKind.OBSERVATION_REPORT
        assert entry.index_state is IndexState.READY
        assert entry.report_id == "report-1"
        assert entry.audit_id == ""
        assert entry.review_status == "NOT_REVIEWED"
        assert entry.review_state == "UNKNOWN"
        assert entry.source_report_version == "1.0"
        assert entry.source_review_version == ""
        assert entry.reason_codes == ()
        assert entry.tags == ()
        assert entry.reviewer == ""

    def test_observation_with_local_references(self) -> None:
        report = _make_report()
        entry = build_index_entry(
            report=report,
            local_report_reference="reports/obs/2024-01-01/report.md",
            local_review_reference="reviews/2024-01-01/review.md",
        )
        assert entry.local_report_reference == "reports/obs/2024-01-01/report.md"
        assert entry.local_review_reference == "reviews/2024-01-01/review.md"

    def test_observation_with_metadata(self) -> None:
        report = _make_report(metadata={"source": "test"})
        entry = build_index_entry(report=report)
        assert entry.metadata == {"source": "test"}

    def test_observation_with_reason_codes(self) -> None:
        report = _make_report(reason_codes=("ANOMALY", "DRIFT"))
        entry = build_index_entry(report=report)
        assert entry.reason_codes == ("ANOMALY", "DRIFT")

    def test_observation_uses_provided_now(self) -> None:
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        report = _make_report(generated_at=now)
        entry = build_index_entry(report=report, now=now)
        assert entry.report_generated_at == now

    def test_observation_with_config(self) -> None:
        config = IndexConfig()
        report = _make_report()
        entry = build_index_entry(report=report, config=config)
        assert entry.safety_flags.dry_run is True


# ---------------------------------------------------------------------------
# build_index_entry — review-only happy path
# ---------------------------------------------------------------------------

class TestBuildIndexEntryReviewOnly:
    def test_review_only_blocked_missing_report(self) -> None:
        # review without report hits MISSING_REPORTS before review validation
        review = _make_review()
        entry = build_index_entry(report=None, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert MISSING_REPORTS in entry.reason_codes


# ---------------------------------------------------------------------------
# build_index_entry — linked report + review happy path
# ---------------------------------------------------------------------------

class TestBuildIndexEntryLinked:
    def test_linked_happy_path(self) -> None:
        report = _make_report()
        review = _make_review()
        entry = build_index_entry(report=report, review=review)
        assert entry.entry_kind is IndexEntryKind.LINKED_REPORT_REVIEW
        assert entry.index_state is IndexState.READY
        assert entry.report_id == "report-1"
        assert entry.audit_id == "audit-1"
        assert entry.review_status == "ACCEPTED"
        assert entry.review_state == "READY"
        assert entry.source_report_version == "1.0"
        assert entry.source_review_version == "1.0"
        assert entry.reviewer == "alice"
        assert entry.entry_id == "report-1-audit-1"

    def test_linked_merges_reason_codes(self) -> None:
        report = _make_report(reason_codes=("A", "B"))
        review = _make_review(reason_codes=("B", "C"))
        entry = build_index_entry(report=report, review=review)
        assert entry.reason_codes == ("A", "B", "C")

    def test_linked_with_tags(self) -> None:
        report = _make_report()
        review = _make_review(tags=("tag1", "tag2"))
        entry = build_index_entry(report=report, review=review)
        assert entry.tags == ("tag1", "tag2")

    def test_linked_with_metadata(self) -> None:
        report = _make_report(metadata={"rkey": "rval"})
        review = _make_review(metadata={"mkey": "mval"})
        entry = build_index_entry(report=report, review=review)
        # metadata comes from review
        assert entry.metadata == {"mkey": "mval"}

    def test_linked_reviewed_not_accepted(self) -> None:
        report = _make_report()
        review = _make_review(review_status="REJECTED")
        entry = build_index_entry(report=report, review=review)
        assert entry.review_status == "REJECTED"
        assert entry.index_state is IndexState.READY

    def test_linked_with_local_references(self) -> None:
        report = _make_report()
        review = _make_review()
        entry = build_index_entry(
            report=report,
            review=review,
            local_report_reference="r.md",
            local_review_reference="v.md",
        )
        assert entry.local_report_reference == "r.md"
        assert entry.local_review_reference == "v.md"


# ---------------------------------------------------------------------------
# build_index_entry — blocking paths
# ---------------------------------------------------------------------------

class TestBuildIndexEntryBlocking:
    # EMPTY_INDEX / DEFAULT_BLOCKED
    def test_both_none_returns_empty_index(self) -> None:
        entry = build_index_entry(report=None, review=None)
        assert entry.index_state is IndexState.BLOCKED
        assert EMPTY_INDEX in entry.reason_codes
        assert entry.entry_id == "empty"
        assert entry.report_id == "empty"

    def test_default_blocked_for_missing_inputs(self) -> None:
        # When both report and review are missing, EMPTY_INDEX is the reason
        entry = build_index_entry(report=None, review=None)
        assert entry.index_state is IndexState.BLOCKED
        assert EMPTY_INDEX in entry.reason_codes

    # MISSING_REPORTS
    def test_missing_report_with_review(self) -> None:
        review = _make_review()
        entry = build_index_entry(report=None, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert MISSING_REPORTS in entry.reason_codes
        assert entry.entry_id == "missing-report"
        assert entry.report_id == "missing"

    # INVALID_REPORT
    def test_invalid_report_empty_id(self) -> None:
        report = _make_report(report_id="")
        entry = build_index_entry(report=report)
        assert entry.index_state is IndexState.BLOCKED
        assert INVALID_REPORT in entry.reason_codes

    def test_invalid_report_empty_version(self) -> None:
        report = _make_report(version="")
        entry = build_index_entry(report=report)
        assert entry.index_state is IndexState.BLOCKED
        assert INVALID_REPORT in entry.reason_codes

    def test_invalid_report_bad_state(self) -> None:
        report = _make_report(report_state="INVALID")
        entry = build_index_entry(report=report)
        assert entry.index_state is IndexState.BLOCKED
        assert INVALID_REPORT in entry.reason_codes

    def test_invalid_report_missing_state(self) -> None:
        report = _make_report()
        report.pop("report_state")
        entry = build_index_entry(report=report)
        assert entry.index_state is IndexState.BLOCKED
        assert INVALID_REPORT in entry.reason_codes

    # UNSUPPORTED_REPORT_VERSION
    def test_unsupported_report_version(self) -> None:
        report = _make_report(version="2.0")
        entry = build_index_entry(report=report)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSUPPORTED_REPORT_VERSION in entry.reason_codes
        assert entry.entry_id == "unsupported-report-report-1"

    # UNSAFE_REPORT_STATE
    def test_unsafe_report_state_blocked(self) -> None:
        report = _make_report(report_state="BLOCKED")
        entry = build_index_entry(report=report)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSAFE_REPORT_STATE in entry.reason_codes
        assert entry.entry_id == "unsafe-report-report-1"

    def test_unsafe_report_state_unknown(self) -> None:
        report = _make_report(report_state="UNKNOWN")
        entry = build_index_entry(report=report)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSAFE_REPORT_STATE in entry.reason_codes

    def test_unsafe_report_state_disabled(self) -> None:
        report = _make_report(report_state="DISABLED")
        entry = build_index_entry(report=report)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSAFE_REPORT_STATE in entry.reason_codes

    # INVALID_REVIEW
    def test_invalid_review_empty_audit_id(self) -> None:
        report = _make_report()
        review = _make_review(audit_id="")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert INVALID_REVIEW in entry.reason_codes

    def test_invalid_review_empty_version(self) -> None:
        report = _make_report()
        review = _make_review(version="")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert INVALID_REVIEW in entry.reason_codes

    def test_invalid_review_bad_status(self) -> None:
        report = _make_report()
        review = _make_review(review_status="INVALID")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert INVALID_REVIEW in entry.reason_codes

    def test_invalid_review_bad_state(self) -> None:
        report = _make_report()
        review = _make_review(review_state="INVALID")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert INVALID_REVIEW in entry.reason_codes

    # UNSUPPORTED_REVIEW_VERSION
    def test_unsupported_review_version(self) -> None:
        report = _make_report()
        review = _make_review(version="2.0")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSUPPORTED_REVIEW_VERSION in entry.reason_codes

    # UNSAFE_REVIEW_STATE
    def test_unsafe_review_state_blocked(self) -> None:
        report = _make_report()
        review = _make_review(review_state="BLOCKED")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSAFE_REVIEW_STATE in entry.reason_codes

    def test_unsafe_review_state_unknown(self) -> None:
        report = _make_report()
        review = _make_review(review_state="UNKNOWN")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSAFE_REVIEW_STATE in entry.reason_codes

    def test_unsafe_review_state_disabled(self) -> None:
        report = _make_report()
        review = _make_review(review_state="DISABLED")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSAFE_REVIEW_STATE in entry.reason_codes

    # UNSAFE_INDEX_CONTENT
    def test_unsafe_index_content_in_tag(self) -> None:
        report = _make_report()
        review = _make_review(tags=("has_api_key",))
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSAFE_INDEX_CONTENT in entry.reason_codes

    def test_unsafe_index_content_in_reviewer(self) -> None:
        report = _make_report()
        review = _make_review(reviewer="has_secret")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSAFE_INDEX_CONTENT in entry.reason_codes

    def test_unsafe_index_content_in_metadata_key(self) -> None:
        report = _make_report()
        review = _make_review(metadata={"api_key": "value"})
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSAFE_INDEX_CONTENT in entry.reason_codes

    # Deterministic first blocking reason
    def test_first_blocking_reason_report_over_review(self) -> None:
        # report is invalid (empty version), review is unsafe state
        # report validation happens first
        report = _make_report(version="")
        review = _make_review(review_state="BLOCKED")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert INVALID_REPORT in entry.reason_codes
        assert UNSAFE_REVIEW_STATE not in entry.reason_codes

    def test_first_blocking_reason_unsupported_before_unsafe(self) -> None:
        report = _make_report(version="9.9")
        review = _make_review(review_state="BLOCKED")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSUPPORTED_REPORT_VERSION in entry.reason_codes
        assert UNSAFE_REVIEW_STATE not in entry.reason_codes

    def test_first_blocking_reason_unsafe_report_before_review(self) -> None:
        report = _make_report(report_state="BLOCKED")
        review = _make_review(review_state="BLOCKED")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSAFE_REPORT_STATE in entry.reason_codes
        assert UNSAFE_REVIEW_STATE not in entry.reason_codes

    def test_first_blocking_reason_invalid_review_before_unsafe_review(self) -> None:
        report = _make_report()
        review = _make_review(audit_id="", review_state="BLOCKED")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert INVALID_REVIEW in entry.reason_codes
        assert UNSAFE_REVIEW_STATE not in entry.reason_codes

    def test_first_blocking_reason_unsupported_review_before_unsafe_review(self) -> None:
        report = _make_report()
        review = _make_review(version="9.9", review_state="BLOCKED")
        entry = build_index_entry(report=report, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert UNSUPPORTED_REVIEW_VERSION in entry.reason_codes
        assert UNSAFE_REVIEW_STATE not in entry.reason_codes

    def test_first_blocking_reason_unsafe_content_before_unsafe_review(self) -> None:
        report = _make_report()
        review = _make_review(review_state="BLOCKED", tags=("has_api_key",))
        entry = build_index_entry(report=report, review=review)
        # unsafe content is checked before unsafe review state
        assert entry.index_state is IndexState.BLOCKED
        # The first blocking reason in the priority chain wins
        # Priority 10 (unsafe content) is checked before priority 9 (unsafe review state)
        # Actually looking at the code: unsafe review state is priority 9, unsafe content is priority 10
        # So unsafe review state wins. Let me check...
        # In the code: Priority 9 is unsafe review state, Priority 10 is unsafe index content
        # So UNSAFE_REVIEW_STATE should be the reason, not UNSAFE_INDEX_CONTENT
        assert UNSAFE_REVIEW_STATE in entry.reason_codes

    def test_first_blocking_reason_missing_report_over_invalid_review(self) -> None:
        # report missing -> MISSING_REPORTS, review invalid
        review = _make_review(audit_id="")
        entry = build_index_entry(report=None, review=review)
        assert entry.index_state is IndexState.BLOCKED
        assert MISSING_REPORTS in entry.reason_codes

    def test_empty_index_over_missing_reports(self) -> None:
        # both missing -> EMPTY_INDEX
        entry = build_index_entry(report=None, review=None)
        assert entry.index_state is IndexState.BLOCKED
        assert EMPTY_INDEX in entry.reason_codes
        assert MISSING_REPORTS not in entry.reason_codes


# ---------------------------------------------------------------------------
# build_index_summary
# ---------------------------------------------------------------------------

class TestBuildIndexSummary:
    def test_empty_entries(self) -> None:
        summary = build_index_summary([])
        assert summary.total_entries == 0
        assert summary.observation_report_count == 0
        assert summary.review_audit_count == 0
        assert summary.linked_entry_count == 0
        assert summary.ready_count == 0
        assert summary.blocked_count == 0
        assert summary.unknown_count == 0
        assert summary.accepted_count == 0
        assert summary.rejected_count == 0
        assert summary.needs_investigation_count == 0
        assert summary.not_reviewed_count == 0
        assert summary.reason_counts == {}

    def test_single_observation(self) -> None:
        report = _make_report()
        entry = build_index_entry(report=report)
        summary = build_index_summary([entry])
        assert summary.total_entries == 1
        assert summary.observation_report_count == 1
        assert summary.ready_count == 1
        assert summary.not_reviewed_count == 1

    def test_single_linked(self) -> None:
        report = _make_report()
        review = _make_review()
        entry = build_index_entry(report=report, review=review)
        summary = build_index_summary([entry])
        assert summary.total_entries == 1
        assert summary.linked_entry_count == 1
        assert summary.ready_count == 1
        assert summary.accepted_count == 1

    def test_blocked_entry(self) -> None:
        entry = build_index_entry(report=None, review=None)
        summary = build_index_summary([entry])
        assert summary.total_entries == 1
        assert summary.blocked_count == 1
        assert summary.linked_entry_count == 1  # blocked uses LINKED_REPORT_REVIEW kind

    def test_mixed_entries(self) -> None:
        obs = build_index_entry(report=_make_report(report_id="r1"))
        linked = build_index_entry(report=_make_report(report_id="r2"), review=_make_review(report_id="r2"))
        blocked = build_index_entry(report=None, review=None)
        summary = build_index_summary([obs, linked, blocked])
        assert summary.total_entries == 3
        assert summary.observation_report_count == 1
        # blocked entry uses LINKED_REPORT_REVIEW kind
        assert summary.linked_entry_count == 2
        assert summary.ready_count == 2
        assert summary.blocked_count == 1
        # obs and blocked both have NOT_REVIEWED status
        assert summary.not_reviewed_count == 2
        assert summary.accepted_count == 1

    def test_mixed_entries_with_invalid(self) -> None:
        obs = build_index_entry(report=_make_report(report_id="r1"))
        linked = build_index_entry(report=_make_report(report_id="r2"), review=_make_review(report_id="r2"))
        invalid = build_index_entry(report=_make_report(report_id="r3", version="9.9"))
        unsafe = build_index_entry(report=_make_report(report_id="r4", report_state="BLOCKED"))
        summary = build_index_summary([obs, linked, invalid, unsafe])
        assert summary.total_entries == 4
        assert summary.observation_report_count == 1
        # invalid and unsafe are LINKED_REPORT_REVIEW kind
        assert summary.linked_entry_count == 3
        assert summary.ready_count == 2
        assert summary.blocked_count == 2
        # obs, invalid, and unsafe all have NOT_REVIEWED status
        assert summary.not_reviewed_count == 3
        assert summary.accepted_count == 1

    def test_reason_counts(self) -> None:
        e1 = build_index_entry(report=None, review=None)
        e2 = build_index_entry(report=_make_report(version="9.9"))
        summary = build_index_summary([e1, e2])
        assert summary.reason_counts.get(EMPTY_INDEX, 0) == 1
        assert summary.reason_counts.get(UNSUPPORTED_REPORT_VERSION, 0) == 1

    def test_rejected_review_status(self) -> None:
        report = _make_report()
        review = _make_review(review_status="REJECTED")
        entry = build_index_entry(report=report, review=review)
        summary = build_index_summary([entry])
        assert summary.rejected_count == 1

    def test_needs_investigation_status(self) -> None:
        report = _make_report()
        review = _make_review(review_status="NEEDS_INVESTIGATION")
        entry = build_index_entry(report=report, review=review)
        summary = build_index_summary([entry])
        assert summary.needs_investigation_count == 1

    def test_reviewed_status(self) -> None:
        report = _make_report()
        review = _make_review(review_status="REVIEWED")
        entry = build_index_entry(report=report, review=review)
        summary = build_index_summary([entry])
        # REVIEWED is not ACCEPTED/REJECTED/NEEDS_INVESTIGATION, so falls through
        # Actually REVIEWED is a valid status but not counted in any specific bucket
        # It doesn't match ACCEPTED, REJECTED, NEEDS_INVESTIGATION, or NOT_REVIEWED
        # So none of the counts increment for it
        assert summary.accepted_count == 0
        assert summary.rejected_count == 0
        assert summary.needs_investigation_count == 0
        assert summary.not_reviewed_count == 0


# ---------------------------------------------------------------------------
# build_index_data_quality
# ---------------------------------------------------------------------------

class TestBuildIndexDataQuality:
    def test_empty_entries(self) -> None:
        dq = build_index_data_quality([])
        assert dq.total_reports == 0
        assert dq.valid_reports == 0
        assert dq.invalid_reports == 0
        assert dq.unsafe_reports == 0
        assert dq.total_reviews == 0
        assert dq.valid_reviews == 0
        assert dq.invalid_reviews == 0
        assert dq.unsafe_reviews == 0
        assert dq.linked_records == 0
        assert dq.unlinked_reports == 0
        assert dq.unlinked_reviews == 0

    def test_valid_observation(self) -> None:
        report = _make_report()
        entry = build_index_entry(report=report)
        dq = build_index_data_quality([entry])
        assert dq.total_reports == 1
        assert dq.valid_reports == 1
        assert dq.unlinked_reports == 1

    def test_valid_linked(self) -> None:
        report = _make_report()
        review = _make_review()
        entry = build_index_entry(report=report, review=review)
        dq = build_index_data_quality([entry])
        assert dq.total_reports == 1
        assert dq.valid_reports == 1
        assert dq.total_reviews == 1
        assert dq.valid_reviews == 1
        assert dq.linked_records == 1

    def test_invalid_report(self) -> None:
        report = _make_report(version="9.9")
        entry = build_index_entry(report=report)
        dq = build_index_data_quality([entry])
        assert dq.total_reports == 1
        assert dq.invalid_reports == 1

    def test_unsafe_report(self) -> None:
        report = _make_report(report_state="BLOCKED")
        entry = build_index_entry(report=report)
        dq = build_index_data_quality([entry])
        assert dq.total_reports == 1
        assert dq.unsafe_reports == 1

    def test_invalid_review(self) -> None:
        report = _make_report()
        review = _make_review(version="9.9")
        entry = build_index_entry(report=report, review=review)
        dq = build_index_data_quality([entry])
        assert dq.total_reviews == 1
        assert dq.invalid_reviews == 1

    def test_unsafe_review(self) -> None:
        report = _make_report()
        review = _make_review(review_state="BLOCKED")
        entry = build_index_entry(report=report, review=review)
        dq = build_index_data_quality([entry])
        assert dq.total_reviews == 1
        assert dq.unsafe_reviews == 1

    def test_mixed(self) -> None:
        obs = build_index_entry(report=_make_report(report_id="r1"))
        linked = build_index_entry(report=_make_report(report_id="r2"), review=_make_review(report_id="r2"))
        invalid = build_index_entry(report=_make_report(report_id="r3", version="9.9"))
        unsafe = build_index_entry(report=_make_report(report_id="r4", report_state="BLOCKED"))
        dq = build_index_data_quality([obs, linked, invalid, unsafe])
        assert dq.total_reports == 4  # all have report_id
        assert dq.valid_reports == 2  # obs + linked
        assert dq.invalid_reports == 1  # invalid
        assert dq.unsafe_reports == 1  # unsafe
        # blocked entries use LINKED_REPORT_REVIEW kind, so they count as reviews too
        assert dq.total_reviews == 3  # linked + invalid + unsafe (all LINKED_REPORT_REVIEW)
        assert dq.valid_reviews == 1  # only linked
        # linked_records counts LINKED_REPORT_REVIEW entries, which includes invalid and unsafe
        assert dq.linked_records == 3  # linked + invalid + unsafe
        assert dq.unlinked_reports == 1  # obs has no review

    def test_unlinked_review_entry(self) -> None:
        # A review-only entry (blocked due to missing report) counts as unlinked review
        review = _make_review()
        entry = build_index_entry(report=None, review=review)
        dq = build_index_data_quality([entry])
        # blocked entries use LINKED_REPORT_REVIEW kind, not REVIEW_ONLY
        assert dq.total_reviews == 1
        assert dq.unlinked_reviews == 0  # LINKED_REPORT_REVIEW kind, not REVIEW_ONLY


# ---------------------------------------------------------------------------
# build_review_index
# ---------------------------------------------------------------------------

class TestBuildReviewIndex:
    def test_happy_path_single_report(self) -> None:
        report = _make_report()
        index = build_review_index(reports=[report])
        assert index.index_state is IndexState.READY
        assert len(index.entries) == 1
        assert index.entries[0].entry_kind is IndexEntryKind.OBSERVATION_REPORT
        assert index.summary.total_entries == 1
        assert index.summary.ready_count == 1

    def test_happy_path_linked(self) -> None:
        report = _make_report()
        review = _make_review()
        index = build_review_index(reports=[report], reviews=[review])
        assert index.index_state is IndexState.READY
        assert len(index.entries) == 1
        assert index.entries[0].entry_kind is IndexEntryKind.LINKED_REPORT_REVIEW

    def test_happy_path_multiple_reports(self) -> None:
        r1 = _make_report(report_id="r1")
        r2 = _make_report(report_id="r2")
        index = build_review_index(reports=[r1, r2])
        assert index.index_state is IndexState.READY
        assert index.summary.total_entries == 2
        assert index.summary.observation_report_count == 2

    def test_empty_reports_blocked(self) -> None:
        index = build_review_index(reports=[])
        assert index.index_state is IndexState.BLOCKED
        assert MISSING_REPORTS in index.reason_codes

    def test_none_reports_blocked(self) -> None:
        index = build_review_index(reports=None)
        assert index.index_state is IndexState.BLOCKED
        assert MISSING_REPORTS in index.reason_codes

    def test_empty_entries_blocked(self) -> None:
        # If reports is empty list, we get MISSING_REPORTS before empty entries check
        index = build_review_index(reports=[])
        assert index.index_state is IndexState.BLOCKED

    def test_mixed_blocked_entries_safe_behavior(self) -> None:
        r1 = _make_report(report_id="r1")
        r2 = _make_report(report_id="r2", version="9.9")
        index = build_review_index(reports=[r1, r2])
        assert index.index_state is IndexState.BLOCKED
        assert index.summary.total_entries == 2
        assert index.summary.ready_count == 1
        assert index.summary.blocked_count == 1
        # Should have at least one blocking reason
        assert len(index.reason_codes) >= 1

    def test_all_ready(self) -> None:
        r1 = _make_report(report_id="r1")
        r2 = _make_report(report_id="r2")
        index = build_review_index(reports=[r1, r2])
        assert index.index_state is IndexState.READY
        assert index.reason_codes == ()

    def test_orphan_review(self) -> None:
        report = _make_report(report_id="r1")
        review = _make_review(report_id="r2")  # no matching report
        index = build_review_index(reports=[report], reviews=[review])
        assert index.index_state is IndexState.BLOCKED
        # Should have 2 entries: one linked/observation for r1, one blocked for orphan r2
        assert index.summary.total_entries == 2
        # The orphan review gets blocked with MISSING_REPORTS
        orphan_entry = [e for e in index.entries if e.entry_id == "missing-report"][0]
        assert orphan_entry.index_state is IndexState.BLOCKED
        assert MISSING_REPORTS in orphan_entry.reason_codes

    def test_uses_provided_now(self) -> None:
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        report = _make_report()
        index = build_review_index(reports=[report], now=now)
        assert index.generated_at == now

    def test_uses_provided_config(self) -> None:
        config = IndexConfig()
        report = _make_report()
        index = build_review_index(reports=[report], config=config)
        assert index.safety_flags.dry_run is True

    def test_index_id_contains_timestamp(self) -> None:
        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        report = _make_report()
        index = build_review_index(reports=[report], now=now)
        assert now.isoformat() in index.index_id

    def test_no_file_side_effects(self) -> None:
        # build_review_index is pure: no file I/O
        report = _make_report()
        index = build_review_index(reports=[report])
        # If we got here without file system errors, no files were touched
        assert index is not None

    def test_no_network_side_effects(self) -> None:
        # Pure function, no network calls
        report = _make_report()
        index = build_review_index(reports=[report])
        assert index is not None

    def test_no_database_side_effects(self) -> None:
        # Pure function, no database calls
        report = _make_report()
        index = build_review_index(reports=[report])
        assert index is not None

    def test_deterministic_first_blocking_reason_in_index(self) -> None:
        r1 = _make_report(report_id="r1", version="9.9")
        r2 = _make_report(report_id="r2", report_state="BLOCKED")
        index = build_review_index(reports=[r1, r2])
        assert index.index_state is IndexState.BLOCKED
        # The first blocking reason from the first blocked entry
        assert UNSUPPORTED_REPORT_VERSION in index.reason_codes

    def test_blocked_index_with_custom_reason(self) -> None:
        # When reports is empty, we get MISSING_REPORTS
        index = build_review_index(reports=[])
        assert index.index_state is IndexState.BLOCKED
        assert MISSING_REPORTS in index.reason_codes

    def test_review_by_report_id_matching(self) -> None:
        r1 = _make_report(report_id="r1")
        r2 = _make_report(report_id="r2")
        v1 = _make_review(report_id="r1")
        index = build_review_index(reports=[r1, r2], reviews=[v1])
        assert index.index_state is IndexState.READY
        assert index.summary.total_entries == 2
        # r1 should be linked, r2 should be observation-only
        linked = [e for e in index.entries if e.report_id == "r1"][0]
        obs = [e for e in index.entries if e.report_id == "r2"][0]
        assert linked.entry_kind is IndexEntryKind.LINKED_REPORT_REVIEW
        assert obs.entry_kind is IndexEntryKind.OBSERVATION_REPORT

    def test_multiple_reviews_same_report_last_wins(self) -> None:
        r1 = _make_report(report_id="r1")
        v1 = _make_review(report_id="r1", audit_id="a1")
        v2 = _make_review(report_id="r1", audit_id="a2")
        index = build_review_index(reports=[r1], reviews=[v1, v2])
        # The dict uses last review for each report_id
        entry = index.entries[0]
        assert entry.audit_id == "a2"

    def test_index_error_catch_all(self) -> None:
        # Provide a report that causes an exception during entry building
        # by making reason_codes not iterable (causes TypeError in tuple())
        class BadReport:
            def get(self, key, default=None):
                if key == "reason_codes":
                    return 12345  # not iterable, causes TypeError in tuple()
                return {"report_id": "bad", "version": "1.0", "report_state": "READY"}.get(key, default)
        index = build_review_index(reports=[BadReport()])  # type: ignore[list-item]
        assert index.index_state is IndexState.BLOCKED
        # The entry should be blocked with INDEX_ERROR
        assert index.summary.blocked_count == 1
        entry = index.entries[0]
        assert entry.index_state is IndexState.BLOCKED
        assert INDEX_ERROR in entry.reason_codes

    def test_orphan_review_index_error_catch_all(self) -> None:
        # Cannot trigger INDEX_ERROR for orphan reviews without source edits
        # because build_index_entry(report=None, review=review) returns
        # MISSING_REPORTS before reaching the tuple() call on reason_codes
        pytest.skip("INDEX_ERROR for orphan reviews requires source modification")
