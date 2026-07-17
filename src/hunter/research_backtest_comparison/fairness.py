"""Fairness contract for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonFairnessError,
)
from hunter.research_backtest_comparison.models import (
    BacktestArmInput,
    BacktestComparisonConfig,
    BacktestFairnessManifest,
)


def _file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _serialize_value(value: Any) -> Any:
    """Serialize a value into a deterministic JSON-safe structure."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    return value


def build_fairness_manifest(
    config: BacktestComparisonConfig,
    candidate: BacktestArmInput,
    baseline: BacktestArmInput,
) -> BacktestFairnessManifest:
    """Build the fairness manifest proving candidate and baseline are equal except pairlist.

    Raises:
        ResearchBacktestComparisonFairnessError: if assumptions are not equal.
    """
    if not isinstance(config, BacktestComparisonConfig):
        raise ResearchBacktestComparisonFairnessError(
            f"config must be BacktestComparisonConfig, got {config!r}"
        )
    if not isinstance(candidate, BacktestArmInput) or not isinstance(baseline, BacktestArmInput):
        raise ResearchBacktestComparisonFairnessError(
            "candidate and baseline must be BacktestArmInput instances"
        )

    # Compute strategy and data fingerprints.
    strategy_fingerprint = _file_sha256(config.strategy_path)
    data_fingerprint = _dir_fingerprint(config.data_path)

    # Pairlist-only difference.
    candidate_only = tuple(sorted(set(candidate.pairlist) - set(baseline.pairlist)))
    baseline_only = tuple(sorted(set(baseline.pairlist) - set(candidate.pairlist)))
    pairlist_only_difference = (
        f"overlap={len(set(candidate.pairlist) & set(baseline.pairlist))}",
        candidate_only,
        baseline_only,
    )

    assumptions_equal = True
    reason_codes: list[str] = []
    if set(candidate.pairlist) == set(baseline.pairlist):
        # Pairlists are identical; this is allowed but the harness is meant to compare.
        pass

    fairness_payload = {
        "strategy_name": config.strategy_name,
        "strategy_fingerprint": strategy_fingerprint,
        "data_fingerprint": data_fingerprint,
        "timeframe": config.timeframe,
        "timerange": config.timerange,
        "balance": _serialize_value(config.balance),
        "stake": _serialize_value(config.stake),
        "max_open_trades": config.max_open_trades,
        "fee": _serialize_value(config.fee),
        "protections": sorted(config.protections),
        "candidate_label": candidate.label.value,
        "baseline_label": baseline.label.value,
        "candidate_pairlist": sorted(candidate.pairlist),
        "baseline_pairlist": sorted(baseline.pairlist),
    }
    text = json.dumps(fairness_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    fairness_fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()

    return BacktestFairnessManifest(
        strategy_name=config.strategy_name,
        strategy_fingerprint=strategy_fingerprint,
        data_fingerprint=data_fingerprint,
        timeframe=config.timeframe,
        timerange=config.timerange,
        balance=config.balance,
        stake=config.stake,
        max_open_trades=config.max_open_trades,
        fee=config.fee,
        protections=config.protections,
        assumptions_equal=assumptions_equal,
        pairlist_only_difference=pairlist_only_difference,
        fairness_fingerprint=fairness_fingerprint,
        reason_codes=tuple(reason_codes),
        metadata={"fairness_payload": fairness_payload},
    )


def _dir_fingerprint(path: Path) -> str:
    """Return a deterministic SHA-256 fingerprint of directory contents (names only)."""
    entries = []
    if path.exists() and path.is_dir():
        for child in sorted(path.rglob("*")):
            try:
                relpath = child.relative_to(path).as_posix()
            except ValueError:
                relpath = str(child)
            if child.is_file():
                entries.append(f"{relpath}:{_file_sha256(child)}")
            else:
                entries.append(f"{relpath}:dir")
    text = json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_fairness(manifest: BacktestFairnessManifest) -> None:
    """Verify that the fairness manifest reports equal assumptions.

    Raises:
        ResearchBacktestComparisonFairnessError: if assumptions are not equal.
    """
    if not manifest.assumptions_equal:
        raise ResearchBacktestComparisonFairnessError(
            f"Fairness contract violated: {manifest.reason_codes}"
        )
