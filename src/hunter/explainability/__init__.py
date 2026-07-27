"""Hunter Candidate Explainability (SPEC-078).

Records, per candidate pair, the real stage decisions of the pairlist
selection pipeline (universe membership, data-quality evidence, liquidity
evidence, relative-strength evidence, ranking cutoff, publish gate) so the
``hunter explain <SYMBOL>`` CLI can answer *why* a pair was or was not
selected without recomputing any selection decision.

Explainability is an auxiliary recording layer: it never changes candidate
eligibility, scores, ranking, pair ordering, selected pairs, published
pairs, existing output artifacts, or research behavior.
"""

from hunter.explainability.models import (
    EXPLAINABILITY_REASON_CODES,
    EXPLAINABILITY_SCHEMA_VERSION,
    PROVENANCE_ORIGINAL,
    PROVENANCE_RECONSTRUCTED,
    PROVENANCE_TYPES,
    REASON_ARTIFACT_INVALID,
    REASON_LEGACY_RUN_INCOMPLETE,
    REASON_NO_SUCCESSFUL_RUN,
    REASON_NOT_IN_UNIVERSE,
    REASON_NOT_RECORDED,
    REASON_OUTSIDE_TARGET_FINAL_PAIRS,
    REASON_PUBLISH_BLOCKED,
    STAGE_FAIL,
    STAGE_PASS,
    STAGE_SKIP,
    STAGE_UNKNOWN,
    CandidateExplanationRecord,
    CandidateStageDecision,
    ExplainabilityError,
    ExplainabilityModelError,
    ExplainabilityStorageError,
    ExplainabilitySymbolError,
    ExplainabilityRunManifest,
)

__all__ = [
    "EXPLAINABILITY_REASON_CODES",
    "EXPLAINABILITY_SCHEMA_VERSION",
    "PROVENANCE_ORIGINAL",
    "PROVENANCE_RECONSTRUCTED",
    "PROVENANCE_TYPES",
    "REASON_ARTIFACT_INVALID",
    "REASON_LEGACY_RUN_INCOMPLETE",
    "REASON_NO_SUCCESSFUL_RUN",
    "REASON_NOT_IN_UNIVERSE",
    "REASON_NOT_RECORDED",
    "REASON_OUTSIDE_TARGET_FINAL_PAIRS",
    "REASON_PUBLISH_BLOCKED",
    "STAGE_FAIL",
    "STAGE_PASS",
    "STAGE_SKIP",
    "STAGE_UNKNOWN",
    "CandidateExplanationRecord",
    "CandidateStageDecision",
    "ExplainabilityError",
    "ExplainabilityModelError",
    "ExplainabilityStorageError",
    "ExplainabilitySymbolError",
    "ExplainabilityRunManifest",
]
