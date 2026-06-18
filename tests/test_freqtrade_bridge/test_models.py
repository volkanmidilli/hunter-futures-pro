"""Tests for Freqtrade bridge models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from hunter.freqtrade_bridge.models import (
    FreqtradeBridgeConfig,
    FreqtradeBridgeContext,
    FreqtradeBridgeDataQuality,
    FreqtradeBridgeInputRefs,
    FreqtradeBridgeMode,
    FreqtradeBridgeSafetyFlags,
    FreqtradeBridgeState,
)


class TestFreqtradeBridgeState:
    """Tests for FreqtradeBridgeState enum."""

    def test_disabled_value(self) -> None:
        assert FreqtradeBridgeState.DISABLED == "DISABLED"

    def test_dry_run_ready_value(self) -> None:
        assert FreqtradeBridgeState.DRY_RUN_READY == "DRY_RUN_READY"

    def test_blocked_value(self) -> None:
        assert FreqtradeBridgeState.BLOCKED == "BLOCKED"

    def test_unknown_value(self) -> None:
        assert FreqtradeBridgeState.UNKNOWN == "UNKNOWN"

    def test_all_states(self) -> None:
        states = list(FreqtradeBridgeState)
        assert len(states) == 4
        assert FreqtradeBridgeState.DISABLED in states
        assert FreqtradeBridgeState.DRY_RUN_READY in states
        assert FreqtradeBridgeState.BLOCKED in states
        assert FreqtradeBridgeState.UNKNOWN in states

    def test_state_string_equality(self) -> None:
        assert FreqtradeBridgeState.BLOCKED == "BLOCKED"
        assert "BLOCKED" == FreqtradeBridgeState.BLOCKED


class TestFreqtradeBridgeMode:
    """Tests for FreqtradeBridgeMode enum."""

    def test_long_research_only_value(self) -> None:
        assert FreqtradeBridgeMode.LONG_RESEARCH_ONLY == "LONG_RESEARCH_ONLY"

    def test_short_research_only_value(self) -> None:
        assert FreqtradeBridgeMode.SHORT_RESEARCH_ONLY == "SHORT_RESEARCH_ONLY"

    def test_block_all_value(self) -> None:
        assert FreqtradeBridgeMode.BLOCK_ALL == "BLOCK_ALL"

    def test_all_modes(self) -> None:
        modes = list(FreqtradeBridgeMode)
        assert len(modes) == 3
        assert FreqtradeBridgeMode.LONG_RESEARCH_ONLY in modes
        assert FreqtradeBridgeMode.SHORT_RESEARCH_ONLY in modes
        assert FreqtradeBridgeMode.BLOCK_ALL in modes

    def test_mode_string_equality(self) -> None:
        assert FreqtradeBridgeMode.BLOCK_ALL == "BLOCK_ALL"
        assert "BLOCK_ALL" == FreqtradeBridgeMode.BLOCK_ALL


class TestFreqtradeBridgeConfig:
    """Tests for FreqtradeBridgeConfig dataclass."""

    def test_default_values(self) -> None:
        config = FreqtradeBridgeConfig()
        assert config.stale_execution_context_seconds == 300
        assert config.dry_run_required is True
        assert config.live_trading_enabled is False
        assert config.exchange_connection_enabled is False
        assert config.freqtrade_runtime_enabled is False
        assert config.strategy_enabled is False
        assert config.real_orders_enabled is False
        assert config.leverage_enabled is False
        assert config.shorting_enabled is False
        assert config.allow_long_research is True
        assert config.allow_short_research is True
        assert config.unsupported_mode_action == FreqtradeBridgeMode.BLOCK_ALL

    def test_valid_custom_stale_seconds(self) -> None:
        config = FreqtradeBridgeConfig(stale_execution_context_seconds=600)
        assert config.stale_execution_context_seconds == 600

    def test_invalid_stale_seconds_zero(self) -> None:
        with pytest.raises(ValueError, match="stale_execution_context_seconds must be positive"):
            FreqtradeBridgeConfig(stale_execution_context_seconds=0)

    def test_invalid_stale_seconds_negative(self) -> None:
        with pytest.raises(ValueError, match="stale_execution_context_seconds must be positive"):
            FreqtradeBridgeConfig(stale_execution_context_seconds=-1)

    def test_dry_run_required_false_raises(self) -> None:
        with pytest.raises(ValueError, match="dry_run_required must be True for MVP-5"):
            FreqtradeBridgeConfig(dry_run_required=False)

    def test_live_trading_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(live_trading_enabled=True)

    def test_exchange_connection_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="exchange_connection_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(exchange_connection_enabled=True)

    def test_freqtrade_runtime_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_runtime_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(freqtrade_runtime_enabled=True)

    def test_strategy_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="strategy_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(strategy_enabled=True)

    def test_real_orders_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(real_orders_enabled=True)

    def test_leverage_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(leverage_enabled=True)

    def test_shorting_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(shorting_enabled=True)

    def test_immutability(self) -> None:
        config = FreqtradeBridgeConfig()
        with pytest.raises(FrozenInstanceError):
            config.dry_run_required = False  # type: ignore[misc]


class TestFreqtradeBridgeSafetyFlags:
    """Tests for FreqtradeBridgeSafetyFlags dataclass."""

    def test_default_values(self) -> None:
        flags = FreqtradeBridgeSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.exchange_connection_enabled is False
        assert flags.freqtrade_runtime_enabled is False
        assert flags.strategy_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.human_override_required is False
        assert flags.max_context_age_seconds == 300

    def test_valid_custom_max_age(self) -> None:
        flags = FreqtradeBridgeSafetyFlags(max_context_age_seconds=600)
        assert flags.max_context_age_seconds == 600

    def test_invalid_max_age_zero(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            FreqtradeBridgeSafetyFlags(max_context_age_seconds=0)

    def test_invalid_max_age_negative(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            FreqtradeBridgeSafetyFlags(max_context_age_seconds=-1)

    def test_dry_run_false_raises(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True for MVP-5"):
            FreqtradeBridgeSafetyFlags(dry_run=False)

    def test_live_trading_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-5"):
            FreqtradeBridgeSafetyFlags(live_trading_enabled=True)

    def test_exchange_connection_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="exchange_connection_enabled must be False for MVP-5"):
            FreqtradeBridgeSafetyFlags(exchange_connection_enabled=True)

    def test_freqtrade_runtime_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_runtime_enabled must be False for MVP-5"):
            FreqtradeBridgeSafetyFlags(freqtrade_runtime_enabled=True)

    def test_strategy_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="strategy_enabled must be False for MVP-5"):
            FreqtradeBridgeSafetyFlags(strategy_enabled=True)

    def test_real_orders_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-5"):
            FreqtradeBridgeSafetyFlags(real_orders_enabled=True)

    def test_leverage_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-5"):
            FreqtradeBridgeSafetyFlags(leverage_enabled=True)

    def test_shorting_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-5"):
            FreqtradeBridgeSafetyFlags(shorting_enabled=True)

    def test_to_dict(self) -> None:
        flags = FreqtradeBridgeSafetyFlags()
        d = flags.to_dict()
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["exchange_connection_enabled"] is False
        assert d["freqtrade_runtime_enabled"] is False
        assert d["strategy_enabled"] is False
        assert d["real_orders_enabled"] is False
        assert d["leverage_enabled"] is False
        assert d["shorting_enabled"] is False
        assert d["human_override_required"] is False
        assert d["max_context_age_seconds"] == 300

    def test_immutability(self) -> None:
        flags = FreqtradeBridgeSafetyFlags()
        with pytest.raises(FrozenInstanceError):
            flags.dry_run = False  # type: ignore[misc]


class TestFreqtradeBridgeInputRefs:
    """Tests for FreqtradeBridgeInputRefs dataclass."""

    def test_default_values(self) -> None:
        refs = FreqtradeBridgeInputRefs()
        assert refs.execution_context_timestamp == ""
        assert refs.execution_context_version == ""

    def test_custom_values(self) -> None:
        refs = FreqtradeBridgeInputRefs(
            execution_context_timestamp="2025-01-15T10:30:00Z",
            execution_context_version="1.0",
        )
        assert refs.execution_context_timestamp == "2025-01-15T10:30:00Z"
        assert refs.execution_context_version == "1.0"

    def test_immutability(self) -> None:
        refs = FreqtradeBridgeInputRefs()
        with pytest.raises(FrozenInstanceError):
            refs.execution_context_timestamp = "x"  # type: ignore[misc]


class TestFreqtradeBridgeDataQuality:
    """Tests for FreqtradeBridgeDataQuality dataclass."""

    def test_default_values(self) -> None:
        dq = FreqtradeBridgeDataQuality()
        assert dq.execution_context_fresh is False
        assert dq.execution_context_valid is False
        assert dq.validation_errors == []

    def test_custom_values(self) -> None:
        dq = FreqtradeBridgeDataQuality(
            execution_context_fresh=True,
            execution_context_valid=True,
            validation_errors=["error1"],
        )
        assert dq.execution_context_fresh is True
        assert dq.execution_context_valid is True
        assert dq.validation_errors == ["error1"]

    def test_to_dict(self) -> None:
        dq = FreqtradeBridgeDataQuality(
            execution_context_fresh=True,
            execution_context_valid=True,
            validation_errors=["error1"],
        )
        d = dq.to_dict()
        assert d["execution_context_fresh"] is True
        assert d["execution_context_valid"] is True
        assert d["validation_errors"] == ["error1"]

    def test_immutability(self) -> None:
        dq = FreqtradeBridgeDataQuality()
        with pytest.raises(FrozenInstanceError):
            dq.execution_context_fresh = True  # type: ignore[misc]


class TestFreqtradeBridgeContext:
    """Tests for FreqtradeBridgeContext dataclass."""

    def test_blocked_factory(self) -> None:
        ctx = FreqtradeBridgeContext.blocked()
        assert ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert ctx.bridge_mode == FreqtradeBridgeMode.BLOCK_ALL
        assert ctx.status == "blocked"
        assert ctx.execution_state == "unknown"
        assert ctx.execution_mode == "unknown"
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.exchange_connection_enabled is False
        assert ctx.freqtrade_runtime_enabled is False
        assert ctx.strategy_enabled is False
        assert ctx.real_orders_enabled is False
        assert ctx.leverage_enabled is False
        assert ctx.shorting_enabled is False
        assert ctx.version == "1.0"
        assert ctx.reason_codes == ["FREQTRADE_BRIDGE_BLOCKED_BY_DEFAULT"]
        assert ctx.is_blocking() is True

    def test_blocked_with_custom_reason(self) -> None:
        ctx = FreqtradeBridgeContext.blocked(reason_codes=["custom_reason"])
        assert ctx.reason_codes == ["custom_reason"]

    def test_blocked_with_custom_timestamp(self) -> None:
        ts = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        ctx = FreqtradeBridgeContext.blocked(timestamp=ts)
        assert ctx.timestamp == ts

    def test_blocked_with_custom_data_quality(self) -> None:
        dq = FreqtradeBridgeDataQuality(execution_context_valid=True)
        ctx = FreqtradeBridgeContext.blocked(data_quality=dq)
        assert ctx.data_quality.execution_context_valid is True

    def test_valid_context_creation(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
        )
        assert ctx.timestamp == ts
        assert ctx.status == "success"
        assert ctx.bridge_state == FreqtradeBridgeState.DRY_RUN_READY
        assert ctx.bridge_mode == FreqtradeBridgeMode.LONG_RESEARCH_ONLY
        assert ctx.execution_state == "dry_run_only"
        assert ctx.execution_mode == "long_research_only"
        assert ctx.dry_run is True
        assert ctx.version == "1.0"
        assert ctx.is_blocking() is False

    def test_version_defaults_to_1_0(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
        )
        assert ctx.version == "1.0"

    def test_version_cannot_be_empty(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="version must be non-empty"):
            FreqtradeBridgeContext(
                timestamp=ts,
                status="success",
                bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
                bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
                execution_state="dry_run_only",
                execution_mode="long_research_only",
                version="",
            )

    def test_default_safety_flags(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
        )
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.exchange_connection_enabled is False
        assert ctx.freqtrade_runtime_enabled is False
        assert ctx.strategy_enabled is False
        assert ctx.real_orders_enabled is False
        assert ctx.leverage_enabled is False
        assert ctx.shorting_enabled is False

    def test_default_reason_codes_empty(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
        )
        assert ctx.reason_codes == []

    def test_is_blocking_for_blocked_state(self) -> None:
        ctx = FreqtradeBridgeContext.blocked()
        assert ctx.is_blocking() is True

    def test_is_blocking_for_unknown_state(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="blocked",
            bridge_state=FreqtradeBridgeState.UNKNOWN,
            bridge_mode=FreqtradeBridgeMode.BLOCK_ALL,
            execution_state="unknown",
            execution_mode="unknown",
        )
        assert ctx.is_blocking() is True

    def test_is_blocking_for_dry_run_ready(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
        )
        assert ctx.is_blocking() is False

    def test_is_blocking_for_disabled(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="blocked",
            bridge_state=FreqtradeBridgeState.DISABLED,
            bridge_mode=FreqtradeBridgeMode.BLOCK_ALL,
            execution_state="unknown",
            execution_mode="unknown",
        )
        assert ctx.is_blocking() is True

    def test_immutability(self) -> None:
        ctx = FreqtradeBridgeContext.blocked()
        with pytest.raises(FrozenInstanceError):
            ctx.dry_run = False  # type: ignore[misc]

    def test_safety_flags_nested(self) -> None:
        ts = datetime.now(timezone.utc)
        flags = FreqtradeBridgeSafetyFlags()
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
            safety_flags=flags,
        )
        assert ctx.safety_flags.dry_run is True
        assert ctx.safety_flags.max_context_age_seconds == 300

    def test_input_refs_nested(self) -> None:
        ts = datetime.now(timezone.utc)
        refs = FreqtradeBridgeInputRefs(
            execution_context_timestamp="2025-01-15T10:30:00Z",
            execution_context_version="1.0",
        )
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
            input_refs=refs,
        )
        assert ctx.input_refs.execution_context_timestamp == "2025-01-15T10:30:00Z"
        assert ctx.input_refs.execution_context_version == "1.0"

    def test_data_quality_nested(self) -> None:
        ts = datetime.now(timezone.utc)
        dq = FreqtradeBridgeDataQuality(
            execution_context_fresh=True,
            execution_context_valid=True,
            validation_errors=[],
        )
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
            data_quality=dq,
        )
        assert ctx.data_quality.execution_context_fresh is True
        assert ctx.data_quality.validation_errors == []
