"""JSON manifest loading and structural validation for external fixtures (Phase B.1 / SPEC-073).

This module provides deterministic JSON loading with strict schema validation.
It rejects malformed JSON, missing required fields, unknown schema versions,
invalid field types, and (optionally) unknown fields.

No file I/O occurs here—this module only parses JSON text and constructs
validated ExternalFixtureManifest instances.

See: docs/research/external_fixture_contract.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hunter.research_backtest_comparison.fixture_models import (
    FIXTURE_MANIFEST_INVALID,
    FIXTURE_MANIFEST_REQUIRED,
    FIXTURE_SCHEMA_UNSUPPORTED,
    FIXTURE_SCHEMA_V1,
    SUPPORTED_FIXTURE_SCHEMAS,
    ExternalFixtureManifest,
    FixtureFileRecord,
)


class FixtureManifestError(ValueError):
    """Raised when manifest loading or validation fails."""

    def __init__(self, message: str, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def load_manifest_from_json(
    json_text: str,
    *,
    strict_schema: bool = True,
) -> ExternalFixtureManifest:
    """Load and validate an ExternalFixtureManifest from JSON text.

    Args:
        json_text: Raw JSON string containing the manifest
        strict_schema: If True, reject unknown fields at the top level.
                      If False, ignore unknown fields (forward compatibility).

    Returns:
        Validated ExternalFixtureManifest instance

    Raises:
        FixtureManifestError: If JSON is malformed, required fields are missing,
                             schema version is unsupported, or field types are invalid.

    Example:
        >>> manifest_json = '''
        ... {
        ...   "fixture_schema_version": "fixture-schema-v1",
        ...   "exchange_identifier": "binance",
        ...   "trading_mode": "futures",
        ...   "timeframe": "1h",
        ...   "pair_list": ["BTC/USDT:USDT"],
        ...   "timerange": "20240101-20240601",
        ...   "expected_strategy_class": "TestStrategy",
        ...   "provenance_note": "Test fixture",
        ...   "files": [
        ...     {
        ...       "relative_path": "candles/btc.json",
        ...       "sha256": "a" * 64
        ...     }
        ...   ]
        ... }
        ... '''
        >>> manifest = load_manifest_from_json(manifest_json)
        >>> manifest.exchange_identifier
        'binance'
    """
    if not json_text or not json_text.strip():
        raise FixtureManifestError(
            "Manifest JSON text is empty",
            FIXTURE_MANIFEST_REQUIRED,
        )

    # Parse JSON
    try:
        raw = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise FixtureManifestError(
            f"Manifest JSON is malformed: {e}",
            FIXTURE_MANIFEST_INVALID,
        ) from e

    if not isinstance(raw, dict):
        raise FixtureManifestError(
            f"Manifest JSON root must be an object, got {type(raw).__name__}",
            FIXTURE_MANIFEST_INVALID,
        )

    # Extract and validate required fields
    required_fields = {
        "fixture_schema_version",
        "exchange_identifier",
        "trading_mode",
        "timeframe",
        "pair_list",
        "timerange",
        "expected_strategy_class",
        "provenance_note",
        "files",
    }
    missing = required_fields - raw.keys()
    if missing:
        raise FixtureManifestError(
            f"Manifest is missing required fields: {sorted(missing)}",
            FIXTURE_MANIFEST_INVALID,
        )

    # Strict schema mode: reject unknown fields
    if strict_schema:
        unknown = set(raw.keys()) - required_fields
        if unknown:
            raise FixtureManifestError(
                f"Manifest contains unknown fields (strict mode): {sorted(unknown)}",
                FIXTURE_MANIFEST_INVALID,
            )

    # Validate schema version
    schema_version = raw["fixture_schema_version"]
    if not isinstance(schema_version, str):
        raise FixtureManifestError(
            f"fixture_schema_version must be a string, got {type(schema_version).__name__}",
            FIXTURE_MANIFEST_INVALID,
        )
    if schema_version not in SUPPORTED_FIXTURE_SCHEMAS:
        raise FixtureManifestError(
            f"Unsupported fixture_schema_version: {schema_version}. "
            f"Supported: {sorted(SUPPORTED_FIXTURE_SCHEMAS)}",
            FIXTURE_SCHEMA_UNSUPPORTED,
        )

    # Validate string fields
    for field in [
        "exchange_identifier",
        "trading_mode",
        "timeframe",
        "timerange",
        "expected_strategy_class",
        "provenance_note",
    ]:
        value = raw[field]
        if not isinstance(value, str):
            raise FixtureManifestError(
                f"{field} must be a string, got {type(value).__name__}",
                FIXTURE_MANIFEST_INVALID,
            )

    # Validate pair_list
    pair_list_raw = raw["pair_list"]
    if not isinstance(pair_list_raw, list):
        raise FixtureManifestError(
            f"pair_list must be an array, got {type(pair_list_raw).__name__}",
            FIXTURE_MANIFEST_INVALID,
        )
    if not pair_list_raw:
        raise FixtureManifestError(
            "pair_list must not be empty",
            FIXTURE_MANIFEST_INVALID,
        )
    for i, pair in enumerate(pair_list_raw):
        if not isinstance(pair, str):
            raise FixtureManifestError(
                f"pair_list[{i}] must be a string, got {type(pair).__name__}",
                FIXTURE_MANIFEST_INVALID,
            )

    # Validate files
    files_raw = raw["files"]
    if not isinstance(files_raw, list):
        raise FixtureManifestError(
            f"files must be an array, got {type(files_raw).__name__}",
            FIXTURE_MANIFEST_INVALID,
        )
    if not files_raw:
        raise FixtureManifestError(
            "files must not be empty",
            FIXTURE_MANIFEST_INVALID,
        )

    # Parse and validate each file record
    file_records: list[FixtureFileRecord] = []
    for i, file_raw in enumerate(files_raw):
        if not isinstance(file_raw, dict):
            raise FixtureManifestError(
                f"files[{i}] must be an object, got {type(file_raw).__name__}",
                FIXTURE_MANIFEST_INVALID,
            )

        # Required file fields
        file_required = {"relative_path", "sha256"}
        file_missing = file_required - file_raw.keys()
        if file_missing:
            raise FixtureManifestError(
                f"files[{i}] is missing required fields: {sorted(file_missing)}",
                FIXTURE_MANIFEST_INVALID,
            )

        # Optional file fields
        relative_path = file_raw["relative_path"]
        sha256 = file_raw["sha256"]
        semantic_role = file_raw.get("semantic_role")
        pair = file_raw.get("pair")
        timeframe = file_raw.get("timeframe")

        # Type validation
        if not isinstance(relative_path, str):
            raise FixtureManifestError(
                f"files[{i}].relative_path must be a string, got {type(relative_path).__name__}",
                FIXTURE_MANIFEST_INVALID,
            )
        if not isinstance(sha256, str):
            raise FixtureManifestError(
                f"files[{i}].sha256 must be a string, got {type(sha256).__name__}",
                FIXTURE_MANIFEST_INVALID,
            )
        if semantic_role is not None and not isinstance(semantic_role, str):
            raise FixtureManifestError(
                f"files[{i}].semantic_role must be a string or null, got {type(semantic_role).__name__}",
                FIXTURE_MANIFEST_INVALID,
            )
        if pair is not None and not isinstance(pair, str):
            raise FixtureManifestError(
                f"files[{i}].pair must be a string or null, got {type(pair).__name__}",
                FIXTURE_MANIFEST_INVALID,
            )
        if timeframe is not None and not isinstance(timeframe, str):
            raise FixtureManifestError(
                f"files[{i}].timeframe must be a string or null, got {type(timeframe).__name__}",
                FIXTURE_MANIFEST_INVALID,
            )

        # FixtureFileRecord validates path/sha256 format in __post_init__
        try:
            record = FixtureFileRecord(
                relative_path=relative_path,
                sha256=sha256,
                semantic_role=semantic_role,
                pair=pair,
                timeframe=timeframe,
            )
        except ValueError as e:
            raise FixtureManifestError(
                f"files[{i}] is invalid: {e}",
                FIXTURE_MANIFEST_INVALID,
            ) from e

        file_records.append(record)

    # Canonicalize: sort pairs and files for deterministic fingerprinting
    pair_list_canonical = tuple(sorted(pair_list_raw))
    files_canonical = tuple(sorted(file_records, key=lambda r: r.relative_path))

    # ExternalFixtureManifest validates duplicate pairs/paths in __post_init__
    try:
        manifest = ExternalFixtureManifest(
            fixture_schema_version=schema_version,
            exchange_identifier=raw["exchange_identifier"],
            trading_mode=raw["trading_mode"],
            timeframe=raw["timeframe"],
            pair_list=pair_list_canonical,
            timerange=raw["timerange"],
            expected_strategy_class=raw["expected_strategy_class"],
            provenance_note=raw["provenance_note"],
            files=files_canonical,
        )
    except ValueError as e:
        raise FixtureManifestError(
            f"Manifest validation failed: {e}",
            FIXTURE_MANIFEST_INVALID,
        ) from e

    return manifest


def load_manifest_from_file(
    path: str | Path,
    *,
    strict_schema: bool = True,
) -> ExternalFixtureManifest:
    """Load and validate an ExternalFixtureManifest from a JSON file.

    Args:
        path: Path to the manifest JSON file
        strict_schema: If True, reject unknown fields at the top level.

    Returns:
        Validated ExternalFixtureManifest instance

    Raises:
        FixtureManifestError: If the file cannot be read or the manifest is invalid.
        FileNotFoundError: If the file does not exist.
    """
    manifest_path = Path(path)
    try:
        json_text = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise FixtureManifestError(
            f"Manifest file not found: {manifest_path}",
            FIXTURE_MANIFEST_REQUIRED,
        ) from e
    except Exception as e:
        raise FixtureManifestError(
            f"Failed to read manifest file {manifest_path}: {e}",
            FIXTURE_MANIFEST_INVALID,
        ) from e

    return load_manifest_from_json(json_text, strict_schema=strict_schema)
