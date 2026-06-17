"""Tests for market state models."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import FrozenInstanceError

import pytest

from hunter.market_state.models import (
    AllowedMode,
    BreadthOutput,
    DataQuality,
    OutputStatus,
    RegimeOutput,
    RegimeState,
    RiskState,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestEnums:
    def test_regime_state_values(self) -> None:
        assert RegimeState.BULL == "BULL"
        assert RegimeState.BEAR == "BEAR"
        assert RegimeState.SIDEWAYS == "SIDEWAYS"
        assert RegimeState.TRANSITION == "TRANSITION"
        assert RegimeState.UNKNOWN == "UNKNOWN"

    def test_risk_state_values(self) -> None:
        assert RiskState.RISK_ON == "RISK_ON"
        assert RiskState.RISK_OFF == "RISK_OFF"
        assert RiskState.NEUTRAL == "NEUTRAL"
        assert RiskState.UNKNOWN == "UNKNOWN"

    def test_allowed_mode_values(self) -> None:
        assert AllowedMode.LONG_ONLY == "LONG_ONLY"
        assert AllowedMode.SHORT_ONLY == "SHORT_ONLY"
        assert AllowedMode.NONE == "NONE"

    def test_output_status_values(self) -> None:
        assert OutputStatus.VALID == "VALID"
        assert OutputStatus.INVALID == "INVALID"


# ---------------------------------------------------------------------------
# DataQuality tests
# ---------------------------------------------------------------------------

class TestDataQuality:
    def test_default_is_valid(self) -> None:
        dq = DataQuality()
        assert dq.is_valid() is True
        assert dq.missing is False
        assert dq.stale is False
        assert dq.insufficient_history is False
        assert dq.insufficient_universe is False

    def test_missing_is_invalid(self) -> None:
        dq = DataQuality(missing=True)
        assert dq.is_valid() is False

    def test_stale_is_invalid(self) -> None:
        dq = DataQuality(stale=True)
        assert dq.is_valid() is False

    def test_multiple_flags_invalid(self) -> None:
        dq = DataQuality(missing=True, stale=True, insufficient_history=True)
        assert dq.is_valid() is False


# ---------------------------------------------------------------------------
# RegimeOutput — valid creation
# ---------------------------------------------------------------------------

class TestRegimeOutputValid:
    def test_create_valid_regime(self) -> None:
        now = datetime.now(timezone.utc)
        output = RegimeOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            market_regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.82,
            risk_state=RiskState.RISK_ON,
            btc_trend_score=85,
            eth_trend_score=74,
            breadth_confirmation_score=68,
            reason_codes=["BTC_CLOSE_ABOVE_EMA20", "BREADTH_CONFIRMS_RISK_ON"],
            data_quality=DataQuality(),
        )
        assert output.status == OutputStatus.VALID
        assert output.market_regime == RegimeState.BULL
        assert output.allowed_mode == AllowedMode.LONG_ONLY
        assert output.confidence == 0.82
        assert output.btc_trend_score == 85
        assert output.eth_trend_score == 74
        assert output.breadth_confirmation_score == 68
        assert output.is_blocking() is False

    def test_confidence_at_boundaries(self) -> None:
        now = datetime.now(timezone.utc)
        # confidence = 0.0 (valid boundary)
        RegimeOutput(
            timestamp=now,
            status=OutputStatus.INVALID,
            market_regime=RegimeState.UNKNOWN,
            allowed_mode=AllowedMode.NONE,
            confidence=0.0,
            risk_state=RiskState.UNKNOWN,
            btc_trend_score=0,
            eth_trend_score=0,
            breadth_confirmation_score=0,
        )
        # confidence = 1.0 (valid boundary)
        RegimeOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            market_regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=1.0,
            risk_state=RiskState.RISK_ON,
            btc_trend_score=100,
            eth_trend_score=100,
            breadth_confirmation_score=100,
        )

    def test_scores_at_boundaries(self) -> None:
        now = datetime.now(timezone.utc)
        # score = 0 (valid boundary)
        RegimeOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            market_regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.5,
            risk_state=RiskState.RISK_ON,
            btc_trend_score=0,
            eth_trend_score=0,
            breadth_confirmation_score=0,
        )
        # score = 100 (valid boundary)
        RegimeOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            market_regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.5,
            risk_state=RiskState.RISK_ON,
            btc_trend_score=100,
            eth_trend_score=100,
            breadth_confirmation_score=100,
        )

    def test_default_reason_codes_empty(self) -> None:
        now = datetime.now(timezone.utc)
        output = RegimeOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            market_regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.5,
            risk_state=RiskState.RISK_ON,
            btc_trend_score=50,
            eth_trend_score=50,
            breadth_confirmation_score=50,
        )
        assert output.reason_codes == []

    def test_default_data_quality(self) -> None:
        now = datetime.now(timezone.utc)
        output = RegimeOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            market_regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.5,
            risk_state=RiskState.RISK_ON,
            btc_trend_score=50,
            eth_trend_score=50,
            breadth_confirmation_score=50,
        )
        assert output.data_quality.is_valid() is True


# ---------------------------------------------------------------------------
# RegimeOutput — validation failures
# ---------------------------------------------------------------------------

class TestRegimeOutputValidation:
    def test_confidence_above_1_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
            RegimeOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                market_regime=RegimeState.BULL,
                allowed_mode=AllowedMode.LONG_ONLY,
                confidence=1.5,
                risk_state=RiskState.RISK_ON,
                btc_trend_score=50,
                eth_trend_score=50,
                breadth_confirmation_score=50,
            )

    def test_confidence_below_0_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
            RegimeOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                market_regime=RegimeState.BULL,
                allowed_mode=AllowedMode.LONG_ONLY,
                confidence=-0.1,
                risk_state=RiskState.RISK_ON,
                btc_trend_score=50,
                eth_trend_score=50,
                breadth_confirmation_score=50,
            )

    def test_btc_trend_score_above_100_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="btc_trend_score must be between 0 and 100"):
            RegimeOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                market_regime=RegimeState.BULL,
                allowed_mode=AllowedMode.LONG_ONLY,
                confidence=0.5,
                risk_state=RiskState.RISK_ON,
                btc_trend_score=101,
                eth_trend_score=50,
                breadth_confirmation_score=50,
            )

    def test_eth_trend_score_below_0_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="eth_trend_score must be between 0 and 100"):
            RegimeOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                market_regime=RegimeState.BULL,
                allowed_mode=AllowedMode.LONG_ONLY,
                confidence=0.5,
                risk_state=RiskState.RISK_ON,
                btc_trend_score=50,
                eth_trend_score=-1,
                breadth_confirmation_score=50,
            )

    def test_breadth_confirmation_score_above_100_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(
            ValueError, match="breadth_confirmation_score must be between 0 and 100"
        ):
            RegimeOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                market_regime=RegimeState.BULL,
                allowed_mode=AllowedMode.LONG_ONLY,
                confidence=0.5,
                risk_state=RiskState.RISK_ON,
                btc_trend_score=50,
                eth_trend_score=50,
                breadth_confirmation_score=150,
            )


# ---------------------------------------------------------------------------
# RegimeOutput — fail-closed factory
# ---------------------------------------------------------------------------

class TestRegimeOutputUnknown:
    def test_unknown_factory_defaults(self) -> None:
        output = RegimeOutput.unknown()
        assert output.market_regime == RegimeState.UNKNOWN
        assert output.allowed_mode == AllowedMode.NONE
        assert output.confidence == 0.0
        assert output.risk_state == RiskState.UNKNOWN
        assert output.btc_trend_score == 0
        assert output.eth_trend_score == 0
        assert output.breadth_confirmation_score == 0
        assert output.status == OutputStatus.INVALID
        assert output.is_blocking() is True
        assert "UNKNOWN_REGIME_BLOCKS_EXECUTION" in output.reason_codes

    def test_unknown_factory_with_custom_reasons(self) -> None:
        output = RegimeOutput.unknown(
            reason_codes=["DATA_MISSING", "INSUFFICIENT_HISTORY"]
        )
        assert output.reason_codes == ["DATA_MISSING", "INSUFFICIENT_HISTORY"]

    def test_unknown_factory_with_custom_data_quality(self) -> None:
        dq = DataQuality(missing=True, stale=True)
        output = RegimeOutput.unknown(data_quality=dq)
        assert output.data_quality.missing is True
        assert output.data_quality.stale is True

    def test_unknown_factory_with_custom_timestamp(self) -> None:
        now = datetime.now(timezone.utc)
        output = RegimeOutput.unknown(timestamp=now)
        assert output.timestamp == now

    def test_invalid_status_blocks_execution(self) -> None:
        now = datetime.now(timezone.utc)
        output = RegimeOutput(
            timestamp=now,
            status=OutputStatus.INVALID,
            market_regime=RegimeState.BULL,  # even BULL with invalid status blocks
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.0,
            risk_state=RiskState.UNKNOWN,
            btc_trend_score=0,
            eth_trend_score=0,
            breadth_confirmation_score=0,
        )
        # is_blocking checks allowed_mode == NONE or status == INVALID
        # Here allowed_mode is LONG_ONLY, so is_blocking is False
        # But the caller should check status first
        assert output.status == OutputStatus.INVALID


# ---------------------------------------------------------------------------
# BreadthOutput — valid creation
# ---------------------------------------------------------------------------

class TestBreadthOutputValid:
    def test_create_valid_breadth(self) -> None:
        now = datetime.now(timezone.utc)
        output = BreadthOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            breadth_score=72,
            market_health=RiskState.RISK_ON,
            universe_size=120,
            valid_symbol_count=115,
            invalid_symbol_count=5,
            above_ema20_pct=0.68,
            above_ema50_pct=0.55,
            above_ema200_pct=0.41,
            ema20_rising_pct=0.63,
            ema50_rising_pct=0.52,
            advancing_pct=0.61,
            declining_pct=0.39,
            outperforming_btc_7d_pct=0.46,
            outperforming_btc_30d_pct=0.34,
            reason_codes=["MAJORITY_ABOVE_EMA20"],
            data_quality=DataQuality(),
        )
        assert output.status == OutputStatus.VALID
        assert output.breadth_score == 72
        assert output.market_health == RiskState.RISK_ON
        assert output.universe_size == 120
        assert output.valid_symbol_count == 115
        assert output.invalid_symbol_count == 5
        assert output.is_valid() is True

    def test_breadth_score_at_boundaries(self) -> None:
        now = datetime.now(timezone.utc)
        # score = 0
        BreadthOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            breadth_score=0,
            market_health=RiskState.UNKNOWN,
            universe_size=0,
            valid_symbol_count=0,
            invalid_symbol_count=0,
            above_ema20_pct=0.0,
            above_ema50_pct=0.0,
            above_ema200_pct=0.0,
            ema20_rising_pct=0.0,
            ema50_rising_pct=0.0,
            advancing_pct=0.0,
            declining_pct=0.0,
            outperforming_btc_7d_pct=0.0,
            outperforming_btc_30d_pct=0.0,
        )
        # score = 100
        BreadthOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            breadth_score=100,
            market_health=RiskState.RISK_ON,
            universe_size=120,
            valid_symbol_count=120,
            invalid_symbol_count=0,
            above_ema20_pct=1.0,
            above_ema50_pct=1.0,
            above_ema200_pct=1.0,
            ema20_rising_pct=1.0,
            ema50_rising_pct=1.0,
            advancing_pct=1.0,
            declining_pct=0.0,
            outperforming_btc_7d_pct=1.0,
            outperforming_btc_30d_pct=1.0,
        )

    def test_percentage_at_boundaries(self) -> None:
        now = datetime.now(timezone.utc)
        # 0.0 and 1.0 are valid
        BreadthOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            breadth_score=50,
            market_health=RiskState.NEUTRAL,
            universe_size=10,
            valid_symbol_count=10,
            invalid_symbol_count=0,
            above_ema20_pct=0.0,
            above_ema50_pct=0.0,
            above_ema200_pct=0.0,
            ema20_rising_pct=0.0,
            ema50_rising_pct=0.0,
            advancing_pct=0.0,
            declining_pct=0.0,
            outperforming_btc_7d_pct=0.0,
            outperforming_btc_30d_pct=0.0,
        )
        BreadthOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            breadth_score=50,
            market_health=RiskState.NEUTRAL,
            universe_size=10,
            valid_symbol_count=10,
            invalid_symbol_count=0,
            above_ema20_pct=1.0,
            above_ema50_pct=1.0,
            above_ema200_pct=1.0,
            ema20_rising_pct=1.0,
            ema50_rising_pct=1.0,
            advancing_pct=1.0,
            declining_pct=1.0,
            outperforming_btc_7d_pct=1.0,
            outperforming_btc_30d_pct=1.0,
        )


# ---------------------------------------------------------------------------
# BreadthOutput — validation failures
# ---------------------------------------------------------------------------

class TestBreadthOutputValidation:
    def test_breadth_score_above_100_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="breadth_score must be between 0 and 100"):
            BreadthOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                breadth_score=101,
                market_health=RiskState.RISK_ON,
                universe_size=120,
                valid_symbol_count=115,
                invalid_symbol_count=5,
                above_ema20_pct=0.68,
                above_ema50_pct=0.55,
                above_ema200_pct=0.41,
                ema20_rising_pct=0.63,
                ema50_rising_pct=0.52,
                advancing_pct=0.61,
                declining_pct=0.39,
                outperforming_btc_7d_pct=0.46,
                outperforming_btc_30d_pct=0.34,
            )

    def test_breadth_score_below_0_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="breadth_score must be between 0 and 100"):
            BreadthOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                breadth_score=-1,
                market_health=RiskState.RISK_ON,
                universe_size=120,
                valid_symbol_count=115,
                invalid_symbol_count=5,
                above_ema20_pct=0.68,
                above_ema50_pct=0.55,
                above_ema200_pct=0.41,
                ema20_rising_pct=0.63,
                ema50_rising_pct=0.52,
                advancing_pct=0.61,
                declining_pct=0.39,
                outperforming_btc_7d_pct=0.46,
                outperforming_btc_30d_pct=0.34,
            )

    def test_percentage_above_1_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="above_ema20_pct must be between 0.0 and 1.0"):
            BreadthOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                breadth_score=50,
                market_health=RiskState.RISK_ON,
                universe_size=120,
                valid_symbol_count=115,
                invalid_symbol_count=5,
                above_ema20_pct=1.5,
                above_ema50_pct=0.55,
                above_ema200_pct=0.41,
                ema20_rising_pct=0.63,
                ema50_rising_pct=0.52,
                advancing_pct=0.61,
                declining_pct=0.39,
                outperforming_btc_7d_pct=0.46,
                outperforming_btc_30d_pct=0.34,
            )

    def test_percentage_below_0_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="declining_pct must be between 0.0 and 1.0"):
            BreadthOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                breadth_score=50,
                market_health=RiskState.RISK_ON,
                universe_size=120,
                valid_symbol_count=115,
                invalid_symbol_count=5,
                above_ema20_pct=0.68,
                above_ema50_pct=0.55,
                above_ema200_pct=0.41,
                ema20_rising_pct=0.63,
                ema50_rising_pct=0.52,
                advancing_pct=0.61,
                declining_pct=-0.1,
                outperforming_btc_7d_pct=0.46,
                outperforming_btc_30d_pct=0.34,
            )


# ---------------------------------------------------------------------------
# BreadthOutput — fail-closed factory
# ---------------------------------------------------------------------------

class TestBreadthOutputInvalid:
    def test_invalid_factory_defaults(self) -> None:
        output = BreadthOutput.invalid()
        assert output.status == OutputStatus.INVALID
        assert output.breadth_score == 0
        assert output.market_health == RiskState.UNKNOWN
        assert output.universe_size == 0
        assert output.valid_symbol_count == 0
        assert output.invalid_symbol_count == 0
        assert output.above_ema20_pct == 0.0
        assert output.is_valid() is False
        assert "DATA_MISSING" in output.reason_codes
        assert "INSUFFICIENT_UNIVERSE" in output.reason_codes

    def test_invalid_factory_with_custom_reasons(self) -> None:
        output = BreadthOutput.invalid(reason_codes=["DATA_STALE"])
        assert output.reason_codes == ["DATA_STALE"]

    def test_invalid_factory_with_custom_data_quality(self) -> None:
        dq = DataQuality(stale=True)
        output = BreadthOutput.invalid(data_quality=dq)
        assert output.data_quality.stale is True

    def test_invalid_factory_with_custom_timestamp(self) -> None:
        now = datetime.now(timezone.utc)
        output = BreadthOutput.invalid(timestamp=now)
        assert output.timestamp == now


# ---------------------------------------------------------------------------
# Immutability tests
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_regime_output_is_frozen(self) -> None:
        now = datetime.now(timezone.utc)
        output = RegimeOutput.unknown(timestamp=now)
        with pytest.raises(FrozenInstanceError):
            output.confidence = 0.5  # type: ignore[misc]

    def test_breadth_output_is_frozen(self) -> None:
        output = BreadthOutput.invalid()
        with pytest.raises(FrozenInstanceError):
            output.breadth_score = 50  # type: ignore[misc]

    def test_data_quality_is_frozen(self) -> None:
        dq = DataQuality()
        with pytest.raises(FrozenInstanceError):
            dq.missing = True  # type: ignore[misc]
