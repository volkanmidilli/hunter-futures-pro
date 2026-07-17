"""Deterministic JSON and Markdown writers for the research evidence ledger (MVP-68 / SPEC-069)."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.research_evidence_ledger.models import (
    EVIDENCE_LEDGER_VERSION,
    SPEC_VERSION,
    UNAVAILABLE,
    AdjustedEvidence,
    EvidenceLedgerEntry,
    EvidenceLedgerManifest,
    EvidenceLedgerReport,
    EvidenceLedgerSafetyFlags,
    EvidenceLedgerWriterError,
    EvidenceLedgerSafetyError,
    EvidenceLedgerSnapshotError,
    ExperimentFamily,
    ExperimentRegistration,
    HypothesisFamily,
    LedgerSnapshot,
    MetricFamily,
    OUTPUT_DIR_REJECTED,
    ReplicationResult,
    WRITER_ERROR,
)

_SAFETY_NOTICE = (
    "This artifact is research-only and records cross-experiment evidence, "
    "registration status, drift findings, multiple-testing adjustments, "
    "and replication summaries.\n"
    "Adjusted evidence and replication labels do not prove profitability "
    "and do not authorize execution, production deployment, live trading, "
    "automatic execution, strategy selection, universe selection, "
    "order placement, signal generation, strategy mutation, "
    "universe mutation, or position changes.\n"
    "Human review remains required."
)


def _serialize_value(value: Any) -> Any:
    """Serialize a value to a deterministic JSON-safe structure."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, frozenset):
        return sorted(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, EvidenceLedgerSafetyFlags):
        return {
            "research_only": value.research_only,
            "execution_approval_granted": value.execution_approval_granted,
            "production_approval_granted": value.production_approval_granted,
            "live_trading_allowed": value.live_trading_allowed,
            "automatic_execution_allowed": value.automatic_execution_allowed,
            "human_approval_required": value.human_approval_required,
            "no_direct_subprocess": value.no_direct_subprocess,
            "no_network_connection": value.no_network_connection,
            "no_database_connection": value.no_database_connection,
            "no_exchange_connection": value.no_exchange_connection,
            "no_remote_changes": value.no_remote_changes,
            "no_action_commands_emitted": value.no_action_commands_emitted,
            "no_strategy_mutation": value.no_strategy_mutation,
            "no_universe_mutation": value.no_universe_mutation,
            "no_config_mutation": value.no_config_mutation,
        }
    return value


