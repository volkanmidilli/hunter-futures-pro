"""Declarative filter rules for research campaign matrix compilation (MVP-69 / SPEC-070).

No eval, dynamic code, or arbitrary Python.
"""

from __future__ import annotations

from typing import Any

from hunter.research_campaign.errors import ResearchCampaignFilterError
from hunter.research_campaign.models import (
    CampaignFilterRule,
    CONTRADICTORY_FILTER_RULES,
    FilterOperator,
)

# Canonical combination keys that filter rules operate on.
_CANONICAL_KEYS: frozenset[str] = frozenset({
    "strategy_name",
    "timeframe",
    "data_id",
    "universe_plan_id",
    "template_id",
    "config_id",
    "experiment_family_id",
    "hypothesis_family_id",
    "metric_names",
    "independence_class",
    "regime_label",
})


def _get_field_value(combination: dict[str, Any], field: str) -> Any | None:
    """Look up *field* in *combination*; return None if absent."""
    return combination.get(field)


def apply_filter_rule(combination: dict[str, Any], rule: CampaignFilterRule) -> bool:
    """Return True if *combination* matches *rule*.

    Parameters
    ----------
    combination : dict[str, Any]
        A canonical combination dict with keys from ``_CANONICAL_KEYS``.
    rule : CampaignFilterRule
        The declarative filter rule to evaluate.

    Returns
    -------
    bool
        True if the rule matches the combination.

    Raises
    ------
    ResearchCampaignFilterError
        If the rule field is not a known canonical key.
    """
    if rule.operator == FilterOperator.MATCH_ALL:
        return True

    if rule.field not in _CANONICAL_KEYS:
        raise ResearchCampaignFilterError(
            f"Unknown filter field {rule.field!r}; expected one of {sorted(_CANONICAL_KEYS)}",
            reason_code="INVALID_FILTER_RULE",
        )

    field_value = _get_field_value(combination, rule.field)

    operator = rule.operator
    value = rule.value

    if operator == FilterOperator.EQUALS:
        return field_value == value

    if operator == FilterOperator.NOT_EQUALS:
        return field_value != value

    if operator == FilterOperator.IN:
        if not isinstance(value, tuple):
            raise ResearchCampaignFilterError(
                f"IN operator requires a tuple value, got {type(value).__name__}",
                reason_code="INVALID_FILTER_RULE",
            )
        return field_value in value

    if operator == FilterOperator.NOT_IN:
        if not isinstance(value, tuple):
            raise ResearchCampaignFilterError(
                f"NOT_IN operator requires a tuple value, got {type(value).__name__}",
                reason_code="INVALID_FILTER_RULE",
            )
        return field_value not in value

    if operator == FilterOperator.PREFIX:
        if not isinstance(field_value, str):
            return False
        return field_value.startswith(str(value))

    # Unreachable: all FilterOperator values handled above.
    raise ResearchCampaignFilterError(
        f"Unsupported filter operator {operator!r}",
        reason_code="INVALID_FILTER_RULE",
    )


def check_contradictory_rules(rules: tuple[CampaignFilterRule, ...]) -> None:
    """Detect contradictory filter rules and raise.

    A contradiction exists when:
    - An include MATCH_ALL rule is paired with any exclude rule; or
    - An include and an exclude rule share the same field, operator, and value.

    Raises
    ------
    ResearchCampaignFilterError
        With reason code ``CONTRADICTORY_FILTER_RULES`` on first detection.
    """
    includes = [r for r in rules if r.action == "include"]
    excludes = [r for r in rules if r.action == "exclude"]

    # MATCH_ALL include paired with any exclude.
    for inc in includes:
        if inc.operator == FilterOperator.MATCH_ALL:
            for exc in excludes:
                raise ResearchCampaignFilterError(
                    f"Include MATCH_ALL contradicts exclude rule on field {exc.field!r} "
                    f"with operator {exc.operator.value}",
                    reason_code=CONTRADICTORY_FILTER_RULES,
                )

    # Same field, operator, and value across include/exclude.
    for inc in includes:
        for exc in excludes:
            if inc.field == exc.field and inc.operator == exc.operator and inc.value == exc.value:
                raise ResearchCampaignFilterError(
                    f"Contradictory include/exclude rules on field {inc.field!r} "
                    f"with operator {inc.operator.value} and value {inc.value!r}",
                    reason_code=CONTRADICTORY_FILTER_RULES,
                )


def filter_combinations(
    combinations: list[dict[str, Any]],
    include_rules: tuple[CampaignFilterRule, ...],
    exclude_rules: tuple[CampaignFilterRule, ...],
) -> list[dict[str, Any]]:
    """Filter a list of canonical combinations through include/exclude rules.

    - If any include rules are present, a combination must match **at least
      one** include rule to be retained (OR semantics).
    - If any exclude rules are present, a combination that matches **any**
      exclude rule is dropped (OR semantics).
    - Include rules are evaluated before exclude rules.

    Returns
    -------
    list[dict[str, Any]]
        Filtered combinations.
    """
    result: list[dict[str, Any]] = []

    for combination in combinations:
        # Include rules (OR): if present, at least one must match.
        if include_rules:
            if not any(apply_filter_rule(combination, r) for r in include_rules):
                continue

        # Exclude rules (OR): if any matches, drop.
        if exclude_rules:
            if any(apply_filter_rule(combination, r) for r in exclude_rules):
                continue

        result.append(combination)

    return result
