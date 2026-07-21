"""Read-only Freqtrade local 1h-futures Feather adapter (SPEC-075).

Discovers local ``*_USDT_USDT-1h-futures.feather`` files under an
operator-supplied directory, validates schema/timestamps/values, windows to
completed UTC candles in ``[as_of_date - 90d, as_of_date)``, and produces a
SPEC-075 ``RankingInputV2`` artifact.

Reuses ``hunter.relative_strength.build_relative_strength_report`` verbatim
for the RS dimension -- no relative-strength algorithm is reimplemented
here. Liquidity and data-quality are new SPEC-075 dimensions computed
locally per the spec's exact formula (close x volume -> daily total -> 30-day
average -> log1p -> cross-sectional average-rank percentile).

Safety: read-only. No network, download, trading, scheduler, server,
queue, or database access. Source Feather files are opened for reading
only and are never modified, renamed, or deleted. Discovery never follows
symlinks and never escapes the supplied data directory.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.feather as feather

from hunter.pairlist_export.feather_models import (
    BTC_BENCHMARK_MISSING,
    DATA_COMPLETE,
    DATA_GAPS_PRESENT,
    DUPLICATE_CANDLES,
    DUPLICATE_PAIR_SOURCE,
    FEATHER_FILENAME_PATTERN,
    FUTURE_CANDLE,
    FILENAME_NOT_MATCHED,
    FeatherAdapterError,
    FeatherDiscoveryError,
    FeatherDiscoveryResult,
    FeatherExclusion,
    FeatherFileRef,
    FeatherRunMetadata,
    FeatherValidationError,
    HIDDEN_OR_TEMP_FILE,
    INSUFFICIENT_LOOKBACK,
    INVALID_CLOSE,
    INVALID_VOLUME,
    MISSING_COLUMN,
    NOT_A_FILE,
    OUT_OF_ORDER_CANDLES,
    PATH_ESCAPE_REJECTED,
    REQUIRED_FEATHER_COLUMNS,
    SYMLINK_REJECTED,
    UNREADABLE_FEATHER_FILE,
)
from hunter.pairlist_export.ranking_input_v2 import (
    RankingInputV2,
    RankingProfile,
    SCHEMA_V2,
    compute_universe_fingerprint,
)
from hunter.relative_strength.engine import build_relative_strength_report
from hunter.relative_strength.models import (
    OhlcvRow,
    RelativeStrengthConfig,
    RelativeStrengthInput,
    RelativeStrengthReport,
    RelativeStrengthState,
)

WINDOW_DAYS = 90
LIQUIDITY_WINDOW_DAYS = 30
HOURS_PER_DAY = 24
EXPECTED_SLOTS = WINDOW_DAYS * HOURS_PER_DAY

_FILENAME_RE = re.compile(FEATHER_FILENAME_PATTERN)


class _SeriesRejected(FeatherValidationError):
    """Internal control-flow exception carrying deterministic reason codes."""

    def __init__(self, reason_codes: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.reason_codes = reason_codes


# ---------------------------------------------------------------------------
# Stage 2 -- Safe discovery, containment, filename parsing.
# ---------------------------------------------------------------------------


def discover_feather_files(data_dir: Path) -> FeatherDiscoveryResult:
    """Scan ``data_dir`` (non-recursive) for valid 1h-futures Feather files.

    Symlinks, hidden/temp files, non-matching filenames, and paths that
    escape ``data_dir`` are excluded deterministically. Files sharing a
    base symbol, or sharing the same underlying inode (e.g. a hardlinked
    duplicate filed under a second symbol), as an already-included file are
    excluded as ``DUPLICATE_PAIR_SOURCE`` (first filename, sorted, wins).
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FeatherDiscoveryError(f"data-dir does not exist or is not a directory: {data_dir}")

    root = data_dir.resolve(strict=True)

    matched: list[FeatherFileRef] = []
    excluded: list[FeatherExclusion] = []
    seen_bases: dict[str, Path] = {}
    seen_inodes: dict[tuple[int, int], Path] = {}

    for entry in sorted(data_dir.iterdir(), key=lambda p: p.name):
        name = entry.name

        if name.startswith(".") or name.endswith("~") or name.endswith(".tmp"):
            excluded.append(
                FeatherExclusion(path=entry, reason_codes=(HIDDEN_OR_TEMP_FILE,), message="hidden or temp file")
            )
            continue

        if entry.is_symlink():
            excluded.append(
                FeatherExclusion(path=entry, reason_codes=(SYMLINK_REJECTED,), message="symlink rejected")
            )
            continue

        if not entry.is_file():
            excluded.append(
                FeatherExclusion(path=entry, reason_codes=(NOT_A_FILE,), message="not a regular file")
            )
            continue

        match = _FILENAME_RE.match(name)
        if not match:
            excluded.append(
                FeatherExclusion(
                    path=entry,
                    reason_codes=(FILENAME_NOT_MATCHED,),
                    message="filename does not match BASE_USDT_USDT-1h-futures.feather",
                )
            )
            continue

        try:
            resolved = entry.resolve(strict=True)
            resolved.relative_to(root)
        except (ValueError, OSError):
            excluded.append(
                FeatherExclusion(path=entry, reason_codes=(PATH_ESCAPE_REJECTED,), message="path escapes data-dir root")
            )
            continue

        base = match.group("base")
        if base in seen_bases:
            excluded.append(
                FeatherExclusion(
                    path=entry,
                    reason_codes=(DUPLICATE_PAIR_SOURCE,),
                    message=f"duplicate source for base symbol {base} (first: {seen_bases[base].name})",
                )
            )
            continue

        stat = entry.stat()
        inode_key = (stat.st_dev, stat.st_ino)
        if inode_key in seen_inodes:
            excluded.append(
                FeatherExclusion(
                    path=entry,
                    reason_codes=(DUPLICATE_PAIR_SOURCE,),
                    message=f"duplicate underlying file (same inode as {seen_inodes[inode_key].name})",
                )
            )
            continue

        seen_bases[base] = entry
        seen_inodes[inode_key] = entry
        matched.append(FeatherFileRef(path=entry, base_symbol=base, pair=f"{base}/USDT:USDT"))

    btc_ref = next((ref for ref in matched if ref.base_symbol == "BTC"), None)
    eth_ref = next((ref for ref in matched if ref.base_symbol == "ETH"), None)
    candidates = tuple(ref for ref in matched if ref.base_symbol not in ("BTC", "ETH"))

    return FeatherDiscoveryResult(
        included=candidates, excluded=tuple(excluded), btc_ref=btc_ref, eth_ref=eth_ref
    )


