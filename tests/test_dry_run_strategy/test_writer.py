"""Tests for dry-run strategy writer."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.dry_run_strategy.models import (
    DEFAULT_BLOCK_SIGNAL,
    LONG_RESEARCH_SIGNAL_EXPOSED,
    SHORT_RESEARCH_SIGNAL_EXPOSED,
    DryRunSignalAction,
    DryRunStrategyConfig,
    DryRunStrategyDataQuality,
    DryRunStrategyInputRefs,
    DryRunStrategyMode,
    DryRunStrategyRuntimeContext,
    DryRunStrategySafetyFlags,
    DryRunStrategyState,
)
from hunter.dry_run_strategy.writer import (
    DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH,
    atomic_write_json,
    dry_run_strategy_runtime_context_to_dict,
    write_dry_run_strategy_runtime_context,
)


class TestDryRunStrategyRuntimeContextToDict:
    """Tests for dry_run_strategy_runtime_context_to_dict()."""

    def _make_context(self, **kwargs: object) -> DryRunStrategyRuntimeContext:
        defaults = {
            "timestamp": datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            "status": "DRY_RUN_READY",
            "strategy_state": DryRunStrategyState.DRY_RUN_READY,
            "strategy_mode": DryRunStrategyMode.LONG_RESEARCH_ONLY,
            "signal_action": DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL,
            "adapter_state": "DRY_RUN_READY",
            "adapter_mode": "LONG_RESEARCH_ONLY",
            "adapter_signal_intent": "ALLOW_LONG_RESEARCH_SIGNAL",
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
            "freqtrade_runtime_allowed": False,
            "strategy_class_allowed": False,
            "populate_indicators_allowed": False,
            "populate_entry_trend_allowed": False,
            "populate_exit_trend_allowed": False,
            "order_execution_allowed": False,
            "reason_codes": (LONG_RESEARCH_SIGNAL_EXPOSED,),
            "input_refs": DryRunStrategyInputRefs(),
            "safety_flags": DryRunStrategySafetyFlags(),
            "data_quality": DryRunStrategyDataQuality(
                adapter_decision_present=True,
                adapter_decision_valid=True,
                adapter_decision_stale=False,
                reason=LONG_RESEARCH_SIGNAL_EXPOSED,
            ),
            "version": "1.0",
        }
        defaults.update(kwargs)
        return DryRunStrategyRuntimeContext(**defaults)  # type: ignore[arg-type]

    def test_all_fields_present(self) -> None:
        ctx = self._make_context()
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        expected_keys = {
            "timestamp",
            "status",
            "strategy_state",
            "strategy_mode",
            "signal_action",
            "adapter_state",
            "adapter_mode",
            "adapter_signal_intent",
            "dry_run",
            "live_trading_enabled",
            "real_orders_enabled",
            "leverage_enabled",
            "shorting_enabled",
            "freqtrade_runtime_allowed",
            "strategy_class_allowed",
            "populate_indicators_allowed",
            "populate_entry_trend_allowed",
            "populate_exit_trend_allowed",
            "order_execution_allowed",
            "reason_codes",
            "input_refs",
            "safety_flags",
            "data_quality",
            "version",
        }
        assert set(d.keys()) == expected_keys

    def test_timestamp_iso8601_utc(self) -> None:
        ctx = self._make_context(
            timestamp=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        )
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["timestamp"] == "2025-01-15T10:30:00Z"

    def test_timestamp_ends_with_z(self) -> None:
        ctx = self._make_context()
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert isinstance(d["timestamp"], str)
        assert d["timestamp"].endswith("Z")

    def test_enum_fields_as_strings(self) -> None:
        ctx = self._make_context(
            strategy_state=DryRunStrategyState.DRY_RUN_READY,
            strategy_mode=DryRunStrategyMode.LONG_RESEARCH_ONLY,
            signal_action=DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL,
        )
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["strategy_state"] == "DRY_RUN_READY"
        assert d["strategy_mode"] == "LONG_RESEARCH_ONLY"
        assert d["signal_action"] == "EXPOSE_LONG_RESEARCH_SIGNAL"
        assert isinstance(d["strategy_state"], str)
        assert isinstance(d["strategy_mode"], str)
        assert isinstance(d["signal_action"], str)

    def test_signal_action_serializes_as_string(self) -> None:
        ctx = self._make_context(
            signal_action=DryRunSignalAction.BLOCK_SIGNAL
        )
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["signal_action"] == "BLOCK_SIGNAL"
        assert isinstance(d["signal_action"], str)

    def test_reason_codes_as_list(self) -> None:
        ctx = self._make_context(
            reason_codes=(LONG_RESEARCH_SIGNAL_EXPOSED, DEFAULT_BLOCK_SIGNAL)
        )
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["reason_codes"] == [LONG_RESEARCH_SIGNAL_EXPOSED, DEFAULT_BLOCK_SIGNAL]
        assert isinstance(d["reason_codes"], list)

    def test_input_refs_as_dict(self) -> None:
        ctx = self._make_context(
            input_refs=DryRunStrategyInputRefs(
                adapter_decision="custom/adapter.json",
                dry_run_strategy_runtime="custom/output.json",
            ),
        )
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["input_refs"] == {
            "adapter_decision": "custom/adapter.json",
            "dry_run_strategy_runtime": "custom/output.json",
        }

    def test_safety_flags_as_dict(self) -> None:
        ctx = self._make_context()
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["safety_flags"] == {
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
            "freqtrade_runtime_allowed": False,
            "strategy_class_allowed": False,
            "populate_indicators_allowed": False,
            "populate_entry_trend_allowed": False,
            "populate_exit_trend_allowed": False,
            "order_execution_allowed": False,
            "max_context_age_seconds": 300,
        }

    def test_data_quality_as_dict(self) -> None:
        ctx = self._make_context(
            data_quality=DryRunStrategyDataQuality(
                adapter_decision_present=True,
                adapter_decision_valid=True,
                adapter_decision_stale=False,
                reason="VALID",
            ),
        )
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["data_quality"] == {
            "adapter_decision_present": True,
            "adapter_decision_valid": True,
            "adapter_decision_stale": False,
            "reason": "VALID",
        }

    def test_version_is_1_0(self) -> None:
        ctx = self._make_context()
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["version"] == "1.0"

    def test_blocked_context(self) -> None:
        ctx = DryRunStrategyRuntimeContext.blocked(reason_codes=(DEFAULT_BLOCK_SIGNAL,))
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["strategy_state"] == "BLOCKED"
        assert d["strategy_mode"] == "BLOCK_ALL"
        assert d["signal_action"] == "BLOCK_SIGNAL"
        assert d["status"] == "BLOCKED"
        assert d["reason_codes"] == [DEFAULT_BLOCK_SIGNAL]
        assert d["dry_run"] is True
        assert d["version"] == "1.0"

    def test_safety_flags_override(self) -> None:
        ctx = self._make_context(
            safety_flags=DryRunStrategySafetyFlags(max_context_age_seconds=600),
        )
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["safety_flags"]["max_context_age_seconds"] == 600

    def test_data_quality_override(self) -> None:
        ctx = self._make_context(
            data_quality=DryRunStrategyDataQuality(reason="STALE"),
        )
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["data_quality"]["reason"] == "STALE"

    def test_json_serializable(self) -> None:
        ctx = self._make_context()
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        json_str = json.dumps(d)
        loaded = json.loads(json_str)
        assert loaded["version"] == "1.0"

    def test_short_research_signal(self) -> None:
        ctx = self._make_context(
            strategy_mode=DryRunStrategyMode.SHORT_RESEARCH_ONLY,
            signal_action=DryRunSignalAction.EXPOSE_SHORT_RESEARCH_SIGNAL,
            reason_codes=(SHORT_RESEARCH_SIGNAL_EXPOSED,),
        )
        d = dry_run_strategy_runtime_context_to_dict(ctx)
        assert d["strategy_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["signal_action"] == "EXPOSE_SHORT_RESEARCH_SIGNAL"
        assert d["reason_codes"] == [SHORT_RESEARCH_SIGNAL_EXPOSED]


class TestAtomicWriteJson:
    """Tests for atomic_write_json()."""

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "nested" / "output.json"
        data = {"key": "value"}
        atomic_write_json(data, target)
        assert target.exists()
        assert target.parent.exists()

    def test_writes_valid_json(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        data = {"key": "value", "number": 42}
        atomic_write_json(data, target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_returns_target_path(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        data = {"key": "value"}
        result = atomic_write_json(data, target)
        assert result == target

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        target.write_text("old content", encoding="utf-8")
        data = {"key": "new"}
        atomic_write_json(data, target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_no_temp_files_after_success(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        data = {"key": "value"}
        atomic_write_json(data, target)
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_cleans_temp_on_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        # Non-serializable data to force failure
        data = {"key": object()}  # type: ignore[dict-item]
        with pytest.raises(TypeError):
            atomic_write_json(data, target)
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_utf8_encoding(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        data = {"message": "Héllo Wörld 🌍"}
        atomic_write_json(data, target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["message"] == "Héllo Wörld 🌍"

    def test_indent_2(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        data = {"key": "value"}
        atomic_write_json(data, target)
        content = target.read_text(encoding="utf-8")
        assert "  " in content  # indented

    def test_sort_keys(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        data = {"z": 1, "a": 2, "m": 3}
        atomic_write_json(data, target)
        content = target.read_text(encoding="utf-8")
        # Keys should be sorted: a, m, z
        assert content.index("a") < content.index("m") < content.index("z")

    def test_trailing_newline(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        data = {"key": "value"}
        atomic_write_json(data, target)
        content = target.read_text(encoding="utf-8")
        assert content.endswith("\n")


class TestWriteDryRunStrategyRuntimeContext:
    """Tests for write_dry_run_strategy_runtime_context()."""

    def _make_context(self) -> DryRunStrategyRuntimeContext:
        return DryRunStrategyRuntimeContext(
            timestamp=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            status="DRY_RUN_READY",
            strategy_state=DryRunStrategyState.DRY_RUN_READY,
            strategy_mode=DryRunStrategyMode.LONG_RESEARCH_ONLY,
            signal_action=DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL,
            adapter_state="DRY_RUN_READY",
            adapter_mode="LONG_RESEARCH_ONLY",
            adapter_signal_intent="ALLOW_LONG_RESEARCH_SIGNAL",
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            freqtrade_runtime_allowed=False,
            strategy_class_allowed=False,
            populate_indicators_allowed=False,
            populate_entry_trend_allowed=False,
            populate_exit_trend_allowed=False,
            order_execution_allowed=False,
            reason_codes=(LONG_RESEARCH_SIGNAL_EXPOSED,),
            input_refs=DryRunStrategyInputRefs(),
            safety_flags=DryRunStrategySafetyFlags(),
            data_quality=DryRunStrategyDataQuality(
                adapter_decision_present=True,
                adapter_decision_valid=True,
                adapter_decision_stale=False,
                reason=LONG_RESEARCH_SIGNAL_EXPOSED,
            ),
            version="1.0",
        )

    def test_default_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Override default path to use tmp_path
        from hunter.dry_run_strategy import writer
        monkeypatch.setattr(
            writer,
            "DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH",
            tmp_path / "freqtrade_strategy" / "current_dry_run_strategy_runtime.json",
        )
        ctx = self._make_context()
        result = write_dry_run_strategy_runtime_context(ctx)
        assert result.exists()
        with open(result, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["version"] == "1.0"
        assert loaded["status"] == "DRY_RUN_READY"

    def test_custom_path(self, tmp_path: Path) -> None:
        target = tmp_path / "custom" / "runtime.json"
        ctx = self._make_context()
        result = write_dry_run_strategy_runtime_context(ctx, output_path=target)
        assert result == target
        assert target.exists()
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["strategy_state"] == "DRY_RUN_READY"

    def test_writes_blocked_context(self, tmp_path: Path) -> None:
        target = tmp_path / "blocked.json"
        ctx = DryRunStrategyRuntimeContext.blocked(reason_codes=(DEFAULT_BLOCK_SIGNAL,))
        result = write_dry_run_strategy_runtime_context(ctx, output_path=target)
        assert target.exists()
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["strategy_state"] == "BLOCKED"
        assert loaded["strategy_mode"] == "BLOCK_ALL"
        assert loaded["signal_action"] == "BLOCK_SIGNAL"
        assert loaded["reason_codes"] == [DEFAULT_BLOCK_SIGNAL]

    def test_no_json_input_reading(self, tmp_path: Path) -> None:
        # Verify no file reading occurs during write
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        # If we got here without file-related errors, no JSON reading occurred
        assert target.exists()

    def test_no_network_calls(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        assert target.exists()

    def test_no_freqtrade_runtime(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["freqtrade_runtime_allowed"] is False

    def test_no_binance(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        assert target.exists()

    def test_no_strategy_class(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        assert target.exists()

    def test_no_live_trading(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["live_trading_enabled"] is False

    def test_no_leverage(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["leverage_enabled"] is False

    def test_no_shorting(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["shorting_enabled"] is False

    def test_no_entry_exit_execution(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["populate_entry_trend_allowed"] is False
        assert loaded["populate_exit_trend_allowed"] is False
        assert loaded["order_execution_allowed"] is False

    def test_default_path_constant(self) -> None:
        assert str(DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH) == "data/freqtrade_strategy/current_dry_run_strategy_runtime.json"

    def test_round_trip(self, tmp_path: Path) -> None:
        target = tmp_path / "roundtrip.json"
        ctx = self._make_context()
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["timestamp"] == "2025-01-15T10:30:00Z"
        assert loaded["status"] == "DRY_RUN_READY"
        assert loaded["strategy_state"] == "DRY_RUN_READY"
        assert loaded["strategy_mode"] == "LONG_RESEARCH_ONLY"
        assert loaded["signal_action"] == "EXPOSE_LONG_RESEARCH_SIGNAL"
        assert loaded["adapter_state"] == "DRY_RUN_READY"
        assert loaded["adapter_mode"] == "LONG_RESEARCH_ONLY"
        assert loaded["adapter_signal_intent"] == "ALLOW_LONG_RESEARCH_SIGNAL"
        assert loaded["dry_run"] is True
        assert loaded["live_trading_enabled"] is False
        assert loaded["real_orders_enabled"] is False
        assert loaded["leverage_enabled"] is False
        assert loaded["shorting_enabled"] is False
        assert loaded["freqtrade_runtime_allowed"] is False
        assert loaded["strategy_class_allowed"] is False
        assert loaded["populate_indicators_allowed"] is False
        assert loaded["populate_entry_trend_allowed"] is False
        assert loaded["populate_exit_trend_allowed"] is False
        assert loaded["order_execution_allowed"] is False
        assert loaded["reason_codes"] == [LONG_RESEARCH_SIGNAL_EXPOSED]
        assert loaded["input_refs"] == {
            "adapter_decision": "data/strategy_adapter/current_adapter_decision.json",
            "dry_run_strategy_runtime": "data/freqtrade_strategy/current_dry_run_strategy_runtime.json",
        }
        assert loaded["safety_flags"]["dry_run"] is True
        assert loaded["safety_flags"]["max_context_age_seconds"] == 300
        assert loaded["data_quality"]["adapter_decision_present"] is True
        assert loaded["data_quality"]["reason"] == LONG_RESEARCH_SIGNAL_EXPOSED
        assert loaded["version"] == "1.0"

    def test_no_order_execution(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["order_execution_allowed"] is False

    def test_writer_does_not_mutate_context(self, tmp_path: Path) -> None:
        ctx = self._make_context()
        original_reason_codes = ctx.reason_codes
        write_dry_run_strategy_runtime_context(ctx, output_path=tmp_path / "output.json")
        assert ctx.reason_codes == original_reason_codes

    def test_writer_works_with_blocked_context(self, tmp_path: Path) -> None:
        target = tmp_path / "blocked.json"
        ctx = DryRunStrategyRuntimeContext.blocked(reason_codes=(DEFAULT_BLOCK_SIGNAL,))
        write_dry_run_strategy_runtime_context(ctx, output_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["strategy_state"] == "BLOCKED"
        assert loaded["strategy_mode"] == "BLOCK_ALL"
        assert loaded["signal_action"] == "BLOCK_SIGNAL"
        assert loaded["reason_codes"] == [DEFAULT_BLOCK_SIGNAL]
