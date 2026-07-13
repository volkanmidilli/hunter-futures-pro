"""Tests for the strategy_contract_consumer engine."""

from __future__ import annotations

import dataclasses
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter import strategy_contract_consumer as scc


@pytest.fixture
def config():
    return scc.StrategyContractConsumerConfig()


@pytest.fixture
def validated_at():
    return datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def safety_flags():
    return {
        "dry_run": True,
        "live_trading_enabled": False,
        "real_orders_enabled": False,
        "leverage_enabled": False,
        "shorting_enabled": False,
        "strategy_runtime_allowed": False,
        "entry_signals_allowed": False,
        "exit_signals_allowed": False,
    }


@pytest.fixture
def valid_data(validated_at, safety_flags):
    return {
        "version": "0.56.0-dev",
        "generated_at": validated_at.isoformat(),
        "research_only": True,
        "human_approval_required": True,
        "mode": "LONG",
        "whitelist": ["BTC/USDT", "ETH/USDT"],
        "blacklist": [],
        "safety_flags": safety_flags,
        "metadata": {"source": "test"},
    }


@pytest.fixture
def make_valid_file(tmp_path, valid_data):
    def _make():
        path = tmp_path / "strategy_contract_input.json"
        import json

        path.write_text(json.dumps(valid_data, sort_keys=True), encoding="utf-8")
        return path

    return _make


def _build(source, config, validated_at):
    return scc.build_validated_strategy_context(source, config, validated_at=validated_at)


def test_valid_mapping_accepted(valid_data, config, validated_at):
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is True
    assert ctx.mode == "LONG"
    assert ctx.whitelist == ("BTC/USDT", "ETH/USDT")
    assert ctx.research_only is True
    assert ctx.human_approval_required is True
    assert scc.VALIDATION_ACCEPTED in ctx.reason_codes


def test_valid_file_accepted(make_valid_file, config, validated_at):
    path = make_valid_file()
    ctx = _build(path, config, validated_at)
    assert ctx.accepted is True
    assert ctx.mode == "LONG"
    assert ctx.whitelist == ("BTC/USDT", "ETH/USDT")


def test_path_and_mapping_parity(make_valid_file, valid_data, config, validated_at):
    path = make_valid_file()
    ctx_from_path = _build(path, config, validated_at)
    ctx_from_mapping = _build(valid_data, config, validated_at)
    # Canonicalize source paths for comparison.
    ctx_from_mapping_same_path = dataclasses.replace(
        ctx_from_mapping, source_path=ctx_from_path.source_path
    )
    assert ctx_from_path == ctx_from_mapping_same_path


def test_missing_input_rejected(config, validated_at):
    ctx = _build(None, config, validated_at)
    assert ctx.accepted is False
    assert ctx.mode == "BLOCK_ALL"
    assert ctx.whitelist == ()
    assert scc.MISSING_INPUT in ctx.reason_codes
    assert scc.VALIDATION_ACCEPTED not in ctx.reason_codes
    assert ctx.source_path == "<missing>"


def test_missing_path_rejected(tmp_path, config, validated_at):
    missing = tmp_path / "does_not_exist.json"
    ctx = _build(missing, config, validated_at)
    assert ctx.accepted is False
    assert scc.INPUT_READ_FAILED in ctx.reason_codes
    assert scc.VALIDATION_ACCEPTED not in ctx.reason_codes


def test_invalid_json_rejected(tmp_path, config, validated_at):
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    ctx = _build(path, config, validated_at)
    assert ctx.accepted is False
    assert scc.INVALID_JSON in ctx.reason_codes


def test_invalid_schema_rejected(tmp_path, config, validated_at):
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    ctx = _build(path, config, validated_at)
    assert ctx.accepted is False
    assert scc.INVALID_SCHEMA in ctx.reason_codes


def test_unsupported_version_rejected(valid_data, config, validated_at):
    valid_data["version"] = "9.9.9"
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.UNSUPPORTED_VERSION in ctx.reason_codes


def test_stale_timestamp_rejected(valid_data, config, validated_at):
    old = validated_at - timedelta(seconds=400)
    valid_data["generated_at"] = old.isoformat()
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.STALE_INPUT in ctx.reason_codes


def test_future_timestamp_rejected(valid_data, config, validated_at):
    future = validated_at + timedelta(seconds=120)
    valid_data["generated_at"] = future.isoformat()
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.INVALID_TIMESTAMP in ctx.reason_codes


def test_unsafe_research_flag_rejected(valid_data, config, validated_at):
    valid_data["research_only"] = False
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.UNSAFE_RESEARCH_FLAG in ctx.reason_codes


def test_missing_human_approval_flag_rejected(valid_data, config, validated_at):
    valid_data["human_approval_required"] = False
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.MISSING_HUMAN_APPROVAL_FLAG in ctx.reason_codes


def test_invalid_mode_rejected(valid_data, config, validated_at):
    valid_data["mode"] = "LIVE"
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.INVALID_MODE in ctx.reason_codes


def test_invalid_pair_rejected(valid_data, config, validated_at):
    valid_data["whitelist"] = ["BTC"]
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.INVALID_PAIR in ctx.reason_codes


def test_duplicate_pair_rejected(valid_data, config, validated_at):
    valid_data["whitelist"] = ["BTC/USDT", "BTC/USDT"]
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.DUPLICATE_PAIR in ctx.reason_codes


