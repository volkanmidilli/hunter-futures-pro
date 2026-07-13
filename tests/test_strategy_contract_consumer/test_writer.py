"""Tests for the strategy_contract_consumer writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter import strategy_contract_consumer as scc


@pytest.fixture
def config():
    return scc.StrategyContractConsumerConfig()


@pytest.fixture
def validated_at():
    return datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


def _make_result(accepted, mode, whitelist, validated_at, generated_at=None):
    return scc.ValidatedStrategyContext(
        accepted=accepted,
        validated_at=validated_at,
        source_fingerprint="a" * 64,
        source_path="<mapping>",
        input_version="0.56.0-dev",
        mode=mode,
        whitelist=whitelist,
        blacklist=(),
        safety_flags={
            "dry_run": True,
            "live_trading_enabled": False,
        },
        reason_codes=(scc.VALIDATION_ACCEPTED,) if accepted else (scc.CONTRADICTORY_INPUT,),
        metadata=MappingProxyType({"run": "test"}),
        generated_at=generated_at,
    )


def test_strategy_context_result_to_dict_structure(validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at)
    data = scc.strategy_context_result_to_dict(ctx)
    assert data["kind"] == "strategy_contract_validation"
    assert data["version"] == scc.STRATEGY_CONTRACT_CONSUMER_VERSION
    assert data["accepted"] is True
    assert data["source_fingerprint"] == "a" * 64
    assert data["source_path"] == "<mapping>"
    assert data["input_version"] == "0.56.0-dev"
    assert data["mode"] == "LONG"
    assert data["research_only"] is True
    assert data["human_approval_required"] is True
    assert data["whitelist"] == ["BTC/USDT"]
    assert data["blacklist"] == []
    assert data["safety_flags"] == {"dry_run": True, "live_trading_enabled": False}
    assert data["reason_codes"] == [scc.VALIDATION_ACCEPTED]
    assert data["metadata"] == {"run": "test"}
    assert data["validated_at"] == validated_at.isoformat()
    assert "safety_notice" in data


def test_dict_serialization_for_rejected_context(validated_at):
    ctx = _make_result(False, "BLOCK_ALL", (), validated_at)
    data = scc.strategy_context_result_to_dict(ctx)
    assert data["accepted"] is False
    assert data["mode"] == "BLOCK_ALL"
    assert data["whitelist"] == []
    assert data["reason_codes"] == [scc.CONTRADICTORY_INPUT]


def test_json_serialization_is_deterministic(validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT", "ETH/USDT"), validated_at)
    text1 = scc.strategy_context_result_to_json_text(ctx)
    text2 = scc.strategy_context_result_to_json_text(ctx)
    assert text1 == text2
    assert text1.endswith("\n")
    parsed = json.loads(text1)
    assert parsed["whitelist"] == ["BTC/USDT", "ETH/USDT"]


def test_markdown_serialization_is_deterministic(validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT", "ETH/USDT"), validated_at)
    text1 = scc.strategy_context_result_to_markdown_text(ctx)
    text2 = scc.strategy_context_result_to_markdown_text(ctx)
    assert text1 == text2


def test_nested_metadata_serialization(validated_at):
    ctx = scc.ValidatedStrategyContext(
        accepted=True,
        validated_at=validated_at,
        source_fingerprint="a" * 64,
        source_path="<mapping>",
        input_version="0.56.0-dev",
        mode="LONG",
        whitelist=("BTC/USDT",),
        blacklist=(),
        safety_flags={"dry_run": True},
        reason_codes=(scc.VALIDATION_ACCEPTED,),
        metadata=MappingProxyType({"nested": MappingProxyType({"value": 42})}),
    )
    data = scc.strategy_context_result_to_dict(ctx)
    assert data["metadata"] == {"nested": {"value": 42}}
    json.loads(scc.strategy_context_result_to_json_text(ctx))


def test_safety_flags_serialization_sorted(validated_at):
    ctx = scc.ValidatedStrategyContext(
        accepted=True,
        validated_at=validated_at,
        source_fingerprint="a" * 64,
        source_path="<mapping>",
        input_version="0.56.0-dev",
        mode="LONG",
        whitelist=("BTC/USDT",),
        blacklist=(),
        safety_flags={"z": True, "a": False, "m": True},
        reason_codes=(scc.VALIDATION_ACCEPTED,),
    )
    data = scc.strategy_context_result_to_dict(ctx)
    assert list(data["safety_flags"].keys()) == ["a", "m", "z"]
    text = scc.strategy_context_result_to_json_text(ctx)
    assert '"a": false' in text
    assert '"m": true' in text
    assert '"z": true' in text


def test_json_keys_sorted(validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at)
    text = scc.strategy_context_result_to_json_text(ctx)
    top_level_keys = []
    for line in text.splitlines():
        # Top-level keys are the first items on lines with no indentation.
        if line.startswith('"'):
            key = line.split('"')[1]
            top_level_keys.append(key)
    assert top_level_keys == sorted(top_level_keys)


def test_write_strategy_context_validation_result_paths(tmp_path, validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at)
    cfg = scc.StrategyContractConsumerConfig(
        output_dir=str(tmp_path / "json"),
        markdown_output_dir=str(tmp_path / "md"),
    )
    json_path, md_path = scc.write_strategy_context_validation_result(ctx, cfg.output_dir, cfg)
    assert json_path == Path(cfg.output_dir) / cfg.json_filename
    assert md_path == Path(cfg.markdown_output_dir) / cfg.markdown_filename
    assert json_path.exists()
    assert md_path.exists()


def test_atomic_json_write(tmp_path, validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at)
    cfg = scc.StrategyContractConsumerConfig(
        output_dir=str(tmp_path / "json"),
        markdown_output_dir=str(tmp_path / "md"),
    )
    json_path, _ = scc.write_strategy_context_validation_result(ctx, cfg.output_dir, cfg)
    text = json_path.read_text(encoding="utf-8")
    assert json.loads(text) is not None


def test_atomic_markdown_write(tmp_path, validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at)
    cfg = scc.StrategyContractConsumerConfig(
        output_dir=str(tmp_path / "json"),
        markdown_output_dir=str(tmp_path / "md"),
    )
    _, md_path = scc.write_strategy_context_validation_result(ctx, cfg.output_dir, cfg)
    text = md_path.read_text(encoding="utf-8")
    assert "# Strategy Contract Validation" in text


def test_repeated_writes_are_byte_identical(tmp_path, validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT", "ETH/USDT"), validated_at)
    cfg = scc.StrategyContractConsumerConfig(
        output_dir=str(tmp_path / "json"),
        markdown_output_dir=str(tmp_path / "md"),
    )
    scc.write_strategy_context_validation_result(ctx, cfg.output_dir, cfg)
    json_first = (Path(cfg.output_dir) / cfg.json_filename).read_bytes()
    md_first = (Path(cfg.markdown_output_dir) / cfg.markdown_filename).read_bytes()

    scc.write_strategy_context_validation_result(ctx, cfg.output_dir, cfg)
    json_second = (Path(cfg.output_dir) / cfg.json_filename).read_bytes()
    md_second = (Path(cfg.markdown_output_dir) / cfg.markdown_filename).read_bytes()

    assert json_first == json_second
    assert md_first == md_second


def test_temp_file_cleanup_after_failure(tmp_path, validated_at, monkeypatch):
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at)
    cfg = scc.StrategyContractConsumerConfig(
        output_dir=str(tmp_path / "json"),
        markdown_output_dir=str(tmp_path / "md"),
    )

    original_replace = __import__("os").replace

    def failing_replace(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("os.replace", failing_replace)
    with pytest.raises(OSError):
        scc.write_strategy_context_validation_result(ctx, cfg.output_dir, cfg)
    monkeypatch.undo()

    # No temp files should remain.
    assert not list((Path(cfg.output_dir)).glob("*.tmp"))
    assert not list((Path(cfg.markdown_output_dir)).glob("*.tmp"))


def test_no_prohibited_wording(validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at)
    md = scc.strategy_context_result_to_markdown_text(ctx)
    prohibited = [
        "live trading",
        "execution ready",
        "approval to trade",
        "production",
        "deploy",
    ]
    for phrase in prohibited:
        assert phrase.lower() not in md.lower(), f"prohibited wording: {phrase}"


def test_public_writer_functions_importable():
    assert callable(scc.strategy_context_result_to_dict)
    assert callable(scc.strategy_context_result_to_json_text)
    assert callable(scc.strategy_context_result_to_markdown_text)
    assert callable(scc.write_strategy_context_validation_result)


def test_generated_at_serialization(validated_at):
    generated_at = datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at, generated_at=generated_at)
    data = scc.strategy_context_result_to_dict(ctx)
    assert data["generated_at"] == generated_at.isoformat()


def test_generated_at_null_serialization(validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at, generated_at=None)
    data = scc.strategy_context_result_to_dict(ctx)
    assert data["generated_at"] is None
    json_text = scc.strategy_context_result_to_json_text(ctx)
    assert '"generated_at": null' in json_text


def test_markdown_includes_artifact_paths(tmp_path, validated_at):
    generated_at = datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at, generated_at=generated_at)
    cfg = scc.StrategyContractConsumerConfig(
        output_dir=str(tmp_path / "data"),
        markdown_output_dir=str(tmp_path / "reports"),
        json_filename="latest_validation.json",
        markdown_filename="latest_validation.md",
    )
    scc.write_strategy_context_validation_result(ctx, cfg.output_dir, cfg)
    md_text = (tmp_path / "reports" / "latest_validation.md").read_text(encoding="utf-8")
    assert str(tmp_path / "data" / "latest_validation.json") in md_text
    assert str(tmp_path / "reports" / "latest_validation.md") in md_text


def test_markdown_without_paths_omits_artifacts_section(validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at)
    md = scc.strategy_context_result_to_markdown_text(ctx)
    assert "## Artifacts" not in md


def test_generated_at_in_markdown(validated_at):
    generated_at = datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at, generated_at=generated_at)
    md = scc.strategy_context_result_to_markdown_text(ctx)
    assert generated_at.isoformat() in md


def test_null_generated_at_in_markdown(validated_at):
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at, generated_at=None)
    md = scc.strategy_context_result_to_markdown_text(ctx)
    assert "Generated At:** _None_" in md


def test_artifact_paths_deterministic(tmp_path, validated_at):
    generated_at = datetime(2026, 7, 12, 10, 0, 0, tzinfo=timezone.utc)
    ctx = _make_result(True, "LONG", ("BTC/USDT",), validated_at, generated_at=generated_at)
    cfg = scc.StrategyContractConsumerConfig(
        output_dir=str(tmp_path / "data"),
        markdown_output_dir=str(tmp_path / "reports"),
    )
    md1 = scc.strategy_context_result_to_markdown_text(
        ctx, json_path=tmp_path / "data" / "latest_validation.json", markdown_path=tmp_path / "reports" / "latest_validation.md"
    )
    md2 = scc.strategy_context_result_to_markdown_text(
        ctx, json_path=tmp_path / "data" / "latest_validation.json", markdown_path=tmp_path / "reports" / "latest_validation.md"
    )
    assert md1 == md2
