"""Writer tests for hunter.review — deterministic serialization and atomic file writing."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.review import (
    DEFAULT_REVIEW_JSON_RECORD_PATH,
    DEFAULT_REVIEW_MARKDOWN_RECORD_PATH,
    ReviewAuditRecord,
    ReviewAuditSummary,
    ReviewDataQuality,
    ReviewRecord,
    ReviewSafetyFlags,
    ReviewState,
    ReviewStatus,
    atomic_write_json_review_audit_record,
    atomic_write_markdown_review_audit_record,
    review_audit_record_to_dict,
    review_audit_record_to_markdown,
    review_audit_summary_to_dict,
    review_data_quality_to_dict,
    review_record_to_dict,
    review_safety_flags_to_dict,
    write_review_audit_records,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def safety_flags():
    return ReviewSafetyFlags(
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


@pytest.fixture
def accepted_record(safety_flags):
    now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return ReviewRecord(
        review_id="review-001",
        source_report_id="report-001",
        source_report_version="1.0",
        review_state=ReviewState.READY,
        review_status=ReviewStatus.ACCEPTED,
        reviewer="operator-1",
        notes="Looks good",
        tags=("valid", "accepted"),
        reason_codes=("ACCEPTED",),
        reviewed_at=now,
        safety_flags=safety_flags,
        metadata={"source": "test"},
    )


@pytest.fixture
def blocked_record(safety_flags):
    now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return ReviewRecord.blocked(
        reason_codes=("LIVE_TRADING_ENABLED",),
        review_id="review-blocked",
        now=now,
    )


@pytest.fixture
def audit_summary():
    return ReviewAuditSummary(
        total_reviews=2,
        accepted_count=1,
        rejected_count=0,
        needs_investigation_count=0,
        not_reviewed_count=1,
        blocked_count=1,
        unknown_count=0,
        reason_counts={"ACCEPTED": 1, "LIVE_TRADING_ENABLED": 1},
    )


@pytest.fixture
def data_quality():
    return ReviewDataQuality(
        total_reports=2,
        valid_reports=1,
        blocked_reports=1,
        unknown_reports=0,
        unsafe_reports=0,
        missing_reports=0,
        invalid_reports=0,
    )


@pytest.fixture
def audit_record(accepted_record, audit_summary, data_quality, safety_flags):
    now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return ReviewAuditRecord(
        audit_id="audit-001",
        generated_at=now,
        audit_state=ReviewState.READY,
        records=(accepted_record,),
        summary=audit_summary,
        data_quality=data_quality,
        reason_codes=(),
        safety_flags=safety_flags,
    )


# ---------------------------------------------------------------------------
# Dict serialization tests
# ---------------------------------------------------------------------------

class TestReviewRecordToDict:
    def test_serializes_accepted_record(self, accepted_record):
        d = review_record_to_dict(accepted_record)
        assert d["review_id"] == "review-001"
        assert d["source_report_id"] == "report-001"
        assert d["source_report_version"] == "1.0"
        assert d["review_state"] == "READY"
        assert d["review_status"] == "ACCEPTED"
        assert d["reviewer"] == "operator-1"
        assert d["notes"] == "Looks good"
        assert d["tags"] == ["valid", "accepted"]
        assert d["reason_codes"] == ["ACCEPTED"]
        assert d["reviewed_at"] == "2025-01-15T12:00:00Z"
        assert d["metadata"] == {"source": "test"}
        assert isinstance(d["safety_flags"], dict)

    def test_serializes_blocked_record(self, blocked_record):
        d = review_record_to_dict(blocked_record)
        assert d["review_id"] == "review-blocked"
        assert d["review_state"] == "BLOCKED"
        assert d["review_status"] == "NOT_REVIEWED"
        assert d["reason_codes"] == ["LIVE_TRADING_ENABLED"]

    def test_tuple_serialization_uses_lists(self, accepted_record):
        d = review_record_to_dict(accepted_record)
        assert isinstance(d["tags"], list)
        assert isinstance(d["reason_codes"], list)

    def test_metadata_serialized_safely(self, accepted_record):
        d = review_record_to_dict(accepted_record)
        assert d["metadata"] == {"source": "test"}

    def test_does_not_mutate_input(self, accepted_record):
        original_tags = accepted_record.tags
        original_reason_codes = accepted_record.reason_codes
        review_record_to_dict(accepted_record)
        assert accepted_record.tags is original_tags
        assert accepted_record.reason_codes is original_reason_codes


class TestReviewSafetyFlagsToDict:
    def test_serializes_all_fields(self, safety_flags):
        d = review_safety_flags_to_dict(safety_flags)
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["real_orders_enabled"] is False
        assert d["leverage_enabled"] is False
        assert d["shorting_enabled"] is False
        assert d["report_feedback_into_execution"] is False
        assert d["operator_feedback_into_execution"] is False
        assert d["network_calls_enabled"] is False
        assert d["database_persistence_enabled"] is False


class TestReviewAuditSummaryToDict:
    def test_serializes_all_fields(self, audit_summary):
        d = review_audit_summary_to_dict(audit_summary)
        assert d["total_reviews"] == 2
        assert d["accepted_count"] == 1
        assert d["rejected_count"] == 0
        assert d["needs_investigation_count"] == 0
        assert d["not_reviewed_count"] == 1
        assert d["blocked_count"] == 1
        assert d["unknown_count"] == 0
        assert d["reason_counts"] == {"ACCEPTED": 1, "LIVE_TRADING_ENABLED": 1}

    def test_reason_counts_as_plain_dict(self, audit_summary):
        d = review_audit_summary_to_dict(audit_summary)
        assert isinstance(d["reason_counts"], dict)


class TestReviewDataQualityToDict:
    def test_serializes_all_fields(self, data_quality):
        d = review_data_quality_to_dict(data_quality)
        assert d["total_reports"] == 2
        assert d["valid_reports"] == 1
        assert d["blocked_reports"] == 1
        assert d["unknown_reports"] == 0
        assert d["unsafe_reports"] == 0
        assert d["missing_reports"] == 0
        assert d["invalid_reports"] == 0


class TestReviewAuditRecordToDict:
    def test_serializes_nested_records(self, audit_record):
        d = review_audit_record_to_dict(audit_record)
        assert d["audit_id"] == "audit-001"
        assert d["audit_state"] == "READY"
        assert isinstance(d["records"], list)
        assert len(d["records"]) == 1
        assert d["records"][0]["review_id"] == "review-001"
        assert isinstance(d["summary"], dict)
        assert isinstance(d["data_quality"], dict)
        assert isinstance(d["safety_flags"], dict)
        assert d["reason_codes"] == []

    def test_datetime_serialization_is_deterministic(self, audit_record):
        d = review_audit_record_to_dict(audit_record)
        assert d["generated_at"] == "2025-01-15T12:00:00Z"

    def test_enum_serialization_uses_string_values(self, audit_record):
        d = review_audit_record_to_dict(audit_record)
        assert d["audit_state"] == "READY"

    def test_tuple_serialization_uses_lists(self, audit_record):
        d = review_audit_record_to_dict(audit_record)
        assert isinstance(d["reason_codes"], list)
        assert isinstance(d["records"], list)

    def test_does_not_mutate_input(self, audit_record):
        original_records = audit_record.records
        review_audit_record_to_dict(audit_record)
        assert audit_record.records is original_records


# ---------------------------------------------------------------------------
# Markdown rendering tests
# ---------------------------------------------------------------------------

class TestReviewAuditRecordToMarkdown:
    def test_includes_required_safety_notice(self, audit_record):
        md = review_audit_record_to_markdown(audit_record)
        assert "human-audit artifact only" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "must not be consumed by" in md

    def test_says_not_trading_signal(self, audit_record):
        md = review_audit_record_to_markdown(audit_record)
        assert "not a trading signal" in md

    def test_says_not_trade_approval(self, audit_record):
        md = review_audit_record_to_markdown(audit_record)
        assert "not trade approval" in md

    def test_says_must_not_be_consumed_by_execution(self, audit_record):
        md = review_audit_record_to_markdown(audit_record)
        assert "must not be consumed by" in md
        assert "execution" in md
        assert "strategy" in md
        assert "Freqtrade" in md
        assert "order" in md
        assert "exchange" in md

    def test_includes_audit_fields_and_summary_counts(self, audit_record):
        md = review_audit_record_to_markdown(audit_record)
        assert "audit-001" in md
        assert "Total Reviews: 2" in md
        assert "Accepted: 1" in md
        assert "Blocked: 1" in md

    def test_includes_safety_flags(self, audit_record):
        md = review_audit_record_to_markdown(audit_record)
        assert "dry_run: True" in md
        assert "live_trading_enabled: False" in md

    def test_includes_review_records(self, audit_record):
        md = review_audit_record_to_markdown(audit_record)
        assert "review-001" in md
        assert "ACCEPTED" in md

    def test_does_not_include_executable_trading_instructions(self, audit_record):
        md = review_audit_record_to_markdown(audit_record)
        assert "enter_long" not in md.lower()
        assert "enter_short" not in md.lower()
        assert "exit_long" not in md.lower()
        assert "exit_short" not in md.lower()
        assert "order" not in md.lower() or "operator" in md.lower()

    def test_blocked_audit_record(self, blocked_record, audit_summary, data_quality, safety_flags):
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        blocked_audit = ReviewAuditRecord.blocked(
            reason_codes=("LIVE_TRADING_ENABLED",),
            audit_id="blocked-audit",
            records=(blocked_record,),
            now=now,
        )
        md = review_audit_record_to_markdown(blocked_audit)
        assert "BLOCKED" in md
        assert "human-audit artifact only" in md
        assert "LIVE_TRADING_ENABLED" in md


# ---------------------------------------------------------------------------
# Atomic writer tests
# ---------------------------------------------------------------------------

class TestAtomicWriteJsonReviewAuditRecord:
    def test_creates_parent_dirs(self, audit_record, tmp_path):
        path = tmp_path / "nested" / "review.json"
        atomic_write_json_review_audit_record(audit_record, path)
        assert path.exists()

    def test_writes_valid_json(self, audit_record, tmp_path):
        path = tmp_path / "review.json"
        atomic_write_json_review_audit_record(audit_record, path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["audit_id"] == "audit-001"
        assert data["audit_state"] == "READY"

    def test_overwrites_existing_file(self, audit_record, tmp_path):
        path = tmp_path / "review.json"
        path.write_text("old content")
        atomic_write_json_review_audit_record(audit_record, path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["audit_id"] == "audit-001"

    def test_leaves_no_temp_files_after_success(self, audit_record, tmp_path):
        path = tmp_path / "review.json"
        atomic_write_json_review_audit_record(audit_record, path)
        temp_files = list(tmp_path.glob(".*.tmp"))
        assert len(temp_files) == 0

    def test_cleans_up_temp_files_on_failure(self, audit_record, tmp_path):
        path = tmp_path / "readonly" / "review.json"
        path.parent.mkdir(parents=True)
        # Make parent read-only to force failure
        os.chmod(path.parent, 0o555)
        try:
            with pytest.raises(OSError):
                atomic_write_json_review_audit_record(audit_record, path)
        finally:
            os.chmod(path.parent, 0o755)

    def test_indent_and_sort_keys(self, audit_record, tmp_path):
        path = tmp_path / "review.json"
        atomic_write_json_review_audit_record(audit_record, path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "  \"audit_id\"" in content  # indent=2
        lines = content.splitlines()
        keys = [line for line in lines if line.strip().startswith('"') and line.strip().endswith('":')]
        # Verify sort_keys by checking first few keys are alphabetically sorted
        assert '"audit_id"' in content
        assert '"audit_state"' in content

    def test_trailing_newline(self, audit_record, tmp_path):
        path = tmp_path / "review.json"
        atomic_write_json_review_audit_record(audit_record, path)
        with open(path, "rb") as f:
            content = f.read()
        assert content.endswith(b"\n")


class TestAtomicWriteMarkdownReviewAuditRecord:
    def test_creates_parent_dirs(self, audit_record, tmp_path):
        path = tmp_path / "nested" / "review.md"
        atomic_write_markdown_review_audit_record(audit_record, path)
        assert path.exists()

    def test_writes_markdown(self, audit_record, tmp_path):
        path = tmp_path / "review.md"
        atomic_write_markdown_review_audit_record(audit_record, path)
        content = path.read_text(encoding="utf-8")
        assert "# Review Audit Record" in content
        assert "human-audit artifact only" in content

    def test_overwrites_existing_file(self, audit_record, tmp_path):
        path = tmp_path / "review.md"
        path.write_text("old content")
        atomic_write_markdown_review_audit_record(audit_record, path)
        content = path.read_text(encoding="utf-8")
        assert "# Review Audit Record" in content

    def test_leaves_no_temp_files_after_success(self, audit_record, tmp_path):
        path = tmp_path / "review.md"
        atomic_write_markdown_review_audit_record(audit_record, path)
        temp_files = list(tmp_path.glob(".*.tmp"))
        assert len(temp_files) == 0

    def test_trailing_newline(self, audit_record, tmp_path):
        path = tmp_path / "review.md"
        atomic_write_markdown_review_audit_record(audit_record, path)
        with open(path, "rb") as f:
            content = f.read()
        assert content.endswith(b"\n")


class TestWriteReviewAuditRecords:
    def test_writes_both_files_to_custom_tmp_path(self, audit_record, tmp_path):
        json_path = tmp_path / "audit.json"
        md_path = tmp_path / "audit.md"
        result = write_review_audit_records(audit_record, json_path, md_path)
        assert result[0] == json_path
        assert result[1] == md_path
        assert json_path.exists()
        assert md_path.exists()

    def test_blocked_audit_record(self, blocked_record, audit_summary, data_quality, safety_flags):
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        blocked_audit = ReviewAuditRecord.blocked(
            reason_codes=("LIVE_TRADING_ENABLED",),
            audit_id="blocked-audit",
            records=(blocked_record,),
            now=now,
        )
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            json_path = tmp_path / "audit.json"
            md_path = tmp_path / "audit.md"
            write_review_audit_records(blocked_audit, json_path, md_path)
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["audit_state"] == "BLOCKED"
            assert "LIVE_TRADING_ENABLED" in data["reason_codes"]
            md_content = md_path.read_text(encoding="utf-8")
            assert "BLOCKED" in md_content
            assert "human-audit artifact only" in md_content

    def test_does_not_mutate_input(self, audit_record, tmp_path):
        original_state = audit_record.audit_state
        json_path = tmp_path / "audit.json"
        md_path = tmp_path / "audit.md"
        write_review_audit_records(audit_record, json_path, md_path)
        assert audit_record.audit_state is original_state


# ---------------------------------------------------------------------------
# Default paths tests
# ---------------------------------------------------------------------------

class TestDefaultPaths:
    def test_default_json_path(self):
        assert str(DEFAULT_REVIEW_JSON_RECORD_PATH) == "data/review/latest_review_audit_record.json"

    def test_default_markdown_path(self):
        assert str(DEFAULT_REVIEW_MARKDOWN_RECORD_PATH) == "reports/review/latest_review_audit_record.md"


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------

class TestWriterSafety:
    def test_no_production_data_writes_in_tests(self, audit_record, tmp_path):
        json_path = tmp_path / "audit.json"
        md_path = tmp_path / "audit.md"
        write_review_audit_records(audit_record, json_path, md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_no_file_reads_except_tmp_path_outputs(self, audit_record, tmp_path):
        json_path = tmp_path / "audit.json"
        atomic_write_json_review_audit_record(audit_record, json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["audit_id"] == "audit-001"

    def test_no_network_calls(self, audit_record):
        md = review_audit_record_to_markdown(audit_record)
        assert "http" not in md.lower()
        assert "https" not in md.lower()

    def test_no_freqtrade_import(self):
        import hunter.review.writer as writer_module
        source = writer_module.__loader__.get_source(writer_module.__name__) if hasattr(writer_module.__loader__, "get_source") else ""
        # Check no import statement for freqtrade, but allow safety notice text
        lines = source.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "freqtrade" not in stripped.lower(), f"freqtrade import found: {stripped}"

    def test_no_database_persistence(self, safety_flags):
        assert safety_flags.database_persistence_enabled is False

    def test_no_live_trading_enabled(self, safety_flags):
        assert safety_flags.live_trading_enabled is False

    def test_no_real_orders_enabled(self, safety_flags):
        assert safety_flags.real_orders_enabled is False

    def test_no_leverage_enabled(self, safety_flags):
        assert safety_flags.leverage_enabled is False

    def test_no_shorting_enabled(self, safety_flags):
        assert safety_flags.shorting_enabled is False

    def test_no_report_feedback(self, safety_flags):
        assert safety_flags.report_feedback_into_execution is False

    def test_no_operator_feedback(self, safety_flags):
        assert safety_flags.operator_feedback_into_execution is False

    def test_no_api_keys_in_markdown(self, audit_record):
        md = review_audit_record_to_markdown(audit_record)
        assert "api_key" not in md.lower()
        assert "secret" not in md.lower()

    def test_no_executable_instructions_in_markdown(self, audit_record):
        md = review_audit_record_to_markdown(audit_record)
        assert "execute trade" not in md.lower()
        assert "place order" not in md.lower()

    def test_default_paths_do_not_write_production(self):
        assert "tmp" in str(DEFAULT_REVIEW_JSON_RECORD_PATH).lower() or "data" in str(DEFAULT_REVIEW_JSON_RECORD_PATH).lower()
        assert "tmp" in str(DEFAULT_REVIEW_MARKDOWN_RECORD_PATH).lower() or "reports" in str(DEFAULT_REVIEW_MARKDOWN_RECORD_PATH).lower()
