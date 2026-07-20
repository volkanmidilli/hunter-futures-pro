"""Unit tests for fixture_models.py (Phase B.1 / SPEC-073)."""

from __future__ import annotations

import pytest

from hunter.research_backtest_comparison.fixture_models import (
    FIXTURE_FILE_ESCAPE,
    FIXTURE_FILE_MISSING,
    FIXTURE_FILE_NOT_REGULAR,
    FIXTURE_FILE_SYMLINK,
    FIXTURE_HASH_INVALID,
    FIXTURE_HASH_MISMATCH,
    FIXTURE_MANIFEST_INVALID,
    FIXTURE_MANIFEST_REQUIRED,
    FIXTURE_PATH_ABSOLUTE,
    FIXTURE_PATH_DUPLICATE,
    FIXTURE_PATH_TRAVERSAL,
    FIXTURE_ROOT_FORBIDDEN,
    FIXTURE_ROOT_NOT_DIRECTORY,
    FIXTURE_ROOT_REQUIRED,
    FIXTURE_SCHEMA_UNSUPPORTED,
    FIXTURE_SCHEMA_V1,
    FIXTURE_UNDECLARED_FILE,
    FIXTURE_VALIDATION_REASON_CODES,
    SUPPORTED_FIXTURE_SCHEMAS,
    ExternalFixtureManifest,
    FixtureFileRecord,
    FixtureValidationResult,
)


# ---------------------------------------------------------------------------
# FixtureFileRecord tests
# ---------------------------------------------------------------------------


def test_fixture_file_record_valid():
    """Valid FixtureFileRecord is created successfully."""
    record = FixtureFileRecord(
        relative_path="candles/BTC-USDT-1h.json",
        sha256="a" * 64,
        semantic_role="candle_file",
        pair="BTC/USDT:USDT",
        timeframe="1h",
    )
    assert record.relative_path == "candles/BTC-USDT-1h.json"
    assert record.sha256 == "a" * 64
    assert record.semantic_role == "candle_file"
    assert record.pair == "BTC/USDT:USDT"
    assert record.timeframe == "1h"


def test_fixture_file_record_minimal():
    """FixtureFileRecord with only required fields."""
    record = FixtureFileRecord(
        relative_path="data.json",
        sha256="b" * 64,
    )
    assert record.relative_path == "data.json"
    assert record.sha256 == "b" * 64
    assert record.semantic_role is None
    assert record.pair is None
    assert record.timeframe is None


def test_fixture_file_record_frozen():
    """FixtureFileRecord is immutable."""
    record = FixtureFileRecord(relative_path="test.json", sha256="c" * 64)
    with pytest.raises(AttributeError, match="can't set attribute|cannot set|cannot assign to field"):
        record.relative_path = "changed.json"  # type: ignore[misc]


def test_fixture_file_record_empty_path():
    """Empty relative_path is rejected."""
    with pytest.raises(ValueError, match="relative_path must not be empty"):
        FixtureFileRecord(relative_path="", sha256="d" * 64)


def test_fixture_file_record_absolute_path():
    """Absolute path is rejected."""
    with pytest.raises(ValueError, match="relative_path must not be absolute"):
        FixtureFileRecord(relative_path="/absolute/path.json", sha256="e" * 64)


def test_fixture_file_record_traversal_simple():
    """Simple .. traversal is rejected."""
    with pytest.raises(ValueError, match="relative_path must not contain '\\.\\.'"):
        FixtureFileRecord(relative_path="../escape.json", sha256="f" * 64)


def test_fixture_file_record_traversal_nested():
    """Nested .. traversal is rejected."""
    with pytest.raises(ValueError, match="relative_path must not contain '\\.\\.'"):
        FixtureFileRecord(relative_path="candles/../../../etc/passwd", sha256="0" * 64)


def test_fixture_file_record_empty_sha256():
    """Empty sha256 is rejected."""
    with pytest.raises(ValueError, match="sha256 must not be empty"):
        FixtureFileRecord(relative_path="test.json", sha256="")


