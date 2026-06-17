-- Hunter Futures Pro SQLite Schema
-- MVP-1 Data Foundation

-- Market symbols registry
CREATE TABLE IF NOT EXISTS market_symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL UNIQUE,
    base_asset TEXT NOT NULL,
    quote_asset TEXT NOT NULL,
    market_type TEXT NOT NULL DEFAULT 'futures',
    status TEXT NOT NULL DEFAULT 'active',
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000)
);

-- OHLCV candles (klines)
CREATE TABLE IF NOT EXISTS candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time INTEGER NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    quote_volume REAL NOT NULL,
    trades INTEGER NOT NULL,
    taker_buy_base REAL NOT NULL,
    taker_buy_quote REAL NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
    UNIQUE(symbol, timeframe, open_time)
);

CREATE INDEX IF NOT EXISTS idx_candles_symbol_timeframe_time
    ON candles(symbol, timeframe, open_time);

-- Funding rates
CREATE TABLE IF NOT EXISTS funding_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    funding_time INTEGER NOT NULL,
    funding_rate REAL NOT NULL,
    mark_price REAL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
    UNIQUE(symbol, funding_time)
);

CREATE INDEX IF NOT EXISTS idx_funding_symbol_time
    ON funding_rates(symbol, funding_time);

-- Open interest snapshots
CREATE TABLE IF NOT EXISTS open_interest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open_interest REAL NOT NULL,
    open_interest_value REAL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_oi_symbol_time
    ON open_interest(symbol, timestamp);

-- Data collection metadata (freshness tracking)
CREATE TABLE IF NOT EXISTS collection_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    data_type TEXT NOT NULL,
    last_collection_time INTEGER,
    last_record_time INTEGER,
    record_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    error_message TEXT,
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
    UNIQUE(symbol, data_type)
);

CREATE INDEX IF NOT EXISTS idx_meta_symbol_type
    ON collection_metadata(symbol, data_type);
