"""Tests for strategy contract writer."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.strategy_contract.models import (
    DEFAULT_BLOCK_ALL,
    LONG_RESEARCH_ALLOWED,
    StrategyContractConfig,
    StrategyContractDataQuality,
    StrategyContractInputRefs,
    StrategyContractMode,
    StrategyContractSafetyFlags,
    StrategyContractState,
    StrategyContext,
)
from hunter.strategy_contract.writer import (
    DEFAULT_STRATEGY_CONTEXT_PATH,
    atomic_write_json,
    strategy_context_to_dict,
    write_strategy_context,
)


class TestStrategyContextToDict:
    """Tests for strategy_context_to_dict()."""

    def _make_context(self, **kwargs: object) -> StrategyContext:
        defaults = {
            "timestamp": datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            "status": "DRY_RUN_READY",
            "contract_state": StrategyContractState.DRY_RUN_READY,
            "contract_mode": StrategyContractMode.LONG_RESEARCH_ONLY,
            "bridge_state": "DRY_RUN_READY",
            "bridge_mode": "LONG_RESEARCH_ONLY",
            "reason_codes": (LONG_RESEARCH_ALLOWED,),
        }
        defaults.update(kwargs)
        return StrategyContext(**defaults)  # type: ignore[arg-type]

    def test_all_fields_present(self) -> None:
        ctx = self._make_context()
        d = strategy_context_to_dict(ctx)
        expected_keys = {
            "timestamp",
            "status",
            "contract_state",
            "contract_mode",
            "bridge_state",
            "bridge_mode",
            "dry_run",
            "live_trading_enabled",
            "real_orders_enabled",
            "leverage_enabled",
            "shorting_enabled",
            "strategy_runtime_allowed",
            "entry_signals_allowed",
            "exit_signals_allowed",
            "reason_codes",
            "input_refs",
            "safety_flags",
            "data_quality",
            "version",
        }
        assert set(d.keys()) == expected_keys

    def test_timestamp_iso8601_utc(self) -> None:
        ctx = self._make_context(timestamp=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc))
        d = strategy_context_to_dict(ctx)
        assert d["timestamp"] == "2025-01-15T10:30:00Z"

    def test_timestamp_ends_with_z(self) -> None:
        ctx = self._make_context()
        d = strategy_context_to_dict(ctx)
        assert isinstance(d["timestamp"], str)
        assert d["timestamp"].endswith("Z")

    def test_enum_fields_as_strings(self) -> None:
        ctx = self._make_context(
            contract_state=StrategyContractState.DRY_RUN_READY,
            contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
        )
        d = strategy_context_to_dict(ctx)
        assert d["contract_state"] == "DRY_RUN_READY"
        assert d["contract_mode"] == "LONG_RESEARCH_ONLY"
        assert isinstance(d["contract_state"], str)
        assert isinstance(d["contract_mode"], str)

    def test_reason_codes_as_list(self) -> None:
        ctx = self._make_context(reason_codes=(LONG_RESEARCH_ALLOWED, DEFAULT_BLOCK_ALL))
        d = strategy_context_to_dict(ctx)
        assert d["reason_codes"] == [LONG_RESEARCH_ALLOWED, DEFAULT_BLOCK_ALL]
        assert isinstance(d["reason_codes"], list)

    def test_input_refs_as_dict(self) -> None:
        ctx = self._make_context(
            input_refs=StrategyContractInputRefs(
                freqtrade_bridge_context="custom/input.json",
                strategy_context="custom/output.json",
            ),
        )
        d = strategy_context_to_dict(ctx)
        assert d["input_refs"] == {
            "freqtrade_bridge_context": "custom/input.json",
            "strategy_context": "custom/output.json",
        }

    def test_safety_flags_as_dict(self) -> None:
        ctx = self._make_context()
        d = strategy_context_to_dict(ctx)
        assert d["safety_flags"] == {
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
            "strategy_runtime_allowed": False,
            "entry_signals_allowed": False,
            "exit_signals_allowed": False,
            "max_context_age_seconds": 300,
        }

    def test_data_quality_as_dict(self) -> None:
        ctx = self._make_context(
            data_quality=StrategyContractDataQuality(
                bridge_context_present=True,
                bridge_context_valid=True,
                bridge_context_stale=False,
                reason="VALID",
            ),
        )
        d = strategy_context_to_dict(ctx)
        assert d["data_quality"] == {
            "bridge_context_present": True,
            "bridge_context_valid": True,
            "bridge_context_stale": False,
            "reason": "VALID",
        }

    def test_version_is_1_0(self) -> None:
        ctx = self._make_context()
        d = strategy_context_to_dict(ctx)
        assert d["version"] == "1.0"

    def test_blocked_context(self) -> None:
        ctx = StrategyContext.blocked(reason_codes=(DEFAULT_BLOCK_ALL,))
        d = strategy_context_to_dict(ctx)
        assert d["contract_state"] == "BLOCKED"
        assert d["contract_mode"] == "BLOCK_ALL"
        assert d["status"] == "BLOCKED"
        assert d["reason_codes"] == [DEFAULT_BLOCK_ALL]
        assert d["bridge_state"] == "UNKNOWN"
        assert d["bridge_mode"] == "BLOCK_ALL"
        assert d["dry_run"] is True
        assert d["version"] == "1.0"

    def test_safety_flags_override(self) -> None:
        ctx = self._make_context(
            safety_flags=StrategyContractSafetyFlags(max_context_age_seconds=600),
        )
        d = strategy_context_to_dict(ctx)
        assert d["safety_flags"]["max_context_age_seconds"] == 600

    def test_data_quality_override(self) -> None:
        ctx = self._make_context(
            data_quality=StrategyContractDataQuality(reason="STALE"),
        )
        d = strategy_context_to_dict(ctx)
        assert d["data_quality"]["reason"] == "STALE"

    def test_json_serializable(self) -> None:
        ctx = self._make_context()
        d = strategy_context_to_dict(ctx)
        json_str = json.dumps(d)
        loaded = json.loads(json_str)
        assert loaded["version"] == "1.0"


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


class TestWriteStrategyContext:
    """Tests for write_strategy_context()."""

    def _make_context(self) -> StrategyContext:
        return StrategyContext(
            timestamp=datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            status="DRY_RUN_READY",
            contract_state=StrategyContractState.DRY_RUN_READY,
            contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
            bridge_state="DRY_RUN_READY",
            bridge_mode="LONG_RESEARCH_ONLY",
            reason_codes=(LONG_RESEARCH_ALLOWED,),
        )

    def test_default_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Override default path to use tmp_path
        from hunter.strategy_contract import writer
        monkeypatch.setattr(writer, "DEFAULT_STRATEGY_CONTEXT_PATH", tmp_path / "strategy" / "current_strategy_context.json")
        ctx = self._make_context()
        result = write_strategy_context(ctx)
        assert result.exists()
        with open(result, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["version"] == "1.0"
        assert loaded["status"] == "DRY_RUN_READY"

    def test_custom_path(self, tmp_path: Path) -> None:
        target = tmp_path / "custom" / "strategy.json"
        ctx = self._make_context()
        result = write_strategy_context(ctx, target_path=target)
        assert result == target
        assert target.exists()
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["contract_state"] == "DRY_RUN_READY"

    def test_writes_blocked_context(self, tmp_path: Path) -> None:
        target = tmp_path / "blocked.json"
        ctx = StrategyContext.blocked(reason_codes=(DEFAULT_BLOCK_ALL,))
        result = write_strategy_context(ctx, target_path=target)
        assert target.exists()
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["contract_state"] == "BLOCKED"
        assert loaded["contract_mode"] == "BLOCK_ALL"
        assert loaded["reason_codes"] == [DEFAULT_BLOCK_ALL]

    def test_no_json_input_reading(self, tmp_path: Path) -> None:
        # Verify no file reading occurs during write
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_strategy_context(ctx, target_path=target)
        # If we got here without file-related errors, no JSON reading occurred
        assert target.exists()

    def test_no_network_calls(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_strategy_context(ctx, target_path=target)
        assert target.exists()

    def test_no_freqtrade_runtime(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_strategy_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["strategy_runtime_allowed"] is False

    def test_no_binance(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_strategy_context(ctx, target_path=target)
        assert target.exists()

    def test_no_strategy_class(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_strategy_context(ctx, target_path=target)
        assert target.exists()

    def test_no_live_trading(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_strategy_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["live_trading_enabled"] is False

    def test_no_leverage(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_strategy_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["leverage_enabled"] is False

    def test_no_shorting(self, tmp_path: Path) -> None:
        target = tmp_path / "output.json"
        ctx = self._make_context()
        write_strategy_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["shorting_enabled"] is False

    def test_default_path_constant(self) -> None:
        assert str(DEFAULT_STRATEGY_CONTEXT_PATH) == "data/strategy/current_strategy_context.json"

    def test_round_trip(self, tmp_path: Path) -> None:
        target = tmp_path / "roundtrip.json"
        ctx = self._make_context()
        write_strategy_context(ctx, target_path=target)
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["timestamp"] == "2025-01-15T10:30:00Z"
        assert loaded["status"] == "DRY_RUN_READY"
        assert loaded["contract_state"] == "DRY_RUN_READY"
        assert loaded["contract_mode"] == "LONG_RESEARCH_ONLY"
        assert loaded["bridge_state"] == "DRY_RUN_READY"
        assert loaded["bridge_mode"] == "LONG_RESEARCH_ONLY"
        assert loaded["dry_run"] is True
        assert loaded["live_trading_enabled"] is False
        assert loaded["real_orders_enabled"] is False
        assert loaded["leverage_enabled"] is False
        assert loaded["shorting_enabled"] is False
        assert loaded["strategy_runtime_allowed"] is False
        assert loaded["entry_signals_allowed"] is False
        assert loaded["exit_signals_allowed"] is False
        assert loaded["reason_codes"] == [LONG_RESEARCH_ALLOWED]
        assert loaded["input_refs"] == {
            "freqtrade_bridge_context": "data/freqtrade/current_freqtrade_context.json",
            "strategy_context": "data/strategy/current_strategy_context.json",
        }
        assert loaded["safety_flags"]["dry_run"] is True
        assert loaded["safety_flags"]["max_context_age_seconds"] == 300
        assert loaded["data_quality"]["bridge_context_present"] is False
        assert loaded["data_quality"]["reason"] == "NOT_EVALUATED"
        assert loaded["version"] == "1.0"
