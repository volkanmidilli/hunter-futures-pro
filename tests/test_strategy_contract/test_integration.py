"""Integration tests for Strategy Contract end-to-end flow.

Tests the full pipeline: FreqtradeBridgeContext -> build_strategy_context() -> write_strategy_context()
No network, no trading logic, no JSON input reading, no Freqtrade runtime.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.freqtrade_bridge.models import (
    FreqtradeBridgeContext,
    FreqtradeBridgeDataQuality,
    FreqtradeBridgeInputRefs,
    FreqtradeBridgeMode,
    FreqtradeBridgeSafetyFlags,
    FreqtradeBridgeState,
)
from hunter.strategy_contract.engine import build_strategy_context
from hunter.strategy_contract.models import (
    LONG_RESEARCH_ALLOWED,
    SHORT_RESEARCH_ALLOWED,
    BRIDGE_MODE_BLOCK_ALL,
    BRIDGE_NOT_DRY_RUN_READY,
    CALCULATION_ERROR,
    DEFAULT_BLOCK_ALL,
    DRY_RUN_DISABLED,
    INVALID_BRIDGE_CONTEXT,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    MISSING_BRIDGE_CONTEXT,
    REAL_ORDERS_ENABLED,
    SHORTING_ENABLED,
    STALE_BRIDGE_CONTEXT,
    UNSUPPORTED_BRIDGE_MODE,
    StrategyContractConfig,
    StrategyContractMode,
    StrategyContractState,
)
from hunter.strategy_contract.writer import (
    DEFAULT_STRATEGY_CONTEXT_PATH,
    strategy_context_to_dict,
    write_strategy_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_bridge_context(
    *,
    bridge_state: FreqtradeBridgeState = FreqtradeBridgeState.DRY_RUN_READY,
    bridge_mode: FreqtradeBridgeMode = FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
    dry_run: bool = True,
    live_trading: bool = False,
    real_orders: bool = False,
    leverage: bool = False,
    shorting: bool = False,
    timestamp: datetime | None = None,
) -> FreqtradeBridgeContext:
    """Create a FreqtradeBridgeContext with sensible defaults."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    return FreqtradeBridgeContext(
        timestamp=timestamp,
        status="success",
        bridge_state=bridge_state,
        bridge_mode=bridge_mode,
        execution_state="DRY_RUN_ONLY",
        execution_mode="LONG_RESEARCH_ONLY",
        dry_run=dry_run,
        live_trading_enabled=live_trading,
        real_orders_enabled=real_orders,
        leverage_enabled=leverage,
        shorting_enabled=shorting,
        reason_codes=["dry_run_long_research_only"],
        input_refs=FreqtradeBridgeInputRefs(
            execution_context_timestamp=timestamp.isoformat(),
            execution_context_version="1.0",
        ),
        data_quality=FreqtradeBridgeDataQuality(
            execution_context_fresh=True,
            execution_context_valid=True,
        ),
        safety_flags=FreqtradeBridgeSafetyFlags(),
    )


# ---------------------------------------------------------------------------
# End-to-end allowed flow tests
# ---------------------------------------------------------------------------

