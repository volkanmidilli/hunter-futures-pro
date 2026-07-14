"""Tests for portfolio_research_adapter validators (MVP-57 Step 2)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from hunter.portfolio_research_adapter.models import (
    BLACKLISTED_PAIR,
    BLOCK_ALL_CONTEXT,
    CONTRADICTORY_CONTEXT,
    EMPTY_WHITELIST,
    INVALID_CONFIG,
    INVALID_PAIR,
    INVALID_SCORE,
    MISSING_CONTEXT,
    MISSING_SCORE,
    PORTFOLIO_ACCEPTED,
    REJECTED_CONTEXT,
    PortfolioResearchConfig,
    PortfolioResearchError,
)
from hunter.portfolio_research_adapter.validator import (
    check_blacklist_exclusion,
    validate_cluster_mapping,
    validate_portfolio_research_config,
    validate_portfolio_research_input,
    validate_score_mapping,
)
from hunter.strategy_contract_consumer.models import ValidatedStrategyContext


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def accepted_context(now: datetime) -> ValidatedStrategyContext:
    return ValidatedStrategyContext(
        accepted=True,
        validated_at=now,
        source_fingerprint="sha256-source",
        source_path="strategy_contract_input.json",
        input_version="0.56.0-dev",
        mode="LONG",
        whitelist=("BTC/USDT", "ETH/USDT", "SOL/USDT"),
        blacklist=(),
        safety_flags={},
        reason_codes=("VALIDATION_ACCEPTED",),
    )


@pytest.fixture
def config() -> PortfolioResearchConfig:
    return PortfolioResearchConfig.default()


class TestValidatePortfolioResearchConfig:
    def test_valid_config(self, config: PortfolioResearchConfig):
        validate_portfolio_research_config(config)

    def test_none_config(self):
        with pytest.raises(PortfolioResearchError, match="config is required"):
            validate_portfolio_research_config(None)
        error = PortfolioResearchError("config is required", reason_code=INVALID_CONFIG)
        assert error.reason_code == INVALID_CONFIG

    def test_invalid_config_type(self):
        with pytest.raises(PortfolioResearchError, match="PortfolioResearchConfig"):
            validate_portfolio_research_config("bad")


class TestValidatePortfolioResearchInput:
    def test_accepted_context(self, accepted_context, config):
        is_valid, codes = validate_portfolio_research_input(accepted_context, config)
        assert is_valid
        assert codes == [PORTFOLIO_ACCEPTED]

    def test_missing_context(self, config):
        is_valid, codes = validate_portfolio_research_input(None, config)
        assert not is_valid
        assert codes == [MISSING_CONTEXT]

    def test_rejected_context(self, accepted_context, config):
        context = _replace(
            accepted_context, accepted=False, mode="BLOCK_ALL", whitelist=()
        )
        is_valid, codes = validate_portfolio_research_input(context, config)
        assert not is_valid
        assert codes == [REJECTED_CONTEXT]

    def test_block_all_mode(self, accepted_context, config):
        context = _replace(accepted_context, mode="BLOCK_ALL")
        is_valid, codes = validate_portfolio_research_input(context, config)
        assert not is_valid
        assert codes == [BLOCK_ALL_CONTEXT]

    def test_empty_whitelist(self, accepted_context, config):
        context = _replace(accepted_context, whitelist=())
        is_valid, codes = validate_portfolio_research_input(context, config)
        assert not is_valid
        assert codes == [EMPTY_WHITELIST]

    def test_invalid_pair_format(self, accepted_context, config):
        context = _replace(accepted_context, whitelist=("BTC",))
        is_valid, codes = validate_portfolio_research_input(context, config)
        assert not is_valid
        assert codes == [INVALID_PAIR]

    def test_blacklisted_in_whitelist(self, accepted_context, config):
        context = _replace(accepted_context, blacklist=("BTC/USDT",))
        is_valid, codes = validate_portfolio_research_input(context, config)
        assert not is_valid
        assert codes == [CONTRADICTORY_CONTEXT]

    def test_duplicate_whitelist(self, accepted_context, config):
        context = _replace(accepted_context, whitelist=("BTC/USDT", "BTC/USDT"))
        is_valid, codes = validate_portfolio_research_input(context, config)
        assert not is_valid
        assert codes == [CONTRADICTORY_CONTEXT]

    def test_duplicate_blacklist(self, accepted_context, config):
        context = _replace(accepted_context, blacklist=("BTC/USDT", "BTC/USDT"))
        is_valid, codes = validate_portfolio_research_input(context, config)
        assert not is_valid
        assert codes == [CONTRADICTORY_CONTEXT]


class TestValidateClusterMapping:
    def test_none_mapping(self):
        validate_cluster_mapping(None)

    def test_valid_mapping(self):
        validate_cluster_mapping({"BTC/USDT": "C1", "ETH/USDT": "C2"})

    def test_invalid_key(self):
        with pytest.raises(PortfolioResearchError, match="key"):
            validate_cluster_mapping({"": "C1"})

    def test_invalid_value(self):
        with pytest.raises(PortfolioResearchError, match="value"):
            validate_cluster_mapping({"BTC/USDT": 123})

    def test_invalid_mapping_type(self):
        with pytest.raises(PortfolioResearchError, match="Mapping"):
            validate_cluster_mapping([("BTC/USDT", "C1")])


class TestValidateScoreMapping:
    def test_not_score_proportional(self):
        is_valid, codes, exclusions = validate_score_mapping(
            {"BTC/USDT": Decimal("1")}, ("BTC/USDT",), "EQUAL_WEIGHT"
        )
        assert is_valid
        assert codes == []
        assert exclusions == []

    def test_valid_scores(self):
        is_valid, codes, exclusions = validate_score_mapping(
            {"BTC/USDT": Decimal("1"), "ETH/USDT": Decimal("2")},
            ("BTC/USDT", "ETH/USDT"),
            "SCORE_PROPORTIONAL",
        )
        assert is_valid
        assert codes == []
        assert exclusions == []

    def test_missing_score_by_pair(self):
        is_valid, codes, exclusions = validate_score_mapping(
            None, ("BTC/USDT",), "SCORE_PROPORTIONAL"
        )
        assert not is_valid
        assert codes == [MISSING_SCORE]
        assert exclusions == []

    def test_missing_pair_score(self):
        is_valid, codes, exclusions = validate_score_mapping(
            {"BTC/USDT": Decimal("1")}, ("BTC/USDT", "ETH/USDT"), "SCORE_PROPORTIONAL"
        )
        assert is_valid
        assert codes == []
        assert exclusions == [("ETH/USDT", MISSING_SCORE)]

    def test_invalid_pair_score_negative(self):
        is_valid, codes, exclusions = validate_score_mapping(
            {"BTC/USDT": Decimal("-1")}, ("BTC/USDT",), "SCORE_PROPORTIONAL"
        )
        assert not is_valid
        assert codes == [MISSING_SCORE]
        assert exclusions == [("BTC/USDT", INVALID_SCORE)]

    def test_zero_score_sum(self):
        is_valid, codes, exclusions = validate_score_mapping(
            {"BTC/USDT": Decimal("0"), "ETH/USDT": Decimal("0")},
            ("BTC/USDT", "ETH/USDT"),
            "SCORE_PROPORTIONAL",
        )
        assert not is_valid
        assert codes == [MISSING_SCORE]
        assert exclusions == [("BTC/USDT", INVALID_SCORE), ("ETH/USDT", INVALID_SCORE)]

    def test_invalid_mapping_type(self):
        with pytest.raises(PortfolioResearchError, match="Mapping"):
            validate_score_mapping([("BTC/USDT", Decimal("1"))], ("BTC/USDT",), "SCORE_PROPORTIONAL")

    def test_invalid_score_value_type(self):
        with pytest.raises(PortfolioResearchError, match="Decimal"):
            validate_score_mapping({"BTC/USDT": 1}, ("BTC/USDT",), "SCORE_PROPORTIONAL")


class TestCheckBlacklistExclusion:
    def test_blacklisted(self):
        assert check_blacklist_exclusion("BTC/USDT", ("BTC/USDT", "ETH/USDT")) is True

    def test_not_blacklisted(self):
        assert check_blacklist_exclusion("SOL/USDT", ("BTC/USDT", "ETH/USDT")) is False


def _replace(context: ValidatedStrategyContext, **kwargs) -> ValidatedStrategyContext:
    """Return a new ValidatedStrategyContext with the given fields replaced."""
    return ValidatedStrategyContext(
        accepted=kwargs.get("accepted", context.accepted),
        validated_at=context.validated_at,
        source_fingerprint=context.source_fingerprint,
        source_path=context.source_path,
        input_version=context.input_version,
        mode=kwargs.get("mode", context.mode),
        whitelist=kwargs.get("whitelist", context.whitelist),
        blacklist=kwargs.get("blacklist", context.blacklist),
        safety_flags=kwargs.get("safety_flags", context.safety_flags),
        reason_codes=kwargs.get("reason_codes", context.reason_codes),
    )
