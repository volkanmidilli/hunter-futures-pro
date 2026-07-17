"""Canonical ordering functions for compiled experiments and combination dicts (MVP-69 / SPEC-070)."""

from __future__ import annotations

from typing import Any

from hunter.research_campaign.models import CompiledExperiment

# Canonical key order for combination sort keys.
_CANONICAL_SORT_KEYS: tuple[str, ...] = (
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
)


def canonical_sort_key_for_combination(combination: dict[str, Any]) -> tuple:
    """Return a deterministic, sort-compatible key for a combination dict.

    Every value is coerced to a tuple of strings so that numeric, string,
    and tuple fields sort consistently and without type-mixing errors.

    Parameters
    ----------
    combination : dict[str, Any]
        A canonical combination dict.

    Returns
    -------
    tuple
        Sort key suitable for ``sorted(..., key=...)``.
    """
    parts: list[tuple[str, ...]] = []
    for key in _CANONICAL_SORT_KEYS:
        val = combination.get(key, "")
        if isinstance(val, (tuple, list)):
            parts.append(tuple(str(v) for v in val))
        else:
            parts.append((str(val),))
    return tuple(parts)


def canonical_sort_experiments(
    experiments: list[CompiledExperiment],
) -> tuple[CompiledExperiment, ...]:
    """Sort compiled experiments deterministically by
    ``(campaign_id, experiment_id, fingerprint)``.

    Parameters
    ----------
    experiments : list[CompiledExperiment]
        Unsorted experiment list.

    Returns
    -------
    tuple[CompiledExperiment, ...]
        Immutable, canonically sorted tuple of experiments.
    """
    return tuple(
        sorted(
            experiments,
            key=lambda e: (e.campaign_id, e.experiment_id, e.fingerprint),
        )
    )
