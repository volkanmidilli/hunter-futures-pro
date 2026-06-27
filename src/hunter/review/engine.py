"""Review engine — deterministic, fail-closed operator review workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .models import (
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
    ReviewRecord,
    ReviewSafetyFlags,
    ReviewState,
    ReviewStatus,
    SHORTING_ENABLED,
    UNSAFE_REPORT_STATE,
    UNSAFE_REVIEW_CONTENT,
    UNSUPPORTED_REPORT_VERSION,
    FORBIDDEN_REVIEW_TERMS,
)


# ---------------------------------------------------------------------------
# Unsafe content detection
# ---------------------------------------------------------------------------

def has_unsafe_review_content(notes: str, tags: tuple[str, ...], metadata: Mapping[str, Any]) -> bool:
    """Return True if notes, tags, or metadata keys contain forbidden terms."""
    text = notes.lower()
    for tag in tags:
        text += " " + tag.lower()
    for key in metadata:
        text += " " + str(key).lower()
    for term in FORBIDDEN_REVIEW_TERMS:
        if term in text:
            return True
    return False


# ---------------------------------------------------------------------------
# Safety flags builder
# ---------------------------------------------------------------------------

def build_review_safety_flags(config: ReviewConfig) -> ReviewSafetyFlags:
    """Convert ReviewConfig into ReviewSafetyFlags preserving fail-closed values."""
    return ReviewSafetyFlags(
        dry_run=config.dry_run,
        live_trading_enabled=config.live_trading_enabled,
        real_orders_enabled=config.real_orders_enabled,
        leverage_enabled=config.leverage_enabled,
        shorting_enabled=config.shorting_enabled,
        report_feedback_into_execution=config.allow_report_feedback_into_execution,
        operator_feedback_into_execution=config.allow_operator_feedback_into_execution,
        network_calls_enabled=False,
        database_persistence_enabled=False,
    )


# ---------------------------------------------------------------------------
# Review record builder
# ---------------------------------------------------------------------------

def build_review_record(
    report: Mapping[str, Any] | None,
    review_status: ReviewStatus,
    reviewer: str,
    notes: str = "",
    tags: tuple[str, ...] = (),
    metadata: Mapping[str, Any] = {},
    config: ReviewConfig | None = None,
    now: datetime | None = None,
) -> ReviewRecord:
    """Build a ReviewRecord from an observation report payload.

    Fail-closed: returns a BLOCKED record on the first blocking reason.
    Priority order (1-13):
      1. missing input          -> MISSING_REPORT
      2. invalid input          -> INVALID_REPORT
      3. unsupported version    -> UNSUPPORTED_REPORT_VERSION
      4. unsafe report_state    -> UNSAFE_REPORT_STATE
      5. dry_run not true       -> DRY_RUN_DISABLED
      6. live_trading enabled   -> LIVE_TRADING_ENABLED
      7. real_orders enabled    -> REAL_ORDERS_ENABLED
      8. leverage enabled       -> LEVERAGE_ENABLED
      9. shorting enabled       -> SHORTING_ENABLED
      10. missing reviewer      -> MISSING_REVIEWER
      11. invalid review status -> INVALID_REVIEW_STATUS
      12. unsafe content        -> UNSAFE_REVIEW_CONTENT
      13. exception             -> REVIEW_ERROR
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if config is None:
        config = ReviewConfig()

    safety_flags = build_review_safety_flags(config)

    try:
        # Priority 1: missing input
        if report is None:
            return ReviewRecord.blocked(
                reason_codes=(MISSING_REPORT,),
                now=now,
            )

        # Priority 2: invalid input (missing required fields)
        if not isinstance(report, Mapping):
            return ReviewRecord.blocked(
                reason_codes=(INVALID_REPORT,),
                now=now,
            )
        required_fields = ("version", "report_state")
        if not all(field in report for field in required_fields):
            return ReviewRecord.blocked(
                reason_codes=(INVALID_REPORT,),
                now=now,
            )

        # Priority 3: unsupported version
        report_version = report.get("version", "")
        if report_version != config.input_version:
            return ReviewRecord.blocked(
                reason_codes=(UNSUPPORTED_REPORT_VERSION,),
                now=now,
            )

        # Priority 4: unsafe report_state
        report_state = report.get("report_state", "")
        if report_state in ("BLOCKED", "UNKNOWN", "DISABLED"):
            return ReviewRecord.blocked(
                reason_codes=(UNSAFE_REPORT_STATE,),
                now=now,
            )

        # Priority 5: dry_run
        if report.get("dry_run", True) is not True:
            return ReviewRecord.blocked(
                reason_codes=(DRY_RUN_DISABLED,),
                now=now,
            )

        # Priority 6: live_trading_enabled
        if report.get("live_trading_enabled", False) is not False:
            return ReviewRecord.blocked(
                reason_codes=(LIVE_TRADING_ENABLED,),
                now=now,
            )

        # Priority 7: real_orders_enabled
        if report.get("real_orders_enabled", False) is not False:
            return ReviewRecord.blocked(
                reason_codes=(REAL_ORDERS_ENABLED,),
                now=now,
            )

        # Priority 8: leverage_enabled
        if report.get("leverage_enabled", False) is not False:
            return ReviewRecord.blocked(
                reason_codes=(LEVERAGE_ENABLED,),
                now=now,
            )

        # Priority 9: shorting_enabled
        if report.get("shorting_enabled", False) is not False:
            return ReviewRecord.blocked(
                reason_codes=(SHORTING_ENABLED,),
                now=now,
            )

        # Priority 10: missing reviewer for reviewed statuses
        if review_status is not ReviewStatus.NOT_REVIEWED and (not reviewer or not isinstance(reviewer, str)):
            return ReviewRecord.blocked(
                reason_codes=(MISSING_REVIEWER,),
                now=now,
            )

        # Priority 11: invalid review status
        if not isinstance(review_status, ReviewStatus):
            return ReviewRecord.blocked(
                reason_codes=(INVALID_REVIEW_STATUS,),
                now=now,
            )

        # Priority 12: unsafe content (notes, tags, metadata)
        if has_unsafe_review_content(notes, tags, metadata):
            return ReviewRecord.blocked(
                reason_codes=(UNSAFE_REVIEW_CONTENT,),
                now=now,
            )

        # All checks passed — build the record
        report_id = report.get("report_id", "unknown")
        report_version = report.get("version", config.input_version)

        if review_status is ReviewStatus.NOT_REVIEWED:
            reason_codes = ()
        else:
            reason_codes = (str(review_status.value),)

        return ReviewRecord(
            review_id=f"review-{now.isoformat()}",
            source_report_id=report_id,
            source_report_version=report_version,
            review_state=ReviewState.READY,
            review_status=review_status,
            reviewer=reviewer,
            notes=notes,
            tags=tags,
            reason_codes=reason_codes,
            reviewed_at=now,
            safety_flags=safety_flags,
            metadata=metadata,
        )

    except Exception:
        # Priority 13: catch-all
        return ReviewRecord.blocked(
            reason_codes=(REVIEW_ERROR,),
            now=now,
        )


