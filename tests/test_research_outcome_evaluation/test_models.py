"""M1 tests: frozen models, safety flags, terminal states, serialization."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_outcome_evaluation.models import (
    DEFAULT_HORIZONS,
    NULL_REASON_CODES,
    PHASE_A_EMITTED_STATES,
    PENDING_HORIZON,
    REASON_FIRST_SNAPSHOT,
    REASON_ZERO_DENOMINATOR,
    RESEARCH_NOTICE,
    OutcomeEvaluationConfig,
    OutcomeEvaluationSafetyFlags,
    PairObservationRecord,
    SnapshotSummaryRecord,
    TerminalState,
    pair_observation_to_dict,
    parse_decimal,
    parse_horizon_hours,
    snapshot_summary_from_dict,
    snapshot_summary_to_dict,
)


# ---------------------------------------------------------------------------
# Safety flags (SPEC-074 fail-closed pattern)
# ---------------------------------------------------------------------------


def test_safety_flags_defaults_constructible() -> None:
    flags = OutcomeEvaluationSafetyFlags()
    assert flags.research_only is True
    assert flags.human_approval_required is True
    assert flags.live_trading_allowed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"research_only": False},
        {"execution_approval_granted": True},
        {"production_approval_granted": True},
        {"live_trading_allowed": True},
        {"automatic_execution_allowed": True},
        {"human_approval_required": False},
    ],
)
def test_safety_flags_fail_closed(overrides: dict) -> None:
    with pytest.raises(ValueError):
        OutcomeEvaluationSafetyFlags(**overrides)


# ---------------------------------------------------------------------------
# Terminal states
# ---------------------------------------------------------------------------


def test_terminal_state_enum_complete() -> None:
    members = {s.value for s in TerminalState}
    assert members == {
        "OUTCOME_AVAILABLE",
        "SNAPSHOT_INVALID",
        "OUTCOME_UNAVAILABLE_NO_SOURCE",
        "OUTCOME_UNAVAILABLE_GAP",
        "OUTCOME_UNAVAILABLE_INVALID_PRICE",
        "BENCHMARK_UNAVAILABLE",
        "OUTCOME_UNAVAILABLE_DELISTED",
    }


def test_phase_a_emitted_states_exclude_delisted() -> None:
    assert TerminalState.OUTCOME_UNAVAILABLE_DELISTED not in PHASE_A_EMITTED_STATES
    assert len(PHASE_A_EMITTED_STATES) == 6


def test_pending_horizon_is_not_a_terminal_state() -> None:
    assert PENDING_HORIZON not in {s.value for s in TerminalState}


# ---------------------------------------------------------------------------
# Horizon parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("token", "hours"),
    [("1d", 24), ("3d", 72), ("7d", 168), ("14d", 336), ("30d", 720)],
)
def test_parse_horizon_hours_valid(token: str, hours: int) -> None:
    assert parse_horizon_hours(token) == hours


@pytest.mark.parametrize("token", ["", "d", "0d", "1h", "1D", "1.5d", "-1d", "1dd", "abc"])
def test_parse_horizon_hours_invalid(token: str) -> None:
    with pytest.raises(ValueError):
        parse_horizon_hours(token)


def test_horizon_extension_without_schema_change() -> None:
    config = OutcomeEvaluationConfig(horizons=("1d", "14d"))
    assert parse_horizon_hours(config.horizons[1]) == 336


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def test_config_defaults() -> None:
    config = OutcomeEvaluationConfig()
    assert config.horizons == DEFAULT_HORIZONS
    assert config.min_window_coverage == Decimal("0.95")


def test_config_rejects_empty_horizons() -> None:
    with pytest.raises(ValueError):
        OutcomeEvaluationConfig(horizons=())


def test_config_rejects_duplicate_horizons() -> None:
    with pytest.raises(ValueError):
        OutcomeEvaluationConfig(horizons=("1d", "1d"))


def test_config_rejects_bad_horizon_token() -> None:
    with pytest.raises(ValueError):
        OutcomeEvaluationConfig(horizons=("1w",))


@pytest.mark.parametrize("value", ["0", "-0.5", "1.01", "2"])
def test_config_rejects_coverage_out_of_range(value: str) -> None:
    with pytest.raises(ValueError):
        OutcomeEvaluationConfig(min_window_coverage=Decimal(value))


def test_config_rejects_non_decimal_coverage() -> None:
    with pytest.raises(ValueError):
        OutcomeEvaluationConfig(min_window_coverage=0.95)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PairObservationRecord
# ---------------------------------------------------------------------------


def _available_observation(**overrides: object) -> PairObservationRecord:
    kwargs: dict = {
        "snapshot_date": "2026-01-10",
        "ranking_profile": "V2_RS_LIQUIDITY",
        "outcome_horizon": "1d",
        "pair": "SOL/USDT:USDT",
        "is_benchmark_pair": False,
        "terminal_state": TerminalState.OUTCOME_AVAILABLE,
        "rank_at_selection": 3,
        "reference_close": Decimal("100.5"),
        "realized_return": Decimal("1.25"),
    }
    kwargs.update(overrides)
    return PairObservationRecord(**kwargs)


def test_observation_available_constructs() -> None:
    record = _available_observation()
    assert record.terminal_state is TerminalState.OUTCOME_AVAILABLE
    assert record.safety_flags.research_only is True


def test_observation_unavailable_constructs_without_metrics() -> None:
    record = _available_observation(
        terminal_state=TerminalState.OUTCOME_UNAVAILABLE_NO_SOURCE,
        reference_close=None,
        realized_return=None,
    )
    assert record.terminal_state is TerminalState.OUTCOME_UNAVAILABLE_NO_SOURCE


@pytest.mark.parametrize(
    "state",
    [
        TerminalState.SNAPSHOT_INVALID,
        TerminalState.OUTCOME_UNAVAILABLE_NO_SOURCE,
        TerminalState.OUTCOME_UNAVAILABLE_GAP,
        TerminalState.OUTCOME_UNAVAILABLE_INVALID_PRICE,
        TerminalState.BENCHMARK_UNAVAILABLE,
    ],
)
def test_observation_accepts_all_phase_a_codes(state: TerminalState) -> None:
    record = _available_observation(
        terminal_state=state, reference_close=None, realized_return=None
    )
    assert record.terminal_state is state


def test_observation_rejects_reserved_delisted() -> None:
    with pytest.raises(ValueError, match="schema-reserved"):
        _available_observation(
            terminal_state=TerminalState.OUTCOME_UNAVAILABLE_DELISTED,
            reference_close=None,
            realized_return=None,
        )


def test_observation_available_requires_realized_return() -> None:
    with pytest.raises(ValueError, match="realized_return"):
        _available_observation(realized_return=None)


def test_observation_available_requires_reference_close() -> None:
    with pytest.raises(ValueError, match="reference_close"):
        _available_observation(reference_close=None)


def test_observation_rejects_non_positive_rank() -> None:
    with pytest.raises(ValueError, match="rank_at_selection"):
        _available_observation(rank_at_selection=0)


# ---------------------------------------------------------------------------
# SnapshotSummaryRecord
# ---------------------------------------------------------------------------


def _summary(**overrides: object) -> SnapshotSummaryRecord:
    kwargs: dict = {
        "snapshot_date": "2026-01-10",
        "ranking_profile": "V2_RS_LIQUIDITY",
        "outcome_horizon": "3d",
        "cohort_size": 2,
        "available_count": 1,
        "unavailable_count": 1,
        "days_since_previous_snapshot": 1,
        "turnover": Decimal("0.5"),
        "retention": Decimal("0.5"),
        "daily_data_availability": Decimal("1"),
    }
    kwargs.update(overrides)
    return SnapshotSummaryRecord(**kwargs)


def test_summary_constructs() -> None:
    summary = _summary()
    assert summary.top_5_return_pct is None
    assert summary.safety_flags.human_approval_required is True


def test_summary_rejects_count_mismatch() -> None:
    with pytest.raises(ValueError, match="cohort_size"):
        _summary(cohort_size=5)


def test_summary_rejects_negative_counts() -> None:
    with pytest.raises(ValueError):
        _summary(available_count=-1, cohort_size=0, unavailable_count=1)


def test_summary_first_snapshot_nulls_require_reasons() -> None:
    summary = _summary(
        days_since_previous_snapshot=None,
        previous_snapshot_reason=REASON_FIRST_SNAPSHOT,
        turnover=None,
        turnover_reason=REASON_FIRST_SNAPSHOT,
        retention=None,
        retention_reason=REASON_FIRST_SNAPSHOT,
    )
    assert summary.previous_snapshot_reason == REASON_FIRST_SNAPSHOT


def test_summary_null_days_without_reason_rejected() -> None:
    with pytest.raises(ValueError, match="previous_snapshot_reason"):
        _summary(days_since_previous_snapshot=None)


def test_summary_null_turnover_without_reason_rejected() -> None:
    with pytest.raises(ValueError, match="turnover_reason"):
        _summary(turnover=None)


def test_summary_null_retention_without_reason_rejected() -> None:
    with pytest.raises(ValueError, match="retention_reason"):
        _summary(retention=None)


def test_summary_null_availability_without_reason_rejected() -> None:
    with pytest.raises(ValueError, match="daily_data_availability_reason"):
        _summary(daily_data_availability=None)


def test_summary_rejects_unknown_reason_code() -> None:
    with pytest.raises(ValueError, match="unknown null-reason"):
        _summary(turnover=None, turnover_reason="SOMETHING_ELSE")


def test_summary_zero_denominator_reason_accepted() -> None:
    summary = _summary(turnover=None, turnover_reason=REASON_ZERO_DENOMINATOR)
    assert summary.turnover_reason == REASON_ZERO_DENOMINATOR
    assert summary.turnover_reason in NULL_REASON_CODES


def test_summary_legacy_missing_top_n_counts_default_to_none() -> None:
    payload = {
        "snapshot_date": "2026-01-10",
        "ranking_profile": "V2_RS_LIQUIDITY",
        "outcome_horizon": "1d",
        "cohort_size": 2,
        "available_count": 1,
        "unavailable_count": 1,
        "top_5_return_pct": "1.5",
        "days_since_previous_snapshot": 0,
        "turnover": "0.5",
        "retention": "0.5",
        "daily_data_availability": "1",
        "metadata": {"terminal_state_counts": {"OUTCOME_AVAILABLE": 1}},
    }
    summary = snapshot_summary_from_dict(payload)
    assert summary.top_5_available_count is None
    assert summary.top_10_available_count is None
    assert summary.top_20_available_count is None
    assert summary.top_30_available_count is None


def test_summary_persisted_zero_top_n_counts_are_zero() -> None:
    payload = {
        "snapshot_date": "2026-01-10",
        "ranking_profile": "V2_RS_LIQUIDITY",
        "outcome_horizon": "1d",
        "cohort_size": 2,
        "available_count": 1,
        "unavailable_count": 1,
        "top_5_return_pct": "1.5",
        "top_5_available_count": 0,
        "top_10_available_count": 0,
        "top_20_available_count": 0,
        "top_30_available_count": 0,
        "days_since_previous_snapshot": 0,
        "turnover": "0.5",
        "retention": "0.5",
        "daily_data_availability": "1",
        "metadata": {"terminal_state_counts": {"OUTCOME_AVAILABLE": 1}},
    }
    summary = snapshot_summary_from_dict(payload)
    assert summary.top_5_available_count == 0
    assert summary.top_10_available_count == 0
    assert summary.top_20_available_count == 0
    assert summary.top_30_available_count == 0


def test_summary_serialization_missing_counts_emitted_as_null() -> None:
    summary = snapshot_summary_to_dict(snapshot_summary_from_dict({
        "snapshot_date": "2026-01-10",
        "ranking_profile": "V2_RS_LIQUIDITY",
        "outcome_horizon": "1d",
        "cohort_size": 2,
        "available_count": 1,
        "unavailable_count": 1,
        "days_since_previous_snapshot": 0,
        "turnover": "0.5",
        "retention": "0.5",
        "daily_data_availability": "1",
        "metadata": {"terminal_state_counts": {"OUTCOME_AVAILABLE": 1}},
    }))
    assert summary["top_5_available_count"] is None
    assert summary["top_10_available_count"] is None
    assert summary["top_20_available_count"] is None
    assert summary["top_30_available_count"] is None


# ---------------------------------------------------------------------------
# Serialization (Decimal-as-string discipline)
# ---------------------------------------------------------------------------


def test_observation_serialization_decimals_as_strings() -> None:
    record = _available_observation(
        benchmark_return=Decimal("0.5"),
        benchmark_relative_return=Decimal("0.75"),
        mae_pct=Decimal("-2.5"),
        mfe_pct=Decimal("3.5"),
        realized_volatility_pct=Decimal("1.111111"),
        relative_strength_score=Decimal("55.5"),
        liquidity_score=Decimal("77.7"),
        coverage_ratio=Decimal("1"),
        reference_timestamp="2026-01-10T08:00:00+00:00",
        window_start="2026-01-10T08:00:00+00:00",
        window_end="2026-01-11T08:00:00+00:00",
    )
    payload = pair_observation_to_dict(record)
    assert payload["reference_close"] == "100.5"
    assert payload["realized_return"] == "1.25"
    assert payload["mae_pct"] == "-2.5"
    assert payload["benchmark_return"] == "0.5"
    assert payload["terminal_state"] == "OUTCOME_AVAILABLE"
    assert payload["safety_flags"]["research_only"] is True
    assert payload["_safety_notice"] == RESEARCH_NOTICE


def test_observation_serialization_nulls_stay_null() -> None:
    record = _available_observation(
        terminal_state=TerminalState.OUTCOME_UNAVAILABLE_GAP,
        reference_close=None,
        realized_return=None,
    )
    payload = pair_observation_to_dict(record)
    assert payload["reference_close"] is None
    assert payload["realized_return"] is None
    assert payload["mae_pct"] is None


def test_summary_serialization() -> None:
    summary = _summary(
        top_5_return_pct=Decimal("1.5"),
        spearman_rank_return=Decimal("0.333333"),
        benchmark_failure_reason=None,
    )
    payload = snapshot_summary_to_dict(summary)
    assert payload["top_5_return_pct"] == "1.5"
    assert payload["top_30_return_pct"] is None
    assert payload["spearman_rank_return"] == "0.333333"
    assert payload["safety_flags"]["human_approval_required"] is True
    assert payload["_safety_notice"] == RESEARCH_NOTICE


def test_parse_decimal_roundtrip() -> None:
    assert parse_decimal("1.25") == Decimal("1.25")
    assert parse_decimal(None) is None
    with pytest.raises(ValueError):
        parse_decimal("not-a-number")
