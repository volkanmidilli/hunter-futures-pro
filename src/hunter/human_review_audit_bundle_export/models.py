"""Frozen dataclasses for hunter.human_review_audit_bundle_export package.

MVP-44 — Local Research Human Review Audit Bundle Export Artifact.

All dataclasses are frozen. Validation runs in __post_init__. The export layer
only accepts caller-provided in-memory bundle reports and explicit local output
and temporary directories. It never opens, follows, traverses, validates,
fetches, or executes upstream reference strings. The planner phase computes a
deterministic export plan without writing files.

Export artifacts are human-audit / research artifacts only. They are not a
production certification, not a trading readiness assessment, not a suitability
assessment, and not a trading signal or recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.human_review_audit_bundle import HumanReviewAuditBundleReport

HUMAN_REVIEW_AUDIT_BUNDLE_EXPORT_VERSION: str = "0.44.0-dev"
EXPORT_KIND: str = "human_review_audit_bundle_export"
MANIFEST_KIND: str = "human_review_audit_bundle_export_manifest"

SAFETY_NOTICE = (
    "This export artifact is a local, audit-only, human-audit research artifact. "
    "It serializes an existing local human-review audit bundle to a caller-controlled "
    "local path for review only and does not imply approval, certification, "
    "production readiness, deployment readiness, trading readiness, recommendation, "
    "suitability assessment, signal validity, task assignment, task completion, or "
    "executable remediation plan."
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HumanReviewAuditBundleExportState(Enum):
    """Aggregate state of an audit bundle export plan or manifest."""

    PLANNED = "planned"
    WRITTEN = "written"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class HumanReviewAuditBundleExportSeverity(Enum):
    """Severity of an export-level issue."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFO = "info"


class HumanReviewAuditBundleExportReasonCode(Enum):
    """Reason codes for audit bundle export plans and manifests."""

    OK = "ok"
    PLANNED = "planned"
    WRITTEN = "written"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"
    UPSTREAM_BLOCKED = "upstream_blocked"
    UPSTREAM_DEGRADED = "upstream_degraded"
    UPSTREAM_NOT_APPLICABLE = "upstream_not_applicable"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    UNSAFE_CONTENT = "unsafe_content"
    PATH_TRAVERSAL_ATTEMPT = "path_traversal_attempt"
    OUTPUT_EXISTS = "output_exists"
    PATH_ERROR = "path_error"
    HASH_MISMATCH = "hash_mismatch"
    WRITE_FAILED = "write_failed"
    INVALID_FORMAT = "invalid_format"
    RESEARCH_ONLY = "research_only"
    HUMAN_AUDIT_ONLY = "human_audit_only"
    NO_EXECUTABLE_ACTIONS = "no_executable_actions"
    NO_TRADING_INSTRUCTIONS = "no_trading_instructions"
    NO_APPROVAL_CLAIMS = "no_approval_claims"
    REFERENCES_OPAQUE = "references_opaque"
    NO_NETWORK = "no_network"
    NO_SERVER = "no_server"
    NO_DATABASE = "no_database"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportConfig:
    """Configuration for the audit bundle export planner."""

    strict: bool = False
    overwrite: bool = False
    format: str = "json"
    safety_scan: bool = True
    verify_hash: bool = True
    dry_run: bool = False

    def __post_init__(self) -> None:
        _ensure_bool(self.strict, "strict")
        _ensure_bool(self.overwrite, "overwrite")
        _ensure_bool(self.safety_scan, "safety_scan")
        _ensure_bool(self.verify_hash, "verify_hash")
        _ensure_bool(self.dry_run, "dry_run")
        _ensure_str_with_default(self.format, "format")


# ---------------------------------------------------------------------------
# Issue / SafetyFlags
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportIssue:
    """An export-level issue: safety, path, writer, or upstream carry-forward."""

    issue_id: str = ""
    issue_type: str = ""
    severity: str = ""
    reason_codes: tuple[str, ...] = ()
    source: str = ""
    title: str = ""
    description: str = ""
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.issue_id, "issue_id")
        _ensure_str_with_default(self.issue_type, "issue_type")
        _ensure_str_with_default(self.severity, "severity")
        _ensure_str_with_default(self.source, "source")
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportSafetyFlags:
    """Safety flags for the audit bundle export plan or manifest."""

    is_safe: bool = True
    audit_only: bool = True
    no_executable_actions: bool = True
    no_trading_instructions: bool = True
    no_approval_claims: bool = True
    references_opaque: bool = True
    no_network: bool = True
    no_server: bool = True
    path_safe: bool = True
    hash_verified: bool = True

    def __post_init__(self) -> None:
        _ensure_bool(self.is_safe, "is_safe")
        _ensure_bool(self.audit_only, "audit_only")
        _ensure_bool(self.no_executable_actions, "no_executable_actions")
        _ensure_bool(self.no_trading_instructions, "no_trading_instructions")
        _ensure_bool(self.no_approval_claims, "no_approval_claims")
        _ensure_bool(self.references_opaque, "references_opaque")
        _ensure_bool(self.no_network, "no_network")
        _ensure_bool(self.no_server, "no_server")
        _ensure_bool(self.path_safe, "path_safe")
        _ensure_bool(self.hash_verified, "hash_verified")


