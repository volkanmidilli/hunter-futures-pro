"""Validation functions for research campaign definitions and compiled campaigns (MVP-69/MVP-70 / SPEC-070)."""

from __future__ import annotations

from hunter.research_campaign.errors import ResearchCampaignDefinitionError
from hunter.research_campaign.models import (
    CampaignExecutionPolicy,
    CampaignParameterSet,
    CompiledCampaign,
    EMPTY_PARAMETER_SET,
    EXECUTION_POLICY_VIOLATION,
    INHERITED_SAFETY_VIOLATION,
    INVALID_DEFINITION,
    ResearchCampaignDefinition,
    ZERO_EXPERIMENT_CAMPAIGN,
)


def _check_empty_parameters(params: CampaignParameterSet) -> None:
    """Raise if any parameter sequence is empty (identity-level re-check)."""
    for name, value in (
        ("strategies", params.strategies),
        ("timeframes", params.timeframes),
        ("historical_data", params.historical_data),
        ("universe_plans", params.universe_plans),
        ("walk_forward_templates", params.walk_forward_templates),
        ("confidence_configs", params.confidence_configs),
        ("experiment_families", params.experiment_families),
        ("hypothesis_families", params.hypothesis_families),
        ("metric_families", params.metric_families),
        ("independence_metadata", params.independence_metadata),
        ("regime_policies", params.regime_policies),
    ):
        if len(value) == 0:
            raise ResearchCampaignDefinitionError(
                f"Parameter set {name!r} must not be empty",
                reason_code=EMPTY_PARAMETER_SET,
            )


def _check_non_canonical_parameters(params: CampaignParameterSet) -> None:
    """Raise if any parameter sequence is not a tuple (non-canonical)."""
    for name, value in (
        ("strategies", params.strategies),
        ("timeframes", params.timeframes),
        ("historical_data", params.historical_data),
        ("universe_plans", params.universe_plans),
        ("walk_forward_templates", params.walk_forward_templates),
        ("confidence_configs", params.confidence_configs),
        ("experiment_families", params.experiment_families),
        ("hypothesis_families", params.hypothesis_families),
        ("metric_families", params.metric_families),
        ("independence_metadata", params.independence_metadata),
        ("regime_policies", params.regime_policies),
    ):
        if not isinstance(value, tuple):
            raise ResearchCampaignDefinitionError(
                f"Parameter set {name!r} must be a tuple, got {type(value).__name__}",
                reason_code="NON_CANONICAL_PARAMETER_SET",
            )


def _check_execution_policy(definition: ResearchCampaignDefinition) -> None:
    """Validate execution policy constraints."""
    if definition.execution_policy == CampaignExecutionPolicy.STOP_AFTER_N_FAILURES:
        if not isinstance(definition.stop_after_n_failures, int) or definition.stop_after_n_failures < 1:
            raise ResearchCampaignDefinitionError(
                "STOP_AFTER_N_FAILURES requires a positive integer stop_after_n_failures",
                reason_code=EXECUTION_POLICY_VIOLATION,
            )


def _check_output_policy(definition: ResearchCampaignDefinition) -> None:
    """Raise if output_policy is missing."""
    if definition.output_policy is None:
        raise ResearchCampaignDefinitionError(
            "Campaign definition must specify an output_policy",
            reason_code=INVALID_DEFINITION,
        )


def _check_safety_flags(definition: ResearchCampaignDefinition) -> None:
    """Raise if any mandatory safety invariant is violated."""
    flags = definition.safety_flags

    violations: list[str] = []
    if not flags.research_only:
        violations.append("research_only must be True")
    if flags.execution_approval_granted:
        violations.append("execution_approval_granted must be False")
    if flags.production_approval_granted:
        violations.append("production_approval_granted must be False")
    if flags.live_trading_allowed:
        violations.append("live_trading_allowed must be False")
    if flags.automatic_execution_allowed:
        violations.append("automatic_execution_allowed must be False")
    if not flags.human_approval_required:
        violations.append("human_approval_required must be True")
    if not flags.no_action_commands_emitted:
        violations.append("no_action_commands_emitted must be True")
    if not flags.no_network_connection:
        violations.append("no_network_connection must be True")
    if not flags.no_database_connection:
        violations.append("no_database_connection must be True")
    if not flags.no_exchange_connection:
        violations.append("no_exchange_connection must be True")
    if not flags.no_remote_changes:
        violations.append("no_remote_changes must be True")
    if not flags.no_parallel_execution:
        violations.append("no_parallel_execution must be True")
    if not flags.no_direct_subprocess:
        violations.append("no_direct_subprocess must be True")
    if not flags.no_strategy_mutation:
        violations.append("no_strategy_mutation must be True")
    if not flags.no_universe_mutation:
        violations.append("no_universe_mutation must be True")
    if not flags.no_config_mutation:
        violations.append("no_config_mutation must be True")

    if violations:
        msg = "; ".join(violations)
        raise ResearchCampaignDefinitionError(
            f"Safety flag violations: {msg}",
            reason_code=INHERITED_SAFETY_VIOLATION,
        )


def validate_definition(definition: ResearchCampaignDefinition) -> None:
    """Validate a research campaign definition.

    Rejects empty / non-canonical parameter sets, execution-policy
    violations, missing output policy, and safety-flag violations.

    Raises
    ------
    ResearchCampaignDefinitionError
        With an appropriate reason code on the first violation.
    """
    # 1. Empty parameter sets (redundant with CampaignParameterSet.__post_init__
    #    but enforced at the validation boundary as well).
    _check_empty_parameters(definition.parameters)

    # 2. Non-canonical parameter sets (not tuples).
    _check_non_canonical_parameters(definition.parameters)

    # 3. Execution policy constraints.
    _check_execution_policy(definition)

    # 4. Output policy must be present.
    _check_output_policy(definition)

    # 5. Safety flag invariants.
    _check_safety_flags(definition)


def validate_compiled_campaign(compiled: CompiledCampaign) -> None:
    """Validate a compiled campaign.

    Validates the embedded definition and checks campaign-level
    invariants such as experiment count.

    Raises
    ------
    ResearchCampaignDefinitionError
        If the compiled campaign is invalid.
    """
    # Re-validate the campaign definition.
    validate_definition(compiled.campaign)

    # Non-zero experiment check.
    if compiled.experiment_count == 0:
        raise ResearchCampaignDefinitionError(
            "Compiled campaign must contain at least one experiment",
            reason_code=ZERO_EXPERIMENT_CAMPAIGN,
        )

    # Consistency check.
    if compiled.experiment_count != len(compiled.experiments):
        raise ResearchCampaignDefinitionError(
            f"experiment_count ({compiled.experiment_count}) "
            f"does not match experiments tuple length ({len(compiled.experiments)})",
            reason_code=INVALID_DEFINITION,
        )
