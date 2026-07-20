"""Unit tests for fixture_manifest.py (Phase B.1 / SPEC-073)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from hunter.research_backtest_comparison.fixture_manifest import (
    FixtureManifestError,
    load_manifest_from_file,
    load_manifest_from_json,
)
from hunter.research_backtest_comparison.fixture_models import (
    FIXTURE_MANIFEST_INVALID,
    FIXTURE_MANIFEST_REQUIRED,
    FIXTURE_SCHEMA_UNSUPPORTED,
    FIXTURE_SCHEMA_V1,
)


# ---------------------------------------------------------------------------
# Valid manifest fixtures
# ---------------------------------------------------------------------------


def valid_manifest_dict() -> dict:
    """Return a valid manifest dictionary."""
    return {
        "fixture_schema_version": FIXTURE_SCHEMA_V1,
        "exchange_identifier": "binance",
        "trading_mode": "futures",
        "timeframe": "1h",
        "pair_list": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
        "timerange": "20240101-20240601",
        "expected_strategy_class": "TestStrategy",
        "provenance_note": "Test fixture for Phase B.1",
        "files": [
            {
                "relative_path": "candles/btc.json",
                "sha256": "a" * 64,
                "semantic_role": "candle_file",
                "pair": "BTC/USDT:USDT",
                "timeframe": "1h",
            },
            {
                "relative_path": "candles/eth.json",
                "sha256": "b" * 64,
            },
        ],
    }


def valid_manifest_json() -> str:
    """Return a valid manifest as JSON text."""
    return json.dumps(valid_manifest_dict(), indent=2)


# ---------------------------------------------------------------------------
# load_manifest_from_json tests
# ---------------------------------------------------------------------------


def test_load_manifest_from_json_valid():
    """Valid JSON manifest loads successfully."""
    manifest = load_manifest_from_json(valid_manifest_json())
    assert manifest.fixture_schema_version == FIXTURE_SCHEMA_V1
    assert manifest.exchange_identifier == "binance"
    assert manifest.trading_mode == "futures"
    assert manifest.timeframe == "1h"
    assert len(manifest.pair_list) == 2
    assert len(manifest.files) == 2


def test_load_manifest_from_json_canonical_ordering():
    """Files and pairs are canonically sorted."""
    manifest = load_manifest_from_json(valid_manifest_json())
    # Pairs are sorted
    assert manifest.pair_list == ("BTC/USDT:USDT", "ETH/USDT:USDT")
    # Files are sorted by relative_path
    assert manifest.files[0].relative_path == "candles/btc.json"
    assert manifest.files[1].relative_path == "candles/eth.json"


def test_load_manifest_from_json_minimal():
    """Minimal manifest with only required fields."""
    minimal = {
        "fixture_schema_version": FIXTURE_SCHEMA_V1,
        "exchange_identifier": "okx",
        "trading_mode": "spot",
        "timeframe": "5m",
        "pair_list": ["BTC/USDT"],
        "timerange": "20240101-20240201",
        "expected_strategy_class": "MinimalStrategy",
        "provenance_note": "Minimal test fixture",
        "files": [
            {
                "relative_path": "data.json",
                "sha256": "c" * 64,
            }
        ],
    }
    manifest = load_manifest_from_json(json.dumps(minimal))
    assert manifest.exchange_identifier == "okx"
    assert len(manifest.files) == 1
    assert manifest.files[0].semantic_role is None


def test_load_manifest_from_json_empty():
    """Empty JSON text is rejected."""
    with pytest.raises(FixtureManifestError, match="empty") as exc_info:
        load_manifest_from_json("")
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_REQUIRED


def test_load_manifest_from_json_whitespace_only():
    """Whitespace-only JSON text is rejected."""
    with pytest.raises(FixtureManifestError, match="empty") as exc_info:
        load_manifest_from_json("   \n\t  ")
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_REQUIRED


def test_load_manifest_from_json_malformed():
    """Malformed JSON is rejected."""
    with pytest.raises(FixtureManifestError, match="malformed") as exc_info:
        load_manifest_from_json("{invalid json")
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_not_object():
    """JSON root must be an object."""
    with pytest.raises(FixtureManifestError, match="root must be an object") as exc_info:
        load_manifest_from_json("[1, 2, 3]")
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_missing_field():
    """Missing required field is rejected."""
    incomplete = valid_manifest_dict()
    del incomplete["timeframe"]
    with pytest.raises(FixtureManifestError, match="missing required fields.*timeframe") as exc_info:
        load_manifest_from_json(json.dumps(incomplete))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_unknown_field_strict():
    """Unknown field is rejected in strict mode."""
    extra = valid_manifest_dict()
    extra["unknown_field"] = "should fail"
    with pytest.raises(FixtureManifestError, match="unknown fields.*unknown_field") as exc_info:
        load_manifest_from_json(json.dumps(extra), strict_schema=True)
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_unknown_field_non_strict():
    """Unknown field is ignored in non-strict mode."""
    extra = valid_manifest_dict()
    extra["future_extension"] = "ignored"
    manifest = load_manifest_from_json(json.dumps(extra), strict_schema=False)
    assert manifest.exchange_identifier == "binance"


def test_load_manifest_from_json_unsupported_schema():
    """Unsupported schema version is rejected."""
    invalid_schema = valid_manifest_dict()
    invalid_schema["fixture_schema_version"] = "fixture-schema-v999"
    with pytest.raises(FixtureManifestError, match="Unsupported fixture_schema_version") as exc_info:
        load_manifest_from_json(json.dumps(invalid_schema))
    assert exc_info.value.reason_code == FIXTURE_SCHEMA_UNSUPPORTED


def test_load_manifest_from_json_schema_not_string():
    """fixture_schema_version must be a string."""
    invalid = valid_manifest_dict()
    invalid["fixture_schema_version"] = 123
    with pytest.raises(FixtureManifestError, match="fixture_schema_version must be a string") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_exchange_not_string():
    """exchange_identifier must be a string."""
    invalid = valid_manifest_dict()
    invalid["exchange_identifier"] = 456
    with pytest.raises(FixtureManifestError, match="exchange_identifier must be a string") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_pair_list_not_array():
    """pair_list must be an array."""
    invalid = valid_manifest_dict()
    invalid["pair_list"] = "BTC/USDT:USDT"
    with pytest.raises(FixtureManifestError, match="pair_list must be an array") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_pair_list_empty():
    """Empty pair_list is rejected."""
    invalid = valid_manifest_dict()
    invalid["pair_list"] = []
    with pytest.raises(FixtureManifestError, match="pair_list must not be empty") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_pair_not_string():
    """pair_list elements must be strings."""
    invalid = valid_manifest_dict()
    invalid["pair_list"] = ["BTC/USDT:USDT", 123]
    with pytest.raises(FixtureManifestError, match="pair_list\\[1\\] must be a string") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_files_not_array():
    """files must be an array."""
    invalid = valid_manifest_dict()
    invalid["files"] = {"relative_path": "test.json", "sha256": "a" * 64}
    with pytest.raises(FixtureManifestError, match="files must be an array") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_files_empty():
    """Empty files array is rejected."""
    invalid = valid_manifest_dict()
    invalid["files"] = []
    with pytest.raises(FixtureManifestError, match="files must not be empty") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_file_not_object():
    """files elements must be objects."""
    invalid = valid_manifest_dict()
    invalid["files"] = ["not an object"]
    with pytest.raises(FixtureManifestError, match="files\\[0\\] must be an object") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_file_missing_field():
    """files elements must have required fields."""
    invalid = valid_manifest_dict()
    invalid["files"] = [{"relative_path": "test.json"}]  # Missing sha256
    with pytest.raises(FixtureManifestError, match="files\\[0\\].*missing required fields.*sha256") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_file_path_not_string():
    """relative_path must be a string."""
    invalid = valid_manifest_dict()
    invalid["files"] = [{"relative_path": 123, "sha256": "a" * 64}]
    with pytest.raises(FixtureManifestError, match="files\\[0\\]\\.relative_path must be a string") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_file_sha256_not_string():
    """sha256 must be a string."""
    invalid = valid_manifest_dict()
    invalid["files"] = [{"relative_path": "test.json", "sha256": 789}]
    with pytest.raises(FixtureManifestError, match="files\\[0\\]\\.sha256 must be a string") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_file_semantic_role_wrong_type():
    """semantic_role must be a string or null."""
    invalid = valid_manifest_dict()
    invalid["files"] = [
        {"relative_path": "test.json", "sha256": "a" * 64, "semantic_role": 123}
    ]
    with pytest.raises(FixtureManifestError, match="files\\[0\\]\\.semantic_role must be a string or null") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_file_invalid_path():
    """FixtureFileRecord validates path format."""
    invalid = valid_manifest_dict()
    invalid["files"] = [{"relative_path": "/absolute/path.json", "sha256": "a" * 64}]
    with pytest.raises(FixtureManifestError, match="files\\[0\\] is invalid.*absolute") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_file_invalid_sha256():
    """FixtureFileRecord validates SHA-256 format."""
    invalid = valid_manifest_dict()
    invalid["files"] = [{"relative_path": "test.json", "sha256": "too_short"}]
    with pytest.raises(FixtureManifestError, match="files\\[0\\] is invalid.*64 characters") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_duplicate_pairs():
    """ExternalFixtureManifest validates duplicate pairs."""
    invalid = valid_manifest_dict()
    invalid["pair_list"] = ["BTC/USDT:USDT", "ETH/USDT:USDT", "BTC/USDT:USDT"]
    with pytest.raises(FixtureManifestError, match="Manifest validation failed.*duplicate") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_duplicate_files():
    """ExternalFixtureManifest validates duplicate file paths."""
    invalid = valid_manifest_dict()
    invalid["files"] = [
        {"relative_path": "test.json", "sha256": "a" * 64},
        {"relative_path": "test.json", "sha256": "b" * 64},
    ]
    with pytest.raises(FixtureManifestError, match="Manifest validation failed.*Duplicate file path") as exc_info:
        load_manifest_from_json(json.dumps(invalid))
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_json_order_independence():
    """Different input order produces identical canonical manifest."""
    manifest_a_dict = valid_manifest_dict()
    manifest_a_dict["pair_list"] = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    manifest_a_dict["files"] = [
        {"relative_path": "candles/btc.json", "sha256": "a" * 64},
        {"relative_path": "candles/eth.json", "sha256": "b" * 64},
    ]

    manifest_b_dict = valid_manifest_dict()
    manifest_b_dict["pair_list"] = ["ETH/USDT:USDT", "BTC/USDT:USDT"]  # Different order
    manifest_b_dict["files"] = [
        {"relative_path": "candles/eth.json", "sha256": "b" * 64},
        {"relative_path": "candles/btc.json", "sha256": "a" * 64},
    ]

    manifest_a = load_manifest_from_json(json.dumps(manifest_a_dict))
    manifest_b = load_manifest_from_json(json.dumps(manifest_b_dict))

    # Canonical payloads must match
    assert manifest_a.canonical_fingerprint_payload() == manifest_b.canonical_fingerprint_payload()


# ---------------------------------------------------------------------------
# load_manifest_from_file tests
# ---------------------------------------------------------------------------


def test_load_manifest_from_file_valid():
    """Valid manifest file loads successfully."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(valid_manifest_json())
        temp_path = f.name

    try:
        manifest = load_manifest_from_file(temp_path)
        assert manifest.exchange_identifier == "binance"
    finally:
        Path(temp_path).unlink()


