"""Snapshot chaining for the research evidence ledger (MVP-68 / SPEC-069)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from hunter.research_evidence_ledger.fingerprint import (
    adjusted_evidence_fingerprint,
    entry_fingerprint,
    experiment_family_fingerprint,
    hypothesis_family_fingerprint,
    metric_family_fingerprint,
    replication_fingerprint,
    snapshot_fingerprint,
)
from hunter.research_evidence_ledger.models import (
    EVIDENCE_LEDGER_VERSION,
    SPEC_VERSION,
    SNAPSHOT_CHAIN_BROKEN,
    AdjustedEvidence,
    EvidenceLedgerEntry,
    EvidenceLedgerSnapshotError,
    ExperimentFamily,
    HypothesisFamily,
    LedgerSnapshot,
    MetricFamily,
    ReplicationResult,
)


def build_snapshot(
    entries: tuple[EvidenceLedgerEntry, ...],
    hypothesis_families: tuple[HypothesisFamily, ...],
    experiment_families: tuple[ExperimentFamily, ...],
    metric_families: tuple[MetricFamily, ...],
    adjustments: tuple[AdjustedEvidence, ...],
    replications: tuple[ReplicationResult, ...],
    previous_snapshot_fingerprint: str = "",
    snapshot_id: str | None = None,
) -> LedgerSnapshot:
    """Build a new immutable ledger snapshot.

    Args:
        entries: Current ledger entries.
        hypothesis_families: Current hypothesis families.
        experiment_families: Current experiment families.
        metric_families: Current metric families.
        adjustments: Current adjustments.
        replications: Current replications.
        previous_snapshot_fingerprint: Fingerprint of the previous snapshot
            (empty string for the first snapshot).
        snapshot_id: Optional explicit snapshot ID. Auto-generated if not provided.

    Returns:
        A new LedgerSnapshot with deterministic fingerprint.

    Raises:
        EvidenceLedgerSnapshotError: If the previous snapshot fingerprint
            is non-empty and indicates a broken chain.
    """
    # Collect deterministic fingerprints of all components
    entry_fps = tuple(
        entry_fingerprint(e) for e in entries
    )
    family_fps = tuple(
        sorted(
            [hypothesis_family_fingerprint(hf) for hf in hypothesis_families]
            + [experiment_family_fingerprint(ef) for ef in experiment_families]
            + [metric_family_fingerprint(mf) for mf in metric_families]
        )
    )
    adjustment_fps = tuple(
        adjusted_evidence_fingerprint(a) for a in adjustments
    )
    replication_fps = tuple(
        replication_fingerprint(r) for r in replications
    )

    # Generate snapshot ID from content
    if snapshot_id is None:
        content_hash = hashlib.sha256(
            "|".join(list(entry_fps) + list(family_fps) + list(adjustment_fps) + list(replication_fps)).encode("utf-8")
        ).hexdigest()[:16]
        snapshot_id = f"snap_{content_hash}"

    snapshot = LedgerSnapshot(
        version=EVIDENCE_LEDGER_VERSION,
        spec_version=SPEC_VERSION,
        snapshot_id=snapshot_id,
        previous_snapshot_fingerprint=previous_snapshot_fingerprint,
        entry_fingerprints=entry_fps,
        family_fingerprints=family_fps,
        adjustment_fingerprints=adjustment_fps,
        replication_fingerprints=replication_fps,
    )

    fp = snapshot_fingerprint(snapshot)
    object.__setattr__(snapshot, "fingerprint", fp)

    return snapshot


def verify_snapshot_chain(
    snapshots: tuple[LedgerSnapshot, ...],
) -> None:
    """Verify integrity of a snapshot chain.

    Each snapshot must have its previous_snapshot_fingerprint match
    the fingerprint of the preceding snapshot.

    Raises EvidenceLedgerSnapshotError if the chain is broken.
    """
    for i, snap in enumerate(snapshots):
        if i == 0:
            # First snapshot may or may not have a previous fingerprint
            continue

        expected_previous = snapshots[i - 1].fingerprint
        if snap.previous_snapshot_fingerprint != expected_previous:
            raise EvidenceLedgerSnapshotError(
                f"Snapshot chain broken at index {i}: "
                f"snapshot {snap.snapshot_id} has "
                f"previous_snapshot_fingerprint {snap.previous_snapshot_fingerprint[:16]}..., "
                f"expected {expected_previous[:16]}...",
                reason_code=SNAPSHOT_CHAIN_BROKEN,
            )
