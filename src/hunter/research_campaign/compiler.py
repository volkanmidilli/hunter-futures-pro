"""Campaign matrix compiler — builds a CompiledCampaign from a ResearchCampaignDefinition (MVP-69 / SPEC-070).

No subprocess, threading, network, eval, exec, or dynamic code.
"""

from __future__ import annotations

import itertools
from datetime import datetime, timezone
from typing import Any

from hunter.research_campaign.errors import (
    ResearchCampaignCompilationError,
    ResearchCampaignFilterError,
)
from hunter.research_campaign.filters import (
    check_contradictory_rules,
    filter_combinations,
)
from hunter.research_campaign.fingerprint import (
    compiled_campaign_fingerprint,
    compiled_experiment_fingerprint,
    experiment_id_from_components,
)
from hunter.research_campaign.models import (
    CampaignParameterSet,
    CampaignRegistrationSet,
    CompiledCampaign,
    CompiledExperiment,
    DUPLICATE_LOGICAL_EXPERIMENT,
    MAX_EXPERIMENT_COUNT_EXCEEDED,
    ResearchCampaignDefinition,
    ZERO_EXPERIMENT_CAMPAIGN,
)
from hunter.research_campaign.ordering import canonical_sort_experiments
from hunter.research_campaign.registration import create_campaign_registration_set
from hunter.research_campaign.validator import validate_definition
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardMode,
    WalkForwardSafetyFlags,
)


def _build_canonical_combination(
    strategy: Any,
    timeframe: str,
    data: Any,
    universe: Any,
    template: Any,
    config: Any,
    exp_family: Any,
    hyp_family: Any,
    metric_scope: Any,
    independence: Any,
    regime: Any,
) -> dict[str, Any]:
    """Build a canonical combination dict from one element of each parameter dimension."""
    return {
        "strategy_name": strategy.strategy_name,
        "strategy_fingerprint": strategy.fingerprint,
        "timeframe": timeframe,
        "data_id": data.data_id,
        "data_fingerprint": data.fingerprint,
        "universe_plan_id": universe.universe_plan_id,
        "universe_plan_fingerprint": universe.fingerprint,
        "candidate_universe_fingerprint": universe.candidate_universe_fingerprint,
        "baseline_universe_fingerprint": universe.baseline_universe_fingerprint,
        "template_id": template.template_id,
        "template_fingerprint": template.fingerprint,
        "config_id": config.config_id,
        "config_fingerprint": config.fingerprint,
        "experiment_family_id": exp_family.family_id,
        "experiment_family_fingerprint": exp_family.fingerprint,
        "hypothesis_family_id": hyp_family.family_id,
        "hypothesis_family_fingerprint": hyp_family.fingerprint,
        "metric_names": metric_scope.metric_names,
        "metric_family_fingerprint": metric_scope.fingerprint if getattr(metric_scope, "fingerprint", "") else "",
        "independence_class": independence.independence_class.value
        if hasattr(independence.independence_class, "value")
        else str(independence.independence_class),
        "independence_source_experiment_ids": independence.source_experiment_ids,
        "regime_label": regime.regime_label.value
        if hasattr(regime.regime_label, "value")
        else str(regime.regime_label),
        "regime_required": regime.required,
    }


def _combination_fingerprint_key(combo: dict[str, Any]) -> str:
    """Deterministic string key for deduplication of combination dicts.

    Includes reference fingerprints so that two parameter references with the
    same human-readable ID but different fingerprints are treated as distinct
    logical experiments. For independence and regime (which have no reference
    fingerprint field), content fields are used.
    """
    keys: tuple[str, ...] = (
        "strategy_fingerprint",
        "timeframe",
        "data_fingerprint",
        "universe_plan_fingerprint",
        "template_fingerprint",
        "config_fingerprint",
        "experiment_family_fingerprint",
        "hypothesis_family_fingerprint",
        "metric_names",
        "independence_class",
        "independence_source_experiment_ids",
        "regime_label",
        "regime_required",
    )
    parts: list[str] = []
    for k in keys:
        v = combo.get(k, "")
        if isinstance(v, (tuple, list)):
            parts.append("|".join(str(x) for x in v))
        else:
            parts.append(str(v))
    return "::".join(parts)


