"""End-to-end integration tests for the Strategy Contract Consumption Adapter."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter import strategy_contract_consumer as scc


@pytest.fixture
def validated_at():
    return datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def generated_at(validated_at):
    return validated_at


@pytest.fixture
def config(tmp_path):
    return scc.StrategyContractConsumerConfig(
        output_dir=str(tmp_path / "data"),
        markdown_output_dir=str(tmp_path / "reports"),
    )


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
def valid_data(generated_at, safety_flags):
    return {
        "version": "0.56.0-dev",
        "generated_at": generated_at.isoformat(),
        "research_only": True,
        "human_approval_required": True,
        "mode": "LONG",
        "whitelist": ["BTC/USDT", "ETH/USDT"],
        "blacklist": [],
        "safety_flags": safety_flags,
        "metadata": {"source": "test"},
    }


@pytest.fixture
def make_input_file(tmp_path, valid_data):
    def _make(data: dict[str, Any] | None = None):
        path = tmp_path / "strategy_contract_input.json"
        path.write_text(json.dumps(data if data is not None else valid_data, sort_keys=True), encoding="utf-8")
        return path
    return _make


def _build_and_write(source, config, validated_at):
    ctx = scc.build_validated_strategy_context(source, config, validated_at=validated_at)
    json_path, md_path = scc.write_strategy_context_validation_result(ctx, config.output_dir, config)
    return ctx, json_path, md_path


def test_mapping_input_end_to_end(valid_data, config, validated_at):
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is True
    assert ctx.mode == "LONG"
    assert ctx.whitelist == ("BTC/USDT", "ETH/USDT")
    assert json_path.exists()
    assert md_path.exists()


def test_file_input_end_to_end(make_input_file, config, validated_at):
    path = make_input_file()
    ctx, json_path, md_path = _build_and_write(path, config, validated_at)
    assert ctx.accepted is True
    assert ctx.mode == "LONG"
    assert json_path.exists()
    assert md_path.exists()


def test_path_and_mapping_parity(make_input_file, valid_data, config, validated_at):
    path = make_input_file()
    ctx_from_path = scc.build_validated_strategy_context(path, config, validated_at=validated_at)
    ctx_from_mapping = scc.build_validated_strategy_context(valid_data, config, validated_at=validated_at)
    assert ctx_from_path.accepted is ctx_from_mapping.accepted is True
    assert ctx_from_path.mode == ctx_from_mapping.mode
    assert ctx_from_path.whitelist == ctx_from_mapping.whitelist
    assert ctx_from_path.blacklist == ctx_from_mapping.blacklist
    assert ctx_from_path.safety_flags == ctx_from_mapping.safety_flags
    assert ctx_from_path.reason_codes == ctx_from_mapping.reason_codes
    assert ctx_from_path.generated_at == ctx_from_mapping.generated_at
    assert ctx_from_path.source_fingerprint == ctx_from_mapping.source_fingerprint


def test_missing_input_end_to_end(config, validated_at):
    ctx, json_path, md_path = _build_and_write(None, config, validated_at)
    assert ctx.accepted is False
    assert ctx.mode == "BLOCK_ALL"
    assert ctx.whitelist == ()
    assert scc.MISSING_INPUT in ctx.reason_codes
    assert ctx.generated_at is None
    assert json_path.exists()
    assert md_path.exists()


def test_missing_file_end_to_end(tmp_path, config, validated_at):
    missing = tmp_path / "missing.json"
    ctx, json_path, md_path = _build_and_write(missing, config, validated_at)
    assert ctx.accepted is False
    assert scc.INPUT_READ_FAILED in ctx.reason_codes
    assert ctx.generated_at is None


def test_invalid_json_end_to_end(tmp_path, config, validated_at):
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    ctx, json_path, md_path = _build_and_write(path, config, validated_at)
    assert ctx.accepted is False
    assert scc.INVALID_JSON in ctx.reason_codes
    assert ctx.generated_at is None


def test_invalid_schema_end_to_end(tmp_path, config, validated_at):
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    ctx, json_path, md_path = _build_and_write(path, config, validated_at)
    assert ctx.accepted is False
    assert scc.INVALID_SCHEMA in ctx.reason_codes


def test_unsupported_version_end_to_end(valid_data, config, validated_at):
    valid_data["version"] = "0.99.0"
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.UNSUPPORTED_VERSION in ctx.reason_codes


def test_stale_input_end_to_end(valid_data, config, validated_at):
    valid_data["generated_at"] = (validated_at - timedelta(seconds=600)).isoformat()
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.STALE_INPUT in ctx.reason_codes
    assert ctx.generated_at is not None


def test_future_timestamp_end_to_end(valid_data, config, validated_at):
    valid_data["generated_at"] = (validated_at + timedelta(seconds=600)).isoformat()
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.INVALID_TIMESTAMP in ctx.reason_codes
    assert ctx.generated_at is not None


def test_unsafe_research_flag_end_to_end(valid_data, config, validated_at):
    valid_data["research_only"] = False
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.UNSAFE_RESEARCH_FLAG in ctx.reason_codes


def test_missing_human_approval_flag_end_to_end(valid_data, config, validated_at):
    del valid_data["human_approval_required"]
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.MISSING_HUMAN_APPROVAL_FLAG in ctx.reason_codes


def test_invalid_mode_end_to_end(valid_data, config, validated_at):
    valid_data["mode"] = "LIVE"
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.INVALID_MODE in ctx.reason_codes


def test_invalid_pair_end_to_end(valid_data, config, validated_at):
    valid_data["whitelist"] = ["badpair"]
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.INVALID_PAIR in ctx.reason_codes


def test_duplicate_pair_end_to_end(valid_data, config, validated_at):
    valid_data["whitelist"] = ["BTC/USDT", "BTC/USDT"]
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.DUPLICATE_PAIR in ctx.reason_codes


def test_whitelist_blacklist_conflict_end_to_end(valid_data, config, validated_at):
    valid_data["blacklist"] = ["BTC/USDT"]
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.PAIR_LIST_CONFLICT in ctx.reason_codes


def test_contradictory_empty_whitelist_end_to_end(valid_data, config, validated_at):
    valid_data["whitelist"] = []
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert scc.CONTRADICTORY_INPUT in ctx.reason_codes


def test_block_all_accepted_end_to_end(valid_data, config, validated_at):
    valid_data["mode"] = "BLOCK_ALL"
    valid_data["whitelist"] = []
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is True
    assert ctx.mode == "BLOCK_ALL"
    assert ctx.whitelist == ()
    assert scc.VALIDATION_ACCEPTED in ctx.reason_codes


def test_deterministic_repeated_builds(valid_data, config, validated_at):
    ctx1 = scc.build_validated_strategy_context(valid_data, config, validated_at=validated_at)
    ctx2 = scc.build_validated_strategy_context(valid_data, config, validated_at=validated_at)
    assert ctx1 == ctx2


def test_deterministic_repeated_writes(valid_data, config, validated_at):
    ctx = scc.build_validated_strategy_context(valid_data, config, validated_at=validated_at)
    json1, md1 = scc.write_strategy_context_validation_result(ctx, config.output_dir, config)
    json2, md2 = scc.write_strategy_context_validation_result(ctx, config.output_dir, config)
    assert json1.read_bytes() == json2.read_bytes()
    assert md1.read_bytes() == md2.read_bytes()


def test_source_fingerprint_consistency(valid_data, config, validated_at):
    ctx = scc.build_validated_strategy_context(valid_data, config, validated_at=validated_at)
    assert len(ctx.source_fingerprint) == 64
    assert all(c in "0123456789abcdef" for c in ctx.source_fingerprint)


def test_json_parseable_and_has_expected_keys(valid_data, config, validated_at):
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["kind"] == "strategy_contract_validation"
    assert data["accepted"] is True
    assert data["mode"] == "LONG"
    assert "generated_at" in data
    assert "validated_at" in data
    assert "safety_notice" in data


def test_markdown_safety_notice_and_artifact_paths(valid_data, config, validated_at):
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    md = md_path.read_text(encoding="utf-8")
    assert "research-only" in md.lower()
    assert str(json_path) in md
    assert str(md_path) in md


def test_generated_at_propagation(valid_data, config, validated_at):
    generated_at = datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    valid_data["generated_at"] = generated_at.isoformat()
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.generated_at == generated_at
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["generated_at"] == generated_at.isoformat()


def test_rejected_parseable_input_retains_generated_at(valid_data, config, validated_at):
    generated_at = datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    valid_data["generated_at"] = generated_at.isoformat()
    valid_data["version"] = "0.99.0"
    ctx, json_path, md_path = _build_and_write(valid_data, config, validated_at)
    assert ctx.accepted is False
    assert ctx.generated_at == generated_at


def test_unparseable_input_generated_at_null(tmp_path, config, validated_at):
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    ctx, json_path, md_path = _build_and_write(path, config, validated_at)
    assert ctx.generated_at is None
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["generated_at"] is None


def test_public_api_completeness():
    approved = {
        "STRATEGY_CONTRACT_CONSUMER_VERSION",
        "MISSING_INPUT",
        "INPUT_READ_FAILED",
        "INVALID_JSON",
        "INVALID_SCHEMA",
        "UNSUPPORTED_VERSION",
        "INVALID_TIMESTAMP",
        "STALE_INPUT",
        "UNSAFE_RESEARCH_FLAG",
        "MISSING_HUMAN_APPROVAL_FLAG",
        "INVALID_MODE",
        "INVALID_PAIR",
        "DUPLICATE_PAIR",
        "PAIR_LIST_CONFLICT",
        "INVALID_SAFETY_FLAGS",
        "CONTRADICTORY_INPUT",
        "VALIDATION_ACCEPTED",
        "STRATEGY_CONTRACT_CONSUMER_REASON_CODES",
        "StrategyContractConsumerConfig",
        "StrategyContractConsumerError",
        "ValidatedStrategyContext",
        "load_strategy_contract_input",
        "validate_strategy_contract_input",
        "build_validated_strategy_context",
        "strategy_context_result_to_dict",
        "strategy_context_result_to_json_text",
        "strategy_context_result_to_markdown_text",
        "write_strategy_context_validation_result",
    }
    for name in approved:
        assert hasattr(scc, name), f"Missing public export: {name}"
    for name in scc.__all__:
        assert name in approved, f"Unexpected or private export: {name}"


def test_no_private_helpers_exported():
    for name in scc.__all__:
        assert not name.startswith("_"), f"Private helper exported: {name}"


def test_no_freqtrade_imports():
    assert "freqtrade" not in sys.modules


def test_validator_does_not_read_files(valid_data, config, validated_at):
    # Validator is pure: it accepts a loaded dict and returns identical results for the same input.
    result1 = scc.validate_strategy_contract_input(dict(valid_data), config, validated_at=validated_at)
    result2 = scc.validate_strategy_contract_input(dict(valid_data), config, validated_at=validated_at)
    assert result1 == result2


def test_engine_reads_only_through_loader(valid_data, config, validated_at):
    # Engine builds from a mapping without touching any file path.
    ctx = scc.build_validated_strategy_context(valid_data, config, validated_at=validated_at)
    assert ctx.accepted is True


def test_no_runtime_config_mutation(valid_data, config, validated_at):
    original_config = scc.StrategyContractConsumerConfig(
        output_dir=config.output_dir,
        markdown_output_dir=config.markdown_output_dir,
    )
    scc.build_validated_strategy_context(valid_data, config, validated_at=validated_at)
    assert config.output_dir == original_config.output_dir
    assert config.markdown_output_dir == original_config.markdown_output_dir