def test_fixture_file_record_short_sha256():
    """Short sha256 is rejected."""
    with pytest.raises(ValueError, match="sha256 must be exactly 64 characters"):
        FixtureFileRecord(relative_path="test.json", sha256="abc123")


def test_fixture_file_record_long_sha256():
    """Long sha256 is rejected."""
    with pytest.raises(ValueError, match="sha256 must be exactly 64 characters"):
        FixtureFileRecord(relative_path="test.json", sha256="a" * 65)


def test_fixture_file_record_uppercase_sha256():
    """Uppercase SHA-256 is rejected."""
    with pytest.raises(ValueError, match="sha256 must be lowercase hexadecimal"):
        FixtureFileRecord(relative_path="test.json", sha256="A" * 64)


def test_fixture_file_record_mixed_case_sha256():
    """Mixed-case SHA-256 is rejected."""
    with pytest.raises(ValueError, match="sha256 must be lowercase hexadecimal"):
        FixtureFileRecord(relative_path="test.json", sha256="aB" + "c" * 62)


def test_fixture_file_record_invalid_hex():
    """Non-hexadecimal characters in sha256 are rejected."""
    with pytest.raises(ValueError, match="sha256 must be lowercase hexadecimal"):
        FixtureFileRecord(relative_path="test.json", sha256="g" * 64)


# ---------------------------------------------------------------------------
# ExternalFixtureManifest tests
# ---------------------------------------------------------------------------


def test_external_fixture_manifest_valid():
    """Valid ExternalFixtureManifest is created successfully."""
    manifest = ExternalFixtureManifest(
        fixture_schema_version=FIXTURE_SCHEMA_V1,
        exchange_identifier="binance",
        trading_mode="futures",
        timeframe="1h",
        pair_list=("BTC/USDT:USDT", "ETH/USDT:USDT"),
        timerange="20240101-20240601",
        expected_strategy_class="TestStrategy",
        provenance_note="Test fixture",
        files=(
            FixtureFileRecord(relative_path="candles/btc.json", sha256="a" * 64),
            FixtureFileRecord(relative_path="candles/eth.json", sha256="b" * 64),
        ),
    )
    assert manifest.fixture_schema_version == FIXTURE_SCHEMA_V1
    assert manifest.exchange_identifier == "binance"
    assert manifest.pair_list == ("BTC/USDT:USDT", "ETH/USDT:USDT")
    assert len(manifest.files) == 2


def test_external_fixture_manifest_frozen():
    """ExternalFixtureManifest is immutable."""
    manifest = ExternalFixtureManifest(
        fixture_schema_version=FIXTURE_SCHEMA_V1,
        exchange_identifier="binance",
        trading_mode="futures",
        timeframe="1h",
        pair_list=("BTC/USDT:USDT",),
        timerange="20240101-20240601",
        expected_strategy_class="TestStrategy",
        provenance_note="Test",
        files=(FixtureFileRecord(relative_path="test.json", sha256="c" * 64),),
    )
    with pytest.raises(AttributeError, match="can't set attribute|cannot set|cannot assign to field"):
        manifest.exchange_identifier = "okx"  # type: ignore[misc]


def test_external_fixture_manifest_unsupported_schema():
    """Unsupported fixture_schema_version is rejected."""
    with pytest.raises(ValueError, match="Unsupported fixture_schema_version"):
        ExternalFixtureManifest(
            fixture_schema_version="unknown-schema-v999",
            exchange_identifier="binance",
            trading_mode="futures",
            timeframe="1h",
            pair_list=("BTC/USDT:USDT",),
            timerange="20240101-20240601",
            expected_strategy_class="TestStrategy",
            provenance_note="Test",
            files=(FixtureFileRecord(relative_path="test.json", sha256="d" * 64),),
        )


def test_external_fixture_manifest_empty_pair_list():
    """Empty pair_list is rejected."""
    with pytest.raises(ValueError, match="pair_list must not be empty"):
        ExternalFixtureManifest(
            fixture_schema_version=FIXTURE_SCHEMA_V1,
            exchange_identifier="binance",
            trading_mode="futures",
            timeframe="1h",
            pair_list=(),
            timerange="20240101-20240601",
            expected_strategy_class="TestStrategy",
            provenance_note="Test",
            files=(FixtureFileRecord(relative_path="test.json", sha256="e" * 64),),
        )


