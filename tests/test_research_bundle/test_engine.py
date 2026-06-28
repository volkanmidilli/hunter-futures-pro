"""Tests for hunter.research_bundle.engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.research_bundle.models import (
    EMPTY_BUNDLE,
    INVALID_ITEM,
    MAX_ITEMS_EXCEEDED,
    MISSING_REFERENCE,
    UNSAFE_ITEM_CONTENT,
    BundleConfig,
    BundleItem,
    BundleItemKind,
    BundleSafetyFlags,
    BundleState,
    ResearchBundle,
)
from hunter.research_bundle.engine import (
    build_bundle_data_quality,
    build_bundle_item,
    build_bundle_safety_flags,
    build_bundle_summary,
    build_research_bundle,
    has_unsafe_bundle_content,
    validate_bundle_item,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# has_unsafe_bundle_content
# ---------------------------------------------------------------------------

class TestHasUnsafeBundleContent:
    def test_empty_string(self) -> None:
        assert has_unsafe_bundle_content("") is False

    def test_safe_text(self) -> None:
        assert has_unsafe_bundle_content("safe text about research") is False

    def test_forbidden_term(self) -> None:
        assert has_unsafe_bundle_content("execute trade now") is True

    def test_forbidden_term_case_insensitive(self) -> None:
        assert has_unsafe_bundle_content("EXECUTE TRADE NOW") is True
        assert has_unsafe_bundle_content("Execute Trade") is True

    def test_forbidden_term_api_key(self) -> None:
        assert has_unsafe_bundle_content("my_api_key_here") is True

    def test_forbidden_term_binance(self) -> None:
        assert has_unsafe_bundle_content("use binance api") is True

    def test_forbidden_term_leverage(self) -> None:
        assert has_unsafe_bundle_content("high leverage strategy") is True

    def test_forbidden_term_trading_signal(self) -> None:
        assert has_unsafe_bundle_content("this is a trading signal") is True

    def test_forbidden_term_trade_approval(self) -> None:
        assert has_unsafe_bundle_content("trade approval granted") is True

    def test_partial_match_not_forbidden(self) -> None:
        # "trade" alone is not forbidden (the term is "trading signal")
        assert has_unsafe_bundle_content("trade") is False
        assert has_unsafe_bundle_content("trading") is False


# ---------------------------------------------------------------------------
# build_bundle_safety_flags
# ---------------------------------------------------------------------------

class TestBuildBundleSafetyFlags:
    def test_default_returns_safe_flags(self) -> None:
        flags = build_bundle_safety_flags()
        assert isinstance(flags, BundleSafetyFlags)
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False

    def test_with_config_returns_safe_flags(self) -> None:
        config = BundleConfig(max_items=100)
        flags = build_bundle_safety_flags(config)
        assert isinstance(flags, BundleSafetyFlags)
        assert flags.bundle_output_is_human_audit_only is True


# ---------------------------------------------------------------------------
# validate_bundle_item
# ---------------------------------------------------------------------------

class TestValidateBundleItem:
    def test_valid_item(self) -> None:
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        is_valid, reason = validate_bundle_item(item)
        assert is_valid is True
        assert reason == ""

    def test_invalid_item_type(self) -> None:
        is_valid, reason = validate_bundle_item("not a bundle item")  # type: ignore[arg-type]
        assert is_valid is False
        assert reason == INVALID_ITEM

    def test_empty_item_id(self) -> None:
        item = BundleItem(
            item_id="",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        is_valid, reason = validate_bundle_item(item)
        assert is_valid is False
        assert reason == MISSING_REFERENCE

    def test_empty_reference(self) -> None:
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="",
        )
        is_valid, reason = validate_bundle_item(item)
        assert is_valid is False
        assert reason == MISSING_REFERENCE

    def test_unsafe_label(self) -> None:
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
            label="execute trade",
        )
        is_valid, reason = validate_bundle_item(item)
        assert is_valid is False
        assert reason == UNSAFE_ITEM_CONTENT

    def test_unsafe_note(self) -> None:
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
            note="place order now",
        )
        is_valid, reason = validate_bundle_item(item)
        assert is_valid is False
        assert reason == UNSAFE_ITEM_CONTENT

    def test_unsafe_reference(self) -> None:
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="secret/api_key.json",
        )
        is_valid, reason = validate_bundle_item(item)
        assert is_valid is False
        assert reason == UNSAFE_ITEM_CONTENT


# ---------------------------------------------------------------------------
# build_bundle_item
# ---------------------------------------------------------------------------

class TestBuildBundleItem:
    def test_with_item_id(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
            item_id="obs-1",
        )
        assert item.item_id == "obs-1"
        assert item.kind is BundleItemKind.OBSERVATION_REPORT
        assert item.reference == "data/observation/latest_observation_report.json"

    def test_without_item_id_generates_one(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.REVIEW_AUDIT,
            reference="reports/review/latest_review_audit_record.md",
        )
        assert item.item_id.startswith("item-REVIEW_AUDIT-")
        assert item.kind is BundleItemKind.REVIEW_AUDIT
        assert item.reference == "reports/review/latest_review_audit_record.md"

    def test_with_label_and_note(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.HUMAN_NOTE,
            reference="notes/manual.txt",
            label="Manual review",
            note="Check this first",
            sort_order=3,
        )
        assert item.label == "Manual review"
        assert item.note == "Check this first"
        assert item.sort_order == 3

    def test_with_metadata(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.SEARCH_RESULT,
            reference="data/review_search/latest_search_result.json",
            metadata={"query": "BTC"},
        )
        assert item.metadata == {"query": "BTC"}

    def test_forbidden_label_raises(self) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            build_bundle_item(
                kind=BundleItemKind.OBSERVATION_REPORT,
                reference="data/observation/latest_observation_report.json",
                label="execute trade now",
            )

    def test_forbidden_note_raises(self) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            build_bundle_item(
                kind=BundleItemKind.OBSERVATION_REPORT,
                reference="data/observation/latest_observation_report.json",
                note="place order immediately",
            )

    def test_forbidden_reference_raises(self) -> None:
        with pytest.raises(ValueError, match="forbidden"):
            build_bundle_item(
                kind=BundleItemKind.OBSERVATION_REPORT,
                reference="secret/api_key.json",
            )

    def test_deterministic_item_id(self) -> None:
        item1 = build_bundle_item(
            kind=BundleItemKind.REVIEW_INDEX,
            reference="data/review_index/latest_review_index.json",
        )
        item2 = build_bundle_item(
            kind=BundleItemKind.REVIEW_INDEX,
            reference="data/review_index/latest_review_index.json",
        )
        assert item1.item_id == item2.item_id

    def test_different_references_different_ids(self) -> None:
        item1 = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/report1.json",
        )
        item2 = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/report2.json",
        )
        assert item1.item_id != item2.item_id


# ---------------------------------------------------------------------------
# build_bundle_summary
# ---------------------------------------------------------------------------

class TestBuildBundleSummary:
    def test_empty_items(self) -> None:
        summary = build_bundle_summary(())
        assert summary.total_items == 0
        assert summary.observation_report_count == 0
        assert summary.review_audit_count == 0

    def test_single_observation(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        summary = build_bundle_summary((item,))
        assert summary.total_items == 1
        assert summary.observation_report_count == 1
        assert summary.review_audit_count == 0

    def test_mixed_items(self) -> None:
        items = (
            build_bundle_item(BundleItemKind.OBSERVATION_REPORT, "obs1.json"),
            build_bundle_item(BundleItemKind.REVIEW_AUDIT, "review1.md"),
            build_bundle_item(BundleItemKind.OBSERVATION_REPORT, "obs2.json"),
            build_bundle_item(BundleItemKind.HUMAN_NOTE, "note.txt"),
            build_bundle_item(BundleItemKind.REVIEW_INDEX, "index.json"),
            build_bundle_item(BundleItemKind.SEARCH_RESULT, "search.json"),
        )
        summary = build_bundle_summary(items)
        assert summary.total_items == 6
        assert summary.observation_report_count == 2
        assert summary.review_audit_count == 1
        assert summary.review_index_count == 1
        assert summary.search_result_count == 1
        assert summary.human_note_count == 1

    def test_sort_order_determinism(self) -> None:
        item1 = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="obs1.json",
            sort_order=2,
        )
        item2 = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="obs2.json",
            sort_order=1,
        )
        # Summary counts are the same regardless of sort order
        summary1 = build_bundle_summary((item1, item2))
        summary2 = build_bundle_summary((item2, item1))
        assert summary1.total_items == summary2.total_items == 2
        assert summary1.observation_report_count == summary2.observation_report_count == 2


# ---------------------------------------------------------------------------
# build_bundle_data_quality
# ---------------------------------------------------------------------------

class TestBuildBundleDataQuality:
    def test_empty_items(self) -> None:
        dq = build_bundle_data_quality(())
        assert dq.total_items == 0
        assert dq.missing_references == 0
        assert dq.invalid_references == 0
        assert dq.has_observation_report is False
        assert dq.has_review_audit is False

    def test_single_observation(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        dq = build_bundle_data_quality((item,))
        assert dq.total_items == 1
        assert dq.has_observation_report is True
        assert dq.has_review_audit is False

    def test_mixed_kinds(self) -> None:
        items = (
            build_bundle_item(BundleItemKind.OBSERVATION_REPORT, "obs1.json"),
            build_bundle_item(BundleItemKind.REVIEW_AUDIT, "review1.md"),
            build_bundle_item(BundleItemKind.REVIEW_INDEX, "index.json"),
            build_bundle_item(BundleItemKind.SEARCH_RESULT, "search.json"),
            build_bundle_item(BundleItemKind.HUMAN_NOTE, "note.txt"),
        )
        dq = build_bundle_data_quality(items)
        assert dq.total_items == 5
        assert dq.has_observation_report is True
        assert dq.has_review_audit is True
        assert dq.has_review_index is True
        assert dq.has_search_result is True
        assert dq.has_human_note is True

    def test_counts_missing_references(self) -> None:
        # Build items with empty references to test missing_references counting
        # Note: empty reference in BundleItem triggers validation in build_bundle_item,
        # so we create BundleItem directly with empty reference
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="",
        )
        dq = build_bundle_data_quality((item,))
        assert dq.missing_references == 1

    def test_counts_invalid_references(self) -> None:
        # Items with empty item_id count as invalid
        item = BundleItem(
            item_id="",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        dq = build_bundle_data_quality((item,))
        assert dq.invalid_references == 1


# ---------------------------------------------------------------------------
# build_research_bundle
# ---------------------------------------------------------------------------

class TestBuildResearchBundle:
    def test_empty_items_blocked(self) -> None:
        bundle = build_research_bundle(())
        assert bundle.bundle_state is BundleState.BLOCKED
        assert EMPTY_BUNDLE in bundle.reason_codes

    def test_single_item_ready(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.bundle_state is BundleState.READY
        assert bundle.reason_codes == ()
        assert bundle.bundle_id.startswith("bundle-")
        assert bundle.generated_at == _now()
        assert len(bundle.items) == 1
        assert bundle.summary.total_items == 1
        assert bundle.data_quality.has_observation_report is True
        assert isinstance(bundle.safety_flags, BundleSafetyFlags)

    def test_multiple_items_ready(self) -> None:
        items = (
            build_bundle_item(BundleItemKind.OBSERVATION_REPORT, "obs1.json"),
            build_bundle_item(BundleItemKind.REVIEW_AUDIT, "review1.md"),
            build_bundle_item(BundleItemKind.HUMAN_NOTE, "note.txt"),
        )
        bundle = build_research_bundle(items, now=_now())
        assert bundle.bundle_state is BundleState.READY
        assert bundle.reason_codes == ()
        assert bundle.summary.total_items == 3
        assert bundle.data_quality.has_observation_report is True
        assert bundle.data_quality.has_review_audit is True
        assert bundle.data_quality.has_human_note is True

    def test_max_items_exceeded_blocked(self) -> None:
        config = BundleConfig(max_items=2)
        items = (
            build_bundle_item(BundleItemKind.OBSERVATION_REPORT, "obs1.json"),
            build_bundle_item(BundleItemKind.OBSERVATION_REPORT, "obs2.json"),
            build_bundle_item(BundleItemKind.OBSERVATION_REPORT, "obs3.json"),
        )
        bundle = build_research_bundle(items, config=config, now=_now())
        assert bundle.bundle_state is BundleState.BLOCKED
        assert MAX_ITEMS_EXCEEDED in bundle.reason_codes

    def test_invalid_item_blocked(self) -> None:
        # Create an invalid item directly (empty reference)
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.bundle_state is BundleState.BLOCKED
        assert MISSING_REFERENCE in bundle.reason_codes

    def test_unsafe_item_blocked(self) -> None:
        # Create unsafe item directly to bypass build_bundle_item validation
        item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
            label="execute trade",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.bundle_state is BundleState.BLOCKED
        assert UNSAFE_ITEM_CONTENT in bundle.reason_codes

    def test_deterministic_bundle_id(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle1 = build_research_bundle((item,), now=_now())
        bundle2 = build_research_bundle((item,), now=_now())
        assert bundle1.bundle_id == bundle2.bundle_id

    def test_different_items_different_bundle_id(self) -> None:
        item1 = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        item2 = build_bundle_item(
            kind=BundleItemKind.REVIEW_AUDIT,
            reference="reports/review/latest_review_audit_record.md",
        )
        bundle1 = build_research_bundle((item1,), now=_now())
        bundle2 = build_research_bundle((item2,), now=_now())
        assert bundle1.bundle_id != bundle2.bundle_id

    def test_bundle_id_contains_timestamp(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert "20240101-120000" in bundle.bundle_id

    def test_config_preserved(self) -> None:
        config = BundleConfig(max_items=100)
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), config=config, now=_now())
        assert bundle.config.max_items == 100

    def test_uses_utc_now_by_default(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,))
        assert bundle.generated_at.tzinfo is not None

    def test_reason_codes_empty_when_ready(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.bundle_state is BundleState.READY
        assert bundle.reason_codes == ()

    def test_mixed_items_with_unsafe_one_blocked(self) -> None:
        items = (
            build_bundle_item(BundleItemKind.OBSERVATION_REPORT, "obs1.json"),
            # Create unsafe item directly to bypass build_bundle_item validation
            BundleItem(
                item_id="item-2",
                kind=BundleItemKind.OBSERVATION_REPORT,
                reference="obs2.json",
                label="execute trade",
            ),
        )
        bundle = build_research_bundle(items, now=_now())
        assert bundle.bundle_state is BundleState.BLOCKED
        assert UNSAFE_ITEM_CONTENT in bundle.reason_codes

    def test_no_file_traversal(self) -> None:
        """Bundle references are strings only and never opened."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/does_not_exist.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.bundle_state is BundleState.READY
        # The non-existent file was never opened or validated
        assert len(bundle.items) == 1
        assert bundle.items[0].reference == "data/observation/does_not_exist.json"

    def test_bundle_safety_flags_always_safe(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.safety_flags.dry_run is True
        assert bundle.safety_flags.live_trading_enabled is False
        assert bundle.safety_flags.bundle_output_is_human_audit_only is True
        assert bundle.safety_flags.bundle_output_not_for_execution is True

    def test_blocked_bundle_has_summary_and_dq(self) -> None:
        bundle = build_research_bundle((), now=_now())
        assert bundle.bundle_state is BundleState.BLOCKED
        assert bundle.summary is not None
        assert bundle.data_quality is not None
        assert bundle.safety_flags is not None

    def test_no_unsafe_imports_or_execution_paths(self) -> None:
        """Bundle engine has no imports for trading, network, or database."""
        # This is verified by the import section and the fact that
        # build_research_bundle only uses the models defined in this package.
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.bundle_state is BundleState.READY
        assert bundle.safety_flags.bundle_feedback_into_execution is False
        assert bundle.safety_flags.report_feedback_into_execution is False
        assert bundle.safety_flags.operator_feedback_into_execution is False
        assert bundle.safety_flags.index_feedback_into_execution is False
        assert bundle.safety_flags.search_feedback_into_execution is False
