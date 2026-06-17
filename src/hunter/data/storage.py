"""Storage layer for market data persistence."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import List, Optional

from .collector import KlineData, FundingRateData


class DataStorage(ABC):
    """Abstract base class for data storage backends."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize storage (create tables, indexes, etc.)."""
        ...

    @abstractmethod
    def save_klines(self, klines: List[KlineData]) -> int:
        """Save klines. Returns number of records inserted."""
        ...

    @abstractmethod
    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[KlineData]:
        """Retrieve klines for a symbol and timeframe."""
        ...

    @abstractmethod
    def get_latest_kline(self, symbol: str, timeframe: str) -> Optional[KlineData]:
        """Get the most recent kline for a symbol and timeframe."""
        ...

    @abstractmethod
    def save_funding_rates(self, rates: List[FundingRateData]) -> int:
        """Save funding rates. Returns number of records inserted."""
        ...

    @abstractmethod
    def get_funding_rates(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[FundingRateData]:
        """Retrieve funding rates for a symbol."""
        ...

    @abstractmethod
    def save_collection_metadata(
        self, symbol: str, data_type: str, last_collection_time: Optional[datetime] = None
    ) -> None:
        """Save or update collection metadata for a symbol and data type."""
        ...

    @abstractmethod
    def get_collection_metadata(self, symbol: str, data_type: str) -> Optional[dict]:
        """Get metadata for a symbol and data type."""
        ...

    @abstractmethod
    def is_data_fresh(self, symbol: str, data_type: str, max_age_seconds: int = 3600) -> bool:
        """Check if data is fresh (within max_age_seconds)."""
        ...


class SQLiteStorage(DataStorage):
    """SQLite implementation of DataStorage.

    Uses Python standard library sqlite3 only.
    No network connections.
    """

    def __init__(self, db_path: str = "data/hunter.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def initialize(self) -> None:
        """Create tables and indexes from schema.sql."""
        schema_path = Path(__file__).parent / "schema.sql"
        conn = self._get_connection()
        if schema_path.exists():
            conn.executescript(schema_path.read_text())
        else:
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _dt_to_ms(self, dt: Optional[datetime]) -> Optional[int]:
        if dt is None:
            return None
        return int(dt.timestamp() * 1000)

    def _ms_to_dt(self, ms: int) -> datetime:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)

    def save_klines(self, klines: List[KlineData]) -> int:
        if not klines:
            return 0
        conn = self._get_connection()
        cursor = conn.cursor()
        inserted = 0
        for k in klines:
            try:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO candles
                    (symbol, timeframe, open_time, open, high, low, close,
                     volume, quote_volume, trades, taker_buy_base, taker_buy_quote)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        k.symbol,
                        k.timeframe,
                        self._dt_to_ms(k.open_time),
                        k.open,
                        k.high,
                        k.low,
                        k.close,
                        k.volume,
                        k.quote_volume,
                        k.trades,
                        k.taker_buy_base,
                        k.taker_buy_quote,
                    ),
                )
                if cursor.rowcount > 0:
                    inserted += 1
            except sqlite3.Error:
                continue
        conn.commit()
        return inserted

    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[KlineData]:
        conn = self._get_connection()
        query = "SELECT * FROM candles WHERE symbol = ? AND timeframe = ?"
        params: List = [symbol, timeframe]
        if start_time is not None:
            query += " AND open_time >= ?"
            params.append(self._dt_to_ms(start_time))
        if end_time is not None:
            query += " AND open_time <= ?"
            params.append(self._dt_to_ms(end_time))
        query += " ORDER BY open_time DESC LIMIT ?"
        params.append(limit)
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [self._row_to_kline(row) for row in rows]

    def get_latest_kline(self, symbol: str, timeframe: str) -> Optional[KlineData]:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM candles WHERE symbol = ? AND timeframe = ? ORDER BY open_time DESC LIMIT 1",
            (symbol, timeframe),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_kline(row)

    def _row_to_kline(self, row: sqlite3.Row) -> KlineData:
        return KlineData(
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            open_time=self._ms_to_dt(row["open_time"]),
            close_time=self._ms_to_dt(row["open_time"]),  # close_time not stored separately
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            quote_volume=row["quote_volume"],
            trades=row["trades"],
            taker_buy_base=row["taker_buy_base"],
            taker_buy_quote=row["taker_buy_quote"],
        )

    def save_funding_rates(self, rates: List[FundingRateData]) -> int:
        if not rates:
            return 0
        conn = self._get_connection()
        cursor = conn.cursor()
        inserted = 0
        for r in rates:
            try:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO funding_rates
                    (symbol, funding_time, funding_rate, mark_price)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        r.symbol,
                        self._dt_to_ms(r.funding_time),
                        r.funding_rate,
                        r.mark_price,
                    ),
                )
                if cursor.rowcount > 0:
                    inserted += 1
            except sqlite3.Error:
                continue
        conn.commit()
        return inserted

    def get_funding_rates(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[FundingRateData]:
        conn = self._get_connection()
        query = "SELECT * FROM funding_rates WHERE symbol = ?"
        params: List = [symbol]
        if start_time is not None:
            query += " AND funding_time >= ?"
            params.append(self._dt_to_ms(start_time))
        if end_time is not None:
            query += " AND funding_time <= ?"
            params.append(self._dt_to_ms(end_time))
        query += " ORDER BY funding_time DESC LIMIT ?"
        params.append(limit)
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [self._row_to_funding_rate(row) for row in rows]

    def _row_to_funding_rate(self, row: sqlite3.Row) -> FundingRateData:
        return FundingRateData(
            symbol=row["symbol"],
            funding_time=self._ms_to_dt(row["funding_time"]),
            funding_rate=row["funding_rate"],
            mark_price=row["mark_price"] if row["mark_price"] is not None else 0.0,
        )

    def save_collection_metadata(
        self, symbol: str, data_type: str, last_collection_time: Optional[datetime] = None
    ) -> None:
        conn = self._get_connection()
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        coll_ms = self._dt_to_ms(last_collection_time) if last_collection_time else now_ms
        conn.execute(
            """
            INSERT INTO collection_metadata (symbol, data_type, last_collection_time, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol, data_type) DO UPDATE SET
                last_collection_time = excluded.last_collection_time,
                updated_at = excluded.updated_at
            """,
            (symbol, data_type, coll_ms, now_ms),
        )
        conn.commit()

    def get_collection_metadata(self, symbol: str, data_type: str) -> Optional[dict]:
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM collection_metadata WHERE symbol = ? AND data_type = ?",
            (symbol, data_type),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "symbol": row["symbol"],
            "data_type": row["data_type"],
            "last_collection_time": row["last_collection_time"],
            "last_record_time": row["last_record_time"],
            "record_count": row["record_count"],
            "status": row["status"],
            "error_message": row["error_message"],
            "updated_at": row["updated_at"],
        }

    def is_data_fresh(self, symbol: str, data_type: str, max_age_seconds: int = 3600) -> bool:
        meta = self.get_collection_metadata(symbol, data_type)
        if meta is None or meta["last_collection_time"] is None:
            return False
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        age_seconds = (now_ms - meta["last_collection_time"]) / 1000
        return age_seconds <= max_age_seconds
