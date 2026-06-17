"""Data collector interface for market data acquisition."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional


@dataclass(frozen=True)
class KlineData:
    """OHLCV candlestick data."""

    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades: int
    taker_buy_base: float
    taker_buy_quote: float


@dataclass(frozen=True)
class FundingRateData:
    """Funding rate snapshot."""

    symbol: str
    funding_time: datetime
    funding_rate: float
    mark_price: float


@dataclass(frozen=True)
class OpenInterestData:
    """Open interest snapshot."""

    symbol: str
    timestamp: datetime
    open_interest: float
    open_interest_value: float


@dataclass(frozen=True)
class MarkPriceData:
    """Mark price snapshot."""

    symbol: str
    timestamp: datetime
    mark_price: float
    index_price: float
    estimated_settle_price: float
    funding_rate: float
    next_funding_time: datetime


@dataclass(frozen=True)
class Ticker24hData:
    """24-hour rolling statistics."""

    symbol: str
    price_change: float
    price_change_percent: float
    weighted_avg_price: float
    last_price: float
    last_quantity: float
    open_price: float
    high_price: float
    low_price: float
    volume: float
    quote_volume: float
    open_time: datetime
    close_time: datetime
    first_trade_id: int
    last_trade_id: int
    trade_count: int


class DataCollector(ABC):
    """Abstract base class for market data collectors.

    Implementations must provide exchange-specific data fetching.
    No network calls are made by the base class.
    """

    @abstractmethod
    def get_exchange_info(self) -> dict[str, Any]:
        """Return exchange metadata (symbols, filters, etc.)."""
        ...

    @abstractmethod
    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[KlineData]:
        """Fetch OHLCV klines for a symbol and timeframe."""
        ...

    @abstractmethod
    def get_funding_rates(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[FundingRateData]:
        """Fetch funding rate history for a symbol."""
        ...

    @abstractmethod
    def get_open_interest(self, symbol: str) -> OpenInterestData:
        """Fetch current open interest for a symbol."""
        ...

    @abstractmethod
    def get_mark_price(self, symbol: str) -> MarkPriceData:
        """Fetch mark price and funding info for a symbol."""
        ...

    @abstractmethod
    def get_24h_ticker(self, symbol: Optional[str] = None) -> List[Ticker24hData]:
        """Fetch 24h rolling statistics. If symbol is None, returns all symbols."""
        ...


class BinanceFuturesCollector(DataCollector):
    """Skeleton for Binance Futures data collector.

    Does NOT connect to Binance. All methods raise NotImplementedError.
    This is a placeholder for future implementation.
    """

    def get_exchange_info(self) -> dict[str, Any]:
        raise NotImplementedError("Binance connection not implemented in MVP-1")

    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[KlineData]:
        raise NotImplementedError("Binance connection not implemented in MVP-1")

    def get_funding_rates(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[FundingRateData]:
        raise NotImplementedError("Binance connection not implemented in MVP-1")

    def get_open_interest(self, symbol: str) -> OpenInterestData:
        raise NotImplementedError("Binance connection not implemented in MVP-1")

    def get_mark_price(self, symbol: str) -> MarkPriceData:
        raise NotImplementedError("Binance connection not implemented in MVP-1")

    def get_24h_ticker(self, symbol: Optional[str] = None) -> List[Ticker24hData]:
        raise NotImplementedError("Binance connection not implemented in MVP-1")
