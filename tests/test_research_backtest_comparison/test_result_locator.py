"""Tests for result locator (MVP-65 Stage 4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonRunnerError,
)
from hunter.research_backtest_comparison.result_locator import locate_result_file
from hunter.research_backtest_comparison.workspace import create_workspace


class TestLocateResultFile:
    def test_valid_file(self) -> None:
        ws = create_workspace(prefix="test_loc_")
        ws.create()
        try:
            result = ws.result_path
            result.write_text("{}")
            located = locate_result_file(result, ws.path)
            assert located == result.resolve()
        finally:
            ws.cleanup(force=True)

    def test_missing_file(self) -> None:
        ws = create_workspace(prefix="test_loc_missing_")
        ws.create()
        try:
            with pytest.raises(ResearchBacktestComparisonRunnerError):
                locate_result_file(ws.result_path, ws.path)
        finally:
            ws.cleanup(force=True)

    def test_symlink_rejected(self) -> None:
        ws = create_workspace(prefix="test_loc_link_")
        ws.create()
        try:
            outside = Path(ws.path.parent) / "outside.json"
            outside.write_text("{}")
            ws.result_path.symlink_to(outside)
            with pytest.raises(ResearchBacktestComparisonRunnerError):
                locate_result_file(ws.result_path, ws.path)
        finally:
            ws.cleanup(force=True)
            if outside.exists():
                outside.unlink()

    def test_symlink_inside_workspace_rejected(self) -> None:
        ws = create_workspace(prefix="test_loc_inside_link_")
        ws.create()
        try:
            # Create a real file inside the workspace.
            real_target = ws.path / "real_result.json"
            real_target.write_text("{}")
            # Symlink whose target IS inside the workspace.
            ws.result_path.symlink_to(real_target)
            with pytest.raises(ResearchBacktestComparisonRunnerError):
                locate_result_file(ws.result_path, ws.path)
        finally:
            ws.cleanup(force=True)

    def test_path_escape_rejected(self) -> None:
        ws = create_workspace(prefix="test_loc_escape_")
        ws.create()
        try:
            outside = ws.path.parent / "outside.json"
            outside.write_text("{}")
            with pytest.raises(ResearchBacktestComparisonRunnerError):
                locate_result_file(outside, ws.path)
        finally:
            ws.cleanup(force=True)
            if outside.exists():
                outside.unlink()
