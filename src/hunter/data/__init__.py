"""Data collector interface for market data acquisition."""

from .collector import (
    DataCollector,
    FundingRateData,
    KlineData,
    MarkPriceData,
    OpenInterestData,
    Ticker24hData,
)

__all__ = [
    "DataCollector",
    "KlineData",
    "FundingRateData",
    "OpenInterestData",
    "MarkPriceData",
    "Ticker24hData",
]
