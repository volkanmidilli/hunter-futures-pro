"""Models for the Governance Handoff Package Builder (MVP-62).

The builder consumes a ``GovernanceDecisionSummary`` (MVP-61), a
``ResearchDecisionGateReport`` (MVP-59), and the latest accepted
``HumanReviewRecord`` (MVP-60), and produces one immutable, research-only
``ResearchGovernanceHandoffPackage``. It never authorizes execution, production
deployment, or trading, and does not integrate with Freqtrade runtime,
exchanges, databases, schedulers, or live trading systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping

GOVERNANCE_HANDOFF_VERSION: str = "0.62.0-dev"

# Governance statuses (from upstream GovernanceDecisionSummary)
READY_FOR_RESEARCH_HANDOFF: Literal["READY_FOR_RESEARCH_HANDOFF"] = "READY_FOR_RESEARCH_HANDOFF"
REVIEW_REQUIRED: Literal["REVIEW_REQUIRED"] = "REVIEW_REQUIRED"
BLOCKED: Literal["BLOCKED"] = "BLOCKED"

GOVERNANCE_STATUSES: frozenset[str] = frozenset(
    {READY_FOR_RESEARCH_HANDOFF, REVIEW_REQUIRED, BLOCKED}
)

# Blocking reason codes
MISSING_GOVERNANCE_SUMMARY = "MISSING_GOVERNANCE_SUMMARY"
MISSING_GATE_REPORT = "MISSING_GATE_REPORT"
MISSING_LATEST_ACCEPTED_REVIEW = "MISSING_LATEST_ACCEPTED_REVIEW"
INVALID_GOVERNANCE_SUMMARY = "INVALID_GOVERNANCE_SUMMARY"
INVALID_GATE_REPORT = "INVALID_GATE_REPORT"
INVALID_REVIEW_RECORD = "INVALID_REVIEW_RECORD"
GOVERNANCE_FINGERPRINT_MISMATCH = "GOVERNANCE_FINGERPRINT_MISMATCH"
GATE_FINGERPRINT_MISMATCH = "GATE_FINGERPRINT_MISMATCH"
REVIEW_FINGERPRINT_MISMATCH = "REVIEW_FINGERPRINT_MISMATCH"
SOURCE_VERSION_MISMATCH = "SOURCE_VERSION_MISMATCH"
CONTRADICTORY_HANDOFF_STATE = "CONTRADICTORY_HANDOFF_STATE"
MISSING_REQUIRED_FINGERPRINT = "MISSING_REQUIRED_FINGERPRINT"
UNSAFE_HANDOFF_FLAG = "UNSAFE_HANDOFF_FLAG"
INVALID_TIMESTAMP = "INVALID_TIMESTAMP"

# Review-required reason codes
GOVERNANCE_REVIEW_REQUIRED = "GOVERNANCE_REVIEW_REQUIRED"
INCOMPLETE_PROVENANCE = "INCOMPLETE_PROVENANCE"
UNKNOWN_NON_BLOCKING_FIELD = "UNKNOWN_NON_BLOCKING_FIELD"
MISSING_OPTIONAL_METADATA = "MISSING_OPTIONAL_METADATA"

# Ready marker
HANDOFF_PACKAGE_READY = "HANDOFF_PACKAGE_READY"

HANDOFF_BLOCKING_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_GOVERNANCE_SUMMARY,
        MISSING_GATE_REPORT,
        MISSING_LATEST_ACCEPTED_REVIEW,
        INVALID_GOVERNANCE_SUMMARY,
        INVALID_GATE_REPORT,
        INVALID_REVIEW_RECORD,
        GOVERNANCE_FINGERPRINT_MISMATCH,
        GATE_FINGERPRINT_MISMATCH,
        REVIEW_FINGERPRINT_MISMATCH,
        SOURCE_VERSION_MISMATCH,
        CONTRADICTORY_HANDOFF_STATE,
        MISSING_REQUIRED_FINGERPRINT,
        UNSAFE_HANDOFF_FLAG,
        INVALID_TIMESTAMP,
    }
)

HANDOFF_REVIEW_REQUIRED_REASON_CODES: frozenset[str] = frozenset(
    {
        GOVERNANCE_REVIEW_REQUIRED,
        INCOMPLETE_PROVENANCE,
        UNKNOWN_NON_BLOCKING_FIELD,
        MISSING_OPTIONAL_METADATA,
    }
)

HANDOFF_REASON_CODES: frozenset[str] = (
    HANDOFF_BLOCKING_REASON_CODES | HANDOFF_REVIEW_REQUIRED_REASON_CODES
)

DEFAULT_REQUIRE_LATEST_ACCEPTED_REVIEW: bool = True
DEFAULT_OUTPUT_DIR: Path = Path("data/governance_handoff")
DEFAULT_REPORT_OUTPUT_DIR: Path = Path("reports/governance_handoff")
DEFAULT_JSON_FILENAME: str = "latest_handoff_package.json"
DEFAULT_MARKDOWN_FILENAME: str = "latest_handoff_package.md"

CANONICAL_SAFETY_FLAGS: Mapping[str, bool] = MappingProxyType(
    {
        "research_only": True,
        "execution_approval_granted": False,
        "production_approval_granted": False,
        "live_trading_allowed": False,
        "automatic_execution_allowed": False,
    }
)


class GovernanceHandoffError(Exception):
    """Base exception for the governance handoff package builder."""

    def __init__(self, *args: Any, reason_code: str | None = None) -> None:
        super().__init__(*args)
        self.reason_code = reason_code


def _coerce_json_value(value: Any) -> Any:
    """Recursively copy a JSON-compatible value.

    Allowed scalar types: ``str``, ``bool``, ``int``, ``float``, ``None``.
    Allowed containers: ``list``, ``tuple``, ``dict`` and other ``Mapping`` values.
    Other types are rejected with ``TypeError``.
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_coerce_json_value(item) for item in value]
    if isinstance(value, (dict, Mapping)):
        return {str(k): _coerce_json_value(v) for k, v in value.items()}
    raise TypeError(f"value is not JSON-compatible: {value!r}")


