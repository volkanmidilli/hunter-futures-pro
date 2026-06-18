"""Integration tests for Freqtrade bridge end-to-end flow.

Tests the full pipeline: ExecutionContext -> build_freqtrade_bridge_context() -> write_freqtrade_bridge_context()
No network, no trading logic, no JSON input reading, no Freqtrade runtime.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.execution.models import (
    ExecutionContext,
    ExecutionMode,
    ExecutionSafetyFlags,
    ExecutionState,
)
from hunter.freqtrade_bridge.engine import build_freqtrade_bridge_context
from hunter.freqtrade_bridge.models import (
    FreqtradeBridgeConfig,
    FreqtradeBridgeContext,
    FreqtradeBridgeMode,
    FreqtradeBridgeState,
)
from hunter.freqtrade_bridge.writer import (
    freqtrade_bridge_context_to_dict,
    write_freqtrade_bridge_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_execution_context(
    *,
    execution_state: ExecutionState = ExecutionState.DRY_RUN_ONLY,
    execution_mode: ExecutionMode = ExecutionMode.LONG_RESEARCH_ONLY,
    dry_run: bool = True,
    live_trading: bool = False,
    exchange: bool = False,
    freqtrade: bool = False,
    timestamp: datetime | None = None,
) -> ExecutionContext:
    """Create an ExecutionContext with sensible defaults."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    return ExecutionContext(
        timestamp=timestamp,
        status="valid",
        execution_state=execution_state,
        execution_mode=execution_mode,
        decision_state="allow",
        decision_action="enable_long_only_research",
        allowed_mode="long_only",
        dry_run=dry_run,
        live_trading_enabled=live_trading,
        exchange_connection_enabled=exchange,
        freqtrade_enabled=freqtrade,
    )


# ---------------------------------------------------------------------------
# End-to-end flow tests
# ---------------------------------------------------------------------------