# ---------------------------------------------------------------------------
# Audit summary builder
# ---------------------------------------------------------------------------

def build_review_audit_summary(records: Iterable[ReviewRecord]) -> ReviewAuditSummary:
    """Aggregate review records into a deterministic summary."""
    total = 0
    accepted = 0
    rejected = 0
    needs_investigation = 0
    not_reviewed = 0
    blocked = 0
    unknown = 0
    reason_counts: dict[str, int] = {}

    for record in records:
        total += 1

        # blocked records are NOT_REVIEWED, so they don't count as reviewed
        if record.review_state is ReviewState.READY:
            if record.review_status is ReviewStatus.REVIEWED:
                not_reviewed += 1  # REVIEWED counts as not_reviewed for summary
            elif record.review_status is ReviewStatus.ACCEPTED:
                accepted += 1
            elif record.review_status is ReviewStatus.REJECTED:
                rejected += 1
            elif record.review_status is ReviewStatus.NEEDS_INVESTIGATION:
                needs_investigation += 1
            elif record.review_status is ReviewStatus.NOT_REVIEWED:
                not_reviewed += 1
        elif record.review_state is ReviewState.BLOCKED:
            blocked += 1
            not_reviewed += 1
        elif record.review_state is ReviewState.UNKNOWN:
            unknown += 1
            not_reviewed += 1

        for reason in record.reason_codes:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    return ReviewAuditSummary(
        total_reviews=total,
        accepted_count=accepted,
        rejected_count=rejected,
        needs_investigation_count=needs_investigation,
        not_reviewed_count=not_reviewed,
        blocked_count=blocked,
        unknown_count=unknown,
        reason_counts=reason_counts,
    )


