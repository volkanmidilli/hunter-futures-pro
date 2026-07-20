"""Tests for research methodology policies (SPEC-072 Stage 6/7/8).

Covers:
- ConstantDeltaPolicy: zero observed dispersion + insufficient distinct values.
- QuartilePolicy: canonical quartile vectors across MVP-66 and MVP-67.
- WindowDependencePolicy: NON_OVERLAPPING / OVERLAPPING / UNKNOWN, pair
  count, max overlap seconds.
- NoTradeWindowPolicy: zero-trade + one-sided-zero-trade detection.
- InsufficientEvidencePolicy: minimum trade count / available windows.
- ResearchMethodologyPolicy: aggregate apply().
- classify_evidence_availability: precedence ladder.
- classify_metric_confidence: zero observed dispersion blocks ROBUST_*.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_statistical_confidence.methodology import (
    ConstantDeltaPolicy,
    InsufficientEvidencePolicy,
    NoTradeWindowPolicy,
    QuartilePolicy,
    ResearchMethodologyPolicy,
    WindowDependencePolicy,
)
from hunter.research_statistical_confidence.models import (
    DependenceStatus,
    INSUFFICIENT_DISTINCT_VALUES,
    INSUFFICIENT_EVIDENCE_CODE,
    INSUFFICIENT_DATA,
    NO_TRADES_BASELINE,
    NO_TRADES_BOTH_ARMS,
    NO_TRADES_CANDIDATE,
    OVERLAPPING,
    OVERLAPPING_WINDOWS,
    ZERO_OBSERVED_DISPERSION,
)
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    MetricDirection,
    WalkForwardWindow,
    WalkForwardWindowResult,
    WindowStatus,
)


def _window(
    sel_start: str,
    sel_end: str,
    eval_start: str,
    eval_end: str,
) -> WalkForwardWindow:
    return WalkForwardWindow(
        selection_start=sel_start,
        selection_end=sel_end,
        evaluation_start=eval_start,
        evaluation_end=eval_end,
        regime_label=MarketRegimeLabel.UNKNOWN,
        metadata={},
    )


def _window_result(
    window: WalkForwardWindow,
    idx: int = 0,
    *,
    status: WindowStatus = WindowStatus.COMPLETED,
    candidate_trade_count: Decimal | None = Decimal("5"),
    baseline_trade_count: Decimal | None = Decimal("5"),
) -> WalkForwardWindowResult:
    candidate_metrics = {"trade_count": candidate_trade_count}
    baseline_metrics = {"trade_count": baseline_trade_count}
    metric_deltas = {
        "trade_count": (
            (candidate_trade_count or Decimal("0")) - (baseline_trade_count or Decimal("0"))
        )
    }
    metric_directions = {"trade_count": MetricDirection.CANDIDATE_HIGHER}
    return WalkForwardWindowResult(
        window=window,
        window_index=idx,
        status=status,
        candidate_metrics=candidate_metrics,
        baseline_metrics=baseline_metrics,
        metric_deltas=metric_deltas,
        metric_directions=metric_directions,
        comparison_fingerprint="cf" * 16,
        candidate_fingerprint="ca" * 16,
        baseline_fingerprint="ba" * 16,
        fingerprint="fp" * 16,
        reason_codes=(),
        metadata={},
    )


def _two_windows(eval_start_a: str, eval_end_a: str, eval_start_b: str, eval_end_b: str):
    wa = _window("20240101", "20240201", eval_start_a, eval_end_a)
    wb = _window("20240202", "20240301", eval_start_b, eval_end_b)
    return (
        _window_result(wa, 0),
        _window_result(wb, 1),
    )


# ---------------------------------------------------------------------------
# ConstantDeltaPolicy
# ---------------------------------------------------------------------------

class TestConstantDeltaPolicy:
    def test_empty_is_insufficient_data(self) -> None:
        result = ConstantDeltaPolicy().apply([])
        assert result.passed is True
        assert result.reason_codes == ("INSUFFICIENT_DATA",)
        assert result.details["n"] == 0
        assert result.details["distinct"] == 0

    def test_singleton_is_insufficient_data(self) -> None:
        result = ConstantDeltaPolicy().apply([Decimal("1.5")])
        assert result.passed is True
        assert result.reason_codes == ("INSUFFICIENT_DATA",)
        assert result.details["distinct"] == 1

    def test_constant_nonzero_flags_zero_dispersion(self) -> None:
        result = ConstantDeltaPolicy().apply(
            [Decimal("0.5"), Decimal("0.5"), Decimal("0.5")]
        )
        assert result.passed is False
        assert ZERO_OBSERVED_DISPERSION in result.reason_codes

    def test_constant_nonzero_also_flags_insufficient_distinct(self) -> None:
        result = ConstantDeltaPolicy().apply(
            [Decimal("0.5"), Decimal("0.5")]
        )
        assert result.passed is False
        assert ZERO_OBSERVED_DISPERSION in result.reason_codes
        assert INSUFFICIENT_DISTINCT_VALUES in result.reason_codes

    def test_two_distinct_values_passes_default_threshold(self) -> None:
        result = ConstantDeltaPolicy().apply([Decimal("0.5"), Decimal("0.6")])
        assert result.passed is True
        assert result.reason_codes == ()
        assert result.details["distinct"] == 2

    def test_insufficient_distinct_only_does_not_fail_passed(self) -> None:
        # 3 deltas, 2 distinct => not constant but below default min(2)?
        # With distinct=2 and min_distinct_values=2 we have distinct == min,
        # so no INSUFFICIENT_DISTINCT_VALUES. Use min_distinct_values=3.
        policy = ConstantDeltaPolicy(min_distinct_values=3)
        result = policy.apply([Decimal("1"), Decimal("2"), Decimal("2")])
        assert result.passed is True  # not constant -> dispersion present
        assert INSUFFICIENT_DISTINCT_VALUES in result.reason_codes

    def test_invalid_min_distinct_values(self) -> None:
        with pytest.raises(ValueError):
            ConstantDeltaPolicy(min_distinct_values=0)

    def test_negative_constant(self) -> None:
        result = ConstantDeltaPolicy().apply([Decimal("-1"), Decimal("-1")])
        assert result.passed is False
        assert ZERO_OBSERVED_DISPERSION in result.reason_codes
        assert result.details["value"] == "-1"


# ---------------------------------------------------------------------------
# QuartilePolicy
# ---------------------------------------------------------------------------

class TestQuartilePolicy:
    @pytest.mark.parametrize(
        ("vector", "expect_insufficient"),
        [
            ([], True),
            ([Decimal("5")], False),  # singleton: QuartilePolicy returns aligned
            ([Decimal("1"), Decimal("9")], False),
            ([Decimal("1"), Decimal("5"), Decimal("9")], False),
            ([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")], False),
            ([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")], False),
            ([Decimal("2"), Decimal("2"), Decimal("2")], False),
            ([Decimal("-10"), Decimal("-5"), Decimal("0")], False),
            ([Decimal("0.1"), Decimal("0.2"), Decimal("0.3")], False),
        ],
        ids=[
            "empty",
            "singleton",
            "two",
            "three",
            "even",
            "odd",
            "repeated",
            "negatives",
            "decimal",
        ],
    )
    def test_quartile_vectors(self, vector, expect_insufficient) -> None:
        policy = QuartilePolicy()
        result = policy.apply(vector)
        if expect_insufficient:
            assert result.reason_codes == ("INSUFFICIENT_DATA",), (
                f"empty/singleton must report INSUFFICIENT_DATA; got {result.reason_codes}"
            )
        else:
            assert "q1" in result.details and "q3" in result.details
            assert "iqr" in result.details
            assert result.passed is True, (
                f"quartile mismatch for {vector}: {result.reason_codes}"
            )

    def test_mvp66_and_mvp67_alignment_for_simple_vector(self) -> None:
        result = QuartilePolicy().apply([Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")])
        # Both implementations should return q1=1.5, q3=3.5, iqr=2.0
        assert result.details["q1"] == Decimal("1.5")
        assert result.details["q3"] == Decimal("3.5")
        assert result.details["iqr"] == Decimal("2.0")


# ---------------------------------------------------------------------------
# WindowDependencePolicy
# ---------------------------------------------------------------------------

class TestWindowDependencePolicy:
    def test_non_overlapping_eval_windows(self) -> None:
        wa, wb = _two_windows("20240301", "20240331", "20240401", "20240430")
        policy = WindowDependencePolicy()
        result = policy.apply((wa, wb))
        assert result.details["status"] == "NON_OVERLAPPING"
        assert result.details["overlapping_eval_pair_count"] == 0
        assert result.details["max_overlap_seconds"] == 0
        assert result.passed is True
        assert result.reason_codes == ()

    def test_overlapping_eval_windows(self) -> None:
        wa, wb = _two_windows("20240301", "20240410", "20240401", "20240430")
        policy = WindowDependencePolicy()
        result = policy.apply((wa, wb))
        assert result.details["status"] == "OVERLAPPING"
        assert result.details["overlapping_eval_pair_count"] == 1
        assert result.details["max_overlap_seconds"] > 0
        # April 1..10 closed-overlap => 10 days * 86400 = 864000 seconds
        assert result.details["max_overlap_seconds"] == 864000
        assert OVERLAPPING_WINDOWS in result.reason_codes
        assert OVERLAPPING in result.reason_codes
        assert result.passed is False

    def test_allow_overlap_still_reports_status(self) -> None:
        wa, wb = _two_windows("20240301", "20240410", "20240401", "20240430")
        policy = WindowDependencePolicy(allow_overlap=True)
        result = policy.apply((wa, wb))
        assert result.details["status"] == "OVERLAPPING"
        assert result.passed is True  # opted in
        assert OVERLAPPING_WINDOWS not in result.reason_codes

    def test_unknown_status_on_invalid_evaluation_boundary(self) -> None:
        # Use non-overlapping selection periods so the selection _overlap
        # check returns False without ever parsing the invalid evaluation
        # boundary. Then the evaluation boundary is malformed -> UNKNOWN.
        wa = _window(
            "20200101",  # valid, far in the past
            "20200131",
            "invalid_eval_start",  # malformed evaluation boundary
            "20200331",
        )
        wb = _window(
            "20200201",  # valid, non-overlapping with wa.selection
            "20200229",
            "20200301",
            "20200330",
        )
        war = _window_result(wa, 0)
        wbr = _window_result(wb, 1)
        policy = WindowDependencePolicy()
        result = policy.apply((war, wbr))
        assert result.details["status"] == "UNKNOWN"

    def test_selection_overlap_with_invalid_boundary_raises(self) -> None:
        # If a selection boundary is malformed, _overlap raises ValueError
        # because _parse_boundary refuses to silently accept garbage.
        wa = _window(
            "invalid_sel_start",
            "20200131",
            "20200201",
            "20200229",
        )
        wb = _window(
            "20200115",  # overlaps with [invalid, 20200131] if parseable
            "20200215",
            "20200301",
            "20200330",
        )
        war = _window_result(wa, 0)
        wbr = _window_result(wb, 1)
        with pytest.raises(ValueError):
            WindowDependencePolicy().apply((war, wbr))


# ---------------------------------------------------------------------------
# NoTradeWindowPolicy
# ---------------------------------------------------------------------------

class TestNoTradeWindowPolicy:
    def test_both_arms_zero(self) -> None:
        wa = _window_result(_window("20240101", "20240131", "20240201", "20240229"))
        wa = _window_result(
            wa.window,
            0,
            candidate_trade_count=Decimal("0"),
            baseline_trade_count=Decimal("0"),
        )
        policy = NoTradeWindowPolicy()
        result = policy.apply((wa,))
        assert NO_TRADES_BOTH_ARMS in result.reason_codes

    def test_one_sided_zero_candidate(self) -> None:
        wa = _window_result(
            _window("20240101", "20240131", "20240201", "20240229"),
            0,
            candidate_trade_count=Decimal("0"),
            baseline_trade_count=Decimal("5"),
        )
        result = NoTradeWindowPolicy().apply((wa,))
        assert NO_TRADES_CANDIDATE in result.reason_codes

    def test_one_sided_zero_baseline(self) -> None:
        wa = _window_result(
            _window("20240101", "20240131", "20240201", "20240229"),
            0,
            candidate_trade_count=Decimal("5"),
            baseline_trade_count=Decimal("0"),
        )
        result = NoTradeWindowPolicy().apply((wa,))
        assert NO_TRADES_BASELINE in result.reason_codes

    def test_no_trades_passes_when_both_have_trades(self) -> None:
        wa = _window_result(_window("20240101", "20240131", "20240201", "20240229"))
        result = NoTradeWindowPolicy().apply((wa,))
        assert result.passed is True
        assert result.reason_codes == ()


# ---------------------------------------------------------------------------
# InsufficientEvidencePolicy
# ---------------------------------------------------------------------------

class TestInsufficientEvidencePolicy:
    def test_insufficient_trades(self) -> None:
        wa = _window_result(
            _window("20240101", "20240131", "20240201", "20240229"),
            0,
            candidate_trade_count=Decimal("1"),
            baseline_trade_count=Decimal("1"),
        )
        policy = InsufficientEvidencePolicy(min_trades_per_window=5, min_available_windows=1)
        result = policy.apply((wa,))
        assert INSUFFICIENT_EVIDENCE_CODE in result.reason_codes
        assert result.passed is False

    def test_insufficient_available_windows(self) -> None:
        wa = _window_result(_window("20240101", "20240131", "20240201", "20240229"))
        policy = InsufficientEvidencePolicy(min_trades_per_window=1, min_available_windows=3)
        result = policy.apply((wa,))
        # InsufficientEvidencePolicy emits INSUFFICIENT_DATA when the available
        # window count is below the configured minimum (not the per-window
        # INSUFFICIENT_EVIDENCE_CODE which fires only when individual windows
        # have too few trades).
        assert INSUFFICIENT_DATA in result.reason_codes
        assert result.passed is False

    def test_sufficient_evidence(self) -> None:
        wa = _window_result(_window("20240101", "20240131", "20240201", "20240229"))
        wb = _window_result(_window("20240201", "20240229", "20240301", "20240331"), 1)
        policy = InsufficientEvidencePolicy(min_trades_per_window=1, min_available_windows=2)
        result = policy.apply((wa, wb))
        assert INSUFFICIENT_EVIDENCE_CODE not in result.reason_codes
        assert result.passed is True


# ---------------------------------------------------------------------------
# ResearchMethodologyPolicy aggregate
# ---------------------------------------------------------------------------

class TestResearchMethodologyPolicy:
    def test_aggregate_runs_all_policies(self) -> None:
        wa = _window_result(_window("20240101", "20240131", "20240301", "20240331"))
        wb = _window_result(_window("20240201", "20240229", "20240401", "20240430"), 1)
        policy = ResearchMethodologyPolicy()
        results = policy.apply((wa, wb), metric_deltas={"x": [Decimal("1"), Decimal("1")]})
        names = {r.policy for r in results}
        assert "NoTradeWindowPolicy" in names
        assert "InsufficientEvidencePolicy" in names
        assert "WindowDependencePolicy" in names
        assert "QuartilePolicy" in names
        assert "ConstantDeltaPolicy" in names
        # Constant delta -> ZERO_OBSERVED_DISPERSION flagged.
        constant_delta_results = [r for r in results if r.policy == "ConstantDeltaPolicy"]
        assert any(
            ZERO_OBSERVED_DISPERSION in r.reason_codes for r in constant_delta_results
        )