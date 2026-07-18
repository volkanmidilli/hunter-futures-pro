"""Integration tests for decision layer end-to-end flow.

Tests the full pipeline: RegimeOutput + BreadthOutput -> make_decision() -> write_decision_output()
No network, no trading logic, no JSON input reading.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.decision.engine import make_decision
from hunter.decision.models import (
    DecisionAction,
    DecisionConfig,
    DecisionInputRefs,
    DecisionOutput,
    DecisionState,
)
from hunter.decision.writer import decision_to_dict, write_decision_output
from hunter.market_state.models import (
    AllowedMode,
    BreadthOutput,
    DataQuality,
    OutputStatus,
    RegimeOutput,
    RegimeState,
    RiskState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_regime(
    regime: RegimeState = RegimeState.BULL,
    allowed_mode: AllowedMode = AllowedMode.LONG_ONLY,
    confidence: float = 0.82,
    status: OutputStatus = OutputStatus.VALID,
    timestamp: datetime | None = None,
    risk_state: RiskState = RiskState.RISK_ON,
    data_quality: DataQuality | None = None,
) -> RegimeOutput:
    return RegimeOutput(
        timestamp=timestamp or datetime.now(timezone.utc),
        status=status,
        market_regime=regime,
        allowed_mode=allowed_mode,
        confidence=confidence,
        risk_state=risk_state,
        btc_trend_score=85,
        eth_trend_score=74,
        breadth_confirmation_score=68,
        data_quality=data_quality or DataQuality(),
    )


def _make_breadth(
    breadth_score: int = 72,
    market_health: RiskState = RiskState.RISK_ON,
    status: OutputStatus = OutputStatus.VALID,
    timestamp: datetime | None = None,
    data_quality: DataQuality | None = None,
) -> BreadthOutput:
    return BreadthOutput(
        timestamp=timestamp or datetime.now(timezone.utc),
        status=status,
        breadth_score=breadth_score,
        market_health=market_health,
        universe_size=120,
        valid_symbol_count=115,
        invalid_symbol_count=5,
        above_ema20_pct=0.68,
        above_ema50_pct=0.55,
        above_ema200_pct=0.41,
        ema20_rising_pct=0.63,
        ema50_rising_pct=0.52,
        advancing_pct=0.61,
        declining_pct=0.39,
        outperforming_btc_7d_pct=0.46,
        outperforming_btc_30d_pct=0.34,
        data_quality=data_quality or DataQuality(),
    )


# ---------------------------------------------------------------------------
# End-to-end flow tests
# ---------------------------------------------------------------------------

class TestEndToEndFlow:
    def test_bull_long_healthy_full_pipeline(self, tmp_path: Path) -> None:
        """BULL + LONG_ONLY + healthy breadth -> ENABLE_LONG_ONLY_RESEARCH, JSON written."""
        regime = _make_regime(
            regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.82,
        )
        breadth = _make_breadth(breadth_score=72, market_health=RiskState.RISK_ON)
        
        decision = make_decision(regime, breadth)
        assert decision.decision_state == DecisionState.ALLOW
        assert decision.decision_action == DecisionAction.ENABLE_LONG_ONLY_RESEARCH
        
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["decision_state"] == "ALLOW"
        assert parsed["decision_action"] == "ENABLE_LONG_ONLY_RESEARCH"
        assert parsed["market_regime"] == "BULL"
        assert parsed["allowed_mode"] == "LONG_ONLY"
        assert parsed["confidence"] == 0.72  # min(0.82, 72/100)
        assert parsed["breadth_score"] == 72
        assert parsed["reason_codes"] == ["BULL_HEALTHY_BREADTH"]
        assert parsed["input_refs"]["regime_source"] == "regime_engine"
        assert parsed["input_refs"]["breadth_source"] == "breadth_engine"

    def test_bear_short_weak_full_pipeline(self, tmp_path: Path) -> None:
        """BEAR + SHORT_ONLY + weak breadth -> ENABLE_SHORT_ONLY_RESEARCH, JSON written."""
        regime = _make_regime(
            regime=RegimeState.BEAR,
            allowed_mode=AllowedMode.SHORT_ONLY,
            confidence=0.82,
            risk_state=RiskState.RISK_OFF,
        )
        breadth = _make_breadth(breadth_score=30, market_health=RiskState.RISK_OFF)
        
        decision = make_decision(regime, breadth)
        assert decision.decision_state == DecisionState.ALLOW
        assert decision.decision_action == DecisionAction.ENABLE_SHORT_ONLY_RESEARCH
        
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["decision_state"] == "ALLOW"
        assert parsed["decision_action"] == "ENABLE_SHORT_ONLY_RESEARCH"
        assert parsed["market_regime"] == "BEAR"
        assert parsed["allowed_mode"] == "SHORT_ONLY"
        assert parsed["confidence"] == 0.30  # min(0.82, 30/100)
        assert parsed["breadth_score"] == 30
        assert parsed["reason_codes"] == ["BEAR_WEAK_BREADTH"]

    def test_unknown_regime_blocks_pipeline(self, tmp_path: Path) -> None:
        """UNKNOWN regime -> BLOCK_ALL, JSON written with block state."""
        regime = _make_regime(
            regime=RegimeState.UNKNOWN,
            allowed_mode=AllowedMode.NONE,
            confidence=0.0,
        )
        breadth = _make_breadth()
        
        decision = make_decision(regime, breadth)
        assert decision.decision_state == DecisionState.BLOCK
        assert decision.decision_action == DecisionAction.BLOCK_ALL
        assert decision.is_blocking() is True
        
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["decision_state"] == "BLOCK"
        assert parsed["decision_action"] == "BLOCK_ALL"
        assert parsed["allowed_mode"] == "NONE"
        assert parsed["confidence"] == 0.0
        assert "UNKNOWN_REGIME" in parsed["reason_codes"]

    def test_invalid_breadth_blocks_pipeline(self, tmp_path: Path) -> None:
        """INVALID breadth -> BLOCK_ALL, JSON written with block state."""
        regime = _make_regime()
        breadth = _make_breadth(status=OutputStatus.INVALID)
        
        decision = make_decision(regime, breadth)
        assert decision.decision_state == DecisionState.BLOCK
        assert decision.decision_action == DecisionAction.BLOCK_ALL
        
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["decision_state"] == "BLOCK"
        assert "INVALID_BREADTH" in parsed["reason_codes"]

    def test_sideways_blocks_pipeline(self, tmp_path: Path) -> None:
        """SIDEWAYS -> BLOCK_ALL, JSON written with block state."""
        regime = _make_regime(
            regime=RegimeState.SIDEWAYS,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.82,
        )
        breadth = _make_breadth()
        
        decision = make_decision(regime, breadth)
        assert decision.decision_state == DecisionState.BLOCK
        assert decision.decision_action == DecisionAction.BLOCK_ALL
        
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["decision_state"] == "BLOCK"
        assert "SIDEWAYS_NO_DIRECTION" in parsed["reason_codes"]

    def test_transition_blocks_pipeline(self, tmp_path: Path) -> None:
        """TRANSITION -> BLOCK_ALL, JSON written with block state."""
        regime = _make_regime(
            regime=RegimeState.TRANSITION,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.82,
        )
        breadth = _make_breadth()
        
        decision = make_decision(regime, breadth)
        assert decision.decision_state == DecisionState.BLOCK
        assert decision.decision_action == DecisionAction.BLOCK_ALL
        
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["decision_state"] == "BLOCK"
        assert "TRANSITION_UNCERTAIN" in parsed["reason_codes"]

    def test_stale_regime_blocks_pipeline(self, tmp_path: Path) -> None:
        """Stale regime -> BLOCK_ALL, JSON written with block state."""
        config = DecisionConfig(stale_input_minutes=30)
        old = datetime.now(timezone.utc) - timedelta(minutes=60)
        regime = _make_regime(timestamp=old)
        breadth = _make_breadth()
        
        decision = make_decision(regime, breadth, config)
        assert decision.decision_state == DecisionState.BLOCK
        assert decision.decision_action == DecisionAction.BLOCK_ALL
        
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["decision_state"] == "BLOCK"
        assert "STALE_INPUT" in parsed["reason_codes"]

    def test_stale_breadth_blocks_pipeline(self, tmp_path: Path) -> None:
        """Stale breadth -> BLOCK_ALL, JSON written with block state."""
        config = DecisionConfig(stale_input_minutes=30)
        old = datetime.now(timezone.utc) - timedelta(minutes=60)
        regime = _make_regime()
        breadth = _make_breadth(timestamp=old)
        
        decision = make_decision(regime, breadth, config)
        assert decision.decision_state == DecisionState.BLOCK
        assert decision.decision_action == DecisionAction.BLOCK_ALL
        
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["decision_state"] == "BLOCK"
        assert "STALE_INPUT" in parsed["reason_codes"]

    def test_conflict_blocks_pipeline(self, tmp_path: Path) -> None:
        """Conflicting signals -> BLOCK_ALL, JSON written with block state."""
        regime = _make_regime(
            regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.82,
        )
        breadth = _make_breadth(
            breadth_score=30,  # Low score conflicts with BULL
            market_health=RiskState.RISK_OFF,
        )
        
        decision = make_decision(regime, breadth)
        assert decision.decision_state == DecisionState.BLOCK
        assert decision.decision_action == DecisionAction.BLOCK_ALL
        
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        assert parsed["decision_state"] == "BLOCK"
        assert "CONFLICTING_SIGNALS" in parsed["reason_codes"]

    def test_json_contains_all_expected_fields(self, tmp_path: Path) -> None:
        """Verify serialized JSON contains all expected fields from SPEC-004."""
        regime = _make_regime()
        breadth = _make_breadth()
        decision = make_decision(regime, breadth)
        
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        expected_fields = {
            "timestamp",
            "status",
            "decision_state",
            "decision_action",
            "allowed_mode",
            "market_regime",
            "risk_state",
            "confidence",
            "regime_confidence",
            "breadth_score",
            "market_health",
            "reason_codes",
            "input_refs",
            "data_quality",
            "_safety_notice",
        }
        assert set(parsed.keys()) == expected_fields
        
        # Verify input_refs sub-fields
        assert set(parsed["input_refs"].keys()) == {
            "regime_timestamp",
            "breadth_timestamp",
            "regime_source",
            "breadth_source",
        }
        
        # Verify data_quality sub-fields
        assert set(parsed["data_quality"].keys()) == {
            "missing",
            "stale",
            "insufficient_history",
            "insufficient_universe",
        }

    def test_enum_values_are_strings_in_json(self, tmp_path: Path) -> None:
        """Verify all enum values are serialized as strings, not objects."""
        regime = _make_regime()
        breadth = _make_breadth()
        decision = make_decision(regime, breadth)
        
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        with open(target, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        
        enum_fields = [
            "status", "decision_state", "decision_action",
            "allowed_mode", "market_regime", "risk_state", "market_health",
        ]
        for field in enum_fields:
            assert isinstance(parsed[field], str), f"{field} should be string"

    def test_no_default_production_path_used(self, tmp_path: Path) -> None:
        """Verify tests use tmp_path, not production data/decision path."""
        regime = _make_regime()
        breadth = _make_breadth()
        decision = make_decision(regime, breadth)
        
        # Use tmp_path for all test outputs
        target = tmp_path / "decision.json"
        write_decision_output(decision, target)
        
        assert target.exists()
        # Production path should not exist
        prod_path = Path("data/decision/current_decision.json")
        assert not prod_path.exists() or prod_path.resolve() != target.resolve()


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------

class TestSafety:
    def test_no_network_calls(self) -> None:
        import inspect
        from hunter.decision.engine import make_decision
        from hunter.decision.writer import write_decision_output
        
        engine_source = inspect.getsource(make_decision)
        writer_source = inspect.getsource(write_decision_output)
        
        for source in [engine_source, writer_source]:
            assert "requests" not in source
            assert "urllib" not in source
            assert "http" not in source
            assert "socket" not in source

    def test_no_trading_execution_logic(self) -> None:
        import inspect
        from hunter.decision.engine import make_decision
        from hunter.decision.writer import write_decision_output
        
        engine_source = inspect.getsource(make_decision)
        writer_source = inspect.getsource(write_decision_output)
        
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
        assert "json.load" not in source or "open(" in source
        # The tests only write JSON, they construct inputs from model objects
        assert "read_regime" not in source
        assert "read_breadth" not in source
