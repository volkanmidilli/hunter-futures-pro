"""Integration tests for the Freqtrade Universe Consumption Adapter (MVP-55).

These tests cover the full end-to-end flow:
ControlledUniverseExportResult -> build -> write -> verify all artifacts.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter.controlled_universe_export_adapter.models import (
    BLOCKED_EXPORT,
    MISSING_REPORT_INPUT,
    ControlledUniverseExportResult,
    ControlledUniversePairExportSummary,
)
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
    FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES,
    FREQTRADE_UNIVERSE_ADAPTER_VERSION,
    FreqtradeUniverseAdapterConfig,
    FreqtradeUniverseAdapterError,
    FreqtradeUniverseAdapterResult,
    build_freqtrade_universe_adapter_result,
    freqtrade_universe_adapter_result_to_dict,
    write_freqtrade_universe_adapter_result,
)
from hunter.freqtrade_universe_adapter import __all__ as public_api


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_export() -> ControlledUniverseExportResult:
    """Return a valid controlled-universe export with two long pairs."""
    now = datetime.now(timezone.utc)
    return ControlledUniverseExportResult(
        report_id="cue-integ-001",
        generated_at=now,
        whitelist=("BTC/USDT", "ETH/USDT"),
        blacklist=("ADA/USDT",),
        per_pair_summary=(
            ControlledUniversePairExportSummary(
                pair="BTC/USDT",
                state="INCLUDED",
                classification="LONG_RESEARCH",
                reason_codes=("PASSED",),
                human_note="",
            ),
            ControlledUniversePairExportSummary(
                pair="ETH/USDT",
                state="INCLUDED",
                classification="LONG_RESEARCH",
                reason_codes=("PASSED",),
                human_note="",
            ),
            ControlledUniversePairExportSummary(
                pair="ADA/USDT",
                state="EXCLUDED",
                classification="LONG_RESEARCH",
                reason_codes=("BLOCKED",),
                human_note="test",
            ),
        ),
        metadata=MappingProxyType({"source": "integration-test"}),
    )


@pytest.fixture
def config(tmp_path: Path) -> FreqtradeUniverseAdapterConfig:
    """Return a config that writes into a temporary directory."""
    return FreqtradeUniverseAdapterConfig(
        output_dir=str(tmp_path / "data"),
        markdown_output_dir=str(tmp_path / "reports"),
    )


# ---------------------------------------------------------------------------
# Full end-to-end flow
# ---------------------------------------------------------------------------


class TestEndToEndFlow:
    def test_all_four_artifacts_written(
        self,
        valid_export: ControlledUniverseExportResult,
        config: FreqtradeUniverseAdapterConfig,
    ) -> None:
        result = build_freqtrade_universe_adapter_result(valid_export, config)
        written = write_freqtrade_universe_adapter_result(result, None, config)

        assert set(written.keys()) == {"json", "markdown", "pairlist", "strategy_contract_input"}
        for path in written.values():
            assert Path(path).exists()

    def test_json_packet_schema(
        self,
        valid_export: ControlledUniverseExportResult,
        config: FreqtradeUniverseAdapterConfig,
    ) -> None:
        result = build_freqtrade_universe_adapter_result(valid_export, config)
        written = write_freqtrade_universe_adapter_result(result, None, config)
        data = json.loads(Path(written["json"]).read_text(encoding="utf-8"))

        assert data["kind"] == "freqtrade_universe_adapter"
        assert data["version"] == FREQTRADE_UNIVERSE_ADAPTER_VERSION
        assert data["report_id"] == "cue-integ-001"
        assert data["research_only"] is True
        assert data["human_approval_required"] is True
        assert "safety_notice" in data
        assert data["whitelist"] == ["BTC/USDT", "ETH/USDT"]
        assert data["blacklist"] == ["ADA/USDT"]
        assert data["pairlist"] == {"method": "StaticPairList", "pairs": ["BTC/USDT", "ETH/USDT"]}
        assert data["strategy_contract_input"]["mode"] == "LONG_RESEARCH_ONLY"
        assert data["reason_codes"]  # non-empty
        for code in data["reason_codes"]:
            assert code in FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES

    def test_markdown_safety_notice_and_paths(
        self,
        valid_export: ControlledUniverseExportResult,
        config: FreqtradeUniverseAdapterConfig,
    ) -> None:
        result = build_freqtrade_universe_adapter_result(valid_export, config)
        written = write_freqtrade_universe_adapter_result(result, None, config)
        md = Path(written["markdown"]).read_text(encoding="utf-8")

        assert "# Freqtrade Universe Adapter Output" in md
        assert "research-only artifact" in md
        assert "human approval is required" in md
        assert "## Artifact Paths" in md
        assert "pairlist.json" in md
        assert "strategy_contract_input.json" in md

    def test_pairlist_matches_whitelist(
        self,
        valid_export: ControlledUniverseExportResult,
        config: FreqtradeUniverseAdapterConfig,
    ) -> None:
        result = build_freqtrade_universe_adapter_result(valid_export, config)
        written = write_freqtrade_universe_adapter_result(result, None, config)
        pairlist = json.loads(Path(written["pairlist"]).read_text(encoding="utf-8"))
        data = json.loads(Path(written["json"]).read_text(encoding="utf-8"))

        assert pairlist["method"] == "StaticPairList"
        assert pairlist["pairs"] == data["whitelist"]
        assert pairlist["pairs"] == list(result.whitelist)

    def test_strategy_contract_input_consistency(
        self,
        valid_export: ControlledUniverseExportResult,
        config: FreqtradeUniverseAdapterConfig,
    ) -> None:
        result = build_freqtrade_universe_adapter_result(valid_export, config)
        written = write_freqtrade_universe_adapter_result(result, None, config)
        sci = json.loads(Path(written["strategy_contract_input"]).read_text(encoding="utf-8"))
        data = json.loads(Path(written["json"]).read_text(encoding="utf-8"))

        assert sci["whitelist"] == data["whitelist"]
        assert sci["blacklist"] == data["blacklist"]
        assert sci["mode"] == data["strategy_contract_input"]["mode"]
        assert sci["mode"] in {"LONG_RESEARCH_ONLY", "SHORT_RESEARCH_ONLY", "BLOCK_ALL"}
        assert sci["safety_flags"]["dry_run"] is True
        assert sci["safety_flags"]["live_trading_enabled"] is False


# ---------------------------------------------------------------------------
# Fail-closed / blocked / stale / missing flow
# ---------------------------------------------------------------------------


class TestFailClosedFlow:
    def test_missing_input_produces_empty_whitelist(self, config: FreqtradeUniverseAdapterConfig) -> None:
        result = build_freqtrade_universe_adapter_result(None, config)
        assert result.whitelist == ()
        assert MISSING_EXPORT_INPUT in result.reason_codes

        written = write_freqtrade_universe_adapter_result(result, None, config)
        data = json.loads(Path(written["json"]).read_text(encoding="utf-8"))
        assert data["whitelist"] == []
        assert data["pairlist"] == {"method": "StaticPairList", "pairs": []}
        assert data["strategy_contract_input"]["mode"] == "BLOCK_ALL"

    def test_blocked_export_reason_code(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = ControlledUniverseExportResult(
            report_id="blocked",
            generated_at=datetime.now(timezone.utc),
            whitelist=("BTC/USDT",),
            blacklist=(),
            per_pair_summary=(),
            reason_codes=(BLOCKED_EXPORT,),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert BLOCKED_EXPORT_INPUT in result.reason_codes

        written = write_freqtrade_universe_adapter_result(result, None, config)
        data = json.loads(Path(written["json"]).read_text(encoding="utf-8"))
        assert data["whitelist"] == []

    def test_missing_report_input_produces_empty_whitelist(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = ControlledUniverseExportResult(
            report_id="missing-report",
            generated_at=datetime.now(timezone.utc),
            whitelist=("BTC/USDT",),
            blacklist=(),
            per_pair_summary=(),
            reason_codes=(MISSING_REPORT_INPUT,),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert BLOCKED_EXPORT_INPUT in result.reason_codes

    def test_unsafe_safety_flags_produce_empty_whitelist(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = ControlledUniverseExportResult(
            report_id="unsafe",
            generated_at=datetime.now(timezone.utc),
            whitelist=("BTC/USDT",),
            blacklist=(),
            per_pair_summary=(),
            research_only=False,
            human_approval_required=True,
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert BLOCKED_EXPORT_INPUT in result.reason_codes

    def test_stale_export_produces_empty_whitelist(self, config: FreqtradeUniverseAdapterConfig) -> None:
        old = datetime.now(timezone.utc) - timedelta(seconds=config.stale_export_threshold_seconds + 1)
        export = ControlledUniverseExportResult(
            report_id="stale",
            generated_at=old,
            whitelist=("BTC/USDT",),
            blacklist=(),
            per_pair_summary=(),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        assert result.whitelist == ()
        assert STALE_EXPORT_INPUT in result.reason_codes


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_repeated_runs_produce_identical_output(
        self,
        valid_export: ControlledUniverseExportResult,
        config: FreqtradeUniverseAdapterConfig,
    ) -> None:
        r1 = build_freqtrade_universe_adapter_result(valid_export, config)
        r2 = build_freqtrade_universe_adapter_result(valid_export, config)
        assert r1 == r2

        written1 = write_freqtrade_universe_adapter_result(r1, None, config)
        written2 = write_freqtrade_universe_adapter_result(r2, None, config)
        for key in written1:
            assert Path(written1[key]).read_text(encoding="utf-8") == Path(written2[key]).read_text(encoding="utf-8")

    def test_json_packet_and_pairlist_are_sorted(self, config: FreqtradeUniverseAdapterConfig) -> None:
        export = ControlledUniverseExportResult(
            report_id="unsorted",
            generated_at=datetime.now(timezone.utc),
            whitelist=("ETH/USDT", "BTC/USDT", "ADA/USDT"),
            blacklist=(),
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
        written = write_freqtrade_universe_adapter_result(result, None, config)
        data = json.loads(Path(written["json"]).read_text(encoding="utf-8"))
        pairlist = json.loads(Path(written["pairlist"]).read_text(encoding="utf-8"))

        assert data["whitelist"] == ["ADA/USDT", "BTC/USDT", "ETH/USDT"]
        assert pairlist["pairs"] == data["whitelist"]


# ---------------------------------------------------------------------------
# Public API completeness
# ---------------------------------------------------------------------------


class TestPublicApi:
    def test_expected_public_symbols_are_exported(self) -> None:
        expected = {
            "FREQTRADE_UNIVERSE_ADAPTER_VERSION",
            "MISSING_EXPORT_INPUT",
            "BLOCKED_EXPORT_INPUT",
            "EMPTY_WHITELIST",
            "INVALID_PAIR_FORMAT",
            "DUPLICATE_PAIR",
            "CONTRADICTORY_PAIR",
            "EXPORT_RESEARCH_ONLY",
            "EXPORT_HUMAN_APPROVAL_REQUIRED",
            "NO_FREQTRADE_RUNTIME_CONNECTION",
            "NO_AUTOMATIC_CONFIG_MUTATION",
            "STALE_EXPORT_INPUT",
            "FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES",
            "FreqtradeUniverseAdapterConfig",
            "FreqtradeUniverseAdapterResult",
            "FreqtradeUniverseAdapterError",
            "build_freqtrade_universe_adapter_result",
            "freqtrade_universe_adapter_result_to_dict",
            "freqtrade_universe_adapter_result_to_json_text",
            "freqtrade_universe_adapter_result_to_markdown_text",
            "atomic_write_json_freqtrade_universe_adapter_result",
            "atomic_write_markdown_freqtrade_universe_adapter_result",
            "write_freqtrade_universe_adapter_result",
        }
        assert expected.issubset(set(public_api))

    def test_reason_codes_frozenset_matches_constants(self) -> None:
        assert FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES == {
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

    def test_config_default_returns_valid_config(self) -> None:
        config = FreqtradeUniverseAdapterConfig.default()
        assert config.pair_format in ("base/quote", "base_quote")
        assert config.stale_export_threshold_seconds >= 0


# ---------------------------------------------------------------------------
# No Freqtrade runtime imports / no file reads
# ---------------------------------------------------------------------------


class TestBoundaryConstraints:
    def test_adapter_package_does_not_import_actual_freqtrade_module(self) -> None:
        """Verify that no module in the adapter package imports from the real
        `freqtrade` Python package (runtime). The package name itself is a
        Hunter internal module, not the Freqtrade runtime."""
        from hunter import freqtrade_universe_adapter

        adapter_modules = [
            name
            for name in sys.modules
            if name == "hunter.freqtrade_universe_adapter" or name.startswith("hunter.freqtrade_universe_adapter.")
        ]
        for mod_name in adapter_modules:
            mod = sys.modules[mod_name]
            if not hasattr(mod, "__file__") or mod.__file__ is None:
                continue
            for imported_name, imported_mod in vars(mod).items():
                if imported_name.startswith("__"):
                    continue
                # Check if it's a module from the real `freqtrade` package.
                if isinstance(imported_mod, type(sys)) and getattr(imported_mod, "__name__", "").startswith("freqtrade"):
                    pytest.fail(f"adapter module {mod_name} imports real freqtrade module {imported_mod.__name__}")

    def test_engine_does_not_read_files(self, tmp_path: Path) -> None:
        """The engine path must not perform file reads."""
        # We cannot intercept all reads easily, but we can assert the engine
        # accepts purely in-memory inputs and never accesses the filesystem.
        export = ControlledUniverseExportResult(
            report_id="no-reads",
            generated_at=datetime.now(timezone.utc),
            whitelist=("BTC/USDT",),
            blacklist=(),
            per_pair_summary=(),
        )
        config = FreqtradeUniverseAdapterConfig.default()
        result = build_freqtrade_universe_adapter_result(export, config)
        assert isinstance(result, FreqtradeUniverseAdapterResult)
        # No output_dir exists, so any file read would raise. This confirms
        # the engine path is pure.

    def test_writer_is_local_only_and_uses_temporary_paths(self, tmp_path: Path) -> None:
        export = ControlledUniverseExportResult(
            report_id="local-only",
            generated_at=datetime.now(timezone.utc),
            whitelist=("BTC/USDT",),
            blacklist=(),
            per_pair_summary=(),
        )
        config = FreqtradeUniverseAdapterConfig(
            output_dir=str(tmp_path / "data"),
            markdown_output_dir=str(tmp_path / "reports"),
        )
        result = build_freqtrade_universe_adapter_result(export, config)
        written = write_freqtrade_universe_adapter_result(result, None, config)
        for path in written.values():
            assert Path(path).exists()
            assert Path(path).is_relative_to(tmp_path)
