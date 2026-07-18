"""Core engine for the research evidence ledger (MVP-68 / SPEC-069)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from hunter.research_evidence_ledger.adjustment import adjust
from hunter.research_evidence_ledger.drift import DriftDetector
from hunter.research_evidence_ledger.duplicate import DuplicateDetector
from hunter.research_evidence_ledger.family import (
    build_experiment_families,
    build_hypothesis_families,
    build_metric_families,
)
from hunter.research_evidence_ledger.fingerprint import (
    entry_fingerprint,
    evidence_fingerprint,
    manifest_fingerprint,
    registration_fingerprint,
    report_fingerprint,
    snapshot_fingerprint,
)
from hunter.research_evidence_ledger.models import (
    DUPLICATE_EVIDENCE,
    EVIDENCE_LEDGER_VERSION,
    SPEC_VERSION,
    AdjustedEvidence,
    AdjustmentConfig,
    EvidenceLedgerEntry,
    EvidenceLedgerManifest,
    EvidenceLedgerReport,
    EvidenceLedgerSafetyError,
    EvidenceLedgerSafetyFlags,
    EvidenceLedgerSnapshotError,
    ExperimentEvidence,
    ExperimentRegistration,
    ExperimentStatus,
    LedgerSnapshot,
    MISSING_REGISTRATION,
    POST_REGISTRATION_MUTATION,
    RESULT_BEFORE_REGISTRATION,
    UNAVAILABLE,
)
from hunter.research_evidence_ledger.replication import analyze_all_replications
from hunter.research_evidence_ledger.snapshot import build_snapshot
from hunter.research_evidence_ledger.validator import (
    validate_registration,
    validate_safety_flags,
)
from hunter.research_statistical_confidence.models import (
    ExperimentConfidenceReport,
    MetricConfidenceResult,
)
from hunter.research_walk_forward.models import (
    WalkForwardExperimentReport,
)


class EvidenceLedgerEngine:
    """Core engine for building research evidence ledger reports.

    Consumes immutable MVP-66 WalkForwardExperimentReport and
    MVP-67 ExperimentConfidenceReport.
    """

    def __init__(self, safety_flags: EvidenceLedgerSafetyFlags | None = None) -> None:
        self._safety_flags = safety_flags or EvidenceLedgerSafetyFlags()
        validate_safety_flags(self._safety_flags)

        self._duplicate_detector = DuplicateDetector()
        self._drift_detector = DriftDetector()

        self._registrations: dict[str, ExperimentRegistration] = {}
        self._evidence: dict[str, ExperimentEvidence] = {}
        self._entries: dict[str, EvidenceLedgerEntry] = {}
        self._adjustments: list[AdjustedEvidence] = []
        self._replications: tuple[Any, ...] = ()
        self._snapshots: list[LedgerSnapshot] = []
        self._hypothesis_families: tuple[Any, ...] = ()
        self._experiment_families: tuple[Any, ...] = ()
        self._metric_families: tuple[Any, ...] = ()

    @property
    def safety_flags(self) -> EvidenceLedgerSafetyFlags:
        return self._safety_flags

    def register_experiment(
        self,
        registration: ExperimentRegistration,
    ) -> ExperimentRegistration:
        """Register an experiment.

        Validates registration, checks for duplicates, and detects drift.
        Returns the registration with its fingerprint.
        """
        validate_registration(registration)

        # Compute fingerprint if not already set
        if not registration.fingerprint:
            fp = registration_fingerprint(registration)
            reg = ExperimentRegistration(**{**registration.__dict__, "fingerprint": fp})
        else:
            reg = registration

        # Check duplicates
        self._duplicate_detector.check_all(reg)

        # Check drift
        self._drift_detector.check_drift(reg)

        # Store
        self._registrations[reg.experiment_id] = reg
        self._duplicate_detector.register_all(reg)
        self._drift_detector.set_baseline(reg)

        return reg

    def ingest_evidence(
        self,
        experiment_id: str,
        walk_forward_report: WalkForwardExperimentReport | None = None,
        confidence_report: ExperimentConfidenceReport | None = None,
    ) -> ExperimentEvidence:
        """Ingest evidence for a registered experiment.

        Raises errors for:
        - Missing registration
        - Result before registration
        - Post-registration mutation (fingerprint mismatch)
        - Duplicate evidence fingerprints
        """
        # Check registration exists
        if experiment_id not in self._registrations:
            raise EvidenceLedgerSnapshotError(
                f"Evidence for unregistered experiment: {experiment_id}",
                reason_code=MISSING_REGISTRATION,
            )

        reg = self._registrations[experiment_id]

        # Detect evidence generated before the experiment was registered.
        evidence_timestamps: list[datetime] = []
        if walk_forward_report is not None:
            evidence_timestamps.append(walk_forward_report.manifest.generated_at)
        if confidence_report is not None:
            evidence_timestamps.append(confidence_report.manifest.generated_at)
        if evidence_timestamps and min(evidence_timestamps) < reg.registered_at:
            raise EvidenceLedgerSnapshotError(
                f"Result for {experiment_id} generated before registration",
                reason_code=RESULT_BEFORE_REGISTRATION,
            )

        # Compute evidence fingerprints
        ev_wf_fp = walk_forward_report.fingerprint if walk_forward_report is not None else ""
        ev_cf_fp = confidence_report.fingerprint if confidence_report is not None else ""

        # Duplicate detection on individual report fingerprints.
        self._duplicate_detector.check_duplicate_walk_forward_fingerprint(
            experiment_id, ev_wf_fp
        )
        self._duplicate_detector.check_duplicate_confidence_fingerprint(
            experiment_id, ev_cf_fp
        )

        # Build evidence object bound to the current registration.
        ev = ExperimentEvidence(
            experiment_id=experiment_id,
            walk_forward_report=walk_forward_report,
            confidence_report=confidence_report,
            walk_forward_fingerprint=ev_wf_fp,
            confidence_fingerprint=ev_cf_fp,
            registration_fingerprint=reg.fingerprint,
        )
        ev_fp = evidence_fingerprint(ev)
        ev = ExperimentEvidence(**{**ev.__dict__, "evidence_fingerprint": ev_fp})

        # Full evidence duplicate detection before accepting the evidence.
        self._check_duplicate_evidence_for_experiment(experiment_id, ev)

        # Record fingerprints so that subsequent ingestion attempts are
        # detected as duplicates even before an entry is built.
        self._duplicate_detector.register_evidence_object(ev, experiment_id)

        self._evidence[experiment_id] = ev
        return ev

    def _check_duplicate_evidence_for_experiment(
        self, experiment_id: str, ev: ExperimentEvidence
    ) -> None:
        """Raise if this evidence is a duplicate of another experiment's evidence."""
        if not ev.evidence_fingerprint:
            return
        if ev.evidence_fingerprint in self._duplicate_detector._seen_evidence_fingerprints:
            existing = self._duplicate_detector._seen_evidence_fingerprints[ev.evidence_fingerprint]
            if existing.registration.experiment_id != experiment_id:
                raise EvidenceLedgerDuplicateError(
                    f"Duplicate evidence fingerprint for {experiment_id}",
                    reason_code=DUPLICATE_EVIDENCE,
                )

    def build_entry(
        self,
        experiment_id: str,
    ) -> EvidenceLedgerEntry:
        """Build a ledger entry combining registration and evidence."""
        if experiment_id not in self._registrations:
            raise EvidenceLedgerSnapshotError(
                f"Cannot build entry for unregistered experiment: {experiment_id}",
                reason_code=MISSING_REGISTRATION,
            )

        reg = self._registrations[experiment_id]
        ev = self._evidence.get(experiment_id)

        # Detect post-registration mutation by comparing the registration
        # fingerprint captured at ingestion time with the current registration.
        if ev is not None and ev.registration_fingerprint and ev.registration_fingerprint != reg.fingerprint:
            raise EvidenceLedgerSnapshotError(
                f"Registration for {experiment_id} mutated after evidence ingestion",
                reason_code=POST_REGISTRATION_MUTATION,
            )

        # Determine the effective status
        status = reg.status

        entry = EvidenceLedgerEntry(
            registration=reg,
            evidence=ev,
            status=status,
        )
        fp = entry_fingerprint(entry)
        entry = EvidenceLedgerEntry(**{**entry.__dict__, "fingerprint": fp})

        # Register evidence fingerprint with duplicate detector
        self._duplicate_detector.register_evidence(entry)

        self._entries[experiment_id] = entry
        return entry

    def build_all_entries(self) -> tuple[EvidenceLedgerEntry, ...]:
        """Build entries for all registrations with evidence."""
        for exp_id in self._registrations:
            if exp_id not in self._entries:
                self.build_entry(exp_id)
        return tuple(self._entries.values())

    def build_families(self) -> None:
        """Build hypothesis, experiment, and metric families from entries."""
        entries = tuple(self._entries.values())
        self._hypothesis_families = build_hypothesis_families(entries)
        self._experiment_families = build_experiment_families(entries)
        self._metric_families = build_metric_families(entries)

    def apply_adjustment(
        self,
        config: AdjustmentConfig,
        raw_values: list[tuple[str, str, Decimal]],
    ) -> list[AdjustedEvidence]:
        """Apply a multiple-testing adjustment to raw evidence values."""
        results = adjust(raw_values, config)
        self._adjustments.extend(results)
        return results

    def analyze_replications(
        self,
        min_independent: int = 1,
    ) -> tuple[Any, ...]:
        """Analyze replication across families."""
        entries = tuple(self._entries.values())

        # Build family ID maps
        hypothesis_family_ids: dict[str, str] = {}
        for hf in self._hypothesis_families:
            hypothesis_family_ids[hf.hypothesis] = hf.hypothesis_family_id

        experiment_family_ids: dict[str, str] = {}
        for ef in self._experiment_families:
            key = "|".join([ef.strategy_name, ef.universe_plan, ef.timeframe, ef.walk_forward_plan_fingerprint])
            experiment_family_ids[key] = ef.experiment_family_id

        metric_names: tuple[str, ...] = ()
        for mf in self._metric_families:
            metric_names = mf.metric_names

        results = analyze_all_replications(
            entries=entries,
            hypothesis_family_ids=hypothesis_family_ids,
            experiment_family_ids=experiment_family_ids,
            metric_names=metric_names,
            min_independent=min_independent,
        )
        self._replications = results
        return results

    def take_snapshot(self) -> LedgerSnapshot:
        """Take a snapshot of the current ledger state."""
        previous_fp = ""
        if self._snapshots:
            previous_fp = self._snapshots[-1].fingerprint

        snapshot = build_snapshot(
            entries=tuple(self._entries.values()),
            hypothesis_families=self._hypothesis_families,
            experiment_families=self._experiment_families,
            metric_families=self._metric_families,
            adjustments=tuple(self._adjustments),
            replications=self._replications,
            previous_snapshot_fingerprint=previous_fp,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def build_report(self) -> EvidenceLedgerReport:
        """Build the final evidence ledger report."""
        entries = tuple(self._entries.values())
        hypothesis_families = self._hypothesis_families
        experiment_families = self._experiment_families
        metric_families = self._metric_families
        adjustments = tuple(self._adjustments)
        replications = self._replications

        # Take snapshot if none exist
        if not self._snapshots:
            self.take_snapshot()

        current_snapshot = self._snapshots[-1]

        # Build the manifest
        generated_at = datetime.now(timezone.utc)

        # Use a placeholder fingerprint for the preliminary report computation
        placeholder_fp = "_pending_"

        manifest = EvidenceLedgerManifest(
            version=EVIDENCE_LEDGER_VERSION,
            spec_version=SPEC_VERSION,
            evidence_ledger_version=EVIDENCE_LEDGER_VERSION,
            generated_at=generated_at,
            entry_count=len(entries),
            family_count=len(hypothesis_families) + len(experiment_families) + len(metric_families),
            adjustment_count=len(adjustments),
            replication_count=len(replications),
            snapshot_fingerprint=current_snapshot.fingerprint,
            overall_fingerprint=placeholder_fp,
            safety_flags=self._safety_flags,
        )

        # Create preliminary report to get fingerprint
        prelim_report = EvidenceLedgerReport(
            version=EVIDENCE_LEDGER_VERSION,
            spec_version=SPEC_VERSION,
            evidence_ledger_version=EVIDENCE_LEDGER_VERSION,
            registrations=tuple(self._registrations.values()),
            entries=entries,
            hypothesis_families=hypothesis_families,
            experiment_families=experiment_families,
            metric_families=metric_families,
            adjustments=adjustments,
            replications=replications,
            snapshot=current_snapshot,
            manifest=manifest,
            safety_flags=self._safety_flags,
            fingerprint=placeholder_fp,
        )

        overall_fp = report_fingerprint(prelim_report)

        # Rebuild manifest with correct overall fingerprint
        manifest = EvidenceLedgerManifest(
            version=EVIDENCE_LEDGER_VERSION,
            spec_version=SPEC_VERSION,
            evidence_ledger_version=EVIDENCE_LEDGER_VERSION,
            generated_at=generated_at,
            entry_count=len(entries),
            family_count=len(hypothesis_families) + len(experiment_families) + len(metric_families),
            adjustment_count=len(adjustments),
            replication_count=len(replications),
            snapshot_fingerprint=current_snapshot.fingerprint,
            overall_fingerprint=overall_fp,
            safety_flags=self._safety_flags,
        )
        manifest_fp = manifest_fingerprint(manifest)

        report = EvidenceLedgerReport(
            version=EVIDENCE_LEDGER_VERSION,
            spec_version=SPEC_VERSION,
            evidence_ledger_version=EVIDENCE_LEDGER_VERSION,
            registrations=tuple(self._registrations.values()),
            entries=entries,
            hypothesis_families=hypothesis_families,
            experiment_families=experiment_families,
            metric_families=metric_families,
            adjustments=adjustments,
            replications=replications,
            snapshot=current_snapshot,
            manifest=manifest,
            safety_flags=self._safety_flags,
            fingerprint=overall_fp,
        )

        return report
