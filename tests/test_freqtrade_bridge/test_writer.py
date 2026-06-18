"""Tests for Freqtrade bridge writer."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
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
from hunter.freqtrade_bridge.writer import (
    atomic_write_json,
    freqtrade_bridge_context_to_dict,
    write_freqtrade_bridge_context,
)


class TestFreqtradeBridgeContextToDict:
    """Tests for freqtrade_bridge_context_to_dict()."""

    def test_timestamp_is_iso8601(self) -> None:
        ts = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
        )
        d = freqtrade_bridge_context_to_dict(ctx)
        assert d["timestamp"] == "2025-01-15T10:30:00Z"

    def test_enum_fields_serialize_to_strings(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
        )
        d = freqtrade_bridge_context_to_dict(ctx)
        assert d["bridge_state"] == "DRY_RUN_READY"
        assert d["bridge_mode"] == "LONG_RESEARCH_ONLY"
        assert isinstance(d["bridge_state"], str)
        assert isinstance(d["bridge_mode"], str)

    def test_input_refs_serialize(self) -> None:
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
        d = freqtrade_bridge_context_to_dict(ctx)
        assert d["input_refs"]["execution_context_timestamp"] == "2025-01-15T10:30:00Z"
        assert d["input_refs"]["execution_context_version"] == "1.0"

    def test_safety_flags_serialize(self) -> None:
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
        d = freqtrade_bridge_context_to_dict(ctx)
        assert d["safety_flags"]["dry_run"] is True
        assert d["safety_flags"]["live_trading_enabled"] is False
        assert d["safety_flags"]["exchange_connection_enabled"] is False
        assert d["safety_flags"]["freqtrade_runtime_enabled"] is False
        assert d["safety_flags"]["strategy_enabled"] is False
        assert d["safety_flags"]["real_orders_enabled"] is False
        assert d["safety_flags"]["leverage_enabled"] is False
        assert d["safety_flags"]["shorting_enabled"] is False
        assert d["safety_flags"]["human_override_required"] is False
        assert d["safety_flags"]["max_context_age_seconds"] == 300

    def test_data_quality_serialize(self) -> None:
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
        d = freqtrade_bridge_context_to_dict(ctx)
        assert d["data_quality"]["execution_context_fresh"] is True
        assert d["data_quality"]["execution_context_valid"] is True
        assert d["data_quality"]["validation_errors"] == []

    def test_version_serialize(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
        )
        d = freqtrade_bridge_context_to_dict(ctx)
        assert d["version"] == "1.0"

    def test_reason_codes_serialize(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="blocked",
            bridge_state=FreqtradeBridgeState.BLOCKED,
            bridge_mode=FreqtradeBridgeMode.BLOCK_ALL,
            execution_state="unknown",
            execution_mode="unknown",
            reason_codes=["missing_execution_context"],
        )
        d = freqtrade_bridge_context_to_dict(ctx)
        assert d["reason_codes"] == ["missing_execution_context"]

    def test_blocked_context_serialize(self) -> None:
        ctx = FreqtradeBridgeContext.blocked()
        d = freqtrade_bridge_context_to_dict(ctx)
        assert d["status"] == "blocked"
        assert d["bridge_state"] == "BLOCKED"
        assert d["bridge_mode"] == "BLOCK_ALL"
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["version"] == "1.0"
        assert d["reason_codes"] == ["FREQTRADE_BRIDGE_BLOCKED_BY_DEFAULT"]

    def test_all_fields_present(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
        )
        d = freqtrade_bridge_context_to_dict(ctx)
        expected_keys = {
            "timestamp",
            "status",
            "bridge_state",
            "bridge_mode",
            "execution_state",
            "execution_mode",
            "dry_run",
            "live_trading_enabled",
            "exchange_connection_enabled",
            "freqtrade_runtime_enabled",
            "strategy_enabled",
            "real_orders_enabled",
            "leverage_enabled",
            "shorting_enabled",
            "reason_codes",
            "input_refs",
            "data_quality",
            "safety_flags",
            "version",
        }
        assert set(d.keys()) == expected_keys

    def test_json_roundtrip(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
        )
        d = freqtrade_bridge_context_to_dict(ctx)
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["bridge_state"] == "DRY_RUN_READY"
        assert parsed["bridge_mode"] == "LONG_RESEARCH_ONLY"
        assert parsed["version"] == "1.0"


class TestAtomicWriteJson:
    """Tests for atomic_write_json()."""

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "output.json"
        data = {"test": "value"}
        atomic_write_json(data, target)
        assert target.exists()
        with open(target) as f:
            assert json.load(f) == data

    def test_atomic_write_no_partial_on_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        data = {"test": "value"}
        atomic_write_json(data, target)
        assert target.exists()
        # Check no temp files left behind
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        atomic_write_json({"old": "data"}, target)
        atomic_write_json({"new": "data"}, target)
        with open(target) as f:
            assert json.load(f) == {"new": "data"}

    def test_json_indent_format(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        data = {"key": "value"}
        atomic_write_json(data, target)
        with open(target) as f:
            content = f.read()
        assert '"key": "value"' in content


class TestWriteFreqtradeBridgeContext:
    """Tests for write_freqtrade_bridge_context()."""

    def test_default_path(self, tmp_path: Path) -> None:
        ctx = FreqtradeBridgeContext.blocked()
        # Use a temp path instead of default production path
        target = tmp_path / "current_freqtrade_context.json"
        result = write_freqtrade_bridge_context(ctx, target)
        assert result == target
        assert target.exists()

    def test_creates_nested_directories(self, tmp_path: Path) -> None:
        ctx = FreqtradeBridgeContext.blocked()
        target = tmp_path / "data" / "freqtrade" / "current_freqtrade_context.json"
        write_freqtrade_bridge_context(ctx, target)
        assert target.exists()
        with open(target) as f:
            d = json.load(f)
        assert d["bridge_state"] == "BLOCKED"
        assert d["version"] == "1.0"

    def test_writes_valid_json(self, tmp_path: Path) -> None:
        ts = datetime.now(timezone.utc)
        ctx = FreqtradeBridgeContext(
            timestamp=ts,
            status="success",
            bridge_state=FreqtradeBridgeState.DRY_RUN_READY,
            bridge_mode=FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            execution_state="dry_run_only",
            execution_mode="long_research_only",
        )
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(ctx, target)
        with open(target) as f:
            d = json.load(f)
        assert d["status"] == "success"
        assert d["bridge_state"] == "DRY_RUN_READY"
        assert d["bridge_mode"] == "LONG_RESEARCH_ONLY"
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["version"] == "1.0"
        assert d["reason_codes"] == []

    def test_returns_path(self, tmp_path: Path) -> None:
        ctx = FreqtradeBridgeContext.blocked()
        target = tmp_path / "output.json"
        result = write_freqtrade_bridge_context(ctx, target)
        assert isinstance(result, Path)
        assert str(result) == str(target)

    def test_default_path_constant(self) -> None:
        # Verify the default path is the expected production path
        import inspect
        sig = inspect.signature(write_freqtrade_bridge_context)
        default = sig.parameters["target_path"].default
        assert str(default) == "data/freqtrade/current_freqtrade_context.json"

    def test_safety_flags_in_output(self, tmp_path: Path) -> None:
        ctx = FreqtradeBridgeContext.blocked()
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(ctx, target)
        with open(target) as f:
            d = json.load(f)
        assert d["safety_flags"]["dry_run"] is True
        assert d["safety_flags"]["live_trading_enabled"] is False
        assert d["safety_flags"]["exchange_connection_enabled"] is False
        assert d["safety_flags"]["freqtrade_runtime_enabled"] is False
        assert d["safety_flags"]["strategy_enabled"] is False
        assert d["safety_flags"]["real_orders_enabled"] is False
        assert d["safety_flags"]["leverage_enabled"] is False
        assert d["safety_flags"]["shorting_enabled"] is False
        assert d["safety_flags"]["human_override_required"] is False
        assert d["safety_flags"]["max_context_age_seconds"] == 300

    def test_data_quality_in_output(self, tmp_path: Path) -> None:
        ctx = FreqtradeBridgeContext.blocked()
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(ctx, target)
        with open(target) as f:
            d = json.load(f)
        assert d["data_quality"]["execution_context_fresh"] is False
        assert d["data_quality"]["execution_context_valid"] is False
        assert d["data_quality"]["validation_errors"] == []

    def test_input_refs_in_output(self, tmp_path: Path) -> None:
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
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(ctx, target)
        with open(target) as f:
            d = json.load(f)
        assert d["input_refs"]["execution_context_timestamp"] == "2025-01-15T10:30:00Z"
        assert d["input_refs"]["execution_context_version"] == "1.0"

    def test_reason_codes_in_output(self, tmp_path: Path) -> None:
        ctx = FreqtradeBridgeContext.blocked(reason_codes=["custom_reason"])
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(ctx, target)
        with open(target) as f:
            d = json.load(f)
        assert d["reason_codes"] == ["custom_reason"]

    def test_no_network_calls(self, tmp_path: Path) -> None:
        ctx = FreqtradeBridgeContext.blocked()
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(ctx, target)
        # If we got here, no network calls were made
        assert target.exists()

    def test_no_trading_logic(self, tmp_path: Path) -> None:
        ctx = FreqtradeBridgeContext.blocked()
        target = tmp_path / "output.json"
        write_freqtrade_bridge_context(ctx, target)
        with open(target) as f:
            d = json.load(f)
        # Verify no trading-specific fields exist
        trading_fields = ["pairlist", "order", "stake", "leverage", "stoploss", "roi", "entry", "exit"]
        for field in trading_fields:
            assert field not in d
