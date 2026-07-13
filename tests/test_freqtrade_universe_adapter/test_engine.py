"""Tests for the Freqtrade Universe Consumption Adapter engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.controlled_universe_export_adapter.models import (
    BLOCKED_EXPORT,
    MISSING_REPORT_INPUT,
    NO_INCLUDED_PAIRS,
    ControlledUniverseExportResult,
    ControlledUniversePairExportSummary,
)
from hunter.freqtrade_universe_adapter.engine import (
    _apply_deduplication_and_contradiction,
    _build_pairlist,
    _deduplicate_pairs,
    _derive_mode,
    _detect_blocked_reason,
    _normalize_pair,
    _normalize_pair_list,
    build_freqtrade_universe_adapter_result,
)
from hunter.freqtrade_universe_adapter.models import (
    BLOCKED_EXPORT_INPUT,
    CONTRADICTORY_PAIR,
    DUPLICATE_PAIR,
    EMPTY_WHITELIST,
    EXPORT_HUMAN_APPROVAL_REQUIRED,
    EXPORT_RESEARCH_ONLY,
    INVALID_PAIR_FORMAT,
    MISSING_EXPORT_INPUT,
    NO_AUTOMATIC_CONFIG_MUTATION,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    STALE_EXPORT_INPUT,
    FreqtradeUniverseAdapterConfig,
    FreqtradeUniverseAdapterResult,
)
from hunter.freqtrade_universe_adapter import (
    FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES,
)
from hunter.strategy_contract import StrategyContractMode


def _make_export_result(
    **overrides: object,
) -> ControlledUniverseExportResult:
    """Build a minimal ControlledUniverseExportResult with sensible defaults."""
    now = datetime.now(timezone.utc)
    defaults: dict[str, object] = {
        "report_id": "cue-test",
        "generated_at": now,
        "whitelist": ("BTC/USDT", "ETH/USDT"),
        "blacklist": (),
        "per_pair_summary": (
            ControlledUniversePairExportSummary(
                pair="BTC/USDT",
                state="INCLUDED",
                classification="LONG_RESEARCH",
                reason_codes=(),
                human_note="ok",
            ),
            ControlledUniversePairExportSummary(
                pair="ETH/USDT",
                state="INCLUDED",
                classification="LONG_RESEARCH",
                reason_codes=(),
                human_note="ok",
            ),
        ),
        "research_only": True,
        "human_approval_required": True,
        "reason_codes": (EXPORT_RESEARCH_ONLY, EXPORT_HUMAN_APPROVAL_REQUIRED),
        "safety_flags": {"no_freqtrade_runtime_connection": True},
        "metadata": {"source": "test"},
    }
    defaults.update(overrides)
    return ControlledUniverseExportResult(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def config() -> FreqtradeUniverseAdapterConfig:
    return FreqtradeUniverseAdapterConfig.default()


class TestNormalizePair:
    def test_base_quote_to_base_quote(self) -> None:
        assert _normalize_pair("BTC/USDT", "base_quote") == "BTC_USDT"

    def test_base_quote_to_base_slash(self) -> None:
        assert _normalize_pair("BTC_USDT", "base/quote") == "BTC/USDT"

    def test_already_target_format(self) -> None:
        assert _normalize_pair("BTC/USDT", "base/quote") == "BTC/USDT"
        assert _normalize_pair("BTC_USDT", "base_quote") == "BTC_USDT"

    def test_lowercase_input(self) -> None:
        assert _normalize_pair("btc/usdt", "base/quote") == "BTC/USDT"

    def test_extra_whitespace(self) -> None:
        assert _normalize_pair("  BTC / USDT  ", "base/quote") == "BTC/USDT"

    def test_invalid_no_separator(self) -> None:
        assert _normalize_pair("BTCUSDT", "base/quote") is None

    def test_invalid_too_many_parts(self) -> None:
        assert _normalize_pair("BTC/USDT/PERP", "base/quote") is None

    def test_invalid_empty_base(self) -> None:
        assert _normalize_pair("/USDT", "base/quote") is None

    def test_invalid_empty_quote(self) -> None:
        assert _normalize_pair("BTC/", "base/quote") is None


class TestDeduplicatePairs:
    def test_preserves_first_occurrence(self) -> None:
        pairs = ("BTC/USDT", "ETH/USDT", "BTC/USDT", "ADA/USDT")
        assert _deduplicate_pairs(pairs) == ("BTC/USDT", "ETH/USDT", "ADA/USDT")

    def test_no_duplicates(self) -> None:
        pairs = ("BTC/USDT", "ETH/USDT")
        assert _deduplicate_pairs(pairs) == pairs


class TestNormalizePairList:
    def test_all_valid(self) -> None:
        pairs, invalid = _normalize_pair_list(("BTC/USDT", "ETH/USDT"), "base/quote")
        assert pairs == ("BTC/USDT", "ETH/USDT")
        assert invalid is False

    def test_excludes_invalid(self) -> None:
        pairs, invalid = _normalize_pair_list(("BTC/USDT", "BAD", "ETH/USDT"), "base/quote")
        assert pairs == ("BTC/USDT", "ETH/USDT")
        assert invalid is True


class TestApplyDeduplicationAndContradiction:
    def test_contradiction_blacklist_wins(self) -> None:
        whitelist, blacklist, dup, contra = _apply_deduplication_and_contradiction(
            ("BTC/USDT", "ETH/USDT"), ("BTC/USDT",)
        )
        assert whitelist == ("ETH/USDT",)
        assert "BTC/USDT" in blacklist
        assert contra is True
        assert dup is False

    def test_duplicate_only(self) -> None:
        whitelist, blacklist, dup, contra = _apply_deduplication_and_contradiction(
            ("BTC/USDT", "BTC/USDT"), ("ETH/USDT",)
        )
        assert whitelist == ("BTC/USDT",)
        assert blacklist == ("ETH/USDT",)
        assert dup is True
        assert contra is False

    def test_sorted_blacklist(self) -> None:
        whitelist, blacklist, _, _ = _apply_deduplication_and_contradiction(
            ("BTC/USDT",), ("ADA/USDT", "ETH/USDT")
        )
        assert blacklist == ("ADA/USDT", "ETH/USDT")


class TestDeriveMode:
    def _summary(self, pair: str, classification: str) -> ControlledUniversePairExportSummary:
        return ControlledUniversePairExportSummary(
            pair=pair,
            state="INCLUDED",
            classification=classification,
            reason_codes=(),
            human_note="",
        )

    def test_long_only(self) -> None:
        summary = self._summary("BTC/USDT", "LONG_RESEARCH")
        assert _derive_mode(("BTC/USDT",), {"BTC/USDT": summary}) == StrategyContractMode.LONG_RESEARCH_ONLY.value

    def test_short_only(self) -> None:
        summary = self._summary("BTC/USDT", "SHORT_RESEARCH")
        assert _derive_mode(("BTC/USDT",), {"BTC/USDT": summary}) == StrategyContractMode.SHORT_RESEARCH_ONLY.value

    def test_mixed_blocks(self) -> None:
        s1 = self._summary("BTC/USDT", "LONG_RESEARCH")
        s2 = self._summary("ETH/USDT", "SHORT_RESEARCH")
        assert _derive_mode(("BTC/USDT", "ETH/USDT"), {"BTC/USDT": s1, "ETH/USDT": s2}) == StrategyContractMode.BLOCK_ALL.value

    def test_empty_blocks(self) -> None:
        assert _derive_mode((), {}) == StrategyContractMode.BLOCK_ALL.value

    def test_watchlist_excluded_from_mode(self) -> None:
        s1 = self._summary("BTC/USDT", "WATCHLIST_RESEARCH")
        assert _derive_mode(("BTC/USDT",), {"BTC/USDT": s1}) == StrategyContractMode.BLOCK_ALL.value

    def test_neutral_excluded_from_mode(self) -> None:
        s1 = self._summary("BTC/USDT", "NEUTRAL_RESEARCH")
        assert _derive_mode(("BTC/USDT",), {"BTC/USDT": s1}) == StrategyContractMode.BLOCK_ALL.value

    def test_long_after_excluding_watchlist(self) -> None:
        s1 = self._summary("BTC/USDT", "LONG_RESEARCH")
        s2 = self._summary("ETH/USDT", "WATCHLIST_RESEARCH")
        assert _derive_mode(("BTC/USDT", "ETH/USDT"), {"BTC/USDT": s1, "ETH/USDT": s2}) == StrategyContractMode.LONG_RESEARCH_ONLY.value


class TestDetectBlockedReason:
    def test_missing_export(self, config: FreqtradeUniverseAdapterConfig) -> None:
        now = datetime.now(timezone.utc)
        assert _detect_blocked_reason(None, config, now) == MISSING_EXPORT_INPUT

    def test_research_only_false(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(research_only=False)
        now = datetime.now(timezone.utc)
        assert _detect_blocked_reason(export, config, now) == BLOCKED_EXPORT_INPUT

    def test_human_approval_required_false(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(human_approval_required=False)
        now = datetime.now(timezone.utc)
        assert _detect_blocked_reason(export, config, now) == BLOCKED_EXPORT_INPUT

    def test_upstream_blocked_export(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(reason_codes=(BLOCKED_EXPORT,))
        now = datetime.now(timezone.utc)
        assert _detect_blocked_reason(export, config, now) == BLOCKED_EXPORT_INPUT

    def test_upstream_missing_report_input(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(reason_codes=(MISSING_REPORT_INPUT,))
        now = datetime.now(timezone.utc)
        assert _detect_blocked_reason(export, config, now) == BLOCKED_EXPORT_INPUT

    def test_stale_export(self, config: FreqtradeUniverseAdapterConfig) -> None:
        generated_at = datetime.now(timezone.utc) - timedelta(seconds=600)
        export = _make_export_result(generated_at=generated_at)
        now = datetime.now(timezone.utc)
        assert _detect_blocked_reason(export, config, now) == STALE_EXPORT_INPUT

    def test_fresh_export(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result()
        now = datetime.now(timezone.utc)
        assert _detect_blocked_reason(export, config, now) is None


class TestBuildPairlist:
    def test_empty(self) -> None:
        assert _build_pairlist(()) == {"method": "StaticPairList", "pairs": []}

    def test_non_empty(self) -> None:
        assert _build_pairlist(("BTC/USDT",)) == {"method": "StaticPairList", "pairs": ["BTC/USDT"]}


class TestBuildFreqtradeUniverseAdapterResult:
    def test_missing_export_result(self, config: FreqtradeUniverseAdapterConfig) -> None:
        result = build_freqtrade_universe_adapter_result(None, config)
        assert isinstance(result, FreqtradeUniverseAdapterResult)
        assert result.report_id == "missing"
        assert result.whitelist == ()
        assert result.blacklist == ()
        assert result.pairlist == {"method": "StaticPairList", "pairs": []}
        assert MISSING_EXPORT_INPUT in result.reason_codes
        assert result.research_only is True
        assert result.human_approval_required is True

    def test_research_only_false(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(research_only=False)
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert BLOCKED_EXPORT_INPUT in result.reason_codes
        assert EMPTY_WHITELIST not in result.reason_codes
        assert result.research_only is True
        assert result.human_approval_required is True

    def test_human_approval_required_false(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(human_approval_required=False)
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert BLOCKED_EXPORT_INPUT in result.reason_codes

    def test_upstream_blocked_export(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT",),
            blacklist=(),
            reason_codes=(BLOCKED_EXPORT,),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert BLOCKED_EXPORT_INPUT in result.reason_codes

    def test_empty_upstream_whitelist(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(whitelist=(), reason_codes=(NO_INCLUDED_PAIRS,))
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert EMPTY_WHITELIST in result.reason_codes
        assert BLOCKED_EXPORT_INPUT not in result.reason_codes

    def test_stale_export(self, config: FreqtradeUniverseAdapterConfig) -> None:
        generated_at = datetime.now(timezone.utc) - timedelta(seconds=600)
        export = _make_export_result(
            generated_at=generated_at,
            whitelist=("BTC/USDT",),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert STALE_EXPORT_INPUT in result.reason_codes
        assert BLOCKED_EXPORT_INPUT not in result.reason_codes

    def test_pair_normalization_base_quote(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC_USDT", "ETH_USDT"),
            blacklist=("ADA_USDT",),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="BTC_USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="ETH_USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="ADA_USDT", state="EXCLUDED", classification="LONG_RESEARCH"
                ),
            ),
        )
        config_with_quote = FreqtradeUniverseAdapterConfig(pair_format="base/quote")
        result = build_freqtrade_universe_adapter_result(export, config_with_quote)
        assert result.whitelist == ("BTC/USDT", "ETH/USDT")  # sorted
        assert result.blacklist == ("ADA/USDT",)
        assert result.pairlist == {"method": "StaticPairList", "pairs": ["BTC/USDT", "ETH/USDT"]}

    def test_pair_normalization_base_quote_to_base_quote(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT",),
            blacklist=(),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
            ),
        )
        config_quote = FreqtradeUniverseAdapterConfig(pair_format="base_quote")
        result = build_freqtrade_universe_adapter_result(export, config_quote)
        assert result.whitelist == ("BTC_USDT",)
        assert result.pairlist == {"method": "StaticPairList", "pairs": ["BTC_USDT"]}

    def test_duplicate_pairs(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT", "BTC/USDT", "ETH/USDT"),
            blacklist=("ADA/USDT", "ADA/USDT"),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="ETH/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="ADA/USDT", state="EXCLUDED", classification="LONG_RESEARCH"
                ),
            ),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ("BTC/USDT", "ETH/USDT")
        assert result.blacklist == ("ADA/USDT",)
        assert DUPLICATE_PAIR in result.reason_codes

    def test_contradictory_pairs(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT", "ETH/USDT"),
            blacklist=("BTC/USDT",),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="ETH/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
            ),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert "BTC/USDT" not in result.whitelist
        assert "BTC/USDT" in result.blacklist
        assert "ETH/USDT" in result.whitelist
        assert CONTRADICTORY_PAIR in result.reason_codes

    def test_invalid_pair_format(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT", "BADPAIR"),
            blacklist=(),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
            ),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ("BTC/USDT",)
        assert INVALID_PAIR_FORMAT in result.reason_codes

    def test_strategy_contract_input_mode(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT", "ETH/USDT"),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="ETH/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
            ),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.strategy_contract_input["mode"] == StrategyContractMode.LONG_RESEARCH_ONLY.value
        assert result.strategy_contract_input["whitelist"] == ["BTC/USDT", "ETH/USDT"]
        assert result.strategy_contract_input["safety_flags"]["dry_run"] is True
        assert result.strategy_contract_input["safety_flags"]["live_trading_enabled"] is False

    def test_mixed_mode_blocks(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT", "ETH/USDT"),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="ETH/USDT", state="INCLUDED", classification="SHORT_RESEARCH"
                ),
            ),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.strategy_contract_input["mode"] == StrategyContractMode.BLOCK_ALL.value

    def test_per_pair_summary_sorted(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="ETH/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
            ),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.per_pair_summary[0].pair == "BTC/USDT"
        assert result.per_pair_summary[1].pair == "ETH/USDT"

    def test_deterministic_output(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result()
        result1 = build_freqtrade_universe_adapter_result(export, config)
        result2 = build_freqtrade_universe_adapter_result(export, config)
        assert result1 == result2

    def test_safety_flags_preserved_and_augmented(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(safety_flags={"custom_flag": True})
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.safety_flags["research_only"] is True
        assert result.safety_flags["human_approval_required"] is True
        assert result.safety_flags["custom_flag"] is True

    def test_metadata_preserved(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(metadata={"source": "test-source"})
        result = build_freqtrade_universe_adapter_result(export, config)
        assert dict(result.metadata) == {"source": "test-source"}

    def test_reason_codes_subset_of_adapter_codes(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT", "ETH/USDT"),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        for code in result.reason_codes:
            assert code in FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES

    def test_blacklist_emitted_when_whitelist_blocked(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT",),
            blacklist=("ETH/USDT",),
            research_only=False,
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert result.blacklist == ("ETH/USDT",)
        assert result.pairlist == {"method": "StaticPairList", "pairs": []}

    def test_blacklist_emitted_when_stale(self, config: FreqtradeUniverseAdapterConfig) -> None:
        generated_at = datetime.now(timezone.utc) - timedelta(seconds=600)
        export = _make_export_result(
            generated_at=generated_at,
            whitelist=("BTC/USDT",),
            blacklist=("ETH/USDT",),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert result.blacklist == ("ETH/USDT",)
        assert STALE_EXPORT_INPUT in result.reason_codes

    def test_all_reason_codes_included_for_valid_input(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result()
        result = build_freqtrade_universe_adapter_result(export, config)
        assert EXPORT_RESEARCH_ONLY in result.reason_codes
        assert EXPORT_HUMAN_APPROVAL_REQUIRED in result.reason_codes
        assert NO_FREQTRADE_RUNTIME_CONNECTION in result.reason_codes
        assert NO_AUTOMATIC_CONFIG_MUTATION in result.reason_codes

    def test_pairlist_sorted(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("ETH/USDT", "BTC/USDT", "ADA/USDT"),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="ETH/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="ADA/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
            ),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ("ADA/USDT", "BTC/USDT", "ETH/USDT")
        assert result.pairlist["pairs"] == ["ADA/USDT", "BTC/USDT", "ETH/USDT"]

    def test_empty_whitelist_after_contradiction(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT",),
            blacklist=("BTC/USDT",),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
            ),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert result.blacklist == ("BTC/USDT",)
        assert CONTRADICTORY_PAIR in result.reason_codes
        assert EMPTY_WHITELIST in result.reason_codes

    def test_watchlist_neutral_mode(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT",),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="WATCHLIST", classification="WATCHLIST_RESEARCH"
                ),
            ),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.strategy_contract_input["mode"] == StrategyContractMode.BLOCK_ALL.value

    def test_neutral_excluded_but_long_present(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = _make_export_result(
            whitelist=("BTC/USDT", "ETH/USDT"),
            per_pair_summary=(
                ControlledUniversePairExportSummary(
                    pair="BTC/USDT", state="INCLUDED", classification="LONG_RESEARCH"
                ),
                ControlledUniversePairExportSummary(
                    pair="ETH/USDT", state="WATCHLIST", classification="WATCHLIST_RESEARCH"
                ),
            ),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.strategy_contract_input["mode"] == StrategyContractMode.LONG_RESEARCH_ONLY.value