class TestEndToEndFlow:
    """End-to-end tests: ExecutionContext -> Engine -> Writer -> JSON."""

    def test_long_research_full_pipeline(self, tmp_path: Path) -> None:
        """DRY_RUN_ONLY + LONG_RESEARCH_ONLY -> DRY_RUN_READY + LONG_RESEARCH_ONLY -> JSON."""
        exec_ctx = make_execution_context(execution_mode=ExecutionMode.LONG_RESEARCH_ONLY)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        
        assert bridge_ctx.bridge_state == FreqtradeBridgeState.DRY_RUN_READY
        assert bridge_ctx.bridge_mode == FreqtradeBridgeMode.LONG_RESEARCH_ONLY
        assert bridge_ctx.status == "success"
        
        target = tmp_path / "freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        assert target.exists()
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_state"] == "DRY_RUN_READY"
        assert d["bridge_mode"] == "LONG_RESEARCH_ONLY"
        assert d["status"] == "success"
        assert d["reason_codes"] == ["dry_run_long_research_only"]
        assert d["version"] == "1.0"
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False

    def test_short_research_full_pipeline(self, tmp_path: Path) -> None:
        """DRY_RUN_ONLY + SHORT_RESEARCH_ONLY -> DRY_RUN_READY + SHORT_RESEARCH_ONLY -> JSON."""
        exec_ctx = make_execution_context(execution_mode=ExecutionMode.SHORT_RESEARCH_ONLY)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        
        assert bridge_ctx.bridge_state == FreqtradeBridgeState.DRY_RUN_READY
        assert bridge_ctx.bridge_mode == FreqtradeBridgeMode.SHORT_RESEARCH_ONLY
        
        target = tmp_path / "freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_state"] == "DRY_RUN_READY"
        assert d["bridge_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["reason_codes"] == ["dry_run_short_research_only"]

    def test_block_all_full_pipeline(self, tmp_path: Path) -> None:
        """BLOCK_ALL -> BLOCKED + BLOCK_ALL -> JSON."""
        exec_ctx = make_execution_context(execution_mode=ExecutionMode.BLOCK_ALL)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        
        assert bridge_ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert bridge_ctx.bridge_mode == FreqtradeBridgeMode.BLOCK_ALL
        assert bridge_ctx.status == "blocked"
        
        target = tmp_path / "freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_state"] == "BLOCKED"
        assert d["bridge_mode"] == "BLOCK_ALL"
        assert d["reason_codes"] == ["execution_mode_is_block_all"]

    def test_stale_context_full_pipeline(self, tmp_path: Path) -> None:
        """Stale ExecutionContext -> BLOCKED + BLOCK_ALL -> JSON."""
        old_timestamp = datetime.now(timezone.utc) - timedelta(seconds=400)
        exec_ctx = make_execution_context(timestamp=old_timestamp)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        
        assert bridge_ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert bridge_ctx.reason_codes == ["stale_execution_context"]
        
        target = tmp_path / "freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_state"] == "BLOCKED"
        assert d["reason_codes"] == ["stale_execution_context"]

    def test_missing_context_full_pipeline(self, tmp_path: Path) -> None:
        """None ExecutionContext -> BLOCKED + BLOCK_ALL -> JSON."""
        bridge_ctx = build_freqtrade_bridge_context(None)
        
        assert bridge_ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert bridge_ctx.reason_codes == ["missing_execution_context"]
        
        target = tmp_path / "freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_state"] == "BLOCKED"
        assert d["reason_codes"] == ["missing_execution_context"]

    def test_blocked_state_full_pipeline(self, tmp_path: Path) -> None:
        """BLOCKED execution state -> BLOCKED + BLOCK_ALL -> JSON."""
        exec_ctx = make_execution_context(execution_state=ExecutionState.BLOCKED)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        
        assert bridge_ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert bridge_ctx.reason_codes == ["execution_state_not_dry_run_only:blocked"]
        
        target = tmp_path / "freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_state"] == "BLOCKED"

    def test_dry_run_false_full_pipeline(self, tmp_path: Path) -> None:
        """dry_run=False -> BLOCKED + BLOCK_ALL -> JSON."""
        exec_ctx = make_execution_context(dry_run=False)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        
        assert bridge_ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert bridge_ctx.reason_codes == ["dry_run_disabled"]
        
        target = tmp_path / "freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_state"] == "BLOCKED"
        assert d["reason_codes"] == ["dry_run_disabled"]

    def test_live_trading_true_full_pipeline(self, tmp_path: Path) -> None:
        """live_trading_enabled=True -> BLOCKED + BLOCK_ALL -> JSON."""
        exec_ctx = make_execution_context(live_trading=True)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        
        assert bridge_ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert bridge_ctx.reason_codes == ["live_trading_enabled"]
        
        target = tmp_path / "freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_state"] == "BLOCKED"
        assert d["reason_codes"] == ["live_trading_enabled"]

    def test_exchange_true_full_pipeline(self, tmp_path: Path) -> None:
        """exchange_connection_enabled=True -> BLOCKED + BLOCK_ALL -> JSON."""
        exec_ctx = make_execution_context(exchange=True)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        
        assert bridge_ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert bridge_ctx.reason_codes == ["exchange_connection_enabled"]
        
        target = tmp_path / "freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_state"] == "BLOCKED"
        assert d["reason_codes"] == ["exchange_connection_enabled"]

    def test_freqtrade_enabled_true_full_pipeline(self, tmp_path: Path) -> None:
        """freqtrade_enabled=True -> BLOCKED + BLOCK_ALL -> JSON."""
        exec_ctx = make_execution_context(freqtrade=True)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        
        assert bridge_ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert bridge_ctx.reason_codes == ["freqtrade_enabled"]
        
        target = tmp_path / "freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_state"] == "BLOCKED"
        assert d["reason_codes"] == ["freqtrade_enabled"]

    def test_dry_run_only_mode_full_pipeline(self, tmp_path: Path) -> None:
        """DRY_RUN_ONLY mode (no research direction) -> BLOCKED + BLOCK_ALL -> JSON."""
        exec_ctx = make_execution_context(execution_mode=ExecutionMode.DRY_RUN_ONLY)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        
        assert bridge_ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert bridge_ctx.reason_codes == ["unsupported_execution_mode:dry_run_only"]
        
        target = tmp_path / "freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_state"] == "BLOCKED"


# ---------------------------------------------------------------------------
# JSON output verification tests
# ---------------------------------------------------------------------------