def test_external_fixture_manifest_duplicate_pairs():
    """Duplicate pairs in pair_list are rejected."""
    with pytest.raises(ValueError, match="pair_list must not contain duplicates"):
        ExternalFixtureManifest(
            fixture_schema_version=FIXTURE_SCHEMA_V1,
            exchange_identifier="binance",
            trading_mode="futures",
            timeframe="1h",
            pair_list=("BTC/USDT:USDT", "ETH/USDT:USDT", "BTC/USDT:USDT"),
            timerange="20240101-20240601",
            expected_strategy_class="TestStrategy",
            provenance_note="Test",
            files=(FixtureFileRecord(relative_path="test.json", sha256="f" * 64),),
        )


def test_external_fixture_manifest_empty_files():
    """Empty files list is rejected."""
    with pytest.raises(ValueError, match="files must not be empty"):
        ExternalFixtureManifest(
            fixture_schema_version=FIXTURE_SCHEMA_V1,
            exchange_identifier="binance",
            trading_mode="futures",
            timeframe="1h",
            pair_list=("BTC/USDT:USDT",),
            timerange="20240101-20240601",
            expected_strategy_class="TestStrategy",
            provenance_note="Test",
            files=(),
        )


def test_external_fixture_manifest_duplicate_files():
    """Duplicate file paths are rejected."""
    with pytest.raises(ValueError, match="Duplicate file path in manifest"):
        ExternalFixtureManifest(
            fixture_schema_version=FIXTURE_SCHEMA_V1,
            exchange_identifier="binance",
            trading_mode="futures",
            timeframe="1h",
            pair_list=("BTC/USDT:USDT",),
            timerange="20240101-20240601",
            expected_strategy_class="TestStrategy",
            provenance_note="Test",
            files=(
                FixtureFileRecord(relative_path="test.json", sha256="a" * 64),
                FixtureFileRecord(relative_path="test.json", sha256="b" * 64),
            ),
        )


def test_external_fixture_manifest_canonical_payload():
    """canonical_fingerprint_payload produces deterministic sorted output."""
    manifest = ExternalFixtureManifest(
        fixture_schema_version=FIXTURE_SCHEMA_V1,
        exchange_identifier="binance",
        trading_mode="futures",
        timeframe="1h",
        pair_list=("ETH/USDT:USDT", "BTC/USDT:USDT"),  # Unsorted input
        timerange="20240101-20240601",
        expected_strategy_class="TestStrategy",
        provenance_note="Test fixture",
        files=(
            FixtureFileRecord(relative_path="candles/eth.json", sha256="b" * 64),
            FixtureFileRecord(relative_path="candles/btc.json", sha256="a" * 64),
        ),
    )
    payload = manifest.canonical_fingerprint_payload()

    # Pairs are sorted
    assert payload["pair_list"] == ["BTC/USDT:USDT", "ETH/USDT:USDT"]

    # Files are sorted by relative_path
    assert len(payload["files"]) == 2
    assert payload["files"][0]["relative_path"] == "candles/btc.json"
    assert payload["files"][1]["relative_path"] == "candles/eth.json"

    # All semantic fields are present
    assert payload["fixture_schema_version"] == FIXTURE_SCHEMA_V1
    assert payload["exchange_identifier"] == "binance"
    assert payload["timeframe"] == "1h"
    assert payload["timerange"] == "20240101-20240601"
    assert payload["expected_strategy_class"] == "TestStrategy"