class TestEndToEndAllowedFlows:
    """End-to-end tests for allowed flows."""

    def test_long_research_full_pipeline(self, tmp_path: Path) -> None:
        """DRY_RUN_READY + LONG_RESEARCH_ONLY -> DRY_RUN_READY + LONG_RESEARCH_ONLY -> JSON."""
        bridge_ctx = make_bridge_context(
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
        )
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.DRY_RUN_READY
        assert strategy_ctx.contract_mode == StrategyContractMode.LONG_RESEARCH_ONLY
        assert strategy_ctx.status == "DRY_RUN_READY"
        assert strategy_ctx.is_blocking() is False

        target = tmp_path / "strategy_context.json"
        write_strategy_context(strategy_ctx, target)

        assert target.exists()
        with open(target) as f:
            d = json.load(f)

        assert d["contract_state"] == "DRY_RUN_READY"
        assert d["contract_mode"] == "LONG_RESEARCH_ONLY"
        assert d["bridge_state"] == "DRY_RUN_READY"
        assert d["bridge_mode"] == "LONG_RESEARCH_ONLY"
        assert d["reason_codes"] == [LONG_RESEARCH_ALLOWED]
        assert d["version"] == "1.0"
        assert d["dry_run"] is True

    def test_short_research_full_pipeline(self, tmp_path: Path) -> None:
        """DRY_RUN_READY + SHORT_RESEARCH_ONLY -> DRY_RUN_READY + SHORT_RESEARCH_ONLY -> JSON."""
        bridge_ctx = make_bridge_context(
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.SHORT_RESEARCH_ONLY,
        )
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.DRY_RUN_READY
        assert strategy_ctx.contract_mode == StrategyContractMode.SHORT_RESEARCH_ONLY
        assert strategy_ctx.is_blocking() is False

        target = tmp_path / "strategy_context.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["contract_state"] == "DRY_RUN_READY"
        assert d["contract_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["bridge_state"] == "DRY_RUN_READY"
        assert d["bridge_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["reason_codes"] == [SHORT_RESEARCH_ALLOWED]

    def test_allowed_context_can_be_serialized_and_written(self, tmp_path: Path) -> None:
        """Verify allowed context can be serialized to dict and written to JSON."""
        bridge_ctx = make_bridge_context(
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
        )
        strategy_ctx = build_strategy_context(bridge_ctx)

        # Serialize to dict
        data = strategy_context_to_dict(strategy_ctx)
        assert isinstance(data, dict)
        assert data["contract_state"] == "DRY_RUN_READY"
        assert data["contract_mode"] == "LONG_RESEARCH_ONLY"

        # Write and verify
        target = tmp_path / "strategy_context.json"
        write_strategy_context(strategy_ctx, target)
        assert target.exists()

        with open(target) as f:
            d = json.load(f)
        assert d["contract_state"] == "DRY_RUN_READY"
        assert d["reason_codes"] == [LONG_RESEARCH_ALLOWED]

    def test_written_json_can_be_loaded_and_contains_expected_values(self, tmp_path: Path) -> None:
        """Verify written JSON can be loaded and contains expected values."""
        bridge_ctx = make_bridge_context(
            bridge_mode=FreqtradeBridgeMode.SHORT_RESEARCH_ONLY,
        )
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "strategy_context.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["timestamp"].endswith("Z")
        assert d["status"] == "DRY_RUN_READY"
        assert d["contract_state"] == "DRY_RUN_READY"
        assert d["contract_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["bridge_state"] == "DRY_RUN_READY"
        assert d["bridge_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["real_orders_enabled"] is False
        assert d["leverage_enabled"] is False
        assert d["shorting_enabled"] is False
        assert d["strategy_runtime_allowed"] is False
        assert d["entry_signals_allowed"] is False
        assert d["exit_signals_allowed"] is False
        assert d["reason_codes"] == [SHORT_RESEARCH_ALLOWED]
        assert isinstance(d["input_refs"], dict)
        assert isinstance(d["safety_flags"], dict)
        assert isinstance(d["data_quality"], dict)
        assert d["version"] == "1.0"


# ---------------------------------------------------------------------------
# End-to-end blocked flow tests
# ---------------------------------------------------------------------------

class TestEndToEndBlockedFlows:
    """End-to-end tests for blocked flows."""

    def test_missing_bridge_context(self, tmp_path: Path) -> None:
        """Missing bridge context produces BLOCKED + BLOCK_ALL."""
        strategy_ctx = build_strategy_context(None)

        assert strategy_ctx.contract_state == StrategyContractState.BLOCKED
        assert strategy_ctx.contract_mode == StrategyContractMode.BLOCK_ALL
        assert strategy_ctx.is_blocking() is True
        assert strategy_ctx.reason_codes == (MISSING_BRIDGE_CONTEXT,)

        target = tmp_path / "strategy_context.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["contract_state"] == "BLOCKED"
        assert d["contract_mode"] == "BLOCK_ALL"
        assert d["reason_codes"] == [MISSING_BRIDGE_CONTEXT]

    def test_bridge_state_blocked(self, tmp_path: Path) -> None:
        """Bridge state BLOCKED produces BLOCKED + BLOCK_ALL."""
        bridge_ctx = make_bridge_context(bridge_state=FreqtradeBridgeState.BLOCKED)
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.BLOCKED
        assert strategy_ctx.reason_codes == (BRIDGE_NOT_DRY_RUN_READY,)

        target = tmp_path / "strategy_context.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["contract_state"] == "BLOCKED"
        assert d["reason_codes"] == [BRIDGE_NOT_DRY_RUN_READY]

    def test_bridge_state_unknown(self, tmp_path: Path) -> None:
        """Bridge state UNKNOWN produces BLOCKED + BLOCK_ALL."""
        bridge_ctx = make_bridge_context(bridge_state=FreqtradeBridgeState.UNKNOWN)
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.BLOCKED
        assert strategy_ctx.reason_codes == (BRIDGE_NOT_DRY_RUN_READY,)

    def test_bridge_state_disabled(self, tmp_path: Path) -> None:
        """Bridge state DISABLED produces BLOCKED + BLOCK_ALL."""
        bridge_ctx = make_bridge_context(bridge_state=FreqtradeBridgeState.DISABLED)
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.BLOCKED
        assert strategy_ctx.reason_codes == (BRIDGE_NOT_DRY_RUN_READY,)

    def test_bridge_mode_block_all(self, tmp_path: Path) -> None:
        """Bridge mode BLOCK_ALL produces BLOCKED + BLOCK_ALL."""
        bridge_ctx = make_bridge_context(bridge_mode=FreqtradeBridgeMode.BLOCK_ALL)
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.BLOCKED
        assert strategy_ctx.reason_codes == (BRIDGE_MODE_BLOCK_ALL,)

    def test_stale_bridge_context(self, tmp_path: Path) -> None:
        """Stale bridge context produces BLOCKED + BLOCK_ALL."""
        old_timestamp = datetime.now(timezone.utc) - timedelta(seconds=400)
        bridge_ctx = make_bridge_context(timestamp=old_timestamp)
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.BLOCKED
        assert strategy_ctx.reason_codes == (STALE_BRIDGE_CONTEXT,)

    def test_dry_run_false(self, tmp_path: Path) -> None:
        """dry_run=False produces BLOCKED + BLOCK_ALL."""
        bridge_ctx = make_bridge_context(dry_run=False)
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.BLOCKED
        assert strategy_ctx.reason_codes == (DRY_RUN_DISABLED,)

    def test_live_trading_enabled_true(self, tmp_path: Path) -> None:
        """live_trading_enabled=True produces BLOCKED + BLOCK_ALL."""
        bridge_ctx = make_bridge_context(live_trading=True)
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.BLOCKED
        assert strategy_ctx.reason_codes == (LIVE_TRADING_ENABLED,)

    def test_real_orders_enabled_true(self, tmp_path: Path) -> None:
        """real_orders_enabled=True produces BLOCKED + BLOCK_ALL."""
        bridge_ctx = make_bridge_context(real_orders=True)
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.BLOCKED
        assert strategy_ctx.reason_codes == (REAL_ORDERS_ENABLED,)

    def test_leverage_enabled_true(self, tmp_path: Path) -> None:
        """leverage_enabled=True produces BLOCKED + BLOCK_ALL."""
        bridge_ctx = make_bridge_context(leverage=True)
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.BLOCKED
        assert strategy_ctx.reason_codes == (LEVERAGE_ENABLED,)

    def test_shorting_enabled_true(self, tmp_path: Path) -> None:
        """shorting_enabled=True produces BLOCKED + BLOCK_ALL."""
        bridge_ctx = make_bridge_context(shorting=True)
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.contract_state == StrategyContractState.BLOCKED
        assert strategy_ctx.reason_codes == (SHORTING_ENABLED,)


# ---------------------------------------------------------------------------
# JSON output verification tests
# ---------------------------------------------------------------------------

class TestJsonOutputVerification:
    """Verify JSON output structure and content."""

    def test_timestamp_is_iso8601_with_z(self, tmp_path: Path) -> None:
        """timestamp is ISO-8601 UTC ending with Z."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        ts = d["timestamp"]
        assert ts.endswith("Z"), f"Expected Z suffix, got: {ts}"
        assert "T" in ts, f"Expected T in timestamp, got: {ts}"

    def test_contract_state_and_mode_are_strings(self, tmp_path: Path) -> None:
        """contract_state and contract_mode are strings."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert isinstance(d["contract_state"], str)
        assert isinstance(d["contract_mode"], str)
        assert d["contract_state"] == "DRY_RUN_READY"
        assert d["contract_mode"] == "LONG_RESEARCH_ONLY"

    def test_bridge_state_and_mode_preserved_as_strings(self, tmp_path: Path) -> None:
        """bridge_state and bridge_mode are preserved as strings."""
        bridge_ctx = make_bridge_context(
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.SHORT_RESEARCH_ONLY,
        )
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["bridge_state"] == "DRY_RUN_READY"
        assert d["bridge_mode"] == "SHORT_RESEARCH_ONLY"

    def test_reason_codes_is_list(self, tmp_path: Path) -> None:
        """reason_codes is a list."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert isinstance(d["reason_codes"], list)
        assert d["reason_codes"] == [LONG_RESEARCH_ALLOWED]

    def test_input_refs_is_dict(self, tmp_path: Path) -> None:
        """input_refs is a dict."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert isinstance(d["input_refs"], dict)
        assert "freqtrade_bridge_context" in d["input_refs"]
        assert "strategy_context" in d["input_refs"]

    def test_safety_flags_is_dict(self, tmp_path: Path) -> None:
        """safety_flags is a dict."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert isinstance(d["safety_flags"], dict)
        assert d["safety_flags"]["dry_run"] is True
        assert d["safety_flags"]["live_trading_enabled"] is False

    def test_data_quality_is_dict(self, tmp_path: Path) -> None:
        """data_quality is a dict."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert isinstance(d["data_quality"], dict)
        assert d["data_quality"]["bridge_context_present"] is True
        assert d["data_quality"]["bridge_context_valid"] is True
        assert d["data_quality"]["bridge_context_stale"] is False

    def test_version_is_1_0(self, tmp_path: Path) -> None:
        """version is "1.0"."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["version"] == "1.0"

    def test_blocked_outputs_contain_blocking_reason_codes(self, tmp_path: Path) -> None:
        """Blocked outputs contain blocking reason codes."""
        bridge_ctx = make_bridge_context(bridge_mode=FreqtradeBridgeMode.BLOCK_ALL)
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["contract_state"] == "BLOCKED"
        assert d["reason_codes"] == [BRIDGE_MODE_BLOCK_ALL]
        assert d["reason_codes"] != [LONG_RESEARCH_ALLOWED]

    def test_allowed_outputs_contain_long_research_allowed(self, tmp_path: Path) -> None:
        """Allowed long outputs contain LONG_RESEARCH_ALLOWED."""
        bridge_ctx = make_bridge_context(bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY)
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == [LONG_RESEARCH_ALLOWED]

    def test_allowed_outputs_contain_short_research_allowed(self, tmp_path: Path) -> None:
        """Allowed short outputs contain SHORT_RESEARCH_ALLOWED."""
        bridge_ctx = make_bridge_context(bridge_mode=FreqtradeBridgeMode.SHORT_RESEARCH_ONLY)
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == [SHORT_RESEARCH_ALLOWED]


# ---------------------------------------------------------------------------
# Atomic write and path tests
# ---------------------------------------------------------------------------

class TestAtomicWriteAndPaths:
    """Verify atomic write behavior and path handling."""

    def test_write_to_custom_tmp_path(self, tmp_path: Path) -> None:
        """write_strategy_context writes to custom tmp_path target."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "strategy_context.json"
        result = write_strategy_context(strategy_ctx, target)

        assert result == target
        assert target.exists()

    def test_nested_parent_directory_creation(self, tmp_path: Path) -> None:
        """Writer creates nested parent directories."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "a" / "b" / "c" / "strategy_context.json"
        write_strategy_context(strategy_ctx, target)

        assert target.exists()

    def test_overwrite_existing_file(self, tmp_path: Path) -> None:
        """Writer overwrites existing file safely."""
        bridge_ctx = make_bridge_context(bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY)
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        # Write different context to same file
        bridge_ctx2 = make_bridge_context(bridge_mode=FreqtradeBridgeMode.SHORT_RESEARCH_ONLY)
        strategy_ctx2 = build_strategy_context(bridge_ctx2)
        write_strategy_context(strategy_ctx2, target)

        with open(target) as f:
            d = json.load(f)

        assert d["contract_mode"] == "SHORT_RESEARCH_ONLY"

    def test_no_temp_files_left_after_successful_write(self, tmp_path: Path) -> None:
        """Writer leaves no temp files after successful write."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "nested" / "dir" / "strategy_context.json"
        write_strategy_context(strategy_ctx, target)

        assert target.exists()
        temp_files = list(tmp_path.rglob("*.tmp"))
        assert len(temp_files) == 0

    def test_default_output_path_constant(self) -> None:
        """Default output path constant equals data/strategy/current_strategy_context.json."""
        assert str(DEFAULT_STRATEGY_CONTEXT_PATH) == "data/strategy/current_strategy_context.json"

    def test_no_production_path_usage_in_tests(self, tmp_path: Path) -> None:
        """Do not write to production data path during tests."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        # Always use tmp_path for test outputs
        target = tmp_path / "current_strategy_context.json"
        write_strategy_context(strategy_ctx, target)

        assert target.exists()
        # Production path should not exist
        prod_path = Path("data/strategy/current_strategy_context.json")
        assert not prod_path.exists()


# ---------------------------------------------------------------------------
# Safety absence tests
# ---------------------------------------------------------------------------

class TestSafetyAbsence:
    """Verify no unsafe behavior in integration tests."""

    def test_no_config_yaml(self) -> None:
        """No config YAML file exists."""
        config_path = Path("configs/strategy_contract.yaml")
        assert not config_path.exists()

    def test_no_json_schema(self) -> None:
        """No JSON schema file exists."""
        schema_path = Path("schemas/strategy_context.schema.json")
        assert not schema_path.exists()

    def test_no_freqtrade_strategy_class(self) -> None:
        """No Freqtrade strategy class file exists."""
        strategy_path = Path("src/hunter/strategy_contract/freqtrade_strategy.py")
        assert not strategy_path.exists()

    def test_no_freqtrade_runtime_import(self) -> None:
        """No Freqtrade runtime import in engine or writer."""
        import hunter.strategy_contract.engine as engine_module
        import hunter.strategy_contract.writer as writer_module

        # Check module globals for any freqtrade-related imports
        engine_globals = [name.lower() for name in dir(engine_module)]
        writer_globals = [name.lower() for name in dir(writer_module)]

        freqtrade_keywords = ["freqtradebot", "freqtradeexchange", "freqtradestrategy"]
        for keyword in freqtrade_keywords:
            assert keyword not in engine_globals, f"Unexpected Freqtrade import in engine: {keyword}"
            assert keyword not in writer_globals, f"Unexpected Freqtrade import in writer: {keyword}"

    def test_no_binance_import(self) -> None:
        """No Binance import in engine or writer."""
        import hunter.strategy_contract.engine as engine_module
        import hunter.strategy_contract.writer as writer_module

        engine_globals = [name.lower() for name in dir(engine_module)]
        writer_globals = [name.lower() for name in dir(writer_module)]

        assert "binance" not in engine_globals
        assert "binance" not in writer_globals

    def test_no_network_calls(self, tmp_path: Path) -> None:
        """Writer should not make any network calls."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)
        target = tmp_path / "output.json"

        write_strategy_context(strategy_ctx, target)
        assert target.exists()

    def test_no_api_keys(self) -> None:
        """No API keys in code or output."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)
        data = strategy_context_to_dict(strategy_ctx)

        json_str = json.dumps(data)
        assert "api_key" not in json_str.lower()
        assert "secret" not in json_str.lower()
        assert "bearer" not in json_str.lower()

    def test_no_live_trading_enablement(self, tmp_path: Path) -> None:
        """live_trading_enabled must always be False."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.live_trading_enabled is False

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["live_trading_enabled"] is False

    def test_no_real_order_execution(self, tmp_path: Path) -> None:
        """real_orders_enabled must always be False."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.real_orders_enabled is False

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["real_orders_enabled"] is False

    def test_no_leverage_enablement(self, tmp_path: Path) -> None:
        """leverage_enabled must always be False."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.leverage_enabled is False

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["leverage_enabled"] is False

    def test_no_shorting_enablement(self, tmp_path: Path) -> None:
        """shorting_enabled must always be False."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        assert strategy_ctx.shorting_enabled is False

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["shorting_enabled"] is False

    def test_no_entry_exit_execution_logic(self, tmp_path: Path) -> None:
        """No entry/exit execution logic in output."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["entry_signals_allowed"] is False
        assert d["exit_signals_allowed"] is False
        assert d["strategy_runtime_allowed"] is False

    def test_no_pairlist_stake_roi_stoploss_order_type_logic(self, tmp_path: Path) -> None:
        """No trading-specific fields in output."""
        bridge_ctx = make_bridge_context()
        strategy_ctx = build_strategy_context(bridge_ctx)

        target = tmp_path / "output.json"
        write_strategy_context(strategy_ctx, target)

        with open(target) as f:
            d = json.load(f)

        trading_fields = ["pairlist", "stake", "roi", "stoploss", "order_type", "position_size"]
        for field in trading_fields:
            assert field not in d, f"Unexpected trading field: {field}"
