# SPEC-064 — Research Market Data CSV Loader and Adapter

**Status:** Approved  
**MVP:** MVP-63  
**Version target:** `v0.63.0-dev`  
**Upstream dependencies:** MVP-24 `Relative Strength Engine`, MVP-26 `Discovery Engine`

## Background

The research pipeline already has pure, deterministic `Relative Strength` and `Discovery` engines that consume `OhlcvRow` and `DiscoveryInput` objects. MVP-63 adds a thin, read-only loader and adapter layer so these engines can be exercised from caller-supplied CSV candle files without inventing market data, without network access, and without synthesizing Open Interest.

```text
BTCUSDT.csv
ETHUSDT.csv (optional)
candidate1.csv
...
        ↓
Research Market Data Loader
        ↓
ResearchMarketDataBundle
        ↓
Relative Strength / Discovery adapters
        ↓
RelativeStrengthReport / DiscoveryInputBundle
```

The bundle is a research-only audit artifact. It is not a trading signal, not a strategy, and not a Freqtrade input or configuration.

## Requirements

### Must Have

- read-only CSV candle loading from caller-provided file paths
- explicit symbol normalization (e.g. `BTCUSDT` → `BTC/USDT`, `BTC/USDT:USDT` → `BTC/USDT`)
- strict validation of CSV structure, timestamps, OHLC relations, volume, and numeric fields
- support for BTC benchmark and optional ETH benchmark
- alignment of all series to the common timestamp intersection
- coverage and gap analysis per series
- deterministic SHA-256 per-series, policy, and bundle fingerprints
- adapter to existing `build_relative_strength_report` engine
- adapter to existing `build_discovery_report` engine with no Open Interest fabrication
- explicit research-only safety flags
- immutable, frozen dataclasses
- deterministic JSON and Markdown artifacts with a safety notice
- fail-closed when required benchmark is missing or all candidates are excluded

### Should Have

- configurable coverage threshold and minimum required rows
- configurable lookback days and required quote currency
- stable sort of symbols and candle rows for deterministic output
- exclusion log capturing each rejected input and its reason codes
- atomic file writes with no silent overwrite
- default artifact paths under `data/research_market_data/` and `reports/research_market_data/`

### Won’t Have

- Freqtrade candle loader or exchange API calls
- automatic downloading of market data
- Open Interest synthesis or fabrication
- trading signals, orders, execution instructions, or strategy changes
- Freqtrade config mutation, server, database, scheduler, or live trading behavior
- production or execution approval

### CSV Format

The loader accepts a standard CSV with a header row containing at least the columns `date`, `open`, `high`, `low`, `close`, `volume`. Timestamps must be ISO-8601 with an explicit UTC offset (naive timestamps are rejected). All numeric fields must be parseable as `Decimal`.

## Method

### Package Layout

```text
src/hunter/research_market_data/
├── __init__.py
├── models.py
├── symbol_normalizer.py
├── csv_loader.py
├── validator.py
├── aligner.py
├── adapters.py
├── fingerprint.py
├── engine.py
└── writer.py

tests/test_research_market_data/
├── __init__.py
├── test_models.py
├── test_symbol_normalizer.py
├── test_csv_loader.py
├── test_validator.py
├── test_aligner.py
├── test_adapters.py
├── test_engine.py
├── test_writer.py
└── test_integration.py
```

### Core Models

```python
@dataclass(frozen=True)
class MarketDataSafetyFlags:
    research_only: bool = True
    execution_approval_granted: bool = False
    production_approval_granted: bool = False
    live_trading_allowed: bool = False
    automatic_execution_allowed: bool = False
```

```python
@dataclass(frozen=True)
class ResearchMarketDataConfig:
    coverage_threshold: Decimal = Decimal("0.98")
    min_required_rows: int = 30
    lookback_days: tuple[int, ...] = (30, 90, 180)
    required_quote_currency: str = "USDT"
    safety_flags: MarketDataSafetyFlags = field(default_factory=MarketDataSafetyFlags)
    metadata: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
```

```python
@dataclass(frozen=True)
class MarketDataFileSpec:
    path: Path
    expected_symbol: str | None = None
    source_label: str | None = None
```

```python
@dataclass(frozen=True)
class CandleSeries:
    pair: str
    timeframe: str
    candles: tuple[NormalizedCandle, ...]
    source: MarketDataSourceRef
    coverage: Decimal
    coverage_threshold: Decimal
    missing_intervals: tuple[MissingInterval, ...]
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]
```

```python
@dataclass(frozen=True)
class ResearchMarketDataBundle:
    config: ResearchMarketDataConfig
    manifest: ResearchMarketDataManifest
    candidates: tuple[CandleSeries, ...]
    btc_series: CandleSeries
    eth_series: CandleSeries | None
    exclusions: tuple[ExcludedMarketDataInput, ...]
    safety_flags: MarketDataSafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]
```

### Public Engine

```python
build_research_market_data_bundle(
    *,
    config: ResearchMarketDataConfig | None = None,
    candidate_specs: Sequence[MarketDataFileSpec],
    btc_spec: MarketDataFileSpec,
    eth_spec: MarketDataFileSpec | None = None,
    generated_at: datetime | None = None,
    metadata: dict[str, str] | None = None,
) -> ResearchMarketDataBundle
```

