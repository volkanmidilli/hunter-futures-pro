"""Models for hunter.research_bundle package.

Frozen dataclasses, enums, reason codes, and forbidden terms for
deterministic research bundle evidence packs.

MVP-14 bundles are human-audit artifacts only.
They are not trading signals, not trade approvals, and must not be consumed by
execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BundleState(Enum):
    """Deterministic bundle states."""
    READY = "READY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class BundleItemKind(Enum):
    """Kind of artifact referenced by a bundle item."""
    OBSERVATION_REPORT = "OBSERVATION_REPORT"
    REVIEW_AUDIT = "REVIEW_AUDIT"
    REVIEW_INDEX = "REVIEW_INDEX"
    SEARCH_RESULT = "SEARCH_RESULT"
    HUMAN_NOTE = "HUMAN_NOTE"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

MISSING_ITEMS = "MISSING_ITEMS"
EMPTY_BUNDLE = "EMPTY_BUNDLE"
INVALID_BUNDLE = "INVALID_BUNDLE"
INVALID_ITEM = "INVALID_ITEM"
MISSING_REFERENCE = "MISSING_REFERENCE"
INVALID_REFERENCE = "INVALID_REFERENCE"
UNSAFE_BUNDLE_CONTENT = "UNSAFE_BUNDLE_CONTENT"
UNSAFE_ITEM_CONTENT = "UNSAFE_ITEM_CONTENT"
UNSAFE_SAFETY_FLAGS = "UNSAFE_SAFETY_FLAGS"
BUNDLE_ERROR = "BUNDLE_ERROR"
DEFAULT_BLOCKED = "DEFAULT_BLOCKED"
MAX_ITEMS_EXCEEDED = "MAX_ITEMS_EXCEEDED"

REASON_CODES: tuple[str, ...] = (
    MISSING_ITEMS,
    EMPTY_BUNDLE,
    INVALID_BUNDLE,
    INVALID_ITEM,
    MISSING_REFERENCE,
    INVALID_REFERENCE,
    UNSAFE_BUNDLE_CONTENT,
    UNSAFE_ITEM_CONTENT,
    UNSAFE_SAFETY_FLAGS,
    BUNDLE_ERROR,
    DEFAULT_BLOCKED,
    MAX_ITEMS_EXCEEDED,
)

# ---------------------------------------------------------------------------
# Forbidden terms
# ---------------------------------------------------------------------------

FORBIDDEN_BUNDLE_TERMS = (
    "execute trade",
    "place order",
    "cancel order",
    "api_key",
    "secret",
    "password",
    "private_key",
    "binance",
    "leverage",
    "short",
    "live trading",
    "real order",
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
    "trading signal",
    "trade approval",
    "strategy signal",
    "freqtrade signal",
    "exchange_credentials",
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BundleConfig:
    """Configuration for bundle building."""
    max_items: int = 500
    include_safety_flags: bool = True
    include_data_quality: bool = True
    include_summary: bool = True

    def __post_init__(self) -> None:
        if self.max_items < 1:
            raise ValueError("max_items must be >= 1")


@dataclass(frozen=True)
class BundleSafetyFlags:
    """Safety flags that must remain fail-closed for bundle artifacts."""
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    bundle_feedback_into_execution: bool = False
    report_feedback_into_execution: bool = False
    operator_feedback_into_execution: bool = False
    index_feedback_into_execution: bool = False
    search_feedback_into_execution: bool = False
    file_reference_traversal_enabled: bool = False
    database_persistence_enabled: bool = False
    web_ui_enabled: bool = False
    dashboard_enabled: bool = False
    # Bundle output is human-audit only — these must be True
    bundle_output_is_human_audit_only: bool = True
    bundle_output_not_trading_signal: bool = True
    bundle_output_not_trade_approval: bool = True
    bundle_output_not_for_execution: bool = True
    bundle_output_not_for_strategy: bool = True
    bundle_output_not_for_freqtrade: bool = True
    bundle_output_not_for_order: bool = True
    bundle_output_not_for_exchange: bool = True

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
            self.bundle_feedback_into_execution,
            self.report_feedback_into_execution,
            self.operator_feedback_into_execution,
            self.index_feedback_into_execution,
            self.search_feedback_into_execution,
            self.file_reference_traversal_enabled,
            self.database_persistence_enabled,
            self.web_ui_enabled,
            self.dashboard_enabled,
        )
        if any(unsafe_flags):
            raise ValueError("unsafe bundle safety flags are enabled")
        safe_flags = (
            self.bundle_output_is_human_audit_only,
            self.bundle_output_not_trading_signal,
            self.bundle_output_not_trade_approval,
            self.bundle_output_not_for_execution,
            self.bundle_output_not_for_strategy,
            self.bundle_output_not_for_freqtrade,
            self.bundle_output_not_for_order,
            self.bundle_output_not_for_exchange,
        )
        if not all(safe_flags):
            raise ValueError("safe bundle output flags must be True")


@dataclass(frozen=True)
class BundleItem:
    """A single item inside a research bundle referencing one artifact."""
    item_id: str
    kind: BundleItemKind
    reference: str
    label: str = ""
    note: str = ""
    sort_order: int = 0
    metadata: Mapping[str, Any] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, BundleItemKind):
            raise ValueError(f"kind must be BundleItemKind, got {type(self.kind)}")
        # Empty item_id and reference are caught by validate_bundle_item
        # to allow engine-level fail-closed handling.


@dataclass(frozen=True)
class BundleSummary:
    """Summary of items inside a research bundle."""
    total_items: int = 0
    observation_report_count: int = 0
    review_audit_count: int = 0
    review_index_count: int = 0
    search_result_count: int = 0
    human_note_count: int = 0
    blocked_items: int = 0
    unknown_items: int = 0

    def __post_init__(self) -> None:
        if self.total_items < 0:
            raise ValueError("total_items must be >= 0")
        if self.observation_report_count < 0:
            raise ValueError("observation_report_count must be >= 0")
        if self.review_audit_count < 0:
            raise ValueError("review_audit_count must be >= 0")
        if self.review_index_count < 0:
            raise ValueError("review_index_count must be >= 0")
        if self.search_result_count < 0:
            raise ValueError("search_result_count must be >= 0")
        if self.human_note_count < 0:
            raise ValueError("human_note_count must be >= 0")
        if self.blocked_items < 0:
            raise ValueError("blocked_items must be >= 0")
        if self.unknown_items < 0:
            raise ValueError("unknown_items must be >= 0")


@dataclass(frozen=True)
class BundleDataQuality:
    """Data quality metrics for a research bundle."""
    total_items: int = 0
    missing_references: int = 0
    invalid_references: int = 0
    blocked_items: int = 0
    has_observation_report: bool = False
    has_review_audit: bool = False
    has_review_index: bool = False
    has_search_result: bool = False
    has_human_note: bool = False

    def __post_init__(self) -> None:
        if self.total_items < 0:
            raise ValueError("total_items must be >= 0")
        if self.missing_references < 0:
            raise ValueError("missing_references must be >= 0")
        if self.invalid_references < 0:
            raise ValueError("invalid_references must be >= 0")
        if self.blocked_items < 0:
            raise ValueError("blocked_items must be >= 0")


@dataclass(frozen=True)
class ResearchBundle:
    """A deterministic, human-audit-only research bundle."""
    bundle_id: str
    generated_at: datetime
    bundle_state: BundleState
    items: tuple[BundleItem, ...]
    summary: BundleSummary
    data_quality: BundleDataQuality
    safety_flags: BundleSafetyFlags
    reason_codes: tuple[str, ...] = ()
    config: BundleConfig = field(default_factory=BundleConfig)
    metadata: Mapping[str, Any] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.bundle_id:
            raise ValueError("bundle_id must be non-empty")
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if not isinstance(self.bundle_state, BundleState):
            raise ValueError(f"bundle_state must be BundleState, got {type(self.bundle_state)}")
        if self.bundle_state is not BundleState.READY and not self.reason_codes:
            raise ValueError("reason_codes must be non-empty when bundle_state is not READY")
        if len(self.items) > self.config.max_items:
            raise ValueError(f"items count {len(self.items)} exceeds max_items {self.config.max_items}")
        for key in self.metadata:
            _check_forbidden_bundle_content(key, "metadata keys")


# ---------------------------------------------------------------------------
# Helper: forbidden content check
# ---------------------------------------------------------------------------

def _check_forbidden_bundle_content(text: str, field_name: str) -> None:
    """Check for forbidden terms in text. Raises ValueError if found."""
    if not text:
        return
    lower = text.lower()
    for term in FORBIDDEN_BUNDLE_TERMS:
        if term in lower:
            raise ValueError(f"forbidden term '{term}' in {field_name}")
