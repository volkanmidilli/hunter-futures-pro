"""Integration tests for freqtrade shell.

Tests the complete in-process MVP-9 shell flow:
  payload dict → validate_runtime_payload → ShellValidationResult
  → shell_validation_result_to_metadata → determine_research_signal
  → apply_research_metadata_to_dataframe → verify research-only metadata.

No file reads, no file writes, no network, no Freqtrade import.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from hunter.freqtrade_shell.adapter import (
    RESEARCH_EXPOSURE_COLUMN,
    RESEARCH_REASON_COLUMN,
    RESEARCH_SIGNAL_COLUMN,
    RESEARCH_STATE_COLUMN,
    apply_research_metadata_to_dataframe,
    determine_research_signal,
    shell_validation_result_to_metadata,
)
from hunter.freqtrade_shell.models import (
    DRY_RUN_DISABLED,
    INVALID_SIGNAL_ACTION,
    INVALID_STRATEGY_STATE,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_METADATA_EXPOSED,
    NOT_DRY_RUN_READY,
    REAL_ORDERS_ENABLED,
    RUNTIME_JSON_INVALID,
    RUNTIME_JSON_INVALID_TIMESTAMP,
    RUNTIME_JSON_MISSING,
    RUNTIME_JSON_VERSION_MISMATCH,
    SHORTING_ENABLED,
    SIGNAL_BLOCKED,
    STALE_RUNTIME_CONTEXT,
    ShellRuntimeConfig,
    ShellSignalExposure,
    ShellState,
    ShellValidationResult,
)
from hunter.freqtrade_shell.validator import validate_runtime_payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeDataFrame:
    """Minimal dataframe-like object for testing."""

    def __init__(self, columns: list[str] | None = None) -> None:
        self.columns = list(columns) if columns else []
        self._data: dict[str, list[Any]] = {}
        for col in self.columns:
            self._data[col] = [1, 2, 3]

    def copy(self) -> FakeDataFrame:
        df = FakeDataFrame.__new__(FakeDataFrame)
        df.columns = list(self.columns)
        df._data = dict(self._data)
        return df

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self.columns:
            self.columns.append(key)
        self._data[key] = [value] * 3

    def __getitem__(self, key: str) -> list[Any]:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self.columns


def _make_payload(**kwargs: Any) -> dict[str, object]:
    """Build a valid MVP-8 runtime payload with overrides."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    defaults: dict[str, object] = {
        "version": "1.0",
        "timestamp": now_iso,
        "strategy_state": "DRY_RUN_READY",
        "strategy_mode": "LONG_RESEARCH_ONLY",
        "signal_action": "EXPOSE_LONG_RESEARCH_SIGNAL",
        "dry_run": True,
        "live_trading_enabled": False,
        "real_orders_enabled": False,
        "leverage_enabled": False,
        "shorting_enabled": False,
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

