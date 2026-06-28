"""Tests for hunter.research_bundle.writer. MVP-14 research_bundle writer tests only. No network, database, Freqtrade, Binance, exchange, live trading, real orders, leverage, shorting."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.research_bundle.models import (
    BUNDLE_ERROR,
    DEFAULT_BLOCKED,
    EMPTY_BUNDLE,
    INVALID_BUNDLE,
    INVALID_ITEM,
    INVALID_REFERENCE,
    MAX_ITEMS_EXCEEDED,
    MISSING_ITEMS,
    MISSING_REFERENCE,
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
from hunter.research_bundle.writer import (
    DEFAULT_BUNDLE_JSON_PATH,
    DEFAULT_BUNDLE_MARKDOWN_PATH,
    atomic_write_json_research_bundle,
    atomic_write_markdown_research_bundle,
    bundle_data_quality_to_dict,
    bundle_item_to_dict,
    bundle_safety_flags_to_dict,
    bundle_summary_to_dict,
    research_bundle_to_dict,
    research_bundle_to_markdown,
    write_research_bundle,
)


def _now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_item(
    item_id: str = "item-1",
    kind: BundleItemKind = BundleItemKind.OBSERVATION_REPORT,
    reference: str = "data/observation/latest_observation_report.json",
    label: str = "Observation Report",
    note: str = "",
    sort_order: int = 0,
    metadata: dict[str, str] | None = None,
) -> BundleItem:
    return BundleItem(
        item_id=item_id,
        kind=kind,
        reference=reference,
        label=label,
        note=note,
        sort_order=sort_order,
        metadata=metadata if metadata is not None else {},
    )


def _make_bundle(
    items: tuple[BundleItem, ...] = (),
    state: BundleState = BundleState.READY,
    reason_codes: tuple[str, ...] = (),
) -> ResearchBundle:
    return ResearchBundle(
        bundle_id="bundle-1",
        generated_at=_now(),
        bundle_state=state,
        items=items,
        summary=BundleSummary(
            total_items=len(items),
            observation_report_count=sum(1 for i in items if i.kind is BundleItemKind.OBSERVATION_REPORT),
            review_audit_count=sum(1 for i in items if i.kind is BundleItemKind.REVIEW_AUDIT),
            review_index_count=sum(1 for i in items if i.kind is BundleItemKind.REVIEW_INDEX),
            search_result_count=sum(1 for i in items if i.kind is BundleItemKind.SEARCH_RESULT),
            human_note_count=sum(1 for i in items if i.note),
            blocked_items=0,
            unknown_items=0,
        ),
        data_quality=BundleDataQuality(
            total_items=len(items),
            missing_references=0,
            invalid_references=0,
            blocked_items=0,
            has_observation_report=any(i.kind is BundleItemKind.OBSERVATION_REPORT for i in items),
            has_review_audit=any(i.kind is BundleItemKind.REVIEW_AUDIT for i in items),
            has_review_index=any(i.kind is BundleItemKind.REVIEW_INDEX for i in items),
            has_search_result=any(i.kind is BundleItemKind.SEARCH_RESULT for i in items),
            has_human_note=any(i.note for i in items),
        ),
        safety_flags=BundleSafetyFlags(),
        reason_codes=reason_codes,
    )


class TestBundleSafetyFlagsToDict:
    def test_safe_output_flags(self) -> None:
        flags = BundleSafetyFlags()
        d = bundle_safety_flags_to_dict(flags)
        assert d["bundle_output_is_human_audit_only"] is True
        assert d["bundle_output_not_trading_signal"] is True
        assert d["bundle_output_not_trade_approval"] is True
        assert d["bundle_output_not_for_execution"] is True
        assert d["bundle_output_not_for_strategy"] is True
        assert d["bundle_output_not_for_freqtrade"] is True
        assert d["bundle_output_not_for_order"] is True
        assert d["bundle_output_not_for_exchange"] is True

    def test_unsafe_flags(self) -> None:
        flags = BundleSafetyFlags()
        d = bundle_safety_flags_to_dict(flags)
        assert d["live_trading_enabled"] is False
        assert d["real_orders_enabled"] is False
        assert d["leverage_enabled"] is False
        assert d["shorting_enabled"] is False
        assert d["bundle_feedback_into_execution"] is False

    def test_keys_sorted(self) -> None:
        flags = BundleSafetyFlags()
        d = bundle_safety_flags_to_dict(flags)
        keys = list(d.keys())
        assert keys == sorted(keys)


class TestBundleItemToDict:
    def test_basic_item(self) -> None:
        item = _make_item()
        d = bundle_item_to_dict(item)
        assert d["item_id"] == "item-1"
        assert d["kind"] == "OBSERVATION_REPORT"
        assert d["reference"] == "data/observation/latest_observation_report.json"
        assert d["label"] == "Observation Report"
        assert d["note"] == ""
        assert d["sort_order"] == 0
        assert d["metadata"] == {}

    def test_item_with_metadata(self) -> None:
        item = _make_item(metadata={"priority": "high", "symbol": "BTC/USDT"})
        d = bundle_item_to_dict(item)
        assert d["metadata"] == {"priority": "high", "symbol": "BTC/USDT"}

    def test_item_with_note(self) -> None:
        item = _make_item(note="Needs further review")
        d = bundle_item_to_dict(item)
        assert d["note"] == "Needs further review"

    def test_different_kind(self) -> None:
        item = _make_item(kind=BundleItemKind.REVIEW_AUDIT, reference="reports/review/latest.md")
        d = bundle_item_to_dict(item)
        assert d["kind"] == "REVIEW_AUDIT"
        assert d["reference"] == "reports/review/latest.md"


class TestBundleSummaryToDict:
    def test_empty_summary(self) -> None:
        summary = BundleSummary()
        d = bundle_summary_to_dict(summary)
        assert d["total_items"] == 0
        assert d["observation_report_count"] == 0
        assert d["review_audit_count"] == 0
        assert d["review_index_count"] == 0
        assert d["search_result_count"] == 0
        assert d["human_note_count"] == 0
        assert d["blocked_items"] == 0

    def test_populated_summary(self) -> None:
        summary = BundleSummary(
            total_items=5,
            observation_report_count=2,
            review_audit_count=1,
            review_index_count=1,
            search_result_count=1,
            human_note_count=3,
            blocked_items=0,
        )
        d = bundle_summary_to_dict(summary)
        assert d["total_items"] == 5
        assert d["observation_report_count"] == 2
        assert d["review_audit_count"] == 1
        assert d["review_index_count"] == 1
        assert d["search_result_count"] == 1
        assert d["human_note_count"] == 3
        assert d["blocked_items"] == 0


class TestBundleDataQualityToDict:
    def test_default_data_quality(self) -> None:
        dq = BundleDataQuality()
        d = bundle_data_quality_to_dict(dq)
        assert d["total_items"] == 0
        assert d["missing_references"] == 0
        assert d["invalid_references"] == 0
        assert d["blocked_items"] == 0
        assert d["has_observation_report"] is False
        assert d["has_review_audit"] is False
        assert d["has_review_index"] is False
        assert d["has_search_result"] is False
        assert d["has_human_note"] is False

    def test_populated_data_quality(self) -> None:
        dq = BundleDataQuality(
            total_items=3,
            missing_references=1,
            invalid_references=0,
            blocked_items=0,
            has_observation_report=True,
            has_review_audit=True,
            has_review_index=False,
            has_search_result=True,
            has_human_note=False,
        )
        d = bundle_data_quality_to_dict(dq)
        assert d["total_items"] == 3
        assert d["missing_references"] == 1
        assert d["has_observation_report"] is True
        assert d["has_review_audit"] is True
        assert d["has_review_index"] is False
        assert d["has_search_result"] is True
        assert d["has_human_note"] is False


class TestResearchBundleToDict:
    def test_empty_bundle(self) -> None:
        bundle = _make_bundle()
        d = research_bundle_to_dict(bundle)
        assert d["bundle_id"] == "bundle-1"
        assert d["generated_at"] == "2024-01-01T12:00:00+00:00"
        assert d["bundle_state"] == "READY"
        assert d["items"] == []
        assert d["reason_codes"] == []
        assert d["safety_flags"]["bundle_output_is_human_audit_only"] is True

    def test_bundle_with_items(self) -> None:
        items = (
            _make_item(item_id="item-1", kind=BundleItemKind.OBSERVATION_REPORT),
            _make_item(item_id="item-2", kind=BundleItemKind.REVIEW_AUDIT, reference="reports/review.md"),
        )
        bundle = _make_bundle(items=items)
        d = research_bundle_to_dict(bundle)
        assert len(d["items"]) == 2
        assert d["items"][0]["item_id"] == "item-1"
        assert d["items"][1]["item_id"] == "item-2"
        assert d["summary"]["total_items"] == 2
        assert d["data_quality"]["total_items"] == 2

    def test_blocked_bundle(self) -> None:
        bundle = _make_bundle(
            state=BundleState.BLOCKED,
            reason_codes=(EMPTY_BUNDLE,),
        )
        d = research_bundle_to_dict(bundle)
        assert d["bundle_state"] == "BLOCKED"
        assert d["reason_codes"] == [EMPTY_BUNDLE]

    def test_bundle_with_metadata(self) -> None:
        item = _make_item(metadata={"priority": "high"})
        bundle = _make_bundle(items=(item,))
        d = research_bundle_to_dict(bundle)
        assert d["items"][0]["metadata"] == {"priority": "high"}

    def test_bundle_with_config(self) -> None:
        bundle = _make_bundle()
        d = research_bundle_to_dict(bundle)
        # Config is not serialized in dict (only in bundle object)
        assert "config" not in d


class TestResearchBundleToMarkdown:
    def test_contains_bundle_id(self) -> None:
        bundle = _make_bundle()
        md = research_bundle_to_markdown(bundle)
        assert "bundle-1" in md

    def test_contains_generated_at(self) -> None:
        bundle = _make_bundle()
        md = research_bundle_to_markdown(bundle)
        assert "2024-01-01T12:00:00+00:00" in md

    def test_contains_human_audit_notice(self) -> None:
        bundle = _make_bundle()
        md = research_bundle_to_markdown(bundle)
        assert "human-audit artifact only" in md

    def test_contains_not_trading_signal(self) -> None:
        bundle = _make_bundle()
        md = research_bundle_to_markdown(bundle)
        assert "not a trading signal" in md

    def test_contains_not_trade_approval(self) -> None:
        bundle = _make_bundle()
        md = research_bundle_to_markdown(bundle)
        assert "not trade approval" in md

    def test_contains_not_for_execution(self) -> None:
        bundle = _make_bundle()
        md = research_bundle_to_markdown(bundle)
        assert "must not be consumed by execution" in md

    def test_contains_file_reference_notice(self) -> None:
        bundle = _make_bundle()
        md = research_bundle_to_markdown(bundle)
        assert "not traversed, opened, followed, validated, or executed" in md

    def test_contains_safety_flags(self) -> None:
        bundle = _make_bundle()
        md = research_bundle_to_markdown(bundle)
        assert "Dry Run" in md
        assert "Live Trading" in md
        assert "Human-Audit Only" in md

    def test_contains_items(self) -> None:
        items = (
            _make_item(item_id="item-1", kind=BundleItemKind.OBSERVATION_REPORT),
            _make_item(item_id="item-2", kind=BundleItemKind.REVIEW_AUDIT, reference="reports/review.md"),
        )
        bundle = _make_bundle(items=items)
        md = research_bundle_to_markdown(bundle)
        assert "item-1" in md
        assert "item-2" in md
        assert "OBSERVATION_REPORT" in md
        assert "REVIEW_AUDIT" in md

    def test_contains_metadata_in_items(self) -> None:
        item = _make_item(metadata={"priority": "high"})
        bundle = _make_bundle(items=(item,))
        md = research_bundle_to_markdown(bundle)
        assert "priority" in md
        assert "high" in md

    def test_contains_reason_codes(self) -> None:
        bundle = _make_bundle(reason_codes=(EMPTY_BUNDLE,))
        md = research_bundle_to_markdown(bundle)
        assert EMPTY_BUNDLE in md

    def test_contains_data_quality(self) -> None:
        bundle = _make_bundle()
        md = research_bundle_to_markdown(bundle)
        assert "Total Items" in md
        assert "Missing References" in md
        assert "Has Observation Report" in md

    def test_contains_summary(self) -> None:
        bundle = _make_bundle()
        md = research_bundle_to_markdown(bundle)
        assert "Total Items" in md
        assert "Observation Reports" in md

    def test_blocked_bundle(self) -> None:
        bundle = _make_bundle(
            state=BundleState.BLOCKED,
            reason_codes=(EMPTY_BUNDLE,),
        )
        md = research_bundle_to_markdown(bundle)
        assert "BLOCKED" in md
        assert EMPTY_BUNDLE in md

    def test_no_executable_instructions(self) -> None:
        bundle = _make_bundle()
        md = research_bundle_to_markdown(bundle).lower()
        assert "enter_long" not in md
        assert "enter_short" not in md
        assert "exit_long" not in md
        assert "exit_short" not in md


class TestAtomicWriteJson:
    def test_writes_json(self, tmp_path: Path) -> None:
        bundle = _make_bundle()
        path = tmp_path / "bundle.json"
        atomic_write_json_research_bundle(bundle, path)
        assert path.exists()
        text = path.read_text()
        assert "bundle-1" in text
        assert "READY" in text

    def test_json_is_valid(self, tmp_path: Path) -> None:
        import json

        bundle = _make_bundle(items=(_make_item(),))
        path = tmp_path / "bundle.json"
        atomic_write_json_research_bundle(bundle, path)
        data = json.loads(path.read_text())
        assert data["bundle_id"] == "bundle-1"
        assert data["bundle_state"] == "READY"
        assert len(data["items"]) == 1

    def test_json_deterministic_keys(self, tmp_path: Path) -> None:
        import json

        bundle = _make_bundle()
        path = tmp_path / "bundle.json"
        atomic_write_json_research_bundle(bundle, path)
        data = json.loads(path.read_text())
        # Top-level keys should be in defined order (not sorted)
        keys = list(data.keys())
        assert keys[0] == "bundle_id"
        assert keys[1] == "generated_at"
        assert keys[2] == "bundle_state"

    def test_ends_with_newline(self, tmp_path: Path) -> None:
        bundle = _make_bundle()
        path = tmp_path / "bundle.json"
        atomic_write_json_research_bundle(bundle, path)
        text = path.read_text()
        assert text.endswith("\n")

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        bundle = _make_bundle()
        path = tmp_path / "nested" / "dir" / "bundle.json"
        atomic_write_json_research_bundle(bundle, path)
        assert path.exists()


class TestAtomicWriteMarkdown:
    def test_writes_markdown(self, tmp_path: Path) -> None:
        bundle = _make_bundle()
        path = tmp_path / "bundle.md"
        atomic_write_markdown_research_bundle(bundle, path)
        assert path.exists()
        text = path.read_text()
        assert "# Research Bundle" in text

    def test_contains_all_sections(self, tmp_path: Path) -> None:
        bundle = _make_bundle(items=(_make_item(),))
        path = tmp_path / "bundle.md"
        atomic_write_markdown_research_bundle(bundle, path)
        text = path.read_text()
        assert "## Safety Notice" in text
        assert "## Summary" in text
        assert "## Data Quality" in text
        assert "## Safety Flags" in text
        assert "## Reason Codes" in text
        assert "## Items" in text

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        bundle = _make_bundle()
        path = tmp_path / "nested" / "dir" / "bundle.md"
        atomic_write_markdown_research_bundle(bundle, path)
        assert path.exists()


class TestWriteResearchBundle:
    def test_writes_both(self, tmp_path: Path) -> None:
        bundle = _make_bundle()
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_returns_paths(self, tmp_path: Path) -> None:
        bundle = _make_bundle()
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        result = write_research_bundle(bundle, json_path, md_path)
        assert result == (json_path, md_path)

    def test_default_paths(self) -> None:
        assert DEFAULT_BUNDLE_JSON_PATH == Path("data/research_bundle/latest_research_bundle.json")
        assert DEFAULT_BUNDLE_MARKDOWN_PATH == Path("reports/research_bundle/latest_research_bundle.md")

    def test_no_temp_files_left(self, tmp_path: Path) -> None:
        bundle = _make_bundle()
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        assert not (tmp_path / "bundle.json.tmp").exists()
        assert not (tmp_path / "bundle.md.tmp").exists()

    def test_no_file_reference_traversal(self, tmp_path: Path) -> None:
        """Writer must not open or read referenced files."""
        bundle = _make_bundle(
            items=(_make_item(reference="/does/not/exist.json"),),
        )
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        assert json_path.exists()
        assert md_path.exists()
        # The reference was never opened or traversed

    def test_no_secrets_in_output(self, tmp_path: Path) -> None:
        bundle = _make_bundle()
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        json_text = json_path.read_text().lower()
        md_text = md_path.read_text().lower()
        for term in ("api_key", "secret", "password", "private_key"):
            assert term not in json_text
            assert term not in md_text

    def test_no_trading_instructions_in_output(self, tmp_path: Path) -> None:
        bundle = _make_bundle()
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        json_text = json_path.read_text().lower()
        md_text = md_path.read_text().lower()
        for term in ("enter_long", "enter_short", "exit_long", "exit_short", "execute trade"):
            assert term not in json_text
            assert term not in md_text

    def test_blocked_bundle_writes(self, tmp_path: Path) -> None:
        bundle = _make_bundle(
            state=BundleState.BLOCKED,
            reason_codes=(EMPTY_BUNDLE,),
        )
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        assert json_path.exists()
        assert md_path.exists()
        text = json_path.read_text()
        assert "BLOCKED" in text
        assert EMPTY_BUNDLE in text

    def test_bundle_with_notes(self, tmp_path: Path) -> None:
        item = _make_item(note="Needs further investigation")
        bundle = _make_bundle(items=(item,))
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        text = md_path.read_text()
        assert "Needs further investigation" in text

    def test_bundle_with_labels(self, tmp_path: Path) -> None:
        item = _make_item(label="Critical observation")
        bundle = _make_bundle(items=(item,))
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        text = md_path.read_text()
        assert "Critical observation" in text
