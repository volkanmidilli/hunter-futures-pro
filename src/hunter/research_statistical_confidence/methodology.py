"""Research methodology policies for walk-forward experiments (SPEC-072).

Policies enforce:
- NoTradeWindowPolicy: windows where one or both arms produced zero trades.
- InsufficientEvidencePolicy: minimum trade count / available windows for evidence.
- QuartilePolicy: consistent quartile computation across MVP-66 and MVP-67.
- ConstantDeltaPolicy: detection of zero observed dispersion (constant deltas).
- WindowDependencePolicy: non-overlapping windows by default, dependency tracking.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from hunter.research_statistical_confidence.descriptive import _quartiles as _sc_quartiles
from hunter.research_statistical_confidence.models import (
    DependenceStatus,
    INSUFFICIENT_DATA,
    INSUFFICIENT_DISTINCT_VALUES,
    INSUFFICIENT_EVIDENCE_CODE,
    NON_OVERLAPPING,
    NO_TRADES_BASELINE,
    NO_TRADES_BOTH_ARMS,
    NO_TRADES_CANDIDATE,
    OVERLAPPING,
    OVERLAPPING_WINDOWS,
    UNKNOWN_DEPENDENCE,
    ZERO_OBSERVED_DISPERSION,
)
from hunter.research_walk_forward.aggregation import _quartiles as _wf_quartiles
from hunter.research_walk_forward.models import WalkForwardWindowResult

_BOUNDARY_FORMAT = "%Y%m%d"
_SECONDS_PER_DAY = 86_400


_TRADE_COUNT_METRIC = "trade_count"


@dataclass(frozen=True)
class PolicyResult:
    """Result of applying a methodology policy."""

    policy: str
    passed: bool
    reason_codes: tuple[str, ...]
    details: dict[str, Any]


def _get_trade_count(metrics: dict[str, Decimal | None]) -> int | None:
    """Return the trade count from a metrics dict, or None if unavailable."""
    value = metrics.get(_TRADE_COUNT_METRIC)
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


class NoTradeWindowPolicy:
    """Flag windows where candidate, baseline, or both arms produced no trades."""

    def __init__(self, flag_baseline: bool = True, flag_candidate: bool = True) -> None:
        self.flag_baseline = flag_baseline
        self.flag_candidate = flag_candidate

    def apply(self, windows: tuple[WalkForwardWindowResult, ...]) -> PolicyResult:
        """Apply the no-trade policy to the provided windows."""
        both_zero: list[int] = []
        candidate_zero: list[int] = []
        baseline_zero: list[int] = []
        reason_codes: list[str] = []

        for window in windows:
            idx = window.window_index
            cand = _get_trade_count(window.candidate_metrics)
            base = _get_trade_count(window.baseline_metrics)

            if cand is None or base is None:
                continue

            if cand == 0 and base == 0:
                both_zero.append(idx)
            elif cand == 0 and self.flag_candidate:
                candidate_zero.append(idx)
            elif base == 0 and self.flag_baseline:
                baseline_zero.append(idx)

        if both_zero:
            reason_codes.append(NO_TRADES_BOTH_ARMS)
        if candidate_zero:
            reason_codes.append(NO_TRADES_CANDIDATE)
        if baseline_zero:
            reason_codes.append(NO_TRADES_BASELINE)

        passed = not reason_codes

        return PolicyResult(
            policy="NoTradeWindowPolicy",
            passed=passed,
            reason_codes=tuple(reason_codes),
            details={
                "both_zero_window_indices": tuple(both_zero),
                "candidate_zero_window_indices": tuple(candidate_zero),
                "baseline_zero_window_indices": tuple(baseline_zero),
            },
        )


class InsufficientEvidencePolicy:
    """Require a minimum number of trades and available windows for evidence."""

    def __init__(
        self,
        *,
        min_trades_per_window: int = 1,
        min_available_windows: int = 1,
    ) -> None:
        self.min_trades_per_window = min_trades_per_window
        self.min_available_windows = min_available_windows

    def apply(self, windows: tuple[WalkForwardWindowResult, ...]) -> PolicyResult:
        """Apply the insufficient-evidence policy."""
        reason_codes: list[str] = []
        insufficient_windows: list[int] = []
        available_count = 0

        for window in windows:
            cand = _get_trade_count(window.candidate_metrics)
            base = _get_trade_count(window.baseline_metrics)
            if cand is None or base is None:
                continue
            available_count += 1
            if cand < self.min_trades_per_window or base < self.min_trades_per_window:
                insufficient_windows.append(window.window_index)

        if available_count < self.min_available_windows:
            reason_codes.append(INSUFFICIENT_DATA)
        if insufficient_windows:
            reason_codes.append(INSUFFICIENT_EVIDENCE_CODE)

        passed = not reason_codes

        return PolicyResult(
            policy="InsufficientEvidencePolicy",
            passed=passed,
            reason_codes=tuple(reason_codes),
            details={
                "available_windows": available_count,
                "min_available_windows": self.min_available_windows,
                "insufficient_window_indices": tuple(insufficient_windows),
                "min_trades_per_window": self.min_trades_per_window,
            },
        )


class QuartilePolicy:
    """Align quartile computation between MVP-66 and MVP-67.

    Both packages use the median-of-halves method. This policy verifies that
    Q1 and Q3 produced by the two implementations are identical for a given
    delta list, and returns a normalized quartile result.
    """

    def apply(self, deltas: list[Decimal]) -> PolicyResult:
        """Apply the quartile alignment policy."""
        if not deltas:
            return PolicyResult(
                policy="QuartilePolicy",
                passed=True,
                reason_codes=(INSUFFICIENT_DATA,),
                details={"q1": None, "q3": None, "iqr": None},
            )

        q1_wf, q3_wf, iqr_wf = _wf_quartiles(deltas)
        q1_sc, q3_sc = _sc_quartiles(deltas)

        # The two implementations are expected to align. If they do not, flag
        # a methodology inconsistency.
        aligned = q1_wf == q1_sc and q3_wf == q3_sc
        details = {
            "q1": q1_wf,
            "q3": q3_wf,
            "iqr": iqr_wf,
            "q1_mvp66": q1_wf,
            "q3_mvp66": q3_wf,
            "q1_mvp67": q1_sc,
            "q3_mvp67": q3_sc,
        }

        return PolicyResult(
            policy="QuartilePolicy",
            passed=aligned,
            reason_codes=tuple() if aligned else ("QUARTILE_MISMATCH",),
            details=details,
        )
class ConstantDeltaPolicy:
    """Detect zero observed dispersion (all deltas identical).

    Stage 7 / SPEC-072: also surfaces ``INSUFFICIENT_DISTINCT_VALUES`` when the
    number of distinct delta values is below ``min_distinct_values``. A
    constant non-zero sample triggers both ``ZERO_OBSERVED_DISPERSION`` and
    ``INSUFFICIENT_DISTINCT_VALUES`` (when ``min_distinct_values`` >= 2). The
    policy ``passed`` flag is False only when the sample has zero observed
    dispersion; insufficient distinct values alone is informational and does
    not block directional stability.
    """

    def __init__(self, min_distinct_values: int = 2) -> None:
        if not isinstance(min_distinct_values, int) or min_distinct_values < 1:
            raise ValueError("min_distinct_values must be a positive int (>=1)")
        self.min_distinct_values = min_distinct_values

    def apply(self, deltas: list[Decimal]) -> PolicyResult:
        """Apply the constant-delta policy."""
        if not deltas:
            return PolicyResult(
                policy="ConstantDeltaPolicy",
                passed=True,
                reason_codes=(INSUFFICIENT_DATA,),
                details={"constant": None, "value": None, "n": 0, "distinct": 0},
            )

        distinct_count = len({d for d in deltas})
        if len(deltas) == 1:
            return PolicyResult(
                policy="ConstantDeltaPolicy",
                passed=True,
                reason_codes=(INSUFFICIENT_DATA,),
                details={
                    "constant": None,
                    "value": str(deltas[0]),
                    "n": 1,
                    "distinct": distinct_count,
                },
            )

        first = deltas[0]
        constant = all(d == first for d in deltas)
        reason_codes_list: list[str] = []
        if constant:
            reason_codes_list.append(ZERO_OBSERVED_DISPERSION)
        if distinct_count < self.min_distinct_values:
            reason_codes_list.append(INSUFFICIENT_DISTINCT_VALUES)
        reason_codes: tuple[str, ...] = tuple(reason_codes_list)

        return PolicyResult(
            policy="ConstantDeltaPolicy",
            passed=not constant,
            reason_codes=reason_codes,
            details={
                "constant": constant,
                "value": str(first) if constant else None,
                "n": len(deltas),
                "distinct": distinct_count,
                "min_distinct_values": self.min_distinct_values,
                "std_dev": "0" if constant else None,
            },
        )


def _parse_boundary_date(value: str) -> int | None:
    """Parse a YYYYMMDD boundary string into an integer day ordinal.

    Returns None when the boundary cannot be parsed. Used to keep pure
    chronological comparisons for overlaps and to compute overlap durations
    in seconds.
    """
    import datetime as _dt

    try:
        parsed = _dt.datetime.strptime(value, _BOUNDARY_FORMAT).date()
    except (TypeError, ValueError):
        return None
    baseline = _dt.date(1970, 1, 1)
    return (parsed - baseline).days


def _overlap_seconds(a_start: str, a_end: str, b_start: str, b_end: str) -> int | None:
    """Return overlap duration in seconds of two closed YYYYMMDD intervals.

    Closed-interval overlap: max(starts) <= min(ends). Returns 0 when the
    boundaries touch exactly, None when any boundary is unparseable.
    """
    a_s = _parse_boundary_date(a_start)
    a_e = _parse_boundary_date(a_end)
    b_s = _parse_boundary_date(b_start)
    b_e = _parse_boundary_date(b_end)
    if a_s is None or a_e is None or b_s is None or b_e is None:
        return None
    start_days = max(a_s, b_s)
    end_days = min(a_e, b_e)
    if start_days > end_days:
        return 0
    return (end_days - start_days + 1) * _SECONDS_PER_DAY


class WindowDependencePolicy:
    """Require non-overlapping windows by default and track dependencies.

    Windows are considered dependent if their selection or evaluation periods
    overlap. Overlapping windows are flagged by default; callers may opt in to
    allow overlaps when the experiment design explicitly requires them (e.g.
    rolling window with lookahead-aware design), but the default is always
    non-overlapping.

    Stage 8 / SPEC-072: the policy returns an explicit ``DependenceStatus``
    (``NON_OVERLAPPING`` / ``OVERLAPPING`` / ``UNKNOWN``), the count of
    overlapping evaluation-window pairs, and the maximum overlap in seconds
    observed across evaluation windows. By default, independent-replication
    claims must exclude overlapping windows.
    """

    def __init__(self, allow_overlap: bool = False) -> None:
        self.allow_overlap = allow_overlap

    def _parse_boundary(self, value: str) -> int:
        """Parse a YYYYMMDD boundary into a sortable integer day ordinal.

        Raises ValueError for malformed boundaries.
        """
        ordinal = _parse_boundary_date(value)
        if ordinal is None:
            raise ValueError(f"invalid boundary string: {value!r}")
        return ordinal

    def _overlap(self, a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
        """Return True if two closed intervals [start, end] overlap."""
        a_s = self._parse_boundary(a_start)
        a_e = self._parse_boundary(a_end)
        b_s = self._parse_boundary(b_start)
        b_e = self._parse_boundary(b_end)
        return max(a_s, b_s) <= min(a_e, b_e)

    def apply(self, windows: tuple[WalkForwardWindowResult, ...]) -> PolicyResult:
        """Apply the window-dependence policy."""
        dependencies: list[tuple[int, int, str]] = []
        reason_codes: list[str] = []
        overlapping_eval_pair_count = 0
        max_overlap_seconds = 0
        unknown_boundary_seen = False

        for i in range(len(windows)):
            for j in range(i + 1, len(windows)):
                wi = windows[i].window
                wj = windows[j].window
                if self._overlap(
                    wi.selection_start,
                    wi.selection_end,
                    wj.selection_start,
                    wj.selection_end,
                ):
                    dependencies.append((i, j, "selection"))
                eval_seconds = _overlap_seconds(
                    wi.evaluation_start,
                    wi.evaluation_end,
                    wj.evaluation_start,
                    wj.evaluation_end,
                )
                if eval_seconds is None:
                    unknown_boundary_seen = True
                elif eval_seconds > 0:
                    dependencies.append((i, j, "evaluation"))
                    overlapping_eval_pair_count += 1
                    if eval_seconds > max_overlap_seconds:
                        max_overlap_seconds = eval_seconds

        if overlapping_eval_pair_count > 0 and not self.allow_overlap:
            reason_codes.append(OVERLAPPING_WINDOWS)
        passed = not (overlapping_eval_pair_count > 0 and not self.allow_overlap)

        if overlapping_eval_pair_count > 0:
            status = DependenceStatus.OVERLAPPING
        elif unknown_boundary_seen:
            status = DependenceStatus.UNKNOWN
        else:
            status = DependenceStatus.NON_OVERLAPPING
        if status is not DependenceStatus.NON_OVERLAPPING and (
            not self.allow_overlap or status is DependenceStatus.UNKNOWN
        ):
            reason_codes.append(status.value)

        return PolicyResult(
            policy="WindowDependencePolicy",
            passed=passed,
            reason_codes=tuple(reason_codes),
            details={
                "allow_overlap": self.allow_overlap,
                "status": status.value,
                "overlapping_eval_pair_count": overlapping_eval_pair_count,
                "max_overlap_seconds": max_overlap_seconds,
                "dependencies": [
                    {"window_a": a, "window_b": b, "kind": kind}
                    for a, b, kind in dependencies
                ],
            },
        )


class ResearchMethodologyPolicy:
    """Combined methodology policy that runs all sub-policies on a window list."""

    def __init__(
        self,
        *,
        min_trades_per_window: int = 1,
        min_available_windows: int = 1,
        allow_overlapping_windows: bool = False,
    ) -> None:
        self.no_trade_policy = NoTradeWindowPolicy()
        self.insufficient_evidence_policy = InsufficientEvidencePolicy(
            min_trades_per_window=min_trades_per_window,
            min_available_windows=min_available_windows,
        )
        self.window_dependence_policy = WindowDependencePolicy(
            allow_overlap=allow_overlapping_windows
        )
        self.quartile_policy = QuartilePolicy()
        self.constant_delta_policy = ConstantDeltaPolicy()

    def apply(
        self,
        windows: tuple[WalkForwardWindowResult, ...],
        metric_deltas: dict[str, list[Decimal]] | None = None,
    ) -> tuple[PolicyResult, ...]:
        """Apply all methodology policies and return individual results."""
        results: list[PolicyResult] = [
            self.no_trade_policy.apply(windows),
            self.insufficient_evidence_policy.apply(windows),
            self.window_dependence_policy.apply(windows),
        ]

        if metric_deltas is not None:
            for deltas in metric_deltas.values():
                results.append(self.quartile_policy.apply(deltas))
                results.append(self.constant_delta_policy.apply(deltas))

        return tuple(results)


__all__ = [
    "PolicyResult",
    "NoTradeWindowPolicy",
    "InsufficientEvidencePolicy",
    "QuartilePolicy",
    "ConstantDeltaPolicy",
    "WindowDependencePolicy",
    "ResearchMethodologyPolicy",
]