def _redact_paths(value: Any) -> Any:
    """Redact absolute paths from serialized output."""
    if isinstance(value, str):
        import re
        value = re.sub(r"/home/[^/]+/", "/home/[REDACTED]/", value)
        value = re.sub(r"/tmp/[^\",}\s\]]+", "/tmp/[REDACTED]", value)
        return value
    if isinstance(value, dict):
        return {k: _redact_paths(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_paths(v) for v in value]
    return value


def _registration_payload(reg: ExperimentRegistration) -> dict[str, Any]:
    """Serialize an experiment registration."""
    return {
        "experiment_id": reg.experiment_id,
        "hypothesis": reg.hypothesis,
        "strategy_name": reg.strategy_name,
        "universe_plan": reg.universe_plan,
        "timeframe": reg.timeframe,
        "walk_forward_plan_fingerprint": reg.walk_forward_plan_fingerprint,
        "metric_family": list(reg.metric_family),
        "independence": reg.independence.value,
        "status": reg.status.value,
        "hypothesis_family_id": reg.hypothesis_family_id,
        "experiment_family_id": reg.experiment_family_id,
        "confidence_config_fingerprint": reg.confidence_config_fingerprint,
        "regime_policy": reg.regime_policy,
        "direction_policy": reg.direction_policy,
        "fingerprint": reg.fingerprint,
    }


def _evidence_ledger_entry_payload(entry: EvidenceLedgerEntry) -> dict[str, Any]:
    """Serialize a ledger entry."""
    payload: dict[str, Any] = {
        "experiment_id": entry.registration.experiment_id,
        "registration_fingerprint": entry.registration.fingerprint,
        "status": entry.status.value,
        "fingerprint": entry.fingerprint,
    }
    if entry.evidence is not None:
        payload["evidence_fingerprint"] = entry.evidence.evidence_fingerprint
        payload["has_walk_forward"] = entry.evidence.walk_forward_report is not None
        payload["has_confidence"] = entry.evidence.confidence_report is not None
    return payload


def _hypothesis_family_payload(family: HypothesisFamily) -> dict[str, Any]:
    return {
        "hypothesis_family_id": family.hypothesis_family_id,
        "hypothesis": family.hypothesis,
        "experiment_ids": list(family.experiment_ids),
        "metric_names": list(family.metric_names),
        "fingerprint": family.fingerprint,
    }


def _experiment_family_payload(family: ExperimentFamily) -> dict[str, Any]:
    return {
        "experiment_family_id": family.experiment_family_id,
        "strategy_name": family.strategy_name,
        "universe_plan": family.universe_plan,
        "timeframe": family.timeframe,
        "walk_forward_plan_fingerprint": family.walk_forward_plan_fingerprint,
        "experiment_ids": list(family.experiment_ids),
        "metric_names": list(family.metric_names),
        "fingerprint": family.fingerprint,
    }


def _metric_family_payload(family: MetricFamily) -> dict[str, Any]:
    return {
        "metric_names": list(family.metric_names),
        "fingerprint": family.fingerprint,
    }


def _snapshot_payload(snapshot: LedgerSnapshot) -> dict[str, Any]:
    return {
        "version": snapshot.version,
        "spec_version": snapshot.spec_version,
        "snapshot_id": snapshot.snapshot_id,
        "previous_snapshot_fingerprint": snapshot.previous_snapshot_fingerprint,
        "entry_fingerprints": list(snapshot.entry_fingerprints),
        "family_fingerprints": list(snapshot.family_fingerprints),
        "adjustment_fingerprints": list(snapshot.adjustment_fingerprints),
        "replication_fingerprints": list(snapshot.replication_fingerprints),
        "fingerprint": snapshot.fingerprint,
    }


def _adjusted_evidence_payload(adj: AdjustedEvidence) -> dict[str, Any]:
    return {
        "experiment_id": adj.experiment_id,
        "metric_name": adj.metric_name,
        "raw_value": str(adj.raw_value),
        "adjusted_value": str(adj.adjusted_value),
        "family_id": adj.family_id,
        "family_type": adj.family_type,
        "method": adj.method.value,
        "rank": adj.rank,
        "family_size": adj.family_size,
        "alpha": str(adj.alpha),
        "fingerprint": adj.fingerprint,
    }


def _replication_payload(result: ReplicationResult) -> dict[str, Any]:
    return {
        "experiment_id": result.experiment_id,
        "metric_name": result.metric_name,
        "family_id": result.family_id,
        "family_type": result.family_type,
        "state": result.state.value,
        "candidate_count": result.candidate_count,
        "baseline_count": result.baseline_count,
        "independent_count": result.independent_count,
        "direction": result.direction.value if result.direction is not None else None,
        "fingerprint": result.fingerprint,
    }


def _manifest_payload(manifest: EvidenceLedgerManifest) -> dict[str, Any]:
    return {
        "version": manifest.version,
        "spec_version": manifest.spec_version,
        "evidence_ledger_version": manifest.evidence_ledger_version,
        "generated_at": manifest.generated_at.isoformat(),
        "entry_count": manifest.entry_count,
        "family_count": manifest.family_count,
        "adjustment_count": manifest.adjustment_count,
        "replication_count": manifest.replication_count,
        "snapshot_fingerprint": manifest.snapshot_fingerprint,
        "overall_fingerprint": manifest.overall_fingerprint,
    }


def _build_report_dict(report: EvidenceLedgerReport) -> dict[str, Any]:
    """Build a deterministic dict from the evidence ledger report."""
    return {
        "version": report.version,
        "spec_version": report.spec_version,
        "evidence_ledger_version": report.evidence_ledger_version,
        "fingerprint": report.fingerprint,
        "research_only": report.research_only,
        "human_approval_required": report.human_approval_required,
        "registrations": [_registration_payload(r) for r in report.registrations],
        "entries": [_evidence_ledger_entry_payload(e) for e in report.entries],
        "hypothesis_families": [_hypothesis_family_payload(hf) for hf in report.hypothesis_families],
        "experiment_families": [_experiment_family_payload(ef) for ef in report.experiment_families],
        "metric_families": [_metric_family_payload(mf) for mf in report.metric_families],
        "adjustments": [_adjusted_evidence_payload(a) for a in report.adjustments],
        "replications": [_replication_payload(r) for r in report.replications],
        "snapshot": _snapshot_payload(report.snapshot),
        "manifest": _manifest_payload(report.manifest),
    }


def _write_json(output_path: Path, payload: dict[str, Any]) -> None:
    """Atomically write a JSON file with deterministic encoding."""
    json_bytes = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
    ).encode("utf-8") + b"\n"

    # Atomic write via temp file + rename
    tmp_path = output_path.with_suffix(".tmp")
    tmp_path.write_bytes(json_bytes)
    tmp_path.rename(output_path)


