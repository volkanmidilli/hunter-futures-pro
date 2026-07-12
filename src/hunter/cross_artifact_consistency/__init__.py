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
from .writer import (
    ConsistencyWriterError,
    ForbiddenPhraseLeakageError as WriterForbiddenPhraseLeakageError,
    consistency_report_to_dict,
    consistency_report_to_json,
    consistency_report_to_markdown,
    validate_no_forbidden_modules as validate_no_forbidden_writer_modules,
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
    "ConsistencyWriterError",
    "CrossArtifactConsistencyConfig",
    "CrossArtifactConsistencyInput",
    "ForbiddenPhraseLeakageError",
    "WriterForbiddenPhraseLeakageError",
    "consistency_report_to_dict",
    "consistency_report_to_json",
    "consistency_report_to_markdown",
    "evaluate_cross_artifact_consistency",
    "validate_no_forbidden_modules",
    "validate_no_forbidden_writer_modules",
]
