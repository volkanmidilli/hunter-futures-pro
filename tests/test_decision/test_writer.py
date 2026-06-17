"""Tests for decision writer."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.decision.models import (
    DecisionAction,
    DecisionConfig,
    DecisionInputRefs,
    DecisionOutput,
    DecisionState,
)
from hunter.decision.writer import (
    atomic_write_json,
    decision_to_dict,
    write_decision_output,
)
from hunter.market_state.models import (
    AllowedMode,
    DataQuality,
    OutputStatus,
    RegimeState,
    RiskState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_decision_output(
    decision_state: DecisionState = DecisionState.ALLOW,
    decision_action: DecisionAction = DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
    allowed_mode: AllowedMode = AllowedMode.LONG_ONLY,
    market_regime: RegimeState = RegimeState.BULL,
    confidence: float = 0.82,
    breadth_score: int = 72,
    market_health: RiskState = RiskState.RISK_ON,
    timestamp: datetime | None = None,
    reason_codes: list[str] | None = None,
    input_refs: DecisionInputRefs | None = None,
    data_quality: DataQuality | None = None,
) -> DecisionOutput:
    return DecisionOutput(
        timestamp=timestamp or datetime.now(timezone.utc),
        status=OutputStatus.VALID,
        decision_state=decision_state,
        decision_action=decision_action,
        allowed_mode=allowed_mode,
        market_regime=market_regime,
        risk_state=RiskState.RISK_ON,
        confidence=confidence,
        regime_confidence=confidence,
        breadth_score=breadth_score,
        market_health=market_health,
        reason_codes=reason_codes or ["BULL_HEALTHY_BREADTH"],
        input_refs=input_refs
        or DecisionInputRefs(
            regime_timestamp="2026-06-17T12:00:00Z",
            breadth_timestamp="2026-06-17T12:00:00Z",
            regime_source="regime_engine",
            breadth_source="breadth_engine",
        ),
        data_quality=data_quality or DataQuality(),
    )


# ---------------------------------------------------------------------------
# decision_to_dict tests
# ---------------------------------------------------------------------------

class TestDecisionToDict:
    def test_serializes_valid_decision(self) -> None:
        now = datetime.now(timezone.utc)
        output = _make_decision_output(timestamp=now)
        d = decision_to_dict(output)
        assert d["timestamp"] == now.strftime("%Y-%m-%dT%H:%M:%SZ")
        assert d["status"] == "VALID"
        assert d["decision_state"] == "ALLOW"
        assert d["decision_action"] == "ENABLE_LONG_ONLY_RESEARCH"
        assert d["allowed_mode"] == "LONG_ONLY"
        assert d["market_regime"] == "BULL"
        assert d["risk_state"] == "RISK_ON"
        assert d["confidence"] == 0.82
        assert d["regime_confidence"] == 0.82
        assert d["breadth_score"] == 72
        assert d["market_health"] == "RISK_ON"
        assert d["reason_codes"] == ["BULL_HEALTHY_BREADTH"]

    def test_serializes_block_decision(self) -> None:
        now = datetime.now(timezone.utc)
        output = DecisionOutput.block_all(timestamp=now)
        d = decision_to_dict(output)
        assert d["decision_state"] == "BLOCK"
        assert d["decision_action"] == "BLOCK_ALL"
        assert d["allowed_mode"] == "NONE"
        assert d["market_regime"] == "UNKNOWN"
        assert d["confidence"] == 0.0
        assert d["regime_confidence"] == 0.0
        assert d["breadth_score"] == 0
        assert d["market_health"] == "UNKNOWN"
        assert d["reason_codes"] == ["DECISION_BLOCKED_BY_DEFAULT"]

    def test_iso_8601_format(self) -> None:
        now = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        output = _make_decision_output(timestamp=now)
        d = decision_to_dict(output)
        assert d["timestamp"] == "2026-06-17T12:00:00Z"

    def test_naive_datetime_gets_z_suffix(self) -> None:
        naive = datetime(2026, 6, 17, 12, 0, 0)
        output = _make_decision_output(timestamp=naive)
        d = decision_to_dict(output)
        assert d["timestamp"] == "2026-06-17T12:00:00Z"

    def test_enum_fields_are_strings(self) -> None:
        output = _make_decision_output()
        d = decision_to_dict(output)
        for key in [
            "status",
            "decision_state",
            "decision_action",
            "allowed_mode",
            "market_regime",
            "risk_state",
            "market_health",
        ]:
            assert isinstance(d[key], str), f"{key} should be a string"

    def test_input_refs_serializes_correctly(self) -> None:
        output = _make_decision_output(
            input_refs=DecisionInputRefs(
                regime_timestamp="2026-06-17T12:00:00Z",
                breadth_timestamp="2026-06-17T12:00:00Z",
                regime_source="regime_engine",
                breadth_source="breadth_engine",
            )
        )
        d = decision_to_dict(output)
        refs = d["input_refs"]
        assert refs["regime_timestamp"] == "2026-06-17T12:00:00Z"
        assert refs["breadth_timestamp"] == "2026-06-17T12:00:00Z"
        assert refs["regime_source"] == "regime_engine"
        assert refs["breadth_source"] == "breadth_engine"

    def test_data_quality_serializes_correctly(self) -> None:
        output = _make_decision_output(
            data_quality=DataQuality(missing=True, stale=True)
        )
        d = decision_to_dict(output)
        dq = d["data_quality"]
        assert dq["missing"] is True
        assert dq["stale"] is True
        assert dq["insufficient_history"] is False
        assert dq["insufficient_universe"] is False

    def test_reason_codes_serializes_correctly(self) -> None:
        output = _make_decision_output(reason_codes=["MISSING_REGIME", "STALE_INPUT"])
        d = decision_to_dict(output)
        assert d["reason_codes"] == ["MISSING_REGIME", "STALE_INPUT"]

    def test_json_roundtrip(self) -> None:
        output = _make_decision_output()
        d = decision_to_dict(output)
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["decision_state"] == "ALLOW"
        assert parsed["confidence"] == 0.82
        assert parsed["breadth_score"] == 72


# ---------------------------------------------------------------------------
# atomic_write_json tests
# ---------------------------------------------------------------------------

class TestAtomicWriteJson:
    def test_writes_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test.json"
            data = {"key": "value", "number": 42}
            atomic_write_json(data, target)
            assert target.exists()
            with open(target, "r", encoding="utf-8") as f:
                parsed = json.load(f)
            assert parsed == data

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "deep" / "nested" / "test.json"
            data = {"key": "value"}
            atomic_write_json(data, target)
            assert target.exists()

    def test_no_partial_file_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test.json"
            # Pass non-serializable data to trigger failure
            data = {"key": object()}  # type: ignore[dict-item]
            with pytest.raises((TypeError, ValueError)):
                atomic_write_json(data, target)
            # Target should not exist (temp file cleaned up)
            assert not target.exists()
            # No .tmp files should remain
            tmp_files = list(Path(tmpdir).glob("*.tmp"))
            assert len(tmp_files) == 0

    def test_json_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test.json"
            data = {"unicode": "日本語"}
            atomic_write_json(data, target)
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()
            assert "日本語" in content


# ---------------------------------------------------------------------------
# write_decision_output tests
# ---------------------------------------------------------------------------

class TestWriteDecisionOutput:
    def test_writes_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "data" / "decision" / "current_decision.json"
            output = _make_decision_output()
            result = write_decision_output(output, target)
            assert result == target
            assert target.exists()
            with open(target, "r", encoding="utf-8") as f:
                parsed = json.load(f)
            assert parsed["decision_state"] == "ALLOW"
            assert parsed["confidence"] == 0.82

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "deep" / "nested" / "decision.json"
            output = _make_decision_output()
            write_decision_output(output, target)
            assert target.exists()

    def test_default_path_is_data_decision_current(self) -> None:
        output = _make_decision_output()
        # Just verify the default path constant
        import inspect
        sig = inspect.signature(write_decision_output)
        default = sig.parameters["target_path"].default
        assert "data/decision/current_decision.json" in str(default)

    def test_invalid_path_fails(self) -> None:
        # Writing to a file in a non-existent directory with no write permissions
        # is hard to test portably; instead verify that bad paths raise
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file where we want to write a directory
            blocking_file = Path(tmpdir) / "blocking"
            blocking_file.write_text("x")
            target = Path(tmpdir) / "blocking" / "decision.json"
            output = _make_decision_output()
            with pytest.raises(OSError):
                write_decision_output(output, target)


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------

class TestSafety:
    def test_no_network_calls(self) -> None:
        import inspect
        source = inspect.getsource(decision_to_dict)
        assert "requests" not in source
        assert "urllib" not in source
        assert "http" not in source
        assert "socket" not in source

    def test_no_trading_logic(self) -> None:
        import inspect
        source = inspect.getsource(decision_to_dict)
        assert "order" not in source.lower()
        assert "position" not in source.lower()
        assert "buy" not in source.lower()
        assert "sell" not in source.lower()
        assert "trade" not in source.lower()
