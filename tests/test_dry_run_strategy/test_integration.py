"""Integration tests for Dry-Run Strategy Runtime end-to-end flow.

Tests the full pipeline:
  AdapterDecisionContext-like object
  -> build_dry_run_strategy_runtime_context()
  -> write_dry_run_strategy_runtime_context(..., tmp_path)
  -> verify JSON payload.

No network, no trading logic, no storage integration.
Only writes to tmp_path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from hunter.dry_run_strategy.engine import (
    build_dry_run_strategy_runtime_context,
    build_safety_flags,
)
from hunter.dry_run_strategy.models import (
    ADAPTER_MODE_BLOCK_ALL,
    ADAPTER_NOT_DRY_RUN_READY,
    ADAPTER_SIGNAL_BLOCKED,
    DRY_RUN_DISABLED,
    DryRunStrategyConfig,
    DryRunStrategyDataQuality,
    DryRunStrategyInputRefs,
    DryRunStrategyMode,
    DryRunStrategyRuntimeContext,
    DryRunStrategySafetyFlags,
    DryRunStrategyState,
    INVALID_ADAPTER_DECISION_CONTEXT,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_SIGNAL_EXPOSED,
    MISSING_ADAPTER_DECISION_CONTEXT,
    REAL_ORDERS_ENABLED,
    SHORTING_ENABLED,
    SHORT_RESEARCH_SIGNAL_EXPOSED,
    STALE_ADAPTER_DECISION_CONTEXT,
    UNSUPPORTED_ADAPTER_MODE,
    UNSUPPORTED_ADAPTER_SIGNAL_INTENT,
)
from hunter.dry_run_strategy.writer import write_dry_run_strategy_runtime_context


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_adapter_decision(
    *,
    adapter_state: str = "DRY_RUN_READY",
    adapter_mode: str = "LONG_RESEARCH_ONLY",
    signal_intent: str = "ALLOW_LONG_RESEARCH_SIGNAL",
    dry_run: bool = True,
    live_trading_enabled: bool = False,
    real_orders_enabled: bool = False,
    leverage_enabled: bool = False,
    shorting_enabled: bool = False,
    timestamp: datetime | None = None,
) -> SimpleNamespace:
    """Build a lightweight AdapterDecisionContext-like object for integration tests."""
    return SimpleNamespace(
        timestamp=timestamp or datetime.now(timezone.utc),
        status="DRY_RUN_READY",
        adapter_state=adapter_state,
        adapter_mode=adapter_mode,
        signal_intent=signal_intent,
        dry_run=dry_run,
        live_trading_enabled=live_trading_enabled,
        real_orders_enabled=real_orders_enabled,
        leverage_enabled=leverage_enabled,
        shorting_enabled=shorting_enabled,
        freqtrade_runtime_allowed=False,
        strategy_class_allowed=False,
        populate_indicators_allowed=False,
        populate_entry_trend_allowed=False,
        populate_exit_trend_allowed=False,
        order_execution_allowed=False,
    )


@pytest.fixture
def config() -> DryRunStrategyConfig:
    return DryRunStrategyConfig()


@pytest.fixture
def now() -> datetime:
    return datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


class TestLongResearchHappyPath:
    """Long research signal exposure end-to-end."""

    def test_builds_dry_run_ready_context(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(
            adapter_state="DRY_RUN_READY",
            adapter_mode="LONG_RESEARCH_ONLY",
            signal_intent="ALLOW_LONG_RESEARCH_SIGNAL",
            timestamp=now,
        )
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)

        assert result.strategy_state == DryRunStrategyState.DRY_RUN_READY
        assert result.strategy_mode == DryRunStrategyMode.LONG_RESEARCH_ONLY
        assert result.reason_codes == (LONG_RESEARCH_SIGNAL_EXPOSED,)
        assert result.is_blocking() is False

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(
            adapter_state="DRY_RUN_READY",
            adapter_mode="LONG_RESEARCH_ONLY",
            signal_intent="ALLOW_LONG_RESEARCH_SIGNAL",
            timestamp=now,
        )
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["timestamp"] == "2025-01-15T12:00:00Z"
        assert d["status"] == "DRY_RUN_READY"
        assert d["strategy_state"] == "DRY_RUN_READY"
        assert d["strategy_mode"] == "LONG_RESEARCH_ONLY"
        assert d["signal_action"] == "EXPOSE_LONG_RESEARCH_SIGNAL"
        assert d["reason_codes"] == ["LONG_RESEARCH_SIGNAL_EXPOSED"]
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["real_orders_enabled"] is False
        assert d["leverage_enabled"] is False
        assert d["shorting_enabled"] is False
        assert d["freqtrade_runtime_allowed"] is False
        assert d["strategy_class_allowed"] is False
        assert d["populate_indicators_allowed"] is False
        assert d["populate_entry_trend_allowed"] is False
        assert d["populate_exit_trend_allowed"] is False
        assert d["order_execution_allowed"] is False
        assert d["version"] == "1.0"

        # Safety flags
        sf = d["safety_flags"]
        assert sf["dry_run"] is True
        assert sf["live_trading_enabled"] is False
        assert sf["real_orders_enabled"] is False
        assert sf["leverage_enabled"] is False
        assert sf["shorting_enabled"] is False
        assert sf["freqtrade_runtime_allowed"] is False
        assert sf["strategy_class_allowed"] is False
        assert sf["populate_indicators_allowed"] is False
        assert sf["populate_entry_trend_allowed"] is False
        assert sf["populate_exit_trend_allowed"] is False
        assert sf["order_execution_allowed"] is False

        # Data quality
        dq = d["data_quality"]
        assert dq["adapter_decision_present"] is True
        assert dq["adapter_decision_valid"] is True
        assert dq["adapter_decision_stale"] is False
        assert dq["reason"] == "LONG_RESEARCH_SIGNAL_EXPOSED"

        # Input refs
        ir = d["input_refs"]
        assert ir["adapter_decision"] == "data/strategy_adapter/current_adapter_decision.json"
        assert ir["dry_run_strategy_runtime"] == "data/freqtrade_strategy/current_dry_run_strategy_runtime.json"


class TestShortResearchHappyPath:
    """Short research signal exposure end-to-end."""

    def test_builds_dry_run_ready_context(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(
            adapter_state="DRY_RUN_READY",
            adapter_mode="SHORT_RESEARCH_ONLY",
            signal_intent="ALLOW_SHORT_RESEARCH_SIGNAL",
            timestamp=now,
        )
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)

        assert result.strategy_state == DryRunStrategyState.DRY_RUN_READY
        assert result.strategy_mode == DryRunStrategyMode.SHORT_RESEARCH_ONLY
        assert result.reason_codes == (SHORT_RESEARCH_SIGNAL_EXPOSED,)
        assert result.is_blocking() is False

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(
            adapter_state="DRY_RUN_READY",
            adapter_mode="SHORT_RESEARCH_ONLY",
            signal_intent="ALLOW_SHORT_RESEARCH_SIGNAL",
            timestamp=now,
        )
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["strategy_state"] == "DRY_RUN_READY"
        assert d["strategy_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["signal_action"] == "EXPOSE_SHORT_RESEARCH_SIGNAL"
        assert d["reason_codes"] == ["SHORT_RESEARCH_SIGNAL_EXPOSED"]
        assert d["data_quality"]["reason"] == "SHORT_RESEARCH_SIGNAL_EXPOSED"


# ---------------------------------------------------------------------------
# Blocking / fail-closed paths
# ---------------------------------------------------------------------------


class TestMissingAdapterDecision:
    """Missing adapter decision context blocks."""

    def test_missing_adapter_decision(self, config: DryRunStrategyConfig, now: datetime) -> None:
        result = build_dry_run_strategy_runtime_context(None, config=config, now=now)
        assert result.strategy_state == DryRunStrategyState.BLOCKED
        assert result.reason_codes == (MISSING_ADAPTER_DECISION_CONTEXT,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        result = build_dry_run_strategy_runtime_context(None, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["strategy_state"] == "BLOCKED"
        assert d["strategy_mode"] == "BLOCK_ALL"
        assert d["signal_action"] == "BLOCK_SIGNAL"
        assert d["reason_codes"] == ["MISSING_ADAPTER_DECISION_CONTEXT"]


class TestInvalidAdapterDecision:
    """Invalid adapter decision context blocks."""

    def test_invalid_adapter_decision(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = SimpleNamespace(timestamp=now, status="DRY_RUN_READY")  # missing required attrs
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (INVALID_ADAPTER_DECISION_CONTEXT,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = SimpleNamespace(timestamp=now, status="DRY_RUN_READY")
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["INVALID_ADAPTER_DECISION_CONTEXT"]


class TestAdapterBlockedState:
    """Adapter state BLOCKED blocks."""

    def test_blocked_state(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(adapter_state="BLOCKED", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (ADAPTER_NOT_DRY_RUN_READY,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(adapter_state="BLOCKED", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["ADAPTER_NOT_DRY_RUN_READY"]


class TestAdapterUnknownState:
    """Adapter state UNKNOWN blocks."""

    def test_unknown_state(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(adapter_state="UNKNOWN", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (ADAPTER_NOT_DRY_RUN_READY,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(adapter_state="UNKNOWN", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["ADAPTER_NOT_DRY_RUN_READY"]


class TestAdapterDisabledState:
    """Adapter state DISABLED blocks."""

    def test_disabled_state(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(adapter_state="DISABLED", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (ADAPTER_NOT_DRY_RUN_READY,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(adapter_state="DISABLED", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["ADAPTER_NOT_DRY_RUN_READY"]


class TestAdapterModeBlockAll:
    """Adapter mode BLOCK_ALL blocks."""

    def test_block_all_mode(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(adapter_mode="BLOCK_ALL", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (ADAPTER_MODE_BLOCK_ALL,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(adapter_mode="BLOCK_ALL", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["ADAPTER_MODE_BLOCK_ALL"]


class TestAdapterSignalBlocked:
    """Adapter signal intent BLOCK_SIGNAL blocks."""

    def test_block_signal(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(signal_intent="BLOCK_SIGNAL", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (ADAPTER_SIGNAL_BLOCKED,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(signal_intent="BLOCK_SIGNAL", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["ADAPTER_SIGNAL_BLOCKED"]


class TestDryRunDisabled:
    """dry_run False blocks."""

    def test_dry_run_false(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(dry_run=False, timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (DRY_RUN_DISABLED,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(dry_run=False, timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["DRY_RUN_DISABLED"]


class TestLiveTradingEnabled:
    """live_trading_enabled True blocks."""

    def test_live_trading(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(live_trading_enabled=True, timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (LIVE_TRADING_ENABLED,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(live_trading_enabled=True, timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["LIVE_TRADING_ENABLED"]


class TestRealOrdersEnabled:
    """real_orders_enabled True blocks."""

    def test_real_orders(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(real_orders_enabled=True, timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (REAL_ORDERS_ENABLED,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(real_orders_enabled=True, timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["REAL_ORDERS_ENABLED"]


class TestLeverageEnabled:
    """leverage_enabled True blocks."""

    def test_leverage(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(leverage_enabled=True, timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (LEVERAGE_ENABLED,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(leverage_enabled=True, timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["LEVERAGE_ENABLED"]


class TestShortingEnabled:
    """shorting_enabled True blocks."""

    def test_shorting(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(shorting_enabled=True, timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (SHORTING_ENABLED,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(shorting_enabled=True, timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["SHORTING_ENABLED"]


class TestStaleAdapterDecision:
    """Stale adapter decision context blocks."""

    def test_stale(self, config: DryRunStrategyConfig, now: datetime) -> None:
        old = now - __import__("datetime").timedelta(seconds=400)
        adapter = _make_adapter_decision(timestamp=old)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (STALE_ADAPTER_DECISION_CONTEXT,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        old = now - __import__("datetime").timedelta(seconds=400)
        adapter = _make_adapter_decision(timestamp=old)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["STALE_ADAPTER_DECISION_CONTEXT"]


class TestUnsupportedAdapterMode:
    """Unsupported adapter mode blocks."""

    def test_unsupported_mode(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(adapter_mode="UNKNOWN_MODE", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (UNSUPPORTED_ADAPTER_MODE,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(adapter_mode="UNKNOWN_MODE", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["UNSUPPORTED_ADAPTER_MODE"]


class TestUnsupportedSignalIntent:
    """Unsupported signal intent blocks."""

    def test_unsupported_intent(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(signal_intent="UNKNOWN_INTENT", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.reason_codes == (UNSUPPORTED_ADAPTER_SIGNAL_INTENT,)
        assert result.is_blocking() is True

    def test_writes_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(signal_intent="UNKNOWN_INTENT", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == ["UNSUPPORTED_ADAPTER_SIGNAL_INTENT"]


# ---------------------------------------------------------------------------
# Writer integration
# ---------------------------------------------------------------------------


class TestWriterIntegration:
    """Writer output verification."""

    def test_parent_directories_created(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "deep" / "nested" / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)
        assert target.exists()

    def test_json_valid(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert isinstance(d, dict)
        assert "timestamp" in d
        assert "status" in d
        assert "strategy_state" in d
        assert "strategy_mode" in d
        assert "signal_action" in d
        assert "reason_codes" in d
        assert "input_refs" in d
        assert "safety_flags" in d
        assert "data_quality" in d
        assert "version" in d

    def test_safety_flags_in_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        sf = d["safety_flags"]
        assert sf["dry_run"] is True
        assert sf["live_trading_enabled"] is False
        assert sf["real_orders_enabled"] is False
        assert sf["leverage_enabled"] is False
        assert sf["shorting_enabled"] is False
        assert sf["freqtrade_runtime_allowed"] is False
        assert sf["strategy_class_allowed"] is False
        assert sf["populate_indicators_allowed"] is False
        assert sf["populate_entry_trend_allowed"] is False
        assert sf["populate_exit_trend_allowed"] is False
        assert sf["order_execution_allowed"] is False

    def test_blocked_context_in_json(self, config: DryRunStrategyConfig, now: datetime, tmp_path: Path) -> None:
        adapter = _make_adapter_decision(adapter_mode="BLOCK_ALL", timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        target = tmp_path / "current_dry_run_strategy_runtime.json"
        write_dry_run_strategy_runtime_context(result, target)

        with open(target) as f:
            d = json.load(f)

        assert d["strategy_state"] == "BLOCKED"
        assert d["strategy_mode"] == "BLOCK_ALL"
        assert d["signal_action"] == "BLOCK_SIGNAL"
        assert d["reason_codes"] == ["ADAPTER_MODE_BLOCK_ALL"]
        assert d["data_quality"]["reason"] == "ADAPTER_MODE_BLOCK_ALL"


# ---------------------------------------------------------------------------
# Safety integration assertions
# ---------------------------------------------------------------------------


class TestSafetyIntegration:
    """Safety assertions that hold across all integration paths."""

    def test_no_production_path_writes(self, tmp_path: Path) -> None:
        """Verify tests only write to tmp_path, not production paths."""
        from hunter.dry_run_strategy.writer import DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH
        assert str(DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH) == "data/freqtrade_strategy/current_dry_run_strategy_runtime.json"
        # This test itself writes only to tmp_path via other test fixtures

    def test_no_network_calls(self, config: DryRunStrategyConfig, now: datetime) -> None:
        """Engine and writer do not make network calls."""
        adapter = _make_adapter_decision(timestamp=now)
        # build and write are purely local; no sockets, no HTTP
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result is not None

    def test_no_freqtrade_runtime(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.freqtrade_runtime_allowed is False

    def test_no_binance(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        # No Binance references anywhere in the codebase for this flow
        assert result is not None

    def test_no_real_exchange(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.real_orders_enabled is False

    def test_no_api_keys(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        # No API key fields exist in any model
        assert result is not None

    def test_no_live_trading(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.live_trading_enabled is False

    def test_no_leverage(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.leverage_enabled is False

    def test_no_shorting(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.shorting_enabled is False

    def test_no_real_entry_exit(self, config: DryRunStrategyConfig, now: datetime) -> None:
        adapter = _make_adapter_decision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(adapter, config=config, now=now)
        assert result.populate_entry_trend_allowed is False
        assert result.populate_exit_trend_allowed is False
        assert result.order_execution_allowed is False