def _generate_markdown(report: EvidenceLedgerReport) -> str:
    """Generate a Markdown summary of the evidence ledger report."""
    lines: list[str] = []
    lines.append("# Evidence Ledger Report")
    lines.append("")
    lines.append(f"**Version:** {report.version}")
    lines.append(f"**Spec:** {report.spec_version}")
    lines.append(f"**Fingerprint:** {report.fingerprint}")
    lines.append(f"**Research-only:** {report.research_only}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Safety Notice")
    lines.append("")
    lines.append(f"```{_SAFETY_NOTICE}```")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Registrations:** {len(report.registrations)}")
    lines.append(f"- **Entries:** {len(report.entries)}")
    lines.append(f"- **Hypothesis Families:** {len(report.hypothesis_families)}")
    lines.append(f"- **Experiment Families:** {len(report.experiment_families)}")
    lines.append(f"- **Metric Families:** {len(report.metric_families)}")
    lines.append(f"- **Adjustments:** {len(report.adjustments)}")
    lines.append(f"- **Replications:** {len(report.replications)}")
    lines.append("")
    lines.append("## Registrations")
    lines.append("")
    for reg in report.registrations:
        lines.append(f"- **{reg.experiment_id}** — {reg.hypothesis[:60]}...")
        lines.append(f"  - Status: {reg.status.value}, Family: {reg.experiment_family_id or 'N/A'}")
    lines.append("")
    lines.append("## Hypothesis Families")
    lines.append("")
    for hf in report.hypothesis_families:
        lines.append(f"- **{hf.hypothesis_family_id}** — {hf.hypothesis[:60]}...")
        lines.append(f"  - Experiments: {len(hf.experiment_ids)}, Metrics: {len(hf.metric_names)}")
    lines.append("")
    lines.append("## Experiment Families")
    lines.append("")
    for ef in report.experiment_families:
        lines.append(f"- **{ef.experiment_family_id}** — {ef.strategy_name}")
        lines.append(f"  - Universe: {ef.universe_plan}, Timeframe: {ef.timeframe}")
        lines.append(f"  - Experiments: {len(ef.experiment_ids)}")
    lines.append("")
    lines.append("## Multiple-Testing Adjustments")
    lines.append("")
    for adj in report.adjustments:
        lines.append(
            f"- {adj.experiment_id}/{adj.metric_name}: "
            f"raw={adj.raw_value} → adj={adj.adjusted_value} "
            f"({adj.method.value}, family={adj.family_id})"
        )
    lines.append("")
    lines.append("## Replication Results")
    lines.append("")
    for rep in report.replications:
        lines.append(
            f"- {rep.experiment_id}/{rep.metric_name}: "
            f"state={rep.state.value}, "
            f"candidate={rep.candidate_count}, baseline={rep.baseline_count}"
        )
    lines.append("")
    lines.append("## Snapshot")
    lines.append("")
    snap = report.snapshot
    lines.append(f"- **Snapshot ID:** {snap.snapshot_id}")
    lines.append(f"- **Previous Snapshot:** {snap.previous_snapshot_fingerprint or '(none)'}")
    lines.append(f"- **Entries:** {len(snap.entry_fingerprints)}")
    lines.append(f"- **Families:** {len(snap.family_fingerprints)}")
    lines.append(f"- **Adjustments:** {len(snap.adjustment_fingerprints)}")
    lines.append(f"- **Replications:** {len(snap.replication_fingerprints)}")
    lines.append("")
    lines.append("## Manifest")
    lines.append("")
    lines.append(f"- **Overall Fingerprint:** {report.manifest.overall_fingerprint}")
    lines.append(f"- **Generated At:** {report.manifest.generated_at.isoformat()}")

    return "\n".join(lines)


