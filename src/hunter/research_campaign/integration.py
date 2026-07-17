"""Integration wrappers for MVP-66 (walk-forward), MVP-67 (confidence), and MVP-68 (evidence ledger).

No subprocess, threading, network, eval, exec, or dynamic code.
"""

from __future__ import annotations

from hunter.research_campaign.errors import ResearchCampaignRunnerError
from hunter.research_campaign.models import MISSING_WALK_FORWARD_EVIDENCE
from hunter.research_evidence_ledger.engine import EvidenceLedgerEngine
from hunter.research_evidence_ledger.models import (
    EvidenceLedgerEntry,
    ExperimentRegistration,
    LedgerSnapshot,
)
from hunter.research_statistical_confidence.engine import (
    run_statistical_confidence,
)
from hunter.research_statistical_confidence.models import (
    ExperimentConfidenceReport,
)
from hunter.research_walk_forward.engine import (
    run_walk_forward_experiment,
)
from hunter.research_walk_forward.models import (
    ExperimentExecutionPolicy,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WindowStatus,
)


def run_walk_forward_for_experiment(
    compiled_experiment: object,
    execution_policy: ExperimentExecutionPolicy = ExperimentExecutionPolicy.COLLECT_ALL,
) -> WalkForwardExperimentReport:
    """Run MVP-66 walk-forward experiment for a compiled experiment.

    Parameters
    ----------
    compiled_experiment : CompiledExperiment
        The compiled experiment providing the walk-forward plan and universe.
    execution_policy : ExperimentExecutionPolicy
        How to handle window failures (default: COLLECT_ALL).

    Returns
    -------
    WalkForwardExperimentReport
        The walk-forward experiment report from MVP-66.
    """
    plan: WalkForwardExperimentPlan = compiled_experiment.walk_forward_plan  # type: ignore[attr-defined]
    universe_plan = compiled_experiment.universe_plan  # type: ignore[attr-defined]

    return run_walk_forward_experiment(
        plan=plan,
        candidate_pairlist=universe_plan.candidate_pairlist,
        baseline_pairlist=universe_plan.baseline_pairlist,
        candidate_universe_fingerprint=universe_plan.candidate_universe_fingerprint,
        baseline_universe_fingerprint=universe_plan.baseline_universe_fingerprint,
        execution_policy=execution_policy,
    )


def run_confidence_for_experiment(
    walk_forward_report: WalkForwardExperimentReport,
    compiled_experiment: object,
) -> ExperimentConfidenceReport:
    """Run MVP-67 statistical confidence for a completed walk-forward experiment.

    Parameters
    ----------
    walk_forward_report : WalkForwardExperimentReport
        The completed walk-forward report from MVP-66.
    compiled_experiment : CompiledExperiment
        The compiled experiment providing the confidence configuration.

    Returns
    -------
    ExperimentConfidenceReport
        The statistical confidence report from MVP-67.

    Raises
    ------
    ResearchCampaignRunnerError
        If the walk-forward report has incomplete windows.
    """
    # Ensure all windows are COMPLETED.
    if not all(
        w.status == WindowStatus.COMPLETED
        for w in walk_forward_report.window_results
    ):
        raise ResearchCampaignRunnerError(
            "Cannot run statistical confidence: walk-forward has incomplete windows",
            reason_code=MISSING_WALK_FORWARD_EVIDENCE,
        )

    confidence_config = compiled_experiment.confidence_config.config  # type: ignore[attr-defined]
    return run_statistical_confidence(
        report=walk_forward_report,
        config=confidence_config,
    )


def ingest_experiment_evidence(
    engine: EvidenceLedgerEngine,
    compiled_experiment: object,
    registration: ExperimentRegistration,
    walk_forward_report: WalkForwardExperimentReport | None,
    confidence_report: ExperimentConfidenceReport | None,
) -> tuple[EvidenceLedgerEntry, LedgerSnapshot]:
    """Ingest evidence from MVP-66 and MVP-67 into the MVP-68 evidence ledger.

    Parameters
    ----------
    engine : EvidenceLedgerEngine
        The evidence ledger engine instance.
    compiled_experiment : CompiledExperiment
        The compiled experiment with family IDs, metric names, etc.
    registration : ExperimentRegistration
        The pre-registration record for this experiment.
    walk_forward_report : WalkForwardExperimentReport | None
        The walk-forward report (if available).
    confidence_report : ExperimentConfidenceReport | None
        The confidence report (if available).

    Returns
    -------
    tuple[EvidenceLedgerEntry, LedgerSnapshot]
        The resulting ledger entry and snapshot.
    """
    # 1. Register the experiment in the ledger.
    engine.register_experiment(registration)

    # 2. Ingest evidence.
    engine.ingest_evidence(
        experiment_id=compiled_experiment.experiment_id,  # type: ignore[attr-defined]
        walk_forward_report=walk_forward_report,
        confidence_report=confidence_report,
    )

    # 3. Build the ledger entry.
    entry: EvidenceLedgerEntry = engine.build_entry(
        experiment_id=compiled_experiment.experiment_id,  # type: ignore[attr-defined]
    )

    # 4. Take a snapshot.
    snapshot: LedgerSnapshot = engine.take_snapshot()

    return entry, snapshot
