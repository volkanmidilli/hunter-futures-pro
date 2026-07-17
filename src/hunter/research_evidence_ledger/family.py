"""Family indexing for the research evidence ledger (MVP-68 / SPEC-069)."""

from __future__ import annotations

from hunter.research_evidence_ledger.fingerprint import (
    experiment_family_fingerprint,
    hypothesis_family_fingerprint,
    metric_family_fingerprint,
)
from hunter.research_evidence_ledger.models import (
    EvidenceLedgerEntry,
    ExperimentFamily,
    HypothesisFamily,
    MetricFamily,
)


def build_hypothesis_families(
    entries: tuple[EvidenceLedgerEntry, ...],
) -> tuple[HypothesisFamily, ...]:
    """Build deterministic hypothesis families from ledger entries.

    Groups entries by exact hypothesis text.
    """
    hypothesis_map: dict[str, dict[str, set[str]]] = {}
    for entry in entries:
        reg = entry.registration
        h = reg.hypothesis
        if h not in hypothesis_map:
            hypothesis_map[h] = {"experiment_ids": set(), "metric_names": set()}
        hypothesis_map[h]["experiment_ids"].add(reg.experiment_id)
        hypothesis_map[h]["metric_names"].update(reg.metric_family)

    families: list[HypothesisFamily] = []
    for hypothesis in sorted(hypothesis_map):
        data = hypothesis_map[hypothesis]
        # Deterministic ID from hypothesis text
        import hashlib
        h_bytes = hypothesis.encode("utf-8")
        family_id = f"hyp_fam_{hashlib.sha256(h_bytes).hexdigest()[:16]}"

        sorted_ids = tuple(sorted(data["experiment_ids"]))
        sorted_metrics = tuple(sorted(data["metric_names"]))

        family = HypothesisFamily(
            hypothesis_family_id=family_id,
            hypothesis=hypothesis,
            experiment_ids=sorted_ids,
            metric_names=sorted_metrics,
        )
        fp = hypothesis_family_fingerprint(family)
        object.__setattr__(family, "fingerprint", fp)
        families.append(family)

    return tuple(families)


def build_experiment_families(
    entries: tuple[EvidenceLedgerEntry, ...],
) -> tuple[ExperimentFamily, ...]:
    """Build deterministic experiment families from ledger entries.

    Groups entries by strategy_name, universe_plan, timeframe,
    and walk_forward_plan_fingerprint.
    """
    family_map: dict[str, dict[str, set[str]]] = {}
    for entry in entries:
        reg = entry.registration
        # Composite key for experiment family
        key_parts = (
            reg.strategy_name,
            reg.universe_plan,
            reg.timeframe,
            reg.walk_forward_plan_fingerprint,
        )
        key = "|".join(key_parts)
        if key not in family_map:
            family_map[key] = {
                "experiment_ids": set(),
                "metric_names": set(),
                "strategy_name": reg.strategy_name,
                "universe_plan": reg.universe_plan,
                "timeframe": reg.timeframe,
                "wf_fp": reg.walk_forward_plan_fingerprint,
            }
        family_map[key]["experiment_ids"].add(reg.experiment_id)
        family_map[key]["metric_names"].update(reg.metric_family)

    import hashlib

    families: list[ExperimentFamily] = []
    for key in sorted(family_map):
        data = family_map[key]
        family_id = f"exp_fam_{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}"

        sorted_ids = tuple(sorted(data["experiment_ids"]))
        sorted_metrics = tuple(sorted(data["metric_names"]))

        family = ExperimentFamily(
            experiment_family_id=family_id,
            strategy_name=data["strategy_name"],
            universe_plan=data["universe_plan"],
            timeframe=data["timeframe"],
            walk_forward_plan_fingerprint=data["wf_fp"],
            experiment_ids=sorted_ids,
            metric_names=sorted_metrics,
        )
        fp = experiment_family_fingerprint(family)
        object.__setattr__(family, "fingerprint", fp)
        families.append(family)

    return tuple(families)


def build_metric_families(
    entries: tuple[EvidenceLedgerEntry, ...],
) -> tuple[MetricFamily, ...]:
    """Build deterministic metric families from ledger entries.

    Groups metric names that co-occur in registrations.
    """
    all_metrics: set[str] = set()
    for entry in entries:
        all_metrics.update(entry.registration.metric_family)

    sorted_metrics = tuple(sorted(all_metrics))
    if not sorted_metrics:
        return ()

    family = MetricFamily(metric_names=sorted_metrics)
    fp = metric_family_fingerprint(family)
    object.__setattr__(family, "fingerprint", fp)
    return (family,)
