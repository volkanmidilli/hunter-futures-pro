"""Deterministic SHA-256 fingerprints for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.research_backtest_comparison.models import (
    BacktestArmInput,
    BacktestComparisonConfig,
    BacktestComparisonResult,
    BacktestFairnessManifest,
    BacktestMetrics,
    BacktestRunResult,
    ResearchBacktestSafetyFlags,
)


def _serialize_value(value: Any) -> Any:
    """Serialize a value into a deterministic JSON-safe structure."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone().isoformat()
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if is_dataclass(value) and not isinstance(value, type):
        return _serialize_value(value.__dict__)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _hash_payload(payload: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 hash of a JSON payload."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strategy_fingerprint(path: str | Path) -> str:
    """Return the SHA-256 fingerprint of the strategy file contents."""
    file_path = Path(path)
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def data_fingerprint(path: str | Path) -> str:
    """Return a deterministic fingerprint of the data directory contents."""
    from hunter.research_backtest_comparison.fairness import _dir_fingerprint

    return _dir_fingerprint(Path(path))


def pairlist_fingerprint(arm: BacktestArmInput) -> str:
    """Return a deterministic fingerprint of an arm's pairlist."""
    payload = {
        "label": arm.label.value,
        "pairlist": sorted(arm.pairlist),
    }
    return _hash_payload(payload)


def config_fingerprint(config: BacktestComparisonConfig) -> str:
    """Return a deterministic fingerprint of the comparison config.

    Excludes temp paths and mutable metadata.
    """
    payload = {
        "strategy_name": config.strategy_name,
        "timeframe": config.timeframe,
        "timerange": config.timerange,
        "balance": _serialize_value(config.balance),
        "stake": _serialize_value(config.stake),
        "max_open_trades": config.max_open_trades,
        "fee": _serialize_value(config.fee),
        "protections": sorted(config.protections),
    }
    return _hash_payload(payload)


def command_fingerprint(args: list[str]) -> str:
    """Return a deterministic fingerprint of a command argument list."""
    # Redact any absolute paths to ensure determinism across machines.
    redacted = []
    for arg in args:
        if isinstance(arg, str):
            if "/tmp/" in arg or "/home/" in arg:
                redacted.append("[REDACTED_PATH]")
            else:
                redacted.append(arg)
        else:
            redacted.append(str(arg))
    payload = {"args": redacted, "subcommand": "backtesting"}
    return _hash_payload(payload)


def raw_result_fingerprint(path: str | Path) -> str:
    """Return the SHA-256 fingerprint of a raw result file's contents."""
    file_path = Path(path)
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def metrics_fingerprint(metrics: BacktestMetrics) -> str:
    """Return a deterministic fingerprint of canonical metrics."""
    payload = {
        "total_return_pct": _serialize_value(metrics.total_return_pct),
        "absolute_profit": _serialize_value(metrics.absolute_profit),
        "final_balance": _serialize_value(metrics.final_balance),
        "max_drawdown_pct": _serialize_value(metrics.max_drawdown_pct),
        "sharpe_ratio": _serialize_value(metrics.sharpe_ratio),
        "sortino_ratio": _serialize_value(metrics.sortino_ratio),
        "calmar_ratio": _serialize_value(metrics.calmar_ratio),
        "profit_factor": _serialize_value(metrics.profit_factor),
        "win_rate_pct": _serialize_value(metrics.win_rate_pct),
        "trade_count": metrics.trade_count,
        "avg_trade_duration": _serialize_value(metrics.avg_trade_duration),
        "fees_paid": _serialize_value(metrics.fees_paid),
    }
    return _hash_payload(payload)


def run_result_fingerprint(
    result: BacktestRunResult,
) -> str:
    """Return a deterministic fingerprint of a single backtest run result.

    Excludes temp paths, stdout, stderr, and workspace paths.
    """
    payload = {
        "label": result.label.value,
        "success": result.success,
        "metrics": metrics_fingerprint(result.metrics),
        "exit_code": result.exit_code,
        "command_fingerprint": result.command_fingerprint,
        "strategy_sha_before": result.strategy_sha_before,
        "strategy_sha_after": result.strategy_sha_after,
        "reason_codes": sorted(result.reason_codes),
    }
    return _hash_payload(payload)


def comparison_fingerprint_from_result(result: BacktestComparisonResult) -> str:
    """Return the comparison fingerprint from a comparison result."""
    return result.comparison_fingerprint


def fairness_fingerprint(manifest: BacktestFairnessManifest) -> str:
    """Return the fairness fingerprint from a fairness manifest."""
    return manifest.fairness_fingerprint


def safety_flags_fingerprint(flags: ResearchBacktestSafetyFlags) -> str:
    """Return a deterministic fingerprint of safety flags."""
    payload = {
        "research_only": flags.research_only,
        "execution_approval_granted": flags.execution_approval_granted,
        "production_approval_granted": flags.production_approval_granted,
        "live_trading_allowed": flags.live_trading_allowed,
        "automatic_execution_allowed": flags.automatic_execution_allowed,
        "human_approval_required": flags.human_approval_required,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
        "no_network_connection": flags.no_network_connection,
        "no_database_connection": flags.no_database_connection,
        "no_exchange_connection": flags.no_exchange_connection,
        "no_automatic_config_mutation": flags.no_automatic_config_mutation,
        "no_open_interest_synthesis": flags.no_open_interest_synthesis,
        "no_remote_changes": flags.no_remote_changes,
        "no_freqtrade_runtime_connection": flags.no_freqtrade_runtime_connection,
        "human_research_only": flags.human_research_only,
    }
    return _hash_payload(payload)


def report_fingerprint(payload: dict[str, Any]) -> str:
    """Return a deterministic fingerprint of a top-level report payload.

    Excludes temp paths, stdout, stderr, and wall-clock timestamps.
    """
    def prune_timestamps(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: prune_timestamps(v)
                for k, v in value.items()
                if k not in ("generated_at",)
            }
        if isinstance(value, list):
            return [prune_timestamps(v) for v in value]
        return value

    pruned = prune_timestamps(payload)
    return _hash_payload(_serialize_value(pruned))
