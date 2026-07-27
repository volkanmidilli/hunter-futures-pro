"""Symbol normalization tests for SPEC-078 ``hunter explain <SYMBOL>``."""

from __future__ import annotations

import pytest

from hunter.explainability.models import ExplainabilitySymbolError
from hunter.explainability.service import normalize_explain_symbol


class TestShortSymbolNormalization:
    def test_bare_base_normalizes_to_usdt_perpetual(self) -> None:
        assert normalize_explain_symbol("BTC") == "BTC/USDT:USDT"

    def test_lowercase_base_is_uppercased(self) -> None:
        assert normalize_explain_symbol("eth") == "ETH/USDT:USDT"

    def test_surrounding_whitespace_is_stripped(self) -> None:
        assert normalize_explain_symbol("  SOL  ") == "SOL/USDT:USDT"

    def test_numeric_base_allowed(self) -> None:
        assert normalize_explain_symbol("1000PEPE") == "1000PEPE/USDT:USDT"


class TestFullPairNormalization:
    def test_full_futures_form_is_preserved(self) -> None:
        assert normalize_explain_symbol("BTC/USDT:USDT") == "BTC/USDT:USDT"

    def test_spot_form_gains_settle_suffix(self) -> None:
        assert normalize_explain_symbol("BTC/USDT") == "BTC/USDT:USDT"

    def test_lowercase_full_form_is_uppercased(self) -> None:
        assert normalize_explain_symbol("btc/usdt:usdt") == "BTC/USDT:USDT"


class TestInvalidAndUnsafeRejection:
    @pytest.mark.parametrize(
        "symbol",
        [
            "",
            "   ",
            "BTC USDT",
            "BTC/USDT:USDT:USDT",
            "BTC/BUSD",
            "BTC/USDC",
            "../etc/passwd",
            "..",
            "BTC\\USDT",
            "/BTC",
            "~/BTC",
            "BTC;DROP TABLE",
            "BTC-USDT",
            "BTC_USDT",
            "B",  # too short (< 2 chars)
            "B" * 21,  # too long (> 20 chars)
            "BTC/USDT/",
            "BTC/",
            "/USDT",
        ],
    )
    def test_rejected(self, symbol: str) -> None:
        with pytest.raises(ExplainabilitySymbolError):
            normalize_explain_symbol(symbol)

    def test_non_string_rejected(self) -> None:
        with pytest.raises(ExplainabilitySymbolError):
            normalize_explain_symbol(None)  # type: ignore[arg-type]