# ---------------------------------------------------------------------------
# Data quality builder
# ---------------------------------------------------------------------------

def build_review_data_quality(records: Iterable[ReviewRecord]) -> ReviewDataQuality:
    """Build data quality metrics from review records."""
    total = 0
    valid = 0
    blocked = 0
    unknown = 0
    unsafe = 0
    missing = 0
    invalid = 0

    for record in records:
        total += 1
        if record.review_state is ReviewState.READY:
            valid += 1
        elif record.review_state is ReviewState.BLOCKED:
            blocked += 1
        elif record.review_state is ReviewState.UNKNOWN:
            unknown += 1

        # Only count reason codes for blocked records to avoid double counting
        if record.review_state is ReviewState.BLOCKED:
            for reason in record.reason_codes:
                if reason == MISSING_REPORT:
                    missing += 1
                elif reason == INVALID_REPORT:
                    invalid += 1
                elif reason == UNSAFE_REPORT_STATE:
                    unsafe += 1

    return ReviewDataQuality(
        total_reports=total,
        valid_reports=valid,
        blocked_reports=blocked,
        unknown_reports=unknown,
        unsafe_reports=unsafe,
        missing_reports=missing,
        invalid_reports=invalid,
    )


# ---------------------------------------------------------------------------
# Audit record builder
# ---------------------------------------------------------------------------

def build_review_audit_record(
    records: Iterable[ReviewRecord],
    config: ReviewConfig | None = None,
    now: datetime | None = None,
) -> ReviewAuditRecord:
    """Build a ReviewAuditRecord from review records.

    Empty records -> BLOCKED audit with DEFAULT_BLOCKED.
    Mixed blocked/unknown -> BLOCKED audit.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if config is None:
        config = ReviewConfig()

    records_tuple = tuple(records)
    summary = build_review_audit_summary(records_tuple)
    data_quality = build_review_data_quality(records_tuple)
    safety_flags = build_review_safety_flags(config)

    if not records_tuple:
        return ReviewAuditRecord.blocked(
            reason_codes=(DEFAULT_BLOCKED,),
            audit_id="empty-audit",
            records=(),
            now=now,
        )

    # Determine audit state
    all_ready = all(r.review_state is ReviewState.READY for r in records_tuple)
    any_blocked = any(r.review_state is ReviewState.BLOCKED for r in records_tuple)

    if all_ready:
        audit_state = ReviewState.READY
        reason_codes = ()
    elif any_blocked:
        audit_state = ReviewState.BLOCKED
        reason_codes = (DEFAULT_BLOCKED,)
    else:
        audit_state = ReviewState.UNKNOWN
        reason_codes = (DEFAULT_BLOCKED,)

    return ReviewAuditRecord(
        audit_id=f"audit-{now.isoformat()}",
        generated_at=now,
        audit_state=audit_state,
        records=records_tuple,
        summary=summary,
        data_quality=data_quality,
        reason_codes=reason_codes,
        safety_flags=safety_flags,
    )
