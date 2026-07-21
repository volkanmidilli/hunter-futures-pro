"""Focused and adversarial tests for hunter.pairlist_export.feather_adapter (SPEC-075)."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
import pytest

from hunter.pairlist_export.feather_adapter import (
    average_rank_percentile,
    build_daily_close_rows,
    build_ranking_input_v2_from_feather,
    compute_data_quality_pct,
    compute_liquidity_raw,
    discover_feather_files,
    load_and_validate_series,
)
from hunter.pairlist_export.feather_models import (
    BTC_BENCHMARK_MISSING,
    DATA_COMPLETE,
    DATA_GAPS_PRESENT,
    DUPLICATE_CANDLES,
    DUPLICATE_PAIR_SOURCE,
    FILENAME_NOT_MATCHED,
    FUTURE_CANDLE,
    FeatherAdapterError,
    FeatherFileRef,
    HIDDEN_OR_TEMP_FILE,
    INSUFFICIENT_LOOKBACK,
    INVALID_CLOSE,
    INVALID_VOLUME,
    MISSING_COLUMN,
    OUT_OF_ORDER_CANDLES,
    SYMLINK_REJECTED,
)
from hunter.pairlist_export.ranking_input_v2 import RankingProfile

from tests.test_pairlist_export._feather_fixtures import (
    build_dataframe,
    hourly_range,
    write_feather,
    write_full_history_pair,
)

AS_OF = date(2026, 7, 21)
NOW = datetime(2026, 7, 21, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Discovery / containment / filename parsing.
# ---------------------------------------------------------------------------


def test_discover_includes_valid_1h_futures_files(tmp_path) -> None:
    write_full_history_pair(tmp_path, "BTC", AS_OF)
    write_full_history_pair(tmp_path, "XRP", AS_OF)

    result = discover_feather_files(tmp_path)

    assert result.btc_ref is not None
    assert result.btc_ref.pair == "BTC/USDT:USDT"
    assert {ref.pair for ref in result.included} == {"XRP/USDT:USDT"}
    assert result.excluded == ()


@pytest.mark.parametrize(
    "filename",
    [
        "BTC_USDT-1h.feather",  # spot
        "BTC_USDT_USDT-1h-mark.feather",  # mark price
        "BTC_USDT_USDT-1h-funding_rate.feather",  # funding rate
        "BTC_USDT_USDT-4h-futures.feather",  # other timeframe
        "BTC_USDT_USDT-15m-futures.feather",  # other timeframe
        "not_a_pair_file.feather",  # malformed
        "btc_USDT_USDT-1h-futures.feather",  # lowercase base
    ],
)
def test_discover_excludes_non_matching_filenames(tmp_path, filename: str) -> None:
    (tmp_path / filename).write_bytes(b"not-a-real-feather-file")

    result = discover_feather_files(tmp_path)

    assert result.included == ()
    assert result.btc_ref is None
    assert len(result.excluded) == 1
    assert result.excluded[0].reason_codes == (FILENAME_NOT_MATCHED,)


@pytest.mark.parametrize("filename", [".BTC_USDT_USDT-1h-futures.feather", "BTC_USDT_USDT-1h-futures.feather.tmp"])
def test_discover_excludes_hidden_and_temp_files(tmp_path, filename: str) -> None:
    (tmp_path / filename).write_bytes(b"x")

    result = discover_feather_files(tmp_path)

    assert result.excluded[0].reason_codes == (HIDDEN_OR_TEMP_FILE,)


def test_discover_rejects_symlinks(tmp_path) -> None:
    outside = tmp_path.parent / "outside_XRP_USDT_USDT-1h-futures.feather"
    write_full_history_pair(tmp_path.parent, "OUTSIDE", AS_OF)
    real_outside = tmp_path.parent / "OUTSIDE_USDT_USDT-1h-futures.feather"

    link_path = tmp_path / "XRP_USDT_USDT-1h-futures.feather"
    os.symlink(real_outside, link_path)

    result = discover_feather_files(tmp_path)

    assert result.included == ()
    assert result.excluded[0].reason_codes == (SYMLINK_REJECTED,)


def test_discover_rejects_duplicate_hardlinked_source(tmp_path) -> None:
    real_path = write_full_history_pair(tmp_path, "BTC", AS_OF)
    hardlink_path = tmp_path / "XBT_USDT_USDT-1h-futures.feather"
    os.link(real_path, hardlink_path)

    result = discover_feather_files(tmp_path)

    # BTC (first, sorted) wins; XBT is the duplicate-source exclusion.
    assert result.btc_ref is not None
    dup = [e for e in result.excluded if e.reason_codes == (DUPLICATE_PAIR_SOURCE,)]
    assert len(dup) == 1
    assert dup[0].path.name == "XBT_USDT_USDT-1h-futures.feather"


def test_discover_raises_for_missing_data_dir(tmp_path) -> None:
    from hunter.pairlist_export.feather_models import FeatherDiscoveryError

    with pytest.raises(FeatherDiscoveryError):
        discover_feather_files(tmp_path / "does-not-exist")


# ---------------------------------------------------------------------------
# Schema / timestamp / value validation.
# ---------------------------------------------------------------------------


def test_missing_column_is_excluded(tmp_path) -> None:
    timestamps = hourly_range(AS_OF, 90)
    df = build_dataframe(timestamps)
    df = df.drop(columns=["volume"])
    path = write_feather(tmp_path, "XRP", df)
    ref = FeatherFileRef(path=path, base_symbol="XRP", pair="XRP/USDT:USDT")

    windowed, exclusion = load_and_validate_series(ref, AS_OF, NOW)

    assert windowed is None
    assert exclusion is not None
    assert exclusion.reason_codes == (MISSING_COLUMN,)


def test_duplicate_timestamps_excluded(tmp_path) -> None:
    timestamps = hourly_range(AS_OF, 90)
    timestamps[5] = timestamps[4]  # inject a duplicate
    df = build_dataframe(timestamps)
    path = write_feather(tmp_path, "XRP", df)
    ref = FeatherFileRef(path=path, base_symbol="XRP", pair="XRP/USDT:USDT")

    windowed, exclusion = load_and_validate_series(ref, AS_OF, NOW)

    assert windowed is None
    assert DUPLICATE_CANDLES in exclusion.reason_codes


def test_out_of_order_timestamps_excluded(tmp_path) -> None:
    timestamps = hourly_range(AS_OF, 90)
    timestamps[3], timestamps[10] = timestamps[10], timestamps[3]  # scramble raw order
    df = build_dataframe(timestamps)
    path = write_feather(tmp_path, "XRP", df)
    ref = FeatherFileRef(path=path, base_symbol="XRP", pair="XRP/USDT:USDT")

    windowed, exclusion = load_and_validate_series(ref, AS_OF, NOW)

    assert windowed is None
    assert OUT_OF_ORDER_CANDLES in exclusion.reason_codes


@pytest.mark.parametrize("bad_close", [float("nan"), float("inf"), 0.0, -5.0])
def test_invalid_close_excluded(tmp_path, bad_close: float) -> None:
    timestamps = hourly_range(AS_OF, 90)
    df = build_dataframe(timestamps)
    df.loc[0, "close"] = bad_close
    path = write_feather(tmp_path, "XRP", df)
    ref = FeatherFileRef(path=path, base_symbol="XRP", pair="XRP/USDT:USDT")

    windowed, exclusion = load_and_validate_series(ref, AS_OF, NOW)

    assert windowed is None
    assert exclusion.reason_codes == (INVALID_CLOSE,)


@pytest.mark.parametrize("bad_volume", [float("nan"), float("-inf"), -1.0])
def test_invalid_volume_excluded(tmp_path, bad_volume: float) -> None:
    timestamps = hourly_range(AS_OF, 90)
    df = build_dataframe(timestamps)
    df.loc[0, "volume"] = bad_volume
    path = write_feather(tmp_path, "XRP", df)
    ref = FeatherFileRef(path=path, base_symbol="XRP", pair="XRP/USDT:USDT")

    windowed, exclusion = load_and_validate_series(ref, AS_OF, NOW)

    assert windowed is None
    assert exclusion.reason_codes == (INVALID_VOLUME,)


def test_future_candle_excluded(tmp_path) -> None:
    timestamps = hourly_range(AS_OF, 90)
    timestamps[-1] = NOW + timedelta(days=365)
    df = build_dataframe(timestamps)
    path = write_feather(tmp_path, "XRP", df)
    ref = FeatherFileRef(path=path, base_symbol="XRP", pair="XRP/USDT:USDT")

    windowed, exclusion = load_and_validate_series(ref, AS_OF, NOW)

    assert windowed is None
    assert FUTURE_CANDLE in exclusion.reason_codes


def test_insufficient_lookback_when_window_empty(tmp_path) -> None:
    old_as_of = date(2020, 1, 1)
    timestamps = hourly_range(old_as_of, 5)  # far outside AS_OF's 90-day window
    df = build_dataframe(timestamps)
    path = write_feather(tmp_path, "XRP", df)
    ref = FeatherFileRef(path=path, base_symbol="XRP", pair="XRP/USDT:USDT")

    windowed, exclusion = load_and_validate_series(ref, AS_OF, NOW)

    assert windowed is None
    assert exclusion.reason_codes == (INSUFFICIENT_LOOKBACK,)


def test_full_and_partial_coverage_data_quality(tmp_path) -> None:
    full_ts = hourly_range(AS_OF, 90)
    full_df = build_dataframe(full_ts)
    full_windowed = full_df  # already exactly the window
    full_pct, full_reason = compute_data_quality_pct(full_windowed)
    assert full_pct == Decimal("100.00")
    assert full_reason == DATA_COMPLETE

    partial_ts = hourly_range(AS_OF, 90)[: 20 * 24]  # only first 20 of 90 days
    partial_df = build_dataframe(partial_ts)
    partial_pct, partial_reason = compute_data_quality_pct(partial_df)
    assert partial_pct < Decimal("100")
    assert partial_reason == DATA_GAPS_PRESENT


def test_daily_close_rows_resamples_to_one_row_per_day(tmp_path) -> None:
    timestamps = hourly_range(AS_OF, 3)
    df = build_dataframe(timestamps, close_step=0.01)
    rows = build_daily_close_rows(df)
    assert len(rows) == 3
    assert all(rows[i].timestamp < rows[i + 1].timestamp for i in range(len(rows) - 1))


# ---------------------------------------------------------------------------
# Liquidity percentile (generic, average-rank ties).
# ---------------------------------------------------------------------------


def test_average_rank_percentile_ties_are_exact() -> None:
    result = average_rank_percentile({"A": 5.0, "B": 5.0})
    assert result["A"] == result["B"] == 50.0


def test_average_rank_percentile_distinguishes_distinct_values() -> None:
    result = average_rank_percentile({"A": 10.0, "B": 5.0, "C": 1.0})
    assert result["A"] > result["B"] > result["C"]
    assert result["A"] == 100.0


def test_liquidity_raw_none_when_no_rows_in_last_30_days(tmp_path) -> None:
    # Full 90-day window but the most recent 30 days have zero rows.
    timestamps = hourly_range(AS_OF - timedelta(days=30), 60)
    df = build_dataframe(timestamps)
    liquidity = compute_liquidity_raw(df, AS_OF)
    assert liquidity is None


# ---------------------------------------------------------------------------
# End-to-end orchestration -- verified RS-engine integration.
# ---------------------------------------------------------------------------


def test_build_ranking_input_requires_btc_benchmark(tmp_path) -> None:
    write_full_history_pair(tmp_path, "XRP", AS_OF)

    with pytest.raises(FeatherAdapterError):
        build_ranking_input_v2_from_feather(data_dir=tmp_path, as_of_date=AS_OF.isoformat(), now=NOW)


def test_build_ranking_input_end_to_end_single_candidate(tmp_path) -> None:
    write_full_history_pair(tmp_path, "BTC", AS_OF, base_close=50000.0)
    write_full_history_pair(tmp_path, "XRP", AS_OF, base_close=1.0, close_step=0.001)

    ranking_input, evidence = build_ranking_input_v2_from_feather(
        data_dir=tmp_path, as_of_date=AS_OF.isoformat(), now=NOW
    )

    assert ranking_input.schema_version == "hunter-ranking-input-v2"
    assert ranking_input.ranking_profile == RankingProfile.V2_RS_LIQUIDITY.value
    assert ranking_input.universe_total == 1
    assert ranking_input.eligible_pairs == ("XRP/USDT:USDT",)
    assert ranking_input.oi_scores == {}
    assert ranking_input.source_metadata["oi_available"] is False

    rs_score = ranking_input.rs_scores["XRP/USDT:USDT"]
    assert rs_score is not None
    assert Decimal("0") <= rs_score <= Decimal("100")

    liquidity_score = ranking_input.liquidity_scores["XRP/USDT:USDT"]
    assert liquidity_score is not None

    dq = ranking_input.data_quality["XRP/USDT:USDT"]
    assert dq == Decimal("100.00")

    assert evidence["XRP/USDT:USDT"][0] == DATA_COMPLETE


def test_build_ranking_input_excludes_out_of_window_pair(tmp_path) -> None:
    write_full_history_pair(tmp_path, "BTC", AS_OF)
    old_ts = hourly_range(date(2020, 1, 1), 5)
    write_feather(tmp_path, "OLD", build_dataframe(old_ts))

    ranking_input, evidence = build_ranking_input_v2_from_feather(
        data_dir=tmp_path, as_of_date=AS_OF.isoformat(), now=NOW
    )

    assert "OLD/USDT:USDT" not in ranking_input.eligible_pairs
    assert evidence["OLD/USDT:USDT"] == (INSUFFICIENT_LOOKBACK,)


def test_build_ranking_input_deterministic_across_runs(tmp_path) -> None:
    write_full_history_pair(tmp_path, "BTC", AS_OF)
    write_full_history_pair(tmp_path, "XRP", AS_OF, close_step=0.001)
    write_full_history_pair(tmp_path, "ADA", AS_OF, close_step=-0.001)

    first, _ = build_ranking_input_v2_from_feather(data_dir=tmp_path, as_of_date=AS_OF.isoformat(), now=NOW)
    second, _ = build_ranking_input_v2_from_feather(data_dir=tmp_path, as_of_date=AS_OF.isoformat(), now=NOW)

    from hunter.pairlist_export.ranking_input_v2 import ranking_input_v2_to_json_text

    assert ranking_input_v2_to_json_text(first) == ranking_input_v2_to_json_text(second)


def test_build_ranking_input_exact_tied_liquidity(tmp_path) -> None:
    write_full_history_pair(tmp_path, "BTC", AS_OF)
    # Identical close/volume patterns -> identical liquidity_raw -> tied percentile.
    write_full_history_pair(tmp_path, "AAA", AS_OF, base_close=10.0, base_volume=500.0)
    write_full_history_pair(tmp_path, "BBB", AS_OF, base_close=10.0, base_volume=500.0)
    write_full_history_pair(tmp_path, "CCC", AS_OF, base_close=10.0, base_volume=5000.0)

    ranking_input, _ = build_ranking_input_v2_from_feather(
        data_dir=tmp_path, as_of_date=AS_OF.isoformat(), now=NOW
    )

    liq = ranking_input.liquidity_scores
    assert liq["AAA/USDT:USDT"] == liq["BBB/USDT:USDT"]
    assert liq["CCC/USDT:USDT"] > liq["AAA/USDT:USDT"]


def test_source_feather_files_are_never_mutated(tmp_path) -> None:
    import hashlib

    btc_path = write_full_history_pair(tmp_path, "BTC", AS_OF)
    xrp_path = write_full_history_pair(tmp_path, "XRP", AS_OF, close_step=0.001)

    def _hash(path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    before = {p: _hash(p) for p in (btc_path, xrp_path)}
    build_ranking_input_v2_from_feather(data_dir=tmp_path, as_of_date=AS_OF.isoformat(), now=NOW)
    after = {p: _hash(p) for p in (btc_path, xrp_path)}

    assert before == after
