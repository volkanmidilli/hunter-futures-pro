"""Integration tests for hunter.review — end-to-end flow from observation report to audit output."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.review.engine import (
    build_review_audit_record,
    build_review_record,
    build_review_safety_flags,
)
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
    SHORTING_ENABLED,
    UNSAFE_REPORT_STATE,
    UNSAFE_REVIEW_CONTENT,
    UNSUPPORTED_REPORT_VERSION,
    ReviewAuditRecord,
    ReviewConfig,
    ReviewRecord,
    ReviewState,
    ReviewStatus,
)
from hunter.review.writer import (
    atomic_write_json_review_audit_record,
    atomic_write_markdown_review_audit_record,
    review_audit_record_to_dict,
    review_audit_record_to_markdown,
    write_review_audit_records,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)


def _safe_report(
    report_state: str = "READY",
    version: str = "1.0",
    dry_run: bool = True,
    live_trading_enabled: bool = False,
    real_orders_enabled: bool = False,
    leverage_enabled: bool = False,
    shorting_enabled: bool = False,
) -> dict:
    return {
        "report_id": "report-001",
        "version": version,
        "report_state": report_state,
        "reported_at": "2026-06-18T12:00:00Z",
        "dry_run": dry_run,
        "live_trading_enabled": live_trading_enabled,
        "real_orders_enabled": real_orders_enabled,
        "leverage_enabled": leverage_enabled,
        "shorting_enabled": shorting_enabled,
        "report_feedback_into_execution": False,
        "operator_feedback_into_execution": False,
        "network_calls_enabled": False,
        "database_persistence_enabled": False,
    }


def _build_accepted_record(report: dict | None = None, reviewer: str = "operator-1") -> ReviewRecord:
    config = ReviewConfig()
    safety_flags = build_review_safety_flags(config)
    return build_review_record(
        report or _safe_report(),
        review_status=ReviewStatus.ACCEPTED,
        reviewer=reviewer,
        notes="Looks good",
        tags=("accepted",),
        config=config,
    )


def _build_rejected_record(report: dict | None = None, reviewer: str = "operator-1") -> ReviewRecord:
    config = ReviewConfig()
    safety_flags = build_review_safety_flags(config)
    return build_review_record(
        report or _safe_report(),
        review_status=ReviewStatus.REJECTED,
        reviewer=reviewer,
        notes="Rejected",
        tags=("rejected",),
        config=config,
    )


def _build_needs_investigation_record(report: dict | None = None, reviewer: str = "operator-1") -> ReviewRecord:
    config = ReviewConfig()
    safety_flags = build_review_safety_flags(config)
    return build_review_record(
        report or _safe_report(),
        review_status=ReviewStatus.NEEDS_INVESTIGATION,
        reviewer=reviewer,
        notes="Needs more info",
        tags=("investigate",),
        config=config,
    )


def _build_not_reviewed_record(report: dict | None = None) -> ReviewRecord:
    config = ReviewConfig()
    safety_flags = build_review_safety_flags(config)
    return build_review_record(
        report or _safe_report(),
        review_status=ReviewStatus.NOT_REVIEWED,
        reviewer="",
        notes="",
        tags=(),
        config=config,
    )


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

class TestAcceptedReviewHappyPath:
    def test_accepted_record_state(self):
        record = _build_accepted_record()
        assert record.review_state is ReviewState.READY
        assert record.review_status is ReviewStatus.ACCEPTED
        assert record.reason_codes == (ReviewStatus.ACCEPTED,)

    def test_accepted_audit_record(self):
        record = _build_accepted_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        assert audit.audit_state is ReviewState.READY
        assert audit.summary.accepted_count == 1
        assert audit.summary.total_reviews == 1

    def test_accepted_json_output(self, tmp_path):
        record = _build_accepted_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        json_path = tmp_path / "audit.json"
        atomic_write_json_review_audit_record(audit, json_path)
        d = review_audit_record_to_dict(audit)
        assert d["audit_state"] == "READY"
        assert d["summary"]["accepted_count"] == 1
        assert len(d["records"]) == 1

    def test_accepted_markdown_output(self, tmp_path):
        record = _build_accepted_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        md_path = tmp_path / "audit.md"
        atomic_write_markdown_review_audit_record(audit, md_path)
        md = review_audit_record_to_markdown(audit)
        assert "human-audit artifact" in md.lower()
        assert "not a trading signal" in md.lower()


class TestRejectedReviewHappyPath:
    def test_rejected_record_state(self):
        record = _build_rejected_record()
        assert record.review_state is ReviewState.READY
        assert record.review_status is ReviewStatus.REJECTED
        assert record.reason_codes == (ReviewStatus.REJECTED,)

    def test_rejected_audit_record(self):
        record = _build_rejected_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        assert audit.audit_state is ReviewState.READY
        assert audit.summary.rejected_count == 1


class TestNeedsInvestigationHappyPath:
    def test_needs_investigation_record_state(self):
        record = _build_needs_investigation_record()
        assert record.review_state is ReviewState.READY
        assert record.review_status is ReviewStatus.NEEDS_INVESTIGATION
        assert record.reason_codes == (ReviewStatus.NEEDS_INVESTIGATION,)

    def test_needs_investigation_audit_record(self):
        record = _build_needs_investigation_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        assert audit.audit_state is ReviewState.READY
        assert audit.summary.needs_investigation_count == 1


class TestNotReviewedPath:
    def test_not_reviewed_record_state(self):
        record = _build_not_reviewed_record()
        assert record.review_state is ReviewState.READY
        assert record.review_status is ReviewStatus.NOT_REVIEWED
        assert record.reason_codes == ()

    def test_not_reviewed_audit_record(self):
        record = _build_not_reviewed_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        assert audit.audit_state is ReviewState.READY
        assert audit.summary.not_reviewed_count == 1


# ---------------------------------------------------------------------------
# Blocking / fail-closed paths
# ---------------------------------------------------------------------------

class TestMissingReport:
    def test_missing_report_record(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        record = build_review_record(
            None,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (MISSING_REPORT,)

    def test_missing_report_audit(self, tmp_path):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        record = build_review_record(
            None,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        assert audit.audit_state is ReviewState.BLOCKED
        json_path, md_path = write_review_audit_records(audit, tmp_path / "audit.json", tmp_path / "audit.md")
        assert json_path.exists()
        assert md_path.exists()


class TestInvalidReportMissingVersion:
    def test_invalid_report_missing_version(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report()
        del report["version"]
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (INVALID_REPORT,)


class TestInvalidReportMissingState:
    def test_invalid_report_missing_state(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report()
        del report["report_state"]
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (INVALID_REPORT,)


class TestUnsupportedReportVersion:
    def test_unsupported_version(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report(version="2.0")
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (UNSUPPORTED_REPORT_VERSION,)


class TestUnsafeReportStateBlocked:
    def test_blocked_report_state(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report(report_state="BLOCKED")
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (UNSAFE_REPORT_STATE,)

    def test_unknown_report_state(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report(report_state="UNKNOWN")
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (UNSAFE_REPORT_STATE,)

    def test_disabled_report_state(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report(report_state="DISABLED")
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (UNSAFE_REPORT_STATE,)


class TestSafetyFlagBlocking:
    def test_dry_run_disabled(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report(dry_run=False)
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (DRY_RUN_DISABLED,)

    def test_live_trading_enabled(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report(live_trading_enabled=True)
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (LIVE_TRADING_ENABLED,)

    def test_real_orders_enabled(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report(real_orders_enabled=True)
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (REAL_ORDERS_ENABLED,)

    def test_leverage_enabled(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report(leverage_enabled=True)
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (LEVERAGE_ENABLED,)

    def test_shorting_enabled(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report(shorting_enabled=True)
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (SHORTING_ENABLED,)


class TestMissingReviewer:
    def test_missing_reviewer_accepted(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report()
        record = build_review_record(
            report,
            review_status=ReviewStatus.ACCEPTED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (MISSING_REVIEWER,)

    def test_missing_reviewer_rejected(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report()
        record = build_review_record(
            report,
            review_status=ReviewStatus.REJECTED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (MISSING_REVIEWER,)

    def test_missing_reviewer_needs_investigation(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report()
        record = build_review_record(
            report,
            review_status=ReviewStatus.NEEDS_INVESTIGATION,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (MISSING_REVIEWER,)

    def test_not_reviewed_allows_empty_reviewer(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report()
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.READY
        assert record.reason_codes == ()


class TestUnsafeReviewContent:
    def test_notes_with_forbidden_term(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report()
        record = build_review_record(
            report,
            review_status=ReviewStatus.REVIEWED,
            reviewer="operator-1",
            notes="This contains a password secret",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (UNSAFE_REVIEW_CONTENT,)

    def test_tags_with_forbidden_term(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report()
        record = build_review_record(
            report,
            review_status=ReviewStatus.REVIEWED,
            reviewer="operator-1",
            notes="",
            tags=("api_key",),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (UNSAFE_REVIEW_CONTENT,)

    def test_metadata_with_forbidden_key(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report()
        record = build_review_record(
            report,
            review_status=ReviewStatus.REVIEWED,
            reviewer="operator-1",
            notes="",
            tags=(),
            config=config,
            metadata={"api_key": "secret123"},
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (UNSAFE_REVIEW_CONTENT,)


class TestDeterministicFirstBlockingReason:
    def test_first_reason_only_missing_over_invalid(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        record = build_review_record(
            None,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (MISSING_REPORT,)

    def test_unsafe_state_over_safety_flags(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        report = _safe_report(report_state="BLOCKED", live_trading_enabled=True)
        record = build_review_record(
            report,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        assert record.review_state is ReviewState.BLOCKED
        assert record.reason_codes == (UNSAFE_REPORT_STATE,)


# ---------------------------------------------------------------------------
# Audit record scenarios
# ---------------------------------------------------------------------------

class TestMixedAuditRecord:
    def test_mixed_records_summary(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        accepted = _build_accepted_record()
        rejected = _build_rejected_record()
        needs_inv = _build_needs_investigation_record()
        not_reviewed = _build_not_reviewed_record()
        blocked = build_review_record(
            _safe_report(report_state="BLOCKED"),
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        audit = build_review_audit_record(
            records=(accepted, rejected, needs_inv, not_reviewed, blocked),
            config=config,
            now=_now(),
        )
        assert audit.summary.accepted_count == 1
        assert audit.summary.rejected_count == 1
        assert audit.summary.needs_investigation_count == 1
        assert audit.summary.not_reviewed_count == 2
        assert audit.summary.blocked_count == 1
        assert audit.summary.total_reviews == 5

    def test_mixed_audit_state_blocked(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        blocked = build_review_record(
            _safe_report(report_state="BLOCKED"),
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer="",
            notes="",
            tags=(),
            config=config,
        )
        audit = build_review_audit_record(
            records=(blocked,),
            config=config,
            now=_now(),
        )
        assert audit.audit_state is ReviewState.BLOCKED


class TestEmptyAuditRecord:
    def test_empty_records_blocked(self):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(),
            config=config,
            now=_now(),
        )
        assert audit.audit_state is ReviewState.BLOCKED
        assert audit.reason_codes == (DEFAULT_BLOCKED,)


# ---------------------------------------------------------------------------
# Writer integration
# ---------------------------------------------------------------------------

class TestWriterIntegration:
    def test_json_contains_nested_records(self, tmp_path):
        record = _build_accepted_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        json_path = tmp_path / "audit.json"
        atomic_write_json_review_audit_record(audit, json_path)
        d = review_audit_record_to_dict(audit)
        assert "records" in d
        assert "summary" in d
        assert "data_quality" in d
        assert "reason_codes" in d
        assert "safety_flags" in d

    def test_markdown_safety_notice(self, tmp_path):
        record = _build_accepted_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        md_path = tmp_path / "audit.md"
        atomic_write_markdown_review_audit_record(audit, md_path)
        md = review_audit_record_to_markdown(audit)
        assert "human-audit artifact" in md.lower()
        assert "not a trading signal" in md.lower()
        assert "not trade approval" in md.lower()
        assert "must not be consumed" in md.lower()

    def test_combined_writer(self, tmp_path):
        record = _build_accepted_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        json_path, md_path = write_review_audit_records(audit, tmp_path / "audit.json", tmp_path / "audit.md")
        assert json_path.exists()
        assert md_path.exists()

    def test_blocked_audit_written(self, tmp_path):
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(),
            config=config,
            now=_now(),
        )
        assert audit.audit_state is ReviewState.BLOCKED
        json_path, md_path = write_review_audit_records(audit, tmp_path / "audit.json", tmp_path / "audit.md")
        assert json_path.exists()
        assert md_path.exists()


# ---------------------------------------------------------------------------
# Safety assertions
# ---------------------------------------------------------------------------

class TestIntegrationSafety:
    def test_no_production_paths_written(self, tmp_path):
        record = _build_accepted_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        json_path, md_path = write_review_audit_records(audit, tmp_path / "audit.json", tmp_path / "audit.md")
        assert str(json_path).startswith(str(tmp_path))
        assert str(md_path).startswith(str(tmp_path))

    def test_no_config_yaml(self):
        assert not Path("config.yaml").exists()

    def test_no_json_schema(self):
        assert not Path("schema.json").exists()

    def test_no_freqtrade_import(self):
        import hunter.review.engine as engine_module
        import hunter.review.writer as writer_module
        for mod in (engine_module, writer_module):
            source = mod.__loader__.get_source(mod.__name__) if hasattr(mod.__loader__, "get_source") else ""
            lines = source.splitlines()
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    assert "freqtrade" not in stripped.lower(), f"freqtrade import in {mod.__name__}: {stripped}"

    def test_no_live_trading(self):
        config = ReviewConfig()
        assert config.live_trading_enabled is False

    def test_no_real_orders(self):
        config = ReviewConfig()
        assert config.real_orders_enabled is False

    def test_no_leverage(self):
        config = ReviewConfig()
        assert config.leverage_enabled is False

    def test_no_shorting(self):
        config = ReviewConfig()
        assert config.shorting_enabled is False

    def test_no_report_feedback(self):
        config = ReviewConfig()
        assert config.allow_report_feedback_into_execution is False

    def test_no_operator_feedback(self):
        config = ReviewConfig()
        assert config.allow_operator_feedback_into_execution is False

    def test_no_api_keys_in_output(self, tmp_path):
        record = _build_accepted_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        d = review_audit_record_to_dict(audit)
        text = str(d).lower()
        assert "api_key" not in text
        assert "secret" not in text
        assert "password" not in text
        assert "token" not in text

    def test_no_executable_instructions_in_markdown(self, tmp_path):
        record = _build_accepted_record()
        config = ReviewConfig()
        safety_flags = build_review_safety_flags(config)
        audit = build_review_audit_record(
            records=(record,),
            config=config,
            now=_now(),
        )
        md = review_audit_record_to_markdown(audit)
        assert "execute" not in md.lower() or "execution" in md.lower()
        assert "buy" not in md.lower()
        assert "sell" not in md.lower()
