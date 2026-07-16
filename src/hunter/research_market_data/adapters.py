"""Adapters from research market data to existing research engines (MVP-63 / SPEC-064).

These adapters are pure data transforms. They do not compute new metrics, do not
fabricate Open Interest, and do not perform any network, exchange, or trading
operation.
"""

from __future__ import annotations

from collections.abc import Sequence

from hunter.discovery.models import DiscoveryInput, DiscoveryInputKind, DiscoveryRelativeStrengthSummary
from hunter.research_market_data.models import (
    CandleSeries,
    DiscoveryInputBundle,
    RelativeStrengthRunInputs,
    ResearchMarketDataBundle,
)
from hunter.relative_strength.models import OhlcvRow, RelativeStrengthInput, RelativeStrengthReport


def candle_series_to_ohlcv_rows(series: CandleSeries) -> tuple[OhlcvRow, ...]:
    """Convert a ``CandleSeries`` to ``OhlcvRow`` values for the RS engine."""
    rows: list[OhlcvRow] = []
    for candle in series.candles:
        rows.append(
            OhlcvRow(
                timestamp=candle.timestamp,
                close=candle.close,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                volume=candle.volume,
            )
        )
    return tuple(rows)


def build_relative_strength_run_inputs(
    bundle: ResearchMarketDataBundle,
) -> RelativeStrengthRunInputs:
    """Build Relative Strength engine inputs from a research market data bundle."""
    candidates = tuple(
        RelativeStrengthInput(symbol=series.pair, rows=candle_series_to_ohlcv_rows(series))
        for series in bundle.candidates
    )
    btc = candle_series_to_ohlcv_rows(bundle.btc_series)
    eth = (
        candle_series_to_ohlcv_rows(bundle.eth_series)
        if bundle.eth_series is not None
        else None
    )
    return RelativeStrengthRunInputs(candidates=candidates, btc=btc, eth=eth)


def relative_strength_report_to_discovery_summaries(
    report: RelativeStrengthReport,
) -> tuple[DiscoveryRelativeStrengthSummary, ...]:
    """Map a ``RelativeStrengthReport`` to Discovery-relative-strength summaries."""
    summaries: list[DiscoveryRelativeStrengthSummary] = []
    for score in report.scores:
        summaries.append(
            DiscoveryRelativeStrengthSummary(
                pair=score.symbol,
                state=score.state.value,
                decision=score.decision.value,
                total_score=score.total_score,
                rank_percentile_30d=score.rank_percentile_30d,
                reason_codes=score.reason_codes,
                metadata={},
            )
        )
    return tuple(summaries)


def discovery_summaries_to_inputs(
    summaries: Sequence[DiscoveryRelativeStrengthSummary],
) -> tuple[DiscoveryInput, ...]:
    """Build ``DiscoveryInput`` values with Open Interest absent."""
    return tuple(
        DiscoveryInput(
            pair=summary.pair,
            input_kind=DiscoveryInputKind.SUMMARY,
            relative_strength=summary,
            open_interest=None,
            tags=(),
            metadata={},
        )
        for summary in summaries
    )


def build_discovery_input_bundle(
    report: RelativeStrengthReport,
) -> DiscoveryInputBundle:
    """Build a complete Discovery input bundle from a Relative Strength report."""
    summaries = relative_strength_report_to_discovery_summaries(report)
    inputs = discovery_summaries_to_inputs(summaries)
    return DiscoveryInputBundle(inputs=inputs)