# ---------------------------------------------------------------------------
# Stage 3 -- Feather schema/timestamp/value validation.
# ---------------------------------------------------------------------------


def _read_raw_dataframe(path: Path) -> pd.DataFrame:
    """Read only ``date``, ``close``, ``volume`` and normalize ``date`` to UTC."""
    try:
        schema_names = set(pa.ipc.open_file(str(path)).schema.names)
    except Exception:
        try:
            schema_names = set(feather.read_table(str(path)).schema.names)
        except Exception as exc:
            raise _SeriesRejected((UNREADABLE_FEATHER_FILE,), f"unreadable feather file: {path}") from exc

    missing = [c for c in REQUIRED_FEATHER_COLUMNS if c not in schema_names]
    if missing:
        raise _SeriesRejected(
            (MISSING_COLUMN,), f"missing required column(s) {missing} in {path}"
        )

    try:
        table = feather.read_table(str(path), columns=list(REQUIRED_FEATHER_COLUMNS))
        df = table.to_pandas()
    except Exception as exc:
        raise _SeriesRejected((UNREADABLE_FEATHER_FILE,), f"unreadable feather file: {path}") from exc

    date_col = df["date"]
    if pd.api.types.is_datetime64_any_dtype(date_col):
        if date_col.dt.tz is None:
            df["date"] = date_col.dt.tz_localize("UTC")
        else:
            df["date"] = date_col.dt.tz_convert("UTC")
    elif pd.api.types.is_numeric_dtype(date_col):
        df["date"] = pd.to_datetime(date_col, unit="ms", utc=True)
    else:
        raise _SeriesRejected((UNREADABLE_FEATHER_FILE,), f"unsupported date column dtype in {path}")

    return df


