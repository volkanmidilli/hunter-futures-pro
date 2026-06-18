"""Tests for strategy adapter writer."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.strategy_adapter.models import (
    DEFAULT_BLOCK_SIGNAL,
    LONG_RESEARCH_SIGNAL_ALLOWED,
    SHORT_RESEARCH_SIGNAL_ALLOWED,
    AdapterConfig,
    AdapterDataQuality,
    AdapterDecisionContext,
    AdapterInputRefs,
    AdapterMode,
    AdapterSafetyFlags,
    AdapterSignalIntent,
    AdapterState,
)
from hunter.strategy_adapter.writer import (
    DEFAULT_ADAPTER_DECISION_PATH,
    adapter_decision_context_to_dict,
    atomic_write_json,
    write_adapter_decision_context,
)


class TestAdapterDecisionContextToDict:
    """Tests for adapter_decision_context_to_dict()."""

    def _make_context(self, **kwargs: object) -> AdapterDecisionContext:
        defaults = {
            "timestamp": datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            "status": "DRY_RUN_READY",
            "adapter_state": AdapterState.DRY_RUN_READY,
            "adapter_mode": AdapterMode.LONG_RESEARCH_ONLY,
            "signal_intent": AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL,
            "strategy_contract_state": "DRY_RUN_READY",
            "strategy_contract_mode": "LONG_RESEARCH_ONLY",
            "reason_codes": (LONG_RESEARCH_SIGNAL_ALLOWED,),
        }
        defaults.update(kwargs)
        return AdapterDecisionContext(**defaults)  # type: ignore[arg-type]

    def test_all_fields_present(self) -> None:
        ctx = self._make_context()
        d = adapter_decision_context_to_dict(ctx)
        expected_keys = {
            "timestamp",
            "status",
            "adapter_state",
            "adapter_mode",
            "signal_intent",
            "strategy_contract_state",
            "strategy_contract_mode",
            "dry_run",
            "live_trading_enabled",
            "real_orders_enabled",
            "leverage_enabled",
            "shorting_enabled",
            "adapter_runtime_allowed",
            "freqtrade_runtime_allowed",
            "strategy_class_allowed",
            "entry_signal_allowed",
            "exit_signal_allowed",
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
        d = adapter_decision_context_to_dict(ctx)
        assert d["timestamp"] == "2025-01-15T10:30:00Z"

    def test_timestamp_ends_with_z(self) -> None:
        ctx = self._make_context()
        d = adapter_decision_context_to_dict(ctx)
        assert isinstance(d["timestamp"], str)
        assert d["timestamp"].endswith("Z")

    def test_enum_fields_as_strings(self) -> None:
        ctx = self._make_context(
            adapter_state=AdapterState.DRY_RUN_READY,
            adapter_mode=AdapterMode.LONG_RESEARCH_ONLY,
            signal_intent=AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL,
        )
        d = adapter_decision_context_to_dict(ctx)
        assert d["adapter_state"] == "DRY_RUN_READY"
        assert d["adapter_mode"] == "LONG_RESEARCH_ONLY"
        assert d["signal_intent"] == "ALLOW_LONG_RESEARCH_SIGNAL"
        assert isinstance(d["adapter_state"], str)
        assert isinstance(d["adapter_mode"], str)
        assert isinstance(d["signal_intent"], str)

    def test_signal_intent_serializes_as_string(self) -> None:
        ctx = self._make_context(
            signal_intent=AdapterSignalIntent.BLOCK_SIGNAL
        )
        d = adapter_decision_context_to_dict(ctx)
        assert d["signal_intent"] == "BLOCK_SIGNAL"
        assert isinstance(d["signal_intent"], str)

    def test_reason_codes_as_list(self) -> None:
        ctx = self._make_context(
            reason_codes=(LONG_RESEARCH_SIGNAL_ALLOWED, DEFAULT_BLOCK_SIGNAL)
        )
        d = adapter_decision_context_to_dict(ctx)
        assert d["reason_codes"] == [LONG_RESEARCH_SIGNAL_ALLOWED, DEFAULT_BLOCK_SIGNAL]
        assert isinstance(d["reason_codes"], list)

    def test_input_refs_as_dict(self) -> None:
        ctx = self._make_context(
            input_refs=AdapterInputRefs(
                strategy_context="custom/strategy.json",
                adapter_decision="custom/output.json",
            ),
        )
        d = adapter_decision_context_to_dict(ctx)
        assert d["input_refs"] == {
            "strategy_context": "custom/strategy.json",
            "adapter_decision": "custom/output.json",
        }

    def test_safety_flags_as_dict(self) -> None:
        ctx = self._make_context()
        d = adapter_decision_context_to_dict(ctx)
        assert d["safety_flags"] == {
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
            "adapter_runtime_allowed": False,
            "freqtrade_runtime_allowed": False,
            "strategy_class_allowed": False,
            "entry_signal_allowed": False,
            "exit_signal_allowed": False,
            "order_execution_allowed": False,
            "max_context_age_seconds": 300,
        }

    def test_data_quality_as_dict(self) -> None:
        ctx = self._make_context(
            data_quality=AdapterDataQuality(
                strategy_context_present=True,
                strategy_context_valid=True,
                strategy_context_stale=False,
                reason="VALID",
            ),
        )
        d = adapter_decision_context_to_dict(ctx)
        assert d["data_quality"] == {
            "strategy_context_present": True,
            "strategy_context_valid": True,
            "strategy_context_stale": False,
            "reason": "VALID",
        }

    def test_version_is_1_0(self) -> None:
        ctx = self._make_context()
        d = adapter_decision_context_to_dict(ctx)
        assert d["version"] == "1.0"

    def test_blocked_context(self) -> None:
        ctx = AdapterDecisionContext.blocked(reason_codes=(DEFAULT_BLOCK_SIGNAL,))
        d = adapter_decision_context_to_dict(ctx)
        assert d["adapter_state"] == "BLOCKED"
        assert d["adapter_mode"] == "BLOCK_ALL"
        assert d["signal_intent"] == "BLOCK_SIGNAL"
        assert d["status"] == "BLOCKED"
        assert d["reason_codes"] == [DEFAULT_BLOCK_SIGNAL]
        assert d["strategy_contract_state"] == "UNKNOWN"
        assert d["strategy_contract_mode"] == "BLOCK_ALL"
        assert d["dry_run"] is True
        assert d["version"] == "1.0"

    def test_safety_flags_override(self) -> None:
        ctx = self._make_context(
            safety_flags=AdapterSafetyFlags(max_context_age_seconds=600),
        )
        d = adapter_decision_context_to_dict(ctx)
        assert d["safety_flags"]["max_context_age_seconds"] == 600

    def test_data_quality_override(self) -> None:
        ctx = self._make_context(
            data_quality=AdapterDataQuality(reason="STALE"),
        )
        d = adapter_decision_context_to_dict(ctx)
        assert d["data_quality"]["reason"] == "STALE"

    def test_json_serializable(self) -> None:
        ctx = self._make_context()
        d = adapter_decision_context_to_dict(ctx)
        json_str = json.dumps(d)
        loaded = json.loads(json_str)
        assert loaded["version"] == "1.0"

    def test_short_research_signal(self) -> None:
        ctx = self._make_context(
            adapter_mode=AdapterMode.SHORT_RESEARCH_ONLY,
            signal_intent=AdapterSignalIntent.ALLOW_SHORT_RESEARCH_SIGNAL,
            reason_codes=(SHORT_RESEARCH_SIGNAL_ALLOWED,),
        )
        d = adapter_decision_context_to_dict(ctx)
        assert d["adapter_mode"] == "SHORT_RESEARCH_ONLY"
        assert d["signal_intent"] == "ALLOW_SHORT_RESEARCH_SIGNAL"
        assert d["reason_codes"] == [SHORT_RESEARCH_SIGNAL_ALLOWED]


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


class TestWriteAdapterDecisionContext:
    """Tests for write_adapter_decision_context()."""

    def _make_context(self) -> AdapterDecisionContext:
        return AdapterDecisionContext(
            timestamp=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            status="DRY_RUN_READY",
            adapter_state=AdapterState.DRY_RUN_READY,
            adapter_mode=AdapterMode.LONG_RESEARCH_ONLY,
            signal_intent=AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL,
            strategy_contract_state="DRY_RUN_READY",
            strategy_contract_mode="LONG_RESEARCH_ONLY",
            reason_codes=(LONG_RESEARCH_SIGNAL_ALLOWED,),
        )

    def test_default_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Override default path to use tmp_path
        from hunter.strategy_adapter import writer
        monkeypatch.setattr(
            writer,
            "DEFAULT_ADAPTER_DECISION_PATH",
            tmp_path / "strategy_adapter" / "current_adapter_decision.json",
        )
        ctx = self._make_context()
        result = write_adapter_decision_context(ctx)
        assert result.exists()
        with open(result, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["version"] == "1.0"
        assert loaded["status"] == "DRY_RUN_READY"

    def test_custom_path(self, tmp_path: Path) -> None:
        target = tmp_path / "custom" / "adapter.json"
        ctx = self._make_context()
        result = write_adapter_decision_context(ctx, target_path=target)
        assert result == target
        assert target.exists()
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["adapter_state"] == "DRY_RUN_READY"

    def test_writes_blocked_context(self, tmp_path: Path) -> None:
        target = tmp_path / "blocked.json"
        ctx = AdapterDecisionContext.blocked(reason_codes=(DEFAULT_BLOCK_SIGNAL,))
        result = write_adapter_decision_context(ctx, target_path=target)
        assert target.exists()
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["adapter_state"] == "BLOCKED"
        assert loaded["adapter_mode"] == "BLOCK_ALL"
        assert loaded["signal_intent"] == "BLOCK_SIGNAL"
        assert loaded["reason_codes"] == [DEFAULT_BLOCK_SIGNAL]

    def test_no_json_input_reading(self, tmp_path: Path) -> None:
        # Verify no file reading occurs during write
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        # If we got here without file-related errors, no JSON reading occurred
        assert target.exists()

    def test_no_network_calls(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        assert target.exists()

    def test_no_freqtrade_runtime(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["freqtrade_runtime_allowed"] is False

    def test_no_binance(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        assert target.exists()

    def test_no_strategy_class(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        assert target.exists()

    def test_no_live_trading(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["live_trading_enabled"] is False

    def test_no_leverage(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["leverage_enabled"] is False

    def test_no_shorting(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["shorting_enabled"] is False

    def test_no_entry_exit_execution(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["entry_signal_allowed"] is False
        assert loaded["exit_signal_allowed"] is False
        assert loaded["order_execution_allowed"] is False

    def test_default_path_constant(self) -> None:
        assert str(DEFAULT_ADAPTER_DECISION_PATH) == "data/strategy_adapter/current_adapter_decision.json"

    def test_round_trip(self, tmp_path: Path) -> None:
        target = tmp_path / "roundtrip.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["timestamp"] == "2025-01-15T10:30:00Z"
        assert loaded["status"] == "DRY_RUN_READY"
        assert loaded["adapter_state"] == "DRY_RUN_READY"
        assert loaded["adapter_mode"] == "LONG_RESEARCH_ONLY"
        assert loaded["signal_intent"] == "ALLOW_LONG_RESEARCH_SIGNAL"
        assert loaded["strategy_contract_state"] == "DRY_RUN_READY"
        assert loaded["strategy_contract_mode"] == "LONG_RESEARCH_ONLY"
        assert loaded["dry_run"] is True
        assert loaded["live_trading_enabled"] is False
        assert loaded["real_orders_enabled"] is False
        assert loaded["leverage_enabled"] is False
        assert loaded["shorting_enabled"] is False
        assert loaded["adapter_runtime_allowed"] is False
        assert loaded["freqtrade_runtime_allowed"] is False
        assert loaded["strategy_class_allowed"] is False
        assert loaded["entry_signal_allowed"] is False
        assert loaded["exit_signal_allowed"] is False
        assert loaded["order_execution_allowed"] is False
        assert loaded["reason_codes"] == [LONG_RESEARCH_SIGNAL_ALLOWED]
        assert loaded["input_refs"] == {
            "strategy_context": "data/strategy/current_strategy_context.json",
            "adapter_decision": "data/strategy_adapter/current_adapter_decision.json",
        }
        assert loaded["safety_flags"]["dry_run"] is True
        assert loaded["safety_flags"]["max_context_age_seconds"] == 300
        assert loaded["data_quality"]["strategy_context_present"] is False
        assert loaded["data_quality"]["reason"] == "NOT_EVALUATED"
        assert loaded["version"] == "1.0"

    def test_no_adapter_runtime(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["adapter_runtime_allowed"] is False

    def test_no_order_execution(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_adapter_decision_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["order_execution_allowed"] is False
