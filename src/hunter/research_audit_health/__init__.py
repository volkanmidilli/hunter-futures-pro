"""Public API for the Research Audit Aggregate Health Report engine (MVP-48)."""

from .engine import (
    ForbiddenPhraseLeakageError,
    HealthEngineError,
    evaluate_research_audit_health,
    validate_no_forbidden_modules,
)
from .models import (
    HealthArtifactSummary,
    HealthConfig,
    HealthDataQuality,
    HealthFamilyRollup,
    HealthFinding,
    HealthInput,
    HealthReasonCode,
    HealthReport,
    HealthSafetyFlags,
    HealthScore,
    HealthSeverity,
    HealthState,
)
from .writer import (
    ForbiddenPhraseLeakageError as WriterForbiddenPhraseLeakageError,
    HealthWriterError,
    health_report_to_dict,
    health_report_to_json,
    health_report_to_markdown,
    validate_no_forbidden_modules as validate_no_forbidden_writer_modules,
)

__all__ = [
    "HealthArtifactSummary",
    "HealthConfig",
    "HealthDataQuality",
    "HealthEngineError",
    "HealthFamilyRollup",
    "HealthFinding",
    "HealthInput",
    "HealthReasonCode",
    "HealthReport",
    "HealthSafetyFlags",
    "HealthScore",
    "HealthSeverity",
    "HealthState",
    "HealthWriterError",
    "ForbiddenPhraseLeakageError",
    "WriterForbiddenPhraseLeakageError",
    "evaluate_research_audit_health",
    "health_report_to_dict",
    "health_report_to_json",
    "health_report_to_markdown",
    "validate_no_forbidden_modules",
    "validate_no_forbidden_writer_modules",
]
