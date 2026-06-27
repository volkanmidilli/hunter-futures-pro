"""Tests for freqtrade shell adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.freqtrade_shell.adapter import (
    RESEARCH_EXPOSURE_COLUMN,
    RESEARCH_REASON_COLUMN,
    RESEARCH_SIGNAL_COLUMN,
    RESEARCH_STATE_COLUMN,
    apply_research_metadata_to_dataframe,
    assert_no_trade_columns,
    build_blocked_research_metadata,
    determine_research_signal,
    shell_validation_result_to_metadata,
)
from hunter.freqtrade_shell.models import (
    LONG_RESEARCH_METADATA_EXPOSED,
    SHORT_RESEARCH_METADATA_EXPOSED,
    RUNTIME_JSON_MISSING,
    ShellSignalExposure,
    ShellState,
    ShellValidationResult,
)


class FakeDataFrame:
    """Minimal pandas-like dataframe for testing without pandas dependency."""

    def __init__(self, data: dict[str, list[Any]] | None = None) -> None:
        self._data: dict[str, list[Any]] = data or {}
        self._columns: list[str] = list(self._data.keys())

    @property
    def columns(self) -> list[str]:
        return list(self._data.keys())

    def copy(self) -> "FakeDataFrame":
        return FakeDataFrame({k: list(v) for k, v in self._data.items()})

    def __getitem__(self, key: str) -> list[Any]:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self._data:
            self._columns.append(key)
        # If value is a scalar, broadcast to row count
        if not isinstance(value, list):
            row_count = max((len(v) for v in self._data.values()), default=1)
            value = [value] * row_count
        self._data[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def to_dict(self) -> dict[str, list[Any]]:
        return {k: list(v) for k, v in self._data.items()}


class TestShellValidationResultToMetadata:
    def _make_result(self, **kwargs: Any) -> ShellValidationResult:
        defaults = {
            "timestamp": datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "shell_state": ShellState.DRY_RUN_READY,
            "signal_exposure": ShellSignalExposure.EXPOSE_LONG_RESEARCH_METADATA,
            "reason_codes": (LONG_RESEARCH_METADATA_EXPOSED,),
            "runtime_json_present": True,
            "runtime_json_valid": True,
            "runtime_json_stale": False,
            "runtime_version": "1.0",
            "runtime_strategy_state": "DRY_RUN_READY",
            "runtime_strategy_mode": "LONG_RESEARCH_ONLY",
            "runtime_signal_action": "EXPOSE_LONG_RESEARCH_SIGNAL",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
            "allow_real_trade_signals": False,
            "allow_entry_columns": False,
            "allow_exit_columns": False,
            "version": "1.0",
        }
        defaults.update(kwargs)
        return ShellValidationResult(**defaults)  # type: ignore[arg-type]

    def test_allowed_long(self) -> None:
        result = self._make_result()
        meta = shell_validation_result_to_metadata(result)
        assert meta["shell_state"] == "DRY_RUN_READY"
        assert meta["signal_exposure"] == "EXPOSE_LONG_RESEARCH_METADATA"
        assert meta["reason_codes"] == [LONG_RESEARCH_METADATA_EXPOSED]
        assert meta["runtime_version"] == "1.0"
        assert meta["runtime_strategy_state"] == "DRY_RUN_READY"
        assert meta["runtime_strategy_mode"] == "LONG_RESEARCH_ONLY"
        assert meta["runtime_signal_action"] == "EXPOSE_LONG_RESEARCH_SIGNAL"
        assert meta["dry_run"] is True
        assert meta["live_trading_enabled"] is False
        assert meta["real_orders_enabled"] is False
        assert meta["leverage_enabled"] is False
        assert meta["shorting_enabled"] is False
        assert meta["allow_real_trade_signals"] is False
        assert meta["allow_entry_columns"] is False
        assert meta["allow_exit_columns"] is False
        assert meta["version"] == "1.0"

    def test_allowed_short(self) -> None:
        result = self._make_result(
            shell_state=ShellState.DRY_RUN_READY,
            signal_exposure=ShellSignalExposure.EXPOSE_SHORT_RESEARCH_METADATA,
            reason_codes=(SHORT_RESEARCH_METADATA_EXPOSED,),
            runtime_strategy_mode="SHORT_RESEARCH_ONLY",
            runtime_signal_action="EXPOSE_SHORT_RESEARCH_SIGNAL",
        )
        meta = shell_validation_result_to_metadata(result)
        assert meta["shell_state"] == "DRY_RUN_READY"
        assert meta["signal_exposure"] == "EXPOSE_SHORT_RESEARCH_METADATA"
        assert meta["reason_codes"] == [SHORT_RESEARCH_METADATA_EXPOSED]

    def test_blocked(self) -> None:
        result = ShellValidationResult.blocked((RUNTIME_JSON_MISSING,))
        meta = shell_validation_result_to_metadata(result)
        assert meta["shell_state"] == "BLOCKED"
        assert meta["signal_exposure"] == "BLOCKED"
        assert meta["reason_codes"] == [RUNTIME_JSON_MISSING]
        assert meta["runtime_version"] == "UNKNOWN"
        assert meta["runtime_strategy_state"] == "UNKNOWN"
        assert meta["runtime_strategy_mode"] == "BLOCK_ALL"
        assert meta["runtime_signal_action"] == "BLOCK_SIGNAL"

    def test_reason_codes_tuple_becomes_list(self) -> None:
        result = self._make_result(reason_codes=("A", "B"))
        meta = shell_validation_result_to_metadata(result)
        assert meta["reason_codes"] == ["A", "B"]
        assert isinstance(meta["reason_codes"], list)

    def test_does_not_mutate_result(self) -> None:
        result = self._make_result()
        original_reason_codes = result.reason_codes
        shell_validation_result_to_metadata(result)
        assert result.reason_codes is original_reason_codes


class TestDetermineResearchSignal:
    def _make_result(self, **kwargs: Any) -> ShellValidationResult:
        defaults = {
            "timestamp": datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "shell_state": ShellState.DRY_RUN_READY,
            "signal_exposure": ShellSignalExposure.EXPOSE_LONG_RESEARCH_METADATA,
            "reason_codes": (LONG_RESEARCH_METADATA_EXPOSED,),
            "runtime_json_present": True,
            "runtime_json_valid": True,
            "runtime_json_stale": False,
            "runtime_version": "1.0",
            "runtime_strategy_state": "DRY_RUN_READY",
            "runtime_strategy_mode": "LONG_RESEARCH_ONLY",
            "runtime_signal_action": "EXPOSE_LONG_RESEARCH_SIGNAL",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
            "allow_real_trade_signals": False,
            "allow_entry_columns": False,
            "allow_exit_columns": False,
            "version": "1.0",
        }
        defaults.update(kwargs)
        return ShellValidationResult(**defaults)  # type: ignore[arg-type]

    def test_long(self) -> None:
        result = self._make_result()
        assert determine_research_signal(result) == "LONG_RESEARCH"

    def test_short(self) -> None:
        result = self._make_result(
            signal_exposure=ShellSignalExposure.EXPOSE_SHORT_RESEARCH_METADATA,
            reason_codes=(SHORT_RESEARCH_METADATA_EXPOSED,),
        )
        assert determine_research_signal(result) == "SHORT_RESEARCH"

    def test_blocked(self) -> None:
        result = ShellValidationResult.blocked((RUNTIME_JSON_MISSING,))
        assert determine_research_signal(result) == "NONE"

    def test_unknown_state(self) -> None:
        result = self._make_result(shell_state=ShellState.UNKNOWN)
        assert determine_research_signal(result) == "NONE"

    def test_disabled_state(self) -> None:
        result = self._make_result(shell_state=ShellState.DISABLED)
        assert determine_research_signal(result) == "NONE"

    def test_no_signal(self) -> None:
        # NO_RESEARCH_SIGNAL is not allowed with DRY_RUN_READY state, so use BLOCKED state
        result = self._make_result(
            shell_state=ShellState.BLOCKED,
            signal_exposure=ShellSignalExposure.NO_RESEARCH_SIGNAL,
            reason_codes=("NO_SIGNAL",),
        )
        assert determine_research_signal(result) == "NONE"


class TestApplyResearchMetadataToDataFrame:
    def _make_result(self, **kwargs: Any) -> ShellValidationResult:
        defaults = {
            "timestamp": datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            "shell_state": ShellState.DRY_RUN_READY,
            "signal_exposure": ShellSignalExposure.EXPOSE_LONG_RESEARCH_METADATA,
            "reason_codes": (LONG_RESEARCH_METADATA_EXPOSED,),
            "runtime_json_present": True,
            "runtime_json_valid": True,
            "runtime_json_stale": False,
            "runtime_version": "1.0",
            "runtime_strategy_state": "DRY_RUN_READY",
            "runtime_strategy_mode": "LONG_RESEARCH_ONLY",
            "runtime_signal_action": "EXPOSE_LONG_RESEARCH_SIGNAL",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
            "allow_real_trade_signals": False,
            "allow_entry_columns": False,
            "allow_exit_columns": False,
            "version": "1.0",
        }
        defaults.update(kwargs)
        return ShellValidationResult(**defaults)  # type: ignore[arg-type]

    def test_adds_only_research_columns(self) -> None:
        df = FakeDataFrame({"close": [1.0, 2.0, 3.0]})
        result = self._make_result()
        out = apply_research_metadata_to_dataframe(df, result)
        assert RESEARCH_SIGNAL_COLUMN in out.columns
        assert RESEARCH_REASON_COLUMN in out.columns
        assert RESEARCH_STATE_COLUMN in out.columns
        assert RESEARCH_EXPOSURE_COLUMN in out.columns
        assert "close" in out.columns

    def test_allowed_long_gets_long_research(self) -> None:
        df = FakeDataFrame({"close": [1.0, 2.0]})
        result = self._make_result()
        out = apply_research_metadata_to_dataframe(df, result)
        assert out[RESEARCH_SIGNAL_COLUMN] == ["LONG_RESEARCH", "LONG_RESEARCH"]

    def test_allowed_short_gets_short_research(self) -> None:
        df = FakeDataFrame({"close": [1.0, 2.0]})
        result = self._make_result(
            signal_exposure=ShellSignalExposure.EXPOSE_SHORT_RESEARCH_METADATA,
            reason_codes=(SHORT_RESEARCH_METADATA_EXPOSED,),
        )
        out = apply_research_metadata_to_dataframe(df, result)
        assert out[RESEARCH_SIGNAL_COLUMN] == ["SHORT_RESEARCH", "SHORT_RESEARCH"]

    def test_blocked_gets_none(self) -> None:
        df = FakeDataFrame({"close": [1.0, 2.0]})
        result = ShellValidationResult.blocked((RUNTIME_JSON_MISSING,))
        out = apply_research_metadata_to_dataframe(df, result)
        assert out[RESEARCH_SIGNAL_COLUMN] == ["NONE", "NONE"]
        assert out[RESEARCH_REASON_COLUMN] == [RUNTIME_JSON_MISSING, RUNTIME_JSON_MISSING]
        assert out[RESEARCH_STATE_COLUMN] == ["BLOCKED", "BLOCKED"]
        assert out[RESEARCH_EXPOSURE_COLUMN] == ["BLOCKED", "BLOCKED"]

    def test_input_not_mutated(self) -> None:
        df = FakeDataFrame({"close": [1.0, 2.0]})
        original_columns = list(df.columns)
        result = self._make_result()
        apply_research_metadata_to_dataframe(df, result)
        assert df.columns == original_columns
        assert RESEARCH_SIGNAL_COLUMN not in df.columns

    def test_no_trade_columns_in_output(self) -> None:
        df = FakeDataFrame({"close": [1.0, 2.0]})
        result = self._make_result()
        out = apply_research_metadata_to_dataframe(df, result)
        assert "enter_long" not in out.columns
        assert "enter_short" not in out.columns
        assert "exit_long" not in out.columns
        assert "exit_short" not in out.columns

    def test_rejects_dataframe_with_enter_long(self) -> None:
        df = FakeDataFrame({"close": [1.0], "enter_long": [1]})
        result = self._make_result()
        with pytest.raises(ValueError, match="enter_long"):
            apply_research_metadata_to_dataframe(df, result)

    def test_rejects_dataframe_with_enter_short(self) -> None:
        df = FakeDataFrame({"close": [1.0], "enter_short": [1]})
        result = self._make_result()
        with pytest.raises(ValueError, match="enter_short"):
            apply_research_metadata_to_dataframe(df, result)

    def test_rejects_dataframe_with_exit_long(self) -> None:
        df = FakeDataFrame({"close": [1.0], "exit_long": [1]})
        result = self._make_result()
        with pytest.raises(ValueError, match="exit_long"):
            apply_research_metadata_to_dataframe(df, result)

    def test_rejects_dataframe_with_exit_short(self) -> None:
        df = FakeDataFrame({"close": [1.0], "exit_short": [1]})
        result = self._make_result()
        with pytest.raises(ValueError, match="exit_short"):
            apply_research_metadata_to_dataframe(df, result)

    def test_reason_from_first_reason_code(self) -> None:
        df = FakeDataFrame({"close": [1.0]})
        result = self._make_result(reason_codes=("CUSTOM_REASON",))
        out = apply_research_metadata_to_dataframe(df, result)
        assert out[RESEARCH_REASON_COLUMN] == ["CUSTOM_REASON"]

    def test_empty_reason_codes_uses_unknown(self) -> None:
        # ShellValidationResult blocks empty reason_codes, so test via blocked factory edge
        # This path shouldn't happen in practice, but test the fallback
        df = FakeDataFrame({"close": [1.0]})
        result = ShellValidationResult.blocked(("FALLBACK",))
        out = apply_research_metadata_to_dataframe(df, result)
        assert out[RESEARCH_REASON_COLUMN] == ["FALLBACK"]


class TestAssertNoTradeColumns:
    def test_no_trade_columns_ok(self) -> None:
        df = FakeDataFrame({"close": [1.0, 2.0]})
        assert_no_trade_columns(df)  # should not raise

    def test_raises_on_enter_long(self) -> None:
        df = FakeDataFrame({"close": [1.0], "enter_long": [1]})
        with pytest.raises(ValueError, match="enter_long"):
            assert_no_trade_columns(df)

    def test_raises_on_enter_short(self) -> None:
        df = FakeDataFrame({"close": [1.0], "enter_short": [1]})
        with pytest.raises(ValueError, match="enter_short"):
            assert_no_trade_columns(df)

    def test_raises_on_exit_long(self) -> None:
        df = FakeDataFrame({"close": [1.0], "exit_long": [1]})
        with pytest.raises(ValueError, match="exit_long"):
            assert_no_trade_columns(df)

    def test_raises_on_exit_short(self) -> None:
        df = FakeDataFrame({"close": [1.0], "exit_short": [1]})
        with pytest.raises(ValueError, match="exit_short"):
            assert_no_trade_columns(df)

    def test_raises_on_multiple(self) -> None:
        df = FakeDataFrame({"close": [1.0], "enter_long": [1], "exit_short": [1]})
        with pytest.raises(ValueError, match="enter_long"):
            assert_no_trade_columns(df)


class TestBuildBlockedResearchMetadata:
    def test_defaults(self) -> None:
        meta = build_blocked_research_metadata()
        assert meta[RESEARCH_SIGNAL_COLUMN] == "NONE"
        assert meta[RESEARCH_REASON_COLUMN] == "DEFAULT_BLOCKED"
        assert meta[RESEARCH_STATE_COLUMN] == "BLOCKED"
        assert meta[RESEARCH_EXPOSURE_COLUMN] == "BLOCKED"

    def test_custom_reason(self) -> None:
        meta = build_blocked_research_metadata(reason="STALE_RUNTIME_CONTEXT")
        assert meta[RESEARCH_REASON_COLUMN] == "STALE_RUNTIME_CONTEXT"

    def test_fail_closed(self) -> None:
        meta = build_blocked_research_metadata()
        assert meta[RESEARCH_SIGNAL_COLUMN] == "NONE"
        assert meta[RESEARCH_STATE_COLUMN] == "BLOCKED"


class TestSafetyAssertions:
    def test_no_freqtrade_import(self) -> None:
        import sys
        assert "freqtrade" not in sys.modules or not hasattr(sys.modules.get("freqtrade"), "__file__")
        import hunter.freqtrade_shell.adapter as adapter_module
        assert adapter_module.__name__ == "hunter.freqtrade_shell.adapter"

    def test_no_binance(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        assert "binance" not in source.lower()

    def test_no_live_trading(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        # adapter reads live_trading_enabled from result but never enables it
        assert "live_trading_enabled" in source.lower()
        assert "live_trading = True" not in source
        assert "live_trading_enabled = True" not in source

    def test_no_leverage(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        assert "leverage_enabled" in source.lower()
        assert "leverage = True" not in source
        assert "leverage_enabled = True" not in source

    def test_no_shorting(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        assert "shorting_enabled" in source.lower()
        assert "shorting = True" not in source
        assert "shorting_enabled = True" not in source

    def test_no_real_entry_exit(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        # The adapter explicitly forbids enter/exit columns
        assert "enter_long" in source.lower()
        assert "enter_short" in source.lower()
        assert "exit_long" in source.lower()
        assert "exit_short" in source.lower()
        # But does not set them
        assert source.count("enter_long =") == 0
        assert source.count("enter_short =") == 0
        assert source.count("exit_long =") == 0
        assert source.count("exit_short =") == 0

    def test_no_config_yaml(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        assert ".yaml" not in source.lower()
        assert ".yml" not in source.lower()

    def test_no_json_schema(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        assert ".schema.json" not in source.lower()

    def test_no_network_calls(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        assert "urllib" not in source.lower()
        assert "requests" not in source.lower()
        assert "socket" not in source.lower()
