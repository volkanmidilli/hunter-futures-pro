"""Ephemeral workspace management for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from types import TracebackType
from typing import Any


class BacktestWorkspace:
    """A repository-external ephemeral workspace for a single backtest arm.

    The workspace is created outside the project tree (under ``/tmp`` or the
    caller-provided temp root) and is automatically cleaned up unless
    ``retain_on_failure`` is True and an exception is propagated while the context
    manager is active.
    """

    def __init__(
        self,
        *,
        prefix: str = "hunter_backtest_",
        temp_root: str | Path | None = None,
        retain_on_failure: bool = True,
    ) -> None:
        self.prefix = prefix
        self.temp_root = Path(temp_root) if temp_root else None
        self.retain_on_failure = retain_on_failure
        self._path: Path | None = None
        self._retain: bool = False

    @property
    def path(self) -> Path:
        """Return the workspace root path."""
        if self._path is None:
            raise RuntimeError("workspace has not been created")
        return self._path

    @property
    def userdir(self) -> Path:
        """Return the Freqtrade userdir path."""
        return self.path / "userdir"

    @property
    def config_path(self) -> Path:
        """Return the temporary Freqtrade config path."""
        return self.path / "config.json"

    @property
    def result_path(self) -> Path:
        """Return the temporary result export path."""
        return self.path / "backtest_result.json"

    @property
    def strategy_path(self) -> Path:
        """Return the strategy symlink/copy path inside the workspace."""
        return self.path / "strategy.py"

    def create(self) -> Path:
        """Create the workspace directory and subdirectories."""
        if self._path is not None:
            raise RuntimeError("workspace already created")
        self._path = Path(
            tempfile.mkdtemp(prefix=self.prefix, dir=self.temp_root)
        )
        self.userdir.mkdir(parents=True, exist_ok=True)
        (self.userdir / "strategies").mkdir(parents=True, exist_ok=True)
        (self.userdir / "data").mkdir(parents=True, exist_ok=True)
        return self._path

    def cleanup(self, force: bool = True) -> None:
        """Remove the workspace directory if it exists and retention is not set.

        Explicit calls default to force=True so tests can clean up retained workspaces.
        """
        if self._path is not None and (force or not self._retain) and self._path.exists():
            shutil.rmtree(self._path, ignore_errors=True)
        self._path = None
        self._retain = False

    def __enter__(self) -> "BacktestWorkspace":
        self.create()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None and self.retain_on_failure:
            self._retain = True
            return
        self.cleanup()

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic dict of workspace paths (used for debugging)."""
        return {
            "workspace": str(self._path) if self._path else None,
            "userdir": str(self.userdir),
            "config_path": str(self.config_path),
            "result_path": str(self.result_path),
        }


def create_workspace(
    *,
    prefix: str = "hunter_backtest_",
    temp_root: str | Path | None = None,
    retain_on_failure: bool = True,
) -> BacktestWorkspace:
    """Create and return an ephemeral workspace (not yet entered as a context)."""
    return BacktestWorkspace(
        prefix=prefix,
        temp_root=temp_root,
        retain_on_failure=retain_on_failure,
    )
