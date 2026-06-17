"""Tests for JSON output writers."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.market_state.models import (
    AllowedMode,
    BreadthOutput,
    DataQuality,
    OutputStatus,
    RegimeOutput,
    RegimeState,
    RiskState,
)
from hunter.market_state.writer import (
    atomic_write_json,
    breadth_to_dict,
    regime_to_dict,
    write_breadth_output,
    write_regime_output,
)


class TestRegimeToDict:
    """Tests for regime output serialization."""

    def test_serializes_valid_regime(self) -> None:
        output = RegimeOutput(
            timestamp=datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc),
            status=OutputStatus.VALID,
            market_regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.82,
            risk_state=RiskState.RISK_ON,
            btc_trend_score=85,
            eth_trend_score=74,
            breadth_confirmation_score=68,
            reason_codes=["BTC_CLOSE_ABOVE_EMA20"],
            data_quality=DataQuality(),
        )
        d = regime_to_dict(output)
        assert d["timestamp"] == "2026-06-17T12:00:00Z"
        assert d["status"] == "VALID"
        assert d["market_regime"] == "BULL"
        assert d["allowed_mode"] == "LONG_ONLY"
        assert d["confidence"] == 0.82
        assert d["risk_state"] == "RISK_ON"
        assert d["btc_trend_score"] == 85
        assert d["eth_trend_score"] == 74
        assert d["breadth_confirmation_score"] == 68
        assert d["reason_codes"] == ["BTC_CLOSE_ABOVE_EMA20"]
        assert d["data_quality"]["missing"] is False

    def test_serializes_unknown_regime(self) -> None:
        output = RegimeOutput.unknown(
            timestamp=datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc),
            reason_codes=["DATA_MISSING"],
            data_quality=DataQuality(missing=True),
        )
        d = regime_to_dict(output)
        assert d["timestamp"] == "2026-06-17T12:00:00Z"
        assert d["status"] == "INVALID"
        assert d["market_regime"] == "UNKNOWN"
        assert d["allowed_mode"] == "NONE"
        assert d["confidence"] == 0.0
        assert d["risk_state"] == "UNKNOWN"
        assert d["reason_codes"] == ["DATA_MISSING"]
        assert d["data_quality"]["missing"] is True

    def test_iso_8601_format(self) -> None:
        output = RegimeOutput(
            timestamp=datetime(2026, 6, 17, 12, 30, 45, tzinfo=timezone.utc),
            status=OutputStatus.VALID,
            market_regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.5,
            risk_state=RiskState.RISK_ON,
            btc_trend_score=50,
            eth_trend_score=0,
            breadth_confirmation_score=0,
            reason_codes=["TEST"],
            data_quality=DataQuality(),
        )
        d = regime_to_dict(output)
        assert d["timestamp"] == "2026-06-17T12:30:45Z"

    def test_naive_datetime_gets_z_suffix(self) -> None:
        output = RegimeOutput(
            timestamp=datetime(2026, 6, 17, 12, 0, 0),
            status=OutputStatus.VALID,
            market_regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.5,
            risk_state=RiskState.RISK_ON,
            btc_trend_score=50,
            eth_trend_score=0,
            breadth_confirmation_score=0,
            reason_codes=["TEST"],
            data_quality=DataQuality(),
        )
        d = regime_to_dict(output)
        assert d["timestamp"] == "2026-06-17T12:00:00Z"

    def test_enum_fields_are_strings(self) -> None:
        output = RegimeOutput(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.VALID,
            market_regime=RegimeState.BEAR,
            allowed_mode=AllowedMode.SHORT_ONLY,
            confidence=0.7,
            risk_state=RiskState.RISK_OFF,
            btc_trend_score=80,
            eth_trend_score=0,
            breadth_confirmation_score=0,
            reason_codes=["TEST"],
            data_quality=DataQuality(),
        )
        d = regime_to_dict(output)
        assert isinstance(d["status"], str)
        assert isinstance(d["market_regime"], str)
        assert isinstance(d["allowed_mode"], str)
        assert isinstance(d["risk_state"], str)
        assert d["market_regime"] == "BEAR"
        assert d["allowed_mode"] == "SHORT_ONLY"

    def test_data_quality_serializes_correctly(self) -> None:
        output = RegimeOutput(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.VALID,
            market_regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.5,
            risk_state=RiskState.RISK_ON,
            btc_trend_score=50,
            eth_trend_score=0,
            breadth_confirmation_score=0,
            reason_codes=["TEST"],
            data_quality=DataQuality(missing=True, stale=True, insufficient_history=True, insufficient_universe=True),
        )
        d = regime_to_dict(output)
        dq = d["data_quality"]
        assert dq["missing"] is True
        assert dq["stale"] is True
        assert dq["insufficient_history"] is True
        assert dq["insufficient_universe"] is True

    def test_reason_codes_serializes_correctly(self) -> None:
        output = RegimeOutput(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.VALID,
            market_regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.5,
            risk_state=RiskState.RISK_ON,
            btc_trend_score=50,
            eth_trend_score=0,
            breadth_confirmation_score=0,
            reason_codes=["CODE1", "CODE2", "CODE3"],
            data_quality=DataQuality(),
        )
        d = regime_to_dict(output)
        assert d["reason_codes"] == ["CODE1", "CODE2", "CODE3"]
        assert isinstance(d["reason_codes"], list)


class TestBreadthToDict:
    """Tests for breadth output serialization."""

    def test_serializes_valid_breadth(self) -> None:
        output = BreadthOutput(
            timestamp=datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc),
            status=OutputStatus.VALID,
            breadth_score=72,
            market_health=RiskState.RISK_ON,
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
            reason_codes=["MAJORITY_ABOVE_EMA20"],
            data_quality=DataQuality(),
        )
        d = breadth_to_dict(output)
        assert d["timestamp"] == "2026-06-17T12:00:00Z"
        assert d["status"] == "VALID"
        assert d["breadth_score"] == 72
        assert d["market_health"] == "RISK_ON"
        assert d["universe_size"] == 120
        assert d["valid_symbol_count"] == 115
        assert d["invalid_symbol_count"] == 5
        assert d["above_ema20_pct"] == 0.68
        assert d["above_ema50_pct"] == 0.55
        assert d["above_ema200_pct"] == 0.41
        assert d["ema20_rising_pct"] == 0.63
        assert d["ema50_rising_pct"] == 0.52
        assert d["advancing_pct"] == 0.61
        assert d["declining_pct"] == 0.39
        assert d["outperforming_btc_7d_pct"] == 0.46
        assert d["outperforming_btc_30d_pct"] == 0.34
        assert d["reason_codes"] == ["MAJORITY_ABOVE_EMA20"]
        assert d["data_quality"]["missing"] is False

    def test_serializes_invalid_breadth(self) -> None:
        output = BreadthOutput.invalid(
            timestamp=datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc),
            reason_codes=["DATA_MISSING"],
            data_quality=DataQuality(missing=True, insufficient_universe=True),
        )
        d = breadth_to_dict(output)
        assert d["timestamp"] == "2026-06-17T12:00:00Z"
        assert d["status"] == "INVALID"
        assert d["breadth_score"] == 0
        assert d["market_health"] == "UNKNOWN"
        assert d["universe_size"] == 0
        assert d["valid_symbol_count"] == 0
        assert d["invalid_symbol_count"] == 0
        assert d["reason_codes"] == ["DATA_MISSING"]
        assert d["data_quality"]["missing"] is True
        assert d["data_quality"]["insufficient_universe"] is True


class TestAtomicWriteJson:
    """Tests for atomic JSON file writes."""

    def test_writes_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test.json"
            data = {"key": "value", "number": 42}
            atomic_write_json(data, target)
            assert target.exists()
            with open(target, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded == data

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "deep" / "nested" / "test.json"
            data = {"key": "value"}
            atomic_write_json(data, target)
            assert target.exists()

    def test_no_partial_file_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test.json"
            # Create a read-only directory to cause failure
            bad_dir = Path(tmpdir) / "readonly"
            bad_dir.mkdir()
            os.chmod(bad_dir, 0o555)
            bad_target = bad_dir / "test.json"
            data = {"key": "value"}
            with pytest.raises(OSError):
                atomic_write_json(data, bad_target)
            # No partial file should exist
            assert not bad_target.exists()
            # No temp file should remain
            temp_files = list(bad_dir.glob("*.tmp"))
            assert len(temp_files) == 0
            os.chmod(bad_dir, 0o755)

    def test_json_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test.json"
            data = {"unicode": "hello 世界", "nested": {"key": "value"}}
            atomic_write_json(data, target)
            with open(target, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["unicode"] == "hello 世界"


class TestWriteRegimeOutput:
    """Tests for writing regime output to file."""

    def test_writes_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "data" / "regime" / "current_regime.json"
            output = RegimeOutput(
                timestamp=datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc),
                status=OutputStatus.VALID,
                market_regime=RegimeState.BULL,
                allowed_mode=AllowedMode.LONG_ONLY,
                confidence=0.82,
                risk_state=RiskState.RISK_ON,
                btc_trend_score=85,
                eth_trend_score=74,
                breadth_confirmation_score=68,
                reason_codes=["BTC_CLOSE_ABOVE_EMA20"],
                data_quality=DataQuality(),
            )
            path = write_regime_output(output, target)
            assert path == target
            assert target.exists()
            with open(target, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["market_regime"] == "BULL"
            assert loaded["confidence"] == 0.82

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "deep" / "regime" / "current_regime.json"
            output = RegimeOutput.unknown()
            write_regime_output(output, target)
            assert target.exists()


class TestWriteBreadthOutput:
    """Tests for writing breadth output to file."""

    def test_writes_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "data" / "breadth" / "current_breadth.json"
            output = BreadthOutput(
                timestamp=datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc),
                status=OutputStatus.VALID,
                breadth_score=72,
                market_health=RiskState.RISK_ON,
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
                reason_codes=["MAJORITY_ABOVE_EMA20"],
                data_quality=DataQuality(),
            )
            path = write_breadth_output(output, target)
            assert path == target
            assert target.exists()
            with open(target, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["breadth_score"] == 72
            assert loaded["market_health"] == "RISK_ON"

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "deep" / "breadth" / "current_breadth.json"
            output = BreadthOutput.invalid()
            write_breadth_output(output, target)
            assert target.exists()


class TestSafety:
    """Safety tests for writer module."""

    def test_no_network_calls(self) -> None:
        """Verify no network imports exist in writer module."""
        import inspect
        import hunter.market_state.writer as writer_module

        source = inspect.getsource(writer_module)
        assert "requests" not in source
        assert "urllib" not in source
        assert "http" not in source
        assert "socket" not in source

    def test_no_trading_logic(self) -> None:
        """Verify no trading execution logic exists in writer module."""
        import inspect
        import hunter.market_state.writer as writer_module

        source = inspect.getsource(writer_module)
        trading_terms = ["order", "position", "trade", "buy", "sell"]
        for term in trading_terms:
            assert term not in source.lower(), f"Found trading term: {term}"
        assert "execute_trade" not in source.lower()
        assert "place_order" not in source.lower()
        assert "entry_price" not in source.lower()
        assert "stop_loss" not in source.lower()
        assert "take_profit" not in source.lower()