# ---------------------------------------------------------------------------
# Input / Plan / Manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportInput:
    """Input for the audit bundle export planner."""

    bundle_report: HumanReviewAuditBundleReport
    output_dir: Path | str
    tmp_path: Path | str
    config: HumanReviewAuditBundleExportConfig = field(default_factory=HumanReviewAuditBundleExportConfig)
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.bundle_report, HumanReviewAuditBundleReport):
            raise TypeError("bundle_report must be a HumanReviewAuditBundleReport")
        if not isinstance(self.output_dir, (str, Path)):
            raise TypeError("output_dir must be a string or Path")
        if not isinstance(self.tmp_path, (str, Path)):
            raise TypeError("tmp_path must be a string or Path")
        if not isinstance(self.config, HumanReviewAuditBundleExportConfig):
            raise TypeError("config must be a HumanReviewAuditBundleExportConfig")
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        object.__setattr__(self, "tmp_path", Path(self.tmp_path))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportPlan:
    """A deterministic, file-write-free export plan."""

    plan_id: str = ""
    report_id: str = ""
    bundle_report_id: str = ""
    filename: str = ""
    output_path: str = ""
    tmp_path: str = ""
    format: str = ""
    content_hash: str = ""
    content_length: int = 0
    generated_at: datetime | None = None
    state: HumanReviewAuditBundleExportState = HumanReviewAuditBundleExportState.PLANNED
    safety_flags: HumanReviewAuditBundleExportSafetyFlags = field(
        default_factory=HumanReviewAuditBundleExportSafetyFlags
    )
    reason_codes: tuple[HumanReviewAuditBundleExportReasonCode, ...] = ()
    issues: tuple[HumanReviewAuditBundleExportIssue, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.plan_id, "plan_id")
        _ensure_str_with_default(self.report_id, "report_id")
        _ensure_str_with_default(self.bundle_report_id, "bundle_report_id")
        _ensure_str_with_default(self.filename, "filename")
        _ensure_str_with_default(self.output_path, "output_path")
        _ensure_str_with_default(self.tmp_path, "tmp_path")
        _ensure_str_with_default(self.format, "format")
        _ensure_str_with_default(self.content_hash, "content_hash")
        _ensure_non_negative_int(self.content_length, "content_length")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.state, HumanReviewAuditBundleExportState):
            raise TypeError("state must be a HumanReviewAuditBundleExportState")
        if not isinstance(self.safety_flags, HumanReviewAuditBundleExportSafetyFlags):
            raise TypeError("safety_flags must be a HumanReviewAuditBundleExportSafetyFlags")
        object.__setattr__(
            self, "reason_codes", _ensure_tuple_of_items(self.reason_codes, HumanReviewAuditBundleExportReasonCode, "reason_codes")
        )
        object.__setattr__(
            self, "issues", _ensure_tuple_of_items(self.issues, HumanReviewAuditBundleExportIssue, "issues")
        )
        _ensure_str_with_default(self.notes, "notes")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleExportManifest:
    """A completed export manifest, possibly in a non-WRITTEN state."""

    manifest_id: str = ""
    report_id: str = ""
    bundle_report_id: str = ""
    filename: str = ""
    output_path: str = ""
    format: str = ""
    content_hash: str = ""
    content_length: int = 0
    state: HumanReviewAuditBundleExportState = HumanReviewAuditBundleExportState.PLANNED
    safety_flags: HumanReviewAuditBundleExportSafetyFlags = field(
        default_factory=HumanReviewAuditBundleExportSafetyFlags
    )
    reason_codes: tuple[HumanReviewAuditBundleExportReasonCode, ...] = ()
    issues: tuple[HumanReviewAuditBundleExportIssue, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.manifest_id, "manifest_id")
        _ensure_str_with_default(self.report_id, "report_id")
        _ensure_str_with_default(self.bundle_report_id, "bundle_report_id")
        _ensure_str_with_default(self.filename, "filename")
        _ensure_str_with_default(self.output_path, "output_path")
        _ensure_str_with_default(self.format, "format")
        _ensure_str_with_default(self.content_hash, "content_hash")
        _ensure_non_negative_int(self.content_length, "content_length")
        if not isinstance(self.state, HumanReviewAuditBundleExportState):
            raise TypeError("state must be a HumanReviewAuditBundleExportState")
        if not isinstance(self.safety_flags, HumanReviewAuditBundleExportSafetyFlags):
            raise TypeError("safety_flags must be a HumanReviewAuditBundleExportSafetyFlags")
        object.__setattr__(
            self, "reason_codes", _ensure_tuple_of_items(self.reason_codes, HumanReviewAuditBundleExportReasonCode, "reason_codes")
        )
        object.__setattr__(
            self, "issues", _ensure_tuple_of_items(self.issues, HumanReviewAuditBundleExportIssue, "issues")
        )
        _ensure_str_with_default(self.notes, "notes")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _ensure_bool(value: Any, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool")


def _ensure_str_with_default(value: Any, name: str) -> None:
    if value is None:
        raise ValueError(f"{name} must be a string")
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")


def _ensure_non_negative_int(value: Any, name: str) -> None:
    if not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _ensure_tuple_of_items(value: Any, item_type: type, name: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, item_type):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(value)
    raise TypeError(f"{name} must be an iterable of {item_type.__name__}")


def _ensure_tuple_of_str(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(x) for x in value)


def _coerce_str_mapping(value: Any) -> Mapping[str, str]:
    if value is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in dict(value).items()})


def _ensure_timezone_aware(value: datetime | None, name: str) -> None:
    if value is None:
        return
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
