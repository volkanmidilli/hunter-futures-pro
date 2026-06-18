"""Tests for strategy contract models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from hunter.strategy_contract.models import (
    CALCULATION_ERROR,
    DEFAULT_BLOCK_ALL,
    DRY_RUN_DISABLED,
    INVALID_BRIDGE_CONTEXT,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_ALLOWED,
    MISSING_BRIDGE_CONTEXT,
    REAL_ORDERS_ENABLED,
    REASON_CODES,
    SHORTING_ENABLED,
    SHORT_RESEARCH_ALLOWED,
    STALE_BRIDGE_CONTEXT,
    UNSUPPORTED_BRIDGE_MODE,
    BRIDGE_MODE_BLOCK_ALL,
    BRIDGE_NOT_DRY_RUN_READY,
    StrategyContractConfig,
    StrategyContractDataQuality,
    StrategyContractInputRefs,
    StrategyContractMode,
    StrategyContractSafetyFlags,
    StrategyContractState,
    StrategyContext,
)


class TestStrategyContractState:
    """Tests for StrategyContractState enum."""

    def test_disabled_value(self) -> None:
        assert StrategyContractState.DISABLED == "DISABLED"

    def test_dry_run_ready_value(self) -> None:
        assert StrategyContractState.DRY_RUN_READY == "DRY_RUN_READY"

    def test_blocked_value(self) -> None:
        assert StrategyContractState.BLOCKED == "BLOCKED"

    def test_unknown_value(self) -> None:
        assert StrategyContractState.UNKNOWN == "UNKNOWN"

    def test_all_states(self) -> None:
        states = list(StrategyContractState)
        assert len(states) == 4
        assert StrategyContractState.DISABLED in states
        assert StrategyContractState.DRY_RUN_READY in states
        assert StrategyContractState.BLOCKED in states
        assert StrategyContractState.UNKNOWN in states

    def test_state_string_equality(self) -> None:
        assert StrategyContractState.BLOCKED == "BLOCKED"
        assert "BLOCKED" == StrategyContractState.BLOCKED


class TestStrategyContractMode:
    """Tests for StrategyContractMode enum."""

    def test_long_research_only_value(self) -> None:
        assert StrategyContractMode.LONG_RESEARCH_ONLY == "LONG_RESEARCH_ONLY"

    def test_short_research_only_value(self) -> None:
        assert StrategyContractMode.SHORT_RESEARCH_ONLY == "SHORT_RESEARCH_ONLY"

    def test_block_all_value(self) -> None:
        assert StrategyContractMode.BLOCK_ALL == "BLOCK_ALL"

    def test_all_modes(self) -> None:
        modes = list(StrategyContractMode)
        assert len(modes) == 3
        assert StrategyContractMode.LONG_RESEARCH_ONLY in modes
        assert StrategyContractMode.SHORT_RESEARCH_ONLY in modes
        assert StrategyContractMode.BLOCK_ALL in modes

    def test_mode_string_equality(self) -> None:
        assert StrategyContractMode.BLOCK_ALL == "BLOCK_ALL"
        assert "BLOCK_ALL" == StrategyContractMode.BLOCK_ALL


class TestReasonCodes:
    """Tests for reason code constants."""

    def test_all_reason_codes_defined(self) -> None:
        assert len(REASON_CODES) == 15
        assert MISSING_BRIDGE_CONTEXT in REASON_CODES
        assert INVALID_BRIDGE_CONTEXT in REASON_CODES
        assert BRIDGE_NOT_DRY_RUN_READY in REASON_CODES
        assert BRIDGE_MODE_BLOCK_ALL in REASON_CODES
        assert DRY_RUN_DISABLED in REASON_CODES
        assert LIVE_TRADING_ENABLED in REASON_CODES
        assert REAL_ORDERS_ENABLED in REASON_CODES
        assert LEVERAGE_ENABLED in REASON_CODES
        assert SHORTING_ENABLED in REASON_CODES
        assert STALE_BRIDGE_CONTEXT in REASON_CODES
        assert UNSUPPORTED_BRIDGE_MODE in REASON_CODES
        assert LONG_RESEARCH_ALLOWED in REASON_CODES
        assert SHORT_RESEARCH_ALLOWED in REASON_CODES
        assert DEFAULT_BLOCK_ALL in REASON_CODES
        assert CALCULATION_ERROR in REASON_CODES

    def test_reason_codes_are_strings(self) -> None:
        for code in REASON_CODES:
            assert isinstance(code, str)
            assert len(code) > 0


class TestStrategyContractConfig:
    """Tests for StrategyContractConfig dataclass."""

    def test_default_values(self) -> None:
        config = StrategyContractConfig()
        assert config.stale_bridge_context_seconds == 300
        assert config.max_context_age_seconds == 300
        assert config.dry_run_required is True
        assert config.live_trading_enabled is False
        assert config.real_orders_enabled is False
        assert config.leverage_enabled is False
        assert config.shorting_enabled is False
        assert config.strategy_runtime_allowed is False
        assert config.entry_signals_allowed is False
        assert config.exit_signals_allowed is False
        assert config.allow_long_research is True
        assert config.allow_short_research is True
        assert config.unsupported_mode_action == StrategyContractMode.BLOCK_ALL

    def test_valid_custom_stale_seconds(self) -> None:
        config = StrategyContractConfig(stale_bridge_context_seconds=600)
        assert config.stale_bridge_context_seconds == 600

    def test_valid_custom_max_age(self) -> None:
        config = StrategyContractConfig(max_context_age_seconds=600)
        assert config.max_context_age_seconds == 600

    def test_invalid_stale_seconds_zero(self) -> None:
        with pytest.raises(ValueError, match="stale_bridge_context_seconds must be positive"):
            StrategyContractConfig(stale_bridge_context_seconds=0)

    def test_invalid_stale_seconds_negative(self) -> None:
        with pytest.raises(ValueError, match="stale_bridge_context_seconds must be positive"):
            StrategyContractConfig(stale_bridge_context_seconds=-1)

    def test_invalid_max_age_zero(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            StrategyContractConfig(max_context_age_seconds=0)

    def test_invalid_max_age_negative(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            StrategyContractConfig(max_context_age_seconds=-1)

    def test_dry_run_required_false_raises(self) -> None:
        with pytest.raises(ValueError, match="dry_run_required must be True for MVP-6"):
            StrategyContractConfig(dry_run_required=False)

    def test_live_trading_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-6"):
            StrategyContractConfig(live_trading_enabled=True)

    def test_real_orders_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-6"):
            StrategyContractConfig(real_orders_enabled=True)

    def test_leverage_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-6"):
            StrategyContractConfig(leverage_enabled=True)

    def test_shorting_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-6"):
            StrategyContractConfig(shorting_enabled=True)

    def test_strategy_runtime_allowed_true_raises(self) -> None:
        with pytest.raises(ValueError, match="strategy_runtime_allowed must be False for MVP-6"):
            StrategyContractConfig(strategy_runtime_allowed=True)

    def test_entry_signals_allowed_true_raises(self) -> None:
        with pytest.raises(ValueError, match="entry_signals_allowed must be False for MVP-6"):
            StrategyContractConfig(entry_signals_allowed=True)

    def test_exit_signals_allowed_true_raises(self) -> None:
        with pytest.raises(ValueError, match="exit_signals_allowed must be False for MVP-6"):
            StrategyContractConfig(exit_signals_allowed=True)

    def test_unsupported_mode_action_not_block_all_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported_mode_action must be BLOCK_ALL for MVP-6"):
            StrategyContractConfig(unsupported_mode_action=StrategyContractMode.LONG_RESEARCH_ONLY)

    def test_immutability(self) -> None:
        config = StrategyContractConfig()
        with pytest.raises(FrozenInstanceError):
            config.dry_run_required = False  # type: ignore[misc]


class TestStrategyContractInputRefs:
    """Tests for StrategyContractInputRefs dataclass."""

    def test_default_values(self) -> None:
        refs = StrategyContractInputRefs()
        assert refs.freqtrade_bridge_context == "data/freqtrade/current_freqtrade_context.json"
        assert refs.strategy_context == "data/strategy/current_strategy_context.json"

    def test_custom_values(self) -> None:
        refs = StrategyContractInputRefs(
            freqtrade_bridge_context="custom/input.json",
            strategy_context="custom/output.json",
        )
        assert refs.freqtrade_bridge_context == "custom/input.json"
        assert refs.strategy_context == "custom/output.json"

    def test_empty_freqtrade_path_raises(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_bridge_context must be a non-empty string"):
            StrategyContractInputRefs(freqtrade_bridge_context="")

    def test_empty_strategy_path_raises(self) -> None:
        with pytest.raises(ValueError, match="strategy_context must be a non-empty string"):
            StrategyContractInputRefs(strategy_context="")

    def test_immutability(self) -> None:
        refs = StrategyContractInputRefs()
        with pytest.raises(FrozenInstanceError):
            refs.freqtrade_bridge_context = "x"  # type: ignore[misc]


class TestStrategyContractSafetyFlags:
    """Tests for StrategyContractSafetyFlags dataclass."""

    def test_default_values(self) -> None:
        flags = StrategyContractSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.strategy_runtime_allowed is False
        assert flags.entry_signals_allowed is False
        assert flags.exit_signals_allowed is False
        assert flags.max_context_age_seconds == 300

    def test_valid_custom_max_age(self) -> None:
        flags = StrategyContractSafetyFlags(max_context_age_seconds=600)
        assert flags.max_context_age_seconds == 600

    def test_invalid_max_age_zero(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            StrategyContractSafetyFlags(max_context_age_seconds=0)

    def test_invalid_max_age_negative(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            StrategyContractSafetyFlags(max_context_age_seconds=-1)

    def test_dry_run_false_raises(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True for MVP-6"):
            StrategyContractSafetyFlags(dry_run=False)

    def test_live_trading_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-6"):
            StrategyContractSafetyFlags(live_trading_enabled=True)

    def test_real_orders_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-6"):
            StrategyContractSafetyFlags(real_orders_enabled=True)

    def test_leverage_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-6"):
            StrategyContractSafetyFlags(leverage_enabled=True)

    def test_shorting_enabled_true_raises(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-6"):
            StrategyContractSafetyFlags(shorting_enabled=True)

    def test_strategy_runtime_allowed_true_raises(self) -> None:
        with pytest.raises(ValueError, match="strategy_runtime_allowed must be False for MVP-6"):
            StrategyContractSafetyFlags(strategy_runtime_allowed=True)

    def test_entry_signals_allowed_true_raises(self) -> None:
        with pytest.raises(ValueError, match="entry_signals_allowed must be False for MVP-6"):
            StrategyContractSafetyFlags(entry_signals_allowed=True)

    def test_exit_signals_allowed_true_raises(self) -> None:
        with pytest.raises(ValueError, match="exit_signals_allowed must be False for MVP-6"):
            StrategyContractSafetyFlags(exit_signals_allowed=True)

    def test_to_dict(self) -> None:
        flags = StrategyContractSafetyFlags()
        d = flags.to_dict()
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["real_orders_enabled"] is False
        assert d["leverage_enabled"] is False
        assert d["shorting_enabled"] is False
        assert d["strategy_runtime_allowed"] is False
        assert d["entry_signals_allowed"] is False
        assert d["exit_signals_allowed"] is False
        assert d["max_context_age_seconds"] == 300

    def test_immutability(self) -> None:
        flags = StrategyContractSafetyFlags()
        with pytest.raises(FrozenInstanceError):
            flags.dry_run = False  # type: ignore[misc]


class TestStrategyContractDataQuality:
    """Tests for StrategyContractDataQuality dataclass."""

    def test_default_values(self) -> None:
        dq = StrategyContractDataQuality()
        assert dq.bridge_context_present is False
        assert dq.bridge_context_valid is False
        assert dq.bridge_context_stale is True
        assert dq.reason == "NOT_EVALUATED"

    def test_custom_values(self) -> None:
        dq = StrategyContractDataQuality(
            bridge_context_present=True,
            bridge_context_valid=True,
            bridge_context_stale=False,
            reason="VALID",
        )
        assert dq.bridge_context_present is True
        assert dq.bridge_context_valid is True
        assert dq.bridge_context_stale is False
        assert dq.reason == "VALID"

    def test_empty_reason_raises(self) -> None:
        with pytest.raises(ValueError, match="reason must be a non-empty string"):
            StrategyContractDataQuality(reason="")

    def test_to_dict(self) -> None:
        dq = StrategyContractDataQuality(
            bridge_context_present=True,
            bridge_context_valid=True,
            bridge_context_stale=False,
            reason="VALID",
        )
        d = dq.to_dict()
        assert d["bridge_context_present"] is True
        assert d["bridge_context_valid"] is True
        assert d["bridge_context_stale"] is False
        assert d["reason"] == "VALID"

    def test_immutability(self) -> None:
        dq = StrategyContractDataQuality()
        with pytest.raises(FrozenInstanceError):
            dq.bridge_context_present = True  # type: ignore[misc]


class TestStrategyContext:
    """Tests for StrategyContext dataclass."""

    def _make_valid(self) -> StrategyContext:
        ts = datetime.now(timezone.utc)
        return StrategyContext(
            timestamp=ts,
            status="DRY_RUN_READY",
            contract_state=StrategyContractState.DRY_RUN_READY,
            contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
            bridge_state="DRY_RUN_READY",
            bridge_mode="LONG_RESEARCH_ONLY",
            reason_codes=(LONG_RESEARCH_ALLOWED,),
        )

    def test_blocked_factory(self) -> None:
        ctx = StrategyContext.blocked(reason_codes=(MISSING_BRIDGE_CONTEXT,))
        assert ctx.contract_state == StrategyContractState.BLOCKED
        assert ctx.contract_mode == StrategyContractMode.BLOCK_ALL
        assert ctx.bridge_state == "UNKNOWN"
        assert ctx.bridge_mode == "BLOCK_ALL"
        assert ctx.status == "BLOCKED"
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.real_orders_enabled is False
        assert ctx.leverage_enabled is False
        assert ctx.shorting_enabled is False
        assert ctx.strategy_runtime_allowed is False
        assert ctx.entry_signals_allowed is False
        assert ctx.exit_signals_allowed is False
        assert ctx.version == "1.0"
        assert ctx.reason_codes == (MISSING_BRIDGE_CONTEXT,)
        assert ctx.is_blocking() is True

    def test_blocked_with_custom_reason(self) -> None:
        ctx = StrategyContext.blocked(reason_codes=(STALE_BRIDGE_CONTEXT,))
        assert ctx.reason_codes == (STALE_BRIDGE_CONTEXT,)
        assert ctx.data_quality.reason == STALE_BRIDGE_CONTEXT

    def test_blocked_with_custom_timestamp(self) -> None:
        ts = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        ctx = StrategyContext.blocked(reason_codes=(DEFAULT_BLOCK_ALL,), timestamp=ts)
        assert ctx.timestamp == ts

    def test_blocked_with_custom_status(self) -> None:
        ctx = StrategyContext.blocked(reason_codes=(DEFAULT_BLOCK_ALL,), status="CUSTOM_BLOCKED")
        assert ctx.status == "CUSTOM_BLOCKED"

    def test_blocked_empty_reason_codes_raises(self) -> None:
        with pytest.raises(ValueError, match="reason_codes must be non-empty"):
            StrategyContext.blocked(reason_codes=())

    def test_valid_context_creation(self) -> None:
        ctx = self._make_valid()
        assert ctx.contract_state == StrategyContractState.DRY_RUN_READY
        assert ctx.contract_mode == StrategyContractMode.LONG_RESEARCH_ONLY
        assert ctx.bridge_state == "DRY_RUN_READY"
        assert ctx.bridge_mode == "LONG_RESEARCH_ONLY"
        assert ctx.dry_run is True
        assert ctx.version == "1.0"
        assert ctx.is_blocking() is False

    def test_version_defaults_to_1_0(self) -> None:
        ctx = self._make_valid()
        assert ctx.version == "1.0"

    def test_version_cannot_be_empty(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="version must be a non-empty string"):
            StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(LONG_RESEARCH_ALLOWED,),
                version="",
            )

    def test_naive_timestamp_raises(self) -> None:
        ts = datetime.now()
        with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
            StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(LONG_RESEARCH_ALLOWED,),
            )

    def test_empty_status_raises(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="status must be a non-empty string"):
            StrategyContext(
                timestamp=ts,
                status="",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(LONG_RESEARCH_ALLOWED,),
            )

    def test_empty_reason_codes_raises(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="reason_codes must be non-empty"):
            StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(),
            )

    def test_dry_run_false_raises(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="dry_run must be True for MVP-6"):
            StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(LONG_RESEARCH_ALLOWED,),
                dry_run=False,
            )

    def test_live_trading_enabled_true_raises(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-6"):
            StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(LONG_RESEARCH_ALLOWED,),
                live_trading_enabled=True,
            )

    def test_real_orders_enabled_true_raises(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-6"):
            StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(LONG_RESEARCH_ALLOWED,),
                real_orders_enabled=True,
            )

    def test_leverage_enabled_true_raises(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-6"):
            StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(LONG_RESEARCH_ALLOWED,),
                leverage_enabled=True,
            )

    def test_shorting_enabled_true_raises(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-6"):
            StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(LONG_RESEARCH_ALLOWED,),
                shorting_enabled=True,
            )

    def test_strategy_runtime_allowed_true_raises(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="strategy_runtime_allowed must be False for MVP-6"):
            StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(LONG_RESEARCH_ALLOWED,),
                strategy_runtime_allowed=True,
            )

    def test_entry_signals_allowed_true_raises(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="entry_signals_allowed must be False for MVP-6"):
            StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(LONG_RESEARCH_ALLOWED,),
                entry_signals_allowed=True,
            )

    def test_exit_signals_allowed_true_raises(self) -> None:
        ts = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="exit_signals_allowed must be False for MVP-6"):
            StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state="DRY_RUN_READY",
                bridge_mode="LONG_RESEARCH_ONLY",
                reason_codes=(LONG_RESEARCH_ALLOWED,),
                exit_signals_allowed=True,
            )

    def test_default_safety_flags(self) -> None:
        ctx = self._make_valid()
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.real_orders_enabled is False
        assert ctx.leverage_enabled is False
        assert ctx.shorting_enabled is False
        assert ctx.strategy_runtime_allowed is False
        assert ctx.entry_signals_allowed is False
        assert ctx.exit_signals_allowed is False

    def test_is_blocking_for_blocked_state(self) -> None:
        ctx = StrategyContext.blocked(reason_codes=(DEFAULT_BLOCK_ALL,))
        assert ctx.is_blocking() is True

    def test_is_blocking_for_unknown_state(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = StrategyContext(
            timestamp=ts,
            status="BLOCKED",
            contract_state=StrategyContractState.UNKNOWN,
            contract_mode=StrategyContractMode.BLOCK_ALL,
            bridge_state="UNKNOWN",
            bridge_mode="BLOCK_ALL",
            reason_codes=(DEFAULT_BLOCK_ALL,),
        )
        assert ctx.is_blocking() is True

    def test_is_blocking_for_dry_run_ready(self) -> None:
        ctx = self._make_valid()
        assert ctx.is_blocking() is False

    def test_is_blocking_for_disabled(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = StrategyContext(
            timestamp=ts,
            status="BLOCKED",
            contract_state=StrategyContractState.DISABLED,
            contract_mode=StrategyContractMode.BLOCK_ALL,
            bridge_state="DISABLED",
            bridge_mode="BLOCK_ALL",
            reason_codes=(DEFAULT_BLOCK_ALL,),
        )
        assert ctx.is_blocking() is True

    def test_is_blocking_for_block_all_mode(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = StrategyContext(
            timestamp=ts,
            status="DRY_RUN_READY",
            contract_state=StrategyContractState.DRY_RUN_READY,
            contract_mode=StrategyContractMode.BLOCK_ALL,
            bridge_state="DRY_RUN_READY",
            bridge_mode="BLOCK_ALL",
            reason_codes=(DEFAULT_BLOCK_ALL,),
        )
        assert ctx.is_blocking() is True

    def test_immutability(self) -> None:
        ctx = StrategyContext.blocked(reason_codes=(DEFAULT_BLOCK_ALL,))
        with pytest.raises(FrozenInstanceError):
            ctx.dry_run = False  # type: ignore[misc]

    def test_safety_flags_nested(self) -> None:
        ctx = self._make_valid()
        assert ctx.safety_flags.dry_run is True
        assert ctx.safety_flags.max_context_age_seconds == 300

    def test_input_refs_nested(self) -> None:
        ctx = self._make_valid()
        assert ctx.input_refs.freqtrade_bridge_context == "data/freqtrade/current_freqtrade_context.json"
        assert ctx.input_refs.strategy_context == "data/strategy/current_strategy_context.json"

    def test_data_quality_nested(self) -> None:
        ctx = self._make_valid()
        assert ctx.data_quality.bridge_context_present is False
        assert ctx.data_quality.reason == "NOT_EVALUATED"

    def test_blocked_factory_data_quality_reason_from_first_code(self) -> None:
        ctx = StrategyContext.blocked(reason_codes=(STALE_BRIDGE_CONTEXT, CALCULATION_ERROR))
        assert ctx.data_quality.reason == STALE_BRIDGE_CONTEXT