def _validate_output_dir(output_dir: str | Path) -> Path:
    """Validate and resolve the output directory.

    Rejects paths under 'data/' and 'reports/'.
    """
    path = Path(output_dir).resolve()
    parts = path.parts

    # Check if any parent directory is named 'data' or 'reports'
    for i, part in enumerate(parts):
        if part in ("data", "reports"):
            raise EvidenceLedgerWriterError(
                f"Output directory rejected: {output_dir} is under '{part}/'",
                reason_code=OUTPUT_DIR_REJECTED,
            )

    return path


class EvidenceLedgerWriter:
    """Writer for evidence ledger artifacts."""

    def __init__(self, output_dir: str | Path) -> None:
        self._output_dir = _validate_output_dir(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    def write_registrations(
        self, registrations: tuple[ExperimentRegistration, ...]
    ) -> Path:
        """Write experiment registrations JSON."""
        payload = {
            "version": EVIDENCE_LEDGER_VERSION,
            "spec_version": SPEC_VERSION,
            "research_only": True,
            "data": [_registration_payload(r) for r in registrations],
        }
        path = self._output_dir / "experiment_registrations.json"
        _write_json(path, _redact_paths(payload))
        return path

    def write_entries(
        self, entries: tuple[EvidenceLedgerEntry, ...]
    ) -> Path:
        """Write evidence ledger entries JSON."""
        payload = {
            "version": EVIDENCE_LEDGER_VERSION,
            "spec_version": SPEC_VERSION,
            "research_only": True,
            "data": [_evidence_ledger_entry_payload(e) for e in entries],
        }
        path = self._output_dir / "evidence_ledger_entries.json"
        _write_json(path, _redact_paths(payload))
        return path

    def write_hypothesis_families(
        self, families: tuple[HypothesisFamily, ...]
    ) -> Path:
        """Write hypothesis family index JSON."""
        payload = {
            "version": EVIDENCE_LEDGER_VERSION,
            "spec_version": SPEC_VERSION,
            "research_only": True,
            "data": [_hypothesis_family_payload(f) for f in families],
        }
        path = self._output_dir / "hypothesis_family_index.json"
        _write_json(path, _redact_paths(payload))
        return path

    def write_experiment_families(
        self, families: tuple[ExperimentFamily, ...]
    ) -> Path:
        """Write experiment family index JSON."""
        payload = {
            "version": EVIDENCE_LEDGER_VERSION,
            "spec_version": SPEC_VERSION,
            "research_only": True,
            "data": [_experiment_family_payload(f) for f in families],
        }
        path = self._output_dir / "experiment_family_index.json"
        _write_json(path, _redact_paths(payload))
        return path

    def write_metric_families(
        self, families: tuple[MetricFamily, ...]
    ) -> Path:
        """Write metric family index JSON."""
        payload = {
            "version": EVIDENCE_LEDGER_VERSION,
            "spec_version": SPEC_VERSION,
            "research_only": True,
            "data": [_metric_family_payload(f) for f in families],
        }
        path = self._output_dir / "metric_family_index.json"
        _write_json(path, _redact_paths(payload))
        return path

    def write_adjustments(
        self, adjustments: tuple[AdjustedEvidence, ...]
    ) -> Path:
        """Write multiple-testing adjustments JSON."""
        payload = {
            "version": EVIDENCE_LEDGER_VERSION,
            "spec_version": SPEC_VERSION,
            "research_only": True,
            "data": [_adjusted_evidence_payload(a) for a in adjustments],
        }
        path = self._output_dir / "multiple_testing_adjustments.json"
        _write_json(path, _redact_paths(payload))
        return path

    def write_replications(
        self, replications: tuple[ReplicationResult, ...]
    ) -> Path:
        """Write replication results JSON."""
        payload = {
            "version": EVIDENCE_LEDGER_VERSION,
            "spec_version": SPEC_VERSION,
            "research_only": True,
            "data": [_replication_payload(r) for r in replications],
        }
        path = self._output_dir / "replication_results.json"
        _write_json(path, _redact_paths(payload))
        return path

    def write_snapshot(self, snapshot: LedgerSnapshot) -> Path:
        """Write ledger snapshot JSON."""
        payload = {
            "version": EVIDENCE_LEDGER_VERSION,
            "spec_version": SPEC_VERSION,
            "research_only": True,
            "data": _snapshot_payload(snapshot),
        }
        path = self._output_dir / "evidence_ledger_snapshot.json"
        _write_json(path, _redact_paths(payload))
        return path

    def write_report(self, report: EvidenceLedgerReport) -> Path:
        """Write evidence ledger report JSON."""
        payload = _build_report_dict(report)
        payload["_safety_notice"] = _SAFETY_NOTICE
        path = self._output_dir / "evidence_ledger_report.json"
        _write_json(path, _redact_paths(payload))
        return path

    def write_report_markdown(self, report: EvidenceLedgerReport) -> Path:
        """Write evidence ledger report Markdown."""
        md = _generate_markdown(report)
        path = self._output_dir / "evidence_ledger_report.md"
        path.write_text(md, encoding="utf-8")
        return path

    def write_manifest(self, manifest: EvidenceLedgerManifest) -> Path:
        """Write evidence ledger manifest JSON."""
        payload = {
            "version": EVIDENCE_LEDGER_VERSION,
            "spec_version": SPEC_VERSION,
            "research_only": True,
            "data": _manifest_payload(manifest),
        }
        path = self._output_dir / "evidence_ledger_manifest.json"
        _write_json(path, _redact_paths(payload))
        return path


def write_all_evidence_ledger_artifacts(
    report: EvidenceLedgerReport,
    output_dir: str | Path,
) -> list[Path]:
    """Write all evidence ledger artifacts to the output directory."""
    writer = EvidenceLedgerWriter(output_dir)
    paths: list[Path] = []

    paths.append(writer.write_registrations(report.registrations))
    paths.append(writer.write_entries(report.entries))
    paths.append(writer.write_hypothesis_families(report.hypothesis_families))
    paths.append(writer.write_experiment_families(report.experiment_families))
    paths.append(writer.write_metric_families(report.metric_families))

    if report.adjustments:
        paths.append(writer.write_adjustments(report.adjustments))
    if report.replications:
        paths.append(writer.write_replications(report.replications))

    paths.append(writer.write_snapshot(report.snapshot))
    paths.append(writer.write_report(report))
    paths.append(writer.write_report_markdown(report))
    paths.append(writer.write_manifest(report.manifest))

    return paths
