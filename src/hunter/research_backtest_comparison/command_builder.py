"""Allowlisted command builder for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonValidationError,
)
from hunter.research_backtest_comparison.models import (
    BacktestComparisonConfig,
)
from hunter.research_backtest_comparison.validator import validate_command_args
from hunter.research_backtest_comparison.workspace import BacktestWorkspace


# Characters that must never appear in command arguments.
_UNSAFE_CHARS: frozenset[str] = frozenset({";", "&", "|", "`", "$", "\n", "\r"})


def _sanitize_arg(arg: str) -> str:
    """Return the arg if safe, otherwise raise."""
    if any(c in arg for c in _UNSAFE_CHARS):
        raise ResearchBacktestComparisonValidationError(
            f"command arg contains unsafe characters: {arg!r}"
        )
    return arg


def build_backtest_command(
    config: BacktestComparisonConfig,
    workspace: BacktestWorkspace,
) -> list[str]:
    """Build the fixed argument list for ``freqtrade backtesting``.

    The command is always:

        <freqtrade> backtesting
        --config <temp-config>
        --userdir <temp-userdir>
        --strategy <strategy-name>
        --timeframe <timeframe>
        --timerange <timerange>
        --export trades
        --export-filename <temp-result>

    Any deviation from this shape (including forbidden subcommands or shell
    metacharacters) raises ResearchBacktestComparisonValidationError.
    """
    if not isinstance(config, BacktestComparisonConfig):
        raise ResearchBacktestComparisonValidationError(
            f"config must be BacktestComparisonConfig, got {config!r}"
        )
    if not isinstance(workspace, BacktestWorkspace):
        raise ResearchBacktestComparisonValidationError(
            f"workspace must be BacktestWorkspace, got {workspace!r}"
        )

    executable = _sanitize_arg(str(config.executable_path))
    strategy_name = _sanitize_arg(config.strategy_name)
    timeframe = _sanitize_arg(config.timeframe)
    timerange = _sanitize_arg(config.timerange)
    config_path = _sanitize_arg(str(workspace.config_path))
    userdir = _sanitize_arg(str(workspace.userdir))
    result_path = _sanitize_arg(str(workspace.result_path))

    args: list[str] = [
        executable,
        "backtesting",
        "--config",
        config_path,
        "--userdir",
        userdir,
        "--strategy",
        strategy_name,
        "--timeframe",
        timeframe,
        "--timerange",
        timerange,
        "--export",
        "trades",
        "--export-filename",
        result_path,
    ]

    validate_command_args(args)
    return args


def command_fingerprint(args: list[str]) -> str:
    """Return a deterministic SHA-256 fingerprint of a command argument list.

    Temp and home paths are redacted to ensure determinism across runs/machines.
    """
    redacted = []
    for arg in args:
        if isinstance(arg, str):
            if "/tmp/" in arg or "/home/" in arg:
                redacted.append("[REDACTED_PATH]")
            else:
                redacted.append(arg)
        else:
            redacted.append(str(arg))
    payload = {
        "args": redacted,
        "subcommand": "backtesting",
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
