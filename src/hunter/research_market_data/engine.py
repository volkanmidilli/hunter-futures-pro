"""Main engine for the research market data package (MVP-63 / SPEC-064)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from hunter.research_market_data.aligner import align_candidate, build_candle_series
from hunter.research_market_data.csv_loader import load_csv_file
from hunter.research_market_data.errors import (
    ResearchMarketDataBundleError,
    ResearchMarketDataError,
)
from hunter.research_market_data.fingerprint import (
    bundle_fingerprint,
    policy_fingerprint,
    series_fingerprint,
)
from hunter.research_market_data.models import (
    ALL_CANDIDATES_EXCLUDED,
    BTC_BENCHMARK_MISSING,
    BTC_ONLY_MODE,
    ETH_BENCHMARK_MISSING,
    EMPTY_FILE,
    ExcludedMarketDataInput,
    FORBIDDEN_PATH,
    HUMAN_RESEARCH_ONLY,
    INPUTS_ALREADY_LOADED,
    INVALID_CSV_HEADER,
    INVALID_FILE_PATH,
    INVALID_NUMERIC,
    INVALID_OHLC_RELATION,
    INVALID_SAFETY_FLAGS,
    MarketDataFileSpec,
    MarketDataSafetyFlags,
    MarketDataSourceRef,
    MISSING_COLUMN,
    MISSING_FILE,
    NAIVE_TIMESTAMP,
    NO_ACTION_COMMANDS_EMITTED,
    NO_DATABASE_CONNECTION,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    NON_FINITE_VALUE,
    NON_UTC_TIMESTAMP,
    NEGATIVE_OR_ZERO_PRICE,
    NEGATIVE_VOLUME,
    OUT_OF_ORDER_INPUT,
    ResearchMarketDataBundle,
    ResearchMarketDataConfig,
    ResearchMarketDataManifest,
    SYMBOL_NORMALIZATION_FAILED,
    TIMESTAMP_PARSE_ERROR,
    UNSUPPORTED_QUOTE_CURRENCY,
    UNSUPPORTED_TIMEFRAME,
    GAPS_FOUND,
    INSUFFICIENT_COVERAGE,
    BELOW_MIN_ROWS,
    DUPLICATE_TIMESTAMP,
    LEVERAGED_TOKEN_EXCLUDED,
    STABLECOIN_PAIR_EXCLUDED,
    UNSAFE_SYMBOL_CONTENT,
)
from hunter.research_market_data.symbol_normalizer import normalize_symbol
from hunter.research_market_data.validator import build_normalized_candles


BLOCKING_REASON_CODES: frozenset[str] = frozenset({
    EMPTY_FILE,
    INVALID_CSV_HEADER,
    INVALID_FILE_PATH,
    INVALID_NUMERIC,
    INVALID_OHLC_RELATION,
    MISSING_COLUMN,
    MISSING_FILE,
    NAIVE_TIMESTAMP,
    NON_FINITE_VALUE,
    NON_UTC_TIMESTAMP,
    NEGATIVE_OR_ZERO_PRICE,
    NEGATIVE_VOLUME,
    OUT_OF_ORDER_INPUT,
    SYMBOL_NORMALIZATION_FAILED,
    TIMESTAMP_PARSE_ERROR,
    UNSUPPORTED_QUOTE_CURRENCY,
    UNSUPPORTED_TIMEFRAME,
    GAPS_FOUND,
    INSUFFICIENT_COVERAGE,
    BELOW_MIN_ROWS,
    DUPLICATE_TIMESTAMP,
    LEVERAGED_TOKEN_EXCLUDED,
    STABLECOIN_PAIR_EXCLUDED,
    UNSAFE_SYMBOL_CONTENT,
    FORBIDDEN_PATH,
})


def _fallback_source(spec: MarketDataFileSpec, file_hash: str = "missing") -> MarketDataSourceRef:
    """Return a source reference for a file that could not be loaded."""
    return MarketDataSourceRef(
        source_id=f"{spec.path.name}:{file_hash}",
        path=spec.path,
        label=spec.source_label or spec.path.name,
        row_count=0,
        file_hash=file_hash,
    )


def _derive_symbol(spec: MarketDataFileSpec) -> str:
    """Derive a raw symbol from a file spec."""
    if spec.expected_symbol:
        return spec.expected_symbol
    return spec.path.stem


def _load_series(
    spec: MarketDataFileSpec,
    config: ResearchMarketDataConfig,
) -> tuple[MarketDataSourceRef, Any]:
    """Load a CSV file and return the source reference and raw rows."""
    source, rows = load_csv_file(spec)
    return source, rows


def _build_and_validate_series(
    source: MarketDataSourceRef,
    raw_rows: Any,
    pair: str,
    config: ResearchMarketDataConfig,
) -> Any:
    """Normalize raw rows and build a ``CandleSeries``."""
    candles = build_normalized_candles(raw_rows, pair)
    return build_candle_series(source, candles, config, pair)


def _pair_from_spec(spec: MarketDataFileSpec) -> tuple[str, tuple[str, ...]]:
    """Return the canonical pair and reason codes for a file spec."""
    raw_symbol = _derive_symbol(spec)
    return normalize_symbol(raw_symbol)


def build_research_market_data_bundle(
    *,
    config: ResearchMarketDataConfig | None = None,
    candidate_specs: Sequence[MarketDataFileSpec],
    btc_spec: MarketDataFileSpec,
    eth_spec: MarketDataFileSpec | None = None,
    generated_at: datetime | None = None,
    metadata: dict[str, str] | None = None,
) -> ResearchMarketDataBundle:
    """Build a deterministic, immutable research market data bundle.

    The engine is read-only and does not perform any network, exchange,
    Freqtrade, database, scheduler, or trading operation.
    """
    config = config or ResearchMarketDataConfig()
    metadata = metadata or {}
    generated_at = generated_at or datetime.now(timezone.utc)

    if not isinstance(config, ResearchMarketDataConfig):
        raise ResearchMarketDataBundleError(
            INVALID_CONFIG, "config must be a ResearchMarketDataConfig"
        )
    if not isinstance(config.safety_flags, MarketDataSafetyFlags):
        raise ResearchMarketDataBundleError(
            INVALID_SAFETY_FLAGS, "config.safety_flags must be a MarketDataSafetyFlags"
        )

    # Load and validate BTC benchmark.
    btc_pair, btc_pair_reasons = _pair_from_spec(btc_spec)
    if btc_pair_reasons:
        raise ResearchMarketDataBundleError(
            BTC_BENCHMARK_MISSING,
            f"BTC benchmark symbol normalization failed: {btc_pair_reasons}",
        )
    try:
        btc_source, btc_rows = _load_series(btc_spec, config)
    except ResearchMarketDataError as exc:
        raise ResearchMarketDataBundleError(
            BTC_BENCHMARK_MISSING,
            f"BTC benchmark could not be loaded: {exc.message}",
        ) from exc
    try:
        btc_series = _build_and_validate_series(btc_source, btc_rows, btc_pair, config)
    except ResearchMarketDataError as exc:
        raise ResearchMarketDataBundleError(
            BTC_BENCHMARK_MISSING,
            f"BTC benchmark validation failed: {exc.message}",
        ) from exc
    if btc_series.reason_codes:
        raise ResearchMarketDataBundleError(
            BTC_BENCHMARK_MISSING,
            f"BTC benchmark has blocking issues: {btc_series.reason_codes}",
        )

    # Load and validate ETH benchmark if provided.
    eth_series = None
    eth_load_reasons: list[str] = []
    if eth_spec is not None:
        eth_pair, eth_pair_reasons = _pair_from_spec(eth_spec)
        if eth_pair_reasons:
            eth_series = None
            eth_load_reasons.append(ETH_BENCHMARK_MISSING)
        else:
            try:
                eth_source, eth_rows = _load_series(eth_spec, config)
                eth_series = _build_and_validate_series(eth_source, eth_rows, eth_pair, config)
            except ResearchMarketDataError as exc:
                eth_series = None
                eth_load_reasons.append(ETH_BENCHMARK_MISSING)

    # Load and validate candidates.
    candidates: list[Any] = []
    exclusions: list[ExcludedMarketDataInput] = []
    for spec in candidate_specs:
        source: MarketDataSourceRef | None = None
        try:
            pair, pair_reasons = _pair_from_spec(spec)
            if pair_reasons:
                source = _fallback_source(spec)
                exclusions.append(
                    ExcludedMarketDataInput(
                        source=source,
                        reason_codes=pair_reasons,
                        message=f"symbol normalization failed: {pair_reasons}",
                    )
                )
                continue

            source, raw_rows = _load_series(spec, config)
            candles = build_normalized_candles(raw_rows, pair)
            series = build_candle_series(source, candles, config, pair)
            if series.reason_codes:
                exclusions.append(
                    ExcludedMarketDataInput(
                        source=source,
                        reason_codes=series.reason_codes,
                        message=f"series validation failed: {series.reason_codes}",
                    )
                )
                continue

            aligned = align_candidate(series, btc_series, eth_series, config)
            if aligned is None:
                exclusions.append(
                    ExcludedMarketDataInput(
                        source=source,
                        reason_codes=(BELOW_MIN_ROWS,),
                        message="candidate did not align with benchmarks",
                    )
                )
                continue

            candidates.append(aligned)
        except ResearchMarketDataError as exc:
            if source is None:
                source = _fallback_source(spec)
            exclusions.append(
                ExcludedMarketDataInput(
                    source=source,
                    reason_codes=(exc.reason_code,),
                    message=exc.message,
                )
            )

    if not candidates:
        raise ResearchMarketDataBundleError(
            ALL_CANDIDATES_EXCLUDED,
            "all candidate inputs were excluded; cannot create bundle",
        )

    # Build fingerprints.
    schema_version = "SPEC-064"
    series_fps = {series.pair: series_fingerprint(series, schema_version) for series in candidates}
    btc_fp = series_fingerprint(btc_series, schema_version)
    eth_fp = series_fingerprint(eth_series, schema_version) if eth_series is not None else None
    policy_fp = policy_fingerprint(config)
    bundle_fp = bundle_fingerprint(
        schema_version=schema_version,
        series_fingerprints=series_fps,
        btc_fingerprint=btc_fp,
        eth_fingerprint=eth_fp,
        policy_fingerprint=policy_fp,
    )

    sources = [series.source for series in candidates]
    sources.append(btc_series.source)
    if eth_series is not None:
        sources.append(eth_series.source)

    reason_codes: list[str] = [
        INPUTS_ALREADY_LOADED,
        NO_NETWORK_CONNECTION,
        NO_DATABASE_CONNECTION,
        NO_FILE_READ_IN_ENGINE,
        NO_ACTION_COMMANDS_EMITTED,
        HUMAN_RESEARCH_ONLY,
    ]
    if eth_series is None:
        reason_codes.append(ETH_BENCHMARK_MISSING)
        reason_codes.append(BTC_ONLY_MODE)
    reason_codes.extend(eth_load_reasons)

    manifest = ResearchMarketDataManifest(
        schema_version=schema_version,
        generated_at=generated_at,
        sources=tuple(sources),
        series_fingerprints=series_fps,
        btc_fingerprint=btc_fp,
        eth_fingerprint=eth_fp,
        policy_fingerprint=policy_fp,
        bundle_fingerprint=bundle_fp,
        safety_flags=config.safety_flags,
        metadata=metadata,
        reason_codes=tuple(reason_codes),
    )

    return ResearchMarketDataBundle(
        config=config,
        manifest=manifest,
        candidates=tuple(candidates),
        btc_series=btc_series,
        eth_series=eth_series,
        exclusions=tuple(exclusions),
        safety_flags=config.safety_flags,
        reason_codes=tuple(reason_codes),
        metadata=metadata,
    )