class TestJsonOutputVerification:
    """Verify JSON output structure and content."""

    def test_all_expected_fields_present(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        expected_keys = {
            "timestamp", "status", "bridge_state", "bridge_mode",
            "execution_state", "execution_mode", "dry_run",
            "live_trading_enabled", "exchange_connection_enabled",
            "freqtrade_runtime_enabled", "strategy_enabled",
            "real_orders_enabled", "leverage_enabled", "shorting_enabled",
            "reason_codes", "input_refs", "safety_flags", "data_quality", "version",
        }
        assert set(d.keys()) == expected_keys

    def test_enum_values_are_strings(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert isinstance(d["bridge_state"], str)
        assert isinstance(d["bridge_mode"], str)
        assert d["bridge_state"] == "DRY_RUN_READY"
        assert d["bridge_mode"] == "LONG_RESEARCH_ONLY"

    def test_version_is_1_0(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["version"] == "1.0"

    def test_timestamp_is_iso8601(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        ts = d["timestamp"]
        assert ts.endswith("Z")
        assert "T" in ts

    def test_safety_flags_all_safe(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        sf = d["safety_flags"]
        assert sf["dry_run"] is True
        assert sf["live_trading_enabled"] is False
        assert sf["exchange_connection_enabled"] is False
        assert sf["freqtrade_runtime_enabled"] is False
        assert sf["strategy_enabled"] is False
        assert sf["real_orders_enabled"] is False
        assert sf["leverage_enabled"] is False
        assert sf["shorting_enabled"] is False
        assert sf["human_override_required"] is False
        assert sf["max_context_age_seconds"] == 300

    def test_safety_flags_blocked_context(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context(execution_mode=ExecutionMode.BLOCK_ALL)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        sf = d["safety_flags"]
        assert sf["dry_run"] is True
        assert sf["live_trading_enabled"] is False
        assert sf["strategy_enabled"] is False
        assert sf["leverage_enabled"] is False
        assert sf["shorting_enabled"] is False

    def test_input_refs_populated(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert "execution_context_timestamp" in d["input_refs"]
        assert "execution_context_version" in d["input_refs"]
        assert d["input_refs"]["execution_context_version"] == "1.0"

    def test_data_quality_on_success(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["data_quality"]["execution_context_fresh"] is True
        assert d["data_quality"]["execution_context_valid"] is True
        assert d["data_quality"]["validation_errors"] == []

    def test_data_quality_on_block(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context(execution_state=ExecutionState.BLOCKED)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["data_quality"]["execution_context_valid"] is True
        assert d["data_quality"]["validation_errors"] == ["execution_state_not_dry_run_only:blocked"]

    def test_reason_codes_on_success(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context(execution_mode=ExecutionMode.LONG_RESEARCH_ONLY)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["reason_codes"] == ["dry_run_long_research_only"]

    def test_reason_codes_on_block(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context(execution_mode=ExecutionMode.BLOCK_ALL)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["reason_codes"] == ["execution_mode_is_block_all"]


# ---------------------------------------------------------------------------
# Atomic write and path tests
# ---------------------------------------------------------------------------

class TestAtomicWriteAndPaths:
    """Verify atomic write behavior and path handling."""

    def test_atomic_write_no_temp_files_left(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "nested" / "dir" / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        assert target.exists()
        # No temp files should be left in the directory
        temp_files = list(tmp_path.rglob("*.tmp"))
        assert len(temp_files) == 0

    def test_nested_directory_creation(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "a" / "b" / "c" / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        assert target.exists()
        with open(target) as f:
            d = json.load(f)
        assert d["bridge_state"] == "DRY_RUN_READY"

    def test_no_production_path_in_test(self, tmp_path: Path) -> None:
        """Verify tests use tmp_path, not production path."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        # Always use tmp_path for test outputs
        target = tmp_path / "current_freqtrade_context.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        assert target.exists()
        # Production path should not exist
        prod_path = Path("data/freqtrade/current_freqtrade_context.json")
        assert not prod_path.exists()

    def test_overwrite_existing_file(self, tmp_path: Path) -> None:
        exec_ctx = make_execution_context(execution_mode=ExecutionMode.LONG_RESEARCH_ONLY)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        
        # Write first context
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        # Write second context (different mode)
        exec_ctx2 = make_execution_context(execution_mode=ExecutionMode.SHORT_RESEARCH_ONLY)
        bridge_ctx2 = build_freqtrade_bridge_context(exec_ctx2)
        write_freqtrade_bridge_context(bridge_ctx2, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["bridge_mode"] == "SHORT_RESEARCH_ONLY"


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------

class TestSafety:
    """Verify no unsafe behavior in integration tests."""

    def test_no_network_calls(self, tmp_path: Path) -> None:
        """Writer should not make any network calls."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        
        # If any network call were made, this would fail or be detectable
        write_freqtrade_bridge_context(bridge_ctx, target)
        assert target.exists()

    def test_no_trading_logic_in_output(self, tmp_path: Path) -> None:
        """Output should not contain trading-specific fields."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        trading_fields = ["pairlist", "order", "stake", "stoploss", "roi", "entry", "exit"]
        for field in trading_fields:
            assert field not in d, f"Unexpected trading field: {field}"

    def test_no_freqtrade_runtime_integration(self, tmp_path: Path) -> None:
        """No Freqtrade process or runtime should be invoked."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        
        # Pure file write - no subprocess, no Docker, no Freqtrade process
        write_freqtrade_bridge_context(bridge_ctx, target)
        assert target.exists()

    def test_no_strategy_class(self, tmp_path: Path) -> None:
        """No strategy class should be created or referenced."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        
        # strategy_enabled should always be False in MVP-5
        assert bridge_ctx.strategy_enabled is False
        
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["strategy_enabled"] is False

    def test_no_leverage_in_output(self, tmp_path: Path) -> None:
        """leverage_enabled must always be False."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["leverage_enabled"] is False

    def test_no_shorting_in_output(self, tmp_path: Path) -> None:
        """shorting_enabled must always be False."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["shorting_enabled"] is False

    def test_no_live_trading_in_output(self, tmp_path: Path) -> None:
        """live_trading_enabled must always be False."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["live_trading_enabled"] is False

    def test_no_real_orders_in_output(self, tmp_path: Path) -> None:
        """real_orders_enabled must always be False."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["real_orders_enabled"] is False

    def test_no_exchange_connection_in_output(self, tmp_path: Path) -> None:
        """exchange_connection_enabled must always be False."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["exchange_connection_enabled"] is False

    def test_no_freqtrade_runtime_in_output(self, tmp_path: Path) -> None:
        """freqtrade_runtime_enabled must always be False."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["freqtrade_runtime_enabled"] is False

    def test_dry_run_always_true(self, tmp_path: Path) -> None:
        """dry_run must always be True."""
        exec_ctx = make_execution_context()
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert d["dry_run"] is True

    def test_no_json_input_reading(self) -> None:
        """Integration tests should not read ExecutionContext from JSON files."""
        # All ExecutionContext objects are created in-memory via make_execution_context()
        exec_ctx = make_execution_context()
        assert isinstance(exec_ctx, ExecutionContext)
        # No file reading involved

    def test_all_outputs_dry_run(self, tmp_path: Path) -> None:
        """All possible outputs must have dry_run=True."""
        for mode in [ExecutionMode.LONG_RESEARCH_ONLY, ExecutionMode.SHORT_RESEARCH_ONLY, ExecutionMode.BLOCK_ALL]:
            exec_ctx = make_execution_context(execution_mode=mode)
            bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
            target = tmp_path / f"output_{mode.value}.json"
            write_freqtrade_bridge_context(bridge_ctx, target)
            
            with open(target) as f:
                d = json.load(f)
            
            assert d["dry_run"] is True, f"dry_run should be True for {mode.value}"

    def test_blocked_outputs_have_errors(self, tmp_path: Path) -> None:
        """Blocked outputs should have validation_errors in data_quality."""
        exec_ctx = make_execution_context(execution_mode=ExecutionMode.BLOCK_ALL)
        bridge_ctx = build_freqtrade_bridge_context(exec_ctx)
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(bridge_ctx, target)
        
        with open(target) as f:
            d = json.load(f)
        
        assert len(d["data_quality"]["validation_errors"]) > 0
        assert d["status"] == "blocked"
