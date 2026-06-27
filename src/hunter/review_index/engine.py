"""Index engine for hunter.review_index package.

In-memory functions for building index entries, summaries, data quality,
and full review indices. No file I/O, no network, no database.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from .models import (
    DEFAULT_BLOCKED,
    EMPTY_INDEX,
    FORBIDDEN_INDEX_TERMS,
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
# Unsafe content detection
# ---------------------------------------------------------------------------

def has_unsafe_index_content(text: str) -> bool:
    """Case-insensitive check for forbidden terms in index text.

    Does not open, traverse, validate, follow, or execute file references.
    """
    if not text:
        return False
    lower = text.lower()
    return any(term in lower for term in FORBIDDEN_INDEX_TERMS)


# ---------------------------------------------------------------------------
# Safety flags builder
# ---------------------------------------------------------------------------

def build_index_safety_flags(config: IndexConfig) -> IndexSafetyFlags:
    """Convert config into safety flags."""
    return IndexSafetyFlags(
        dry_run=config.dry_run,
        live_trading_enabled=config.live_trading_enabled,
        real_orders_enabled=config.real_orders_enabled,
        leverage_enabled=config.leverage_enabled,
        shorting_enabled=config.shorting_enabled,
        report_feedback_into_execution=config.allow_report_feedback_into_execution,
        operator_feedback_into_execution=config.allow_operator_feedback_into_execution,
        index_feedback_into_execution=config.allow_index_feedback_into_execution,
        file_reference_traversal_enabled=config.allow_file_reference_traversal,
        database_persistence_enabled=config.allow_database_persistence,
        web_ui_enabled=config.allow_web_ui,
        dashboard_enabled=config.allow_dashboard,
    )


# ---------------------------------------------------------------------------
# Index entry builder
# ---------------------------------------------------------------------------

def build_index_entry(
    report: Mapping[str, Any] | None = None,
    review: Mapping[str, Any] | None = None,
    config: IndexConfig | None = None,
    local_report_reference: str = "",
    local_review_reference: str = "",
    now: datetime | None = None,
) -> IndexEntry:
    """Build a single IndexEntry from a report and optional review.

    Fail-closed with deterministic first blocking reason.
    Does not repair, infer, upgrade, or normalize missing/unsafe inputs.
    File references are strings only; not traversed/validated/opened/followed/executed.
    """
    if config is None:
        config = IndexConfig()

    if now is None:
        now = datetime.now(timezone.utc)

    safety_flags = build_index_safety_flags(config)

    # Priority 1: both missing -> EMPTY_INDEX
    if report is None and review is None:
        return IndexEntry.blocked(
            entry_id="empty",
            report_id="empty",
            reason_codes=(EMPTY_INDEX,),
            safety_flags=safety_flags,
        )

    # Priority 2: report missing -> MISSING_REPORTS
    if report is None:
        return IndexEntry.blocked(
            entry_id="missing-report",
            report_id="missing",
            reason_codes=(MISSING_REPORTS,),
            safety_flags=safety_flags,
        )

    # Priority 3: report invalid
    report_id = report.get("report_id", "")
    report_version = report.get("version", "")
    report_state = report.get("report_state", "")
    report_generated_at = report.get("generated_at")
    if not report_id or not report_version or report_state not in ("DISABLED", "READY", "BLOCKED", "UNKNOWN"):
        return IndexEntry.blocked(
            entry_id="invalid-report",
            report_id=report_id or "invalid",
            reason_codes=(INVALID_REPORT,),
            safety_flags=safety_flags,
        )

    # Priority 4: unsupported report version
    if report_version != config.observation_report_version:
        return IndexEntry.blocked(
            entry_id=f"unsupported-report-{report_id}",
            report_id=report_id,
            reason_codes=(UNSUPPORTED_REPORT_VERSION,),
            safety_flags=safety_flags,
        )

    # Priority 5: unsafe report state
    if report_state in ("BLOCKED", "UNKNOWN", "DISABLED"):
        return IndexEntry.blocked(
            entry_id=f"unsafe-report-{report_id}",
            report_id=report_id,
            reason_codes=(UNSAFE_REPORT_STATE,),
            safety_flags=safety_flags,
        )

    # Priority 6: review missing -> MISSING_REVIEWS (warning, not blocking for report-only)
    # Priority 7: review invalid
    if review is not None:
        audit_id = review.get("audit_id", "")
        review_version = review.get("version", "")
        review_status = review.get("review_status", "")
        review_state = review.get("review_state", "")
        reviewed_at = review.get("reviewed_at")
        reviewer = review.get("reviewer", "")
        tags = review.get("tags", ())
        metadata = review.get("metadata", {})

        if not audit_id or not review_version or review_status not in (
            "NOT_REVIEWED", "REVIEWED", "ACCEPTED", "REJECTED", "NEEDS_INVESTIGATION"
        ) or review_state not in ("DISABLED", "READY", "BLOCKED", "UNKNOWN"):
            return IndexEntry.blocked(
                entry_id=f"invalid-review-{report_id}",
                report_id=report_id,
                reason_codes=(INVALID_REVIEW,),
                safety_flags=safety_flags,
            )

        # Priority 8: unsupported review version
        if review_version != config.review_audit_version:
            return IndexEntry.blocked(
                entry_id=f"unsupported-review-{report_id}",
                report_id=report_id,
                reason_codes=(UNSUPPORTED_REVIEW_VERSION,),
                safety_flags=safety_flags,
            )

        # Priority 9: unsafe review state
        if review_state in ("BLOCKED", "UNKNOWN", "DISABLED"):
            return IndexEntry.blocked(
                entry_id=f"unsafe-review-{report_id}",
                report_id=report_id,
                reason_codes=(UNSAFE_REVIEW_STATE,),
                safety_flags=safety_flags,
            )

        # Priority 10: unsafe index content
        for tag in tags:
            if has_unsafe_index_content(tag):
                return IndexEntry.blocked(
                    entry_id=f"unsafe-content-{report_id}",
                    report_id=report_id,
                    reason_codes=(UNSAFE_INDEX_CONTENT,),
                    safety_flags=safety_flags,
                )
        if has_unsafe_index_content(reviewer):
            return IndexEntry.blocked(
                entry_id=f"unsafe-content-{report_id}",
                report_id=report_id,
                reason_codes=(UNSAFE_INDEX_CONTENT,),
                safety_flags=safety_flags,
            )
        for key in metadata:
            if has_unsafe_index_content(key):
                return IndexEntry.blocked(
                    entry_id=f"unsafe-content-{report_id}",
                    report_id=report_id,
                    reason_codes=(UNSAFE_INDEX_CONTENT,),
                    safety_flags=safety_flags,
                )

        # Build linked entry
        entry_kind = IndexEntryKind.LINKED_REPORT_REVIEW
        report_reasons = report.get("reason_codes", ())
        review_reasons = review.get("reason_codes", ())
        merged_reasons = tuple(dict.fromkeys((*report_reasons, *review_reasons)))

        return IndexEntry(
            entry_id=f"{report_id}-{audit_id}",
            entry_kind=entry_kind,
            index_state=IndexState.READY,
            report_id=report_id,
            audit_id=audit_id,
            report_generated_at=report_generated_at,
            audit_generated_at=review.get("generated_at"),
            reviewed_at=reviewed_at,
            review_status=review_status,
            review_state=review_state,
            source_report_version=report_version,
            source_review_version=review_version,
            reason_codes=merged_reasons,
            tags=tuple(tags) if isinstance(tags, (list, tuple)) else (),
            reviewer=reviewer,
            local_report_reference=local_report_reference,
            local_review_reference=local_review_reference,
            safety_flags=safety_flags,
            metadata=dict(metadata) if metadata else {},
        )

    # Report only (no review)
    return IndexEntry(
        entry_id=report_id,
        entry_kind=IndexEntryKind.OBSERVATION_REPORT,
        index_state=IndexState.READY,
        report_id=report_id,
        audit_id="",
        report_generated_at=report_generated_at,
        audit_generated_at=None,
        reviewed_at=None,
        review_status="NOT_REVIEWED",
        review_state="UNKNOWN",
        source_report_version=report_version,
        source_review_version="",
        reason_codes=tuple(report.get("reason_codes", ())),
        tags=(),
        reviewer="",
        local_report_reference=local_report_reference,
        local_review_reference=local_review_reference,
        safety_flags=safety_flags,
        metadata=dict(report.get("metadata", {})) if report.get("metadata") else {},
    )


# ---------------------------------------------------------------------------
# Index summary builder
# ---------------------------------------------------------------------------

def build_index_summary(entries: Iterable[IndexEntry]) -> IndexSummary:
    """Aggregate counts across all index entries."""
    total = 0
    obs_count = 0
    review_count = 0
    linked_count = 0
    ready_count = 0
    blocked_count = 0
    unknown_count = 0
    accepted_count = 0
    rejected_count = 0
    needs_inv_count = 0
    not_reviewed_count = 0
    reason_counts: dict[str, int] = {}

    for entry in entries:
        total += 1
        if entry.entry_kind is IndexEntryKind.OBSERVATION_REPORT:
            obs_count += 1
        elif entry.entry_kind is IndexEntryKind.REVIEW_AUDIT_RECORD:
            review_count += 1
        elif entry.entry_kind is IndexEntryKind.LINKED_REPORT_REVIEW:
            linked_count += 1

        if entry.index_state is IndexState.READY:
            ready_count += 1
        elif entry.index_state is IndexState.BLOCKED:
            blocked_count += 1
        elif entry.index_state is IndexState.UNKNOWN:
            unknown_count += 1

        if entry.review_status == "ACCEPTED":
            accepted_count += 1
        elif entry.review_status == "REJECTED":
            rejected_count += 1
        elif entry.review_status == "NEEDS_INVESTIGATION":
            needs_inv_count += 1
        elif entry.review_status == "NOT_REVIEWED":
            not_reviewed_count += 1

        for rc in entry.reason_codes:
            reason_counts[rc] = reason_counts.get(rc, 0) + 1

    return IndexSummary(
        total_entries=total,
        observation_report_count=obs_count,
        review_audit_count=review_count,
        linked_entry_count=linked_count,
        ready_count=ready_count,
        blocked_count=blocked_count,
        unknown_count=unknown_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        needs_investigation_count=needs_inv_count,
        not_reviewed_count=not_reviewed_count,
        reason_counts=reason_counts,
    )


# ---------------------------------------------------------------------------
# Index data quality builder
# ---------------------------------------------------------------------------

def build_index_data_quality(
    entries: Iterable[IndexEntry],
) -> IndexDataQuality:
    """Assess index completeness and quality from entries.

    Missing/invalid/unsafe inputs are summarized as BLOCKED/UNKNOWN/INVALID
    in data quality, not repaired, inferred, upgraded, or normalized.
    """
    total_reports = 0
    valid_reports = 0
    invalid_reports = 0
    unsafe_reports = 0
    total_reviews = 0
    valid_reviews = 0
    invalid_reviews = 0
    unsafe_reviews = 0
    linked_records = 0
    unlinked_reports = 0
    unlinked_reviews = 0

    for entry in entries:
        if entry.entry_kind in (IndexEntryKind.OBSERVATION_REPORT, IndexEntryKind.LINKED_REPORT_REVIEW):
            total_reports += 1
            if entry.index_state is IndexState.READY:
                valid_reports += 1
            elif entry.index_state is IndexState.BLOCKED:
                if any(rc in (INVALID_REPORT, UNSUPPORTED_REPORT_VERSION) for rc in entry.reason_codes):
                    invalid_reports += 1
                elif any(rc == UNSAFE_REPORT_STATE for rc in entry.reason_codes):
                    unsafe_reports += 1

        if entry.entry_kind in (IndexEntryKind.REVIEW_AUDIT_RECORD, IndexEntryKind.LINKED_REPORT_REVIEW):
            total_reviews += 1
            if entry.index_state is IndexState.READY:
                valid_reviews += 1
            elif entry.index_state is IndexState.BLOCKED:
                if any(rc in (INVALID_REVIEW, UNSUPPORTED_REVIEW_VERSION) for rc in entry.reason_codes):
                    invalid_reviews += 1
                elif any(rc == UNSAFE_REVIEW_STATE for rc in entry.reason_codes):
                    unsafe_reviews += 1

        if entry.entry_kind is IndexEntryKind.LINKED_REPORT_REVIEW:
            linked_records += 1
        elif entry.entry_kind is IndexEntryKind.OBSERVATION_REPORT:
            unlinked_reports += 1
        elif entry.entry_kind is IndexEntryKind.REVIEW_AUDIT_RECORD:
            unlinked_reviews += 1

    return IndexDataQuality(
        total_reports=total_reports,
        valid_reports=valid_reports,
        invalid_reports=invalid_reports,
        unsafe_reports=unsafe_reports,
        total_reviews=total_reviews,
        valid_reviews=valid_reviews,
        invalid_reviews=invalid_reviews,
        unsafe_reviews=unsafe_reviews,
        linked_records=linked_records,
        unlinked_reports=unlinked_reports,
        unlinked_reviews=unlinked_reviews,
    )


# ---------------------------------------------------------------------------
# Full review index builder
# ---------------------------------------------------------------------------

def build_review_index(
    reports: Iterable[Mapping[str, Any]] | None = None,
    reviews: Iterable[Mapping[str, Any]] | None = None,
    config: IndexConfig | None = None,
    now: datetime | None = None,
) -> ReviewIndex:
    """Build full ReviewIndex from reports and optional reviews.

    Fail-closed: empty or invalid inputs produce blocked index.
    Never triggers action. Never feeds output into execution paths.
    """
    if config is None:
        config = IndexConfig()
    if now is None:
        now = datetime.now(timezone.utc)

    safety_flags = build_index_safety_flags(config)

    # Priority 1: missing reports
    reports_list = list(reports) if reports is not None else []
    if not reports_list:
        return ReviewIndex.blocked(
            index_id="missing-reports",
            generated_at=now,
            reason_codes=(MISSING_REPORTS,),
            safety_flags=safety_flags,
        )

    # Build entries
    reviews_list = list(reviews) if reviews is not None else []
    review_by_report: dict[str, Mapping[str, Any]] = {}
    for review in reviews_list:
        report_id = review.get("report_id", "")
        if report_id:
            review_by_report[report_id] = review

    entries: list[IndexEntry] = []
    for report in reports_list:
        report_id = report.get("report_id", "")
        review = review_by_report.get(report_id)
        try:
            entry = build_index_entry(
                report=report,
                review=review,
                config=config,
                now=now,
            )
            entries.append(entry)
        except Exception:
            # Catch-all: produce blocked entry for this report
            entries.append(
                IndexEntry.blocked(
                    entry_id=f"error-{report_id}",
                    report_id=report_id or "error",
                    reason_codes=(INDEX_ERROR,),
                    safety_flags=safety_flags,
                )
            )

    # Handle orphan reviews (reviews without matching reports)
    report_ids = {r.get("report_id", "") for r in reports_list}
    for review in reviews_list:
        report_id = review.get("report_id", "")
        if report_id and report_id not in report_ids:
            try:
                entry = build_index_entry(
                    report=None,
                    review=review,
                    config=config,
                    now=now,
                )
                entries.append(entry)
            except Exception:
                entries.append(
                    IndexEntry.blocked(
                        entry_id=f"error-orphan-{report_id}",
                        report_id=report_id or "error",
                        reason_codes=(INDEX_ERROR,),
                        safety_flags=safety_flags,
                    )
                )

    # Empty entries -> blocked
    if not entries:
        return ReviewIndex.blocked(
            index_id="empty",
            generated_at=now,
            reason_codes=(EMPTY_INDEX,),
            safety_flags=safety_flags,
        )

    summary = build_index_summary(entries)
    data_quality = build_index_data_quality(entries)

    # Determine overall index state
    if all(e.index_state is IndexState.READY for e in entries):
        index_state = IndexState.READY
        reason_codes: tuple[str, ...] = ()
    elif any(e.index_state is IndexState.BLOCKED for e in entries):
        index_state = IndexState.BLOCKED
        # Collect first blocking reason from each blocked entry
        reasons: list[str] = []
        for e in entries:
            if e.index_state is IndexState.BLOCKED and e.reason_codes:
                reasons.append(e.reason_codes[0])
        reason_codes = tuple(dict.fromkeys(reasons)) if reasons else (DEFAULT_BLOCKED,)
    else:
        index_state = IndexState.UNKNOWN
        reason_codes = (DEFAULT_BLOCKED,)

    return ReviewIndex(
        index_id=f"index-{now.isoformat()}",
        generated_at=now,
        index_state=index_state,
        entries=tuple(entries),
        summary=summary,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
    )
