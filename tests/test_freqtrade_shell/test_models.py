"""Tests for freqtrade shell models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.freqtrade_shell.models import (
    DEFAULT_BLOCKED,
    DRY_RUN_DISABLED,
    INVALID_SIGNAL_ACTION,
    INVALID_STRATEGY_STATE,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_METADATA_EXPOSED,
    NOT_DRY_RUN_READY,
    REAL_ORDERS_ENABLED,
    REASON_CODES,
    RUNTIME_JSON_INVALID,
    RUNTIME_JSON_INVALID_TIMESTAMP,
    RUNTIME_JSON_MISSING,
    RUNTIME_JSON_VERSION_MISMATCH,
    SHORTING_ENABLED,
    SHORT_RESEARCH_METADATA_EXPOSED,
    SIGNAL_BLOCKED,
    STALE_RUNTIME_CONTEXT,
    VALIDATION_ERROR,
    ShellRuntimeConfig,
    ShellSignalExposure,
    ShellState,
    ShellValidationResult,
)


class TestShellState:
    def test_disabled(self) -> None:
        assert ShellState.DISABLED == "DISABLED"
        assert ShellState.DISABLED.value == "DISABLED"

    def test_dry_run_ready(self) -> None:
        assert ShellState.DRY_RUN_READY == "DRY_RUN_READY"
        assert ShellState.DRY_RUN_READY.value == "DRY_RUN_READY"

    def test_blocked(self) -> None:
        assert ShellState.BLOCKED == "BLOCKED"
        assert ShellState.BLOCKED.value == "BLOCKED"

    def test_unknown(self) -> None:
        assert ShellState.UNKNOWN == "UNKNOWN"
        assert ShellState.UNKNOWN.value == "UNKNOWN"

    def test_members(self) -> None:
        assert list(ShellState) == [
            ShellState.DISABLED,
            ShellState.DRY_RUN_READY,
            ShellState.BLOCKED,
            ShellState.UNKNOWN,
        ]


class TestShellSignalExposure:
    def test_expose_long(self) -> None:
        assert ShellSignalExposure.EXPOSE_LONG_RESEARCH_METADATA == "EXPOSE_LONG_RESEARCH_METADATA"

    def test_expose_short(self) -> None:
        assert ShellSignalExposure.EXPOSE_SHORT_RESEARCH_METADATA == "EXPOSE_SHORT_RESEARCH_METADATA"

    def test_no_signal(self) -> None:
        assert ShellSignalExposure.NO_RESEARCH_SIGNAL == "NO_RESEARCH_SIGNAL"

    def test_blocked(self) -> None:
        assert ShellSignalExposure.BLOCKED == "BLOCKED"

    def test_members(self) -> None:
        assert list(ShellSignalExposure) == [
            ShellSignalExposure.EXPOSE_LONG_RESEARCH_METADATA,
            ShellSignalExposure.EXPOSE_SHORT_RESEARCH_METADATA,
            ShellSignalExposure.NO_RESEARCH_SIGNAL,
            ShellSignalExposure.BLOCKED,
        ]


class TestShellRuntimeConfig:
    def test_defaults(self) -> None:
        c = ShellRuntimeConfig()
        assert c.runtime_json_path == "data/freqtrade_strategy/current_dry_run_strategy_runtime.json"
        assert c.max_runtime_age_seconds == 300
        assert c.dry_run_required is True
        assert c.allow_research_metadata is True
        assert c.allow_real_trade_signals is False
        assert c.allow_entry_columns is False
        assert c.allow_exit_columns is False
        assert c.allow_freqtrade_runtime_connection is False
        assert c.allow_binance_connection is False
        assert c.allow_real_exchange_connection is False
        assert c.allow_api_keys is False
        assert c.allow_live_trading is False
        assert c.allow_real_orders is False
        assert c.allow_leverage is False
        assert c.allow_shorting is False

    def test_empty_path(self) -> None:
        with pytest.raises(ValueError, match="runtime_json_path"):
            ShellRuntimeConfig(runtime_json_path="")

    def test_non_string_path(self) -> None:
        with pytest.raises(ValueError, match="runtime_json_path"):
            ShellRuntimeConfig(runtime_json_path=123)  # type: ignore[arg-type]

    def test_zero_max_age(self) -> None:
        with pytest.raises(ValueError, match="max_runtime_age_seconds"):
            ShellRuntimeConfig(max_runtime_age_seconds=0)

    def test_negative_max_age(self) -> None:
        with pytest.raises(ValueError, match="max_runtime_age_seconds"):
            ShellRuntimeConfig(max_runtime_age_seconds=-1)

    def test_dry_run_required_false(self) -> None:
        with pytest.raises(ValueError, match="dry_run_required"):
            ShellRuntimeConfig(dry_run_required=False)

    def test_allow_real_trade_signals_true(self) -> None:
        with pytest.raises(ValueError, match="allow_real_trade_signals"):
            ShellRuntimeConfig(allow_real_trade_signals=True)

    def test_allow_entry_columns_true(self) -> None:
        with pytest.raises(ValueError, match="allow_entry_columns"):
            ShellRuntimeConfig(allow_entry_columns=True)

    def test_allow_exit_columns_true(self) -> None:
        with pytest.raises(ValueError, match="allow_exit_columns"):
            ShellRuntimeConfig(allow_exit_columns=True)

    def test_allow_freqtrade_runtime_connection_true(self) -> None:
        with pytest.raises(ValueError, match="allow_freqtrade_runtime_connection"):
            ShellRuntimeConfig(allow_freqtrade_runtime_connection=True)

    def test_allow_binance_connection_true(self) -> None:
        with pytest.raises(ValueError, match="allow_binance_connection"):
            ShellRuntimeConfig(allow_binance_connection=True)

    def test_allow_real_exchange_connection_true(self) -> None:
        with pytest.raises(ValueError, match="allow_real_exchange_connection"):
            ShellRuntimeConfig(allow_real_exchange_connection=True)

    def test_allow_api_keys_true(self) -> None:
        with pytest.raises(ValueError, match="allow_api_keys"):
            ShellRuntimeConfig(allow_api_keys=True)

    def test_allow_live_trading_true(self) -> None:
        with pytest.raises(ValueError, match="allow_live_trading"):
            ShellRuntimeConfig(allow_live_trading=True)

    def test_allow_real_orders_true(self) -> None:
        with pytest.raises(ValueError, match="allow_real_orders"):
            ShellRuntimeConfig(allow_real_orders=True)

    def test_allow_leverage_true(self) -> None:
        with pytest.raises(ValueError, match="allow_leverage"):
            ShellRuntimeConfig(allow_leverage=True)

    def test_allow_shorting_true(self) -> None:
        with pytest.raises(ValueError, match="allow_shorting"):
            ShellRuntimeConfig(allow_shorting=True)

    def test_custom_path(self) -> None:
        c = ShellRuntimeConfig(runtime_json_path="custom/path.json")
        assert c.runtime_json_path == "custom/path.json"

    def test_custom_max_age(self) -> None:
        c = ShellRuntimeConfig(max_runtime_age_seconds=60)
        assert c.max_runtime_age_seconds == 60

    def test_immutability(self) -> None:
        c = ShellRuntimeConfig()
        with pytest.raises(FrozenInstanceError):
            c.max_runtime_age_seconds = 60  # type: ignore[misc]


class TestShellValidationResult:
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

    def test_defaults(self) -> None:
        r = self._make_result()
        assert r.shell_state == ShellState.DRY_RUN_READY
        assert r.signal_exposure == ShellSignalExposure.EXPOSE_LONG_RESEARCH_METADATA
        assert r.reason_codes == (LONG_RESEARCH_METADATA_EXPOSED,)
        assert r.version == "1.0"

    def test_blocked_factory(self) -> None:
        r = ShellValidationResult.blocked((RUNTIME_JSON_MISSING,))
        assert r.shell_state == ShellState.BLOCKED
        assert r.signal_exposure == ShellSignalExposure.BLOCKED
        assert r.reason_codes == (RUNTIME_JSON_MISSING,)
        assert r.runtime_json_present is False
        assert r.runtime_json_valid is False
        assert r.runtime_json_stale is True
        assert r.runtime_version == "UNKNOWN"
        assert r.runtime_strategy_state == "UNKNOWN"
        assert r.runtime_strategy_mode == "BLOCK_ALL"
        assert r.runtime_signal_action == "BLOCK_SIGNAL"
        assert r.dry_run is True
        assert r.live_trading_enabled is False
        assert r.real_orders_enabled is False
        assert r.leverage_enabled is False
        assert r.shorting_enabled is False
        assert r.allow_real_trade_signals is False
        assert r.allow_entry_columns is False
        assert r.allow_exit_columns is False
        assert r.version == "1.0"
        assert r.timestamp.tzinfo is not None

    def test_blocked_factory_custom_timestamp(self) -> None:
        ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        r = ShellValidationResult.blocked((RUNTIME_JSON_MISSING,), timestamp=ts)
        assert r.timestamp == ts

    def test_naive_timestamp_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            self._make_result(timestamp=datetime(2025, 1, 15, 12, 0, 0))

    def test_empty_reason_codes_rejected(self) -> None:
        with pytest.raises(ValueError, match="reason_codes"):
            self._make_result(reason_codes=())

    def test_list_reason_codes_rejected(self) -> None:
        with pytest.raises(ValueError, match="reason_codes"):
            self._make_result(reason_codes=[LONG_RESEARCH_METADATA_EXPOSED])  # type: ignore[arg-type]

    def test_dry_run_ready_with_blocked_exposure_rejected(self) -> None:
        with pytest.raises(ValueError, match="EXPOSE_LONG_RESEARCH_METADATA"):
            self._make_result(
                shell_state=ShellState.DRY_RUN_READY,
                signal_exposure=ShellSignalExposure.BLOCKED,
            )

    def test_dry_run_ready_with_no_signal_exposure_rejected(self) -> None:
        with pytest.raises(ValueError, match="EXPOSE_LONG_RESEARCH_METADATA"):
            self._make_result(
                shell_state=ShellState.DRY_RUN_READY,
                signal_exposure=ShellSignalExposure.NO_RESEARCH_SIGNAL,
            )

    def test_allow_real_trade_signals_true_rejected(self) -> None:
        with pytest.raises(ValueError, match="allow_real_trade_signals"):
            self._make_result(allow_real_trade_signals=True)

    def test_allow_entry_columns_true_rejected(self) -> None:
        with pytest.raises(ValueError, match="allow_entry_columns"):
            self._make_result(allow_entry_columns=True)

    def test_allow_exit_columns_true_rejected(self) -> None:
        with pytest.raises(ValueError, match="allow_exit_columns"):
            self._make_result(allow_exit_columns=True)

    def test_live_trading_enabled_true_rejected(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled"):
            self._make_result(live_trading_enabled=True)

    def test_real_orders_enabled_true_rejected(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled"):
            self._make_result(real_orders_enabled=True)

    def test_leverage_enabled_true_rejected(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled"):
            self._make_result(leverage_enabled=True)

    def test_shorting_enabled_true_rejected(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled"):
            self._make_result(shorting_enabled=True)

    def test_empty_version_rejected(self) -> None:
        with pytest.raises(ValueError, match="version"):
            self._make_result(version="")

    def test_immutability(self) -> None:
        r = self._make_result()
        with pytest.raises(FrozenInstanceError):
            r.shell_state = ShellState.BLOCKED  # type: ignore[misc]


class TestReasonCodes:
    def test_all_present(self) -> None:
        expected = {
            RUNTIME_JSON_MISSING,
            RUNTIME_JSON_INVALID,
            RUNTIME_JSON_VERSION_MISMATCH,
            RUNTIME_JSON_INVALID_TIMESTAMP,
            STALE_RUNTIME_CONTEXT,
            INVALID_STRATEGY_STATE,
            INVALID_SIGNAL_ACTION,
            SIGNAL_BLOCKED,
            NOT_DRY_RUN_READY,
            DRY_RUN_DISABLED,
            LIVE_TRADING_ENABLED,
            REAL_ORDERS_ENABLED,
            LEVERAGE_ENABLED,
            SHORTING_ENABLED,
            LONG_RESEARCH_METADATA_EXPOSED,
            SHORT_RESEARCH_METADATA_EXPOSED,
            DEFAULT_BLOCKED,
            VALIDATION_ERROR,
        }
        assert set(REASON_CODES) == expected

    def test_tuple_type(self) -> None:
        assert isinstance(REASON_CODES, tuple)
