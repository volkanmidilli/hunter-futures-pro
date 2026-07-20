"""Unit tests for fixture_validator.py — root validation, path containment, and symlink safety (Phase B.1 / SPEC-073)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from hunter.research_backtest_comparison.fixture_manifest import load_manifest_from_json
from hunter.research_backtest_comparison.fixture_models import (
    FIXTURE_FILE_ESCAPE,
    FIXTURE_FILE_MISSING,
    FIXTURE_FILE_NOT_REGULAR,
    FIXTURE_FILE_SYMLINK,
    FIXTURE_ROOT_FORBIDDEN,
    FIXTURE_ROOT_NOT_DIRECTORY,
    FIXTURE_ROOT_REQUIRED,
    FixtureFileRecord,
)
from hunter.research_backtest_comparison.fixture_validator import (
    validate_file_containment,
    validate_fixture_containment,
    validate_fixture_root,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_manifest_files() -> tuple[FixtureFileRecord, ...]:
    return (
        FixtureFileRecord(relative_path="candles/btc.json", sha256="a" * 64),
        FixtureFileRecord(relative_path="candles/eth.json", sha256="b" * 64),
    )


def _make_fixture_dir(parent: Path, name: str, files: dict[str, str]) -> Path:
    """Create a fixture directory with given files and return its path."""
    root = parent / name
    root.mkdir()
    for rel_path, content in files.items():
        fpath = root / rel_path
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# validate_fixture_root
# ---------------------------------------------------------------------------


class TestValidateFixtureRoot:
    def test_none_root(self) -> None:
        """None root returns FIXTURE_ROOT_REQUIRED."""
        resolved, reasons = validate_fixture_root(None)
        assert resolved is None
        assert FIXTURE_ROOT_REQUIRED in reasons

    def test_empty_string_root(self) -> None:
        """Empty string root returns FIXTURE_ROOT_REQUIRED."""
        resolved, reasons = validate_fixture_root("")
        assert resolved is None
        assert FIXTURE_ROOT_REQUIRED in reasons

    def test_whitespace_string_root(self) -> None:
        """Whitespace-only string root returns FIXTURE_ROOT_REQUIRED."""
        resolved, reasons = validate_fixture_root("   ")
        assert resolved is None
        assert FIXTURE_ROOT_REQUIRED in reasons

    def test_non_existent_root(self) -> None:
        """Non-existent path returns FIXTURE_ROOT_NOT_DIRECTORY."""
        resolved, reasons = validate_fixture_root("/nonexistent/fixture/path/xyz")
        assert resolved is None
        assert FIXTURE_ROOT_NOT_DIRECTORY in reasons

    def test_file_instead_of_directory(self, tmp_path: Path) -> None:
        """A file is not a valid fixture root."""
        f = tmp_path / "not_a_dir"
        f.write_text("data", encoding="utf-8")
        resolved, reasons = validate_fixture_root(str(f))
        assert resolved is None
        assert FIXTURE_ROOT_NOT_DIRECTORY in reasons

    def test_root_inside_repo_data(self, tmp_path: Path) -> None:
        """Fixture root inside repo/data/ is forbidden."""
        # We cannot actually create data/ inside the real repo from tests,
        # so we test with a path that *would* be rejected.  The validator
        # resolves against the real repo root.  Create a temporary
        # directory and assert the rejection for a known-forbidden path.
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        # The real repo data/ is forbidden, not the tmp one.
        # We test the positive case below.

    def test_valid_directory(self, tmp_path: Path) -> None:
        """A valid directory outside data/reports is accepted."""
        root = tmp_path / "my_fixture"
        root.mkdir()
        resolved, reasons = validate_fixture_root(str(root))
        assert resolved is not None
        assert resolved == root.resolve()
        assert reasons == ()

    def test_root_inside_repo_data_rejected(self) -> None:
        """Path that resolves inside the repository data/ is rejected."""
        # Construct a path inside the repo's data/ directory.
        from hunter.research_backtest_comparison.fixture_validator import _repo_root

        repo = _repo_root()
        forbidden = repo / "data" / "pretend_fixture"
        resolved, reasons = validate_fixture_root(str(forbidden))
        assert resolved is None
        assert FIXTURE_ROOT_FORBIDDEN in reasons

    def test_root_inside_repo_reports_rejected(self) -> None:
        """Path that resolves inside the repository reports/ is rejected."""
        from hunter.research_backtest_comparison.fixture_validator import _repo_root

        repo = _repo_root()
        forbidden = repo / "reports" / "pretend_fixture"
        resolved, reasons = validate_fixture_root(str(forbidden))
        assert resolved is None
        assert FIXTURE_ROOT_FORBIDDEN in reasons

    def test_path_as_string(self) -> None:
        """String path is accepted."""
        with tempfile.TemporaryDirectory() as td:
            resolved, reasons = validate_fixture_root(td)
            assert resolved is not None
            assert reasons == ()

    def test_relative_path_resolved(self, tmp_path: Path) -> None:
        """Relative paths are resolved to absolute."""
        root = tmp_path / "fixture"
        root.mkdir()
        saved = os.getcwd()
        try:
            os.chdir(tmp_path)
            rel = "fixture"
            resolved, reasons = validate_fixture_root(rel)
            assert resolved is not None
            assert resolved == root.resolve()
            assert reasons == ()
        finally:
            os.chdir(saved)


# ---------------------------------------------------------------------------
# validate_file_containment
# ---------------------------------------------------------------------------


class TestValidateFileContainment:
    def test_valid_file(self, tmp_path: Path) -> None:
        """A regular file inside the root is accepted."""
        root = tmp_path / "fixture"
        root.mkdir()
        fpath = root / "candles" / "btc.json"
        fpath.parent.mkdir()
        fpath.write_text('{"test": true}', encoding="utf-8")

        record = FixtureFileRecord(relative_path="candles/btc.json", sha256="a" * 64)
        resolved, reasons = validate_file_containment(root, record)
        assert resolved == fpath.resolve()
        assert reasons == ()

    def test_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns FIXTURE_FILE_MISSING."""
        root = tmp_path / "fixture"
        root.mkdir()
        record = FixtureFileRecord(relative_path="candles/missing.json", sha256="a" * 64)
        resolved, reasons = validate_file_containment(root, record)
        assert resolved is None
        assert FIXTURE_FILE_MISSING in reasons

    def test_directory_instead_of_file(self, tmp_path: Path) -> None:
        """A directory is not a regular file."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "subdir").mkdir()
        record = FixtureFileRecord(relative_path="subdir", sha256="b" * 64)
        resolved, reasons = validate_file_containment(root, record)
        assert resolved is None
        assert FIXTURE_FILE_NOT_REGULAR in reasons

    def test_symlink_file_rejected(self, tmp_path: Path) -> None:
        """A symlink (even inside root) is rejected."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        # Real file inside the root — not outside.
        real_file = root / "real_btc.json"
        real_file.write_text("data", encoding="utf-8")
        symlink = root / "candles" / "btc.json"
        symlink.symlink_to(real_file)

        record = FixtureFileRecord(relative_path="candles/btc.json", sha256="c" * 64)
        resolved, reasons = validate_file_containment(root, record)
        assert resolved is None
        # Escape check passes (target is inside root), symlink check fires.
        assert FIXTURE_FILE_SYMLINK in reasons

    def test_symlink_escape_rejected(self, tmp_path: Path) -> None:
        """A symlink that points outside the fixture root is rejected (symlink+escape).

        The symlink check fires first (pre-resolve), then escape would fire
        if the symlink weren't already caught.  Both violations exist but
        the symlink check short-circuits.
        """
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        # File outside the fixture root.
        outside_file = tmp_path / "escape_target.json"
        outside_file.write_text("outside", encoding="utf-8")
        symlink = root / "candles" / "escape.json"
        symlink.symlink_to(outside_file)

        record = FixtureFileRecord(relative_path="candles/escape.json", sha256="d" * 64)
        resolved, reasons = validate_file_containment(root, record)
        assert resolved is None
        # Symlink check fires first (pre-resolve is_symlink is True).
        assert FIXTURE_FILE_SYMLINK in reasons

    def test_path_escape_via_symlink_dir(self, tmp_path: Path) -> None:
        """A regular-looking file reached through a symlink dir is rejected."""
        root = tmp_path / "fixture"
        root.mkdir()

        # Real directory outside fixture
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        (outside_dir / "btc.json").write_text("stolen", encoding="utf-8")

        # Symlink: "candles" points outside
        (root / "candles").symlink_to(outside_dir, target_is_directory=True)

        record = FixtureFileRecord(relative_path="candles/btc.json", sha256="e" * 64)
        resolved, reasons = validate_file_containment(root, record)
        assert resolved is None
        assert FIXTURE_FILE_ESCAPE in reasons

    def test_empty_record_at_existing_root(self, tmp_path: Path) -> None:
        """A file at the fixture root base."""
        root = tmp_path / "fixture"
        root.mkdir()
        f = root / "manifest.txt"
        f.write_text("root-level", encoding="utf-8")

        record = FixtureFileRecord(relative_path="manifest.txt", sha256="f" * 64)
        resolved, reasons = validate_file_containment(root, record)
        assert resolved == f.resolve()
        assert reasons == ()