def test_external_fixture_manifest_canonical_payload_order_independence():
    """Different input order produces identical canonical payload."""
    manifest_a = ExternalFixtureManifest(
        fixture_schema_version=FIXTURE_SCHEMA_V1,
        exchange_identifier="binance",
        trading_mode="futures",
        timeframe="1h",
        pair_list=("BTC/USDT:USDT", "ETH/USDT:USDT"),
        timerange="20240101-20240601",
        expected_strategy_class="TestStrategy",
        provenance_note="Test",
        files=(
            FixtureFileRecord(relative_path="a.json", sha256="a" * 64),
            FixtureFileRecord(relative_path="b.json", sha256="b" * 64),
        ),
    )
    manifest_b = ExternalFixtureManifest(
        fixture_schema_version=FIXTURE_SCHEMA_V1,
        exchange_identifier="binance",
        trading_mode="futures",
        timeframe="1h",
        pair_list=("ETH/USDT:USDT", "BTC/USDT:USDT"),  # Different order
        timerange="20240101-20240601",
        expected_strategy_class="TestStrategy",
        provenance_note="Test",
        files=(
            FixtureFileRecord(relative_path="b.json", sha256="b" * 64),
            FixtureFileRecord(relative_path="a.json", sha256="a" * 64),
        ),
    )
    assert manifest_a.canonical_fingerprint_payload() == manifest_b.canonical_fingerprint_payload()


# ---------------------------------------------------------------------------
# FixtureValidationResult tests
# ---------------------------------------------------------------------------


def test_fixture_validation_result_valid():
    """Valid FixtureValidationResult (success case)."""
    result = FixtureValidationResult(
        valid=True,
        fixture_fingerprint="a" * 64,
        validated_file_count=2,
        declared_file_count=2,
        validated_relative_paths=("a.json", "b.json"),
        reason_codes=(),
        safety_invariants={"research_only": True},
    )
    assert result.valid is True
    assert result.validated_file_count == 2
    assert result.declared_file_count == 2
    assert len(result.validated_relative_paths) == 2
    assert len(result.reason_codes) == 0


def test_fixture_validation_result_invalid():
    """Invalid FixtureValidationResult (failure case)."""
    result = FixtureValidationResult(
        valid=False,
        fixture_fingerprint="",
        validated_file_count=1,
        declared_file_count=2,
        validated_relative_paths=("a.json",),
        reason_codes=(FIXTURE_FILE_MISSING, FIXTURE_HASH_MISMATCH),
        safety_invariants={"research_only": True},
    )
    assert result.valid is False
    assert result.validated_file_count == 1
    assert result.declared_file_count == 2
    assert len(result.reason_codes) == 2


def test_fixture_validation_result_frozen():
    """FixtureValidationResult is immutable."""
    result = FixtureValidationResult(
        valid=True,
        fixture_fingerprint="b" * 64,
        validated_file_count=1,
        declared_file_count=1,
        validated_relative_paths=("test.json",),
        reason_codes=(),
        safety_invariants={},
    )
    with pytest.raises(AttributeError, match="can't set attribute|cannot set|cannot assign to field"):
        result.valid = False  # type: ignore[misc]


def test_fixture_validation_result_valid_with_reasons():
    """valid=True with non-empty reason_codes is rejected."""
    with pytest.raises(ValueError, match="valid=True but reason_codes is not empty"):
        FixtureValidationResult(
            valid=True,
            fixture_fingerprint="c" * 64,
            validated_file_count=1,
            declared_file_count=1,
            validated_relative_paths=("test.json",),
            reason_codes=(FIXTURE_FILE_MISSING,),
            safety_invariants={},
        )


def test_fixture_validation_result_invalid_without_reasons():
    """valid=False with empty reason_codes is rejected."""
    with pytest.raises(ValueError, match="valid=False but reason_codes is empty"):
        FixtureValidationResult(
            valid=False,
            fixture_fingerprint="",
            validated_file_count=0,
            declared_file_count=1,
            validated_relative_paths=(),
            reason_codes=(),
            safety_invariants={},
        )


def test_fixture_validation_result_validated_exceeds_declared():
    """validated_file_count > declared_file_count is rejected."""
    with pytest.raises(ValueError, match="validated_file_count .* > declared_file_count"):
        FixtureValidationResult(
            valid=True,
            fixture_fingerprint="d" * 64,
            validated_file_count=3,
            declared_file_count=2,
            validated_relative_paths=("a.json", "b.json", "c.json"),
            reason_codes=(),
            safety_invariants={},
        )


