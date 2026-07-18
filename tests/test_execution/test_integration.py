"""Integration tests for execution bridge end-to-end flow.

Tests the full pipeline: DecisionOutput -> build_execution_context() -> write_execution_context()
No network, no trading logic, no JSON input reading, no Freqtrade runtime.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.decision.models import DecisionAction, DecisionOutput, DecisionState
from hunter.execution.engine import build_execution_context
from hunter.execution.models import (
    ExecutionBridgeConfig,
    ExecutionContext,
    ExecutionInputRefs,
    ExecutionMode,
    ExecutionSafetyFlags,
    ExecutionState,
)
from hunter.execution.writer import execution_context_to_dict, write_execution_context
from hunter.market_state.models import AllowedMode, DataQuality, OutputStatus, RegimeState, RiskState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_decision_output(
    *,
    decision_state: DecisionState = DecisionState.ALLOW,
    decision_action: DecisionAction = DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
    allowed_mode: AllowedMode = AllowedMode.LONG_ONLY,
    status: OutputStatus = OutputStatus.VALID,
    timestamp: datetime | None = None,
    data_quality: DataQuality | None = None,
) -> DecisionOutput:
    """Create a DecisionOutput with sensible defaults."""
    return DecisionOutput(
        timestamp=timestamp or datetime.now(timezone.utc),
        status=status,
        decision_state=decision_state,
        decision_action=decision_action,
        allowed_mode=allowed_mode,
        market_regime=RegimeState.BULL,
        risk_state=RiskState.RISK_ON,
        confidence=0.85,
        regime_confidence=0.90,
        breadth_score=75,
        market_health=RiskState.RISK_ON,
        data_quality=data_quality or DataQuality(),
    )


# ---------------------------------------------------------------------------
# End-to-end flow tests
# ---------------------------------------------------------------------------

class TestEndToEndFlow:
    def test_long_research_full_pipeline(self, tmp_path: Path) -> None:
        """ENABLE_LONG_ONLY_RESEARCH -> DRY_RUN_ONLY + LONG_RESEARCH_ONLY, JSON written."""
        decision = make_decision_output(
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
        )
        config = ExecutionBridgeConfig()
        
        ctx = build_execution_context(decision, config)
        assert ctx.execution_state == ExecutionState.DRY_RUN_ONLY
        assert ctx.execution_mode == ExecutionMode.LONG_RESEARCH_ONLY
        assert ctx.is_blocking() is False
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.exchange_connection_enabled is False
        assert ctx.freqtrade_enabled is False
        assert ctx.version == "1.0"
        assert "LONG_RESEARCH_ENABLED" in ctx.reason_codes
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["execution_state"] == "DRY_RUN_ONLY"
        assert parsed["execution_mode"] == "LONG_RESEARCH_ONLY"
        assert parsed["decision_state"] == "ALLOW"
        assert parsed["decision_action"] == "ENABLE_LONG_ONLY_RESEARCH"
        assert parsed["allowed_mode"] == "LONG_ONLY"
        assert parsed["dry_run"] is True
        assert parsed["live_trading_enabled"] is False
        assert parsed["exchange_connection_enabled"] is False
        assert parsed["freqtrade_enabled"] is False
        assert parsed["version"] == "1.0"
        assert parsed["reason_codes"] == ["LONG_RESEARCH_ENABLED"]
        assert parsed["input_refs"]["decision_source"] == "decision_engine"
        assert parsed["input_refs"]["decision_timestamp"].endswith("Z")

    def test_short_research_full_pipeline(self, tmp_path: Path) -> None:
        """ENABLE_SHORT_ONLY_RESEARCH -> DRY_RUN_ONLY + SHORT_RESEARCH_ONLY, JSON written."""
        decision = make_decision_output(
            decision_action=DecisionAction.ENABLE_SHORT_ONLY_RESEARCH,
            allowed_mode=AllowedMode.SHORT_ONLY,
        )
        config = ExecutionBridgeConfig()
        
        ctx = build_execution_context(decision, config)
        assert ctx.execution_state == ExecutionState.DRY_RUN_ONLY
        assert ctx.execution_mode == ExecutionMode.SHORT_RESEARCH_ONLY
        assert ctx.is_blocking() is False
        assert ctx.dry_run is True
        assert "SHORT_RESEARCH_ENABLED" in ctx.reason_codes
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["execution_state"] == "DRY_RUN_ONLY"
        assert parsed["execution_mode"] == "SHORT_RESEARCH_ONLY"
        assert parsed["decision_action"] == "ENABLE_SHORT_ONLY_RESEARCH"
        assert parsed["reason_codes"] == ["SHORT_RESEARCH_ENABLED"]

    def test_block_all_full_pipeline(self, tmp_path: Path) -> None:
        """BLOCK_ALL -> BLOCKED + BLOCK_ALL, JSON written."""
        decision = make_decision_output(
            decision_action=DecisionAction.BLOCK_ALL,
            decision_state=DecisionState.ALLOW,
            allowed_mode=AllowedMode.NONE,
        )
        config = ExecutionBridgeConfig()
        
        ctx = build_execution_context(decision, config)
        assert ctx.execution_state == ExecutionState.BLOCKED
        assert ctx.execution_mode == ExecutionMode.BLOCK_ALL
        assert ctx.is_blocking() is True
        assert ctx.dry_run is True
        assert "ACTION_BLOCKED_ALL" in ctx.reason_codes
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["execution_state"] == "BLOCKED"
        assert parsed["execution_mode"] == "BLOCK_ALL"
        assert parsed["status"] == "INVALID"
        assert parsed["decision_state"] == "BLOCK"
        assert parsed["decision_action"] == "BLOCK_ALL"
        assert parsed["allowed_mode"] == "NONE"
        assert "ACTION_BLOCKED_ALL" in parsed["reason_codes"]

    def test_manual_review_full_pipeline(self, tmp_path: Path) -> None:
        """MANUAL_REVIEW -> BLOCKED + BLOCK_ALL, JSON written."""
        decision = make_decision_output(
            decision_action=DecisionAction.MANUAL_REVIEW,
            decision_state=DecisionState.ALLOW,
        )
        config = ExecutionBridgeConfig()
        
        ctx = build_execution_context(decision, config)
        assert ctx.execution_state == ExecutionState.BLOCKED
        assert ctx.execution_mode == ExecutionMode.BLOCK_ALL
        assert ctx.is_blocking() is True
        assert "MANUAL_REVIEW_REQUIRED" in ctx.reason_codes
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["execution_state"] == "BLOCKED"
        assert parsed["execution_mode"] == "BLOCK_ALL"
        assert "MANUAL_REVIEW_REQUIRED" in parsed["reason_codes"]

    def test_stale_decision_blocks_pipeline(self, tmp_path: Path) -> None:
        """Stale decision -> BLOCKED + BLOCK_ALL, JSON written."""
        old = datetime.now(timezone.utc) - timedelta(minutes=200)
        decision = make_decision_output(timestamp=old)
        config = ExecutionBridgeConfig()
        
        ctx = build_execution_context(decision, config)
        assert ctx.execution_state == ExecutionState.BLOCKED
        assert ctx.execution_mode == ExecutionMode.BLOCK_ALL
        assert ctx.is_blocking() is True
        assert "STALE_DECISION" in ctx.reason_codes
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["execution_state"] == "BLOCKED"
        assert parsed["execution_mode"] == "BLOCK_ALL"
        assert "STALE_DECISION" in parsed["reason_codes"]

    def test_missing_decision_blocks_pipeline(self, tmp_path: Path) -> None:
        """None decision -> BLOCKED + BLOCK_ALL, JSON written."""
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(None, config)
        
        assert ctx.execution_state == ExecutionState.BLOCKED
        assert ctx.execution_mode == ExecutionMode.BLOCK_ALL
        assert ctx.is_blocking() is True
        assert "MISSING_DECISION" in ctx.reason_codes
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["execution_state"] == "BLOCKED"
        assert parsed["execution_mode"] == "BLOCK_ALL"
        assert "MISSING_DECISION" in parsed["reason_codes"]

    def test_invalid_decision_blocks_pipeline(self, tmp_path: Path) -> None:
        """INVALID status -> BLOCKED + BLOCK_ALL, JSON written."""
        decision = make_decision_output(status=OutputStatus.INVALID)
        config = ExecutionBridgeConfig()
        
        ctx = build_execution_context(decision, config)
        assert ctx.execution_state == ExecutionState.BLOCKED
        assert ctx.execution_mode == ExecutionMode.BLOCK_ALL
        assert ctx.is_blocking() is True
        assert "INVALID_DECISION" in ctx.reason_codes
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["execution_state"] == "BLOCKED"
        assert parsed["execution_mode"] == "BLOCK_ALL"
        assert "INVALID_DECISION" in parsed["reason_codes"]

    def test_blocked_decision_state_blocks_pipeline(self, tmp_path: Path) -> None:
        """BLOCK decision_state -> BLOCKED + BLOCK_ALL, JSON written."""
        decision = make_decision_output(decision_state=DecisionState.BLOCK)
        config = ExecutionBridgeConfig()
        
        ctx = build_execution_context(decision, config)
        assert ctx.execution_state == ExecutionState.BLOCKED
        assert ctx.execution_mode == ExecutionMode.BLOCK_ALL
        assert ctx.is_blocking() is True
        assert "DECISION_BLOCKED" in ctx.reason_codes
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["execution_state"] == "BLOCKED"
        assert parsed["execution_mode"] == "BLOCK_ALL"
        assert "DECISION_BLOCKED" in parsed["reason_codes"]

    def test_unsafe_config_blocks_or_fails(self, tmp_path: Path) -> None:
        """Unsafe config (dry_run=False) fails at config creation."""
        with pytest.raises(ValueError, match="dry_run_required must be True for MVP-4"):
            ExecutionBridgeConfig(dry_run_required=False)

    def test_unsafe_live_trading_config_fails(self, tmp_path: Path) -> None:
        """Unsafe config (live_trading=True) fails at config creation."""
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-4"):
            ExecutionBridgeConfig(live_trading_enabled=True)

    def test_unsafe_exchange_config_fails(self, tmp_path: Path) -> None:
        """Unsafe config (exchange=True) fails at config creation."""
        with pytest.raises(ValueError, match="exchange_connection_enabled must be False for MVP-4"):
            ExecutionBridgeConfig(exchange_connection_enabled=True)

    def test_unsafe_freqtrade_config_fails(self, tmp_path: Path) -> None:
        """Unsafe config (freqtrade=True) fails at config creation."""
        with pytest.raises(ValueError, match="freqtrade_enabled must be False for MVP-4"):
            ExecutionBridgeConfig(freqtrade_enabled=True)


# ---------------------------------------------------------------------------
# JSON output verification tests
# ---------------------------------------------------------------------------

class TestJsonOutputVerification:
    def test_all_expected_fields_present(self, tmp_path: Path) -> None:
        """Verify serialized JSON contains all expected fields from SPEC-005."""
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        expected_fields = {
            "timestamp",
            "status",
            "execution_state",
            "execution_mode",
            "decision_state",
            "decision_action",
            "allowed_mode",
            "dry_run",
            "live_trading_enabled",
            "exchange_connection_enabled",
            "freqtrade_enabled",
            "reason_codes",
            "input_refs",
            "data_quality",
            "safety_flags",
            "version",
            "_safety_notice",
        }
        assert set(parsed.keys()) == expected_fields
        
        # Verify input_refs sub-fields
        assert set(parsed["input_refs"].keys()) == {
            "decision_timestamp",
            "decision_source",
        }
        
        # Verify data_quality sub-fields
        assert set(parsed["data_quality"].keys()) == {
            "missing",
            "stale",
            "insufficient_history",
            "insufficient_universe",
        }
        
        # Verify safety_flags sub-fields
        assert set(parsed["safety_flags"].keys()) == {
            "dry_run",
            "live_trading_enabled",
            "exchange_connection_enabled",
            "freqtrade_enabled",
            "human_override_required",
            "max_context_age_seconds",
        }

    def test_enum_values_are_strings(self, tmp_path: Path) -> None:
        """Verify all enum values are serialized as strings, not objects."""
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        enum_fields = [
            "status", "execution_state", "execution_mode",
            "decision_state", "decision_action", "allowed_mode",
        ]
        for field in enum_fields:
            assert isinstance(parsed[field], str), f"{field} should be string"

    def test_safety_flags_values(self, tmp_path: Path) -> None:
        """Verify safety_flags contain expected values."""
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        flags = parsed["safety_flags"]
        assert flags["dry_run"] is True
        assert flags["live_trading_enabled"] is False
        assert flags["exchange_connection_enabled"] is False
        assert flags["freqtrade_enabled"] is False
        assert flags["human_override_required"] is False
        assert flags["max_context_age_seconds"] == 300

    def test_version_is_1_0(self, tmp_path: Path) -> None:
        """Verify version field is "1.0"."""
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["version"] == "1.0"

    def test_timestamp_is_iso8601_with_z(self, tmp_path: Path) -> None:
        """Verify timestamp is ISO-8601 format with Z suffix."""
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        ts = parsed["timestamp"]
        assert ts.endswith("Z")
        assert "T" in ts

    def test_blocked_context_json_fields(self, tmp_path: Path) -> None:
        """Verify blocked context JSON has correct values."""
        decision = make_decision_output(decision_state=DecisionState.BLOCK)
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        
        target = tmp_path / "blocked.json"
        write_execution_context(ctx, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["status"] == "INVALID"
        assert parsed["execution_state"] == "BLOCKED"
        assert parsed["execution_mode"] == "BLOCK_ALL"
        assert parsed["decision_state"] == "BLOCK"
        assert parsed["decision_action"] == "BLOCK_ALL"
        assert parsed["allowed_mode"] == "NONE"
        assert parsed["dry_run"] is True
        assert parsed["live_trading_enabled"] is False
        assert parsed["version"] == "1.0"


# ---------------------------------------------------------------------------
# Atomic write and path tests
# ---------------------------------------------------------------------------

class TestAtomicWriteAndPaths:
    def test_atomic_write_to_tmp_path(self, tmp_path: Path) -> None:
        """Verify atomic write works in temporary directory."""
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        assert target.exists()
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        assert parsed["execution_state"] == "DRY_RUN_ONLY"

    def test_nested_directory_creation(self, tmp_path: Path) -> None:
        """Verify parent directories are created automatically."""
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        
        target = tmp_path / "deep" / "nested" / "execution.json"
        write_execution_context(ctx, target)
        
        assert target.exists()

    def test_no_default_production_path_used(self, tmp_path: Path) -> None:
        """Verify tests use tmp_path, not production data/execution path."""
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        
        assert target.exists()
        prod_path = Path("data/execution/current_execution_context.json")
        assert not prod_path.exists() or prod_path.resolve() != target.resolve()


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------

class TestSafety:
    def test_no_network_calls(self) -> None:
        """Verify engine and writer do not make network calls."""
        import inspect
        from hunter.execution.engine import build_execution_context
        from hunter.execution.writer import write_execution_context
        
        engine_source = inspect.getsource(build_execution_context)
        writer_source = inspect.getsource(write_execution_context)
        
        for source in [engine_source, writer_source]:
            assert "requests" not in source
            assert "urllib" not in source
            assert "http" not in source
            assert "socket" not in source

    def test_no_trading_execution_logic(self) -> None:
        """Verify no trading execution logic exists."""
        import inspect
        from hunter.execution.engine import build_execution_context
        from hunter.execution.writer import write_execution_context
        
        engine_source = inspect.getsource(build_execution_context)
        writer_source = inspect.getsource(write_execution_context)
        
        for source in [engine_source, writer_source]:
            assert "buy(" not in source.lower()
            assert "sell(" not in source.lower()
            assert "position(" not in source.lower()
            assert "trade(" not in source.lower()
            assert "execute(" not in source.lower()
            assert "place_order" not in source.lower()

    def test_no_json_input_reading(self) -> None:
        """Verify integration tests do not read JSON input files."""
        import inspect
        source = inspect.getsource(TestEndToEndFlow)
        # Tests only write JSON, they construct inputs from model objects
        assert "read_decision" not in source
        assert "load_decision" not in source
        assert "from_json" not in source

    def test_no_freqtrade_runtime_integration(self) -> None:
        """Verify no Freqtrade runtime integration exists."""
        import hunter.execution.engine as engine_module
        import hunter.execution.writer as writer_module
        
        for module in [engine_module, writer_module]:
            source = module.__file__
            assert source is not None
            with open(source) as f:
                code = f.read()
            assert "from freqtrade" not in code.lower()
            assert "import freqtrade" not in code.lower()
            assert "strategy" not in code.lower()
            assert "pairlist" not in code.lower()

    def test_no_decision_output_json_reading(self) -> None:
        """Verify engine does not read DecisionOutput from JSON."""
        import inspect
        from hunter.execution.engine import build_execution_context
        source = inspect.getsource(build_execution_context)
        assert "json.load" not in source
        assert "open(" not in source or "json" not in source
        assert "read_decision" not in source
        assert "current_decision.json" not in source

    def test_all_outputs_have_dry_run_true(self) -> None:
        """Verify all execution contexts have dry_run=True."""
        # Successful path
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        assert ctx.dry_run is True
        
        # Blocked path
        blocked_ctx = build_execution_context(None, config)
        assert blocked_ctx.dry_run is True
        
        # Blocked factory
        factory_ctx = ExecutionContext.blocked()
        assert factory_ctx.dry_run is True

    def test_no_live_trading_enabled(self) -> None:
        """Verify live_trading_enabled is always False."""
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        assert ctx.live_trading_enabled is False
        
        blocked_ctx = build_execution_context(None, config)
        assert blocked_ctx.live_trading_enabled is False

    def test_no_exchange_connection_enabled(self) -> None:
        """Verify exchange_connection_enabled is always False."""
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        assert ctx.exchange_connection_enabled is False
        
        blocked_ctx = build_execution_context(None, config)
        assert blocked_ctx.exchange_connection_enabled is False

    def test_no_freqtrade_enabled(self) -> None:
        """Verify freqtrade_enabled is always False."""
        decision = make_decision_output()
        config = ExecutionBridgeConfig()
        ctx = build_execution_context(decision, config)
        assert ctx.freqtrade_enabled is False
        
        blocked_ctx = build_execution_context(None, config)
        assert blocked_ctx.freqtrade_enabled is False
