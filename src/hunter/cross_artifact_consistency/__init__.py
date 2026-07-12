"""Public API for the Cross-Artifact Consistency Engine (MVP-47)."""

from .engine import (
    ConsistencyEngineError,
    ForbiddenPhraseLeakageError,
    evaluate_cross_artifact_consistency,
    validate_no_forbidden_modules,
)
from .models import (
    ArtifactRef,
    ArtifactSummary,
    ConsistencyDataQuality,
    ConsistencyFinding,
    ConsistencyReasonCode,
    ConsistencyReport,
    ConsistencyRule,
    ConsistencySafetyFlags,
    ConsistencySeverity,
    ConsistencyState,
    CrossArtifactConsistencyConfig,
    CrossArtifactConsistencyInput,
)

__all__ = [
    "ArtifactRef",
    "ArtifactSummary",
    "ConsistencyDataQuality",
    "ConsistencyEngineError",
    "ConsistencyFinding",
    "ConsistencyReasonCode",
    "ConsistencyReport",
    "ConsistencyRule",
    "ConsistencySafetyFlags",
    "ConsistencySeverity",
    "ConsistencyState",
    "CrossArtifactConsistencyConfig",
    "CrossArtifactConsistencyInput",
    "ForbiddenPhraseLeakageError",
    "evaluate_cross_artifact_consistency",
    "validate_no_forbidden_modules",
]
