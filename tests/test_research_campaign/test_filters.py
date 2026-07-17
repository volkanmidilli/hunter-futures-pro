"""Tests for research_campaign filters (MVP-69/MVP-70)."""

from __future__ import annotations

import pytest

from hunter.research_campaign.errors import ResearchCampaignFilterError
from hunter.research_campaign.filters import (
    apply_filter_rule,
    check_contradictory_rules,
    filter_combinations,
)
from hunter.research_campaign.models import (
    CampaignFilterRule,
    FilterOperator,
)


def _canonical_combo(**overrides) -> dict:
    """Build a canonical combination dict with defaults."""
    base = {
        "strategy_name": "strat_a",
        "timeframe": "1h",
        "data_id": "ohlcv_1h",
        "universe_plan_id": "uni_a",
        "template_id": "wf_rolling",
        "config_id": "conf_a",
        "experiment_family_id": "exp_fam_a",
        "hypothesis_family_id": "hyp_fam_a",
        "metric_names": ("sharpe_ratio",),
        "independence_class": "INDEPENDENT",
        "regime_label": "UNKNOWN",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test each operator
# ---------------------------------------------------------------------------


class TestFilterOperatorEquals:
    def test_equals_match(self) -> None:
        combo = _canonical_combo(strategy_name="strat_a")
        rule = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.EQUALS,
            value="strat_a",
            action="include",
        )
        assert apply_filter_rule(combo, rule) is True

    def test_equals_no_match(self) -> None:
        combo = _canonical_combo(strategy_name="strat_b")
        rule = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.EQUALS,
            value="strat_a",
            action="include",
        )
        assert apply_filter_rule(combo, rule) is False


class TestFilterOperatorNotEquals:
    def test_not_equals_match(self) -> None:
        combo = _canonical_combo(strategy_name="strat_b")
        rule = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.NOT_EQUALS,
            value="strat_a",
            action="include",
        )
        assert apply_filter_rule(combo, rule) is True

    def test_not_equals_no_match(self) -> None:
        combo = _canonical_combo(strategy_name="strat_a")
        rule = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.NOT_EQUALS,
            value="strat_a",
            action="include",
        )
        assert apply_filter_rule(combo, rule) is False


class TestFilterOperatorIn:
    def test_in_match(self) -> None:
        combo = _canonical_combo(timeframe="4h")
        rule = CampaignFilterRule(
            field="timeframe",
            operator=FilterOperator.IN,
            value=("1h", "4h"),
            action="include",
        )
        assert apply_filter_rule(combo, rule) is True

    def test_in_no_match(self) -> None:
        combo = _canonical_combo(timeframe="1d")
        rule = CampaignFilterRule(
            field="timeframe",
            operator=FilterOperator.IN,
            value=("1h", "4h"),
            action="include",
        )
        assert apply_filter_rule(combo, rule) is False


class TestFilterOperatorNotIn:
    def test_not_in_match(self) -> None:
        combo = _canonical_combo(timeframe="1d")
        rule = CampaignFilterRule(
            field="timeframe",
            operator=FilterOperator.NOT_IN,
            value=("1h", "4h"),
            action="include",
        )
        assert apply_filter_rule(combo, rule) is True

    def test_not_in_no_match(self) -> None:
        combo = _canonical_combo(timeframe="1h")
        rule = CampaignFilterRule(
            field="timeframe",
            operator=FilterOperator.NOT_IN,
            value=("1h", "4h"),
            action="include",
        )
        assert apply_filter_rule(combo, rule) is False


class TestFilterOperatorPrefix:
    def test_prefix_match(self) -> None:
        combo = _canonical_combo(strategy_name="strat_extra")
        rule = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.PREFIX,
            value="strat_",
            action="include",
        )
        assert apply_filter_rule(combo, rule) is True

    def test_prefix_no_match(self) -> None:
        combo = _canonical_combo(strategy_name="other")
        rule = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.PREFIX,
            value="strat_",
            action="include",
        )
        assert apply_filter_rule(combo, rule) is False

    def test_prefix_non_string_field(self) -> None:
        """PREFIX on a non-string field returns False."""
        combo = _canonical_combo(metric_names=("sharpe_ratio",))
        rule = CampaignFilterRule(
            field="metric_names",
            operator=FilterOperator.PREFIX,
            value="sharpe",
            action="include",
        )
        # metric_names is a tuple, so PREFIX returns False
        assert apply_filter_rule(combo, rule) is False


class TestFilterOperatorMatchAll:
    def test_match_all_always_true(self) -> None:
        combo = _canonical_combo()
        rule = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.MATCH_ALL,
            value="ignored",
            action="include",
        )
        assert apply_filter_rule(combo, rule) is True

    def test_match_all_different_field_still_true(self) -> None:
        combo = _canonical_combo()
        rule = CampaignFilterRule(
            field="timeframe",
            operator=FilterOperator.MATCH_ALL,
            value="anything",
            action="include",
        )
        assert apply_filter_rule(combo, rule) is True


# ---------------------------------------------------------------------------
# Unknown field raises
# ---------------------------------------------------------------------------


class TestUnknownField:
    def test_unknown_field_raises(self) -> None:
        combo = _canonical_combo()
        rule = CampaignFilterRule(
            field="nonexistent_field",
            operator=FilterOperator.EQUALS,
            value="x",
            action="include",
        )
        with pytest.raises(ResearchCampaignFilterError, match="Unknown filter field"):
            apply_filter_rule(combo, rule)


