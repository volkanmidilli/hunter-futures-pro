"""Cohort-level summary generation for SPEC-076 (M4).

Turnover and retention compare the current snapshot's selected pair set
against ``D_prev`` — the immediately preceding available valid immutable
snapshot for the same ``ranking_profile`` ordered by ``snapshot_date``
(source-based, never evaluation-store-based).  ``FIRST_SNAPSHOT`` means no
earlier valid immutable snapshot exists for the same ``ranking_profile``.

``daily_data_availability`` is the share of cohort members whose Feather
price source was discovered.  Turnover, retention, and availability are
duplicated identically across horizon summaries for reporting convenience.

Formulas (closed decisions):
- turnover  = 1 - |S_current ∩ S_previous| / |S_current|
- retention = |S_current ∩ S_previous| / |S_previous|
- Zero denominator -> ``None`` with an explicit reason code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from hunter.research_outcome_evaluation.models import (
    REASON_FIRST_SNAPSHOT,
    REASON_ZERO_DENOMINATOR,
    SnapshotSummaryRecord,
)
from hunter.research_outcome_evaluation.snapshot_reader import SnapshotCohort

PREVIOUS_RATIO_QUANT = Decimal("0.000001")


@dataclass(frozen=True)
class PreviousSnapshotMetrics:
    """Turnover/retention/day-delta values versus ``D_prev``."""

    days_since_previous_snapshot: int | None
    previous_snapshot_reason: str | None
    turnover: Decimal | None
    turnover_reason: str | None
    retention: Decimal | None
    retention_reason: str | None


def compute_previous_snapshot_metrics(
    *,
    current: SnapshotCohort,
    previous: SnapshotCohort | None,
) -> PreviousSnapshotMetrics:
    """Compute turnover, retention, and days-since-previous versus ``D_prev``."""
    if previous is None:
        return PreviousSnapshotMetrics(
            days_since_previous_snapshot=None,
            previous_snapshot_reason=REASON_FIRST_SNAPSHOT,
            turnover=None,
            turnover_reason=REASON_FIRST_SNAPSHOT,
            retention=None,
            retention_reason=REASON_FIRST_SNAPSHOT,
        )

    days = (date.fromisoformat(current.snapshot_date) - date.fromisoformat(previous.snapshot_date)).days
    current_pairs = {entry.pair for entry in current.entries}
    previous_pairs = {entry.pair for entry in previous.entries}
    intersection = current_pairs & previous_pairs

    if not current_pairs:
        turnover = None
        turnover_reason = REASON_ZERO_DENOMINATOR
    else:
        turnover = (
            Decimal(1) - Decimal(len(intersection)) / Decimal(len(current_pairs))
        ).quantize(PREVIOUS_RATIO_QUANT)
        turnover_reason = None

    if not previous_pairs:
        retention = None
        retention_reason = REASON_ZERO_DENOMINATOR
    else:
        retention = (Decimal(len(intersection)) / Decimal(len(previous_pairs))).quantize(
            PREVIOUS_RATIO_QUANT
        )
        retention_reason = None

    return PreviousSnapshotMetrics(
        days_since_previous_snapshot=days,
        previous_snapshot_reason=None,
        turnover=turnover,
        turnover_reason=turnover_reason,
        retention=retention,
        retention_reason=retention_reason,
    )


def compute_daily_data_availability(
    *,
    pairs: tuple[str, ...],
    available_sources: frozenset[str],
) -> tuple[Decimal | None, str | None]:
    """Share of cohort members with a discovered price source.

    Returns ``(value, reason)``; zero cohort size -> ``(None, ZERO_DENOMINATOR)``.
    """
    if not pairs:
        return None, REASON_ZERO_DENOMINATOR
    available = sum(1 for pair in pairs if pair in available_sources)
    value = (Decimal(available) / Decimal(len(pairs))).quantize(PREVIOUS_RATIO_QUANT)
    return value, None


def find_previous_snapshot(
    *,
    cohort: SnapshotCohort,
    valid_snapshots: tuple[SnapshotCohort, ...],
) -> SnapshotCohort | None:
    """Return ``D_prev``: the immediately preceding valid immutable snapshot
    for the same ``ranking_profile`` ordered by ``snapshot_date``.
    """
    candidates = [
        other
        for other in valid_snapshots
        if other.ranking_profile == cohort.ranking_profile
        and other.snapshot_date < cohort.snapshot_date
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda other: other.snapshot_date)
    return candidates[-1]
