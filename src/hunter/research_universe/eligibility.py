"""Common eligibility policy for Candidate and Baseline universes (MVP-64 / SPEC-065)."""

from __future__ import annotations

from typing import Any

from hunter.research_market_data.models import CandleSeries
from hunter.research_universe.models import (
    BENCHMARK_PAIR_EXCLUDED,
    COVERAGE_BELOW_MIN,
    INELIGIBLE_PAIR,
    LEVERAGED_TOKEN_EXCLUDED,
    PairEligibilityResult,
    STABLECOIN_PAIR_EXCLUDED,
    UNSAFE_SYMBOL_CONTENT,
    ResearchUniverseConfig,
)

# Stablecoin symbols used as quote or base currencies.
_STABLECOIN_SYMBOLS: frozenset[str] = frozenset(
    {
        "USDT",
        "USDC",
        "BUSD",
        "DAI",
        "TUSD",
        "PAX",
        "USDP",
        "FDUSD",
        "UST",
    }
)


_LEVERAGED_TOKEN_PATTERNS: tuple[str, ...] = (
    "UP",
    "DOWN",
    "1L",
    "2L",
    "3L",
    "4L",
    "5L",
    "6L",
    "7L",
    "8L",
    "9L",
    "10L",
    "1S",
    "2S",
    "3S",
    "4S",
    "5S",
    "6S",
    "7S",
    "8S",
    "9S",
    "10S",
    "BULL",
    "BEAR",
)


def _is_leveraged_token(pair: str) -> bool:
    """Return True if the canonical pair base looks like a leveraged token."""
    base = pair.split("/")[0].upper()
    for pattern in _LEVERAGED_TOKEN_PATTERNS:
        if pattern in base:
            return True
    return False


def _is_stablecoin_pair(pair: str) -> bool:
    """Return True if both sides of the pair are stablecoins."""
    parts = pair.split("/")
    if len(parts) != 2:
        return False
    base, quote = parts[0].upper(), parts[1].upper()
    if base in _STABLECOIN_SYMBOLS and quote in _STABLECOIN_SYMBOLS:
        return True
    return False


def _has_unsafe_content(pair: str) -> bool:
    """Return True if the pair contains unsafe characters or structure."""
    if not pair or not isinstance(pair, str):
        return True
    if pair != pair.strip():
        return True
    if ".." in pair or pair.startswith("/") or pair.endswith("/"):
        return True
    if pair.count("/") != 1:
        return True
    if any(ch.isspace() for ch in pair):
        return True
    return False


def _selection_window_fully_inside_series(
    series: CandleSeries,
    window: Any,
) -> bool:
    """Return True if the selection window is inside the series timestamp range."""
    if not series.candles:
        return False
    first = series.candles[0].timestamp
    last = series.candles[-1].timestamp
    return window.start >= first and window.end <= last


def assess_pair_eligibility(
    pair: str,
    series: CandleSeries,
    config: ResearchUniverseConfig,
) -> PairEligibilityResult:
    """Assess a single pair's eligibility for both Candidate and Baseline universes.

    Eligibility is independent of the universe kind; ranking happens later.
    """
    reasons: list[str] = []

    if _has_unsafe_content(pair):
        reasons.append(UNSAFE_SYMBOL_CONTENT)
        return PairEligibilityResult(
            pair=pair,
            is_eligible=False,
            coverage=0.0,
            source_fingerprint=series.source.file_hash,
            reason_codes=tuple(reasons),
        )

    if _is_stablecoin_pair(pair):
        reasons.append(STABLECOIN_PAIR_EXCLUDED)
        return PairEligibilityResult(
            pair=pair,
            is_eligible=False,
            coverage=float(series.coverage),
            source_fingerprint=series.source.file_hash,
            reason_codes=tuple(reasons),
        )

    if _is_leveraged_token(pair):
        reasons.append(LEVERAGED_TOKEN_EXCLUDED)
        return PairEligibilityResult(
            pair=pair,
            is_eligible=False,
            coverage=float(series.coverage),
            source_fingerprint=series.source.file_hash,
            reason_codes=tuple(reasons),
        )

    if pair.upper() in (b.upper() for b in config.benchmark_pairs):
        reasons.append(BENCHMARK_PAIR_EXCLUDED)
        return PairEligibilityResult(
            pair=pair,
            is_eligible=False,
            coverage=float(series.coverage),
            source_fingerprint=series.source.file_hash,
            reason_codes=tuple(reasons),
        )

    if float(series.coverage) < config.min_coverage_ratio:
        reasons.append(COVERAGE_BELOW_MIN)
        return PairEligibilityResult(
            pair=pair,
            is_eligible=False,
            coverage=float(series.coverage),
            source_fingerprint=series.source.file_hash,
            reason_codes=tuple(reasons),
        )

    if not _selection_window_fully_inside_series(series, config.selection_window):
        reasons.append(INELIGIBLE_PAIR)
        return PairEligibilityResult(
            pair=pair,
            is_eligible=False,
            coverage=float(series.coverage),
            source_fingerprint=series.source.file_hash,
            reason_codes=tuple(reasons),
        )

    return PairEligibilityResult(
        pair=pair,
        is_eligible=True,
        coverage=float(series.coverage),
        source_fingerprint=series.source.file_hash,
        reason_codes=tuple(reasons),
    )


def build_eligibility_policy_fingerprint(
    config: ResearchUniverseConfig,
) -> str:
    """Build a deterministic fingerprint of the eligibility policy."""
    from hunter.research_universe.fingerprint import policy_fingerprint

    return policy_fingerprint(config)
