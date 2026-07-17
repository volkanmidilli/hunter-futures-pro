"""Tests for workspace management (MVP-65 Stage 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hunter.research_backtest_comparison.workspace import BacktestWorkspace, create_workspace


class TestBacktestWorkspace:
    def test_create_and_cleanup(self) -> None:
        ws = create_workspace(prefix="test_ws_")
        ws.create()
        path = ws.path
        assert path.exists()
        assert ws.userdir.exists()
        assert (ws.userdir / "strategies").exists()
        assert ws.config_path.parent.exists()
        ws.cleanup()
        assert not path.exists()

    def test_context_manager_cleanup(self) -> None:
        with create_workspace(prefix="test_ctx_") as ws:
            path = ws.path
            assert path.exists()
        assert not path.exists()

    def test_context_manager_retain_on_failure(self) -> None:
        ws = create_workspace(prefix="test_ret_", retain_on_failure=True)
        path: Path | None = None
        try:
            with ws:
                path = ws.path
                raise ValueError("boom")
        except ValueError:
            pass
        assert path is not None
        assert path.exists()
        ws.cleanup()
        assert not path.exists()

    def test_path_before_create(self) -> None:
        ws = create_workspace()
        with pytest.raises(RuntimeError):
            _ = ws.path

    def test_double_create(self) -> None:
        ws = create_workspace(prefix="test_double_")
        ws.create()
        with pytest.raises(RuntimeError):
            ws.create()
        ws.cleanup()