def compile_campaign(
    definition: ResearchCampaignDefinition,
    *,
    compile_only: bool = False,
) -> CompiledCampaign | tuple[CompiledCampaign, CampaignRegistrationSet]:
    """Compile a research campaign definition into a compiled campaign matrix.

    Parameters
    ----------
    definition : ResearchCampaignDefinition
        The validated campaign definition.
    compile_only : bool, keyword-only
        If True, return only the ``CompiledCampaign`` (no registration set).
        If False, return ``(CompiledCampaign, CampaignRegistrationSet)``.

    Returns
    -------
    CompiledCampaign or tuple[CompiledCampaign, CampaignRegistrationSet]
    """
    # 1. Validate the definition.
    validate_definition(definition)

    params: CampaignParameterSet = definition.parameters

    # 2. Build the Cartesian product of all parameter dimensions.
    raw_combinations: list[dict[str, Any]] = []
    for (
        strategy,
        timeframe,
        data,
        universe,
        template,
        config,
        exp_family,
        hyp_family,
        metric_scope,
        independence,
        regime,
    ) in itertools.product(
        params.strategies,
        params.timeframes,
        params.historical_data,
        params.universe_plans,
        params.walk_forward_templates,
        params.confidence_configs,
        params.experiment_families,
        params.hypothesis_families,
        params.metric_families,
        params.independence_metadata,
        params.regime_policies,
    ):
        combo = _build_canonical_combination(
            strategy, timeframe, data, universe, template, config,
            exp_family, hyp_family, metric_scope, independence, regime,
        )
        raw_combinations.append(combo)

    # 3. Apply filter rules.
    check_contradictory_rules(params.include_rules + params.exclude_rules)
    try:
        filtered: list[dict[str, Any]] = filter_combinations(
            raw_combinations,
            params.include_rules,
            params.exclude_rules,
        )
    except ResearchCampaignFilterError:
        raise

    # 4. Deduplicate by canonical combination key.
    seen: set[str] = set()
    unique_combinations: list[dict[str, Any]] = []
    for combo in filtered:
        key = _combination_fingerprint_key(combo)
        if key in seen:
            raise ResearchCampaignCompilationError(
                f"Duplicate logical experiment detected: {combo}",
                reason_code=DUPLICATE_LOGICAL_EXPERIMENT,
            )
        seen.add(key)
        unique_combinations.append(combo)

    # 5. Enforce max_experiment_count.
    if len(unique_combinations) > definition.max_experiment_count:
        raise ResearchCampaignCompilationError(
            f"Product size {len(unique_combinations)} exceeds "
            f"max_experiment_count {definition.max_experiment_count}",
            reason_code=MAX_EXPERIMENT_COUNT_EXCEEDED,
        )

    # 6. Reject zero-result campaigns.
    excluded_count = len(raw_combinations) - len(unique_combinations)
    if len(unique_combinations) == 0:
        raise ResearchCampaignCompilationError(
            "Campaign produced zero experiments after filtering",
            reason_code=ZERO_EXPERIMENT_CAMPAIGN,
        )

    # 7. Build compiled experiments.
    compiled_experiments: list[CompiledExperiment] = []
    for combo in unique_combinations:
        # Look up the original parameter objects for this combination.
        # We need them to build the WalkForwardExperimentPlan and references.
        strategy_name: str = combo["strategy_name"]
        timeframe_s: str = combo["timeframe"]
        data_id: str = combo["data_id"]
        universe_plan_id: str = combo["universe_plan_id"]
        template_id: str = combo["template_id"]
        config_id: str = combo["config_id"]
        experiment_family_id: str = combo["experiment_family_id"]
        hypothesis_family_id: str = combo["hypothesis_family_id"]
        metric_names: tuple[str, ...] = combo["metric_names"]
        independence_class: str = combo["independence_class"]
        regime_label: str = combo["regime_label"]

        # Recover original objects from parameter sets (use fingerprints to
        # distinguish references that share the same human-readable ID).
        strategy_ref = next(s for s in params.strategies if s.fingerprint == combo["strategy_fingerprint"])
        data_ref = next(d for d in params.historical_data if d.fingerprint == combo["data_fingerprint"])
        universe_ref = next(u for u in params.universe_plans if u.fingerprint == combo["universe_plan_fingerprint"])
        template_ref = next(t for t in params.walk_forward_templates if t.fingerprint == combo["template_fingerprint"])
        config_ref = next(c for c in params.confidence_configs if c.fingerprint == combo["config_fingerprint"])
        exp_family_ref = next(f for f in params.experiment_families if f.fingerprint == combo["experiment_family_fingerprint"])
        hyp_family_ref = next(f for f in params.hypothesis_families if f.fingerprint == combo["hypothesis_family_fingerprint"])
        metric_scope_ref = next(
            m for m in params.metric_families if m.metric_names == metric_names
        )
        independence_ref = next(
            ind for ind in params.independence_metadata
            if (
                ind.independence_class.value
                if hasattr(ind.independence_class, "value")
                else str(ind.independence_class)
            ) == independence_class
            and ind.source_experiment_ids == combo["independence_source_experiment_ids"]
        )
        regime_ref = next(
            r for r in params.regime_policies
            if (
                r.regime_label.value
                if hasattr(r.regime_label, "value")
                else str(r.regime_label)
            ) == regime_label
            and r.required == combo["regime_required"]
        )

        # 7a. Build WalkForwardExperimentPlan.
        mode_str = template_ref.mode  # string like "ROLLING" or "EXPANDING"
        wf_mode = WalkForwardMode(mode_str)

        common_config = WalkForwardCommonConfig(
            strategy_name=strategy_ref.strategy_name,
            strategy_path=strategy_ref.strategy_path,
            data_path=data_ref.data_path,
            timeframe=timeframe_s,
            balance=params.common_config.balance,
            stake=params.common_config.stake,
            max_open_trades=params.common_config.max_open_trades,
            fee=params.common_config.fee,
            executable_path=params.common_config.executable_path,
            protections=params.common_config.protections,
            timeout_seconds=params.common_config.timeout_seconds,
            env_allowlist=params.common_config.env_allowlist,
            extra_env=params.common_config.extra_env,
            metadata=params.common_config.metadata,
        )

        safety_flags = WalkForwardSafetyFlags()

        wf_plan = WalkForwardExperimentPlan(
            mode=wf_mode,
            windows=template_ref.windows,
            common=common_config,
            contiguous=template_ref.contiguous,
            safety_flags=safety_flags,
            fingerprint="",
            reason_codes=(),
            metadata={},
        )

        # Compute plan fingerprint.
        from hunter.research_walk_forward.fingerprint import plan_fingerprint

        plan_fp = plan_fingerprint(wf_plan)
        wf_plan = WalkForwardExperimentPlan(
            mode=wf_plan.mode,
            windows=wf_plan.windows,
            common=wf_plan.common,
            contiguous=wf_plan.contiguous,
            safety_flags=wf_plan.safety_flags,
            fingerprint=plan_fp,
            reason_codes=wf_plan.reason_codes,
            metadata=wf_plan.metadata,
        )

        # 7b. Compute experiment_id.
        experiment_id = experiment_id_from_components(
            campaign_id=definition.campaign_id,
            strategy_name=strategy_ref.strategy_name,
            timeframe=timeframe_s,
            data_id=data_ref.data_id,
            universe_plan_id=universe_ref.universe_plan_id,
            template_id=template_ref.template_id,
            config_id=config_ref.config_id,
            experiment_family_id=exp_family_ref.family_id,
            hypothesis_family_id=hyp_family_ref.family_id,
            metric_names=metric_scope_ref.metric_names,
            independence_class=(
                independence_ref.independence_class.value
                if hasattr(independence_ref.independence_class, "value")
                else str(independence_ref.independence_class)
            ),
            regime_label=(
                regime_ref.regime_label.value
                if hasattr(regime_ref.regime_label, "value")
                else str(regime_ref.regime_label)
            ),
            strategy_fingerprint=strategy_ref.fingerprint,
            historical_data_fingerprint=data_ref.fingerprint,
            universe_plan_fingerprint=universe_ref.fingerprint,
            walk_forward_template_fingerprint=template_ref.fingerprint,
            confidence_config_fingerprint=config_ref.fingerprint,
            experiment_family_fingerprint=exp_family_ref.fingerprint,
            hypothesis_family_fingerprint=hyp_family_ref.fingerprint,
        )

        # 7c. Build the CompiledExperiment (registration_fingerprint="" initially).
        compiled_exp = CompiledExperiment(
            experiment_id=experiment_id,
            campaign_id=definition.campaign_id,
            strategy=strategy_ref,
            timeframe=timeframe_s,
            historical_data=data_ref,
            universe_plan=universe_ref,
            walk_forward_template=template_ref,
            confidence_config=config_ref,
            experiment_family=exp_family_ref,
            hypothesis_family=hyp_family_ref,
            metric_family=metric_scope_ref,
            independence=independence_ref,
            regime_policy=regime_ref,
            walk_forward_plan=wf_plan,
            fingerprint="",
            registration_fingerprint="",
        )

        # Compute experiment fingerprint.
        exp_fp = compiled_experiment_fingerprint(compiled_exp)
        compiled_exp = CompiledExperiment(
            experiment_id=compiled_exp.experiment_id,
            campaign_id=compiled_exp.campaign_id,
            strategy=compiled_exp.strategy,
            timeframe=compiled_exp.timeframe,
            historical_data=compiled_exp.historical_data,
            universe_plan=compiled_exp.universe_plan,
            walk_forward_template=compiled_exp.walk_forward_template,
            confidence_config=compiled_exp.confidence_config,
            experiment_family=compiled_exp.experiment_family,
            hypothesis_family=compiled_exp.hypothesis_family,
            metric_family=compiled_exp.metric_family,
            independence=compiled_exp.independence,
            regime_policy=compiled_exp.regime_policy,
            walk_forward_plan=compiled_exp.walk_forward_plan,
            fingerprint=exp_fp,
            registration_fingerprint=compiled_exp.registration_fingerprint,
        )
        compiled_experiments.append(compiled_exp)

    # 8. Sort experiments.
    sorted_experiments = canonical_sort_experiments(compiled_experiments)

    # 9. Build CompiledCampaign.
    compile_timestamp = datetime.now(timezone.utc)
    compiled_campaign = CompiledCampaign(
        campaign=definition,
        experiments=sorted_experiments,
        experiment_count=len(sorted_experiments),
        excluded_count=excluded_count,
        fingerprint="",
        compile_timestamp=compile_timestamp,
        reason_codes=definition.reason_codes,
    )

    # Compute campaign fingerprint.
    cc_fp = compiled_campaign_fingerprint(compiled_campaign)
    object.__setattr__(compiled_campaign, "fingerprint", cc_fp)

    # 10. Return depending on compile_only mode.
    if compile_only:
        return compiled_campaign

    registration_set = create_campaign_registration_set(compiled_campaign)
    return compiled_campaign, registration_set
