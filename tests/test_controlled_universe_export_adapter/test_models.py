"""Tests for controlled_universe_export_adapter models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.controlled_universe_export_adapter.models import (
    BLOCKED_EXPORT,
    CONTROLLED_UNIVERSE_EXPORT_REASON_CODES,
    CONTROLLED_UNIVERSE_EXPORT_VERSION,
    EXPORT_HUMAN_APPROVAL_REQUIRED,
    EXPORT_RESEARCH_ONLY,
    MISSING_REPORT_INPUT,
    NO_AUTOMATIC_CONFIG_MUTATION,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    NO_INCLUDED_PAIRS,
    ControlledUniverseExportConfig,
    ControlledUniverseExportError,
    ControlledUniverseExportResult,
    ControlledUniversePairExportSummary,
)


class TestControlledUniverseExportConfig:
    def test_default_config(self) -> None:
        config = ControlledUniverseExportConfig.default()
        assert config.pair_format == "base/quote"
        assert config.output_dir == "data/controlled_universe_export"
        assert config.markdown_output_dir == "reports/controlled_universe_export"
        assert config.json_filename == "latest_export.json"
        assert config.markdown_filename == "latest_export.md"
        assert config.include_watchlist_in_whitelist is False
        assert config.include_reason_codes_in_summary is True

    def test_base_quote_format(self) -> None:
        config = ControlledUniverseExportConfig(pair_format="base_quote")
        assert config.pair_format == "base_quote"

    def test_invalid_pair_format(self) -> None:
        with pytest.raises(ValueError, match="pair_format must be"):
            ControlledUniverseExportConfig(pair_format="invalid")

    def test_empty_output_dir(self) -> None:
        with pytest.raises(ValueError, match="output_dir must be a non-empty string"):
            ControlledUniverseExportConfig(output_dir="  ")

    def test_non_bool_include_watchlist(self) -> None:
        with pytest.raises(ValueError, match="include_watchlist_in_whitelist must be a bool"):
            ControlledUniverseExportConfig(include_watchlist_in_whitelist="yes")  # type: ignore[arg-type]


class TestControlledUniversePairExportSummary:
    def test_valid_summary(self) -> None:
        summary = ControlledUniversePairExportSummary(
            pair="BTC/USDT",
            state="INCLUDED",
            classification="LONG_RESEARCH",
            reason_codes=("PASSED_UNIVERSE_FILTER",),
            human_note="passed controlled universe filter",
        )
        assert summary.pair == "BTC/USDT"
        assert summary.state == "INCLUDED"
        assert summary.reason_codes == ("PASSED_UNIVERSE_FILTER",)

    def test_empty_pair(self) -> None:
        with pytest.raises(ValueError, match="pair must be a non-empty string"):
            ControlledUniversePairExportSummary(
                pair="",
                state="INCLUDED",
                classification="LONG_RESEARCH",
                human_note="",
            )

    def test_reason_codes_coerced(self) -> None:
        summary = ControlledUniversePairExportSummary(
            pair="ETH/USDT",
            state="WATCHLIST",
            classification="WATCHLIST_RESEARCH",
            reason_codes=["HUMAN_RESEARCH_ONLY"],
            human_note="watchlist",
        )
        assert isinstance(summary.reason_codes, tuple)
        assert summary.reason_codes == ("HUMAN_RESEARCH_ONLY",)


class TestControlledUniverseExportResult:
    def test_valid_result(self) -> None:
        now = datetime.now(timezone.utc)
        result = ControlledUniverseExportResult(
            report_id="cue-test",
            generated_at=now,
            whitelist=("BTC/USDT",),
            blacklist=("ETH/USDT",),
            per_pair_summary=(),
            reason_codes=(EXPORT_RESEARCH_ONLY,),
        )
        assert result.report_id == "cue-test"
        assert result.research_only is True
        assert result.human_approval_required is True

    def test_empty_report_id(self) -> None:
        with pytest.raises(ValueError, match="report_id must be a non-empty string"):
            ControlledUniverseExportResult(
                report_id="",
                generated_at=datetime.now(timezone.utc),
                whitelist=(),
                blacklist=(),
                per_pair_summary=(),
            )

    def test_naive_datetime(self) -> None:
        with pytest.raises(ValueError, match="generated_at must be timezone-aware"):
            ControlledUniverseExportResult(
                report_id="cue-test",
                generated_at=datetime.now(),  # type: ignore[arg-type]
                whitelist=(),
                blacklist=(),
                per_pair_summary=(),
            )

    def test_non_bool_research_only(self) -> None:
        with pytest.raises(ValueError, match="research_only must be a bool"):
            ControlledUniverseExportResult(
                report_id="cue-test",
                generated_at=datetime.now(timezone.utc),
                whitelist=(),
                blacklist=(),
                per_pair_summary=(),
                research_only="yes",  # type: ignore[arg-type]
            )

    def test_unsupported_reason_code(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            ControlledUniverseExportResult(
                report_id="cue-test",
                generated_at=datetime.now(timezone.utc),
                whitelist=(),
                blacklist=(),
                per_pair_summary=(),
                reason_codes=("UNKNOWN_CODE",),
            )

    def test_lists_coerced_to_tuple(self) -> None:
        result = ControlledUniverseExportResult(
            report_id="cue-test",
            generated_at=datetime.now(timezone.utc),
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
        for code in CONTROLLED_UNIVERSE_EXPORT_REASON_CODES:
            result = ControlledUniverseExportResult(
                report_id="cue-test",
                generated_at=datetime.now(timezone.utc),
                whitelist=(),
                blacklist=(),
                per_pair_summary=(),
                reason_codes=(code,),
            )
            assert result.reason_codes == (code,)

    def test_version_constant(self) -> None:
        assert CONTROLLED_UNIVERSE_EXPORT_VERSION == "0.53.0-dev"

    def test_error_class(self) -> None:
        assert issubclass(ControlledUniverseExportError, Exception)