def test_whitelist_blacklist_conflict_rejected(valid_data, config, validated_at):
    valid_data["whitelist"] = ["BTC/USDT"]
    valid_data["blacklist"] = ["BTC/USDT"]
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.PAIR_LIST_CONFLICT in ctx.reason_codes


def test_contradictory_empty_whitelist_rejected(valid_data, config, validated_at):
    valid_data["whitelist"] = []
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.CONTRADICTORY_INPUT in ctx.reason_codes


def test_block_all_accepted(valid_data, config, validated_at):
    valid_data["mode"] = "BLOCK_ALL"
    valid_data["whitelist"] = []
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is True
    assert ctx.mode == "BLOCK_ALL"
    assert ctx.whitelist == ()
    assert scc.VALIDATION_ACCEPTED in ctx.reason_codes


def test_fingerprint_is_deterministic(valid_data, config, validated_at):
    ctx1 = _build(valid_data, config, validated_at)
    ctx2 = _build(valid_data, config, validated_at)
    assert ctx1.source_fingerprint == ctx2.source_fingerprint
    assert len(ctx1.source_fingerprint) == 64
    assert all(c in "0123456789abcdef" for c in ctx1.source_fingerprint)


def test_result_is_deterministic(valid_data, config, validated_at):
    ctx1 = _build(valid_data, config, validated_at)
    ctx2 = _build(valid_data, config, validated_at)
    assert ctx1 == ctx2


def test_result_is_immutable(valid_data, config, validated_at):
    ctx = _build(valid_data, config, validated_at)
    with pytest.raises(AttributeError):
        ctx.accepted = False


def test_loader_exception_converts_to_rejected_context(tmp_path, config, validated_at):
    missing = tmp_path / "missing.json"
    ctx = _build(missing, config, validated_at)
    assert ctx.accepted is False
    assert scc.INPUT_READ_FAILED in ctx.reason_codes
    assert scc.VALIDATION_ACCEPTED not in ctx.reason_codes


def test_no_file_writes(tmp_path, valid_data, config, validated_at):
    output_dir = tmp_path / "output"
    cfg = scc.StrategyContractConsumerConfig(output_dir=str(output_dir))
    _build(valid_data, cfg, validated_at)
    assert not output_dir.exists()


def test_no_freqtrade_runtime_imported():
    assert "freqtrade" not in sys.modules


def test_source_path_for_mapping(valid_data, config, validated_at):
    ctx = _build(valid_data, config, validated_at)
    assert ctx.source_path == "<mapping>"


def test_loader_failure_fingerprint_is_deterministic(tmp_path, config, validated_at):
    """Same missing path must produce the same fingerprint."""
    missing = tmp_path / "does_not_exist.json"
    ctx1 = _build(missing, config, validated_at)
    ctx2 = _build(missing, config, validated_at)
    assert ctx1.source_fingerprint == ctx2.source_fingerprint
    assert len(ctx1.source_fingerprint) == 64


def test_loader_failure_fingerprints_differ_by_path(tmp_path, config, validated_at):
    """Different missing paths must produce different fingerprints."""
    missing_a = tmp_path / "a.json"
    missing_b = tmp_path / "b.json"
    ctx_a = _build(missing_a, config, validated_at)
    ctx_b = _build(missing_b, config, validated_at)
    assert ctx_a.source_fingerprint != ctx_b.source_fingerprint


def test_loader_failure_fingerprints_differ_by_reason(tmp_path, config, validated_at):
    """Same path with different failure reasons must produce different fingerprints."""
    path = tmp_path / "ambiguous.json"
    path.write_text("not json", encoding="utf-8")
    ctx_bad_json = _build(path, config, validated_at)
    assert scc.INVALID_JSON in ctx_bad_json.reason_codes

    path.unlink()
    ctx_missing = _build(path, config, validated_at)
    assert scc.INPUT_READ_FAILED in ctx_missing.reason_codes

    assert ctx_bad_json.source_fingerprint != ctx_missing.source_fingerprint


def test_missing_input_fingerprint_is_deterministic(config, validated_at):
    ctx1 = _build(None, config, validated_at)
    ctx2 = _build(None, config, validated_at)
    assert ctx1.source_fingerprint == ctx2.source_fingerprint
    assert len(ctx1.source_fingerprint) == 64


def test_multiple_reason_codes_sorted_and_no_validation_accepted(valid_data, config, validated_at):
    valid_data["version"] = "9.9.9"
    valid_data["research_only"] = False
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.VALIDATION_ACCEPTED not in ctx.reason_codes
    assert ctx.reason_codes == tuple(sorted(ctx.reason_codes))


def test_generated_at_propagated_for_accepted(valid_data, config, validated_at):
    ctx = _build(valid_data, config, validated_at)
    assert ctx.generated_at == validated_at


def test_generated_at_propagated_for_rejected_stale(valid_data, config, validated_at):
    from datetime import datetime, timedelta
    generated_at = datetime(2026, 7, 13, 11, 0, 0, tzinfo=timezone.utc)
    valid_data["generated_at"] = generated_at.isoformat()
    ctx = _build(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert ctx.generated_at == generated_at


def test_generated_at_is_none_for_missing_input(config, validated_at):
    ctx = _build(None, config, validated_at)
    assert ctx.generated_at is None


def test_generated_at_is_none_for_invalid_json(tmp_path, config, validated_at):
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    ctx = _build(path, config, validated_at)
    assert ctx.generated_at is None


def test_no_freqtrade_runtime_imported():
    assert "freqtrade" not in sys.modules
