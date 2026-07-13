"""Tests for the Freqtrade Universe Consumption Adapter models and public API."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from hunter.controlled_universe_export_adapter.models import (
    ControlledUniversePairExportSummary,
)
from hunter.freqtrade_universe_adapter import (
    BLOCKED_EXPORT_INPUT,
    CONTRADICTORY_PAIR,
    DUPLICATE_PAIR,
    EMPTY_WHITELIST,
    EXPORT_HUMAN_APPROVAL_REQUIRED,
    EXPORT_RESEARCH_ONLY,
    FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES,
    FREQTRADE_UNIVERSE_ADAPTER_VERSION,
    INVALID_PAIR_FORMAT,
    MISSING_EXPORT_INPUT,
    NO_AUTOMATIC_CONFIG_MUTATION,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    STALE_EXPORT_INPUT,
    FreqtradeUniverseAdapterConfig,
    FreqtradeUniverseAdapterError,
    FreqtradeUniverseAdapterResult,
    atomic_write_json_freqtrade_universe_adapter_result,
    atomic_write_markdown_freqtrade_universe_adapter_result,
    build_freqtrade_universe_adapter_result,
    freqtrade_universe_adapter_result_to_dict,
    freqtrade_universe_adapter_result_to_json_text,
    freqtrade_universe_adapter_result_to_markdown_text,
    write_freqtrade_universe_adapter_result,
)


class TestFreqtradeUniverseAdapterConfig:
    def test_default_config(self) -> None:
        config = FreqtradeUniverseAdapterConfig.default()
        assert config.output_dir == "data/freqtrade_universe_adapter"
        assert config.markdown_output_dir == "reports/freqtrade_universe_adapter"
        assert config.pair_format == "base/quote"
        assert config.stale_export_threshold_seconds == 300
        assert config.include_blacklist is True
        assert config.include_per_pair_summary is True
        assert config.json_filename == "latest_universe.json"
        assert config.markdown_filename == "latest_universe.md"
        assert config.pairlist_filename == "pairlist.json"
        assert config.strategy_contract_input_filename == "strategy_contract_input.json"
        assert dict(config.metadata) == {}

    def test_base_quote_format(self) -> None:
        config = FreqtradeUniverseAdapterConfig(pair_format="base_quote")
        assert config.pair_format == "base_quote"

    def test_invalid_pair_format(self) -> None:
        with pytest.raises(ValueError, match="pair_format must be"):
            FreqtradeUniverseAdapterConfig(pair_format="invalid")

    def test_empty_output_dir(self) -> None:
        with pytest.raises(ValueError, match="output_dir must be a non-empty string"):
            FreqtradeUniverseAdapterConfig(output_dir="  ")

    def test_empty_markdown_output_dir(self) -> None:
        with pytest.raises(ValueError, match="markdown_output_dir must be a non-empty string"):
            FreqtradeUniverseAdapterConfig(markdown_output_dir="")

    def test_empty_json_filename(self) -> None:
        with pytest.raises(ValueError, match="json_filename must be a non-empty string"):
            FreqtradeUniverseAdapterConfig(json_filename="  ")

    def test_non_bool_include_blacklist(self) -> None:
        with pytest.raises(ValueError, match="include_blacklist must be a bool"):
            FreqtradeUniverseAdapterConfig(include_blacklist="yes")  # type: ignore[arg-type]

    def test_non_bool_include_per_pair_summary(self) -> None:
        with pytest.raises(ValueError, match="include_per_pair_summary must be a bool"):
            FreqtradeUniverseAdapterConfig(include_per_pair_summary=1)  # type: ignore[arg-type]

    def test_negative_stale_threshold(self) -> None:
        with pytest.raises(ValueError, match="stale_export_threshold_seconds must be a non-negative integer"):
            FreqtradeUniverseAdapterConfig(stale_export_threshold_seconds=-1)

    def test_non_int_stale_threshold(self) -> None:
        with pytest.raises(ValueError, match="stale_export_threshold_seconds must be a non-negative integer"):
            FreqtradeUniverseAdapterConfig(stale_export_threshold_seconds="300")  # type: ignore[arg-type]

    def test_metadata_coerced(self) -> None:
        config = FreqtradeUniverseAdapterConfig(metadata={"source": "test"})
        assert dict(config.metadata) == {"source": "test"}

    def test_config_is_frozen(self) -> None:
        config = FreqtradeUniverseAdapterConfig.default()
        with pytest.raises(FrozenInstanceError):
            config.pair_format = "base_quote"  # type: ignore[misc]


class TestFreqtradeUniverseAdapterResult:
    def _make_result(
        self,
        **overrides: object,
    ) -> FreqtradeUniverseAdapterResult:
        defaults: dict[str, object] = {
            "report_id": "fua-test",
            "generated_at": datetime.now(timezone.utc),
            "whitelist": ("BTC/USDT", "ETH/USDT"),
            "blacklist": ("DOGE/USDT",),
            "pairlist": {"method": "StaticPairList", "pairs": ["BTC/USDT", "ETH/USDT"]},
            "strategy_contract_input": {
                "whitelist": ["BTC/USDT", "ETH/USDT"],
                "blacklist": ["DOGE/USDT"],
                "mode": "LONG_RESEARCH_ONLY",
                "safety_flags": {"dry_run": True, "live_trading_enabled": False},
                "metadata": {"source": "ControlledUniverseExportResult"},
            },
            "per_pair_summary": (),
            "reason_codes": (EXPORT_RESEARCH_ONLY,),
            "safety_flags": {"research_only": True, "human_approval_required": True},
        }
        defaults.update(overrides)
        return FreqtradeUniverseAdapterResult(**defaults)  # type: ignore[arg-type]

    def test_valid_result(self) -> None:
        result = self._make_result()
        assert result.report_id == "fua-test"
        assert result.version == FREQTRADE_UNIVERSE_ADAPTER_VERSION
        assert result.research_only is True
        assert result.human_approval_required is True
        assert result.whitelist == ("BTC/USDT", "ETH/USDT")
        assert result.blacklist == ("DOGE/USDT",)

    def test_empty_report_id(self) -> None:
        with pytest.raises(ValueError, match="report_id must be a non-empty string"):
            self._make_result(report_id="")

    def test_naive_datetime(self) -> None:
        with pytest.raises(ValueError, match="generated_at must be timezone-aware"):
            self._make_result(generated_at=datetime.now())  # type: ignore[arg-type]

    def test_non_bool_research_only(self) -> None:
        with pytest.raises(ValueError, match="research_only must be a bool"):
            self._make_result(research_only="yes")  # type: ignore[arg-type]

    def test_non_bool_human_approval_required(self) -> None:
        with pytest.raises(ValueError, match="human_approval_required must be a bool"):
            self._make_result(human_approval_required=1)  # type: ignore[arg-type]

    def test_research_only_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="research_only and human_approval_required must both be True"):
            self._make_result(research_only=False)

    def test_human_approval_required_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="research_only and human_approval_required must both be True"):
            self._make_result(human_approval_required=False)

    def test_unsupported_reason_code(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            self._make_result(reason_codes=("UNKNOWN_CODE",))

    def test_lists_coerced_to_tuple(self) -> None:
        result = self._make_result(
            whitelist=["BTC/USDT"],
            blacklist=["ETH/USDT"],
            per_pair_summary=[],
            reason_codes=[EXPORT_RESEARCH_ONLY],
        )
        assert isinstance(result.whitelist, tuple)
        assert isinstance(result.blacklist, tuple)
        assert isinstance(result.per_pair_summary, tuple)
        assert isinstance(result.reason_codes, tuple)

    def test_all_reason_codes_supported(self) -> None:
        for code in FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES:
            result = self._make_result(reason_codes=(code,))
            assert result.reason_codes == (code,)

    def test_empty_whitelist_pair(self) -> None:
        with pytest.raises(ValueError, match="whitelist pairs must be non-empty strings"):
            self._make_result(whitelist=("",))

    def test_empty_blacklist_pair(self) -> None:
        with pytest.raises(ValueError, match="blacklist pairs must be non-empty strings"):
            self._make_result(blacklist=("  ",))

    def test_invalid_pairlist_type(self) -> None:
        with pytest.raises(ValueError, match="pairlist must be a dict"):
            self._make_result(pairlist=["BTC/USDT"])  # type: ignore[arg-type]

    def test_invalid_strategy_contract_input_type(self) -> None:
        with pytest.raises(ValueError, match="strategy_contract_input must be a dict"):
            self._make_result(strategy_contract_input=None)  # type: ignore[arg-type]

    def test_invalid_safety_flags_type(self) -> None:
        with pytest.raises(ValueError, match="safety_flags must be a dict"):
            self._make_result(safety_flags=None)  # type: ignore[arg-type]

    def test_invalid_safety_flags_values(self) -> None:
        with pytest.raises(ValueError, match=r"safety_flags must be a dict\[str, bool\]"):
            self._make_result(safety_flags={"research_only": "true"})  # type: ignore[arg-type]

    def test_per_pair_summary_preserved(self) -> None:
        summary = ControlledUniversePairExportSummary(
            pair="BTC/USDT",
            state="INCLUDED",
            classification="LONG_RESEARCH",
            reason_codes=("PASSED",),
            human_note="ok",
        )
        result = self._make_result(per_pair_summary=(summary,))
        assert result.per_pair_summary == (summary,)

    def test_result_is_frozen(self) -> None:
        result = self._make_result()
        with pytest.raises(FrozenInstanceError):
            result.report_id = "changed"  # type: ignore[misc]

    def test_metadata_coerced(self) -> None:
        result = self._make_result(metadata={"source": "test"})
        assert dict(result.metadata) == {"source": "test"}


class TestReasonCodesAndVersion:
    def test_version_constant(self) -> None:
        assert FREQTRADE_UNIVERSE_ADAPTER_VERSION == "0.55.0-dev"

    def test_reason_codes_complete(self) -> None:
        expected = {
            MISSING_EXPORT_INPUT,
            BLOCKED_EXPORT_INPUT,
            EMPTY_WHITELIST,
            INVALID_PAIR_FORMAT,
            DUPLICATE_PAIR,
            CONTRADICTORY_PAIR,
            EXPORT_RESEARCH_ONLY,
            EXPORT_HUMAN_APPROVAL_REQUIRED,
            NO_FREQTRADE_RUNTIME_CONNECTION,
            NO_AUTOMATIC_CONFIG_MUTATION,
            STALE_EXPORT_INPUT,
        }
        assert FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES == expected

    def test_error_class(self) -> None:
        assert issubclass(FreqtradeUniverseAdapterError, Exception)


class TestPublicApi:
    def test_all_reason_codes_exported(self) -> None:
        from hunter.freqtrade_universe_adapter import (
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
        )

        assert all(
            code in FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES
            for code in (
                MISSING_EXPORT_INPUT,
                BLOCKED_EXPORT_INPUT,
                EMPTY_WHITELIST,
                INVALID_PAIR_FORMAT,
                DUPLICATE_PAIR,
                CONTRADICTORY_PAIR,
                EXPORT_RESEARCH_ONLY,
                EXPORT_HUMAN_APPROVAL_REQUIRED,
                NO_FREQTRADE_RUNTIME_CONNECTION,
                NO_AUTOMATIC_CONFIG_MUTATION,
                STALE_EXPORT_INPUT,
            )
        )

    def test_engine_is_importable(self) -> None:
        assert callable(build_freqtrade_universe_adapter_result)

    def test_writer_exports_are_callable(self) -> None:
        result = FreqtradeUniverseAdapterResult(
            report_id="fua-test",
            generated_at=datetime.now(timezone.utc),
            whitelist=(),
            blacklist=(),
            pairlist={},
            strategy_contract_input={},
            per_pair_summary=(),
            reason_codes=(MISSING_EXPORT_INPUT,),
            safety_flags={"research_only": True, "human_approval_required": True},
        )
        assert isinstance(freqtrade_universe_adapter_result_to_dict(result), dict)
        assert isinstance(freqtrade_universe_adapter_result_to_json_text(result), str)
        assert isinstance(freqtrade_universe_adapter_result_to_markdown_text(result), str)