def _coerce_json_mapping(
    value: Mapping[str, object] | dict[str, object] | None,
) -> Mapping[str, object]:
    """Coerce a mapping to an immutable deep copy with JSON-compatible values."""
    if value is None:
        return MappingProxyType({})
    coerced = {str(k): _coerce_json_value(v) for k, v in value.items()}
    return MappingProxyType(coerced)


def _validate_non_empty_string(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")


@dataclass(frozen=True)
class GovernanceHandoffConfig:
    """Configuration for the governance handoff package builder."""

    require_latest_accepted_review: bool = DEFAULT_REQUIRE_LATEST_ACCEPTED_REVIEW
    output_dir: Path = DEFAULT_OUTPUT_DIR
    report_output_dir: Path = DEFAULT_REPORT_OUTPUT_DIR
    json_filename: str = DEFAULT_JSON_FILENAME
    markdown_filename: str = DEFAULT_MARKDOWN_FILENAME
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.require_latest_accepted_review, bool):
            raise ValueError(
                "require_latest_accepted_review must be a bool, "
                f"got {self.require_latest_accepted_review!r}"
            )
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(str(self.output_dir)))
        if not isinstance(self.report_output_dir, Path):
            object.__setattr__(
                self, "report_output_dir", Path(str(self.report_output_dir))
            )
        _validate_non_empty_string("json_filename", self.json_filename)
        _validate_non_empty_string("markdown_filename", self.markdown_filename)
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))

    @classmethod
    def default(cls) -> "GovernanceHandoffConfig":
        """Return the default governance handoff configuration."""
        return cls()


@dataclass(frozen=True)
class HandoffSourceReference:
    """Reference to an upstream source included in a handoff package."""

    source_name: str
    source_version: str
    fingerprint: str
    accepted: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string("source_name", self.source_name)
        _validate_non_empty_string("source_version", self.source_version)
        _validate_non_empty_string("fingerprint", self.fingerprint)
        if not isinstance(self.accepted, bool):
            raise ValueError(f"accepted must be a bool, got {self.accepted!r}")
        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(
                self, "reason_codes", tuple(str(c) for c in self.reason_codes)
            )


@dataclass(frozen=True)
class ResearchGovernanceHandoffManifest:
    """Manifest describing the contents and provenance of a handoff package."""

    package_version: str
    package_fingerprint: str
    built_at: datetime
    governance_fingerprint: str
    gate_fingerprint: str
    review_record_fingerprint: str | None
    source_versions: Mapping[str, str]
    artifact_filenames: Mapping[str, str]
    safety_flags: Mapping[str, bool]

    def __post_init__(self) -> None:
        _validate_non_empty_string("package_version", self.package_version)
        _validate_non_empty_string("package_fingerprint", self.package_fingerprint)
        _validate_non_empty_string("governance_fingerprint", self.governance_fingerprint)
        _validate_non_empty_string("gate_fingerprint", self.gate_fingerprint)
        if self.review_record_fingerprint is not None:
            _validate_non_empty_string(
                "review_record_fingerprint", self.review_record_fingerprint
            )
        if not isinstance(self.built_at, datetime) or self.built_at.tzinfo is None:
            raise ValueError(
                "built_at must be a timezone-aware datetime, "
                f"got {self.built_at!r}"
            )
        if not isinstance(self.source_versions, Mapping):
            raise ValueError(
                f"source_versions must be a Mapping, got {self.source_versions!r}"
            )
        if not isinstance(self.artifact_filenames, Mapping):
            raise ValueError(
                f"artifact_filenames must be a Mapping, got {self.artifact_filenames!r}"
            )
        if not isinstance(self.safety_flags, Mapping):
            raise ValueError(
                f"safety_flags must be a Mapping, got {self.safety_flags!r}"
            )


