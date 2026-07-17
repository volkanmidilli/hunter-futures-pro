"""Deterministic SHA-256 fingerprints for the research evidence ledger (MVP-68 / SPEC-069)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.research_evidence_ledger.models import (
    AdjustedEvidence,
    EvidenceLedgerEntry,
    EvidenceLedgerManifest,
    EvidenceLedgerReport,
    EvidenceLedgerSafetyFlags,
    EvidenceLedgerSnapshotError,
    ExperimentEvidence,
    ExperimentFamily,
    ExperimentRegistration,
    HypothesisFamily,
    LedgerSnapshot,
    MetricFamily,
    ReplicationResult,
)

_FINGERPRINT_EXCLUDED_KEYS: frozenset[str] = frozenset({
    "generated_at",
    "fingerprint",
    "notes",
    "metadata",
    "reason_codes",
})


def _serialize_value(value: Any, exclude_notes: bool = True) -> Any:
    """Serialize a value into a deterministic JSON-safe structure.

    Excludes notes, timestamps, and other non-deterministic fields.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone().isoformat()
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        cleaned = {}
        for k, v in value.items():
            if exclude_notes and k in _FINGERPRINT_EXCLUDED_KEYS:
                continue
            cleaned[str(k)] = _serialize_value(v)
        return {k: cleaned[k] for k in sorted(cleaned)}
    if is_dataclass(value) and not isinstance(value, type):
        return _serialize_dataclass(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _serialize_dataclass(obj: Any) -> dict[str, Any]:
    """Serialize a dataclass instance to a dict for fingerprinting.

    Excludes fingerprint, notes, metadata, and reason_codes fields.
    Also excludes fields that contain absolute paths, temp paths,
    timestamps, generated_at, durations, PID, hostname, object IDs,
    dict insertion order, display notes, and file mtime.
    """
    result = {}
    for name in sorted(obj.__dataclass_fields__):
        # Skip excluded fields
        if name in _FINGERPRINT_EXCLUDED_KEYS:
            continue
        # Skip metadata and reason_codes
        if name in ("metadata", "reason_codes", "notes"):
            continue
        value = getattr(obj, name)

        # Special handling for safety_flags - include the full serialization
        if isinstance(value, EvidenceLedgerSafetyFlags):
            result[name] = _serialize_safety_flags(value)
            continue

        result[name] = _serialize_value(value)
    return result


def _serialize_safety_flags(flags: EvidenceLedgerSafetyFlags) -> dict[str, bool]:
    """Serialize safety flags deterministically."""
    return {
        "research_only": flags.research_only,
        "execution_approval_granted": flags.execution_approval_granted,
        "production_approval_granted": flags.production_approval_granted,
        "live_trading_allowed": flags.live_trading_allowed,
        "automatic_execution_allowed": flags.automatic_execution_allowed,
        "human_approval_required": flags.human_approval_required,
        "no_direct_subprocess": flags.no_direct_subprocess,
        "no_network_connection": flags.no_network_connection,
        "no_database_connection": flags.no_database_connection,
        "no_exchange_connection": flags.no_exchange_connection,
        "no_remote_changes": flags.no_remote_changes,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
        "no_strategy_mutation": flags.no_strategy_mutation,
        "no_universe_mutation": flags.no_universe_mutation,
        "no_config_mutation": flags.no_config_mutation,
    }


def _hash_payload(payload: dict[str, Any]) -> str:
    """Return a deterministic SHA-256 hash of a JSON payload."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def registration_fingerprint(registration: ExperimentRegistration) -> str:
    """Return a deterministic fingerprint of an experiment registration.

    Excludes notes, timestamps, PID, hostname, paths, insertion order,
    fingerprint, metadata, and reason_codes.
    """
    payload = _serialize_dataclass(registration)
    return _hash_payload(payload)


def evidence_fingerprint(evidence: ExperimentEvidence) -> str:
    """Return a deterministic fingerprint of experiment evidence.

    Excludes metadata and reason_codes.
    """
    payload: dict[str, Any] = {
        "experiment_id": evidence.experiment_id,
    }
    if evidence.walk_forward_report is not None:
        payload["walk_forward_fingerprint"] = evidence.walk_forward_fingerprint
    if evidence.confidence_report is not None:
        payload["confidence_fingerprint"] = evidence.confidence_fingerprint
    return _hash_payload(payload)


def entry_fingerprint(entry: EvidenceLedgerEntry) -> str:
    """Return a deterministic fingerprint of a ledger entry.

    Excludes fingerprint, metadata, reason_codes, and notes.
    """
    payload: dict[str, Any] = {
        "registration_fingerprint": entry.registration.fingerprint,
        "status": entry.status.value,
    }
    if entry.evidence is not None:
        payload["evidence_fingerprint"] = entry.evidence.evidence_fingerprint
    return _hash_payload(payload)


def hypothesis_family_fingerprint(family: HypothesisFamily) -> str:
    """Return a deterministic fingerprint of a hypothesis family."""
    payload: dict[str, Any] = {
        "hypothesis_family_id": family.hypothesis_family_id,
        "hypothesis": family.hypothesis,
        "experiment_ids": sorted(family.experiment_ids),
        "metric_names": sorted(family.metric_names),
    }
    return _hash_payload(payload)


def experiment_family_fingerprint(family: ExperimentFamily) -> str:
    """Return a deterministic fingerprint of an experiment family."""
    payload: dict[str, Any] = {
        "experiment_family_id": family.experiment_family_id,
        "strategy_name": family.strategy_name,
        "universe_plan": family.universe_plan,
        "timeframe": family.timeframe,
        "walk_forward_plan_fingerprint": family.walk_forward_plan_fingerprint,
        "experiment_ids": sorted(family.experiment_ids),
        "metric_names": sorted(family.metric_names),
    }
    return _hash_payload(payload)


def metric_family_fingerprint(family: MetricFamily) -> str:
    """Return a deterministic fingerprint of a metric family."""
    payload: dict[str, Any] = {
        "metric_names": sorted(family.metric_names),
    }
    return _hash_payload(payload)


def adjusted_evidence_fingerprint(evidence: AdjustedEvidence) -> str:
    """Return a deterministic fingerprint of adjusted evidence."""
    payload: dict[str, Any] = {
        "experiment_id": evidence.experiment_id,
        "metric_name": evidence.metric_name,
        "raw_value": str(evidence.raw_value),
        "adjusted_value": str(evidence.adjusted_value),
        "family_id": evidence.family_id,
        "family_type": evidence.family_type,
        "method": evidence.method.value,
        "rank": evidence.rank,
        "family_size": evidence.family_size,
        "alpha": str(evidence.alpha),
    }
    return _hash_payload(payload)


def replication_fingerprint(result: ReplicationResult) -> str:
    """Return a deterministic fingerprint of a replication result."""
    payload: dict[str, Any] = {
        "experiment_id": result.experiment_id,
        "metric_name": result.metric_name,
        "family_id": result.family_id,
        "family_type": result.family_type,
        "state": result.state.value,
        "candidate_count": result.candidate_count,
        "baseline_count": result.baseline_count,
        "independent_count": result.independent_count,
        "direction": result.direction.value if result.direction is not None else None,
    }
    return _hash_payload(payload)


def snapshot_fingerprint(snapshot: LedgerSnapshot) -> str:
    """Return a deterministic fingerprint of a ledger snapshot.

    Excludes the snapshot's own fingerprint.
    """
    payload: dict[str, Any] = {
        "version": snapshot.version,
        "spec_version": snapshot.spec_version,
        "snapshot_id": snapshot.snapshot_id,
        "previous_snapshot_fingerprint": snapshot.previous_snapshot_fingerprint,
        "entry_fingerprints": list(snapshot.entry_fingerprints),
        "family_fingerprints": list(snapshot.family_fingerprints),
        "adjustment_fingerprints": list(snapshot.adjustment_fingerprints),
        "replication_fingerprints": list(snapshot.replication_fingerprints),
    }
    return _hash_payload(payload)


def manifest_fingerprint(manifest: EvidenceLedgerManifest) -> str:
    """Return a deterministic fingerprint of the manifest.

    Excludes generated_at.
    """
    payload: dict[str, Any] = {
        "version": manifest.version,
        "spec_version": manifest.spec_version,
        "evidence_ledger_version": manifest.evidence_ledger_version,
        "entry_count": manifest.entry_count,
        "family_count": manifest.family_count,
        "adjustment_count": manifest.adjustment_count,
        "replication_count": manifest.replication_count,
        "snapshot_fingerprint": manifest.snapshot_fingerprint,
        "overall_fingerprint": manifest.overall_fingerprint,
    }
    return _hash_payload(payload)


def report_fingerprint(report: EvidenceLedgerReport) -> str:
    """Return a deterministic fingerprint of the full report."""
    payload: dict[str, Any] = {
        "version": report.version,
        "spec_version": report.spec_version,
        "evidence_ledger_version": report.evidence_ledger_version,
        "snapshot_fingerprint": report.snapshot.fingerprint,
        "manifest_fingerprint": report.manifest.overall_fingerprint,
    }
    return _hash_payload(payload)