def test_fixture_validation_result_count_mismatch():
    """validated_file_count != len(validated_relative_paths) is rejected."""
    with pytest.raises(
        ValueError, match="validated_file_count .* != len\\(validated_relative_paths\\)"
    ):
        FixtureValidationResult(
            valid=True,
            fixture_fingerprint="e" * 64,
            validated_file_count=2,
            declared_file_count=2,
            validated_relative_paths=("a.json",),  # Only 1 path
            reason_codes=(),
            safety_invariants={},
        )


# ---------------------------------------------------------------------------
# Reason code constants
# ---------------------------------------------------------------------------


def test_reason_code_constants_exist():
    """All 16 reason codes are defined."""
    assert FIXTURE_ROOT_REQUIRED == "FIXTURE_ROOT_REQUIRED"
    assert FIXTURE_ROOT_FORBIDDEN == "FIXTURE_ROOT_FORBIDDEN"
    assert FIXTURE_ROOT_NOT_DIRECTORY == "FIXTURE_ROOT_NOT_DIRECTORY"
    assert FIXTURE_MANIFEST_REQUIRED == "FIXTURE_MANIFEST_REQUIRED"
    assert FIXTURE_MANIFEST_INVALID == "FIXTURE_MANIFEST_INVALID"
    assert FIXTURE_SCHEMA_UNSUPPORTED == "FIXTURE_SCHEMA_UNSUPPORTED"
    assert FIXTURE_PATH_ABSOLUTE == "FIXTURE_PATH_ABSOLUTE"
    assert FIXTURE_PATH_TRAVERSAL == "FIXTURE_PATH_TRAVERSAL"
    assert FIXTURE_PATH_DUPLICATE == "FIXTURE_PATH_DUPLICATE"
    assert FIXTURE_FILE_MISSING == "FIXTURE_FILE_MISSING"
    assert FIXTURE_FILE_NOT_REGULAR == "FIXTURE_FILE_NOT_REGULAR"
    assert FIXTURE_FILE_SYMLINK == "FIXTURE_FILE_SYMLINK"
    assert FIXTURE_FILE_ESCAPE == "FIXTURE_FILE_ESCAPE"
    assert FIXTURE_HASH_INVALID == "FIXTURE_HASH_INVALID"
    assert FIXTURE_HASH_MISMATCH == "FIXTURE_HASH_MISMATCH"
    assert FIXTURE_UNDECLARED_FILE == "FIXTURE_UNDECLARED_FILE"


def test_fixture_validation_reason_codes_frozen():
    """FIXTURE_VALIDATION_REASON_CODES is a frozen set."""
    assert isinstance(FIXTURE_VALIDATION_REASON_CODES, frozenset)
    assert len(FIXTURE_VALIDATION_REASON_CODES) == 16


def test_fixture_validation_reason_codes_complete():
    """All reason codes are in the frozen set."""
    expected = {
        FIXTURE_ROOT_REQUIRED,
        FIXTURE_ROOT_FORBIDDEN,
        FIXTURE_ROOT_NOT_DIRECTORY,
        FIXTURE_MANIFEST_REQUIRED,
        FIXTURE_MANIFEST_INVALID,
        FIXTURE_SCHEMA_UNSUPPORTED,
        FIXTURE_PATH_ABSOLUTE,
        FIXTURE_PATH_TRAVERSAL,
        FIXTURE_PATH_DUPLICATE,
        FIXTURE_FILE_MISSING,
        FIXTURE_FILE_NOT_REGULAR,
        FIXTURE_FILE_SYMLINK,
        FIXTURE_FILE_ESCAPE,
        FIXTURE_HASH_INVALID,
        FIXTURE_HASH_MISMATCH,
        FIXTURE_UNDECLARED_FILE,
    }
    assert FIXTURE_VALIDATION_REASON_CODES == expected


def test_supported_fixture_schemas():
    """SUPPORTED_FIXTURE_SCHEMAS contains fixture-schema-v1."""
    assert isinstance(SUPPORTED_FIXTURE_SCHEMAS, frozenset)
    assert FIXTURE_SCHEMA_V1 in SUPPORTED_FIXTURE_SCHEMAS
    assert len(SUPPORTED_FIXTURE_SCHEMAS) >= 1