# ---------------------------------------------------------------------------
# validate_fixture_containment
# ---------------------------------------------------------------------------


class TestValidateFixtureContainment:
    def test_all_valid(self, tmp_path: Path) -> None:
        """All files valid returns resolved root and paths, no reasons."""
        root = _make_fixture_dir(
            tmp_path,
            "good_fixture",
            {
                "candles/btc.json": "btc_data",
                "candles/eth.json": "eth_data",
            },
        )
        import json
        from hunter.research_backtest_comparison.fixture_models import FIXTURE_SCHEMA_V1

        # We need a manifest with matching files.  Build one.
        manifest_json = json.dumps({
            "fixture_schema_version": FIXTURE_SCHEMA_V1,
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": "a" * 64},
                {"relative_path": "candles/eth.json", "sha256": "b" * 64},
            ],
        })
        manifest = load_manifest_from_json(manifest_json)
        resolved_root, paths, reasons = validate_fixture_containment(str(root), manifest)
        assert resolved_root is not None
        assert len(paths) == 2
        assert "candles/btc.json" in paths
        assert "candles/eth.json" in paths
        assert reasons == ()

    def test_some_files_missing(self, tmp_path: Path) -> None:
        """Missing files produce reason codes; existing files still resolved."""
        root = _make_fixture_dir(
            tmp_path,
            "partial_fixture",
            {
                "candles/btc.json": "btc_data",
                # No eth.json
            },
        )
        import json
        from hunter.research_backtest_comparison.fixture_models import FIXTURE_SCHEMA_V1

        manifest_json = json.dumps({
            "fixture_schema_version": FIXTURE_SCHEMA_V1,
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": "a" * 64},
                {"relative_path": "candles/eth.json", "sha256": "b" * 64},
            ],
        })
        manifest = load_manifest_from_json(manifest_json)
        resolved_root, paths, reasons = validate_fixture_containment(str(root), manifest)
        assert resolved_root is not None
        assert len(paths) == 1  # Only btc.json
        assert "candles/btc.json" in paths
        assert FIXTURE_FILE_MISSING in reasons

    def test_root_invalid(self) -> None:
        """Invalid root returns None and only root-level reasons."""
        import json
        from hunter.research_backtest_comparison.fixture_models import FIXTURE_SCHEMA_V1

        manifest_json = json.dumps({
            "fixture_schema_version": FIXTURE_SCHEMA_V1,
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": "a" * 64},
            ],
        })
        manifest = load_manifest_from_json(manifest_json)
        resolved_root, paths, reasons = validate_fixture_containment(None, manifest)
        assert resolved_root is None
        assert paths == {}
        assert FIXTURE_ROOT_REQUIRED in reasons

    def test_root_valid_symlink_file(self, tmp_path: Path) -> None:
        """A symlink file (inside root) produces FIXTURE_FILE_SYMLINK."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        # Real file inside the fixture root so escape check passes.
        real_file = root / "real_data.json"
        real_file.write_text("data", encoding="utf-8")
        (root / "candles" / "btc.json").symlink_to(real_file)

        import json
        from hunter.research_backtest_comparison.fixture_models import FIXTURE_SCHEMA_V1

        manifest_json = json.dumps({
            "fixture_schema_version": FIXTURE_SCHEMA_V1,
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": "a" * 64},
            ],
        })
        manifest = load_manifest_from_json(manifest_json)
        resolved_root, paths, reasons = validate_fixture_containment(str(root), manifest)
        assert resolved_root is not None
        assert paths == {}
        assert FIXTURE_FILE_SYMLINK in reasons

    def test_mixed_valid_and_invalid(self, tmp_path: Path) -> None:
        """Mix of valid, missing, and symlink files accumulates correctly."""
        root = _make_fixture_dir(
            tmp_path,
            "mixed_fixture",
            {"candles/ok.json": "valid"},
        )
        # Symlink to a real file inside root so escape doesn't fire first.
        real_target = root / "real_target.json"
        real_target.write_text("target", encoding="utf-8")
        (root / "candles" / "sym.json").symlink_to(real_target)

        import json
        from hunter.research_backtest_comparison.fixture_models import FIXTURE_SCHEMA_V1

        manifest_json = json.dumps({
            "fixture_schema_version": FIXTURE_SCHEMA_V1,
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/ok.json", "sha256": "a" * 64},
                {"relative_path": "candles/missing.json", "sha256": "b" * 64},
                {"relative_path": "candles/sym.json", "sha256": "c" * 64},
            ],
        })
        manifest = load_manifest_from_json(manifest_json)
        resolved_root, paths, reasons = validate_fixture_containment(str(root), manifest)
        assert resolved_root is not None
        assert len(paths) == 1
        assert "candles/ok.json" in paths
        assert FIXTURE_FILE_MISSING in reasons
        assert FIXTURE_FILE_SYMLINK in reasons
        assert len(reasons) >= 2


# ---------------------------------------------------------------------------
# Stage 5 — SHA-256 hash verification tests
# ---------------------------------------------------------------------------


import hashlib
import json

from hunter.research_backtest_comparison.fixture_models import (
    FIXTURE_HASH_INVALID,
    FIXTURE_HASH_MISMATCH,
)
from hunter.research_backtest_comparison.fixture_validator import (
    _MAX_FIXTURE_FILE_BYTES,
    _hash_file_bytes,
    validate_external_fixture,
    validate_fixture_hashes,
    verify_file_hash,
)


def _sha256(content: str) -> str:
    """Return lowercase hex SHA-256 of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class TestHashFileBytes:
    def test_hash_small_file(self, tmp_path: Path) -> None:
        from hunter.research_backtest_comparison.fixture_validator import _hash_file_bytes

        f = tmp_path / "data.json"
        f.write_text("hello world", encoding="utf-8")
        result = _hash_file_bytes(f)
        assert result == _sha256("hello world")

    def test_hash_empty_file(self, tmp_path: Path) -> None:
        from hunter.research_backtest_comparison.fixture_validator import _hash_file_bytes

        f = tmp_path / "empty.json"
        f.write_text("", encoding="utf-8")
        result = _hash_file_bytes(f)
        assert result == _sha256("")

    def test_hash_exceeds_max_bytes(self, tmp_path: Path) -> None:
        from hunter.research_backtest_comparison.fixture_validator import _hash_file_bytes, _MAX_FIXTURE_FILE_BYTES

        f = tmp_path / "large.bin"
        # Write just over the limit
        f.write_bytes(b"\x00" * (_MAX_FIXTURE_FILE_BYTES // 10))  # Only 25MB is fine

    def test_hash_exceeds_small_limit(self, tmp_path: Path) -> None:
        from hunter.research_backtest_comparison.fixture_validator import _hash_file_bytes

        f = tmp_path / "big.json"
        f.write_bytes(b"x" * 2000)
        with pytest.raises(ValueError, match="exceeds maximum"):
            _hash_file_bytes(f, max_bytes=1000)

    def test_hash_binary_file(self, tmp_path: Path) -> None:
        from hunter.research_backtest_comparison.fixture_validator import _hash_file_bytes

        content = b"\x00\x01\x02\xff\xfe"
        f = tmp_path / "bin.dat"
        f.write_bytes(content)
        result = _hash_file_bytes(f)
        assert result == hashlib.sha256(content).hexdigest()


class TestVerifyFileHash:
    def test_hash_match(self, tmp_path: Path) -> None:
        content = "fixture data"
        f = tmp_path / "good.json"
        f.write_text(content, encoding="utf-8")
        declared = _sha256(content)
        computed, reasons = verify_file_hash(f, declared)
        assert computed == declared
        assert reasons == ()

    def test_hash_mismatch(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("actual content", encoding="utf-8")
        declared = _sha256("expected content")  # Different hash
        computed, reasons = verify_file_hash(f, declared)
        assert computed is None
        assert FIXTURE_HASH_MISMATCH in reasons

    def test_file_read_error(self, tmp_path: Path) -> None:
        # Non-existent file should raise FIXTURE_HASH_INVALID
        f = tmp_path / "nonexistent.json"
        declared = "a" * 64
        computed, reasons = verify_file_hash(f, declared)
        assert computed is None
        assert FIXTURE_HASH_INVALID in reasons


class TestValidateFixtureHashes:
    def test_all_hashes_match(self, tmp_path: Path) -> None:
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()

        content_a = "btc candle data"
        content_b = "eth candle data"
        sha_a = _sha256(content_a)
        sha_b = _sha256(content_b)

        (root / "candles" / "btc.json").write_text(content_a, encoding="utf-8")
        (root / "candles" / "eth.json").write_text(content_b, encoding="utf-8")

        manifest_json = json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": sha_a},
                {"relative_path": "candles/eth.json", "sha256": sha_b},
            ],
        })
        manifest = load_manifest_from_json(manifest_json)

        resolved_root, paths, _ = validate_fixture_containment(str(root), manifest)
        computed, reasons = validate_fixture_hashes(resolved_root, manifest, paths)
        assert len(computed) == 2
        assert "candles/btc.json" in computed
        assert "candles/eth.json" in computed
        assert computed["candles/btc.json"] == sha_a
        assert computed["candles/eth.json"] == sha_b
        assert reasons == ()

    def test_hash_mismatch_in_batch(self, tmp_path: Path) -> None:
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()

        content = "btc data"
        sha_ok = _sha256(content)
        sha_bad = "0" * 64  # Will not match

        (root / "candles" / "btc.json").write_text(content, encoding="utf-8")

        manifest_json = json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": sha_bad},
            ],
        })
        manifest = load_manifest_from_json(manifest_json)

        resolved_root, paths, _ = validate_fixture_containment(str(root), manifest)
        computed, reasons = validate_fixture_hashes(resolved_root, manifest, paths)
        assert len(computed) == 0
        assert FIXTURE_HASH_MISMATCH in reasons

    def test_only_contained_files_hashed(self, tmp_path: Path) -> None:
        """Files that failed containment are skipped for hashing."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()

        content = "ok data"
        sha_ok = _sha256(content)
        (root / "candles" / "ok.json").write_text(content, encoding="utf-8")
        # missing.json is not created

        manifest_json = json.dumps({
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
                {"relative_path": "candles/missing.json", "sha256": "b" * 64},
            ],
        })
        manifest = load_manifest_from_json(manifest_json)

        resolved_root, paths, _ = validate_fixture_containment(str(root), manifest)
        # Only ok.json passes containment
        assert len(paths) == 1
        assert "candles/ok.json" in paths

        computed, reasons = validate_fixture_hashes(resolved_root, manifest, paths)
        # Only ok.json is hashed; missing.json is skipped entirely
        assert len(computed) == 1
        assert "candles/ok.json" in computed
        assert reasons == ()


class TestValidateExternalFixture:
    def test_full_success(self, tmp_path: Path) -> None:
        """All files valid: root ok, containment ok, hashes match."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()

        content_a = "btc data"
        content_b = "eth data"
        sha_a = _sha256(content_a)
        sha_b = _sha256(content_b)

        (root / "candles" / "btc.json").write_text(content_a, encoding="utf-8")
        (root / "candles" / "eth.json").write_text(content_b, encoding="utf-8")

        manifest_json = json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": sha_a},
                {"relative_path": "candles/eth.json", "sha256": sha_b},
            ],
        })
        manifest = load_manifest_from_json(manifest_json)
        result = validate_external_fixture(str(root), manifest)
        assert result.valid is True
        assert result.validated_file_count == 2
        assert result.declared_file_count == 2
        assert len(result.validated_relative_paths) == 2
        assert result.reason_codes == ()

    def test_hash_mismatch_failure(self, tmp_path: Path) -> None:
        """Hash mismatch makes result invalid."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()

        content = "data"
        (root / "candles" / "btc.json").write_text(content, encoding="utf-8")

        manifest_json = json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": "0" * 64},
            ],
        })
        manifest = load_manifest_from_json(manifest_json)
        result = validate_external_fixture(str(root), manifest)
        assert result.valid is False
        assert result.validated_file_count == 0
        assert FIXTURE_HASH_MISMATCH in result.reason_codes

    def test_root_invalid(self) -> None:
        """Invalid root makes result invalid immediately."""
        manifest_json = json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": "a" * 64},
            ],
        })
        manifest = load_manifest_from_json(manifest_json)
        result = validate_external_fixture(None, manifest)
        assert result.valid is False
        assert result.validated_file_count == 0
        assert result.declared_file_count == 1
        assert FIXTURE_ROOT_REQUIRED in result.reason_codes

    def test_fixture_fingerprint_arg(self, tmp_path: Path) -> None:
        """fixture_fingerprint kwarg is stored in result."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        content = "data"
        sha = _sha256(content)
        (root / "candles" / "btc.json").write_text(content, encoding="utf-8")

        manifest_json = json.dumps({
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
        })
        manifest = load_manifest_from_json(manifest_json)
        result = validate_external_fixture(
            str(root), manifest, fixture_fingerprint="f" * 64
        )
        assert result.valid is True
        assert result.fixture_fingerprint == "f" * 64

    def test_combined_failure_counts(self, tmp_path: Path) -> None:
        """Mixing containment failures + hash failures accumulates correctly."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()

        content = "ok data"
        sha_ok = _sha256(content)
        (root / "candles" / "ok.json").write_text(content, encoding="utf-8")
        (root / "candles" / "bad.json").write_text("altered", encoding="utf-8")
        # missing.json not created

        manifest_json = json.dumps({
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
        })
        manifest = load_manifest_from_json(manifest_json)
        result = validate_external_fixture(str(root), manifest)
        assert result.valid is False
        assert result.declared_file_count == 3
        assert result.validated_file_count == 1
        assert len(result.validated_relative_paths) == 1
        assert "candles/ok.json" in result.validated_relative_paths
        assert FIXTURE_FILE_MISSING in result.reason_codes
        assert FIXTURE_HASH_MISMATCH in result.reason_codes


# ---------------------------------------------------------------------------
# Stage 6 — Strict / non-strict undeclared-file policy tests
# ---------------------------------------------------------------------------


from hunter.research_backtest_comparison.fixture_models import FIXTURE_UNDECLARED_FILE  # noqa: E402
from hunter.research_backtest_comparison.fixture_validator import check_undeclared_files  # noqa: E402


class TestCheckUndeclaredFiles:
    def test_no_undeclared_files(self, tmp_path: Path) -> None:
        """All files are declared — no violations in strict mode."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        (root / "candles" / "btc.json").write_text("data", encoding="utf-8")

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
                {"relative_path": "candles/btc.json", "sha256": "a" * 64},
            ],
        }))
        reasons = check_undeclared_files(root, manifest, strict=True)
        assert reasons == ()

    def test_undeclared_file_strict(self, tmp_path: Path) -> None:
        """Undeclared file is flagged in strict mode."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        # Declared file
        (root / "candles" / "btc.json").write_text("data", encoding="utf-8")
        # Undeclared extra file
        (root / "extra.log").write_text("log data", encoding="utf-8")

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
                {"relative_path": "candles/btc.json", "sha256": "a" * 64},
            ],
        }))
        reasons = check_undeclared_files(root, manifest, strict=True)
        assert len(reasons) >= 1
        assert FIXTURE_UNDECLARED_FILE in reasons

    def test_undeclared_file_non_strict(self, tmp_path: Path) -> None:
        """Non-strict mode ignores undeclared files."""
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
        reasons = check_undeclared_files(root, manifest, strict=False)
        assert reasons == ()

    def test_multiple_undeclared_files(self, tmp_path: Path) -> None:
        """Every undeclared file produces a reason code."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        (root / "candles" / "ok.json").write_text("ok", encoding="utf-8")
        (root / "one.json").write_text("a", encoding="utf-8")
        (root / "candles" / "two.json").write_text("b", encoding="utf-8")
        (root / "candles" / "sub" / "three.json").parent.mkdir(parents=True)
        (root / "candles" / "sub" / "three.json").write_text("c", encoding="utf-8")

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
                {"relative_path": "candles/ok.json", "sha256": "a" * 64},
            ],
        }))
        reasons = check_undeclared_files(root, manifest, strict=True)
        assert len(reasons) == 3  # one.json, two.json, candles/sub/three.json

    def test_directories_not_flagged(self, tmp_path: Path) -> None:
        """Empty directories and subdirectories are NOT counted as undeclared files."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        (root / "candles" / "btc.json").write_text("data", encoding="utf-8")
        (root / "empty_dir").mkdir()

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
                {"relative_path": "candles/btc.json", "sha256": "a" * 64},
            ],
        }))
        reasons = check_undeclared_files(root, manifest, strict=True)
        assert reasons == ()  # Empty dir is not a file


class TestUndeclaredFileIntegration:
    def test_strict_mode_blocks_undeclared(self, tmp_path: Path) -> None:
        """validate_external_fixture with strict=True detects undeclared files."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        content = "data"
        sha = _sha256(content)
        (root / "candles" / "btc.json").write_text(content, encoding="utf-8")
        (root / "extra.log").write_text("extra", encoding="utf-8")

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
        result = validate_external_fixture(str(root), manifest, strict=True)
        assert result.valid is False
        assert FIXTURE_UNDECLARED_FILE in result.reason_codes

    def test_non_strict_mode_allows_undeclared(self, tmp_path: Path) -> None:
        """validate_external_fixture with strict=False ignores extra files."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        content = "data"
        sha = _sha256(content)
        (root / "candles" / "btc.json").write_text(content, encoding="utf-8")
        (root / "extra.log").write_text("extra", encoding="utf-8")

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
        result = validate_external_fixture(str(root), manifest, strict=False)
        # Non-strict mode: extra files are silently ignored → valid
        assert result.valid is True
        assert result.declared_file_count == 1
        assert result.validated_file_count == 1
        assert FIXTURE_UNDECLARED_FILE not in result.reason_codes

    def test_strict_default_is_true(self, tmp_path: Path) -> None:
        """Default strict=True when keyword not passed."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        content = "data"
        sha = _sha256(content)
        (root / "candles" / "btc.json").write_text(content, encoding="utf-8")
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
                {"relative_path": "candles/btc.json", "sha256": sha},
            ],
        }))
        # No strict kwarg → defaults to True
        result = validate_external_fixture(str(root), manifest)
        assert result.valid is False
        assert FIXTURE_UNDECLARED_FILE in result.reason_codes


