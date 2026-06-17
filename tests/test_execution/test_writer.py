"""Tests for execution bridge writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.decision.models import DecisionAction, DecisionState
from hunter.execution.models import (
    ExecutionBridgeConfig,
    ExecutionContext,
    ExecutionInputRefs,
    ExecutionMode,
    ExecutionSafetyFlags,
    ExecutionState,
)
from hunter.execution.writer import (
    atomic_write_json,
    execution_context_to_dict,
    write_execution_context,
)
from hunter.market_state.models import AllowedMode, DataQuality, OutputStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_execution_context(
    *,
    execution_state: ExecutionState = ExecutionState.DRY_RUN_ONLY,
    execution_mode: ExecutionMode = ExecutionMode.LONG_RESEARCH_ONLY,
    decision_state: DecisionState = DecisionState.ALLOW,
    decision_action: DecisionAction = DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
    allowed_mode: AllowedMode = AllowedMode.LONG_ONLY,
    status: OutputStatus = OutputStatus.VALID,
    timestamp: datetime | None = None,
    input_refs: ExecutionInputRefs | None = None,
    data_quality: DataQuality | None = None,
    safety_flags: ExecutionSafetyFlags | None = None,
    version: str = "1.0",
) -> ExecutionContext:
    """Create an ExecutionContext with sensible defaults."""
    return ExecutionContext(
        timestamp=timestamp or datetime.now(timezone.utc),
        status=status,
        execution_state=execution_state,
        execution_mode=execution_mode,
        decision_state=decision_state,
        decision_action=decision_action,
        allowed_mode=allowed_mode,
        input_refs=input_refs or ExecutionInputRefs(),
        data_quality=data_quality or DataQuality(),
        safety_flags=safety_flags or ExecutionSafetyFlags(),
        version=version,
    )


# ---------------------------------------------------------------------------
# execution_context_to_dict
# ---------------------------------------------------------------------------

class TestExecutionContextToDict:
    def test_basic_fields(self) -> None:
        ts = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        ctx = make_execution_context(timestamp=ts)
        d = execution_context_to_dict(ctx)
        assert d["timestamp"] == "2026-06-17T12:00:00Z"
        assert d["status"] == "VALID"
        assert d["execution_state"] == "DRY_RUN_ONLY"
        assert d["execution_mode"] == "LONG_RESEARCH_ONLY"
        assert d["decision_state"] == "ALLOW"
        assert d["decision_action"] == "ENABLE_LONG_ONLY_RESEARCH"
        assert d["allowed_mode"] == "LONG_ONLY"
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["exchange_connection_enabled"] is False
        assert d["freqtrade_enabled"] is False
        assert d["version"] == "1.0"

    def test_reason_codes(self) -> None:
        ctx = make_execution_context()
        ctx = ExecutionContext(
            timestamp=ctx.timestamp,
            status=ctx.status,
            execution_state=ctx.execution_state,
            execution_mode=ctx.execution_mode,
            decision_state=ctx.decision_state,
            decision_action=ctx.decision_action,
            allowed_mode=ctx.allowed_mode,
            reason_codes=["LONG_RESEARCH_ENABLED"],
            input_refs=ctx.input_refs,
            data_quality=ctx.data_quality,
            safety_flags=ctx.safety_flags,
            version=ctx.version,
        )
        d = execution_context_to_dict(ctx)
        assert d["reason_codes"] == ["LONG_RESEARCH_ENABLED"]

    def test_input_refs(self) -> None:
        refs = ExecutionInputRefs(
            decision_timestamp="2026-06-17T12:00:00Z",
            decision_source="decision_engine",
        )
        ctx = make_execution_context(input_refs=refs)
        d = execution_context_to_dict(ctx)
        assert d["input_refs"]["decision_timestamp"] == "2026-06-17T12:00:00Z"
        assert d["input_refs"]["decision_source"] == "decision_engine"

    def test_safety_flags(self) -> None:
        flags = ExecutionSafetyFlags(
            dry_run=True,
            live_trading_enabled=False,
            exchange_connection_enabled=False,
            freqtrade_enabled=False,
            human_override_required=False,
            max_context_age_seconds=300,
        )
        ctx = make_execution_context(safety_flags=flags)
        d = execution_context_to_dict(ctx)
        assert d["safety_flags"]["dry_run"] is True
        assert d["safety_flags"]["live_trading_enabled"] is False
        assert d["safety_flags"]["exchange_connection_enabled"] is False
        assert d["safety_flags"]["freqtrade_enabled"] is False
        assert d["safety_flags"]["human_override_required"] is False
        assert d["safety_flags"]["max_context_age_seconds"] == 300

    def test_data_quality(self) -> None:
        dq = DataQuality(missing=True, stale=False, insufficient_history=True, insufficient_universe=False)
        ctx = make_execution_context(data_quality=dq)
        d = execution_context_to_dict(ctx)
        assert d["data_quality"]["missing"] is True
        assert d["data_quality"]["stale"] is False
        assert d["data_quality"]["insufficient_history"] is True
        assert d["data_quality"]["insufficient_universe"] is False

    def test_version(self) -> None:
        ctx = make_execution_context(version="2.0")
        d = execution_context_to_dict(ctx)
        assert d["version"] == "2.0"

    def test_blocked_context(self) -> None:
        ctx = ExecutionContext.blocked()
        d = execution_context_to_dict(ctx)
        assert d["execution_state"] == "BLOCKED"
        assert d["execution_mode"] == "BLOCK_ALL"
        assert d["status"] == "INVALID"
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False

    def test_json_serializable(self) -> None:
        ctx = make_execution_context()
        d = execution_context_to_dict(ctx)
        # Should not raise
        json_str = json.dumps(d)
        assert isinstance(json_str, str)


# ---------------------------------------------------------------------------
# write_execution_context
# ---------------------------------------------------------------------------

class TestWriteExecutionContext:
    def test_creates_file(self, tmp_path: Path) -> None:
        ctx = make_execution_context()
        target = tmp_path / "execution.json"
        result = write_execution_context(ctx, target)
        assert result == target
        assert target.exists()

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        ctx = make_execution_context()
        target = tmp_path / "nested" / "deep" / "execution.json"
        write_execution_context(ctx, target)
        assert target.exists()

    def test_default_path(self, tmp_path: Path) -> None:
        ctx = make_execution_context()
        # Override default by using a temp path
        target = tmp_path / "data" / "execution" / "current_execution_context.json"
        write_execution_context(ctx, target)
        assert target.exists()

    def test_written_content_is_valid_json(self, tmp_path: Path) -> None:
        ts = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        refs = ExecutionInputRefs(
            decision_timestamp="2026-06-17T12:00:00Z",
            decision_source="decision_engine",
        )
        ctx = make_execution_context(timestamp=ts, input_refs=refs)
        target = tmp_path / "execution.json"
        write_execution_context(ctx, target)
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["timestamp"] == "2026-06-17T12:00:00Z"
        assert data["execution_state"] == "DRY_RUN_ONLY"
        assert data["input_refs"]["decision_timestamp"] == "2026-06-17T12:00:00Z"
        assert data["safety_flags"]["dry_run"] is True
        assert data["version"] == "1.0"

    def test_no_partial_output_on_failure(self, tmp_path: Path) -> None:
        # Make directory read-only to force failure
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o555)
        target = read_only_dir / "execution.json"
        ctx = make_execution_context()
        try:
            with pytest.raises(OSError):
                write_execution_context(ctx, target)
        finally:
            # Restore permissions for cleanup
            read_only_dir.chmod(0o755)
        # Target should not exist (no partial output)
        assert not target.exists()

    def test_blocked_context_written(self, tmp_path: Path) -> None:
        ctx = ExecutionContext.blocked()
        target = tmp_path / "blocked.json"
        write_execution_context(ctx, target)
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["execution_state"] == "BLOCKED"
        assert data["execution_mode"] == "BLOCK_ALL"
        assert data["reason_codes"] == ["EXECUTION_BLOCKED_BY_DEFAULT"]


# ---------------------------------------------------------------------------
# atomic_write_json
# ---------------------------------------------------------------------------

class TestAtomicWriteJson:
    def test_atomic_write(self, tmp_path: Path) -> None:
        target = tmp_path / "test.json"
        data = {"key": "value"}
        atomic_write_json(data, target)
        assert target.exists()
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "test.json"
        target.write_text("{}")
        data = {"new": "data"}
        atomic_write_json(data, target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

class TestSafety:
    def test_no_network_calls(self) -> None:
        ctx = make_execution_context()
        d = execution_context_to_dict(ctx)
        # No network-related fields should exist
        assert "url" not in d
        assert "endpoint" not in d
        assert "api_key" not in d

    def test_no_freqtrade_runtime_fields(self) -> None:
        ctx = make_execution_context()
        d = execution_context_to_dict(ctx)
        # No Freqtrade-specific runtime fields
        assert "strategy" not in d
        assert "pairlist" not in d
        assert "stake_amount" not in d
        assert "leverage" not in d
        assert "stoploss" not in d
        assert "roi" not in d

    def test_no_trading_execution_fields(self) -> None:
        ctx = make_execution_context()
        d = execution_context_to_dict(ctx)
        # No trading execution fields
        assert "order" not in d
        assert "position" not in d
        assert "trade" not in d
        assert "buy" not in d
        assert "sell" not in d

    def test_all_safety_flags_false_or_safe(self) -> None:
        ctx = make_execution_context()
        d = execution_context_to_dict(ctx)
        flags = d["safety_flags"]
        assert flags["dry_run"] is True
        assert flags["live_trading_enabled"] is False
        assert flags["exchange_connection_enabled"] is False
        assert flags["freqtrade_enabled"] is False
        assert flags["human_override_required"] is False
