"""Pure data models for hunter.human_review_audit_bundle_export_verification.

MVP-45 Step 1 — Local, audit-only, read-only verification/replay of MVP-44 audit
bundle export artifacts. All models are frozen dataclasses with no I/O, no
network, and no trading semantics.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from hunter.human_review_audit_bundle_export.models import (
    HumanReviewAuditBundleExportManifest,
)

HUMAN_REVIEW_AUDIT_BUNDLE_EXPORT_VERIFICATION_VERSION: str = "0.45.0-dev"
VERIFICATION_KIND: str = "human_review_audit_bundle_export_verification"
SAFETY_NOTICE = (
    "This verification report is a local, audit-only, human-audit research artifact. "
    "It verifies caller-provided bytes against caller-provided manifest metadata only. "
    "It does not imply approval, certification, production readiness, deployment readiness, "
    "trading readiness, recommendation, suitability assessment, signal validity, "
    "task assignment, task completion, or executable remediation plan."
)


# ---------------------------------------------------------------------------
# Validation helpers (defined before dataclasses so they can be referenced)
# ---------------------------------------------------------------------------


def _ensure_bool(value: Any, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool, got {type(value).__name__}")


def _ensure_str(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str, got {type(value).__name__}")


def _ensure_non_negative_int(value: Any, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TypeError(f"{name} must be a non-negative int, got {value!r}")


def _ensure_tuple_of_str(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    return tuple(str(item) for item in value)


def _ensure_mapping_str_str(value: Any, name: str) -> Mapping[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a Mapping[str, str], got {type(value).__name__}")
    return {str(k): str(v) for k, v in value.items()}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HumanReviewAuditBundleExportVerificationState(Enum):
    """Aggregate state of a verification report."""

    VERIFIED = "verified"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"
    INVALID = "invalid"
    DEGRADED = "degraded"


class HumanReviewAuditBundleExportVerificationSeverity(Enum):
    """Severity of a verification issue."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFO = "info"


