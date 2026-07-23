"""M4 tests: engine orchestration end-to-end (tmp_path only)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.feather as feather
import pytest

from hunter.research_outcome_evaluation.engine import run_outcome_evaluation
from hunter.research_outcome_evaluation.models import (
    REASON_FIRST_SNAPSHOT,
    OutcomeEvaluationConfig,
    TerminalState,
)

NOW = datetime(2026, 1, 12, 0, 0, tzinfo=timezone.utc)


def _write_feather(path: Path, start: datetime, count: int, base: float = 100.0) -> None:
    rows = [
        {
            "date": start + timedelta(hours=i),
            "open": base + i,
            "high": base + i + 1.0,
            "low": base + i - 1.0,
            "close": base + i,
            "volume": 10.0,
        }
        for i in range(count)
    ]
    feather.write_feather(pa.Table.from_pylist(rows), str(path))


def _snapshot_payload(pairs: list[str], day: str = "2026-01-10", profile: str = "V2_RS_LIQUIDITY") -> dict:
    return {
        "as_of_date": day,
        "ranking_profile": profile,
        "schema_version": "hunter-ranking-input-v2",
        "selected": [
            {
                "pair": pair,
                "rank": i + 1,
                "selected": True,
                "rs_score": str(Decimal(90 - i * 10)),
                "liquidity_score": str(Decimal(80 - i * 5)),
                "reason_codes": ["RS_SCORE"],
                "fingerprint": f"fp{i}",
            }
            for i, pair in enumerate(pairs)
        ],
        "fingerprint": f"audit-{day}",
    }


def _write_snapshot(directory: Path, pairs: list[str], day: str = "2026-01-10", profile: str = "V2_RS_LIQUIDITY") -> Path:
    path = directory / f"hunter-pairs-{day.replace('-', '')}-audit.json"
    path.write_text(json.dumps(_snapshot_payload(pairs, day, profile)), encoding="utf-8")
    return path


def _setup_dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    snapshot_dir = tmp_path / "snapshots"
    data_dir = tmp_path / "prices"
    store_dir = tmp_path / "store"
    snapshot_dir.mkdir()
    data_dir.mkdir()
    store_dir.mkdir()
    return snapshot_dir, data_dir, store_dir


def _run(snapshot_dir: Path, data_dir: Path, store_dir: Path, **kwargs: object):
    kwargs.setdefault("now", NOW)
    kwargs.setdefault("all_matured", True)
    kwargs.setdefault("config", OutcomeEvaluationConfig(horizons=("1d",)))
    return run_outcome_evaluation(
        snapshot_dir=snapshot_dir,
        data_dir=data_dir,
        store_dir=store_dir,
        **kwargs,  # type: ignore[arg-type]
    )


def _full_data(data_dir: Path, pairs: list[str]) -> None:
    start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
    for i, pair in enumerate(["BTC/USDT:USDT"] + pairs):
        base = pair.split("/")[0]
        _write_feather(data_dir / f"{base}_USDT_USDT-1h-futures.feather", start, 72, 100.0 + i * 10)


def test_happy_path_all_available(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT", "AVAX/USDT:USDT"])
    _full_data(data_dir, ["SOL/USDT:USDT", "AVAX/USDT:USDT"])

    report = _run(snapshot_dir, data_dir, store_dir)

    assert len(report.cohorts) == 1
    cohort = report.cohorts[0]
    assert cohort.snapshot_date == "2026-01-10"
    assert cohort.outcome_horizon == "1d"
    assert len(cohort.observations) == 2
    for obs in cohort.observations:
        assert obs.terminal_state is TerminalState.OUTCOME_AVAILABLE
        assert obs.realized_return is not None
        assert obs.benchmark_return is not None
        assert obs.benchmark_relative_return is not None
        assert obs.mae_pct is not None
        assert obs.mfe_pct is not None
        assert obs.realized_volatility_pct is not None
        assert obs.coverage_ratio == Decimal("1.000000")
        assert obs.safety_flags.research_only is True

    summary = cohort.summary
    assert summary.cohort_size == 2
    assert summary.available_count == 2
    assert summary.unavailable_count == 0
    assert summary.previous_snapshot_reason == REASON_FIRST_SNAPSHOT
    assert summary.turnover_reason == REASON_FIRST_SNAPSHOT
    assert summary.benchmark_failure_reason is None
    assert summary.daily_data_availability == Decimal("1.000000")
    assert summary.top_5_return_pct is not None
    assert summary.spearman_rank_return is not None
    assert len(report.artifact_paths) == 2
    assert (store_dir / "observations").is_dir()
    assert (store_dir / "summaries").is_dir()


def test_benchmark_failure_marks_pairs(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT"])
    # Pair data only, no BTC file.
    start = datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc)
    _write_feather(data_dir / "SOL_USDT_USDT-1h-futures.feather", start, 72)

    report = _run(snapshot_dir, data_dir, store_dir)
    (obs,) = report.cohorts[0].observations
    assert obs.terminal_state is TerminalState.BENCHMARK_UNAVAILABLE
    assert obs.realized_return is None
    summary = report.cohorts[0].summary
    assert summary.benchmark_failure_reason == TerminalState.OUTCOME_UNAVAILABLE_NO_SOURCE.value
    assert summary.available_count == 0


def test_missing_pair_source(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT", "GHOST/USDT:USDT"])
    _full_data(data_dir, ["SOL/USDT:USDT"])

    report = _run(snapshot_dir, data_dir, store_dir)
    states = {obs.pair: obs.terminal_state for obs in report.cohorts[0].observations}
    assert states["SOL/USDT:USDT"] is TerminalState.OUTCOME_AVAILABLE
    assert states["GHOST/USDT:USDT"] is TerminalState.OUTCOME_UNAVAILABLE_NO_SOURCE
    summary = report.cohorts[0].summary
    assert summary.available_count == 1
    assert summary.unavailable_count == 1
    assert summary.daily_data_availability == Decimal("0.500000")


def test_invalid_snapshot_marks_all_members(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    payload = _snapshot_payload(["SOL/USDT:USDT", "AVAX/USDT:USDT"])
    payload["selected"].append(dict(payload["selected"][0]))  # duplicate pair
    path = snapshot_dir / "hunter-pairs-20260110-audit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    _full_data(data_dir, ["SOL/USDT:USDT", "AVAX/USDT:USDT"])

    report = _run(snapshot_dir, data_dir, store_dir)
    assert len(report.invalid_snapshots) == 1
    assert len(report.cohorts) == 0
    cohort = report.invalid_cohorts[0]
    assert {obs.terminal_state for obs in cohort.observations} == {TerminalState.SNAPSHOT_INVALID}
    assert cohort.summary.available_count == 0
    assert cohort.summary.turnover_reason == "INSUFFICIENT_OBSERVATIONS"
    assert cohort.summary.metadata.get("invalid_snapshot") is True
    assert cohort.summary.metadata.get("invalid_reason")


def test_pending_horizon_never_persisted(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT"], day="2026-01-11")
    _full_data(data_dir, ["SOL/USDT:USDT"])
    early_now = datetime(2026, 1, 12, 7, 0, tzinfo=timezone.utc)  # 1d endpoint = Jan 12 08:00

    report = run_outcome_evaluation(
        snapshot_dir=snapshot_dir,
        data_dir=data_dir,
        store_dir=store_dir,
        config=OutcomeEvaluationConfig(horizons=("1d",)),
        all_matured=True,
        now=early_now,
    )
    assert report.cohorts == ()
    assert report.pending_cohorts == ("2026-01-11|V2_RS_LIQUIDITY|1d",)
    assert not (store_dir / "observations").exists() or not list((store_dir / "observations").glob("*.json"))


def test_btc_selected_special_case(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    _write_snapshot(snapshot_dir, ["BTC/USDT:USDT", "SOL/USDT:USDT"])
    _full_data(data_dir, ["SOL/USDT:USDT"])

    report = _run(snapshot_dir, data_dir, store_dir)
    states = {obs.pair: obs for obs in report.cohorts[0].observations}
    btc = states["BTC/USDT:USDT"]
    assert btc.is_benchmark_pair is True
    assert btc.terminal_state is TerminalState.OUTCOME_AVAILABLE
    assert btc.benchmark_return == btc.realized_return
    assert btc.benchmark_relative_return == Decimal("0.000000")
    # BTC excluded from benchmark-relative aggregation.
    summary = report.cohorts[0].summary
    sol = states["SOL/USDT:USDT"]
    assert summary.benchmark_relative_return_pct == sol.benchmark_relative_return


def test_turnover_with_previous_snapshot(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT", "AVAX/USDT:USDT"], day="2026-01-09")
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT", "DOGE/USDT:USDT"], day="2026-01-10")
    _full_data(data_dir, ["SOL/USDT:USDT", "AVAX/USDT:USDT", "DOGE/USDT:USDT"])

    report = _run(snapshot_dir, data_dir, store_dir)
    by_date = {c.snapshot_date: c for c in report.cohorts}
    day1 = by_date["2026-01-09"].summary
    day2 = by_date["2026-01-10"].summary
    assert day1.turnover_reason == REASON_FIRST_SNAPSHOT
    # intersection = {SOL} = 1; turnover = 1 - 1/2 = 0.5; retention = 1/2 = 0.5
    assert day2.turnover == Decimal("0.500000")
    assert day2.retention == Decimal("0.500000")
    assert day2.days_since_previous_snapshot == 1


def test_as_of_range_filters_snapshots(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT"], day="2026-01-09")
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT"], day="2026-01-10")
    _full_data(data_dir, ["SOL/USDT:USDT"])

    report = run_outcome_evaluation(
        snapshot_dir=snapshot_dir,
        data_dir=data_dir,
        store_dir=store_dir,
        config=OutcomeEvaluationConfig(horizons=("1d",)),
        as_of_start="2026-01-10",
        as_of_end="2026-01-10",
        now=NOW,
    )
    assert [c.snapshot_date for c in report.cohorts] == ["2026-01-10"]


def test_selection_required() -> None:
    with pytest.raises(ValueError, match="selection required"):
        run_outcome_evaluation(
            snapshot_dir=Path("x"),
            data_dir=Path("y"),
            store_dir=Path("z"),
        )


def test_no_observation_silently_discarded(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT", "GHOST/USDT:USDT", "AVAX/USDT:USDT"])
    _full_data(data_dir, ["SOL/USDT:USDT", "AVAX/USDT:USDT"])

    report = _run(snapshot_dir, data_dir, store_dir)
    cohort = report.cohorts[0]
    assert len(cohort.observations) == 3
    assert cohort.summary.cohort_size == 3
    total = sum(report.terminal_state_counts.values())
    assert total == 3


def test_top_n_policy_counts_partial_availability(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    pairs = ["SOL/USDT:USDT", "AVAX/USDT:USDT", "GHOST/USDT:USDT", "MISSING/USDT:USDT"]
    _write_snapshot(snapshot_dir, pairs)
    _full_data(data_dir, ["SOL/USDT:USDT", "AVAX/USDT:USDT"])

    report = _run(snapshot_dir, data_dir, store_dir)
    cohort = report.cohorts[0]
    summary = cohort.summary
    assert summary.available_count == 2
    # All four cuts use the same policy and report available counts.
    assert summary.top_5_available_count == 2
    assert summary.top_10_available_count == 2
    assert summary.top_20_available_count == 2
    assert summary.top_30_available_count == 2
    assert summary.top_5_return_pct is not None
    assert summary.top_10_return_pct is not None
    assert summary.top_20_return_pct is not None
    assert summary.top_30_return_pct is not None


def test_top_n_zero_available_is_null(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    _write_snapshot(snapshot_dir, ["GHOST/USDT:USDT"])
    # Only BTC data, no GHOST data.
    _write_feather(data_dir / "BTC_USDT_USDT-1h-futures.feather", NOW - timedelta(hours=72), 72, 100.0)

    report = _run(snapshot_dir, data_dir, store_dir)
    summary = report.cohorts[0].summary
    assert summary.top_5_return_pct is None
    assert summary.top_5_available_count == 0
    assert summary.top_10_available_count == 0


def test_invalid_cohort_excluded_from_cohorts_and_gate(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT"], day="2026-01-10")
    payload = _snapshot_payload(["AVAX/USDT:USDT"], day="2026-01-11", profile="V2_RS_LIQUIDITY")
    payload["selected"].append(dict(payload["selected"][0]))  # duplicate -> invalid
    path = snapshot_dir / "hunter-pairs-20260111-audit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    _full_data(data_dir, ["SOL/USDT:USDT", "AVAX/USDT:USDT"])

    report = _run(snapshot_dir, data_dir, store_dir)
    assert len(report.cohorts) == 1
    assert len(report.invalid_cohorts) == 1
    assert report.cohorts[0].snapshot_date == "2026-01-10"
    assert report.invalid_cohorts[0].snapshot_date == "2026-01-11"
    assert report.invalid_cohorts[0].summary.metadata.get("invalid_snapshot") is True


def test_identical_rerun_no_op(tmp_path: Path) -> None:
    snapshot_dir, data_dir, store_dir = _setup_dirs(tmp_path)
    _write_snapshot(snapshot_dir, ["SOL/USDT:USDT"])
    _full_data(data_dir, ["SOL/USDT:USDT"])

    report1 = _run(snapshot_dir, data_dir, store_dir)
    report2 = _run(snapshot_dir, data_dir, store_dir)
    assert report1.cohorts[0].summary.fingerprint == report2.cohorts[0].summary.fingerprint
    assert report1.artifact_paths == report2.artifact_paths