def _validate_raw_series(df: pd.DataFrame, path: Path, now: datetime) -> None:
    """Validate the full raw series: values and timestamp integrity.

    Raises :class:`_SeriesRejected` with all applicable reason codes
    accumulated (a series may be both duplicate and out-of-order).
    """
    close = pd.to_numeric(df["close"], errors="coerce").to_numpy(dtype="float64")
    volume = pd.to_numeric(df["volume"], errors="coerce").to_numpy(dtype="float64")

    reasons: list[str] = []
    if (~np.isfinite(close)).any() or (close <= 0).any():
        reasons.append(INVALID_CLOSE)
    if (~np.isfinite(volume)).any() or (volume < 0).any():
        reasons.append(INVALID_VOLUME)

    ts = df["date"]
    if ts.duplicated().any():
        reasons.append(DUPLICATE_CANDLES)
    diffs = ts.diff().dropna()
    if (diffs < pd.Timedelta(0)).any():
        reasons.append(OUT_OF_ORDER_CANDLES)
    if (ts > pd.Timestamp(now)).any():
        reasons.append(FUTURE_CANDLE)

    if reasons:
        raise _SeriesRejected(tuple(reasons), f"validation failed for {path}: {reasons}")


def _window_bounds(as_of_date: date, lookback_days: int) -> tuple[datetime, datetime]:
    start = datetime.combine(as_of_date - timedelta(days=lookback_days), time.min, tzinfo=timezone.utc)
    end = datetime.combine(as_of_date, time.min, tzinfo=timezone.utc)
    return start, end