class HumanReviewAuditBundleExportVerificationReasonCode(Enum):
    """Reason codes for verification issues and report state."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    HASH_MISMATCH = "hash_mismatch"
    LENGTH_MISMATCH = "length_mismatch"
    STATE_NOT_VERIFIABLE = "state_not_verifiable"
    MISSING_MANIFEST_METADATA = "missing_manifest_metadata"
    UNSUPPORTED_FORMAT = "unsupported_format"
    SAFETY_NOTICE_MISSING = "safety_notice_missing"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    UPSTREAM_BLOCKED = "upstream_blocked"
    UPSTREAM_NOT_APPLICABLE = "upstream_not_applicable"
    UPSTREAM_PLANNED = "upstream_planned"
    TEXT_HASH_MISMATCH = "text_hash_mismatch"


# ---------------------------------------------------------------------------
# Dataclasses with inline validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportVerificationConfig:
    """Pure local configuration for verification.

    All fields are caller-provided; no environment, network, or filesystem values
    are consulted.
    """

    strict: bool = False
    require_safety_notice: bool = True
    verify_text_hash: bool = False
    allow_not_applicable: bool = True

    def __post_init__(self) -> None:
        _ensure_bool(self.strict, "strict")
        _ensure_bool(self.require_safety_notice, "require_safety_notice")
        _ensure_bool(self.verify_text_hash, "verify_text_hash")
        _ensure_bool(self.allow_not_applicable, "allow_not_applicable")


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportVerificationIssue:
    """A single verification issue."""

    issue_id: str = ""
    issue_type: str = ""
    severity: str = ""
    reason_codes: tuple[str, ...] = ()
    source: str = ""
    title: str = ""
    description: str = ""
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        _ensure_str(self.issue_id, "issue_id")
        _ensure_str(self.issue_type, "issue_type")
        _ensure_str(self.severity, "severity")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        _ensure_str(self.source, "source")
        _ensure_str(self.title, "title")
        _ensure_str(self.description, "description")


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportVerificationDataQuality:
    """Counters for verification checks and issue distributions."""

    checks_performed: int = 0
    hash_mismatch_count: int = 0
    length_mismatch_count: int = 0
    state_not_verifiable_count: int = 0
    missing_safety_notice_count: int = 0
    forbidden_term_count: int = 0
    blocking_issues: int = 0
    advisory_issues: int = 0
    info_findings: int = 0

    def __post_init__(self) -> None:
        _ensure_non_negative_int(self.checks_performed, "checks_performed")
        _ensure_non_negative_int(self.hash_mismatch_count, "hash_mismatch_count")
        _ensure_non_negative_int(self.length_mismatch_count, "length_mismatch_count")
        _ensure_non_negative_int(self.state_not_verifiable_count, "state_not_verifiable_count")
        _ensure_non_negative_int(self.missing_safety_notice_count, "missing_safety_notice_count")
        _ensure_non_negative_int(self.forbidden_term_count, "forbidden_term_count")
        _ensure_non_negative_int(self.blocking_issues, "blocking_issues")
        _ensure_non_negative_int(self.advisory_issues, "advisory_issues")
        _ensure_non_negative_int(self.info_findings, "info_findings")


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportVerificationSafetyFlags:
    """Safety flags for the verification report."""

    is_safe: bool = True
    audit_only: bool = True
    no_executable_actions: bool = True
    no_trading_instructions: bool = True
    no_approval_claims: bool = True
    references_opaque: bool = True
    no_network: bool = True
    no_server: bool = True
    hash_verified: bool = False
    length_verified: bool = False
    state_verifiable: bool = False
    safety_notice_present: bool = False

    def __post_init__(self) -> None:
        _ensure_bool(self.is_safe, "is_safe")
        _ensure_bool(self.audit_only, "audit_only")
        _ensure_bool(self.no_executable_actions, "no_executable_actions")
        _ensure_bool(self.no_trading_instructions, "no_trading_instructions")
        _ensure_bool(self.no_approval_claims, "no_approval_claims")
        _ensure_bool(self.references_opaque, "references_opaque")
        _ensure_bool(self.no_network, "no_network")
        _ensure_bool(self.no_server, "no_server")
        _ensure_bool(self.hash_verified, "hash_verified")
        _ensure_bool(self.length_verified, "length_verified")
        _ensure_bool(self.state_verifiable, "state_verifiable")
        _ensure_bool(self.safety_notice_present, "safety_notice_present")


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportVerificationInput:
    """Input for the verification engine.

    The manifest and artifact_bytes are caller-provided; the engine performs no
    I/O to obtain them. expected_format is an optional caller hint used only for
    advisory format classification.
    """

    manifest: HumanReviewAuditBundleExportManifest
    artifact_bytes: bytes = b""
    expected_format: str = ""
    config: HumanReviewAuditBundleExportVerificationConfig = field(
        default_factory=HumanReviewAuditBundleExportVerificationConfig
    )
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, HumanReviewAuditBundleExportManifest):
            raise TypeError(
                f"manifest must be a HumanReviewAuditBundleExportManifest, got {type(self.manifest).__name__}"
            )
        if not isinstance(self.artifact_bytes, bytes):
            raise TypeError(
                f"artifact_bytes must be bytes, got {type(self.artifact_bytes).__name__}"
            )
        _ensure_str(self.expected_format, "expected_format")
        if not isinstance(self.config, HumanReviewAuditBundleExportVerificationConfig):
            raise TypeError(
                f"config must be a HumanReviewAuditBundleExportVerificationConfig, got {type(self.config).__name__}"
            )
        object.__setattr__(self, "metadata", _ensure_mapping_str_str(self.metadata, "metadata"))


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportVerificationReport:
    """Result of a verification run.

    The report contains no raw artifact bytes and no resolved filesystem paths.
    All IDs and refs are opaque strings.
    """

    verification_id: str = ""
    report_id: str = ""
    manifest_id: str = ""
    bundle_report_id: str = ""
    generated_at: datetime | None = None
    state: HumanReviewAuditBundleExportVerificationState = (
        HumanReviewAuditBundleExportVerificationState.INVALID
    )
    config: HumanReviewAuditBundleExportVerificationConfig = field(
        default_factory=HumanReviewAuditBundleExportVerificationConfig
    )
    input_summary: Mapping[str, str] = field(default_factory=dict)
    data_quality: HumanReviewAuditBundleExportVerificationDataQuality = field(
        default_factory=HumanReviewAuditBundleExportVerificationDataQuality
    )
    safety_flags: HumanReviewAuditBundleExportVerificationSafetyFlags = field(
        default_factory=HumanReviewAuditBundleExportVerificationSafetyFlags
    )
    reason_codes: tuple[HumanReviewAuditBundleExportVerificationReasonCode, ...] = ()
    issues: tuple[HumanReviewAuditBundleExportVerificationIssue, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        _ensure_str(self.verification_id, "verification_id")
        _ensure_str(self.report_id, "report_id")
        _ensure_str(self.manifest_id, "manifest_id")
        _ensure_str(self.bundle_report_id, "bundle_report_id")
        if not isinstance(self.state, HumanReviewAuditBundleExportVerificationState):
            raise TypeError("state must be a HumanReviewAuditBundleExportVerificationState")
        if not isinstance(self.config, HumanReviewAuditBundleExportVerificationConfig):
            raise TypeError("config must be a HumanReviewAuditBundleExportVerificationConfig")
        object.__setattr__(self, "input_summary", _ensure_mapping_str_str(self.input_summary, "input_summary"))
        if not isinstance(self.data_quality, HumanReviewAuditBundleExportVerificationDataQuality):
            raise TypeError("data_quality must be a HumanReviewAuditBundleExportVerificationDataQuality")
        if not isinstance(self.safety_flags, HumanReviewAuditBundleExportVerificationSafetyFlags):
            raise TypeError("safety_flags must be a HumanReviewAuditBundleExportVerificationSafetyFlags")
        if not isinstance(self.issues, tuple):
            object.__setattr__(self, "issues", tuple(self.issues))
        _ensure_str(self.notes, "notes")
        object.__setattr__(self, "metadata", _ensure_mapping_str_str(self.metadata, "metadata"))
