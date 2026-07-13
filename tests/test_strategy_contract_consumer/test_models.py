"""Tests for strategy_contract_consumer models and public API exports."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter import strategy_contract_consumer as scc


def test_version_constant_is_semantic_dev():
    assert scc.STRATEGY_CONTRACT_CONSUMER_VERSION == "0.56.0-dev"


def test_reason_codes_are_unique_strings():
    codes = scc.STRATEGY_CONTRACT_CONSUMER_REASON_CODES
    assert all(isinstance(c, str) for c in codes)
    assert len(codes) == len(set(codes))
    assert "MISSING_INPUT" in codes
    assert "VALIDATION_ACCEPTED" in codes


def test_reason_codes_match_spec_approved_list():
    expected = {
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
    }
    assert scc.STRATEGY_CONTRACT_CONSUMER_REASON_CODES == expected


def test_strategy_contract_consumer_error_carries_reason_code():
    err = scc.StrategyContractConsumerError("boom", reason_code="INVALID_JSON")
    assert str(err) == "boom"
    assert err.reason_code == "INVALID_JSON"


def test_strategy_contract_consumer_error_default_reason_code():
    err = scc.StrategyContractConsumerError("boom")
    assert err.reason_code is None


def test_config_defaults():
    cfg = scc.StrategyContractConsumerConfig()
    assert cfg.output_dir == "data/strategy_contract_validation"
    assert cfg.markdown_output_dir == "reports/strategy_contract_validation"
    assert cfg.json_filename == "latest_validation.json"
    assert cfg.markdown_filename == "latest_validation.md"
    assert cfg.stale_input_threshold_seconds == 300
    assert cfg.future_input_tolerance_seconds == 60
    assert "0.56.0-dev" in cfg.supported_versions


def test_config_custom():
    cfg = scc.StrategyContractConsumerConfig(
        output_dir="out",
        stale_input_threshold_seconds=60,
        supported_versions=frozenset({"1.0.0"}),
    )
    assert cfg.output_dir == "out"
    assert cfg.stale_input_threshold_seconds == 60
    assert cfg.supported_versions == frozenset({"1.0.0"})


def test_config_invalid_threshold():
    with pytest.raises(ValueError):
        scc.StrategyContractConsumerConfig(stale_input_threshold_seconds=-1)


def test_config_coerces_metadata():
    cfg = scc.StrategyContractConsumerConfig(metadata={"a": "1", "b": [1, True, None]})
    assert dict(cfg.metadata) == {"a": "1", "b": [1, True, None]}
    assert cfg.metadata["b"] is not [1, True, None]  # deep-copied


def test_config_rejects_non_json_metadata():
    with pytest.raises(TypeError):
        scc.StrategyContractConsumerConfig(metadata={"a": object()})


def _make_valid_result(accepted: bool, mode: str, whitelist: tuple[str, ...]):
    return scc.ValidatedStrategyContext(
        accepted=accepted,
        validated_at=datetime.now(timezone.utc),
        source_fingerprint="sha256-abc",
        source_path="<memory>",
        input_version="0.56.0-dev",
        mode=mode,
        whitelist=whitelist,
        blacklist=(),
        safety_flags={"dry_run": True},
        reason_codes=(scc.VALIDATION_ACCEPTED,),
    )


def test_validated_context_accepted():
    ctx = _make_valid_result(True, "LONG", ("BTC/USDT", "ETH/USDT"))
    assert ctx.accepted is True
    assert ctx.mode == "LONG"
    assert ctx.whitelist == ("BTC/USDT", "ETH/USDT")
    assert ctx.research_only is True
    assert ctx.human_approval_required is True


@pytest.mark.parametrize("mode", ["LONG", "SHORT"])
def test_validated_context_accepted_long_and_short(mode):
    ctx = _make_valid_result(True, mode, ("BTC/USDT",))
    assert ctx.accepted is True
    assert ctx.mode == mode


def test_validated_context_block_all_accepted():
    ctx = _make_valid_result(True, "BLOCK_ALL", ())
    assert ctx.accepted is True
    assert ctx.mode == "BLOCK_ALL"
    assert ctx.whitelist == ()


def test_validated_context_blocked_forces_empty_whitelist():
    with pytest.raises(ValueError):
        _make_valid_result(False, "LONG", ("BTC/USDT",))


def test_validated_context_blocked_ok():
    ctx = _make_valid_result(False, "BLOCK_ALL", ())
    assert ctx.accepted is False
    assert ctx.mode == "BLOCK_ALL"
    assert ctx.whitelist == ()


def test_validated_context_invalid_mode():
    with pytest.raises(ValueError):
        _make_valid_result(True, "LIVE_TRADING", ("BTC/USDT",))


def test_validated_context_research_only_invariant():
    ctx = _make_valid_result(True, "LONG", ("BTC/USDT",))
    with pytest.raises(AttributeError):
        ctx.research_only = False


def test_public_api_exports():
    names = {
        "STRATEGY_CONTRACT_CONSUMER_VERSION",
        "MISSING_INPUT",
        "VALIDATION_ACCEPTED",
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
    for name in names:
        assert hasattr(scc, name), f"Missing export: {name}"


@pytest.mark.parametrize(
    "func",
    [
        scc.strategy_context_result_to_dict,
        scc.strategy_context_result_to_json_text,
        scc.strategy_context_result_to_markdown_text,
        scc.write_strategy_context_validation_result,
    ],
)
def test_unimplemented_stubs_raise(func):
    with pytest.raises(NotImplementedError):
        if func is scc.write_strategy_context_validation_result:
            func(
                _make_valid_result(True, "LONG", ("BTC/USDT",)),
                "out",
                scc.StrategyContractConsumerConfig(),
            )
        else:
            func(_make_valid_result(True, "LONG", ("BTC/USDT",)))
