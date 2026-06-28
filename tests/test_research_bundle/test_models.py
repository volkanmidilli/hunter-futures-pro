"""Tests for hunter.research_bundle.models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.research_bundle.models import (
    BUNDLE_ERROR,
    DEFAULT_BLOCKED,
    EMPTY_BUNDLE,
    FORBIDDEN_BUNDLE_TERMS,
    INVALID_BUNDLE,
    INVALID_ITEM,
    INVALID_REFERENCE,
    MAX_ITEMS_EXCEEDED,
    MISSING_ITEMS,
    MISSING_REFERENCE,
    REASON_CODES,
    UNSAFE_BUNDLE_CONTENT,
    UNSAFE_ITEM_CONTENT,
    UNSAFE_SAFETY_FLAGS,
    BundleConfig,
    BundleDataQuality,
    BundleItem,
    BundleItemKind,
    BundleSafetyFlags,
    BundleState,
    BundleSummary,
    ResearchBundle,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestBundleState:
    def test_values(self) -> None:
        assert BundleState.READY.value == "READY"
        assert BundleState.BLOCKED.value == "BLOCKED"
        assert BundleState.UNKNOWN.value == "UNKNOWN"


class TestBundleItemKind:
    def test_values(self) -> None:
        assert BundleItemKind.OBSERVATION_REPORT.value == "OBSERVATION_REPORT"
        assert BundleItemKind.REVIEW_AUDIT.value == "REVIEW_AUDIT"
        assert BundleItemKind.REVIEW_INDEX.value == "REVIEW_INDEX"
        assert BundleItemKind.SEARCH_RESULT.value == "SEARCH_RESULT"
        assert BundleItemKind.HUMAN_NOTE.value == "HUMAN_NOTE"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

class TestReasonCodes:
    def test_reason_codes_tuple(self) -> None:
        assert isinstance(REASON_CODES, tuple)
        assert len(REASON_CODES) == 12
        assert MISSING_ITEMS in REASON_CODES
        assert EMPTY_BUNDLE in REASON_CODES
        assert INVALID_BUNDLE in REASON_CODES
        assert INVALID_ITEM in REASON_CODES
        assert MISSING_REFERENCE in REASON_CODES
        assert INVALID_REFERENCE in REASON_CODES
        assert UNSAFE_BUNDLE_CONTENT in REASON_CODES
        assert UNSAFE_ITEM_CONTENT in REASON_CODES
        assert UNSAFE_SAFETY_FLAGS in REASON_CODES
        assert BUNDLE_ERROR in REASON_CODES
        assert DEFAULT_BLOCKED in REASON_CODES
        assert MAX_ITEMS_EXCEEDED in REASON_CODES

    def test_forbidden_terms_tuple(self) -> None:
        assert isinstance(FORBIDDEN_BUNDLE_TERMS, tuple)
        assert len(FORBIDDEN_BUNDLE_TERMS) >= 1
        assert "execute trade" in FORBIDDEN_BUNDLE_TERMS
        assert "binance" in FORBIDDEN_BUNDLE_TERMS
        assert "api_key" in FORBIDDEN_BUNDLE_TERMS


# ---------------------------------------------------------------------------
# BundleConfig
# ---------------------------------------------------------------------------

class TestBundleConfig:
    def test_defaults(self) -> None:
        config = BundleConfig()
        assert config.max_items == 500
        assert config.include_safety_flags is True
        assert config.include_data_quality is True
        assert config.include_summary is True

    def test_custom_max_items(self) -> None:
        config = BundleConfig(max_items=100)
        assert config.max_items == 100

    def test_zero_max_items_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_items"):
            BundleConfig(max_items=0)

    def test_negative_max_items_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_items"):
            BundleConfig(max_items=-1)

    def test_is_frozen(self) -> None:
        config = BundleConfig()
        with pytest.raises(FrozenInstanceError):
            config.max_items = 100  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BundleSafetyFlags
# ---------------------------------------------------------------------------

class TestBundleSafetyFlags:
    def test_safe_defaults(self) -> None:
        flags = BundleSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.bundle_feedback_into_execution is False
        assert flags.report_feedback_into_execution is False
        assert flags.operator_feedback_into_execution is False
        assert flags.index_feedback_into_execution is False
        assert flags.search_feedback_into_execution is False
        assert flags.file_reference_traversal_enabled is False
        assert flags.database_persistence_enabled is False
        assert flags.web_ui_enabled is False
        assert flags.dashboard_enabled is False
        assert flags.bundle_output_is_human_audit_only is True
        assert flags.bundle_output_not_trading_signal is True
        assert flags.bundle_output_not_trade_approval is True
        assert flags.bundle_output_not_for_execution is True
        assert flags.bundle_output_not_for_strategy is True
        assert flags.bundle_output_not_for_freqtrade is True
        assert flags.bundle_output_not_for_order is True
        assert flags.bundle_output_not_for_exchange is True

    @pytest.mark.parametrize(
        "field_name",
        (
            "live_trading_enabled",
            "real_orders_enabled",
            "leverage_enabled",
            "shorting_enabled",
            "bundle_feedback_into_execution",
            "report_feedback_into_execution",
            "operator_feedback_into_execution",
            "index_feedback_into_execution",
            "search_feedback_into_execution",
            "file_reference_traversal_enabled",
            "database_persistence_enabled",
            "web_ui_enabled",
            "dashboard_enabled",
        ),
    )
    def test_unsafe_flags_rejected(self, field_name: str) -> None:
        with pytest.raises(ValueError, match="unsafe"):
            BundleSafetyFlags(**{field_name: True})

    @pytest.mark.parametrize(
        "field_name",
        (
            "bundle_output_is_human_audit_only",
            "bundle_output_not_trading_signal",
            "bundle_output_not_trade_approval",
            "bundle_output_not_for_execution",
            "bundle_output_not_for_strategy",
            "bundle_output_not_for_freqtrade",
            "bundle_output_not_for_order",
            "bundle_output_not_for_exchange",
        ),
    )
    def test_safe_output_flags_must_be_true(self, field_name: str) -> None:
        with pytest.raises(ValueError, match="safe"):
            BundleSafetyFlags(**{field_name: False})

    def test_is_frozen(self) -> None:
        flags = BundleSafetyFlags()
        with pytest.raises(FrozenInstanceError):
            flags.dry_run = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BundleItem
# ---------------------------------------------------------------------------

class TestBundleItem:
    def test_defaults(self) -> None:
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        assert item.item_id == "item-1"
        assert item.kind is BundleItemKind.OBSERVATION_REPORT
        assert item.reference == "data/observation/latest_observation_report.json"
        assert item.label == ""
        assert item.note == ""
        assert item.sort_order == 0

    def test_all_fields(self) -> None:
        item = BundleItem(
            item_id="item-2",
            kind=BundleItemKind.HUMAN_NOTE,
            reference="notes/manual-review.txt",
            label="Manual review",
            note="Needs investigation",
            sort_order=5,
            metadata={"priority": "high"},
        )
        assert item.item_id == "item-2"
        assert item.kind is BundleItemKind.HUMAN_NOTE
        assert item.reference == "notes/manual-review.txt"
        assert item.label == "Manual review"
        assert item.note == "Needs investigation"
        assert item.sort_order == 5
        assert item.metadata == {"priority": "high"}

    def test_empty_item_id_allowed(self) -> None:
        # Empty item_id is allowed at construction; caught by validate_bundle_item
        item = BundleItem(
            item_id="",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        assert item.item_id == ""
        assert item.reference == "data/observation/latest_observation_report.json"

    def test_empty_reference_allowed(self) -> None:
        # Empty reference is allowed at construction; caught by validate_bundle_item
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="",
        )
        assert item.reference == ""
        assert item.item_id == "item-1"

    def test_invalid_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            BundleItem(
                item_id="item-1",
                kind="invalid",  # type: ignore[arg-type]
                reference="data/observation/latest_observation_report.json",
            )

    def test_forbidden_term_in_label_allowed_at_construction(self) -> None:
        # Forbidden content is caught by validate_bundle_item, not at construction
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
            label="Execute trade now",
        )
        assert item.label == "Execute trade now"

    def test_forbidden_term_in_note_allowed_at_construction(self) -> None:
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
            note="place order immediately",
        )
        assert item.note == "place order immediately"

    def test_forbidden_term_in_reference_allowed_at_construction(self) -> None:
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="secret/api_key.json",
        )
        assert item.reference == "secret/api_key.json"

    def test_forbidden_term_in_metadata_key_allowed_at_construction(self) -> None:
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
            metadata={"api_key": "123"},
        )
        assert item.metadata == {"api_key": "123"}

    def test_is_frozen(self) -> None:
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        with pytest.raises(FrozenInstanceError):
            item.item_id = "new-id"  # type: ignore[misc]

    def test_metadata_is_mapping(self) -> None:
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
            metadata={"key": "value"},
        )
        assert isinstance(item.metadata, Mapping)


# ---------------------------------------------------------------------------
# BundleSummary
# ---------------------------------------------------------------------------

class TestBundleSummary:
    def test_defaults(self) -> None:
        summary = BundleSummary()
        assert summary.total_items == 0
        assert summary.observation_report_count == 0
        assert summary.review_audit_count == 0
        assert summary.review_index_count == 0
        assert summary.search_result_count == 0
        assert summary.human_note_count == 0
        assert summary.blocked_items == 0
        assert summary.unknown_items == 0

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValueError, match="total_items"):
            BundleSummary(total_items=-1)

    def test_is_frozen(self) -> None:
        summary = BundleSummary()
        with pytest.raises(FrozenInstanceError):
            summary.total_items = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BundleDataQuality
# ---------------------------------------------------------------------------

class TestBundleDataQuality:
    def test_defaults(self) -> None:
        dq = BundleDataQuality()
        assert dq.total_items == 0
        assert dq.missing_references == 0
        assert dq.invalid_references == 0
        assert dq.blocked_items == 0
        assert dq.has_observation_report is False
        assert dq.has_review_audit is False
        assert dq.has_review_index is False
        assert dq.has_search_result is False
        assert dq.has_human_note is False

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValueError, match="total_items"):
            BundleDataQuality(total_items=-1)
        with pytest.raises(ValueError, match="missing_references"):
            BundleDataQuality(missing_references=-1)
        with pytest.raises(ValueError, match="invalid_references"):
            BundleDataQuality(invalid_references=-1)
        with pytest.raises(ValueError, match="blocked_items"):
            BundleDataQuality(blocked_items=-1)

    def test_is_frozen(self) -> None:
        dq = BundleDataQuality()
        with pytest.raises(FrozenInstanceError):
            dq.total_items = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ResearchBundle
# ---------------------------------------------------------------------------

class TestResearchBundle:
    def _make_item(self, item_id: str = "item-1", kind: BundleItemKind = BundleItemKind.OBSERVATION_REPORT) -> BundleItem:
        return BundleItem(
            item_id=item_id,
            kind=kind,
            reference="data/observation/latest_observation_report.json",
        )

    def test_ready_bundle(self) -> None:
        item = self._make_item()
        bundle = ResearchBundle(
            bundle_id="bundle-1",
            generated_at=_now(),
            bundle_state=BundleState.READY,
            items=(item,),
            summary=BundleSummary(),
            data_quality=BundleDataQuality(),
            safety_flags=BundleSafetyFlags(),
        )
        assert bundle.bundle_id == "bundle-1"
        assert bundle.bundle_state is BundleState.READY
        assert len(bundle.items) == 1
        assert bundle.reason_codes == ()

    def test_blocked_bundle_with_reason_codes(self) -> None:
        item = self._make_item()
        bundle = ResearchBundle(
            bundle_id="bundle-1",
            generated_at=_now(),
            bundle_state=BundleState.BLOCKED,
            items=(item,),
            summary=BundleSummary(),
            data_quality=BundleDataQuality(),
            safety_flags=BundleSafetyFlags(),
            reason_codes=(EMPTY_BUNDLE,),
        )
        assert bundle.bundle_state is BundleState.BLOCKED
        assert bundle.reason_codes == (EMPTY_BUNDLE,)

    def test_blocked_without_reason_codes_rejected(self) -> None:
        with pytest.raises(ValueError, match="reason_codes"):
            ResearchBundle(
                bundle_id="bundle-1",
                generated_at=_now(),
                bundle_state=BundleState.BLOCKED,
                items=(self._make_item(),),
                summary=BundleSummary(),
                data_quality=BundleDataQuality(),
                safety_flags=BundleSafetyFlags(),
                reason_codes=(),
            )

    def test_empty_bundle_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="bundle_id"):
            ResearchBundle(
                bundle_id="",
                generated_at=_now(),
                bundle_state=BundleState.READY,
                items=(self._make_item(),),
                summary=BundleSummary(),
                data_quality=BundleDataQuality(),
                safety_flags=BundleSafetyFlags(),
            )

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            ResearchBundle(
                bundle_id="bundle-1",
                generated_at=datetime(2024, 1, 1, 12, 0),
                bundle_state=BundleState.READY,
                items=(self._make_item(),),
                summary=BundleSummary(),
                data_quality=BundleDataQuality(),
                safety_flags=BundleSafetyFlags(),
            )

    def test_invalid_bundle_state_rejected(self) -> None:
        with pytest.raises(ValueError, match="bundle_state"):
            ResearchBundle(
                bundle_id="bundle-1",
                generated_at=_now(),
                bundle_state="READY",  # type: ignore[arg-type]
                items=(self._make_item(),),
                summary=BundleSummary(),
                data_quality=BundleDataQuality(),
                safety_flags=BundleSafetyFlags(),
            )

    def test_items_exceed_max_items_rejected(self) -> None:
        config = BundleConfig(max_items=1)
        item1 = self._make_item("item-1")
        item2 = self._make_item("item-2")
        with pytest.raises(ValueError, match="exceeds max_items"):
            ResearchBundle(
                bundle_id="bundle-1",
                generated_at=_now(),
                bundle_state=BundleState.READY,
                items=(item1, item2),
                summary=BundleSummary(),
                data_quality=BundleDataQuality(),
                safety_flags=BundleSafetyFlags(),
                config=config,
            )

    def test_forbidden_term_in_metadata_rejected(self) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            ResearchBundle(
                bundle_id="bundle-1",
                generated_at=_now(),
                bundle_state=BundleState.READY,
                items=(self._make_item(),),
                summary=BundleSummary(),
                data_quality=BundleDataQuality(),
                safety_flags=BundleSafetyFlags(),
                metadata={"api_key": "secret"},
            )

    def test_is_frozen(self) -> None:
        bundle = ResearchBundle(
            bundle_id="bundle-1",
            generated_at=_now(),
            bundle_state=BundleState.READY,
            items=(self._make_item(),),
            summary=BundleSummary(),
            data_quality=BundleDataQuality(),
            safety_flags=BundleSafetyFlags(),
        )
        with pytest.raises(FrozenInstanceError):
            bundle.bundle_id = "new-id"  # type: ignore[misc]
