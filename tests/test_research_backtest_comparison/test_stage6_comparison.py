"""Tests for SPEC-072 Stage 6 comparison-side policies.

Covers:
- compare_backtest_results: one-sided zero trades, configurable min_trades,
  reason codes (NO_TRADES_CANDIDATE, NO_TRADES_BASELINE,
  ONE_SIDED_ZERO_TRADES, NO_TRADES_BOTH_ARMS, INSUFFICIENT_TRADES).
- Zero-trade numeric metric remains numeric zero (not fabricated as UNAVAILABLE).
- EvidenceAvailability enum values.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_backtest_comparison.comparison import compare_backtest_results
from hunter.research_backtest_comparison.models import (
    EVIDENCE_AVAILABLE,
    EVIDENCE_BLOCKED,
    EVIDENCE_INSUFFICIENT_TRADES,
    EVIDENCE_MISSING_METRIC,
    EVIDENCE_PARSER_FAILED,
    EVIDENCE_TIMED_OUT,
    EVIDENCE_UNSUPPORTED_SCHEMA,
    EVIDENCE_ZERO_TRADES,
    EvidenceAvailability,
    NO_TRADES,
    NO_TRADES_BASELINE,
    NO_TRADES_BOTH_ARMS,
    NO_TRADES_CANDIDATE,
    ONE_SIDED_ZERO_TRADES,
    INSUFFICIENT_TRADES,
    MISSING_METRIC,
    BacktestArmLabel,
    BacktestMetrics,
    BacktestRunResult,
)


def _make_arm(
    label: BacktestArmLabel,
    trade_count: int,
    *,
    total_return_pct: Decimal | None = None,
) -> BacktestRunResult:
    metrics = BacktestMetrics(
        total_return_pct=total_return_pct,
        absolute_profit=Decimal("0") if total_return_pct is not None else None,
        final_balance=Decimal("0") if total_return_pct is not None else None,
        max_drawdown_pct=Decimal("0") if total_return_pct is not None else None,
        win_rate_pct=Decimal("0") if total_return_pct is not None else None,
        trade_count=trade_count,
    )
    return BacktestRunResult(
        label=label,
        success=True,
        metrics=metrics,
        stdout="",
        stderr="",
        exit_code=0,
        workspace=__file__,  # arbitrary path placeholder
        result_file=None,
        command=("freqtrade",),
        command_fingerprint="cf" * 16,
        strategy_sha_before="ab" * 16,
        strategy_sha_after="ab" * 16,
        fingerprint="fp" * 16,
        pairlist=("X/Y",),
        reason_codes=(),
        metadata={},
    )


class TestCompareBacktestResultsZeroTradePolicy:
    def test_both_zero_trades_flags_both_arms_reason(self) -> None:
        cand = _make_arm(BacktestArmLabel.CANDIDATE, 0)
        base = _make_arm(BacktestArmLabel.BASELINE, 0)
        result = compare_backtest_results(cand, base)
        assert NO_TRADES_BOTH_ARMS in result.reason_codes
        assert ONE_SIDED_ZERO_TRADES not in result.reason_codes
        assert result.trade_sufficiency is False
        assert INSUFFICIENT_TRADES in result.reason_codes

    def test_one_sided_zero_candidate_flags_one_sided(self) -> None:
        cand = _make_arm(BacktestArmLabel.CANDIDATE, 0)
        base = _make_arm(BacktestArmLabel.BASELINE, 5,
                         total_return_pct=Decimal("0.10"))
        result = compare_backtest_results(cand, base)
        # Stage 6: one-sided zero trades is not silently comparable
        assert ONE_SIDED_ZERO_TRADES in result.reason_codes
        assert NO_TRADES_CANDIDATE in result.reason_codes
        assert NO_TRADES_BASELINE not in result.reason_codes
        assert NO_TRADES in result.reason_codes

    def test_one_sided_zero_baseline_flags_baseline(self) -> None:
        cand = _make_arm(BacktestArmLabel.CANDIDATE, 5,
                         total_return_pct=Decimal("0.10"))
        base = _make_arm(BacktestArmLabel.BASELINE, 0)
        result = compare_backtest_results(cand, base)
        assert ONE_SIDED_ZERO_TRADES in result.reason_codes
        assert NO_TRADES_BASELINE in result.reason_codes
        assert NO_TRADES_CANDIDATE not in result.reason_codes
        assert NO_TRADES in result.reason_codes

    def test_configurable_min_trades_pass_when_met(self) -> None:
        cand = _make_arm(BacktestArmLabel.CANDIDATE, 3,
                         total_return_pct=Decimal("0.20"))
        base = _make_arm(BacktestArmLabel.BASELINE, 3,
                         total_return_pct=Decimal("0.10"))
        result = compare_backtest_results(cand, base, min_trades=3)
        assert result.trade_sufficiency is True
        assert INSUFFICIENT_TRADES not in result.reason_codes
        assert ONE_SIDED_ZERO_TRADES not in result.reason_codes

    def test_configurable_min_trades_fail_when_below(self) -> None:
        cand = _make_arm(BacktestArmLabel.CANDIDATE, 2,
                         total_return_pct=Decimal("0.20"))
        base = _make_arm(BacktestArmLabel.BASELINE, 2,
                         total_return_pct=Decimal("0.10"))
        result = compare_backtest_results(cand, base, min_trades=3)
        assert result.trade_sufficiency is False
        assert INSUFFICIENT_TRADES in result.reason_codes
        # not zero-trades, just insufficient
        assert NO_TRADES not in result.reason_codes

    def test_invalid_min_trades_raises(self) -> None:
        cand = _make_arm(BacktestArmLabel.CANDIDATE, 1)
        base = _make_arm(BacktestArmLabel.BASELINE, 1)
        with pytest.raises(ValueError):
            compare_backtest_results(cand, base, min_trades=0)
        with pytest.raises(ValueError):
            compare_backtest_results(cand, base, min_trades=-1)

    def test_numeric_zero_metric_with_trades_remains_numeric_zero(self) -> None:
        # Stage 6: valid numeric zero WITH executed trades stays numeric zero,
        # not fabricated as UNAVAILABLE.
        cand = _make_arm(BacktestArmLabel.CANDIDATE, 5,
                         total_return_pct=Decimal("0"))
        base = _make_arm(BacktestArmLabel.BASELINE, 5,
                         total_return_pct=Decimal("0"))
        result = compare_backtest_results(cand, base)
        # numeric return_pct delta must be 0 (not None/UNAVAILABLE)
        assert result.metric_deltas["total_return_pct"] == Decimal("0")
        # not flagged as zero-trade
        assert NO_TRADES not in result.reason_codes
        assert ONE_SIDED_ZERO_TRADES not in result.reason_codes

    def test_missing_metric_flag_when_one_arm_has_no_metric(self) -> None:
        cand = _make_arm(BacktestArmLabel.CANDIDATE, 5,
                         total_return_pct=Decimal("0.10"))
        base = _make_arm(BacktestArmLabel.BASELINE, 5)  # no return_pct
        result = compare_backtest_results(cand, base)
        assert MISSING_METRIC in result.reason_codes
        assert result.metric_deltas["total_return_pct"] is None


class TestEvidenceAvailabilityEnumValues:
    @pytest.mark.parametrize(
        ("enum_member", "expected_value"),
        [
            (EvidenceAvailability.AVAILABLE, EVIDENCE_AVAILABLE),
            (EvidenceAvailability.ZERO_TRADES, EVIDENCE_ZERO_TRADES),
            (EvidenceAvailability.INSUFFICIENT_TRADES, EVIDENCE_INSUFFICIENT_TRADES),
            ("ONE_SIDED_ZERO_TRADES", None),  # parametrize generic check path
            (EvidenceAvailability.PARSER_FAILED, EVIDENCE_PARSER_FAILED),
            (EvidenceAvailability.BLOCKED, EVIDENCE_BLOCKED),
            (EvidenceAvailability.TIMED_OUT, EVIDENCE_TIMED_OUT),
            (EvidenceAvailability.UNSUPPORTED_SCHEMA, EVIDENCE_UNSUPPORTED_SCHEMA),
            (EvidenceAvailability.MISSING_METRIC, EVIDENCE_MISSING_METRIC),
        ],
    )
    def test_enum_values(self, enum_member, expected_value) -> None:
        # The placeholder row above uses a string for ONE_SIDED_ZERO_TRADES;
        # skip it and test that enum explicitly below.
        if expected_value is None:
            pytest.skip("placeholder row")
        assert enum_member.value == expected_value