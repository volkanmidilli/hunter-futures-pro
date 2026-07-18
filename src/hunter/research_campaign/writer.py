"""Deterministic JSON and Markdown writer for research campaign artifacts (MVP-69 / SPEC-070).

No subprocess, threading, network, eval, exec, or dynamic code.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from hunter.research_campaign.errors import ResearchCampaignWriterError
from hunter.research_campaign.models import (
    OUTPUT_DIR_REJECTED,
    SILENT_OVERWRITE_BLOCKED,
    CampaignArtifactManifest,
    CampaignCheckpoint,
    CampaignDossier,
    CampaignEvidenceSummary,
    CampaignExecutionManifest,
    CampaignOutputPolicy,
    CampaignRegistrationSet,
    CampaignResumeManifest,
    CampaignStatusSummary,
    CompiledCampaign,
    ExperimentExecutionRecord,
    ResearchCampaignDefinition,
    ResearchCampaignSafetyFlags,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SAFETY_NOTICE = (
    "RESEARCH ONLY: This artifact is produced by the research campaign compiler "
    "and orchestrator (MVP-69/MVP-70, SPEC-070).\n"
    "All compiled experiments are research-only simulations. "
    "They do not authorize execution, production deployment, live trading, "
    "automatic execution, order placement, signal generation, "
    "strategy mutation, universe mutation, or position changes.\n"
    "Human review remains required.\n"
    "Past performance does not guarantee future results."
)

_REJECTED_DIR_PREFIXES: tuple[str, ...] = (os.sep + "data", os.sep + "reports", "data", "reports")
_PATH_REDACT_PATTERN: re.Pattern = re.compile(r"/home/[^/\s]+")
_SECRET_REDACT_PATTERN: re.Pattern = re.compile(r"(?i)(key|token|secret|password)[:=]\s*[^\s&]+")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _redact_text(text: str) -> str:
    """Redact paths and secret-like values in text."""
    text = _PATH_REDACT_PATTERN.sub("/home/***", text)
    text = _SECRET_REDACT_PATTERN.sub(r"\1=***", text)
    return text


def _serialize_value(value: Any) -> Any:
    """Serialize a value into a deterministic JSON-safe structure."""
    if value is None:
        return None
    if hasattr(value, "__dict__"):
        # Dataclass instance — convert via its dict.
        return {
            k: _serialize_value(v)
            for k, v in value.__dict__.items()
            if not k.startswith("_")
        }
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        # Redact strings for safety.
        if isinstance(value, str):
            return _redact_text(value)
        return value
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def _write_json_atomic(path: Path, payload: dict[str, Any], overwrite: bool) -> None:
    """Write a JSON payload atomically to *path*.

    Rejects silent overwrites unless *overwrite* is True.
    """
    if path.exists() and not overwrite:
        raise ResearchCampaignWriterError(
            f"Output file already exists: {path}",
            reason_code=SILENT_OVERWRITE_BLOCKED,
        )

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(
                payload,
                f,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                indent=2,
            )
            f.write("\n")
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _write_markdown_atomic(path: Path, content: str, overwrite: bool) -> None:
    """Write Markdown content atomically to *path*."""
    if path.exists() and not overwrite:
        raise ResearchCampaignWriterError(
            f"Output file already exists: {path}",
            reason_code=SILENT_OVERWRITE_BLOCKED,
        )

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _validate_output_dir(output_dir: Path) -> None:
    """Raise if output_dir is under data/ or reports/."""
    resolved = output_dir.resolve()
    for prefix in _REJECTED_DIR_PREFIXES:
        resolved_str = resolved.as_posix()
        if resolved_str.endswith("/" + prefix) or ("/" + prefix + "/") in resolved_str:
            raise ResearchCampaignWriterError(
                f"Output directory rejected: {output_dir} is under {prefix}/",
                reason_code=OUTPUT_DIR_REJECTED,
            )


# ---------------------------------------------------------------------------
# Artifact payload builders
# ---------------------------------------------------------------------------


def _build_definition_payload(
    definition: ResearchCampaignDefinition,
) -> dict[str, Any]:
    return {
        "campaign_id": definition.campaign_id,
        "campaign_schema_version": definition.campaign_schema_version,
        "max_experiment_count": definition.max_experiment_count,
        "execution_policy": definition.execution_policy.value,
        "stop_after_n_failures": definition.stop_after_n_failures,
        "resume_policy": definition.resume_policy.value,
        "fingerprint": definition.fingerprint,
        "safety_flags": _serialize_value(definition.safety_flags),
        "reason_codes": list(definition.reason_codes),
    }


def _build_compiled_matrix_payload(
    compiled: CompiledCampaign,
) -> dict[str, Any]:
    return {
        "campaign_fingerprint": compiled.campaign.fingerprint,
        "experiment_count": compiled.experiment_count,
        "excluded_count": compiled.excluded_count,
        "fingerprint": compiled.fingerprint,
        "compile_timestamp": compiled.compile_timestamp.isoformat(),
        "reason_codes": list(compiled.reason_codes),
        "experiments": [
            {
                "experiment_id": e.experiment_id,
                "campaign_id": e.campaign_id,
                "strategy_name": e.strategy.strategy_name,
                "timeframe": e.timeframe,
                "data_id": e.historical_data.data_id,
                "universe_plan_id": e.universe_plan.universe_plan_id,
                "template_id": e.walk_forward_template.template_id,
                "config_id": e.confidence_config.config_id,
                "experiment_family_id": e.experiment_family.family_id,
                "hypothesis_family_id": e.hypothesis_family.family_id,
                "metric_names": list(e.metric_family.metric_names),
                "fingerprint": e.fingerprint,
            }
            for e in compiled.experiments
        ],
    }


def _build_registrations_payload(
    registration_set: CampaignRegistrationSet,
) -> dict[str, Any]:
    return {
        "campaign_fingerprint": registration_set.campaign.fingerprint,
        "fingerprint": registration_set.fingerprint,
        "registrations": [
            {
                "experiment_id": r.experiment_id,
                "hypothesis": r.hypothesis,
                "strategy_name": r.strategy_name,
                "universe_plan": r.universe_plan,
                "timeframe": r.timeframe,
                "walk_forward_plan_fingerprint": r.walk_forward_plan_fingerprint,
                "metric_family": list(r.metric_family),
                "independence": r.independence.value,
                "status": r.status.value,
                "fingerprint": r.fingerprint,
            }
            for r in registration_set.registrations
        ],
    }


def _build_execution_manifest_payload(
    manifest: CampaignExecutionManifest,
) -> dict[str, Any]:
    return {
        "campaign_definition_fingerprint": manifest.campaign_definition.fingerprint,
        "compiled_campaign_fingerprint": manifest.compiled_campaign.fingerprint,
        "registration_set_fingerprint": manifest.registration_set.fingerprint,
        "fingerprint": manifest.fingerprint,
        "created_at": manifest.created_at.isoformat(),
        "reason_codes": list(manifest.reason_codes),
    }


def _build_records_payload(
    records: tuple[ExperimentExecutionRecord, ...],
) -> dict[str, Any]:
    return {
        "records": [
            {
                "experiment_id": r.experiment_id,
                "campaign_id": r.campaign_id,
                "experiment_fingerprint": r.experiment_fingerprint,
                "registration_fingerprint": r.registration_fingerprint,
                "outcome": r.outcome.value,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat(),
                "reason_codes": list(r.reason_codes),
                "evidence": _serialize_value(r.evidence),
            }
            for r in records
        ],
    }


def _build_resume_manifest_payload(
    manifest: CampaignResumeManifest,
) -> dict[str, Any]:
    return {
        "campaign_fingerprint": manifest.campaign_fingerprint,
        "resume_policy": manifest.resume_policy.value,
        "fingerprint": manifest.fingerprint,
        "created_at": manifest.created_at.isoformat(),
        "reason_codes": list(manifest.reason_codes),
        "prior_evidence_count": len(manifest.prior_evidence),
    }


def _build_evidence_summary_payload(
    summary: CampaignEvidenceSummary,
) -> dict[str, Any]:
    return {
        "walk_forward_attempted": summary.walk_forward_attempted,
        "walk_forward_completed": summary.walk_forward_completed,
        "confidence_attempted": summary.confidence_attempted,
        "confidence_completed": summary.confidence_completed,
        "ledger_entries": summary.ledger_entries,
        "ledger_snapshots": summary.ledger_snapshots,
        "fingerprint": summary.fingerprint,
    }


def _build_dossier_payload(
    dossier: CampaignDossier,
) -> dict[str, Any]:
    return {
        "campaign_id": dossier.campaign_id,
        "campaign_fingerprint": dossier.campaign_fingerprint,
        "compiled_campaign_fingerprint": dossier.compiled_campaign_fingerprint,
        "fingerprint": dossier.fingerprint,
        "generated_at": dossier.generated_at.isoformat(),
        "reason_codes": list(dossier.reason_codes),
        "status_summary": _serialize_value(dossier.status_summary),
        "evidence_summary": _serialize_value(dossier.evidence_summary),
        "safety_flags": _serialize_value(dossier.safety_flags),
        "_safety_notice": _SAFETY_NOTICE,
    }


# ---------------------------------------------------------------------------
# CampaignWriter
# ---------------------------------------------------------------------------


class CampaignWriter:
    """Deterministic writer for research campaign artifacts.

    Every write method performs:
    - Output-directory safety checks
    - Atomic file writes (temp file + replace)
    - Silent-overwrite protection
    - Path and secret redaction in text
    """

    def __init__(
        self,
        output_dir: str | Path,
        overwrite: bool = False,
    ) -> None:
        self._output_dir = Path(output_dir).resolve()
        _validate_output_dir(self._output_dir)
        self._overwrite = overwrite
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    @property
    def overwrite(self) -> bool:
        return self._overwrite

    # ------------------------------------------------------------------
    # Single artifact writes
    # ------------------------------------------------------------------

    def write_definition(
        self,
        definition: ResearchCampaignDefinition,
    ) -> Path:
        """Write ``research_campaign_definition.json``."""
        path = self._output_dir / "research_campaign_definition.json"
        payload = _build_definition_payload(definition)
        _write_json_atomic(path, payload, self._overwrite)
        return path

    def write_compiled_matrix(
        self,
        compiled_campaign: CompiledCampaign,
    ) -> Path:
        """Write ``compiled_experiment_matrix.json``."""
        path = self._output_dir / "compiled_experiment_matrix.json"
        payload = _build_compiled_matrix_payload(compiled_campaign)
        _write_json_atomic(path, payload, self._overwrite)
        return path

    def write_campaign_registrations(
        self,
        registration_set: CampaignRegistrationSet,
    ) -> Path:
        """Write ``campaign_registrations.json``."""
        path = self._output_dir / "campaign_registrations.json"
        payload = _build_registrations_payload(registration_set)
        _write_json_atomic(path, payload, self._overwrite)
        return path

    def write_execution_manifest(
        self,
        manifest: CampaignExecutionManifest,
    ) -> Path:
        """Write ``campaign_execution_manifest.json``."""
        path = self._output_dir / "campaign_execution_manifest.json"
        payload = _build_execution_manifest_payload(manifest)
        _write_json_atomic(path, payload, self._overwrite)
        return path

    def write_execution_records(
        self,
        records: tuple[ExperimentExecutionRecord, ...],
    ) -> Path:
        """Write ``campaign_execution_records.json``."""
        path = self._output_dir / "campaign_execution_records.json"
        payload = _build_records_payload(records)
        _write_json_atomic(path, payload, self._overwrite)
        return path

    def write_resume_manifest(
        self,
        manifest: CampaignResumeManifest,
    ) -> Path:
        """Write ``campaign_resume_manifest.json``."""
        path = self._output_dir / "campaign_resume_manifest.json"
        payload = _build_resume_manifest_payload(manifest)
        _write_json_atomic(path, payload, self._overwrite)
        return path

    def write_evidence_summary(
        self,
        summary: CampaignEvidenceSummary,
    ) -> Path:
        """Write ``campaign_evidence_summary.json``."""
        path = self._output_dir / "campaign_evidence_summary.json"
        payload = _build_evidence_summary_payload(summary)
        _write_json_atomic(path, payload, self._overwrite)
        return path

    def write_dossier(
        self,
        dossier: CampaignDossier,
    ) -> Path:
        """Write ``campaign_dossier.json``."""
        path = self._output_dir / "campaign_dossier.json"
        payload = _build_dossier_payload(dossier)
        _write_json_atomic(path, payload, self._overwrite)
        return path

    def write_dossier_markdown(
        self,
        dossier: CampaignDossier,
    ) -> Path:
        """Write ``campaign_dossier.md``."""
        path = self._output_dir / "campaign_dossier.md"
        content = _build_dossier_markdown(dossier)
        _write_markdown_atomic(path, content, self._overwrite)
        return path

    def write_artifact_manifest(
        self,
        artifact_paths: tuple[str, ...],
        dossier_fingerprint: str,
        campaign_id: str,
    ) -> Path:
        """Write ``campaign_artifact_manifest.json``."""
        path = self._output_dir / "campaign_artifact_manifest.json"
        manifest = CampaignArtifactManifest(
            campaign_id=campaign_id,
            artifact_paths=artifact_paths,
            dossier_fingerprint=dossier_fingerprint,
        )
        from hunter.research_campaign.fingerprint import (
            artifact_manifest_fingerprint,
        )

        fp = artifact_manifest_fingerprint(manifest)
        object.__setattr__(manifest, "fingerprint", fp)

        payload = {
            "campaign_id": manifest.campaign_id,
            "artifact_paths": list(manifest.artifact_paths),
            "dossier_fingerprint": manifest.dossier_fingerprint,
            "fingerprint": manifest.fingerprint,
            "generated_at": manifest.generated_at.isoformat(),
        }
        _write_json_atomic(path, payload, self._overwrite)
        return path

    # ------------------------------------------------------------------
    # Checkpoint write
    # ------------------------------------------------------------------

    def write_checkpoint(
        self,
        checkpoint_id: str,
        campaign_id: str,
        checkpoint_index: int,
        experiment_records: tuple[ExperimentExecutionRecord, ...],
        status: str | object,
        previous_checkpoint_fingerprint: str = "",
    ) -> Path:
        """Write a checkpoint file atomically."""
        from hunter.research_campaign.fingerprint import (
            checkpoint_fingerprint,
        )

        checkpoint = CampaignCheckpoint(
            checkpoint_id=checkpoint_id,
            campaign_id=campaign_id,
            checkpoint_index=checkpoint_index,
            experiment_records=experiment_records,
            status=status,
            previous_checkpoint_fingerprint=previous_checkpoint_fingerprint,
        )
        fp = checkpoint_fingerprint(checkpoint)
        object.__setattr__(checkpoint, "fingerprint", fp)

        path = (
            self._output_dir
            / "checkpoints"
            / f"checkpoint_{checkpoint_index:04d}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "checkpoint_id": checkpoint.checkpoint_id,
            "campaign_id": checkpoint.campaign_id,
            "checkpoint_index": checkpoint.checkpoint_index,
            "previous_checkpoint_fingerprint": checkpoint.previous_checkpoint_fingerprint,
            "status": checkpoint.status.value
            if hasattr(checkpoint.status, "value")
            else str(checkpoint.status),
            "fingerprint": checkpoint.fingerprint,
            "created_at": checkpoint.created_at.isoformat(),
            "reason_codes": list(checkpoint.reason_codes),
        }
        _write_json_atomic(path, payload, self._overwrite)
        return path

    # ------------------------------------------------------------------
    # Batch write
    # ------------------------------------------------------------------

    def write_all_campaign_artifacts(
        self,
        definition: ResearchCampaignDefinition,
        compiled_campaign: CompiledCampaign,
        registration_set: CampaignRegistrationSet,
        execution_manifest: CampaignExecutionManifest,
        execution_records: tuple[ExperimentExecutionRecord, ...],
        dossier: CampaignDossier,
        resume_manifest: CampaignResumeManifest | None = None,
        evidence_summary: CampaignEvidenceSummary | None = None,
    ) -> tuple[Path, ...]:
        """Write all 10 campaign artifacts and return their paths."""
        paths: list[Path] = []

        paths.append(self.write_definition(definition))
        paths.append(self.write_compiled_matrix(compiled_campaign))
        paths.append(self.write_campaign_registrations(registration_set))
        paths.append(self.write_execution_manifest(execution_manifest))
        paths.append(self.write_execution_records(execution_records))

        if resume_manifest is not None:
            paths.append(self.write_resume_manifest(resume_manifest))

        if evidence_summary is not None:
            paths.append(self.write_evidence_summary(evidence_summary))

        paths.append(self.write_dossier(dossier))
        paths.append(self.write_dossier_markdown(dossier))

        artifact_paths = tuple(str(p) for p in paths)
        paths.append(
            self.write_artifact_manifest(
                artifact_paths=artifact_paths,
                dossier_fingerprint=dossier.fingerprint,
                campaign_id=dossier.campaign_id,
            )
        )

        return tuple(paths)


# ---------------------------------------------------------------------------
# Markdown dossier builder
# ---------------------------------------------------------------------------


def _build_dossier_markdown(dossier: CampaignDossier) -> str:
    """Build a Markdown summary of the campaign dossier."""
    lines: list[str] = []
    lines.append(f"# Campaign Dossier: {dossier.campaign_id}")
    lines.append("")
    lines.append(f"- **Campaign Fingerprint**: `{dossier.campaign_fingerprint}`")
    lines.append(
        f"- **Compiled Campaign Fingerprint**: `{dossier.compiled_campaign_fingerprint}`"
    )
    lines.append(f"- **Dossier Fingerprint**: `{dossier.fingerprint}`")
    lines.append(f"- **Generated At**: {dossier.generated_at.isoformat()}")
    lines.append("")

    # Status summary.
    ss = dossier.status_summary
    lines.append("## Status Summary")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total | {ss.total} |")
    lines.append(f"| Completed | {ss.completed} |")
    lines.append(f"| Failed | {ss.failed} |")
    lines.append(f"| Blocked | {ss.blocked} |")
    lines.append(f"| Timed Out | {ss.timed_out} |")
    lines.append(f"| Unsupported | {ss.unsupported} |")
    lines.append(f"| Insufficient Evidence | {ss.insufficient_evidence} |")
    lines.append(f"| Withdrawn | {ss.withdrawn} |")
    lines.append(f"| Skipped by Policy | {ss.skipped_by_policy} |")
    lines.append(f"| Stale Resume Evidence | {ss.stale_resume_evidence} |")
    lines.append("")

    # Evidence summary.
    es = dossier.evidence_summary
    lines.append("## Evidence Summary")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Walk-Forward Attempted | {es.walk_forward_attempted} |")
    lines.append(f"| Walk-Forward Completed | {es.walk_forward_completed} |")
    lines.append(f"| Confidence Attempted | {es.confidence_attempted} |")
    lines.append(f"| Confidence Completed | {es.confidence_completed} |")
    lines.append(f"| Ledger Entries | {es.ledger_entries} |")
    lines.append(f"| Ledger Snapshots | {es.ledger_snapshots} |")
    lines.append("")

    # Execution records.
    lines.append("## Execution Records")
    lines.append("")
    lines.append(f"Total records: {len(dossier.execution_records)}")
    lines.append("")
    for rec in dossier.execution_records:
        lines.append(
            f"- **{rec.experiment_id}**: {rec.outcome.value} "
            f"(fingerprint: `{rec.experiment_fingerprint[:16]}...`)"
        )
    lines.append("")

    # Safety notice.
    lines.append("---")
    lines.append("")
    lines.append(f"_{_SAFETY_NOTICE}_")
    lines.append("")

    return "\n".join(lines)
