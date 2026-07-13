"""Tests for the strategy_contract_consumer validator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
        "whitelist": ["BTC/USDT"],
        "blacklist": [],
        "safety_flags": safety_flags,
        "metadata": {"source": "test"},
    }


def _validate(data, config, validated_at):
    return scc.validate_strategy_contract_input(data, config, validated_at=validated_at)


def test_valid_input_is_accepted(valid_data, config, validated_at):
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is True
    assert result["mode"] == "LONG"
    assert result["whitelist"] == ("BTC/USDT",)
    assert result["blacklist"] == ()
    assert result["reason_codes"] == (scc.VALIDATION_ACCEPTED,)
    assert result["input_version"] == "0.56.0-dev"
    assert result["metadata"] == {"source": "test"}


def test_missing_input_returns_blocked(config, validated_at):
    result = _validate(None, config, validated_at)
    assert result["accepted"] is False
    assert result["mode"] == "BLOCK_ALL"
    assert result["whitelist"] == ()
    assert result["reason_codes"] == (scc.MISSING_INPUT,)


def test_missing_required_field_adds_invalid_schema(valid_data, config, validated_at):
    del valid_data["version"]
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.INVALID_SCHEMA in result["reason_codes"]


def test_unknown_top_level_field_adds_invalid_schema(valid_data, config, validated_at):
    valid_data["extra"] = True
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.INVALID_SCHEMA in result["reason_codes"]


def test_unsupported_version_adds_unsupported_version(valid_data, config, validated_at):
    valid_data["version"] = "0.99.0"
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.UNSUPPORTED_VERSION in result["reason_codes"]


def test_invalid_timestamp_adds_invalid_timestamp(valid_data, config, validated_at):
    valid_data["generated_at"] = "not-a-timestamp"
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.INVALID_TIMESTAMP in result["reason_codes"]


def test_naive_timestamp_adds_invalid_timestamp(valid_data, config, validated_at):
    valid_data["generated_at"] = "2026-07-13T12:00:00"
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.INVALID_TIMESTAMP in result["reason_codes"]


def test_stale_input_adds_stale_input(valid_data, config, validated_at):
    generated = validated_at - timedelta(seconds=400)
    valid_data["generated_at"] = generated.isoformat()
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.STALE_INPUT in result["reason_codes"]


def test_future_input_adds_invalid_timestamp(valid_data, config, validated_at):
    generated = validated_at + timedelta(seconds=120)
    valid_data["generated_at"] = generated.isoformat()
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.INVALID_TIMESTAMP in result["reason_codes"]


def test_false_research_only_adds_unsafe_research_flag(valid_data, config, validated_at):
    valid_data["research_only"] = False
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.UNSAFE_RESEARCH_FLAG in result["reason_codes"]


def test_missing_human_approval_flag_adds_missing_flag(valid_data, config, validated_at):
    valid_data["human_approval_required"] = False
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.MISSING_HUMAN_APPROVAL_FLAG in result["reason_codes"]


def test_invalid_mode_adds_invalid_mode(valid_data, config, validated_at):
    valid_data["mode"] = "LIVE"
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.INVALID_MODE in result["reason_codes"]
    assert result["mode"] == "BLOCK_ALL"


@pytest.mark.parametrize("mode", ["LONG", "SHORT"])
def test_long_and_short_modes_accepted(valid_data, config, validated_at, mode):
    valid_data["mode"] = mode
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is True
    assert result["mode"] == mode


def test_block_all_with_empty_whitelist_accepted(valid_data, config, validated_at):
    valid_data["mode"] = "BLOCK_ALL"
    valid_data["whitelist"] = []
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is True
    assert result["mode"] == "BLOCK_ALL"
    assert result["whitelist"] == ()


def test_invalid_pair_adds_invalid_pair(valid_data, config, validated_at):
    valid_data["whitelist"] = ["BTC"]
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.INVALID_PAIR in result["reason_codes"]


def test_pair_underscore_normalized(valid_data, config, validated_at):
    valid_data["whitelist"] = ["btc_usdt", "ETH/USDT"]
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is True
    assert result["whitelist"] == ("BTC/USDT", "ETH/USDT")


def test_duplicate_whitelist_pair_adds_duplicate_pair(valid_data, config, validated_at):
    valid_data["whitelist"] = ["BTC/USDT", "BTC/USDT"]
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.DUPLICATE_PAIR in result["reason_codes"]


def test_duplicate_blacklist_pair_adds_duplicate_pair(valid_data, config, validated_at):
    valid_data["blacklist"] = ["DOGE/USDT", "DOGE/USDT"]
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.DUPLICATE_PAIR in result["reason_codes"]


def test_whitelist_blacklist_conflict_adds_conflict(valid_data, config, validated_at):
    valid_data["whitelist"] = ["BTC/USDT", "ETH/USDT"]
    valid_data["blacklist"] = ["BTC/USDT"]
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.PAIR_LIST_CONFLICT in result["reason_codes"]
    assert "BTC/USDT" not in result["whitelist"]
    assert "BTC/USDT" in result["blacklist"]


def test_long_empty_whitelist_adds_contradictory_input(valid_data, config, validated_at):
    valid_data["whitelist"] = []
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.CONTRADICTORY_INPUT in result["reason_codes"]
    assert result["whitelist"] == ()


def test_short_empty_whitelist_adds_contradictory_input(valid_data, config, validated_at):
    valid_data["mode"] = "SHORT"
    valid_data["whitelist"] = []
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.CONTRADICTORY_INPUT in result["reason_codes"]


def test_block_all_nonempty_whitelist_adds_contradictory_input(valid_data, config, validated_at):
    valid_data["mode"] = "BLOCK_ALL"
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.CONTRADICTORY_INPUT in result["reason_codes"]
    assert result["whitelist"] == ()


def test_unknown_safety_flag_is_preserved_and_sorted(valid_data, config, validated_at):
    valid_data["safety_flags"]["unknown"] = False
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is True
    assert "unknown" in result["safety_flags"]
    assert list(result["safety_flags"].keys()) == sorted(result["safety_flags"].keys())


def test_unsafe_safety_flag_true_is_allowed(valid_data, config, validated_at):
    valid_data["safety_flags"]["live_trading_enabled"] = True
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is True
    assert result["safety_flags"]["live_trading_enabled"] is True


def test_dry_run_false_is_allowed(valid_data, config, validated_at):
    valid_data["safety_flags"]["dry_run"] = False
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is True


def test_missing_safety_flag_is_allowed(valid_data, config, validated_at):
    del valid_data["safety_flags"]["exit_signals_allowed"]
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is True


def test_safety_flag_non_bool_adds_invalid_safety_flags(valid_data, config, validated_at):
    valid_data["safety_flags"]["dry_run"] = "yes"
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.INVALID_SAFETY_FLAGS in result["reason_codes"]


def test_metadata_non_json_value_adds_invalid_schema(valid_data, config, validated_at):
    valid_data["metadata"] = {"a": object()}
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is False
    assert scc.INVALID_SCHEMA in result["reason_codes"]


def test_metadata_nested_values_are_preserved_and_copied(valid_data, config, validated_at):
    valid_data["metadata"] = {"nested": {"list": [1, True, None]}, "number": 42}
    result = _validate(valid_data, config, validated_at)
    assert result["accepted"] is True
    assert result["metadata"] == {"nested": {"list": [1, True, None]}, "number": 42}
    result["metadata"]["nested"]["list"].append("mutated")
    assert valid_data["metadata"]["nested"]["list"] == [1, True, None]


def test_reason_codes_are_sorted_and_unique(valid_data, config, validated_at):
    valid_data["version"] = "0.99.0"
    valid_data["mode"] = "LIVE"
    result = _validate(valid_data, config, validated_at)
    codes = result["reason_codes"]
    assert len(codes) == len(set(codes))
    assert list(codes) == sorted(codes)


def test_validated_at_must_be_timezone_aware(valid_data, config):
    with pytest.raises(scc.StrategyContractConsumerError) as exc_info:
        _validate(valid_data, config, datetime(2026, 7, 13, 12, 0, 0))
    assert exc_info.value.reason_code == scc.INVALID_TIMESTAMP


def test_validator_does_not_mutate_input(valid_data, config, validated_at):
    original = dict(valid_data)
    _validate(valid_data, config, validated_at)
    assert valid_data == original
