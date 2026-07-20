"""Integration tests proving Phase B.1 fixture validation is wired into the research_backtest_comparison public API (Stage 8)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hunter.research_backtest_comparison import (
    ExternalFixtureManifest,
    FixtureFileRecord,
    FixtureValidationResult,
    FIXTURE_VALIDATION_REASON_CODES,
    check_undeclared_files,
    compute_fixture_fingerprint,
    validate_external_fixture,
)
from hunter.research_backtest_comparison.fixture_manifest import (
    load_manifest_from_json,
)
from hunter.research_backtest_comparison.fixture_models import (
    FIXTURE_FILE_MISSING,
    FIXTURE_HASH_MISMATCH,
    FIXTURE_ROOT_REQUIRED,
    FIXTURE_UNDECLARED_FILE,
)


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class TestPublicAPIFixtureIntegration:
    """Prove that the fixture validation pipeline is exported via __init__.py."""

    def test_validate_external_fixture_success(self, tmp_path: Path) -> None:
        """End-to-end success from public API."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        content = "btc data"
        sha = _sha256(content)
        (root / "candles" / "btc.json").write_text(content, encoding="utf-8")

        manifest = load_manifest_from_json(json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": sha},
            ],
        }))
        result = validate_external_fixture(str(root), manifest)
        assert result.valid is True
        assert result.validated_file_count == 1
        assert result.declared_file_count == 1
        assert result.reason_codes == ()

    def test_fingerprint_integration(self) -> None:
        """compute_fixture_fingerprint exported and stable."""
        manifest = load_manifest_from_json(json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/a.json", "sha256": "a" * 64},
            ],
        }))
        fp = compute_fixture_fingerprint(manifest)
        assert len(fp) == 64
        assert fp == compute_fixture_fingerprint(manifest)

    def test_undeclared_via_public_api(self, tmp_path: Path) -> None:
        """check_undeclared_files exported and functional."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "btc.json").write_text("data", encoding="utf-8")
        (root / "extra.txt").write_text("extra", encoding="utf-8")

        manifest = load_manifest_from_json(json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "btc.json", "sha256": "a" * 64},
            ],
        }))
        reasons = check_undeclared_files(root, manifest, strict=True)
        assert FIXTURE_UNDECLARED_FILE in reasons

    def test_combined_failure_from_public_api(self, tmp_path: Path) -> None:
        """Root + containment + hash + undeclared failures all propagate."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        content = "ok"
        sha_ok = _sha256(content)
        (root / "candles" / "ok.json").write_text(content, encoding="utf-8")
        (root / "candles" / "bad.json").write_text("wrong", encoding="utf-8")
        (root / "extra.txt").write_text("extra", encoding="utf-8")
        # missing.json not created

        manifest = load_manifest_from_json(json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/ok.json", "sha256": sha_ok},
                {"relative_path": "candles/bad.json", "sha256": "0" * 64},
                {"relative_path": "candles/missing.json", "sha256": "a" * 64},
            ],
        }))
        result = validate_external_fixture(str(root), manifest, strict=True)
        assert result.valid is False
        assert result.declared_file_count == 3
        assert result.validated_file_count == 1
        assert "candles/ok.json" in result.validated_relative_paths
        # All three failure categories present
        assert FIXTURE_FILE_MISSING in result.reason_codes  # missing.json
        assert FIXTURE_HASH_MISMATCH in result.reason_codes  # bad.json
        assert FIXTURE_UNDECLARED_FILE in result.reason_codes  # extra.txt

    def test_fixture_root_invalid_fail_closed(self) -> None:
        """Invalid root produces fail-closed result with correct counts."""
        manifest = load_manifest_from_json(json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/a.json", "sha256": "a" * 64},
                {"relative_path": "candles/b.json", "sha256": "b" * 64},
            ],
        }))
        result = validate_external_fixture(None, manifest)
        assert result.valid is False
        assert result.validated_file_count == 0
        assert result.declared_file_count == 2
        assert result.validated_relative_paths == ()
        assert FIXTURE_ROOT_REQUIRED in result.reason_codes

    def test_fixture_validation_result_type_exported(self) -> None:
        """FixtureValidationResult is importable from public API."""
        result = FixtureValidationResult(
            valid=True,
            fixture_fingerprint="f" * 64,
            validated_file_count=1,
            declared_file_count=1,
            validated_relative_paths=("test.json",),
            reason_codes=(),
            safety_invariants={"research_only": True},
        )
        assert result.valid is True
        assert isinstance(result, FixtureValidationResult)

    def test_fixture_file_record_type_exported(self) -> None:
        """FixtureFileRecord is importable from public API."""
        record = FixtureFileRecord(
            relative_path="candles/a.json",
            sha256="a" * 64,
        )
        assert isinstance(record, FixtureFileRecord)
        assert record.relative_path == "candles/a.json"

    def test_external_fixture_manifest_type_exported(self) -> None:
        """ExternalFixtureManifest is importable from public API."""
        manifest = ExternalFixtureManifest(
            fixture_schema_version="fixture-schema-v1",
            exchange_identifier="binance",
            trading_mode="futures",
            timeframe="1h",
            pair_list=("BTC/USDT:USDT",),
            timerange="20240101-20240601",
            expected_strategy_class="TestStrategy",
            provenance_note="Test",
            files=(FixtureFileRecord(relative_path="test.json", sha256="a" * 64),),
        )
        assert isinstance(manifest, ExternalFixtureManifest)

    def test_reason_codes_exported(self) -> None:
        """All fixture reason codes in the frozen set."""
        assert isinstance(FIXTURE_VALIDATION_REASON_CODES, frozenset)
        assert FIXTURE_FILE_MISSING in FIXTURE_VALIDATION_REASON_CODES
        assert FIXTURE_HASH_MISMATCH in FIXTURE_VALIDATION_REASON_CODES
        assert FIXTURE_UNDECLARED_FILE in FIXTURE_VALIDATION_REASON_CODES
        assert FIXTURE_ROOT_REQUIRED in FIXTURE_VALIDATION_REASON_CODES
        assert len(FIXTURE_VALIDATION_REASON_CODES) == 16