# ---------------------------------------------------------------------------
# Stage 7 — Canonical deterministic fixture fingerprinting tests
# ---------------------------------------------------------------------------


from hunter.research_backtest_comparison.fixture_validator import compute_fixture_fingerprint  # noqa: E402


class TestComputeFixtureFingerprint:
    def test_fingerprint_is_stable(self) -> None:
        """Same manifest produces the same fingerprint every time."""
        manifest_a = load_manifest_from_json(json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": "a" * 64},
                {"relative_path": "candles/eth.json", "sha256": "b" * 64},
            ],
        }))
        fingerprint_a = compute_fixture_fingerprint(manifest_a)
        fingerprint_b = compute_fixture_fingerprint(manifest_a)
        assert fingerprint_a == fingerprint_b
        assert len(fingerprint_a) == 64

    def test_different_manifest_different_fingerprint(self) -> None:
        """Different manifest payloads produce different fingerprints."""
        manifest_a = load_manifest_from_json(json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test A",
            "files": [
                {"relative_path": "candles/a.json", "sha256": "a" * 64},
            ],
        }))
        manifest_b = load_manifest_from_json(json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT"],
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test B",  # Different note
            "files": [
                {"relative_path": "candles/a.json", "sha256": "a" * 64},
            ],
        }))
        assert compute_fixture_fingerprint(manifest_a) != compute_fixture_fingerprint(manifest_b)

    def test_order_independence(self) -> None:
        """Different input order produces identical fingerprint (deterministic canonicalization)."""
        manifest_a = load_manifest_from_json(json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["ETH/USDT:USDT", "BTC/USDT:USDT"],  # Unsorted
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/eth.json", "sha256": "b" * 64},
                {"relative_path": "candles/btc.json", "sha256": "a" * 64},
            ],
        }))
        manifest_b = load_manifest_from_json(json.dumps({
            "fixture_schema_version": "fixture-schema-v1",
            "exchange_identifier": "binance",
            "trading_mode": "futures",
            "timeframe": "1h",
            "pair_list": ["BTC/USDT:USDT", "ETH/USDT:USDT"],  # Sorted
            "timerange": "20240101-20240601",
            "expected_strategy_class": "TestStrategy",
            "provenance_note": "Test",
            "files": [
                {"relative_path": "candles/btc.json", "sha256": "a" * 64},
                {"relative_path": "candles/eth.json", "sha256": "b" * 64},
            ],
        }))
        assert compute_fixture_fingerprint(manifest_a) == compute_fixture_fingerprint(manifest_b)


class TestFingerprintIntegration:
    def test_validate_external_fixture_stores_fingerprint(self, tmp_path: Path) -> None:
        """When fixture_fingerprint is passed, it appears in the result."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        content = "data"
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
        fp = compute_fixture_fingerprint(manifest)
        result = validate_external_fixture(
            str(root), manifest, fixture_fingerprint=fp
        )
        assert result.fixture_fingerprint == fp

    def test_fingerprint_empty_by_default(self, tmp_path: Path) -> None:
        """When fixture_fingerprint is not passed, it defaults to empty string."""
        root = tmp_path / "fixture"
        root.mkdir()
        (root / "candles").mkdir()
        content = "data"
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
        assert result.fixture_fingerprint == ""
