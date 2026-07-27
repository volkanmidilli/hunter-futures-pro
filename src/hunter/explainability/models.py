"""Canonical immutable models for SPEC-078 Hunter Candidate Explainability.

All models are frozen dataclasses with mapping fields coerced to
:class:`types.MappingProxyType` and code collections coerced to tuples,
following the repository's existing immutable-model conventions.
Serialization is deterministic: ``to_dict`` output is stable for identical
input and is written with ``json.dumps(..., indent=2, sort_keys=True)``.

These models *record* decisions made by the real pairlist pipeline; they
never recompute them.  Missing information is represented explicitly
(``None`` / ``UNKNOWN``), never inferred.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

EXPLAINABILITY_SCHEMA_VERSION = "spec-078-explainability-v1"

# ---------------------------------------------------------------------------
# Stage statuses
# ---------------------------------------------------------------------------

STAGE_PASS = "PASS"
STAGE_FAIL = "FAIL"
STAGE_SKIP = "SKIP"
STAGE_UNKNOWN = "UNKNOWN"

STAGE_STATUSES: frozenset[str] = frozenset(
    {STAGE_PASS, STAGE_FAIL, STAGE_SKIP, STAGE_UNKNOWN}
)

# ---------------------------------------------------------------------------
# Reason codes introduced by SPEC-078
#
# Lookup/decision states the existing pipeline has no code for.  Codes that
# already exist in the pipeline (INSUFFICIENT_EVIDENCE,
# PROFILE_EVIDENCE_INCOMPLETE, BELOW_MIN_PAIRS, ABOVE_MAX_PAIRS, ...) are
# reused verbatim by the recorder and are intentionally NOT redefined here.
# ---------------------------------------------------------------------------

REASON_NO_SUCCESSFUL_RUN = "NO_SUCCESSFUL_RUN"
REASON_NOT_IN_UNIVERSE = "NOT_IN_UNIVERSE"
REASON_NOT_RECORDED = "NOT_RECORDED"
REASON_ARTIFACT_INVALID = "ARTIFACT_INVALID"
REASON_OUTSIDE_TARGET_FINAL_PAIRS = "OUTSIDE_TARGET_FINAL_PAIRS"
REASON_PUBLISH_BLOCKED = "PUBLISH_BLOCKED"

EXPLAINABILITY_REASON_CODES: frozenset[str] = frozenset(
    {
        REASON_NO_SUCCESSFUL_RUN,
        REASON_NOT_IN_UNIVERSE,
        REASON_NOT_RECORDED,
        REASON_ARTIFACT_INVALID,
        REASON_OUTSIDE_TARGET_FINAL_PAIRS,
        REASON_PUBLISH_BLOCKED,
    }
)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ExplainabilityError(Exception):
    """Base error for the explainability package."""


class ExplainabilityModelError(ExplainabilityError):
    """Model construction or deserialization failure."""


class ExplainabilityStorageError(ExplainabilityError):
    """Atomic artifact write or immutability-conflict failure."""


class ExplainabilitySymbolError(ExplainabilityError):
    """Invalid or unsafe CLI symbol input."""


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def _coerce_mapping(value: Mapping[str, Any] | None, field_name: str) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise ExplainabilityModelError(
            f"{field_name} must be a mapping, got {type(value).__name__}"
        )
    return MappingProxyType(dict(value))


def _coerce_codes(value: Sequence[str] | None, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ExplainabilityModelError(
            f"{field_name} must be a sequence of strings, got {type(value).__name__}"
        )
    codes = tuple(value)
    for code in codes:
        if not isinstance(code, str):
            raise ExplainabilityModelError(
                f"{field_name} entries must be strings, got {type(code).__name__}"
            )
    return codes


def _coerce_stages(
    value: Sequence["CandidateStageDecision"] | None,
) -> tuple["CandidateStageDecision", ...]:
    if value is None:
        return ()
    stages = tuple(value)
    for stage in stages:
        if not isinstance(stage, CandidateStageDecision):
            raise ExplainabilityModelError(
                f"stages entries must be CandidateStageDecision, got {type(stage).__name__}"
            )
    orders = [s.stage_order for s in stages]
    if len(set(orders)) != len(orders):
        raise ExplainabilityModelError("stage_order values must be unique")
    return stages


# ---------------------------------------------------------------------------
# Canonical models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateStageDecision:
    """One pipeline stage's recorded decision for one candidate pair.

    ``metrics`` and ``thresholds`` preserve the real observed values and the
    thresholds actually applied by the component that owns the criterion.
    Values must be JSON scalars (``str``/``int``/``float``/``bool``/``None``).
    """

    stage_id: str
    stage_order: int
    status: str
    metrics: Mapping[str, Any] = field(default_factory=dict)
    thresholds: Mapping[str, Any] = field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.stage_id, str) or not self.stage_id:
            raise ExplainabilityModelError("stage_id must be a non-empty string")
        if not isinstance(self.stage_order, int) or isinstance(self.stage_order, bool):
            raise ExplainabilityModelError("stage_order must be an int")
        if self.status not in STAGE_STATUSES:
            raise ExplainabilityModelError(
                f"status must be one of {sorted(STAGE_STATUSES)}, got {self.status!r}"
            )
        object.__setattr__(self, "metrics", _coerce_mapping(self.metrics, "metrics"))
        object.__setattr__(self, "thresholds", _coerce_mapping(self.thresholds, "thresholds"))
        object.__setattr__(self, "reason_codes", _coerce_codes(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "metadata", _coerce_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "stage_order": self.stage_order,
            "status": self.status,
            "metrics": dict(self.metrics),
            "thresholds": dict(self.thresholds),
            "reason_codes": list(self.reason_codes),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CandidateStageDecision":
        if not isinstance(payload, Mapping):
            raise ExplainabilityModelError("stage payload must be a mapping")
        try:
            return cls(
                stage_id=payload["stage_id"],
                stage_order=payload["stage_order"],
                status=payload["status"],
                metrics=payload.get("metrics"),
                thresholds=payload.get("thresholds"),
                reason_codes=payload.get("reason_codes"),
                metadata=payload.get("metadata"),
            )
        except KeyError as exc:
            raise ExplainabilityModelError(f"stage payload missing field: {exc}") from exc
        except TypeError as exc:
            raise ExplainabilityModelError(f"stage payload invalid: {exc}") from exc


@dataclass(frozen=True)
class CandidateExplanationRecord:
    """The canonical per-candidate explanation record for one pipeline run.

    ``final_score`` is ``None`` when the pipeline produced no single
    composite score for the pair (the current pipeline ranks by a
    deterministic compound key, not a composite total) -- the absence is
    recorded, never inferred.
    """

    schema_version: str
    run_id: str
    completed_at: str
    pair: str
    stages: tuple[CandidateStageDecision, ...] = ()
    score_components: Mapping[str, Any] = field(default_factory=dict)
    final_score: float | None = None
    final_rank: int | None = None
    eligible_candidate_count: int | None = None
    target_final_pairs: int | None = None
    selected: bool | None = None
    published: bool | None = None
    final_reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, str) or not self.schema_version:
            raise ExplainabilityModelError("schema_version must be a non-empty string")
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ExplainabilityModelError("run_id must be a non-empty string")
        if not isinstance(self.completed_at, str) or not self.completed_at:
            raise ExplainabilityModelError("completed_at must be a non-empty string")
        if not isinstance(self.pair, str) or not self.pair:
            raise ExplainabilityModelError("pair must be a non-empty string")
        object.__setattr__(self, "stages", _coerce_stages(self.stages))
        object.__setattr__(
            self, "score_components", _coerce_mapping(self.score_components, "score_components")
        )
        if self.final_score is not None and not isinstance(self.final_score, (int, float)):
            raise ExplainabilityModelError("final_score must be a number or None")
        if self.final_score is not None and isinstance(self.final_score, bool):
            raise ExplainabilityModelError("final_score must be a number or None")
        if self.final_rank is not None and (
            not isinstance(self.final_rank, int) or isinstance(self.final_rank, bool)
        ):
            raise ExplainabilityModelError("final_rank must be an int or None")
        if self.selected is not None and not isinstance(self.selected, bool):
            raise ExplainabilityModelError("selected must be a bool or None")
        if self.published is not None and not isinstance(self.published, bool):
            raise ExplainabilityModelError("published must be a bool or None")
        object.__setattr__(
            self, "final_reason_codes", _coerce_codes(self.final_reason_codes, "final_reason_codes")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "completed_at": self.completed_at,
            "pair": self.pair,
            "stages": [stage.to_dict() for stage in self.stages],
            "score_components": dict(self.score_components),
            "final_score": self.final_score,
            "final_rank": self.final_rank,
            "eligible_candidate_count": self.eligible_candidate_count,
            "target_final_pairs": self.target_final_pairs,
            "selected": self.selected,
            "published": self.published,
            "final_reason_codes": list(self.final_reason_codes),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CandidateExplanationRecord":
        if not isinstance(payload, Mapping):
            raise ExplainabilityModelError("record payload must be a mapping")
        try:
            stages_raw = payload["stages"]
            if not isinstance(stages_raw, Sequence) or isinstance(stages_raw, str):
                raise ExplainabilityModelError("stages must be a sequence")
            return cls(
                schema_version=payload["schema_version"],
                run_id=payload["run_id"],
                completed_at=payload["completed_at"],
                pair=payload["pair"],
                stages=tuple(CandidateStageDecision.from_dict(s) for s in stages_raw),
                score_components=payload.get("score_components"),
                final_score=payload.get("final_score"),
                final_rank=payload.get("final_rank"),
                eligible_candidate_count=payload.get("eligible_candidate_count"),
                target_final_pairs=payload.get("target_final_pairs"),
                selected=payload.get("selected"),
                published=payload.get("published"),
                final_reason_codes=payload.get("final_reason_codes"),
            )
        except KeyError as exc:
            raise ExplainabilityModelError(f"record payload missing field: {exc}") from exc
        except TypeError as exc:
            raise ExplainabilityModelError(f"record payload invalid: {exc}") from exc


@dataclass(frozen=True)
class ExplainabilityRunManifest:
    """Manifest for one recorded pipeline run.

    ``gate_allowed``/``published`` describe the run outcome; only runs with
    both True may replace the latest-successful-run pointer.
    ``eligible_pairs`` is the actual candidate universe the pipeline ranked
    (sorted); it lets lookups distinguish ``NOT_IN_UNIVERSE`` from
    ``NOT_RECORDED`` without inferring anything.
    """

    schema_version: str
    run_id: str
    completed_at: str
    as_of_date: str
    ranking_profile: str
    universe_total: int
    eligible_count: int
    selected_count: int
    target_final_pairs: int
    min_pairs: int
    max_pairs: int
    gate_allowed: bool
    gate_reason_codes: tuple[str, ...] = ()
    published: bool = False
    eligible_pairs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("schema_version", "run_id", "completed_at", "as_of_date", "ranking_profile"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ExplainabilityModelError(f"{name} must be a non-empty string")
        for name in (
            "universe_total",
            "eligible_count",
            "selected_count",
            "target_final_pairs",
            "min_pairs",
            "max_pairs",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ExplainabilityModelError(f"{name} must be an int")
        if not isinstance(self.gate_allowed, bool) or not isinstance(self.published, bool):
            raise ExplainabilityModelError("gate_allowed and published must be bools")
        object.__setattr__(
            self, "gate_reason_codes", _coerce_codes(self.gate_reason_codes, "gate_reason_codes")
        )
        object.__setattr__(
            self, "eligible_pairs", _coerce_codes(self.eligible_pairs, "eligible_pairs")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "completed_at": self.completed_at,
            "as_of_date": self.as_of_date,
            "ranking_profile": self.ranking_profile,
            "universe_total": self.universe_total,
            "eligible_count": self.eligible_count,
            "selected_count": self.selected_count,
            "target_final_pairs": self.target_final_pairs,
            "min_pairs": self.min_pairs,
            "max_pairs": self.max_pairs,
            "gate_allowed": self.gate_allowed,
            "gate_reason_codes": list(self.gate_reason_codes),
            "published": self.published,
            "eligible_pairs": list(self.eligible_pairs),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExplainabilityRunManifest":
        if not isinstance(payload, Mapping):
            raise ExplainabilityModelError("manifest payload must be a mapping")
        try:
            return cls(
                schema_version=payload["schema_version"],
                run_id=payload["run_id"],
                completed_at=payload["completed_at"],
                as_of_date=payload["as_of_date"],
                ranking_profile=payload["ranking_profile"],
                universe_total=payload["universe_total"],
                eligible_count=payload["eligible_count"],
                selected_count=payload["selected_count"],
                target_final_pairs=payload["target_final_pairs"],
                min_pairs=payload["min_pairs"],
                max_pairs=payload["max_pairs"],
                gate_allowed=payload["gate_allowed"],
                gate_reason_codes=payload.get("gate_reason_codes"),
                published=payload.get("published", False),
                eligible_pairs=payload.get("eligible_pairs"),
            )
        except KeyError as exc:
            raise ExplainabilityModelError(f"manifest payload missing field: {exc}") from exc
        except TypeError as exc:
            raise ExplainabilityModelError(f"manifest payload invalid: {exc}") from exc
