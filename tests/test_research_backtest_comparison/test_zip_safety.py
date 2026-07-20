"""Adversarial ZIP safety tests for export_parser.py (v0.71.0-rc.2).

Tests every ZIP validation check: encrypted members, duplicates, absolute
paths, ``..`` traversal, backslash traversal, symlinks, special files,
excessive member count, oversized members, excessive total size, ZIP-bomb
compression ratios, ambiguous JSON members, missing expected members, and
a valid real-Freqtrade ZIP layout.
"""

from __future__ import annotations

import io
import json
import os
import stat
import struct
import tempfile
import zipfile
from pathlib import Path

import pytest

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonParserError,
)
from hunter.research_backtest_comparison.export_parser import (
    _validate_zip_and_read_member,
    _zip_validate_member_name,
    _zip_is_regular_file,
)
from hunter.research_backtest_comparison.models import (
    ZIP_ABSOLUTE_PATH,
    ZIP_AMBIGUOUS_JSON_MEMBERS,
    ZIP_BACKSLASH_TRAVERSAL,
    ZIP_BOMB_SUSPECTED,
    ZIP_DUPLICATE_MEMBER,
    ZIP_ENCRYPTED_MEMBER,
    ZIP_EXCESSIVE_MEMBER_COUNT,
    ZIP_EXCESSIVE_TOTAL_SIZE,
    ZIP_MISSING_EXPECTED_MEMBER,
    ZIP_OVERSIZED_MEMBER,
    ZIP_PATH_TRAVERSAL,
    ZIP_SPECIAL_FILE_MEMBER,
    ZIP_SYMLINK_MEMBER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_zip(path: Path, members: dict[str, bytes]) -> None:
    """Create a ZIP file at *path* with the given member name → content map.

    Uses deflated compression (matching real Freqtrade export behavior)
    so that compression-ratio checks are meaningful.
    """
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in members.items():
            zf.writestr(name, content)


def _make_encrypted_zip(path: Path, member_name: str, content: bytes) -> None:
    """Create a ZIP with an encrypted member (flag_bits & 0x1).

    Must patch both local file header AND central directory entry,
    because ``zipfile.ZipFile.infolist()`` reads flag_bits from the
    central directory.
    """
    _make_zip(path, {member_name: content})
    raw = bytearray(path.read_bytes())

    # Patch local file header GPBF (offset +6 from PK\x03\x04).
    lfh_idx = raw.find(b"PK\x03\x04")
    if lfh_idx >= 0:
        flags = struct.unpack_from("<H", raw, lfh_idx + 6)[0]
        struct.pack_into("<H", raw, lfh_idx + 6, flags | 0x1)

    # Patch central directory entry GPBF (offset +8 from PK\x01\x02).
    cde_idx = raw.find(b"PK\x01\x02")
    if cde_idx >= 0:
        flags = struct.unpack_from("<H", raw, cde_idx + 8)[0]
        struct.pack_into("<H", raw, cde_idx + 8, flags | 0x1)

    path.write_bytes(raw)


def _make_symlink_zip(path: Path, member_name: str, content: bytes) -> None:
    """Create a ZIP where *member_name* has Unix symlink external attributes."""
    import struct

    _make_zip(path, {member_name: content})
    # Patch the central directory external_attr for the member.
    raw = path.read_bytes()
    # Find the central directory entry (0x02014b50) for the member.
    cde_idx = raw.find(b"PK\x01\x02")
    if cde_idx >= 0:
        ext_attr_offset = cde_idx + 38  # external_attr is at offset 38 in CDE
        new_raw = bytearray(raw)
        # Set Unix symlink mode (S_IFLNK | 0o777 = 0o120777)
        symlink_mode = stat.S_IFLNK | 0o777
        struct.pack_into("<I", new_raw, ext_attr_offset, symlink_mode << 16)
        path.write_bytes(new_raw)


# ---------------------------------------------------------------------------
# Tests: ZIP member name validation
# ---------------------------------------------------------------------------


class TestZipValidateMemberName:
    """Tests for _zip_validate_member_name."""

    def test_valid_simple_name(self) -> None:
        ok, reason = _zip_validate_member_name("result.json")
        assert ok is True
        assert reason is None

    def test_valid_nested_path(self) -> None:
        ok, reason = _zip_validate_member_name("backtest_results/result.json")
        assert ok is True
        assert reason is None

    def test_rejects_absolute_path(self) -> None:
        ok, reason = _zip_validate_member_name("/etc/passwd")
        assert ok is False
        assert reason == ZIP_ABSOLUTE_PATH

    def test_rejects_dotdot_traversal(self) -> None:
        ok, reason = _zip_validate_member_name("../../../etc/passwd")
        assert ok is False
        assert reason == ZIP_PATH_TRAVERSAL

    def test_rejects_dotdot_at_start(self) -> None:
        ok, reason = _zip_validate_member_name("..hidden/result.json")
        # ".." is not a segment by itself here (it's "..hidden")
        assert ok is True
        assert reason is None

    def test_rejects_dotdot_mid_path(self) -> None:
        ok, reason = _zip_validate_member_name("a/../b.json")
        assert ok is False
        assert reason == ZIP_PATH_TRAVERSAL

    def test_rejects_backslash_traversal(self) -> None:
        ok, reason = _zip_validate_member_name("a\\..\\b.json")
        assert ok is False
        assert reason == ZIP_BACKSLASH_TRAVERSAL


# ---------------------------------------------------------------------------
# Tests: ZIP member type detection
# ---------------------------------------------------------------------------


class TestZipIsRegularFile:
    """Tests for _zip_is_regular_file."""

    def test_regular_file(self) -> None:
        info = zipfile.ZipInfo("test.json")
        info.create_system = 3  # Unix
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        ok, reason = _zip_is_regular_file(info)
        assert ok is True
        assert reason is None

    def test_symlink_file(self) -> None:
        info = zipfile.ZipInfo("link.json")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        ok, reason = _zip_is_regular_file(info)
        assert ok is False
        assert reason == ZIP_SYMLINK_MEMBER

    def test_special_file_fifo(self) -> None:
        info = zipfile.ZipInfo("fifo")
        info.create_system = 3
        info.external_attr = (stat.S_IFIFO | 0o644) << 16
        ok, reason = _zip_is_regular_file(info)
        assert ok is False
        assert reason == ZIP_SPECIAL_FILE_MEMBER

    def test_zero_mode_defaults_regular(self) -> None:
        """Mode=0 (stripped metadata) treated as regular file."""
        info = zipfile.ZipInfo("test.json")
        info.create_system = 3
        info.external_attr = 0
        ok, reason = _zip_is_regular_file(info)
        assert ok is True

    def test_permission_only_defaults_regular(self) -> None:
        """Permissions without file-type bits (like Python's zipfile produces)."""
        info = zipfile.ZipInfo("test.json")
        info.create_system = 3
        info.external_attr = 0o644 << 16
        ok, reason = _zip_is_regular_file(info)
        assert ok is True

    def test_non_unix_system_defaults_regular(self) -> None:
        """Non-Unix create_system (e.g. FAT) treated as regular."""
        info = zipfile.ZipInfo("test.json")
        info.create_system = 0  # FAT
        info.external_attr = (stat.S_IFLNK | 0o777) << 16  # irrelevant
        ok, reason = _zip_is_regular_file(info)
        assert ok is True


# ---------------------------------------------------------------------------
# Tests: ZIP validation — valid case
# ---------------------------------------------------------------------------


class TestZipValidationValid:
    """Tests for valid Freqtrade-style ZIP layouts."""

    def test_valid_single_json_member(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        content = json.dumps({"strategy": {"Test": {"total_trades": 0}}})
        _make_zip(zip_path, {"backtest-result.json": content.encode("utf-8")})

        result = _validate_zip_and_read_member(
            zip_path, expected_member_name="backtest-result.json"
        )
        parsed = json.loads(result)
        assert parsed["strategy"]["Test"]["total_trades"] == 0

    def test_valid_with_directory_entries(self, tmp_path: Path) -> None:
        """Directory entries (trailing /) are silently skipped."""
        zip_path = tmp_path / "backtest-result.zip"
        content = json.dumps({"total_trades": 5})
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("results/", "")  # directory entry
            zf.writestr("results/backtest-result.json", content)

        result = _validate_zip_and_read_member(
            zip_path, expected_member_name="results/backtest-result.json"
        )
        parsed = json.loads(result)
        assert parsed["total_trades"] == 5


# ---------------------------------------------------------------------------
# Tests: ZIP validation — rejection cases
# ---------------------------------------------------------------------------


class TestZipValidationRejections:
    """Adversarial rejection tests for every ZIP validation check."""

    # --- Encrypted member ---

    def test_rejects_encrypted_member(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        _make_encrypted_zip(zip_path, "backtest-result.json", b'{"x":1}')
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="backtest-result.json"
            )
        assert exc.value.reason_code == ZIP_ENCRYPTED_MEMBER

    # --- Duplicate member names ---

    def test_rejects_duplicate_member(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        content = json.dumps({"x": 1})
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("backtest-result.json", content)
            zf.writestr("backtest-result.json", content)

        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="backtest-result.json"
            )
        assert exc.value.reason_code == ZIP_DUPLICATE_MEMBER

    # --- Absolute path ---

    def test_rejects_absolute_path_member(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        _make_zip(zip_path, {"/etc/backtest-result.json": b'{"x":1}'})
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="backtest-result.json"
            )
        assert exc.value.reason_code == ZIP_ABSOLUTE_PATH

    # --- Path traversal ---

    def test_rejects_dotdot_traversal_member(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        _make_zip(zip_path, {"../../../backtest-result.json": b'{"x":1}'})
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="backtest-result.json"
            )
        assert exc.value.reason_code == ZIP_PATH_TRAVERSAL

    # --- Backslash traversal ---

    def test_rejects_backslash_traversal_member(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        _make_zip(zip_path, {"a\\..\\backtest-result.json": b'{"x":1}'})
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="backtest-result.json"
            )
        assert exc.value.reason_code == ZIP_BACKSLASH_TRAVERSAL

    # --- Symlink member ---

    def test_rejects_symlink_member(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        _make_symlink_zip(zip_path, "backtest-result.json", b'{"x":1}')
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="backtest-result.json"
            )
        assert exc.value.reason_code == ZIP_SYMLINK_MEMBER

    # --- Special file member ---

    def test_rejects_special_file_member(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        _make_zip(zip_path, {"backtest-result.json": b'{"x":1}'})
        # Patch central directory to mark as FIFO
        raw = zip_path.read_bytes()
        cde_idx = raw.find(b"PK\x01\x02")
        new_raw = bytearray(raw)
        fifo_mode = stat.S_IFIFO | 0o644
        struct.pack_into("<I", new_raw, cde_idx + 38, fifo_mode << 16)
        zip_path.write_bytes(new_raw)
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="backtest-result.json"
            )
        assert exc.value.reason_code == ZIP_SPECIAL_FILE_MEMBER

    # --- Excessive member count ---

    def test_rejects_excessive_member_count(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        members: dict[str, bytes] = {}
        for i in range(33):
            members[f"file_{i}.json"] = b"{}"
        _make_zip(zip_path, members)
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="file_0.json"
            )
        assert exc.value.reason_code == ZIP_EXCESSIVE_MEMBER_COUNT

    # --- Oversized individual member ---

    def test_rejects_oversized_member(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        big = b"x" * (16 * 1024 * 1024 + 1)
        _make_zip(zip_path, {"backtest-result.json": big})
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="backtest-result.json"
            )
        assert exc.value.reason_code == ZIP_OVERSIZED_MEMBER

    # --- Excessive total uncompressed size ---

    def test_rejects_excessive_total_size(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        # 8 x 9 MiB = 72 MiB > 64 MiB limit.
        # Incompressible random data so the compression-ratio check passes.
        chunk = os.urandom(9 * 1024 * 1024)
        members: dict[str, bytes] = {}
        for i in range(8):
            members[f"file_{i}.json"] = chunk
        _make_zip(zip_path, members)
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="file_0.json"
            )
        assert exc.value.reason_code == ZIP_EXCESSIVE_TOTAL_SIZE

    # --- ZIP bomb (suspicious compression ratio) ---

    def test_rejects_zip_bomb(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        # Highly compressible content: 1 MB of zeros → 1 KB compressed
        big = b"\x00" * (1024 * 1024)  # 1 MB of zeros
        _make_zip(zip_path, {"backtest-result.json": big})
        # The result will have compression ratio way beyond 50:1
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="backtest-result.json"
            )
        assert exc.value.reason_code == ZIP_BOMB_SUSPECTED

    # --- Ambiguous JSON members ---

    def test_rejects_ambiguous_json_members(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        _make_zip(
            zip_path,
            {
                "result-a.json": b'{"x":1}',
                "result-b.json": b'{"x":2}',
            },
        )
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="result-a.json"
            )
        assert exc.value.reason_code == ZIP_AMBIGUOUS_JSON_MEMBERS

    # --- Missing expected member ---

    def test_rejects_missing_expected_member(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "backtest-result.zip"
        _make_zip(zip_path, {"other-file.txt": b"not json"})
        with pytest.raises(ResearchBacktestComparisonParserError) as exc:
            _validate_zip_and_read_member(
                zip_path, expected_member_name="backtest-result.json"
            )
        assert exc.value.reason_code == ZIP_MISSING_EXPECTED_MEMBER
