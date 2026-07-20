"""Frozen models for external offline fixture manifest and validation (Phase B.1 / SPEC-073).

This module provides the core dataclasses and reason codes for the external fixture
validation contract. Fixtures are caller-provided, immutable historical-data bundles
used to validate that Hunter's deterministic backtest export parser agrees with a real
Freqtrade installation.

Key invariants:
- Fixtures are never mutated
- Only declared files are read and validated
- Every file's SHA-256 hash is verified
- Path traversal and symlink escapes are rejected
- Repository data/ and reports/ paths are forbidden
- No network, retry, or parallel execution

See: docs/research/external_fixture_contract.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Fixture validation reason codes (SPEC-073)
# ---------------------------------------------------------------------------

FIXTURE_ROOT_REQUIRED = "FIXTURE_ROOT_REQUIRED"
FIXTURE_ROOT_FORBIDDEN = "FIXTURE_ROOT_FORBIDDEN"
FIXTURE_ROOT_NOT_DIRECTORY = "FIXTURE_ROOT_NOT_DIRECTORY"
FIXTURE_MANIFEST_REQUIRED = "FIXTURE_MANIFEST_REQUIRED"
FIXTURE_MANIFEST_INVALID = "FIXTURE_MANIFEST_INVALID"
FIXTURE_SCHEMA_UNSUPPORTED = "FIXTURE_SCHEMA_UNSUPPORTED"
FIXTURE_PATH_ABSOLUTE = "FIXTURE_PATH_ABSOLUTE"
FIXTURE_PATH_TRAVERSAL = "FIXTURE_PATH_TRAVERSAL"
FIXTURE_PATH_DUPLICATE = "FIXTURE_PATH_DUPLICATE"
FIXTURE_FILE_MISSING = "FIXTURE_FILE_MISSING"
FIXTURE_FILE_NOT_REGULAR = "FIXTURE_FILE_NOT_REGULAR"
FIXTURE_FILE_SYMLINK = "FIXTURE_FILE_SYMLINK"
FIXTURE_FILE_ESCAPE = "FIXTURE_FILE_ESCAPE"
FIXTURE_HASH_INVALID = "FIXTURE_HASH_INVALID"
FIXTURE_HASH_MISMATCH = "FIXTURE_HASH_MISMATCH"
FIXTURE_UNDECLARED_FILE = "FIXTURE_UNDECLARED_FILE"

FIXTURE_VALIDATION_REASON_CODES: frozenset[str] = frozenset(
    {
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
)

# Supported fixture schema versions
FIXTURE_SCHEMA_V1 = "fixture-schema-v1"
SUPPORTED_FIXTURE_SCHEMAS: frozenset[str] = frozenset({FIXTURE_SCHEMA_V1})


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureFileRecord:
    """A single file in the external fixture manifest.

    All paths are relative to the fixture root. Validation rejects:
    - Empty paths
    - Absolute paths
    - Path traversal (..)
    - Uppercase SHA-256
    - Non-64-character SHA-256

    Attributes:
        relative_path: Path relative to fixture root (no leading slash, no ..)
        sha256: Lowercase 64-character hexadecimal SHA-256 digest
        semantic_role: Optional role (e.g., "candle_file", "config_file")
        pair: Optional trading pair (e.g., "BTC/USDT:USDT")
        timeframe: Optional timeframe (e.g., "1h", "5m")
    """

    relative_path: str
    sha256: str
    semantic_role: str | None = None
    pair: str | None = None
    timeframe: str | None = None

    def __post_init__(self) -> None:
        """Validate immutable field constraints."""
        if not self.relative_path:
            raise ValueError("relative_path must not be empty")
        if self.relative_path.startswith("/"):
            raise ValueError(f"relative_path must not be absolute: {self.relative_path}")
        if ".." in self.relative_path.split("/"):
            raise ValueError(f"relative_path must not contain '..': {self.relative_path}")
        if not self.sha256:
            raise ValueError("sha256 must not be empty")
        if len(self.sha256) != 64:
            raise ValueError(f"sha256 must be exactly 64 characters: {self.sha256}")
        if not all(c in "0123456789abcdef" for c in self.sha256):
            raise ValueError(f"sha256 must be lowercase hexadecimal: {self.sha256}")


@dataclass(frozen=True)
class ExternalFixtureManifest:
    """Immutable external offline fixture manifest (SPEC-073).

    Describes the historical data bundle structure, metadata, and per-file
    SHA-256 hashes. The manifest is loaded from JSON and must pass structural
    validation before any file I/O occurs.

    All collections are stored as immutable tuples to prevent mutation.
    The manifest is deterministically canonicalized: pairs are sorted,
    files are sorted by relative_path.

    Attributes:
        fixture_schema_version: Schema identifier (must be in SUPPORTED_FIXTURE_SCHEMAS)
        exchange_identifier: Exchange name (e.g., "binance", "okx")
        trading_mode: Trading mode (e.g., "futures", "spot")
        timeframe: Canonical timeframe (e.g., "1h", "5m")
        pair_list: Ordered tuple of trading pairs (non-empty, no duplicates)
        timerange: Freqtrade timerange string (e.g., "20240101-20240601")
        expected_strategy_class: Strategy class name this fixture is intended for
        provenance_note: Free-form provenance / license / source citation
        files: Ordered tuple of FixtureFileRecord (non-empty, no duplicate paths)
    """

    fixture_schema_version: str
    exchange_identifier: str
    trading_mode: str
    timeframe: str
    pair_list: tuple[str, ...]
    timerange: str
    expected_strategy_class: str
    provenance_note: str
    files: tuple[FixtureFileRecord, ...]

    def __post_init__(self) -> None:
        """Validate immutable structural constraints."""
        if self.fixture_schema_version not in SUPPORTED_FIXTURE_SCHEMAS:
            raise ValueError(
                f"Unsupported fixture_schema_version: {self.fixture_schema_version}. "
                f"Supported: {sorted(SUPPORTED_FIXTURE_SCHEMAS)}"
            )
        if not self.pair_list:
            raise ValueError("pair_list must not be empty")
        if len(self.pair_list) != len(set(self.pair_list)):
            raise ValueError("pair_list must not contain duplicates")
        if not self.files:
            raise ValueError("files must not be empty")
        seen_paths: set[str] = set()
        for record in self.files:
            if record.relative_path in seen_paths:
                raise ValueError(f"Duplicate file path in manifest: {record.relative_path}")
            seen_paths.add(record.relative_path)

    def canonical_fingerprint_payload(self) -> dict[str, Any]:
        """Return the canonical deterministic payload for fingerprinting.

        Excludes runtime-only fields (absolute fixture root, timestamps,
        PID, hostname, mtime, inode, directory enumeration order).
        Includes all semantic fields in deterministic sorted order.
        """
        return {
            "fixture_schema_version": self.fixture_schema_version,
            "exchange_identifier": self.exchange_identifier,
            "trading_mode": self.trading_mode,
            "timeframe": self.timeframe,
            "pair_list": sorted(self.pair_list),
            "timerange": self.timerange,
            "expected_strategy_class": self.expected_strategy_class,
            "provenance_note": self.provenance_note,
            "files": [
                {
                    "relative_path": f.relative_path,
                    "sha256": f.sha256,
                    "semantic_role": f.semantic_role,
                    "pair": f.pair,
                    "timeframe": f.timeframe,
                }
                for f in sorted(self.files, key=lambda x: x.relative_path)
            ],
        }


@dataclass(frozen=True)
class FixtureValidationResult:
    """Immutable result of external fixture validation (SPEC-073).

    Records the validation outcome, fingerprint, validated files, and any
    reason codes. All collections are immutable tuples.

    Attributes:
        valid: True if all validations passed
        fixture_fingerprint: Deterministic SHA-256 of canonical manifest payload
        validated_file_count: Number of files successfully validated (hash matched)
        declared_file_count: Total number of files declared in manifest
        validated_relative_paths: Ordered tuple of successfully validated paths
        reason_codes: Ordered tuple of validation failure reason codes (empty if valid)
        safety_invariants: Frozen dict of safety flags (research_only, etc.)
    """

    valid: bool
    fixture_fingerprint: str
    validated_file_count: int
    declared_file_count: int
    validated_relative_paths: tuple[str, ...]
    reason_codes: tuple[str, ...]
    safety_invariants: dict[str, bool]

    def __post_init__(self) -> None:
        """Validate result consistency."""
        if self.valid and self.reason_codes:
            raise ValueError("valid=True but reason_codes is not empty")
        if not self.valid and not self.reason_codes:
            raise ValueError("valid=False but reason_codes is empty")
        if self.validated_file_count > self.declared_file_count:
            raise ValueError(
                f"validated_file_count ({self.validated_file_count}) > "
                f"declared_file_count ({self.declared_file_count})"
            )
        if self.validated_file_count != len(self.validated_relative_paths):
            raise ValueError(
                f"validated_file_count ({self.validated_file_count}) != "
                f"len(validated_relative_paths) ({len(self.validated_relative_paths)})"
            )
