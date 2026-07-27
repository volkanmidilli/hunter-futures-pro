"""Human and JSON rendering for SPEC-078 explain lookups.

The human formatter prints only genuinely recorded fields; missing values
are shown as ``UNKNOWN`` (scalar fields) or ``NOT_RECORDED`` (absent
records), never guessed.  The JSON formatter emits the canonical
:class:`CandidateExplanationRecord` payload (inside a small lookup
envelope) -- the same structured model a future read-only dashboard/API
would consume, not a separately constructed representation.
"""

from __future__ import annotations

import json
from typing import Any

from hunter.explainability.models import (
    EXPLAINABILITY_SCHEMA_VERSION,
    CandidateExplanationRecord,
    CandidateStageDecision,
)
from hunter.explainability.service import ExplainLookupResult

UNKNOWN = "UNKNOWN"
NOT_RECORDED = "NOT_RECORDED"


def _bool_text(value: bool | None) -> str:
    if value is None:
        return UNKNOWN
    return "YES" if value else "NO"


def _number_text(value: int | float | None) -> str:
    return UNKNOWN if value is None else str(value)


def _stage_detail(stage: CandidateStageDecision) -> str:
    parts = [f"{key}={value}" for key, value in sorted(stage.metrics.items())]
    parts.extend(f"{key}={value}" for key, value in sorted(stage.thresholds.items()))
    parts.extend(stage.reason_codes)
    return " ".join(parts)


def _record_lines(record: CandidateExplanationRecord) -> list[str]:
    final_rank = UNKNOWN
    if record.final_rank is not None:
        if record.eligible_candidate_count is not None:
            final_rank = f"{record.final_rank} / {record.eligible_candidate_count}"
        else:
            final_rank = str(record.final_rank)
    final_reason = (
        ", ".join(record.final_reason_codes) if record.final_reason_codes else UNKNOWN
    )
    lines = [
        f"{'PAIR':<20}{record.pair}",
        f"{'RUN':<20}{record.run_id}",
        f"{'PROVENANCE':<20}{record.provenance_type}",
        f"{'SELECTED':<20}{_bool_text(record.selected)}",
        f"{'PUBLISHED':<20}{_bool_text(record.published)}",
        f"{'FINAL SCORE':<20}{_number_text(record.final_score)}",
        f"{'FINAL RANK':<20}{final_rank}",
        f"{'TARGET':<20}{_number_text(record.target_final_pairs)}",
        f"{'FINAL REASON':<20}{final_reason}",
        "",
        "STAGES",
    ]
    for stage in record.stages:
        detail = _stage_detail(stage)
        line = f"{stage.stage_order:02d}  {stage.stage_id:<22}{stage.status}"
        if detail:
            line += f"   {detail}"
        lines.append(line)
    return lines


def format_human(result: ExplainLookupResult) -> str:
    """Render the human-readable explanation for a lookup result."""
    if result.record is not None:
        return "\n".join(_record_lines(result.record))

    # Fail-closed states: print only what is genuinely known.
    run_id = result.manifest.run_id if result.manifest is not None else UNKNOWN
    provenance = result.manifest.provenance_type if result.manifest is not None else UNKNOWN
    reason = ", ".join(result.reason_codes) if result.reason_codes else UNKNOWN
    record_state = NOT_RECORDED
    lines = [
        f"{'PAIR':<20}{result.pair}",
        f"{'RUN':<20}{run_id}",
        f"{'PROVENANCE':<20}{provenance}",
        f"{'SELECTED':<20}{record_state}",
        f"{'PUBLISHED':<20}{record_state}",
        f"{'FINAL SCORE':<20}{UNKNOWN}",
        f"{'FINAL RANK':<20}{UNKNOWN}",
        f"{'TARGET':<20}{UNKNOWN}",
        f"{'FINAL REASON':<20}{reason}",
    ]
    return "\n".join(lines)


def lookup_result_to_dict(result: ExplainLookupResult) -> dict[str, Any]:
    """Build the JSON envelope: lookup status plus the canonical record.

    ``record`` is exactly the :class:`CandidateExplanationRecord` dict the
    human output is rendered from; it is ``null`` for fail-closed lookups.
    """
    return {
        "schema_version": EXPLAINABILITY_SCHEMA_VERSION,
        "status": result.status,
        "reason_codes": list(result.reason_codes),
        "pair": result.pair,
        "run_id": result.manifest.run_id if result.manifest is not None else None,
        "provenance_type": (
            result.manifest.provenance_type if result.manifest is not None else None
        ),
        "record": result.record.to_dict() if result.record is not None else None,
    }


def format_json(result: ExplainLookupResult) -> str:
    """Render the lookup result as deterministic JSON."""
    return json.dumps(lookup_result_to_dict(result), indent=2, sort_keys=True) + "\n"