class TestLongResearchHappyPath:
    def test_long_payload_validates_to_ready(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        assert result.shell_state is ShellState.DRY_RUN_READY
        assert result.signal_exposure is ShellSignalExposure.EXPOSE_LONG_RESEARCH_METADATA
        assert result.reason_codes == (LONG_RESEARCH_METADATA_EXPOSED,)

    def test_long_research_signal(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        assert determine_research_signal(result) == "LONG_RESEARCH"

    def test_long_dataframe_has_research_columns(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert RESEARCH_SIGNAL_COLUMN in df.columns
        assert df[RESEARCH_SIGNAL_COLUMN] == ["LONG_RESEARCH"] * 3
        assert RESEARCH_REASON_COLUMN in df.columns
        assert RESEARCH_STATE_COLUMN in df.columns
        assert RESEARCH_EXPOSURE_COLUMN in df.columns

    def test_long_dataframe_no_trade_columns(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert "enter_long" not in df.columns
        assert "enter_short" not in df.columns
        assert "exit_long" not in df.columns
        assert "exit_short" not in df.columns


class TestShortResearchHappyPath:
    def test_short_payload_validates_to_ready(self) -> None:
        payload = _make_payload(
            strategy_mode="SHORT_RESEARCH_ONLY",
            signal_action="EXPOSE_SHORT_RESEARCH_SIGNAL",
        )
        result = validate_runtime_payload(payload)
        assert result.shell_state is ShellState.DRY_RUN_READY
        assert result.signal_exposure is ShellSignalExposure.EXPOSE_SHORT_RESEARCH_METADATA
        assert result.reason_codes == ("SHORT_RESEARCH_METADATA_EXPOSED",)

    def test_short_research_signal(self) -> None:
        payload = _make_payload(
            strategy_mode="SHORT_RESEARCH_ONLY",
            signal_action="EXPOSE_SHORT_RESEARCH_SIGNAL",
        )
        result = validate_runtime_payload(payload)
        assert determine_research_signal(result) == "SHORT_RESEARCH"

    def test_short_dataframe_has_research_columns(self) -> None:
        payload = _make_payload(
            strategy_mode="SHORT_RESEARCH_ONLY",
            signal_action="EXPOSE_SHORT_RESEARCH_SIGNAL",
        )
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert RESEARCH_SIGNAL_COLUMN in df.columns
        assert df[RESEARCH_SIGNAL_COLUMN] == ["SHORT_RESEARCH"] * 3

    def test_short_dataframe_no_trade_columns(self) -> None:
        payload = _make_payload(
            strategy_mode="SHORT_RESEARCH_ONLY",
            signal_action="EXPOSE_SHORT_RESEARCH_SIGNAL",
        )
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert "enter_long" not in df.columns
        assert "enter_short" not in df.columns
        assert "exit_long" not in df.columns
        assert "exit_short" not in df.columns


# ---------------------------------------------------------------------------
# Fail-closed / blocking paths
# ---------------------------------------------------------------------------

class TestMissingPayload:
    def test_missing_payload(self) -> None:
        result = validate_runtime_payload(None)
        assert result.reason_codes == (RUNTIME_JSON_MISSING,)
        assert result.shell_state is ShellState.BLOCKED
        assert determine_research_signal(result) == "NONE"

    def test_missing_dataframe(self) -> None:
        result = validate_runtime_payload(None)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestInvalidPayload:
    def test_invalid_payload(self) -> None:
        result = validate_runtime_payload({"version": "1.0"})  # missing required fields
        assert result.reason_codes == (RUNTIME_JSON_INVALID,)
        assert result.shell_state is ShellState.BLOCKED

    def test_invalid_dataframe(self) -> None:
        result = validate_runtime_payload({"version": "1.0"})
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestVersionMismatch:
    def test_version_mismatch(self) -> None:
        payload = _make_payload(version="2.0")
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (RUNTIME_JSON_VERSION_MISMATCH,)
        assert result.shell_state is ShellState.BLOCKED

    def test_version_mismatch_dataframe(self) -> None:
        payload = _make_payload(version="2.0")
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestDryRunDisabled:
    def test_dry_run_false(self) -> None:
        payload = _make_payload(dry_run=False)
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (DRY_RUN_DISABLED,)
        assert result.shell_state is ShellState.BLOCKED

    def test_dry_run_false_dataframe(self) -> None:
        payload = _make_payload(dry_run=False)
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestLiveTradingEnabled:
    def test_live_trading_true(self) -> None:
        payload = _make_payload(live_trading_enabled=True)
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (LIVE_TRADING_ENABLED,)
        assert result.shell_state is ShellState.BLOCKED

    def test_live_trading_true_dataframe(self) -> None:
        payload = _make_payload(live_trading_enabled=True)
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestRealOrdersEnabled:
    def test_real_orders_true(self) -> None:
        payload = _make_payload(real_orders_enabled=True)
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (REAL_ORDERS_ENABLED,)
        assert result.shell_state is ShellState.BLOCKED

    def test_real_orders_true_dataframe(self) -> None:
        payload = _make_payload(real_orders_enabled=True)
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestLeverageEnabled:
    def test_leverage_true(self) -> None:
        payload = _make_payload(leverage_enabled=True)
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (LEVERAGE_ENABLED,)
        assert result.shell_state is ShellState.BLOCKED

    def test_leverage_true_dataframe(self) -> None:
        payload = _make_payload(leverage_enabled=True)
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestShortingEnabled:
    def test_shorting_true(self) -> None:
        payload = _make_payload(shorting_enabled=True)
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (SHORTING_ENABLED,)
        assert result.shell_state is ShellState.BLOCKED

    def test_shorting_true_dataframe(self) -> None:
        payload = _make_payload(shorting_enabled=True)
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestInvalidTimestamp:
    def test_invalid_timestamp(self) -> None:
        payload = _make_payload(timestamp="not-a-timestamp")
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (RUNTIME_JSON_INVALID_TIMESTAMP,)
        assert result.shell_state is ShellState.BLOCKED

    def test_invalid_timestamp_dataframe(self) -> None:
        payload = _make_payload(timestamp="not-a-timestamp")
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestStaleRuntimeContext:
    def test_stale_timestamp(self) -> None:
        old_iso = "2020-01-01T00:00:00Z"
        payload = _make_payload(timestamp=old_iso)
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (STALE_RUNTIME_CONTEXT,)
        assert result.shell_state is ShellState.BLOCKED

    def test_stale_timestamp_dataframe(self) -> None:
        old_iso = "2020-01-01T00:00:00Z"
        payload = _make_payload(timestamp=old_iso)
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestInvalidStrategyState:
    def test_invalid_strategy_state(self) -> None:
        payload = _make_payload(strategy_state="INVALID_STATE")
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (INVALID_STRATEGY_STATE,)
        assert result.shell_state is ShellState.BLOCKED

    def test_invalid_strategy_state_dataframe(self) -> None:
        payload = _make_payload(strategy_state="INVALID_STATE")
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestInvalidSignalAction:
    def test_invalid_signal_action(self) -> None:
        payload = _make_payload(signal_action="INVALID_ACTION")
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (INVALID_SIGNAL_ACTION,)
        assert result.shell_state is ShellState.BLOCKED

    def test_invalid_signal_action_dataframe(self) -> None:
        payload = _make_payload(signal_action="INVALID_ACTION")
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestSignalBlocked:
    def test_block_signal(self) -> None:
        payload = _make_payload(signal_action="BLOCK_SIGNAL")
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (SIGNAL_BLOCKED,)
        assert result.shell_state is ShellState.BLOCKED

    def test_block_signal_dataframe(self) -> None:
        payload = _make_payload(signal_action="BLOCK_SIGNAL")
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestNoSignal:
    def test_no_signal(self) -> None:
        payload = _make_payload(signal_action="NO_SIGNAL")
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (SIGNAL_BLOCKED,)
        assert result.shell_state is ShellState.BLOCKED

    def test_no_signal_dataframe(self) -> None:
        payload = _make_payload(signal_action="NO_SIGNAL")
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


class TestNotDryRunReady:
    def test_blocked_state(self) -> None:
        payload = _make_payload(strategy_state="BLOCKED")
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (NOT_DRY_RUN_READY,)
        assert result.shell_state is ShellState.BLOCKED

    def test_unknown_state(self) -> None:
        payload = _make_payload(strategy_state="UNKNOWN")
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (NOT_DRY_RUN_READY,)
        assert result.shell_state is ShellState.BLOCKED

    def test_disabled_state(self) -> None:
        payload = _make_payload(strategy_state="DISABLED")
        result = validate_runtime_payload(payload)
        assert result.reason_codes == (NOT_DRY_RUN_READY,)
        assert result.shell_state is ShellState.BLOCKED

    def test_blocked_state_dataframe(self) -> None:
        payload = _make_payload(strategy_state="BLOCKED")
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3

    def test_unknown_state_dataframe(self) -> None:
        payload = _make_payload(strategy_state="UNKNOWN")
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3

    def test_disabled_state_dataframe(self) -> None:
        payload = _make_payload(strategy_state="DISABLED")
        result = validate_runtime_payload(payload)
        df = apply_research_metadata_to_dataframe(FakeDataFrame(["close"]), result)
        assert df[RESEARCH_SIGNAL_COLUMN] == ["NONE"] * 3


# ---------------------------------------------------------------------------
# Forbidden trade columns
# ---------------------------------------------------------------------------

class TestForbiddenTradeColumns:
    def test_rejects_enter_long(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        df = FakeDataFrame(["close", "enter_long"])
        with pytest.raises(ValueError, match="Real trade columns are forbidden"):
            apply_research_metadata_to_dataframe(df, result)

    def test_rejects_enter_short(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        df = FakeDataFrame(["close", "enter_short"])
        with pytest.raises(ValueError, match="Real trade columns are forbidden"):
            apply_research_metadata_to_dataframe(df, result)

    def test_rejects_exit_long(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        df = FakeDataFrame(["close", "exit_long"])
        with pytest.raises(ValueError, match="Real trade columns are forbidden"):
            apply_research_metadata_to_dataframe(df, result)

    def test_rejects_exit_short(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        df = FakeDataFrame(["close", "exit_short"])
        with pytest.raises(ValueError, match="Real trade columns are forbidden"):
            apply_research_metadata_to_dataframe(df, result)


# ---------------------------------------------------------------------------
# Metadata verification
# ---------------------------------------------------------------------------

class TestMetadataVerification:
    def test_enum_serialization(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        meta = shell_validation_result_to_metadata(result)
        assert meta["shell_state"] == "DRY_RUN_READY"
        assert meta["signal_exposure"] == "EXPOSE_LONG_RESEARCH_METADATA"

    def test_reason_codes_list(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        meta = shell_validation_result_to_metadata(result)
        assert isinstance(meta["reason_codes"], list)
        assert meta["reason_codes"] == [LONG_RESEARCH_METADATA_EXPOSED]

    def test_runtime_fields_present(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        meta = shell_validation_result_to_metadata(result)
        assert meta["runtime_version"] == "1.0"
        assert meta["runtime_strategy_state"] == "DRY_RUN_READY"
        assert meta["runtime_strategy_mode"] == "LONG_RESEARCH_ONLY"
        assert meta["runtime_signal_action"] == "EXPOSE_LONG_RESEARCH_SIGNAL"

    def test_unsafe_flags_false(self) -> None:
        payload = _make_payload()
        result = validate_runtime_payload(payload)
        meta = shell_validation_result_to_metadata(result)
        assert meta["dry_run"] is True
        assert meta["live_trading_enabled"] is False
        assert meta["real_orders_enabled"] is False
        assert meta["leverage_enabled"] is False
        assert meta["shorting_enabled"] is False
        assert meta["allow_real_trade_signals"] is False
        assert meta["allow_entry_columns"] is False
        assert meta["allow_exit_columns"] is False


# ---------------------------------------------------------------------------
# Safety assertions
# ---------------------------------------------------------------------------

class TestSafetyAssertions:
    def test_no_freqtrade_import(self) -> None:
        import sys
        assert "freqtrade" not in sys.modules or not hasattr(sys.modules.get("freqtrade"), "__file__")

    def test_no_freqtrade_strategy_class(self) -> None:
        import hunter.freqtrade_shell as pkg
        assert not hasattr(pkg, "IStrategy")
        assert not hasattr(pkg, "FreqtradeStrategy")

    def test_no_config_yaml(self) -> None:
        import hunter.freqtrade_shell as pkg
        import inspect
        source = inspect.getsource(pkg)
        assert ".yaml" not in source.lower()
        assert ".yml" not in source.lower()

    def test_no_json_schema(self) -> None:
        import hunter.freqtrade_shell as pkg
        import inspect
        source = inspect.getsource(pkg)
        assert "jsonschema" not in source.lower()
        assert ".schema.json" not in source.lower()

    def test_no_network_calls(self) -> None:
        import hunter.freqtrade_shell as pkg
        import inspect
        source = inspect.getsource(pkg)
        assert "requests" not in source.lower()
        assert "urllib" not in source.lower()
        assert "socket" not in source.lower()

    def test_no_binance(self) -> None:
        import hunter.freqtrade_shell as pkg
        import inspect
        source = inspect.getsource(pkg)
        assert "binance" not in source.lower()

    def test_no_live_trading(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        assert "live_trading = True" not in source
        assert "live_trading_enabled = True" not in source

    def test_no_real_orders(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        assert "real_orders = True" not in source
        assert "real_orders_enabled = True" not in source

    def test_no_leverage(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        assert "leverage = True" not in source
        assert "leverage_enabled = True" not in source

    def test_no_shorting(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        assert "shorting = True" not in source
        assert "shorting_enabled = True" not in source

    def test_no_real_entry_exit(self) -> None:
        import hunter.freqtrade_shell.adapter as adapter_module
        import inspect
        source = inspect.getsource(adapter_module)
        assert "enter_long =" not in source
        assert "enter_short =" not in source
        assert "exit_long =" not in source
        assert "exit_short =" not in source
        # The adapter only rejects/forbids these columns
        assert "enter_long" in source
        assert "enter_short" in source
        assert "exit_long" in source
        assert "exit_short" in source

    def test_no_production_data_access(self) -> None:
        import hunter.freqtrade_shell as pkg
        import inspect
        source = inspect.getsource(pkg)
        assert "data/freqtrade_strategy" not in source
        assert "current_dry_run_strategy_runtime" not in source
