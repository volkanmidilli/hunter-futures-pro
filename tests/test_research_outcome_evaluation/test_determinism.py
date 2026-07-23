"""M6 tests: determinism, immutability, multi-horizon integration, safety."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.feather as feather
import pytest

from hunter.research_outcome_evaluation.engine import run_outcome_evaluation
from hunter.research_outcome_evaluation.errors import EvaluationStoreError
from hunter.research_outcome_evaluation.models import (
    OutcomeEvaluationConfig,
    TerminalState,
)

NOW = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)


def _write_feather(path: Path, start: datetime, count: int, base: float = 100.0) -> None:
    rows = [
        {
            "date": start + timedelta(hours=i),
            "open": base + i * 0.5,
            "high": base + i * 0.5 + 1.0,
            "low": base + i * 0.5 - 1.0,
            "close": base + i * 0.5,
            "volume": 10.0,
        }
        for i in range(count)
    ]
    feather.write_feather(pa.Table.from_pylist(rows), str(path))


def _write_snapshot(directory: Path, pairs: list[str], day: str = "2026-01-10") -> None:
    payload = {
        "as_of_date": day,
        "ranking_profile": "V2_RS_LIQUIDITY",
        "schema_version": "hunter-ranking-input-v2",
        "selected": [
            {
                "pair": pair,
                "rank": i + 1,
                "selected": True,
                "rs_score": str(90 - i * 10),
                "liquidity_score": str(80 - i * 5),
                "reason_codes": [],
                "fingerprint": f"fp{i}",
            }
            for i, pair in enumerate(pairs)
        ],
        "fingerprint": f"audit-{day}",
    }
    (directory / f"hunter-pairs-{day.replace('-', '')}-audit.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


@pytest.fixture()
def inputs(tmp_path: Path) -> tuple[Path, Path]:
    snapshot_dir = tmp_path / "snapshots"
    data_dir = tmp_path / "prices"
    snapshot_dir.mkdir()
    data_dir.mkdir()
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT", "AVAX/USDT:USDT"])
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    for i, base in enumerate(["BTC", "SOL", "AVAX"]):
        _write_feather(data_dir / f"{base}_USDT_USDT-1h-futures.feather", start, 400, 100.0 + i * 25)
    return snapshot_dir, data_dir


def _run(snapshot_dir: Path, data_dir: Path, store_dir: Path, horizons: tuple[str, ...] = ("1d",)):
    return run_outcome_evaluation(
        snapshot_dir=snapshot_dir,
        data_dir=data_dir,
        store_dir=store_dir,
        config=OutcomeEvaluationConfig(horizons=horizons),
        all_matured=True,
        now=NOW,
    )


def _artifact_bytes(store_dir: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for sub in ("observations", "summaries"):
        directory = store_dir / sub
        if directory.is_dir():
            for path in sorted(directory.glob("*.json")):
                result[f"{sub}/{path.name}"] = path.read_bytes()
    return result


def test_determinism_identical_artifacts(inputs: tuple[Path, Path], tmp_path: Path) -> None:
    snapshot_dir, data_dir = inputs
    store_a = tmp_path / "store_a"
    store_b = tmp_path / "store_b"
    _run(snapshot_dir, data_dir, store_a)
    _run(snapshot_dir, data_dir, store_b)
    bytes_a = _artifact_bytes(store_a)
    bytes_b = _artifact_bytes(store_b)
    assert bytes_a.keys() == bytes_b.keys()
    assert bytes_a == bytes_b


def test_determinism_fingerprints_stable(inputs: tuple[Path, Path], tmp_path: Path) -> None:
    snapshot_dir, data_dir = inputs
    store_a = tmp_path / "store_a"
    store_b = tmp_path / "store_b"
    report_a = _run(snapshot_dir, data_dir, store_a)
    report_b = _run(snapshot_dir, data_dir, store_b)
    fp_a = [obs.fingerprint for obs in report_a.cohorts[0].observations]
    fp_b = [obs.fingerprint for obs in report_b.cohorts[0].observations]
    assert fp_a == fp_b
    assert report_a.cohorts[0].summary.fingerprint == report_b.cohorts[0].summary.fingerprint


def test_immutability_rerun_is_noop(inputs: tuple[Path, Path], tmp_path: Path) -> None:
    snapshot_dir, data_dir = inputs
    store = tmp_path / "store"
    _run(snapshot_dir, data_dir, store)
    before = _artifact_bytes(store)
    _run(snapshot_dir, data_dir, store)
    after = _artifact_bytes(store)
    assert before == after


def test_immutability_conflicting_content_rejected(inputs: tuple[Path, Path], tmp_path: Path) -> None:
    snapshot_dir, data_dir = inputs
    store = tmp_path / "store"
    _run(snapshot_dir, data_dir, store)
    target = next((store / "summaries").glob("*.json"))
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["cohort_size"] = 999
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(EvaluationStoreError):
        _run(snapshot_dir, data_dir, store)


def test_store_rejects_data_and_reports_dirs(inputs: tuple[Path, Path]) -> None:
    snapshot_dir, data_dir = inputs
    repo_root = Path(__file__).resolve().parents[2]
    with pytest.raises(Exception, match="data|reports"):
        _run(snapshot_dir, data_dir, repo_root / "data")
    with pytest.raises(Exception, match="data|reports"):
        _run(snapshot_dir, data_dir, repo_root / "reports")


def test_multi_horizon_integration(inputs: tuple[Path, Path], tmp_path: Path) -> None:
    snapshot_dir, data_dir = inputs
    store = tmp_path / "store"
    report = _run(snapshot_dir, data_dir, store, horizons=("1d", "3d", "7d"))
    assert len(report.cohorts) == 3
    horizons_seen = {c.outcome_horizon for c in report.cohorts}
    assert horizons_seen == {"1d", "3d", "7d"}
    for cohort in report.cohorts:
        for obs in cohort.observations:
            assert obs.terminal_state is TerminalState.OUTCOME_AVAILABLE
        summary = cohort.summary
        # Horizon-specific metrics differ across horizons (no cross-horizon
        # aggregation under one identity).
        assert summary.spearman_rank_return is not None
        assert summary.metadata["terminal_state_counts"]["OUTCOME_AVAILABLE"] == 2
    returns_by_horizon = {
        c.outcome_horizon: c.observations[0].realized_return for c in report.cohorts
    }
    assert len(set(returns_by_horizon.values())) == 3


def test_safety_no_forbidden_imports() -> None:
    package = Path(__file__).resolve().parents[2] / "src" / "hunter" / "research_outcome_evaluation"
    forbidden = ("subprocess", "socket", "requests", "urllib.request", "freqtrade")
    for path in package.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            for token in forbidden:
                assert token not in stripped, f"{path.name} imports forbidden module {token!r}"


def test_terminal_state_coverage_all_phase_a_codes(tmp_path: Path) -> None:
    """Exercise every Phase A terminal code across scenarios."""
    snapshot_dir = tmp_path / "snapshots"
    data_dir = tmp_path / "prices"
    store = tmp_path / "store"
    snapshot_dir.mkdir()
    data_dir.mkdir()

    # Snapshot 1 (valid): GHOST (no source), GAPPAIR (gap), BADPRICE (invalid
    # endpoint), SOL (available); BTC present.
    pairs = ["SOL/USDT:USDT", "GHOST/USDT:USDT", "GAPPAIR/USDT:USDT", "BADPRICE/USDT:USDT"]
    _write_snapshot(snapshot_dir, pairs, day="2026-01-10")
    # Snapshot 2 (invalid: duplicate pairs) -> SNAPSHOT_INVALID members.
    payload = json.loads((snapshot_dir / "hunter-pairs-20260110-audit.json").read_text(encoding="utf-8"))
    payload["as_of_date"] = "2026-01-11"
    payload["fingerprint"] = "audit-2026-01-11"
    payload["selected"].append(dict(payload["selected"][0]))
    (snapshot_dir / "hunter-pairs-20260111-audit.json").write_text(json.dumps(payload), encoding="utf-8")

    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    _write_feather(data_dir / "BTC_USDT_USDT-1h-futures.feather", start, 400, 100.0)
    _write_feather(data_dir / "SOL_USDT_USDT-1h-futures.feather", start, 400, 200.0)
    # GAPPAIR: series ends before the 1d endpoint candle (2026-01-11 07:00).
    _write_feather(data_dir / "GAPPAIR_USDT_USDT-1h-futures.feather", start, 100, 300.0)
    # BADPRICE: invalid close at the reference candle (2026-01-10 07:00 = idx 127).
    rows = [
        {
            "date": start + timedelta(hours=i),
            "open": 400.0,
            "high": 401.0,
            "low": 399.0,
            "close": -1.0 if i == 127 else 400.0,
            "volume": 10.0,
        }
        for i in range(400)
    ]
    feather.write_feather(pa.Table.from_pylist(rows), str(data_dir / "BADPRICE_USDT_USDT-1h-futures.feather"))

    report = _run(snapshot_dir, data_dir, store)
    states = set()
    for cohort in report.cohorts:
        for obs in cohort.observations:
            states.add(obs.terminal_state)
    for cohort in report.invalid_cohorts:
        for obs in cohort.observations:
            states.add(obs.terminal_state)
    assert TerminalState.OUTCOME_AVAILABLE in states
    assert TerminalState.SNAPSHOT_INVALID in states
    assert TerminalState.OUTCOME_UNAVAILABLE_NO_SOURCE in states
    assert TerminalState.OUTCOME_UNAVAILABLE_GAP in states
    assert TerminalState.OUTCOME_UNAVAILABLE_INVALID_PRICE in states
    # BENCHMARK_UNAVAILABLE covered by engine tests (BTC missing scenario).
    assert TerminalState.OUTCOME_UNAVAILABLE_DELISTED not in states
