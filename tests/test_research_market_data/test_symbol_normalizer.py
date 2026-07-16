"""Tests for hunter.research_market_data.symbol_normalizer."""

from __future__ import annotations

import pytest

from hunter.research_market_data.models import (
    LEVERAGED_TOKEN_EXCLUDED,
    STABLECOIN_PAIR_EXCLUDED,
    SYMBOL_NORMALIZATION_FAILED,
    UNSUPPORTED_QUOTE_CURRENCY,
)
from hunter.research_market_data.symbol_normalizer import normalize_symbol


class TestNormalizeSymbol:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("BTCUSDT", "BTC/USDT"),
            ("BTC_USDT", "BTC/USDT"),
            ("BTC-USDT", "BTC/USDT"),
            ("BTC/USDT", "BTC/USDT"),
            ("BTC/USDT:USDT", "BTC/USDT"),
            ("btcusdt", "BTC/USDT"),
            ("eth_usdt", "ETH/USDT"),
        ],
    )
    def test_successful_normalization(self, raw: str, expected: str) -> None:
        pair, reasons = normalize_symbol(raw)
        assert pair == expected
        assert reasons == ()

    def test_unsupported_quote(self) -> None:
        pair, reasons = normalize_symbol("ETH/BTC")
        assert pair == "ETH/BTC"
        assert UNSUPPORTED_QUOTE_CURRENCY in reasons

    def test_leveraged_token_excluded(self) -> None:
        pair, reasons = normalize_symbol("BTCUPUSDT")
        assert pair == "BTCUP/USDT"
        assert LEVERAGED_TOKEN_EXCLUDED in reasons

    def test_stablecoin_pair_excluded(self) -> None:
        pair, reasons = normalize_symbol("USDCUSDT")
        assert pair == "USDC/USDT"
        assert STABLECOIN_PAIR_EXCLUDED in reasons

    def test_empty_symbol(self) -> None:
        pair, reasons = normalize_symbol("")
        assert pair == ""
        assert SYMBOL_NORMALIZATION_FAILED in reasons

    def test_only_quote(self) -> None:
        pair, reasons = normalize_symbol("USDT")
        assert SYMBOL_NORMALIZATION_FAILED in reasons

    def test_unsupported_quote_currency_override(self) -> None:
        pair, reasons = normalize_symbol("BTCUSDT", required_quote="BTC")
        assert UNSUPPORTED_QUOTE_CURRENCY in reasons