### Adapters

```python
build_relative_strength_run_inputs(bundle) -> RelativeStrengthRunInputs
candle_series_to_ohlcv_rows(series) -> tuple[OhlcvRow, ...]
relative_strength_report_to_discovery_summaries(report) -> tuple[DiscoveryRelativeStrengthSummary, ...]
discovery_summaries_to_inputs(summaries) -> tuple[DiscoveryInput, ...]
build_discovery_input_bundle(report) -> DiscoveryInputBundle
```

### Safety Invariants

```python
{
    "research_only": True,
    "execution_approval_granted": False,
    "production_approval_granted": False,
    "live_trading_allowed": False,
    "automatic_execution_allowed": False,
}
```

Any contradiction yields `INVALID_SAFETY_FLAGS` and bundle construction fails.

### Reason Codes

Validation / exclusion:

```text
INVALID_CONFIG
INVALID_SAFETY_FLAGS
INVALID_FILE_PATH
FORBIDDEN_PATH
MISSING_FILE
EMPTY_FILE
INVALID_CSV_HEADER
MISSING_COLUMN
AMBIGUOUS_COLUMN
TIMESTAMP_PARSE_ERROR
NAIVE_TIMESTAMP
NON_UTC_TIMESTAMP
INVALID_NUMERIC
NON_FINITE_VALUE
NEGATIVE_OR_ZERO_PRICE
NEGATIVE_VOLUME
INVALID_OHLC_RELATION
DUPLICATE_TIMESTAMP
OUT_OF_ORDER_INPUT
UNSUPPORTED_TIMEFRAME
INSUFFICIENT_COVERAGE
GAPS_FOUND
BELOW_MIN_ROWS
SYMBOL_NORMALIZATION_FAILED
UNSUPPORTED_QUOTE_CURRENCY
UNSAFE_SYMBOL_CONTENT
LEVERAGED_TOKEN_EXCLUDED
STABLECOIN_PAIR_EXCLUDED
```

Bundle-level:

```text
BTC_BENCHMARK_MISSING
ETH_BENCHMARK_MISSING
ALL_CANDIDATES_EXCLUDED
BTC_ONLY_MODE
INPUTS_ALREADY_LOADED
NO_NETWORK_CONNECTION
NO_DATABASE_CONNECTION
NO_FILE_READ_IN_ENGINE
NO_ACTION_COMMANDS_EMITTED
HUMAN_RESEARCH_ONLY
```

### Fingerprinting

- `series_fingerprint` — canonical JSON of sorted candles + source + timeframe + coverage, SHA-256 hex.
- `policy_fingerprint` — canonical JSON of sorted config fields, SHA-256 hex.
- `bundle_fingerprint` — canonical JSON of schema version, sorted series fingerprints, BTC/ETH fingerprints, and policy fingerprint, SHA-256 hex.

### Artifacts

```text
data/research_market_data/latest_bundle.json
reports/research_market_data/latest_bundle.md
```

Artifacts must include the safety notice:

```text
This research market data bundle is a human-audit / research-only artifact.
It is not a trading signal, not trade approval, not strategy approval, not execution approval,
not portfolio approval, not universe approval, and not a Freqtrade input or configuration.
It does not emit action commands, suggest orders, create leverage, or create execution instructions.
Explicit human approval is required before any downstream use.
```

### Writer API

```python
research_market_data_bundle_to_dict(bundle) -> dict[str, Any]
research_market_data_bundle_to_json_text(bundle) -> str
research_market_data_bundle_to_markdown_text(bundle) -> str
write_research_market_data_bundle(bundle, *, json_path, markdown_path, overwrite=False) -> tuple[Path, Path]
atomic_write_json_research_market_data_bundle(bundle, path, overwrite=False) -> Path
atomic_write_markdown_research_market_data_bundle(bundle, path, overwrite=False) -> Path
```

Rules:

- deterministic JSON with sorted keys
- atomic temp-file + `os.replace`
- temp cleanup on failure
- no silent overwrite of existing files
- no source artifact reads

### Determinism

Identical CSV inputs, config, and `generated_at` must produce identical `CandleSeries`, bundle, fingerprints, JSON, and Markdown.

## Implementation Notes

- All dataclasses are frozen; mappings are `MappingProxyType` defensive copies.
- The loader only reads the single CSV file passed to it; it does not traverse directories.
- Validator rejects naive timestamps, duplicate timestamps, and out-of-order input.
- OHLC relation checks: `low <= open <= high`, `low <= close <= high`, `low <= high`.
- Symbol normalizer strips leverage/stablecoin markers and quote suffixes; unsupported quotes are excluded.
- Coverage is computed as `actual / expected` over the observed interval.
- Gap detection records contiguous missing intervals with expected vs. actual counts.
- Benchmark alignment uses the intersection of timestamps; candidates must remain above `min_required_rows` and coverage threshold.
- Adapters are pure data transforms; no metrics are recomputed.

## Gathering Results

Acceptance requires strict CSV validation, deterministic bundle and fingerprint generation, correct adapter integration with the existing Relative Strength and Discovery engines, no Open Interest fabrication, safety invariants, atomic deterministic writers, focused and full test suites passing, project version `0.63.0-dev`, local annotated tag `v0.63.0-dev`, and no push.
