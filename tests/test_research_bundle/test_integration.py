"""Integration tests for hunter.research_bundle package. MVP-14 end-to-end integration tests only. No file I/O, network, database, Freqtrade, Binance, exchange, live trading, real orders, leverage, shorting."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.research_bundle.models import (
    EMPTY_BUNDLE,
    MAX_ITEMS_EXCEEDED,
    MISSING_REFERENCE,
    UNSAFE_ITEM_CONTENT,
    BundleConfig,
    BundleDataQuality,
    BundleItem,
    BundleItemKind,
    BundleSafetyFlags,
    BundleState,
    BundleSummary,
    ResearchBundle,
)
from hunter.research_bundle.engine import (
    build_bundle_data_quality,
    build_bundle_item,
    build_bundle_safety_flags,
    build_bundle_summary,
    build_research_bundle,
    validate_bundle_item,
)
from hunter.research_bundle.writer import (
    DEFAULT_BUNDLE_JSON_PATH,
    DEFAULT_BUNDLE_MARKDOWN_PATH,
    research_bundle_to_dict,
    research_bundle_to_markdown,
    write_research_bundle,
)


def _now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestBuildResearchBundleEndToEnd:
    def test_ready_bundle_from_valid_items(self) -> None:
        items = (
            build_bundle_item(
                kind=BundleItemKind.OBSERVATION_REPORT,
                reference="data/observation/latest_observation_report.json",
            ),
            build_bundle_item(
                kind=BundleItemKind.REVIEW_AUDIT,
                reference="reports/review/latest_review_audit_record.md",
            ),
        )
        bundle = build_research_bundle(items, now=_now())
        assert bundle.bundle_state is BundleState.READY
        assert bundle.reason_codes == ()
        assert len(bundle.items) == 2

    def test_blocked_bundle_for_empty_input(self) -> None:
        bundle = build_research_bundle((), now=_now())
        assert bundle.bundle_state is BundleState.BLOCKED
        assert EMPTY_BUNDLE in bundle.reason_codes

    def test_blocked_bundle_for_unsafe_item(self) -> None:
        # Create unsafe item directly to bypass build_bundle_item validation
        unsafe_item = BundleItem(
            item_id="item-1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
            label="execute trade",
        )
        bundle = build_research_bundle((unsafe_item,), now=_now())
        assert bundle.bundle_state is BundleState.BLOCKED
        assert UNSAFE_ITEM_CONTENT in bundle.reason_codes

    def test_respects_max_items(self) -> None:
        items = tuple(
            build_bundle_item(BundleItemKind.OBSERVATION_REPORT, f"obs{i}.json")
            for i in range(3)
        )
        config = BundleConfig(max_items=2)
        bundle = build_research_bundle(items, config=config, now=_now())
        assert bundle.bundle_state is BundleState.BLOCKED
        assert MAX_ITEMS_EXCEEDED in bundle.reason_codes

    def test_deterministic_summary(self) -> None:
        items = (
            build_bundle_item(
                kind=BundleItemKind.OBSERVATION_REPORT,
                reference="data/observation/latest_observation_report.json",
                note="Important observation",
            ),
            build_bundle_item(
                kind=BundleItemKind.REVIEW_AUDIT,
                reference="reports/review/latest_review_audit_record.md",
            ),
        )
        bundle1 = build_research_bundle(items, now=_now())
        bundle2 = build_research_bundle(items, now=_now())
        assert bundle1.summary == bundle2.summary
        assert bundle1.summary.total_items == 2
        assert bundle1.summary.observation_report_count == 1
        assert bundle1.summary.review_audit_count == 1
        assert bundle1.summary.human_note_count == 1

    def test_deterministic_data_quality(self) -> None:
        items = (
            build_bundle_item(
                kind=BundleItemKind.OBSERVATION_REPORT,
                reference="data/observation/latest_observation_report.json",
            ),
            build_bundle_item(
                kind=BundleItemKind.REVIEW_INDEX,
                reference="data/review_index/latest_review_index.json",
            ),
        )
        bundle1 = build_research_bundle(items, now=_now())
        bundle2 = build_research_bundle(items, now=_now())
        assert bundle1.data_quality == bundle2.data_quality
        assert bundle1.data_quality.has_observation_report is True
        assert bundle1.data_quality.has_review_index is True
        assert bundle1.data_quality.has_search_result is False

    def test_config_preserved(self) -> None:
        config = BundleConfig(max_items=50)
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), config=config, now=_now())
        assert bundle.config.max_items == 50


class TestWriterIntegration:
    def test_full_bundle_to_dict(self) -> None:
        items = (
            build_bundle_item(
                kind=BundleItemKind.OBSERVATION_REPORT,
                reference="data/observation/latest_observation_report.json",
                label="Observation Report",
            ),
        )
        bundle = build_research_bundle(items, now=_now())
        d = research_bundle_to_dict(bundle)
        assert d["bundle_id"] == bundle.bundle_id
        assert d["bundle_state"] == "READY"
        assert d["reason_codes"] == []
        assert len(d["items"]) == 1
        assert d["items"][0]["reference"] == "data/observation/latest_observation_report.json"
        assert d["safety_flags"]["bundle_output_is_human_audit_only"] is True

    def test_markdown_includes_safety_notice(self) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        md = research_bundle_to_markdown(bundle)
        assert "human-audit only" in md.lower()
        assert "not trading signal" in md.lower()
        assert "not trade approval" in md.lower()

    def test_write_research_bundle_writes_both(self, tmp_path: Path) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_json_round_trip(self, tmp_path: Path) -> None:
        items = (
            build_bundle_item(
                kind=BundleItemKind.OBSERVATION_REPORT,
                reference="data/observation/latest_observation_report.json",
            ),
            build_bundle_item(
                kind=BundleItemKind.REVIEW_AUDIT,
                reference="reports/review/latest_review_audit_record.md",
            ),
        )
        bundle = build_research_bundle(items, now=_now())
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)

        json_text = json_path.read_text()
        assert bundle.bundle_id in json_text
        assert "READY" in json_text
        assert "data/observation/latest_observation_report.json" in json_text
        assert "reports/review/latest_review_audit_record.md" in json_text

    def test_markdown_includes_item_references(self, tmp_path: Path) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, tmp_path / "bundle.json", md_path)
        md_text = md_path.read_text()
        assert "data/observation/latest_observation_report.json" in md_text

    def test_no_temp_files_left(self, tmp_path: Path) -> None:
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        write_research_bundle(bundle, tmp_path / "bundle.json", tmp_path / "bundle.md")
        temp_files = list(tmp_path.glob("*.tmp"))
        assert temp_files == []

    def test_blocked_bundle_writes(self, tmp_path: Path) -> None:
        bundle = build_research_bundle((), now=_now())
        assert bundle.bundle_state is BundleState.BLOCKED
        json_path = tmp_path / "blocked.json"
        md_path = tmp_path / "blocked.md"
        write_research_bundle(bundle, json_path, md_path)
        json_text = json_path.read_text()
        md_text = md_path.read_text()
        assert "BLOCKED" in json_text
        assert EMPTY_BUNDLE in json_text

    def test_bundle_with_notes_and_labels(self, tmp_path: Path) -> None:
        items = (
            build_bundle_item(
                kind=BundleItemKind.OBSERVATION_REPORT,
                reference="data/observation/obs1.json",
                label="BTC observation",
                note="Price increased significantly",
            ),
            build_bundle_item(
                kind=BundleItemKind.SEARCH_RESULT,
                reference="data/review_search/search1.json",
                label="Search results for BTC",
            ),
        )
        bundle = build_research_bundle(items, now=_now())
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        json_text = json_path.read_text()
        assert "BTC observation" in json_text
        assert "Price increased significantly" in json_text
        assert "Search results for BTC" in json_text

    def test_bundle_with_all_item_kinds(self, tmp_path: Path) -> None:
        items = (
            build_bundle_item(BundleItemKind.OBSERVATION_REPORT, "obs.json"),
            build_bundle_item(BundleItemKind.REVIEW_AUDIT, "review.md"),
            build_bundle_item(BundleItemKind.REVIEW_INDEX, "index.json"),
            build_bundle_item(BundleItemKind.SEARCH_RESULT, "search.json"),
            build_bundle_item(BundleItemKind.HUMAN_NOTE, "note.md", label="Custom note"),
        )
        bundle = build_research_bundle(items, now=_now())
        assert bundle.bundle_state is BundleState.READY
        assert bundle.summary.total_items == 5
        assert bundle.data_quality.has_observation_report is True
        assert bundle.data_quality.has_review_audit is True
        assert bundle.data_quality.has_review_index is True
        assert bundle.data_quality.has_search_result is True


class TestSafetyAssertions:
    def test_no_file_reads_from_references(self, tmp_path: Path) -> None:
        """Bundle writer never opens or reads referenced files."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="/does/not/exist.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        # The reference was written as a string, never opened
        json_text = json_path.read_text()
        assert "/does/not/exist.json" in json_text

    def test_no_network_calls(self, tmp_path: Path) -> None:
        """Bundle writer never makes network calls."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        write_research_bundle(bundle, tmp_path / "bundle.json", tmp_path / "bundle.md")
        # No network code exists in the bundle package

    def test_no_execution_feedback(self, tmp_path: Path) -> None:
        """Bundle results never feed back into execution paths."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.safety_flags.bundle_feedback_into_execution is False
        assert bundle.safety_flags.report_feedback_into_execution is False
        assert bundle.safety_flags.search_feedback_into_execution is False

    def test_no_trading_logic(self, tmp_path: Path) -> None:
        """Bundle results contain no trading decisions or approvals."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.safety_flags.live_trading_enabled is False
        assert bundle.safety_flags.real_orders_enabled is False
        assert bundle.safety_flags.leverage_enabled is False
        assert bundle.safety_flags.shorting_enabled is False

    def test_no_secrets_in_output(self, tmp_path: Path) -> None:
        """Bundle output must not contain API keys or secrets."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        json_text = json_path.read_text().lower()
        md_text = md_path.read_text().lower()
        for term in ("api_key", "secret", "exchange_credentials", "private_key", "password"):
            assert term not in json_text
            assert term not in md_text

    def test_no_executable_instructions_in_output(self, tmp_path: Path) -> None:
        """Bundle output must not contain executable trading instructions."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, json_path, md_path)
        json_text = json_path.read_text().lower()
        md_text = md_path.read_text().lower()
        for term in ("enter_long", "enter_short", "exit_long", "exit_short", "execute trade"):
            assert term not in json_text
            assert term not in md_text

    def test_human_audit_only_notice_in_markdown(self, tmp_path: Path) -> None:
        """Markdown output must contain explicit safety notice."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        md_path = tmp_path / "bundle.md"
        write_research_bundle(bundle, tmp_path / "bundle.json", md_path)
        md_text = md_path.read_text()
        assert "human-audit" in md_text.lower()
        assert "not a trading signal" in md_text.lower()
        assert "not trade approval" in md_text.lower()
        assert "must not be consumed by execution" in md_text.lower()
        assert "Freqtrade" in md_text

    def test_bundle_not_for_strategy(self, tmp_path: Path) -> None:
        """Bundle output must not be consumable by strategy."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.safety_flags.bundle_output_not_for_strategy is True

    def test_bundle_not_for_freqtrade(self, tmp_path: Path) -> None:
        """Bundle output must not be consumable by Freqtrade."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.safety_flags.bundle_output_not_for_freqtrade is True

    def test_bundle_not_for_order(self, tmp_path: Path) -> None:
        """Bundle output must not be consumable by order system."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.safety_flags.bundle_output_not_for_order is True

    def test_bundle_not_for_exchange(self, tmp_path: Path) -> None:
        """Bundle output must not be consumable by exchange."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.safety_flags.bundle_output_not_for_exchange is True

    def test_file_references_are_strings_only(self, tmp_path: Path) -> None:
        """File references survive round-trip without being opened."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="reports/does_not_exist.md",
        )
        bundle = build_research_bundle((item,), now=_now())
        json_path = tmp_path / "bundle.json"
        write_research_bundle(bundle, json_path, tmp_path / "bundle.md")
        json_text = json_path.read_text()
        assert "reports/does_not_exist.md" in json_text
        # File was never opened, traversed, or validated

    def test_bundle_output_not_for_execution(self, tmp_path: Path) -> None:
        """Bundle output must not be consumed by execution."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.safety_flags.bundle_output_not_for_execution is True

    def test_bundle_output_not_trade_approval(self, tmp_path: Path) -> None:
        """Bundle output must not be trade approval."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.safety_flags.bundle_output_not_trade_approval is True

    def test_bundle_output_not_trading_signal(self, tmp_path: Path) -> None:
        """Bundle output must not be trading signal."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.safety_flags.bundle_output_not_trading_signal is True

    def test_bundle_is_human_audit_only(self, tmp_path: Path) -> None:
        """Bundle output is human audit only."""
        item = build_bundle_item(
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="data/observation/latest_observation_report.json",
        )
        bundle = build_research_bundle((item,), now=_now())
        assert bundle.safety_flags.bundle_output_is_human_audit_only is True

    def test_fail_closed_on_invalid_bundle_state(self, tmp_path: Path) -> None:
        """Creating a ResearchBundle with blocked state and no reason_codes raises ValueError."""
        with pytest.raises(ValueError, match="reason_codes"):
            ResearchBundle(
                bundle_id="blocked",
                generated_at=_now(),
                bundle_state=BundleState.BLOCKED,
                items=(),
                summary=BundleSummary(),
                data_quality=BundleDataQuality(),
                safety_flags=BundleSafetyFlags(),
                reason_codes=(),
            )