def _windowed_series(df: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    """Return completed candles in ``[as_of_date - 90d, as_of_date)``, sorted ascending."""
    start, end = _window_bounds(as_of_date, WINDOW_DAYS)
    mask = (df["date"] >= start) & (df["date"] < end)
    return df.loc[mask].sort_values("date").reset_index(drop=True)


def load_and_validate_series(
    ref: FeatherFileRef, as_of_date: date, now: datetime
) -> tuple[pd.DataFrame | None, FeatherExclusion | None]:
    """Load, validate, and window a single Feather file.

    Returns ``(windowed_df, None)`` on success or ``(None, exclusion)`` on
    any validation failure (including empty post-window coverage, which is
    ``INSUFFICIENT_LOOKBACK``).
    """
    try:
        df = _read_raw_dataframe(ref.path)
        _validate_raw_series(df, ref.path, now)
    except _SeriesRejected as exc:
        return None, FeatherExclusion(path=ref.path, reason_codes=exc.reason_codes, message=str(exc))

    windowed = _windowed_series(df, as_of_date)
    if windowed.empty:
        return None, FeatherExclusion(
            path=ref.path, reason_codes=(INSUFFICIENT_LOOKBACK,), message="no completed candles in the as-of window"
        )
    return windowed, None


# ---------------------------------------------------------------------------
# Stage 4 -- RS adapter, liquidity scorer, data-quality scorer.
# ---------------------------------------------------------------------------


def build_daily_close_rows(windowed: pd.DataFrame) -> tuple[OhlcvRow, ...]:
    """Resample completed hourly candles to one close-per-UTC-day.

    This is the only bridge into the existing relative-strength engine:
    the engine's ``lookback_days`` semantics are row-offsets, so feeding it
    daily-close rows (rather than raw hourly rows) makes its unmodified
    7/14/30 "day" lookback windows behave correctly.
    """
    working = windowed.copy()
    working["day"] = working["date"].dt.date
    daily = working.sort_values("date").groupby("day", as_index=False, sort=True).last()
    return tuple(
        OhlcvRow(timestamp=row["date"], close=float(row["close"])) for _, row in daily.iterrows()
    )


def compute_data_quality_pct(windowed: pd.DataFrame) -> tuple[Decimal, str]:
    """Return (percentage of expected 1h slots present, reason code)."""
    actual = len(windowed)
    pct = min(Decimal(100), (Decimal(actual) / Decimal(EXPECTED_SLOTS) * Decimal(100)))
    pct = pct.quantize(Decimal("0.01"))
    reason = DATA_COMPLETE if actual >= EXPECTED_SLOTS else DATA_GAPS_PRESENT
    return pct, reason


def compute_liquidity_raw(windowed: pd.DataFrame, as_of_date: date) -> float | None:
    """Return ``log1p(mean(daily close*volume))`` over the last 30 window days.

    Returns ``None`` if no candles fall within the last-30-day sub-window.
    """
    start, _end = _window_bounds(as_of_date, LIQUIDITY_WINDOW_DAYS)
    sub = windowed.loc[windowed["date"] >= start]
    if sub.empty:
        return None
    working = sub.copy()
    working["dollar_volume"] = working["close"].astype(float) * working["volume"].astype(float)
    working["day"] = working["date"].dt.date
    daily_totals = working.groupby("day")["dollar_volume"].sum()
    average_daily = float(daily_totals.mean())
    return math.log1p(max(0.0, average_daily))


def average_rank_percentile(values: dict[str, float]) -> dict[str, float]:
    """Cross-sectional 0-100 percentile rank, descending value, average rank on ties.

    A small generic statistical primitive (not the relative-strength
    engine's coupled percentile helper, which operates on
    ``RelativeStrengthScore`` period-return metrics specifically).
    """
    if not values:
        return {}
    items = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
    n = len(items)
    result: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j < n and items[j][1] == items[i][1]:
            j += 1
        average_rank = (i + 1 + j) / 2.0
        percentile = (n - average_rank) / (n - 1) * 100.0 if n > 1 else 100.0
        percentile = round(percentile, 4)
        for k in range(i, j):
            result[items[k][0]] = percentile
        i = j
    return result


# ---------------------------------------------------------------------------
# Stage 5 -- Ranking-input v2 orchestration.
# ---------------------------------------------------------------------------


def build_ranking_input_v2_from_feather(
    *,
    data_dir: Path,
    as_of_date: str,
    rs_config: RelativeStrengthConfig | None = None,
    now: datetime | None = None,
) -> tuple[RankingInputV2, dict[str, tuple[str, ...]]]:
    """Build a SPEC-075 ``V2_RS_LIQUIDITY`` ranking-input artifact from local Feather files.

    Returns ``(ranking_input, evidence)`` where ``evidence`` maps every
    considered pair (and excluded filename, if applicable) to its
    deterministic reason codes for downstream audit use.

    Raises :class:`FeatherAdapterError` if no BTC 1h-futures benchmark file
    is discovered, or if the BTC benchmark has no completed candles in the
    as-of window -- relative strength cannot be computed without it.
    """
    data_dir = Path(data_dir)
    as_of = date.fromisoformat(as_of_date)
    now = now or datetime.now(timezone.utc)
    rs_config = rs_config or RelativeStrengthConfig()

    discovery = discover_feather_files(data_dir)

    evidence: dict[str, tuple[str, ...]] = {}
    for exclusion in discovery.excluded:
        evidence[str(exclusion.path.name)] = exclusion.reason_codes

    if discovery.btc_ref is None:
        raise FeatherAdapterError(
            f"no BTC_USDT_USDT-1h-futures.feather benchmark file found under {data_dir}"
        )

    btc_windowed, btc_exclusion = load_and_validate_series(discovery.btc_ref, as_of, now)
    if btc_windowed is None:
        assert btc_exclusion is not None
        evidence[discovery.btc_ref.pair] = (BTC_BENCHMARK_MISSING,) + btc_exclusion.reason_codes
        raise FeatherAdapterError(
            f"BTC benchmark has no usable candles in the as-of window: {btc_exclusion.message}"
        )
    btc_daily_rows = build_daily_close_rows(btc_windowed)

    eth_daily_rows: tuple[OhlcvRow, ...] | None = None
    if discovery.eth_ref is not None:
        eth_windowed, _eth_exclusion = load_and_validate_series(discovery.eth_ref, as_of, now)
        if eth_windowed is not None:
            eth_daily_rows = build_daily_close_rows(eth_windowed)

    universe_total = len(discovery.included)

    rs_inputs: list[RelativeStrengthInput] = []
    liquidity_raw: dict[str, float] = {}
    data_quality: dict[str, Decimal] = {}
    considered_pairs: list[str] = []

    for ref in discovery.included:
        windowed, exclusion = load_and_validate_series(ref, as_of, now)
        if windowed is None:
            assert exclusion is not None
            evidence[ref.pair] = exclusion.reason_codes
            continue

        considered_pairs.append(ref.pair)
        dq_pct, dq_reason = compute_data_quality_pct(windowed)
        data_quality[ref.pair] = dq_pct
        reason_codes = [dq_reason]

        liq = compute_liquidity_raw(windowed, as_of)
        if liq is not None:
            liquidity_raw[ref.pair] = liq

        rs_inputs.append(RelativeStrengthInput(symbol=ref.pair, rows=build_daily_close_rows(windowed)))
        evidence[ref.pair] = tuple(reason_codes)

    liquidity_percentiles = average_rank_percentile(liquidity_raw)

    if rs_inputs:
        rs_report: RelativeStrengthReport = build_relative_strength_report(
            universe=rs_inputs, btc_benchmark=btc_daily_rows, eth_benchmark=eth_daily_rows, config=rs_config
        )
        rs_by_pair = {score.symbol: score for score in rs_report.scores}
    else:
        rs_by_pair = {}

    rs_scores: dict[str, Decimal | None] = {}
    liquidity_scores: dict[str, Decimal | None] = {}
    eligible_pairs: list[str] = []

    for pair in considered_pairs:
        score = rs_by_pair.get(pair)
        rs_value: Decimal | None = None
        if score is not None and score.state == RelativeStrengthState.READY:
            rs_value = Decimal(str(score.total_score))
        rs_scores[pair] = rs_value

        liq_pct = liquidity_percentiles.get(pair)
        liquidity_scores[pair] = Decimal(str(liq_pct)) if liq_pct is not None else None

        if rs_value is not None and liquidity_scores[pair] is not None and pair in data_quality:
            eligible_pairs.append(pair)
        else:
            missing_dims = []
            if rs_value is None:
                missing_dims.append("rs")
            if liquidity_scores[pair] is None:
                missing_dims.append("liquidity")
            evidence[pair] = evidence.get(pair, ()) + tuple(f"MISSING_{d.upper()}" for d in missing_dims)

    eligible_pairs.sort()
    universe_fingerprint = compute_universe_fingerprint(tuple(eligible_pairs))

    metadata = FeatherRunMetadata(
        source="freqtrade-feather",
        timeframe="1h",
        rs_lookback_days=WINDOW_DAYS,
        liquidity_lookback_days=LIQUIDITY_WINDOW_DAYS,
        oi_available=False,
        universe_size_at_scoring=universe_total,
        universe_fingerprint=universe_fingerprint,
    )

    ranking_input = RankingInputV2(
        schema_version=SCHEMA_V2,
        ranking_profile=RankingProfile.V2_RS_LIQUIDITY.value,
        as_of_date=as_of_date,
        universe_total=universe_total,
        eligible_pairs=tuple(eligible_pairs),
        rs_scores={p: rs_scores.get(p) for p in eligible_pairs},
        liquidity_scores={p: liquidity_scores.get(p) for p in eligible_pairs},
        oi_scores={},
        data_quality={p: data_quality.get(p) for p in eligible_pairs},
        source_metadata={
            "source": metadata.source,
            "timeframe": metadata.timeframe,
            "rs_lookback_days": metadata.rs_lookback_days,
            "liquidity_lookback_days": metadata.liquidity_lookback_days,
            "oi_available": metadata.oi_available,
            "universe_size_at_scoring": metadata.universe_size_at_scoring,
            "universe_fingerprint": metadata.universe_fingerprint,
        },
    )

    return ranking_input, evidence
