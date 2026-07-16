"""Symbol normalization for research market data (MVP-63 / SPEC-064).

All supported symbols are normalized to the canonical Freqtrade-compatible form
``BASE/QUOTE`` with ``USDT`` as the only supported quote currency in MVP-63.
"""

from __future__ import annotations

from hunter.research_market_data.models import (
    LEVERAGED_TOKEN_EXCLUDED,
    STABLECOIN_PAIR_EXCLUDED,
    SYMBOL_NORMALIZATION_FAILED,
    UNSAFE_SYMBOL_CONTENT,
    UNSUPPORTED_QUOTE_CURRENCY,
)

SUPPORTED_QUOTE_CURRENCIES: frozenset[str] = frozenset({"USDT"})

STABLECOIN_BASES: frozenset[str] = frozenset({
    "USDT", "USDC", "BUSD", "DAI", "TUSD", "PAX", "FDUSD", "USDD", "UST",
})

LEVERAGE_TOKEN_MARKERS: tuple[str, ...] = (
    "UP", "DOWN", "BULL", "BEAR", "3L", "3S", "4L", "4S", "5L", "5S"
)

FORBIDDEN_SYMBOL_SUBSTRINGS: frozenset[str] = frozenset({
    "BINANCE",
    "API_KEY",
    "SECRET",
    "PLACE_ORDER",
    "EXECUTE",
    "LEVERAGE",
    "SHORTING",
    "ENTER_LONG",
    "ENTER_SHORT",
    "EXIT_LONG",
    "EXIT_SHORT",
})


def _strip_futures_suffix(symbol: str) -> str:
    """Remove perpetual futures suffixes such as ``:USDT`` or ``-PERP``."""
    if ":" in symbol:
        symbol = symbol.split(":", 1)[0]
    if symbol.upper().endswith("-PERP"):
        symbol = symbol[:-5]
    return symbol


def _split_base_quote(symbol: str, required_quote: str) -> tuple[str, str] | None:
    """Split a raw symbol into base and quote components."""
    upper = symbol.upper()
    for sep in ("/", "_", "-"):
        if sep in upper:
            parts = upper.split(sep)
            if len(parts) == 2:
                return parts[0], parts[1]
            if len(parts) > 2:
                return None
    # If the symbol ends with the required quote, split there.
    if upper.endswith(required_quote) and len(upper) > len(required_quote):
        return upper[: -len(required_quote)], required_quote
    return None


def _is_leveraged_token(base: str) -> bool:
    """Return True if the base symbol looks like a leveraged token."""
    upper = base.upper()
    for marker in LEVERAGE_TOKEN_MARKERS:
        if marker in upper:
            return True
    return False


def _is_stablecoin_pair(base: str, quote: str) -> bool:
    """Return True if both base and quote are stablecoins."""
    return base.upper() in STABLECOIN_BASES and quote.upper() in STABLECOIN_BASES


def _has_forbidden_content(symbol: str) -> bool:
    """Return True if the symbol contains forbidden trading/execution tokens."""
    upper = symbol.upper()
    for token in FORBIDDEN_SYMBOL_SUBSTRINGS:
        if token in upper:
            return True
    return False


def normalize_symbol(
    symbol: str,
    required_quote: str = "USDT",
) -> tuple[str, tuple[str, ...]]:
    """Normalize a raw symbol to ``BASE/QUOTE``.

    Returns ``(canonical_pair, reason_codes)``. On success ``reason_codes`` is
    empty. On failure ``canonical_pair`` is the cleaned but rejected string and
    ``reason_codes`` contains one or more machine-readable reason codes.
    """
    if not isinstance(symbol, str) or not symbol.strip():
        return "", (SYMBOL_NORMALIZATION_FAILED,)

    if required_quote.upper() not in SUPPORTED_QUOTE_CURRENCIES:
        return symbol.strip(), (UNSUPPORTED_QUOTE_CURRENCY,)

    cleaned = _strip_futures_suffix(symbol.strip()).upper().replace(" ", "")
    if not cleaned:
        return "", (SYMBOL_NORMALIZATION_FAILED,)

    if _has_forbidden_content(cleaned):
        return cleaned, (UNSAFE_SYMBOL_CONTENT,)

    split = _split_base_quote(cleaned, required_quote.upper())
    if split is None:
        return cleaned, (SYMBOL_NORMALIZATION_FAILED,)
    base, quote = split

    if quote != required_quote.upper():
        return f"{base}/{quote}", (UNSUPPORTED_QUOTE_CURRENCY,)

    if not base or base == quote:
        return f"{base}/{quote}", (SYMBOL_NORMALIZATION_FAILED,)

    if _is_leveraged_token(base):
        return f"{base}/{quote}", (LEVERAGED_TOKEN_EXCLUDED,)

    if _is_stablecoin_pair(base, quote):
        return f"{base}/{quote}", (STABLECOIN_PAIR_EXCLUDED,)

    return f"{base}/{quote}", ()
