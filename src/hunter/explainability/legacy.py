"""Legacy-run migration for SPEC-078 (pre-SPEC-078 production publishes).

Imports a *real* published pairlist + audit (the original decision
artifacts of a pre-explainability Hunter run) into the explainability
store as a run with ``provenance_type=RECONSTRUCTED``.  Migration never
reruns ranking and never invents criteria: every value comes from the
source artifacts, and anything the source artifacts did not record
(data-quality values, the exact ``target_final_pairs`` threshold, gate
metadata) is left UNKNOWN with the gap stated in ``reconstruction_notes``.

Without an audit artifact the run's decision records are incomplete: the
manifest is written with ``decision_records_complete=False`` and lookups
fail closed with ``LEGACY_RUN_INCOMPLETE`` rather than guessing universe
membership.

Pointer discipline: a reconstructed run advances ``latest.json`` only per
:func:`storage.should_advance_reconstructed_pointer` -- never over an
ORIGINAL run, and only over an *older* reconstructed production publish.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hunter.explainability.models import (
    EXPLAINABILITY_SCHEMA_VERSION,
    PROVENANCE_RECONSTRUCTED,
    REASON_OUTSIDE_TARGET_FINAL_PAIRS,
    STAGE_FAIL,
    STAGE_PASS,
    STAGE_SKIP,
    STAGE_UNKNOWN,
    CandidateExplanationRecord,
    CandidateStageDecision,
    ExplainabilityError,
    ExplainabilityRunManifest,
)
from hunter.explainability.storage import (
    should_advance_reconstructed_pointer,
    write_latest_pointer,
    write_run,
)
from hunter.pairlist_export.models import (
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_PROFILE_EVIDENCE_INCOMPLETE,
)

GATE_OK = "OK"

_INSUFFICIENCY_CODES: frozenset[str] = frozenset(
    {REASON_INSUFFICIENT_EVIDENCE, REASON_PROFILE_EVIDENCE_INCOMPLETE}
)


class LegacyImportError(ExplainabilityError):
    """Legacy artifact is missing, unreadable, or internally inconsistent."""


@dataclass(frozen=True)
class LegacyImportResult:
    """Outcome of a legacy-run import."""

    run_id: str
    provenance_type: str
    candidate_count: int
    decision_records_complete: bool
    pointer_advanced: bool
    source_artifact_paths: tuple[str, ...]
    reconstruction_notes: str


def _load_json(path: Path, label: str) -> Any:
    if not path.is_file():
        raise LegacyImportError(f"{label} artifact not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegacyImportError(f"{label} artifact is unreadable: {path}") from exc


def _validate_pairlist(payload: Any, path: Path) -> tuple[str, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("pairs"), list):
        raise LegacyImportError(f"pairlist artifact has no 'pairs' list: {path}")
    pairs = payload["pairs"]
    if not all(isinstance(p, str) for p in pairs):
        raise LegacyImportError(f"pairlist artifact contains non-string pairs: {path}")
    return tuple(pairs)


def _validate_audit(payload: Any, path: Path) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise LegacyImportError(f"audit artifact is not a JSON object: {path}")
    for key in ("as_of_date", "selected", "rejected"):
        if key not in payload:
            raise LegacyImportError(f"audit artifact missing {key!r}: {path}")
    return payload


def _audit_entries(audit: dict[str, Any]) -> list[dict[str, Any]]:
    entries = list(audit.get("selected") or ()) + list(audit.get("rejected") or ())
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("pair"), str):
            raise LegacyImportError("audit artifact contains a malformed pair entry")
    return entries


def _legacy_run_id(as_of_date: str, audit: dict[str, Any] | None, pairlist_pairs: tuple[str, ...]) -> str:
    if audit is not None and isinstance(audit.get("fingerprint"), str) and audit["fingerprint"]:
        return f"{as_of_date}__legacy__{audit['fingerprint'][:12]}"
    canonical = json.dumps(list(pairlist_pairs), separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"{as_of_date}__legacy__{digest}"


def _build_legacy_record(
    entry: dict[str, Any],
    *,
    run_id: str,
    completed_at: str,
    published_pairs: frozenset[str],
    universe_total: int | None,
    eligible_count: int,
    source_run_id: str,
) -> CandidateExplanationRecord:
    """Build one candidate record strictly from a legacy audit entry."""
    pair = entry["pair"]
    selected = bool(entry.get("selected", False))
    published = selected and pair in published_pairs
    rank = entry.get("rank") if isinstance(entry.get("rank"), int) else None
    codes = tuple(c for c in (entry.get("reason_codes") or ()) if isinstance(c, str))
    insufficiency = tuple(c for c in codes if c in _INSUFFICIENCY_CODES)

    universe_stage = CandidateStageDecision(
        stage_id="universe",
        stage_order=1,
        status=STAGE_PASS,
        metrics={"universe_total": universe_total, "eligible_count": eligible_count},
        metadata={"evidence": "legacy audit"},
    )
    data_quality_stage = CandidateStageDecision(
        stage_id="data_quality",
        stage_order=2,
        status=STAGE_UNKNOWN,
        metrics={"data_quality_pct": entry.get("data_quality_pct")},
        metadata={"evidence": "not recorded in legacy audit"},
    )
    oi = entry.get("oi_score")
    liquidity_stage = CandidateStageDecision(
        stage_id="liquidity",
        stage_order=3,
        status=STAGE_PASS if oi is not None else STAGE_UNKNOWN,
        metrics={"oi_score": oi},
        metadata={"evidence": "legacy audit"},
    )
    rs = entry.get("rs_score")
    rs_stage = CandidateStageDecision(
        stage_id="relative_strength",
        stage_order=4,
        status=STAGE_PASS if rs is not None else STAGE_UNKNOWN,
        metrics={"rs_score": rs},
        metadata={"evidence": "legacy audit"},
    )
    if selected:
        ranking_status = STAGE_PASS
        ranking_codes: tuple[str, ...] = ()
    elif insufficiency:
        ranking_status = STAGE_FAIL
        ranking_codes = insufficiency
    else:
        ranking_status = STAGE_FAIL
        ranking_codes = (REASON_OUTSIDE_TARGET_FINAL_PAIRS,)
    ranking_stage = CandidateStageDecision(
        stage_id="ranking",
        stage_order=5,
        status=ranking_status,
        metrics={"rank": rank},
        thresholds={},
        reason_codes=ranking_codes,
        metadata={
            "selected": selected,
            "evidence": "legacy audit; exact target_final_pairs threshold not recorded",
        },
    )
    if not selected:
        publish_stage = CandidateStageDecision(
            stage_id="publish",
            stage_order=6,
            status=STAGE_SKIP,
            metadata={"selected": False},
        )
    elif published:
        publish_stage = CandidateStageDecision(
            stage_id="publish",
            stage_order=6,
            status=STAGE_PASS,
            reason_codes=(GATE_OK,),
            metadata={"selected": True, "published": True, "evidence": "published pairlist"},
        )
    else:
        publish_stage = CandidateStageDecision(
            stage_id="publish",
            stage_order=6,
            status=STAGE_FAIL,
            reason_codes=("PUBLISH_BLOCKED",),
            metadata={"selected": True, "published": False, "evidence": "published pairlist"},
        )

    if selected and published:
        final_codes: tuple[str, ...] = (GATE_OK,)
    elif insufficiency:
        final_codes = insufficiency
    else:
        final_codes = (REASON_OUTSIDE_TARGET_FINAL_PAIRS,)

    return CandidateExplanationRecord(
        schema_version=EXPLAINABILITY_SCHEMA_VERSION,
        run_id=run_id,
        completed_at=completed_at,
        pair=pair,
        stages=(universe_stage, data_quality_stage, liquidity_stage, rs_stage, ranking_stage, publish_stage),
        score_components={
            "rs_score": rs,
            "oi_score": oi,
            "liquidity_score": entry.get("liquidity_score"),
            "data_quality_pct": entry.get("data_quality_pct"),
        },
        final_score=None,
        final_rank=rank,
        eligible_candidate_count=eligible_count,
        target_final_pairs=None,
        selected=selected,
        published=published,
        final_reason_codes=final_codes,
        provenance_type=PROVENANCE_RECONSTRUCTED,
        source_run_id=source_run_id,
    )


def import_legacy_run(
    explainability_dir: Path,
    *,
    pairlist_path: Path,
    audit_path: Path | None = None,
    notes: str = "",
) -> LegacyImportResult:
    """Import a pre-SPEC-078 published run into the explainability store.

    Args:
        explainability_dir: Explainability artifact root.
        pairlist_path: The *actual* published ``hunter-pairs.json`` (required).
        audit_path: The matching ``hunter-pairs-audit.json`` (optional; without
            it the run is imported as decision-records-incomplete and lookups
            fail closed with ``LEGACY_RUN_INCOMPLETE``).
        notes: Extra operator notes appended to ``reconstruction_notes``.

    Returns:
        A :class:`LegacyImportResult` describing the imported run and whether
        the latest-run pointer advanced.
    """
    pairlist_path = Path(pairlist_path)
    pairlist_payload = _load_json(pairlist_path, "pairlist")
    published_pairs = frozenset(_validate_pairlist(pairlist_payload, pairlist_path))

    source_paths = [str(pairlist_path)]
    audit: dict[str, Any] | None = None
    if audit_path is not None:
        audit_path = Path(audit_path)
        audit = _validate_audit(_load_json(audit_path, "audit"), audit_path)
        source_paths.append(str(audit_path))

    completed_at = datetime.now(timezone.utc).isoformat()
    gaps: list[str] = []
    if audit is None:
        gaps.append("no audit artifact: decision records incomplete")
    else:
        gaps.append("data-quality values not recorded in legacy audit")
        gaps.append("exact target_final_pairs threshold not recorded in legacy audit")
    reconstruction_notes = "; ".join(gaps + ([notes] if notes else []))

    if audit is not None:
        as_of_date = str(audit["as_of_date"])
        entries = _audit_entries(audit)
        eligible_pairs = tuple(sorted(e["pair"] for e in entries))
        selected_count = sum(1 for e in entries if e.get("selected"))
        universe_total = audit.get("universe_total")
        if not isinstance(universe_total, int):
            universe_total = None
            gaps_note = "universe_total not recorded"
            reconstruction_notes += f"; {gaps_note}"
        audit_selected = frozenset(e["pair"] for e in entries if e.get("selected"))
        if audit_selected != published_pairs:
            raise LegacyImportError(
                "audit selected set does not match the published pairlist: "
                f"audit-only={sorted(audit_selected - published_pairs)}, "
                f"pairlist-only={sorted(published_pairs - audit_selected)}"
            )
        run_id = _legacy_run_id(as_of_date, audit, tuple(sorted(published_pairs)))
        records = tuple(
            _build_legacy_record(
                entry,
                run_id=run_id,
                completed_at=completed_at,
                published_pairs=published_pairs,
                universe_total=universe_total,
                eligible_count=len(entries),
                source_run_id=run_id,
            )
            for entry in entries
        )
        manifest = ExplainabilityRunManifest(
            schema_version=EXPLAINABILITY_SCHEMA_VERSION,
            run_id=run_id,
            completed_at=completed_at,
            as_of_date=as_of_date,
            ranking_profile=str(audit.get("ranking_profile") or "UNKNOWN"),
            universe_total=universe_total,
            eligible_count=len(entries),
            selected_count=selected_count,
            target_final_pairs=None,
            min_pairs=None,
            max_pairs=None,
            gate_allowed=True,
            gate_reason_codes=(GATE_OK,),
            published=True,
            eligible_pairs=eligible_pairs,
            provenance_type=PROVENANCE_RECONSTRUCTED,
            source_run_id=run_id,
            source_artifact_paths=tuple(source_paths),
            reconstruction_notes=reconstruction_notes,
            decision_records_complete=True,
        )
    else:
        as_of_date = "UNKNOWN"
        run_id = _legacy_run_id(as_of_date, None, tuple(sorted(published_pairs)))
        records = ()
        manifest = ExplainabilityRunManifest(
            schema_version=EXPLAINABILITY_SCHEMA_VERSION,
            run_id=run_id,
            completed_at=completed_at,
            as_of_date=as_of_date,
            ranking_profile="UNKNOWN",
            universe_total=None,
            eligible_count=None,
            selected_count=len(published_pairs),
            target_final_pairs=None,
            min_pairs=None,
            max_pairs=None,
            gate_allowed=True,
            gate_reason_codes=(GATE_OK,),
            published=True,
            eligible_pairs=(),
            provenance_type=PROVENANCE_RECONSTRUCTED,
            source_run_id=run_id,
            source_artifact_paths=tuple(source_paths),
            reconstruction_notes=reconstruction_notes,
            decision_records_complete=False,
        )
    advance = should_advance_reconstructed_pointer(
        Path(explainability_dir), new_as_of_date=as_of_date
    )
    write_run(Path(explainability_dir), manifest, records, update_latest=False)
    if advance:
        write_latest_pointer(Path(explainability_dir), manifest)

    return LegacyImportResult(
        run_id=run_id,
        provenance_type=PROVENANCE_RECONSTRUCTED,
        candidate_count=len(records),
        decision_records_complete=manifest.decision_records_complete,
        pointer_advanced=advance,
        source_artifact_paths=tuple(source_paths),
        reconstruction_notes=reconstruction_notes,
    )