# ---------------------------------------------------------------------------
# Contradictory rule detection
# ---------------------------------------------------------------------------


class TestContradictoryRules:
    def test_same_field_value_include_exclude(self) -> None:
        """Same field, operator, and value across include/exclude is contradictory."""
        inc = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.EQUALS,
            value="strat_a",
            action="include",
        )
        exc = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.EQUALS,
            value="strat_a",
            action="exclude",
        )
        with pytest.raises(ResearchCampaignFilterError, match="Contradictory"):
            check_contradictory_rules((inc, exc))

    def test_match_all_include_with_exclude(self) -> None:
        """MATCH_ALL include paired with any exclude is contradictory."""
        inc = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.MATCH_ALL,
            value="any",
            action="include",
        )
        exc = CampaignFilterRule(
            field="timeframe",
            operator=FilterOperator.EQUALS,
            value="1h",
            action="exclude",
        )
        with pytest.raises(ResearchCampaignFilterError, match="MATCH_ALL"):
            check_contradictory_rules((inc, exc))

    def test_non_contradictory_pass(self) -> None:
        """Different field/operator/value pairs pass."""
        inc = CampaignFilterRule(
            field="strategy_name",
            operator=FilterOperator.EQUALS,
            value="strat_a",
            action="include",
        )
        exc = CampaignFilterRule(
            field="timeframe",
            operator=FilterOperator.EQUALS,
            value="1d",
            action="exclude",
        )
        # Should not raise
        check_contradictory_rules((inc, exc))

    def test_no_rules_pass(self) -> None:
        """No rules means no contradiction."""
        check_contradictory_rules(())


# ---------------------------------------------------------------------------
# filter_combinations integration
# ---------------------------------------------------------------------------


class TestFilterCombinations:
    def test_no_rules_returns_all(self) -> None:
        combos = [_canonical_combo(strategy_name="a"), _canonical_combo(strategy_name="b")]
        result = filter_combinations(combos, include_rules=(), exclude_rules=())
        assert len(result) == 2

    def test_include_rule_selects(self) -> None:
        combos = [_canonical_combo(strategy_name="a"), _canonical_combo(strategy_name="b")]
        rules = (
            CampaignFilterRule(
                field="strategy_name",
                operator=FilterOperator.EQUALS,
                value="a",
                action="include",
            ),
        )
        result = filter_combinations(combos, include_rules=rules, exclude_rules=())
        assert len(result) == 1
        assert result[0]["strategy_name"] == "a"

    def test_exclude_rule_removes(self) -> None:
        combos = [_canonical_combo(strategy_name="a"), _canonical_combo(strategy_name="b")]
        rules = (
            CampaignFilterRule(
                field="strategy_name",
                operator=FilterOperator.EQUALS,
                value="a",
                action="exclude",
            ),
        )
        result = filter_combinations(combos, include_rules=(), exclude_rules=rules)
        assert len(result) == 1
        assert result[0]["strategy_name"] == "b"

    def test_include_and_exclude_together(self) -> None:
        """Include strat_a or strat_b, exclude strat_b → only strat_a."""
        combos = [
            _canonical_combo(strategy_name="a"),
            _canonical_combo(strategy_name="b"),
            _canonical_combo(strategy_name="c"),
        ]
        include = (
            CampaignFilterRule(
                field="strategy_name",
                operator=FilterOperator.IN,
                value=("a", "b"),
                action="include",
            ),
        )
        exclude = (
            CampaignFilterRule(
                field="strategy_name",
                operator=FilterOperator.EQUALS,
                value="b",
                action="exclude",
            ),
        )
        result = filter_combinations(combos, include_rules=include, exclude_rules=exclude)
        assert len(result) == 1
        assert result[0]["strategy_name"] == "a"

    def test_include_or_semantics(self) -> None:
        """OR semantics: at least one include rule must match."""
        combos = [
            _canonical_combo(strategy_name="a", timeframe="1h"),
            _canonical_combo(strategy_name="b", timeframe="4h"),
            _canonical_combo(strategy_name="c", timeframe="1d"),
        ]
        include = (
            CampaignFilterRule(
                field="strategy_name",
                operator=FilterOperator.EQUALS,
                value="a",
                action="include",
            ),
            CampaignFilterRule(
                field="timeframe",
                operator=FilterOperator.EQUALS,
                value="4h",
                action="include",
            ),
        )
        result = filter_combinations(combos, include_rules=include, exclude_rules=())
        assert len(result) == 2
        names = {c["strategy_name"] for c in result}
        assert names == {"a", "b"}

    def test_include_not_matching_drops_all(self) -> None:
        """If no combination matches any include rule, result is empty."""
        combos = [_canonical_combo(strategy_name="a"), _canonical_combo(strategy_name="b")]
        include = (
            CampaignFilterRule(
                field="strategy_name",
                operator=FilterOperator.EQUALS,
                value="nonexistent",
                action="include",
            ),
        )
        result = filter_combinations(combos, include_rules=include, exclude_rules=())
        assert len(result) == 0

    def test_match_all_include_keeps_all(self) -> None:
        """MATCH_ALL include keeps all combinations."""
        combos = [
            _canonical_combo(strategy_name="a"),
            _canonical_combo(strategy_name="b"),
        ]
        include = (
            CampaignFilterRule(
                field="strategy_name",
                operator=FilterOperator.MATCH_ALL,
                value="anything",
                action="include",
            ),
        )
        result = filter_combinations(combos, include_rules=include, exclude_rules=())
        assert len(result) == 2