@dataclass(frozen=True)
class ResearchGovernanceHandoffPackage:
    """Immutable, deterministic governance handoff package.

    ``handoff_allowed`` is ``True`` only when the governance status is
    ``READY_FOR_RESEARCH_HANDOFF``, provenance is valid, and no blocking or
    review-required reasons are present. It never authorizes execution,
    production deployment, or trading.
    """

    version: str
    package_fingerprint: str
    built_at: datetime
    governance_status: Literal[
        "READY_FOR_RESEARCH_HANDOFF",
        "REVIEW_REQUIRED",
        "BLOCKED",
    ]
    handoff_allowed: bool
    governance_source: HandoffSourceReference
    gate_source: HandoffSourceReference
    review_source: HandoffSourceReference | None
    blocking_reason_codes: tuple[str, ...]
    review_reason_codes: tuple[str, ...]
    manifest: ResearchGovernanceHandoffManifest
    research_only: bool
    execution_approval_granted: bool
    production_approval_granted: bool
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        _validate_non_empty_string("version", self.version)
        _validate_non_empty_string("package_fingerprint", self.package_fingerprint)
        if not isinstance(self.built_at, datetime) or self.built_at.tzinfo is None:
            raise ValueError(
                f"built_at must be a timezone-aware datetime, got {self.built_at!r}"
            )
        if self.governance_status not in GOVERNANCE_STATUSES:
            raise ValueError(
                f"governance_status must be one of {sorted(GOVERNANCE_STATUSES)}, "
                f"got {self.governance_status!r}"
            )
        if not isinstance(self.handoff_allowed, bool):
            raise ValueError(
                f"handoff_allowed must be a bool, got {self.handoff_allowed!r}"
            )
        if not isinstance(self.blocking_reason_codes, tuple):
            object.__setattr__(
                self,
                "blocking_reason_codes",
                tuple(str(c) for c in self.blocking_reason_codes),
            )
        if not isinstance(self.review_reason_codes, tuple):
            object.__setattr__(
                self,
                "review_reason_codes",
                tuple(str(c) for c in self.review_reason_codes),
            )
        if not isinstance(self.research_only, bool):
            raise ValueError(f"research_only must be a bool, got {self.research_only!r}")
        if not isinstance(self.execution_approval_granted, bool):
            raise ValueError(
                f"execution_approval_granted must be a bool, "
                f"got {self.execution_approval_granted!r}"
            )
        if not isinstance(self.production_approval_granted, bool):
            raise ValueError(
                f"production_approval_granted must be a bool, "
                f"got {self.production_approval_granted!r}"
            )
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))


__all__ = [
    "GOVERNANCE_HANDOFF_VERSION",
    "READY_FOR_RESEARCH_HANDOFF",
    "REVIEW_REQUIRED",
    "BLOCKED",
    "GOVERNANCE_STATUSES",
    "HANDOFF_BLOCKING_REASON_CODES",
    "HANDOFF_REVIEW_REQUIRED_REASON_CODES",
    "HANDOFF_REASON_CODES",
    "MISSING_GOVERNANCE_SUMMARY",
    "MISSING_GATE_REPORT",
    "MISSING_LATEST_ACCEPTED_REVIEW",
    "INVALID_GOVERNANCE_SUMMARY",
    "INVALID_GATE_REPORT",
    "INVALID_REVIEW_RECORD",
    "GOVERNANCE_FINGERPRINT_MISMATCH",
    "GATE_FINGERPRINT_MISMATCH",
    "REVIEW_FINGERPRINT_MISMATCH",
    "SOURCE_VERSION_MISMATCH",
    "CONTRADICTORY_HANDOFF_STATE",
    "MISSING_REQUIRED_FINGERPRINT",
    "UNSAFE_HANDOFF_FLAG",
    "INVALID_TIMESTAMP",
    "GOVERNANCE_REVIEW_REQUIRED",
    "INCOMPLETE_PROVENANCE",
    "UNKNOWN_NON_BLOCKING_FIELD",
    "MISSING_OPTIONAL_METADATA",
    "HANDOFF_PACKAGE_READY",
    "DEFAULT_REQUIRE_LATEST_ACCEPTED_REVIEW",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_REPORT_OUTPUT_DIR",
    "DEFAULT_JSON_FILENAME",
    "DEFAULT_MARKDOWN_FILENAME",
    "CANONICAL_SAFETY_FLAGS",
    "GovernanceHandoffError",
    "GovernanceHandoffConfig",
    "HandoffSourceReference",
    "ResearchGovernanceHandoffManifest",
    "ResearchGovernanceHandoffPackage",
]