def test_load_manifest_from_file_not_found():
    """Non-existent file is rejected."""
    with pytest.raises(FixtureManifestError, match="not found") as exc_info:
        load_manifest_from_file("/nonexistent/path/manifest.json")
    assert exc_info.value.reason_code == FIXTURE_MANIFEST_REQUIRED


def test_load_manifest_from_file_read_error():
    """File read errors are caught."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir) / "subdir"
        dir_path.mkdir()
        # Try to read a directory as a file
        with pytest.raises(FixtureManifestError, match="Failed to read manifest file") as exc_info:
            load_manifest_from_file(dir_path)
        assert exc_info.value.reason_code == FIXTURE_MANIFEST_INVALID


def test_load_manifest_from_file_strict_mode():
    """strict_schema parameter is passed through."""
    manifest_with_extra = valid_manifest_dict()
    manifest_with_extra["extra_field"] = "should be ignored"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(json.dumps(manifest_with_extra))
        temp_path = f.name

    try:
        # Strict mode: should fail
        with pytest.raises(FixtureManifestError, match="unknown fields"):
            load_manifest_from_file(temp_path, strict_schema=True)

        # Non-strict mode: should succeed
        manifest = load_manifest_from_file(temp_path, strict_schema=False)
        assert manifest.exchange_identifier == "binance"
    finally:
        Path(temp_path).unlink()


# ---------------------------------------------------------------------------
# FixtureManifestError tests
# ---------------------------------------------------------------------------


def test_fixture_manifest_error_attributes():
    """FixtureManifestError preserves reason_code."""
    error = FixtureManifestError("Test message", FIXTURE_MANIFEST_INVALID)
    assert str(error) == "Test message"
    assert error.reason_code == FIXTURE_MANIFEST_INVALID
