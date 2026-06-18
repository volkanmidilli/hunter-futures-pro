"""Integration tests for Strategy Adapter end-to-end flow.

Tests the full pipeline: StrategyContext -> build_adapter_decision_context() -> write_adapter_decision_context()
No network, no trading logic, no JSON input reading, no Freqtrade runtime.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter.strategy_adapter.engine import build_adapter_decision_context
from hunter.strategy_adapter.models import (
    CALCULATION_ERROR,
    DEFAULT_BLOCK_SIGNAL,
    DRY_RUN_DISABLED,
    INVALID_STRATEGY_CONTEXT,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_SIGNAL_ALLOWED,
    MISSING_STRATEGY_CONTEXT,
    REAL_ORDERS_ENABLED,
    SHORTING_ENABLED,
    SHORT_RESEARCH_SIGNAL_ALLOWED,
    STALE_STRATEGY_CONTEXT,
    STRATEGY_CONTRACT_MODE_BLOCK_ALL,
    STRATEGY_CONTRACT_NOT_DRY_RUN_READY,
    UNSUPPORTED_STRATEGY_MODE,
    AdapterConfig,
    AdapterDecisionContext,
    AdapterMode,
    AdapterSignalIntent,
    AdapterState,
)
from hunter.strategy_adapter.writer import (
    DEFAULT_ADAPTER_DECISION_PATH,
    adapter_decision_context_to_dict,
    write_adapter_decision_context,
)
from hunter.strategy_contract.models import (
    StrategyContractMode,
    StrategyContractState,
    StrategyContext,
    StrategyContractInputRefs,
    StrategyContractSafetyFlags,
    StrategyContractDataQuality,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_strategy_context(**kwargs: Any) -> StrategyContext:
    """Build a real StrategyContext with safe overrides."""
    ts = kwargs.pop("timestamp", datetime.now(timezone.utc))
    return StrategyContext(
        timestamp=ts,
        status=kwargs.pop("status", "DRY_RUN_READY"),
        contract_state=kwargs.pop("contract_state", StrategyContractState.DRY_RUN_READY),
        contract_mode=kwargs.pop("contract_mode", StrategyContractMode.LONG_RESEARCH_ONLY),
        bridge_state=kwargs.pop("bridge_state", "DRY_RUN_READY"),
        bridge_mode=kwargs.pop("bridge_mode", "LONG_RESEARCH_ONLY"),
        dry_run=kwargs.pop("dry_run", True),
        live_trading_enabled=kwargs.pop("live_trading_enabled", False),
        real_orders_enabled=kwargs.pop("real_orders_enabled", False),
        leverage_enabled=kwargs.pop("leverage_enabled", False),
        shorting_enabled=kwargs.pop("shorting_enabled", False),
        reason_codes=kwargs.pop("reason_codes", ("dry_run_long_research_only",)),
        input_refs=kwargs.pop("input_refs", StrategyContractInputRefs()),
        safety_flags=kwargs.pop("safety_flags", StrategyContractSafetyFlags()),
        data_quality=kwargs.pop("data_quality", StrategyContractDataQuality(
            bridge_context_present=True,
            bridge_context_valid=True,
            bridge_context_stale=False,
            reason="VALID",
        )),
    )


class _ValidStrategyContext:
    """Minimal mock that satisfies _REQUIRED_STRATEGY_ATTRS."""

    def __init__(self, **kwargs: Any) -> None:
        defaults = dict(
            timestamp=datetime.now(timezone.utc),
            status="DRY_RUN_READY",
            contract_state=StrategyContractState.DRY_RUN_READY,
            contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# End-to-end allowed signal flow tests
# ---------------------------------------------------------------------------

class TestEndToEndAllowedSignalFlows:
    """End-to-end tests for allowed signal flows."""

    def test_long_research_signal_full_pipeline(self, tmp_path: Path) -> None:
        """DRY_RUN_READY + LONG_RESEARCH_ONLY -> ALLOW_LONG_RESEARCH_SIGNAL -> JSON."""
        strategy_ctx = _make_strategy_context(
            contract_state=StrategyContractState.DRY_RUN_READY,
            contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
        )
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.DRY_RUN_READY
        assert adapter_ctx.adapter_mode == AdapterMode.LONG_RESEARCH_ONLY
        assert adapter_ctx.signal_intent == AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL
        assert adapter_ctx.status == "DRY_RUN_READY"
        assert adapter_ctx.is_blocking() is False

        target = tmp_path / "adapter_decision.json"
        write_adapter_decision_context(adapter_ctx, target)

        assert target.exists()
        with open(target) as f:
            d = json.load(f)

        assert d["adapter_state"] == "DRY_RUN_READY"
        assert d["adapter_mode"] == "LONG_RESEARCH_ONLY"
        assert d["signal_intent"] == "ALLOW_LONG_RESEARCH_SIGNAL"
        assert d["strategy_contract_state"] == "DRY_RUN_READY"
        assert d["strategy_contract_mode"] == "LONG_RESEARCH_ONLY"
        assert d["reason_codes"] == [LONG_RESEARCH_SIGNAL_ALLOWED]
        assert d["version"] == "1.0"
        assert d["dry_run"] is True

    def test_short_research_signal_full_pipeline(self, tmp_path: Path) -> None:
        """DRY_RUN_READY + SHORT_RESEARCH_ONLY -> ALLOW_SHORT_RESEARCH_SIGNAL -> JSON."""
        strategy_ctx = _make_strategy_context(
            contract_state=StrategyContractState.DRY_RUN_READY,
            contract_mode=StrategyContractMode.SHORT_RESEARCH_ONLY,
        )
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.DRY_RUN_READY
        assert adapter_ctx.adapter_mode == AdapterMode.SHORT_RESEARCH_ONLY
        assert adapter_ctx.signal_intent == AdapterSignalIntent.ALLOW_SHORT_RESEARCH_SIGNAL
        assert adapter_ctx.is_blocking() is False

        target = tmp_path / "adapter_decision.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["adapter_state"] == "DRY_RUN_READY"
        assert d["adapter_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["signal_intent"] == "ALLOW_SHORT_RESEARCH_SIGNAL"
        assert d["strategy_contract_state"] == "DRY_RUN_READY"
        assert d["strategy_contract_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["reason_codes"] == [SHORT_RESEARCH_SIGNAL_ALLOWED]

    def test_allowed_adapter_decision_can_be_serialized_and_written(self, tmp_path: Path) -> None:
        """Verify allowed adapter decision can be serialized to dict and written to JSON."""
        strategy_ctx = _make_strategy_context(
            contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
        )
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        # Serialize to dict
        data = adapter_decision_context_to_dict(adapter_ctx)
        assert isinstance(data, dict)
        assert data["adapter_state"] == "DRY_RUN_READY"
        assert data["adapter_mode"] == "LONG_RESEARCH_ONLY"
        assert data["signal_intent"] == "ALLOW_LONG_RESEARCH_SIGNAL"

        # Write and verify
        target = tmp_path / "adapter_decision.json"
        write_adapter_decision_context(adapter_ctx, target)
        assert target.exists()

        with open(target) as f:
            d = json.load(f)
        assert d["adapter_state"] == "DRY_RUN_READY"
        assert d["reason_codes"] == [LONG_RESEARCH_SIGNAL_ALLOWED]

    def test_written_json_can_be_loaded_and_contains_expected_values(self, tmp_path: Path) -> None:
        """Verify written JSON can be loaded and contains expected values."""
        strategy_ctx = _make_strategy_context(
            contract_mode=StrategyContractMode.SHORT_RESEARCH_ONLY,
        )
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "adapter_decision.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["timestamp"].endswith("Z")
        assert d["status"] == "DRY_RUN_READY"
        assert d["adapter_state"] == "DRY_RUN_READY"
        assert d["adapter_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["signal_intent"] == "ALLOW_SHORT_RESEARCH_SIGNAL"
        assert d["strategy_contract_state"] == "DRY_RUN_READY"
        assert d["strategy_contract_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["real_orders_enabled"] is False
        assert d["leverage_enabled"] is False
        assert d["shorting_enabled"] is False
        assert d["adapter_runtime_allowed"] is False
        assert d["freqtrade_runtime_allowed"] is False
        assert d["strategy_class_allowed"] is False
        assert d["entry_signal_allowed"] is False
        assert d["exit_signal_allowed"] is False
        assert d["order_execution_allowed"] is False
        assert d["reason_codes"] == [SHORT_RESEARCH_SIGNAL_ALLOWED]
        assert isinstance(d["input_refs"], dict)
        assert isinstance(d["safety_flags"], dict)
        assert isinstance(d["data_quality"], dict)
        assert d["version"] == "1.0"


# ---------------------------------------------------------------------------
# End-to-end blocked signal flow tests
# ---------------------------------------------------------------------------

class TestEndToEndBlockedSignalFlows:
    """End-to-end tests for blocked signal flows."""

    def test_missing_strategy_context(self, tmp_path: Path) -> None:
        """Missing StrategyContext produces BLOCKED + BLOCK_ALL + BLOCK_SIGNAL."""
        adapter_ctx = build_adapter_decision_context(None)

        assert adapter_ctx.adapter_state == AdapterState.BLOCKED
        assert adapter_ctx.adapter_mode == AdapterMode.BLOCK_ALL
        assert adapter_ctx.signal_intent == AdapterSignalIntent.BLOCK_SIGNAL
        assert adapter_ctx.is_blocking() is True
        assert adapter_ctx.reason_codes == (MISSING_STRATEGY_CONTEXT,)

        target = tmp_path / "adapter_decision.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["adapter_state"] == "BLOCKED"
        assert d["adapter_mode"] == "BLOCK_ALL"
        assert d["signal_intent"] == "BLOCK_SIGNAL"
        assert d["reason_codes"] == [MISSING_STRATEGY_CONTEXT]

    def test_strategy_contract_state_blocked(self, tmp_path: Path) -> None:
        """Strategy contract state BLOCKED produces BLOCKED + BLOCK_ALL + BLOCK_SIGNAL."""
        strategy_ctx = _make_strategy_context(contract_state=StrategyContractState.BLOCKED)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.BLOCKED
        assert adapter_ctx.reason_codes == (STRATEGY_CONTRACT_NOT_DRY_RUN_READY,)

        target = tmp_path / "adapter_decision.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["adapter_state"] == "BLOCKED"
        assert d["reason_codes"] == [STRATEGY_CONTRACT_NOT_DRY_RUN_READY]

    def test_strategy_contract_state_unknown(self, tmp_path: Path) -> None:
        """Strategy contract state UNKNOWN produces BLOCKED + BLOCK_ALL + BLOCK_SIGNAL."""
        strategy_ctx = _make_strategy_context(contract_state=StrategyContractState.UNKNOWN)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.BLOCKED
        assert adapter_ctx.reason_codes == (STRATEGY_CONTRACT_NOT_DRY_RUN_READY,)

    def test_strategy_contract_state_disabled(self, tmp_path: Path) -> None:
        """Strategy contract state DISABLED produces BLOCKED + BLOCK_ALL + BLOCK_SIGNAL."""
        strategy_ctx = _make_strategy_context(contract_state=StrategyContractState.DISABLED)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.BLOCKED
        assert adapter_ctx.reason_codes == (STRATEGY_CONTRACT_NOT_DRY_RUN_READY,)

    def test_strategy_contract_mode_block_all(self, tmp_path: Path) -> None:
        """Strategy contract mode BLOCK_ALL produces BLOCKED + BLOCK_ALL + BLOCK_SIGNAL."""
        strategy_ctx = _make_strategy_context(contract_mode=StrategyContractMode.BLOCK_ALL)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.BLOCKED
        assert adapter_ctx.reason_codes == (STRATEGY_CONTRACT_MODE_BLOCK_ALL,)

    def test_stale_strategy_context(self, tmp_path: Path) -> None:
        """Stale StrategyContext produces BLOCKED + BLOCK_ALL + BLOCK_SIGNAL."""
        old_timestamp = datetime.now(timezone.utc) - timedelta(seconds=400)
        strategy_ctx = _make_strategy_context(timestamp=old_timestamp)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.BLOCKED
        assert adapter_ctx.reason_codes == (STALE_STRATEGY_CONTEXT,)

    def test_dry_run_false(self, tmp_path: Path) -> None:
        """dry_run=False produces BLOCKED + BLOCK_ALL + BLOCK_SIGNAL."""
        strategy_ctx = _ValidStrategyContext(dry_run=False)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.BLOCKED
        assert adapter_ctx.reason_codes == (DRY_RUN_DISABLED,)

    def test_live_trading_enabled_true(self, tmp_path: Path) -> None:
        """live_trading_enabled=True produces BLOCKED + BLOCK_ALL + BLOCK_SIGNAL."""
        strategy_ctx = _ValidStrategyContext(live_trading_enabled=True)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.BLOCKED
        assert adapter_ctx.reason_codes == (LIVE_TRADING_ENABLED,)

    def test_real_orders_enabled_true(self, tmp_path: Path) -> None:
        """real_orders_enabled=True produces BLOCKED + BLOCK_ALL + BLOCK_SIGNAL."""
        strategy_ctx = _ValidStrategyContext(real_orders_enabled=True)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.BLOCKED
        assert adapter_ctx.reason_codes == (REAL_ORDERS_ENABLED,)

    def test_leverage_enabled_true(self, tmp_path: Path) -> None:
        """leverage_enabled=True produces BLOCKED + BLOCK_ALL + BLOCK_SIGNAL."""
        strategy_ctx = _ValidStrategyContext(leverage_enabled=True)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.BLOCKED
        assert adapter_ctx.reason_codes == (LEVERAGE_ENABLED,)

    def test_shorting_enabled_true(self, tmp_path: Path) -> None:
        """shorting_enabled=True produces BLOCKED + BLOCK_ALL + BLOCK_SIGNAL."""
        strategy_ctx = _ValidStrategyContext(shorting_enabled=True)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.adapter_state == AdapterState.BLOCKED
        assert adapter_ctx.reason_codes == (SHORTING_ENABLED,)


# ---------------------------------------------------------------------------
# JSON output verification tests
# ---------------------------------------------------------------------------

class TestJsonOutputVerification:
    """Verify JSON output structure and content."""

    def test_timestamp_is_iso8601_with_z(self, tmp_path: Path) -> None:
        """timestamp is ISO-8601 UTC ending with Z."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        ts = d["timestamp"]
        assert ts.endswith("Z"), f"Expected Z suffix, got: {ts}"
        assert "T" in ts, f"Expected T in timestamp, got: {ts}"

    def test_adapter_state_mode_signal_intent_are_strings(self, tmp_path: Path) -> None:
        """adapter_state, adapter_mode, and signal_intent are strings."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert isinstance(d["adapter_state"], str)
        assert isinstance(d["adapter_mode"], str)
        assert isinstance(d["signal_intent"], str)
        assert d["adapter_state"] == "DRY_RUN_READY"
        assert d["adapter_mode"] == "LONG_RESEARCH_ONLY"
        assert d["signal_intent"] == "ALLOW_LONG_RESEARCH_SIGNAL"

    def test_strategy_contract_state_and_mode_preserved_as_strings(self, tmp_path: Path) -> None:
        """strategy_contract_state and strategy_contract_mode are preserved as strings."""
        strategy_ctx = _make_strategy_context(
            contract_state=StrategyContractState.DRY_RUN_READY,
            contract_mode=StrategyContractMode.SHORT_RESEARCH_ONLY,
        )
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["strategy_contract_state"] == "DRY_RUN_READY"
        assert d["strategy_contract_mode"] == "SHORT_RESEARCH_ONLY"

    def test_reason_codes_is_list(self, tmp_path: Path) -> None:
        """reason_codes is a list."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert isinstance(d["reason_codes"], list)
        assert d["reason_codes"] == [LONG_RESEARCH_SIGNAL_ALLOWED]

    def test_input_refs_is_dict(self, tmp_path: Path) -> None:
        """input_refs is a dict."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert isinstance(d["input_refs"], dict)
        assert "strategy_context" in d["input_refs"]
        assert "adapter_decision" in d["input_refs"]

    def test_safety_flags_is_dict(self, tmp_path: Path) -> None:
        """safety_flags is a dict."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert isinstance(d["safety_flags"], dict)
        assert d["safety_flags"]["dry_run"] is True
        assert d["safety_flags"]["live_trading_enabled"] is False

    def test_data_quality_is_dict(self, tmp_path: Path) -> None:
        """data_quality is a dict."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert isinstance(d["data_quality"], dict)

    def test_version_is_1_0(self, tmp_path: Path) -> None:
        """version is "1.0"."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["version"] == "1.0"

    def test_blocked_outputs_contain_blocking_reason_codes(self, tmp_path: Path) -> None:
        """Blocked outputs contain blocking reason codes."""
        strategy_ctx = _make_strategy_context(contract_mode=StrategyContractMode.BLOCK_ALL)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["adapter_state"] == "BLOCKED"
        assert d["reason_codes"] == [STRATEGY_CONTRACT_MODE_BLOCK_ALL]
        assert d["reason_codes"] != [LONG_RESEARCH_SIGNAL_ALLOWED]

    def test_allowed_outputs_contain_long_research_signal_allowed(self, tmp_path: Path) -> None:
        """Allowed long outputs contain LONG_RESEARCH_SIGNAL_ALLOWED."""
        strategy_ctx = _make_strategy_context(contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == [LONG_RESEARCH_SIGNAL_ALLOWED]

    def test_allowed_outputs_contain_short_research_signal_allowed(self, tmp_path: Path) -> None:
        """Allowed short outputs contain SHORT_RESEARCH_SIGNAL_ALLOWED."""
        strategy_ctx = _make_strategy_context(contract_mode=StrategyContractMode.SHORT_RESEARCH_ONLY)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["reason_codes"] == [SHORT_RESEARCH_SIGNAL_ALLOWED]


# ---------------------------------------------------------------------------
# Atomic write and path tests
# ---------------------------------------------------------------------------

class TestAtomicWriteAndPaths:
    """Verify atomic write behavior and path handling."""

    def test_write_to_custom_tmp_path(self, tmp_path: Path) -> None:
        """write_adapter_decision_context writes to custom tmp_path target."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "adapter_decision.json"
        result = write_adapter_decision_context(adapter_ctx, target)

        assert result == target
        assert target.exists()

    def test_nested_parent_directory_creation(self, tmp_path: Path) -> None:
        """Writer creates nested parent directories."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "a" / "b" / "c" / "adapter_decision.json"
        write_adapter_decision_context(adapter_ctx, target)

        assert target.exists()

    def test_overwrite_existing_file(self, tmp_path: Path) -> None:
        """Writer overwrites existing file safely."""
        strategy_ctx = _make_strategy_context(contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY)
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        # Write different context to same file
        strategy_ctx2 = _make_strategy_context(contract_mode=StrategyContractMode.SHORT_RESEARCH_ONLY)
        adapter_ctx2 = build_adapter_decision_context(strategy_ctx2)
        write_adapter_decision_context(adapter_ctx2, target)

        with open(target) as f:
            d = json.load(f)

        assert d["adapter_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["signal_intent"] == "ALLOW_SHORT_RESEARCH_SIGNAL"

    def test_no_temp_files_left_after_successful_write(self, tmp_path: Path) -> None:
        """Writer leaves no temp files after successful write."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "nested" / "dir" / "adapter_decision.json"
        write_adapter_decision_context(adapter_ctx, target)

        assert target.exists()
        temp_files = list(tmp_path.rglob("*.tmp"))
        assert len(temp_files) == 0

    def test_default_output_path_constant(self) -> None:
        """Default output path constant equals data/strategy_adapter/current_adapter_decision.json."""
        assert str(DEFAULT_ADAPTER_DECISION_PATH) == "data/strategy_adapter/current_adapter_decision.json"

    def test_no_production_path_usage_in_tests(self, tmp_path: Path) -> None:
        """Do not write to production data path during tests."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        # Always use tmp_path for test outputs
        target = tmp_path / "current_adapter_decision.json"
        write_adapter_decision_context(adapter_ctx, target)

        assert target.exists()
        # Production path should not exist
        prod_path = Path("data/strategy_adapter/current_adapter_decision.json")
        assert not prod_path.exists()


# ---------------------------------------------------------------------------
# Safety absence tests
# ---------------------------------------------------------------------------

class TestSafetyAbsence:
    """Verify no unsafe behavior in integration tests."""

    def test_no_config_yaml(self) -> None:
        """No config YAML file exists."""
        config_path = Path("configs/strategy_adapter.yaml")
        assert not config_path.exists()

    def test_no_json_schema(self) -> None:
        """No JSON schema file exists."""
        schema_path = Path("schemas/strategy_adapter_decision.schema.json")
        assert not schema_path.exists()

    def test_no_deployable_freqtrade_strategy_class(self) -> None:
        """No deployable Freqtrade strategy class file exists."""
        strategy_path = Path("src/hunter/strategy_adapter/freqtrade_strategy.py")
        assert not strategy_path.exists()

    def test_no_freqtrade_runtime_import(self) -> None:
        """No Freqtrade runtime import in engine or writer."""
        import hunter.strategy_adapter.engine as engine_module
        import hunter.strategy_adapter.writer as writer_module

        engine_globals = [name.lower() for name in dir(engine_module)]
        writer_globals = [name.lower() for name in dir(writer_module)]

        freqtrade_keywords = ["freqtradebot", "freqtradeexchange", "freqtradestrategy"]
        for keyword in freqtrade_keywords:
            assert keyword not in engine_globals, f"Unexpected Freqtrade import in engine: {keyword}"
            assert keyword not in writer_globals, f"Unexpected Freqtrade import in writer: {keyword}"

    def test_no_binance_import(self) -> None:
        """No Binance import in engine or writer."""
        import hunter.strategy_adapter.engine as engine_module
        import hunter.strategy_adapter.writer as writer_module

        engine_globals = [name.lower() for name in dir(engine_module)]
        writer_globals = [name.lower() for name in dir(writer_module)]

        assert "binance" not in engine_globals
        assert "binance" not in writer_globals

    def test_no_network_calls(self, tmp_path: Path) -> None:
        """Writer should not make any network calls."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)
        target = tmp_path / "output.json"

        write_adapter_decision_context(adapter_ctx, target)
        assert target.exists()

    def test_no_api_keys(self) -> None:
        """No API keys in code or output."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)
        data = adapter_decision_context_to_dict(adapter_ctx)

        json_str = json.dumps(data)
        assert "api_key" not in json_str.lower()
        assert "secret" not in json_str.lower()
        assert "bearer" not in json_str.lower()

    def test_no_live_trading_enablement(self, tmp_path: Path) -> None:
        """live_trading_enabled must always be False."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.live_trading_enabled is False

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["live_trading_enabled"] is False

    def test_no_real_order_execution(self, tmp_path: Path) -> None:
        """real_orders_enabled must always be False."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.real_orders_enabled is False

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["real_orders_enabled"] is False

    def test_no_leverage_enablement(self, tmp_path: Path) -> None:
        """leverage_enabled must always be False."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.leverage_enabled is False

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["leverage_enabled"] is False

    def test_no_shorting_enablement(self, tmp_path: Path) -> None:
        """shorting_enabled must always be False."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        assert adapter_ctx.shorting_enabled is False

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)
        assert d["shorting_enabled"] is False

    def test_no_entry_exit_execution_logic(self, tmp_path: Path) -> None:
        """No entry/exit execution logic in output."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        assert d["entry_signal_allowed"] is False
        assert d["exit_signal_allowed"] is False
        assert d["order_execution_allowed"] is False
        assert d["adapter_runtime_allowed"] is False
        assert d["freqtrade_runtime_allowed"] is False
        assert d["strategy_class_allowed"] is False

    def test_no_pairlist_stake_roi_stoploss_order_type_logic(self, tmp_path: Path) -> None:
        """No trading-specific fields in output."""
        strategy_ctx = _make_strategy_context()
        adapter_ctx = build_adapter_decision_context(strategy_ctx)

        target = tmp_path / "output.json"
        write_adapter_decision_context(adapter_ctx, target)

        with open(target) as f:
            d = json.load(f)

        trading_fields = ["pairlist", "stake", "roi", "stoploss", "order_type", "position_size"]
        for field in trading_fields:
            assert field not in d, f"Unexpected trading field: {field}"
