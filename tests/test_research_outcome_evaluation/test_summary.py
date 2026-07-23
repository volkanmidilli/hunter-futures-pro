"""M4 tests: summary generation helpers (turnover, retention, availability)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from hunter.research_outcome_evaluation.models import (
    REASON_FIRST_SNAPSHOT,
    REASON_ZERO_DENOMINATOR,
)
from hunter.research_outcome_evaluation.snapshot_reader import SnapshotCohort, SnapshotPairEntry
from hunter.research_outcome_evaluation.summary import (
    compute_daily_data_availability,
    compute_previous_snapshot_metrics,
    find_previous_snapshot,
)


def _cohort(day: str, pairs: list[str], profile: str = "V2_RS_LIQUIDITY") -> SnapshotCohort:
    return SnapshotCohort(
        snapshot_date=day,
        ranking_profile=profile,
        entries=tuple(
            SnapshotPairEntry(pair=p, rank=i + 1, relative_strength_score=None, liquidity_score=None)
            for i, p in enumerate(pairs)
        ),
        source_path=Path(f"hunter-pairs-{day.replace('-', '')}-audit.json"),
        source_fingerprint="fp",
    )


def test_first_snapshot_metrics() -> None:
    current = _cohort("2026-01-10", ["A/USDT:USDT"])
    metrics = compute_previous_snapshot_metrics(current=current, previous=None)
    assert metrics.days_since_previous_snapshot is None
    assert metrics.previous_snapshot_reason == REASON_FIRST_SNAPSHOT
    assert metrics.turnover is None
    assert metrics.turnover_reason == REASON_FIRST_SNAPSHOT
    assert metrics.retention is None
    assert metrics.retention_reason == REASON_FIRST_SNAPSHOT


def test_turnover_retention_formulas() -> None:
    previous = _cohort("2026-01-09", ["A/USDT:USDT", "B/USDT:USDT", "C/USDT:USDT", "D/USDT:USDT"])
    current = _cohort("2026-01-10", ["A/USDT:USDT", "B/USDT:USDT"])
    metrics = compute_previous_snapshot_metrics(current=current, previous=previous)
    # intersection = 2; turnover = 1 - 2/2 = 0; retention = 2/4 = 0.5
    assert metrics.days_since_previous_snapshot == 1
    assert metrics.turnover == Decimal("0.000000")
    assert metrics.retention == Decimal("0.500000")
    assert metrics.turnover_reason is None
    assert metrics.retention_reason is None


def test_turnover_zero_denominator() -> None:
    previous = _cohort("2026-01-09", ["A/USDT:USDT"])
    current = _cohort("2026-01-10", [])
    metrics = compute_previous_snapshot_metrics(current=current, previous=previous)
    assert metrics.turnover is None
    assert metrics.turnover_reason == REASON_ZERO_DENOMINATOR
    # retention: |intersection| / |previous| = 0/1 = 0
    assert metrics.retention == Decimal("0.000000")


def test_retention_zero_denominator() -> None:
    previous = _cohort("2026-01-09", [])
    current = _cohort("2026-01-10", ["A/USDT:USDT"])
    metrics = compute_previous_snapshot_metrics(current=current, previous=previous)
    assert metrics.retention is None
    assert metrics.retention_reason == REASON_ZERO_DENOMINATOR
    assert metrics.turnover == Decimal("1.000000")


def test_find_previous_snapshot_same_profile_only() -> None:
    a1 = _cohort("2026-01-08", ["X/USDT:USDT"], profile="V1_RS_OI")
    b1 = _cohort("2026-01-09", ["X/USDT:USDT"], profile="V2_RS_LIQUIDITY")
    b2 = _cohort("2026-01-10", ["X/USDT:USDT"], profile="V2_RS_LIQUIDITY")
    found = find_previous_snapshot(cohort=b2, valid_snapshots=(a1, b1, b2))
    assert found is b1
    # Profile with no earlier snapshot -> FIRST_SNAPSHOT path.
    found_none = find_previous_snapshot(cohort=a1, valid_snapshots=(a1, b1, b2))
    assert found_none is None


def test_find_previous_snapshot_skips_self_and_future() -> None:
    b1 = _cohort("2026-01-09", ["X/USDT:USDT"])
    b2 = _cohort("2026-01-10", ["X/USDT:USDT"])
    b3 = _cohort("2026-01-11", ["X/USDT:USDT"])
    found = find_previous_snapshot(cohort=b2, valid_snapshots=(b1, b2, b3))
    assert found is b1


def test_daily_data_availability() -> None:
    value, reason = compute_daily_data_availability(
        pairs=("A/USDT:USDT", "B/USDT:USDT", "C/USDT:USDT"),
        available_sources=frozenset({"A/USDT:USDT", "C/USDT:USDT"}),
    )
    assert value == (Decimal(2) / Decimal(3)).quantize(Decimal("0.000001"))
    assert reason is None


def test_daily_data_availability_zero_denominator() -> None:
    value, reason = compute_daily_data_availability(pairs=(), available_sources=frozenset())
    assert value is None
    assert reason == REASON_ZERO_DENOMINATOR
