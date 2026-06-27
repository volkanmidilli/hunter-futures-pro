"""Review models — frozen dataclasses and enums for MVP-11 operator review workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReviewStatus(str, Enum):
    NOT_REVIEWED = "NOT_REVIEWED"
    REVIEWED = "REVIEWED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NEEDS_INVESTIGATION = "NEEDS_INVESTIGATION"


class ReviewState(str, Enum):
    DISABLED = "DISABLED"
    READY = "READY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class ReviewOutputFormat(str, Enum):
    JSON = "JSON"
    MARKDOWN = "MARKDOWN"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

MISSING_REPORT = "MISSING_REPORT"
INVALID_REPORT = "INVALID_REPORT"
UNSUPPORTED_REPORT_VERSION = "UNSUPPORTED_REPORT_VERSION"
UNSAFE_REPORT_STATE = "UNSAFE_REPORT_STATE"
DRY_RUN_DISABLED = "DRY_RUN_DISABLED"
LIVE_TRADING_ENABLED = "LIVE_TRADING_ENABLED"
REAL_ORDERS_ENABLED = "REAL_ORDERS_ENABLED"
LEVERAGE_ENABLED = "LEVERAGE_ENABLED"
SHORTING_ENABLED = "SHORTING_ENABLED"
MISSING_REVIEWER = "MISSING_REVIEWER"
INVALID_REVIEW_STATUS = "INVALID_REVIEW_STATUS"
UNSAFE_REVIEW_CONTENT = "UNSAFE_REVIEW_CONTENT"
REVIEW_ERROR = "REVIEW_ERROR"
DEFAULT_BLOCKED = "DEFAULT_BLOCKED"

REASON_CODES = (
    MISSING_REPORT,
    INVALID_REPORT,
    UNSUPPORTED_REPORT_VERSION,
    UNSAFE_REPORT_STATE,
    DRY_RUN_DISABLED,
    LIVE_TRADING_ENABLED,
    REAL_ORDERS_ENABLED,
    LEVERAGE_ENABLED,
    SHORTING_ENABLED,
    MISSING_REVIEWER,
    INVALID_REVIEW_STATUS,
    UNSAFE_REVIEW_CONTENT,
    REVIEW_ERROR,
    DEFAULT_BLOCKED,
)


# ---------------------------------------------------------------------------
# Forbidden content
# ---------------------------------------------------------------------------

FORBIDDEN_REVIEW_TERMS = frozenset({
    "api_key",
    "secret",
    "exchange_credentials",
    "executable_instructions",
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
    "order",
    "leverage",
    "shorting",
    "binance",
    "exchange",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReviewConfig:
    input_version: str = "1.0"
    max_report_age_seconds: int = 3600
    enable_json_output: bool = True
    enable_markdown_output: bool = True
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    allow_report_feedback_into_execution: bool = False
    allow_operator_feedback_into_execution: bool = False

    def __post_init__(self) -> None:
        if not self.input_version or not isinstance(self.input_version, str):
            raise ValueError("input_version must be a non-empty string")
        if self.max_report_age_seconds <= 0:
            raise ValueError("max_report_age_seconds must be > 0")
        if not self.enable_json_output and not self.enable_markdown_output:
            raise ValueError("at least one output format must be enabled")
        if not self.dry_run:
            raise ValueError("dry_run must be True")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False")
        if self.allow_report_feedback_into_execution:
            raise ValueError("allow_report_feedback_into_execution must be False")
        if self.allow_operator_feedback_into_execution:
            raise ValueError("allow_operator_feedback_into_execution must be False")


@dataclass(frozen=True)
class ReviewSafetyFlags:
    dry_run: bool
    live_trading_enabled: bool
    real_orders_enabled: bool
    leverage_enabled: bool
    shorting_enabled: bool
    report_feedback_into_execution: bool
    operator_feedback_into_execution: bool
    network_calls_enabled: bool = False
    database_persistence_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.dry_run:
            raise ValueError("dry_run must be True")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False")
        if self.report_feedback_into_execution:
            raise ValueError("report_feedback_into_execution must be False")
        if self.operator_feedback_into_execution:
            raise ValueError("operator_feedback_into_execution must be False")
        if self.network_calls_enabled:
            raise ValueError("network_calls_enabled must be False")
        if self.database_persistence_enabled:
            raise ValueError("database_persistence_enabled must be False")


@dataclass(frozen=True)
class ReviewRecord:
    review_id: str
    source_report_id: str
    source_report_version: str
    review_state: ReviewState
    review_status: ReviewStatus
    reviewer: str
    notes: str
    tags: tuple[str, ...]
    reason_codes: tuple[str, ...]
    reviewed_at: datetime
    safety_flags: ReviewSafetyFlags
    metadata: Mapping[str, Any] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.review_id or not isinstance(self.review_id, str):
            raise ValueError("review_id must be a non-empty string")
        if not self.source_report_id or not isinstance(self.source_report_id, str):
            raise ValueError("source_report_id must be a non-empty string")
        if not self.source_report_version or not isinstance(self.source_report_version, str):
            raise ValueError("source_report_version must be a non-empty string")
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        if self.review_status is not ReviewStatus.NOT_REVIEWED:
            if not self.reviewer or not isinstance(self.reviewer, str):
                raise ValueError("reviewer must be a non-empty string when review_status is not NOT_REVIEWED")
        if self.review_state is not ReviewState.READY:
            if self.review_status not in (ReviewStatus.NOT_REVIEWED, ReviewStatus.NEEDS_INVESTIGATION):
                raise ValueError(
                    f"review_status must be NOT_REVIEWED or NEEDS_INVESTIGATION when review_state is not READY, got {self.review_status}"
                )
        if self.review_status is not ReviewStatus.NOT_REVIEWED:
            if not self.reason_codes:
                raise ValueError("reason_codes must be non-empty when review_status is not NOT_REVIEWED")
        # Forbidden content check
        _check_forbidden_content(self.notes, "notes")
        for tag in self.tags:
            _check_forbidden_content(tag, "tags")
        for key in self.metadata:
            _check_forbidden_content(key, "metadata keys")

    @classmethod
    def blocked(
        cls,
        reason_codes: tuple[str, ...],
        review_id: str = "blocked-review",
        source_report_id: str = "unknown",
        source_report_version: str = "1.0",
        reviewer: str = "SYSTEM",
        notes: str = "Fail-closed review record due to safety violation",
        tags: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> ReviewRecord:
        if now is None:
            now = datetime.now(timezone.utc)
        if metadata is None:
            metadata = {}
        return cls(
            review_id=review_id,
            source_report_id=source_report_id,
            source_report_version=source_report_version,
            review_state=ReviewState.BLOCKED,
            review_status=ReviewStatus.NOT_REVIEWED,
            reviewer=reviewer,
            notes=notes,
            tags=tags,
            reason_codes=reason_codes,
            reviewed_at=now,
            safety_flags=ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
                network_calls_enabled=False,
                database_persistence_enabled=False,
            ),
            metadata=metadata,
        )


@dataclass(frozen=True)
class ReviewAuditSummary:
    total_reviews: int
    accepted_count: int
    rejected_count: int
    needs_investigation_count: int
    not_reviewed_count: int
    blocked_count: int
    unknown_count: int
    reason_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        if self.total_reviews < 0:
            raise ValueError("total_reviews must be >= 0")
        if self.accepted_count < 0:
            raise ValueError("accepted_count must be >= 0")
        if self.rejected_count < 0:
            raise ValueError("rejected_count must be >= 0")
        if self.needs_investigation_count < 0:
            raise ValueError("needs_investigation_count must be >= 0")
        if self.not_reviewed_count < 0:
            raise ValueError("not_reviewed_count must be >= 0")
        if self.blocked_count < 0:
            raise ValueError("blocked_count must be >= 0")
        if self.unknown_count < 0:
            raise ValueError("unknown_count must be >= 0")
        total = (
            self.accepted_count
            + self.rejected_count
            + self.needs_investigation_count
            + self.not_reviewed_count
        )
        if total != self.total_reviews:
            raise ValueError("category counts must sum to total_reviews")
        if self.blocked_count + self.unknown_count > self.not_reviewed_count:
            raise ValueError(
                "blocked_count + unknown_count must not exceed not_reviewed_count"
            )
        for reason, count in self.reason_counts.items():
            if count < 0:
                raise ValueError(f"reason_counts value for '{reason}' must be >= 0")


@dataclass(frozen=True)
class ReviewDataQuality:
    total_reports: int
    valid_reports: int
    blocked_reports: int
    unknown_reports: int
    unsafe_reports: int
    missing_reports: int
    invalid_reports: int

    def __post_init__(self) -> None:
        if self.total_reports < 0:
            raise ValueError("total_reports must be >= 0")
        if self.valid_reports < 0:
            raise ValueError("valid_reports must be >= 0")
        if self.blocked_reports < 0:
            raise ValueError("blocked_reports must be >= 0")
        if self.unknown_reports < 0:
            raise ValueError("unknown_reports must be >= 0")
        if self.unsafe_reports < 0:
            raise ValueError("unsafe_reports must be >= 0")
        if self.missing_reports < 0:
            raise ValueError("missing_reports must be >= 0")
        if self.invalid_reports < 0:
            raise ValueError("invalid_reports must be >= 0")
        total = (
            self.valid_reports
            + self.blocked_reports
            + self.unknown_reports
        )
        if total != self.total_reports:
            raise ValueError("valid + blocked + unknown must sum to total_reports")
        if self.unsafe_reports + self.missing_reports + self.invalid_reports > self.blocked_reports:
            raise ValueError(
                "unsafe + missing + invalid must not exceed blocked_reports"
            )


@dataclass(frozen=True)
class ReviewAuditRecord:
    audit_id: str
    generated_at: datetime
    audit_state: ReviewState
    records: tuple[ReviewRecord, ...]
    summary: ReviewAuditSummary
    data_quality: ReviewDataQuality
    reason_codes: tuple[str, ...]
    safety_flags: ReviewSafetyFlags

    def __post_init__(self) -> None:
        if not self.audit_id or not isinstance(self.audit_id, str):
            raise ValueError("audit_id must be a non-empty string")
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if not isinstance(self.records, tuple):
            raise ValueError("records must be a tuple")
        if self.audit_state is not ReviewState.READY and not self.reason_codes:
            raise ValueError("reason_codes must be non-empty when audit_state is not READY")

    @classmethod
    def blocked(
        cls,
        reason_codes: tuple[str, ...],
        audit_id: str = "blocked-audit",
        records: tuple[ReviewRecord, ...] = (),
        now: datetime | None = None,
    ) -> ReviewAuditRecord:
        if now is None:
            now = datetime.now(timezone.utc)
        summary = ReviewAuditSummary(
            total_reviews=len(records),
            accepted_count=0,
            rejected_count=0,
            needs_investigation_count=0,
            not_reviewed_count=len(records),
            blocked_count=len(records),
            unknown_count=0,
            reason_counts={},
        )
        data_quality = ReviewDataQuality(
            total_reports=len(records),
            valid_reports=0,
            blocked_reports=len(records),
            unknown_reports=0,
            unsafe_reports=0,
            missing_reports=0,
            invalid_reports=0,
        )
        safety_flags = ReviewSafetyFlags(
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
        return cls(
            audit_id=audit_id,
            generated_at=now,
            audit_state=ReviewState.BLOCKED,
            records=records,
            summary=summary,
            data_quality=data_quality,
            reason_codes=reason_codes,
            safety_flags=safety_flags,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_forbidden_content(text: str, field_name: str) -> None:
    """Raise ValueError if text contains forbidden review terms (case-insensitive)."""
    lower = text.lower()
    for term in FORBIDDEN_REVIEW_TERMS:
        if term in lower:
            raise ValueError(f"{field_name} contains forbidden term: {term}")
