"""Tests for executable validation (MVP-65 Stage 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonExecutableError,
)
from hunter.research_backtest_comparison.executable import (
    validate_executable,
    verify_executable_supports_backtesting,
)
from hunter.research_backtest_comparison.models import INVALID_EXECUTABLE


class TestValidateExecutable:
    def test_valid_version(self, tmp_path: Path) -> None:
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh\necho 'freqtrade 2024.1'")
        exe.chmod(0o755)
        info = validate_executable(exe)
        assert info.is_valid is True
        assert "2024.1" in info.version

    def test_missing_executable(self, tmp_path: Path) -> None:
        info = validate_executable(tmp_path / "missing")
        assert info.is_valid is False
        assert INVALID_EXECUTABLE in info.reason_codes

    def test_non_absolute_path(self, tmp_path: Path) -> None:
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh\necho 'freqtrade 2024.1'")
        exe.chmod(0o755)
        info = validate_executable("freqtrade")
        assert info.is_valid is False

    def test_nonzero_exit(self, tmp_path: Path) -> None:
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh\necho error >&2\nexit 1")
        exe.chmod(0o755)
        info = validate_executable(exe)
        assert info.is_valid is False

    def test_verify_executable_supports_backtesting_valid(self, tmp_path: Path) -> None:
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh\necho 'freqtrade 2024.1'")
        exe.chmod(0o755)
        info = validate_executable(exe)
        verify_executable_supports_backtesting(info)

    def test_verify_executable_supports_backtesting_invalid(self, tmp_path: Path) -> None:
        info = validate_executable(tmp_path / "missing")
        with pytest.raises(ResearchBacktestComparisonExecutableError):
            verify_executable_supports_backtesting(info)

    def test_allowlisted_env(self, tmp_path: Path) -> None:
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh\necho $TZ")
        exe.chmod(0o755)
        info = validate_executable(exe, extra_env={"TZ": "Europe/Istanbul", "SECRET": "key"})
        assert info.is_valid is True
        assert "UTC" in info.version
        assert "Europe/Istanbul" not in info.version
