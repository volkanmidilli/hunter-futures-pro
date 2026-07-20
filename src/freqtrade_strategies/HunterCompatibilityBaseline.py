"""Compatibility-only no-trade strategy. Not a trading strategy and not evidence of profitability.

HunterCompatibilityBaseline exists solely to exercise the Freqtrade backtesting
command/config/export/parser plumbing for Phase B.2 real compatibility checks
(MVP-65 / SPEC-066). It never generates entry or exit signals, so any backtest
run against it is expected to produce zero trades. It must not be interpreted
as a trading strategy, a research result, or a profitability claim.

Structurally identical to HunterCompatibilityCandidate except for class name.
"""

from __future__ import annotations

from pandas import DataFrame

from freqtrade.strategy import IStrategy


class HunterCompatibilityBaseline(IStrategy):
    """Compatibility-only no-trade strategy. Not a trading strategy and not evidence of profitability."""

    INTERFACE_VERSION = 3

    can_short: bool = False

    minimal_roi: dict = {"0": 10.0}
    stoploss: float = -1.0

    trailing_stop = False
    timeframe = "5m"

    process_only_new_candles = True
    startup_candle_count: int = 0

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """No indicators are computed; only standard OHLCV columns are used."""
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Never enters a position."""
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Never exits a position (no entries ever occur)."""
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
