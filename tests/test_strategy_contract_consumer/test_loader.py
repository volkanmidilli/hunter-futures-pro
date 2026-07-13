"""Tests for the strategy_contract_consumer loader."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from hunter import strategy_contract_consumer as scc


def test_load_none_returns_none():
    assert scc.load_strategy_contract_input(None) is None


def test_load_none_with_config_returns_none():
    assert scc.load_strategy_contract_input(None, config=scc.StrategyContractConsumerConfig()) is None


def test_load_path_reads_valid_json(tmp_path):
    data = {"version": "0.56.0-dev", "mode": "LONG"}
    path = tmp_path / "strategy_contract_input.json"
    path.write_text('{"version":"0.56.0-dev","mode":"LONG"}', encoding="utf-8")
    result = scc.load_strategy_contract_input(path)
    assert result == data


def test_load_str_path_reads_valid_json(tmp_path):
    path = tmp_path / "strategy_contract_input.json"
    path.write_text('{"version":"0.56.0-dev","mode":"SHORT"}', encoding="utf-8")
    result = scc.load_strategy_contract_input(str(path))
    assert result == {"version": "0.56.0-dev", "mode": "SHORT"}


def test_load_mapping_returns_copy():
    source = {"version": "0.56.0-dev", "mode": "BLOCK_ALL"}
    result = scc.load_strategy_contract_input(source)
    assert result == source
    assert result is not source


def test_load_mapping_is_deep_copy():
    source = {"version": "0.56.0-dev", "safety_flags": {"dry_run": True}}
    result = scc.load_strategy_contract_input(source)
    result["safety_flags"]["dry_run"] = False
    assert source["safety_flags"]["dry_run"] is True


def test_load_mapping_does_not_mutate_source():
    source = {"version": "0.56.0-dev", "metadata": {"a": "1"}}
    original = copy.deepcopy(source)
    scc.load_strategy_contract_input(source)
    assert source == original


def test_load_missing_path_raises_input_read_failed(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(scc.StrategyContractConsumerError) as exc_info:
        scc.load_strategy_contract_input(missing)
    assert exc_info.value.reason_code == scc.INPUT_READ_FAILED


def test_load_missing_str_path_raises_input_read_failed(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(scc.StrategyContractConsumerError) as exc_info:
        scc.load_strategy_contract_input(str(missing))
    assert exc_info.value.reason_code == scc.INPUT_READ_FAILED


def test_load_invalid_json_raises_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(scc.StrategyContractConsumerError) as exc_info:
        scc.load_strategy_contract_input(path)
    assert exc_info.value.reason_code == scc.INVALID_JSON


def test_load_non_object_top_level_raises_invalid_schema(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(scc.StrategyContractConsumerError) as exc_info:
        scc.load_strategy_contract_input(path)
    assert exc_info.value.reason_code == scc.INVALID_SCHEMA


def test_load_top_level_string_raises_invalid_schema(tmp_path):
    path = tmp_path / "string.json"
    path.write_text('"hello"', encoding="utf-8")
    with pytest.raises(scc.StrategyContractConsumerError) as exc_info:
        scc.load_strategy_contract_input(path)
    assert exc_info.value.reason_code == scc.INVALID_SCHEMA


def test_load_top_level_number_raises_invalid_schema(tmp_path):
    path = tmp_path / "number.json"
    path.write_text("123", encoding="utf-8")
    with pytest.raises(scc.StrategyContractConsumerError) as exc_info:
        scc.load_strategy_contract_input(path)
    assert exc_info.value.reason_code == scc.INVALID_SCHEMA


def test_load_mapping_with_non_object_raises_invalid_schema():
    with pytest.raises(scc.StrategyContractConsumerError) as exc_info:
        scc.load_strategy_contract_input([1, 2, 3])
    assert exc_info.value.reason_code == scc.INVALID_SCHEMA
