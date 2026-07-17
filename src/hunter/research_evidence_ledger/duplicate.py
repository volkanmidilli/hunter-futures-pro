"""Duplicate detection for the research evidence ledger (MVP-68 / SPEC-069)."""

from __future__ import annotations

from hunter.research_evidence_ledger.models import (
    DUPLICATE_EVIDENCE,
    DUPLICATE_FINGERPRINT,
    DUPLICATE_ID,
    EvidenceLedgerDuplicateError,
    EvidenceLedgerEntry,
    ExperimentRegistration,
    REPEATED_HYPOTHESIS,
)


class DuplicateDetector:
    """Detect duplicate registrations, evidence, and hypotheses."""

    def __init__(self) -> None:
        self._seen_ids: dict[str, ExperimentRegistration] = {}
        self._seen_fingerprints: dict[str, ExperimentRegistration] = {}
        self._seen_evidence_fingerprints: dict[str, EvidenceLedgerEntry] = {}
        self._seen_hypotheses: dict[str, list[str]] = {}

    def check_duplicate_id(
        self, registration: ExperimentRegistration
    ) -> None:
        """Raise if the experiment_id is already registered."""
        if registration.experiment_id in self._seen_ids:
            existing = self._seen_ids[registration.experiment_id]
            raise EvidenceLedgerDuplicateError(
                f"Duplicate experiment ID: {registration.experiment_id}",
                reason_code=DUPLICATE_ID,
            )

    def check_duplicate_fingerprint(
        self, registration: ExperimentRegistration
    ) -> None:
        """Raise if the registration fingerprint is already seen."""
        if registration.fingerprint in self._seen_fingerprints:
            existing = self._seen_fingerprints[registration.fingerprint]
            raise EvidenceLedgerDuplicateError(
                f"Duplicate registration fingerprint for {registration.experiment_id}",
                reason_code=DUPLICATE_FINGERPRINT,
            )

    def check_duplicate_evidence(
        self, entry: EvidenceLedgerEntry
    ) -> None:
        """Raise if the evidence fingerprint is already ingested."""
        if entry.evidence is None:
            return
        fp = entry.evidence.evidence_fingerprint
        if not fp:
            return
        if fp in self._seen_evidence_fingerprints:
            raise EvidenceLedgerDuplicateError(
                f"Duplicate evidence fingerprint for {entry.registration.experiment_id}",
                reason_code=DUPLICATE_EVIDENCE,
            )

    def check_repeated_hypothesis(self, hypothesis: str) -> None:
        """Warn/raise if the same hypothesis text appears multiple times."""
        if hypothesis in self._seen_hypotheses:
            raise EvidenceLedgerDuplicateError(
                f"Repeated hypothesis: {hypothesis[:80]}...",
                reason_code=REPEATED_HYPOTHESIS,
            )

    def register_id(self, registration: ExperimentRegistration) -> None:
        """Record an experiment ID as seen."""
        self._seen_ids[registration.experiment_id] = registration

    def register_fingerprint(self, registration: ExperimentRegistration) -> None:
        """Record a registration fingerprint as seen."""
        self._seen_fingerprints[registration.fingerprint] = registration

    def register_evidence(self, entry: EvidenceLedgerEntry) -> None:
        """Record evidence fingerprint."""
        if entry.evidence is not None:
            fp = entry.evidence.evidence_fingerprint
            if fp:
                self._seen_evidence_fingerprints[fp] = entry

    def register_hypothesis(self, hypothesis: str, experiment_id: str) -> None:
        """Record a hypothesis as seen."""
        if hypothesis not in self._seen_hypotheses:
            self._seen_hypotheses[hypothesis] = []
        self._seen_hypotheses[hypothesis].append(experiment_id)

    def check_all(
        self, registration: ExperimentRegistration
    ) -> None:
        """Run all duplicate checks against a registration."""
        self.check_duplicate_id(registration)
        self.check_duplicate_fingerprint(registration)
        self.check_repeated_hypothesis(registration.hypothesis)

    def register_all(
        self, registration: ExperimentRegistration
    ) -> None:
        """Register all identifiers for a registration."""
        self.register_id(registration)
        self.register_fingerprint(registration)
        self.register_hypothesis(registration.hypothesis, registration.experiment_id)
