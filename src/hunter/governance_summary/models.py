"""Models for the Governance Decision Summary Aggregator (MVP-61).

MVP-61 combines the gate result from ``ResearchDecisionGateReport`` (MVP-59),
the review chain from ``HumanReviewRecord`` (MVP-60), and chain verification
state into one deterministic governance summary. The result is research-only
and never authorizes execution, production use, or trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping

GOVERNANCE_SUMMARY_VERSION: str = "0.61.0-dev"

# Governance statuses
READY_FOR_RESEARCH_HANDOFF: Literal["READY_FOR_RESEARCH_HANDOFF"] = "READY_FOR_RESEARCH_HANDOFF"
REVIEW_REQUIRED: Literal["REVIEW_REQUIRED"] = "REVIEW_REQUIRED"
BLOCKED: Literal["BLOCKED"] = "BLOCKED"

GOVERNANCE_STATUSES: frozenset[str] = frozenset(
    {READY_FOR_RESEARCH_HANDOFF, REVIEW_REQUIRED, BLOCKED}
)

# Blocking reason codes
MISSING_GATE_REPORT = "MISSING_GATE_REPORT"
INVALID_GATE_REPORT = "INVALID_GATE_REPORT"
GATE_DECISION_NO_GO = "GATE_DECISION_NO_GO"
MISSING_REVIEW_CHAIN = "MISSING_REVIEW_CHAIN"
BROKEN_REVIEW_CHAIN = "BROKEN_REVIEW_CHAIN"
TAMPERED_REVIEW_RECORD = "TAMPERED_REVIEW_RECORD"
DUPLICATE_REVIEW_RECORD = "DUPLICATE_REVIEW_RECORD"
CONTRADICTORY_GOVERNANCE_STATE = "CONTRADICTORY_GOVERNANCE_STATE"
MISSING_REQUIRED_FINGERPRINT = "MISSING_REQUIRED_FINGERPRINT"
UNSAFE_GOVERNANCE_FLAG = "UNSAFE_GOVERNANCE_FLAG"
INVALID_TIMESTAMP = "INVALID_TIMESTAMP"

# Review-required reason codes
NO_ACCEPTED_REVIEW = "NO_ACCEPTED_REVIEW"
GATE_REVIEW_REQUIRED = "GATE_REVIEW_REQUIRED"
OPEN_CHANGE_REQUEST = "OPEN_CHANGE_REQUEST"
LATEST_REVIEW_REJECTED = "LATEST_REVIEW_REJECTED"
LATEST_REVIEW_REQUESTS_CHANGES = "LATEST_REVIEW_REQUESTS_CHANGES"
INCOMPLETE_PROVENANCE = "INCOMPLETE_PROVENANCE"
UNKNOWN_NON_BLOCKING_FIELD = "UNKNOWN_NON_BLOCKING_FIELD"

GOVERNANCE_BLOCKING_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_GATE_REPORT,
        INVALID_GATE_REPORT,
        GATE_DECISION_NO_GO,
        MISSING_REVIEW_CHAIN,
        BROKEN_REVIEW_CHAIN,
        TAMPERED_REVIEW_RECORD,
        DUPLICATE_REVIEW_RECORD,
        CONTRADICTORY_GOVERNANCE_STATE,
        MISSING_REQUIRED_FINGERPRINT,
        UNSAFE_GOVERNANCE_FLAG,
        INVALID_TIMESTAMP,
    }
)

GOVERNANCE_REVIEW_REQUIRED_REASON_CODES: frozenset[str] = frozenset(
    {
        NO_ACCEPTED_REVIEW,
        GATE_REVIEW_REQUIRED,
        OPEN_CHANGE_REQUEST,
        LATEST_REVIEW_REJECTED,
        LATEST_REVIEW_REQUESTS_CHANGES,
        INCOMPLETE_PROVENANCE,
        UNKNOWN_NON_BLOCKING_FIELD,
    }
)

GOVERNANCE_REASON_CODES: frozenset[str] = (
    GOVERNANCE_BLOCKING_REASON_CODES | GOVERNANCE_REVIEW_REQUIRED_REASON_CODES
)

DEFAULT_REQUIRE_REVIEW_CHAIN: bool = True
DEFAULT_OUTPUT_DIR: Path = Path("data/governance_summary")
DEFAULT_REPORT_OUTPUT_DIR: Path = Path("reports/governance_summary")
DEFAULT_JSON_FILENAME: str = "latest_governance_summary.json"
DEFAULT_MARKDOWN_FILENAME: str = "latest_governance_summary.md"


def _coerce_json_value(value: Any) -> Any:
    """Recursively copy a JSON-compatible value."""
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


class GovernanceSummaryError(Exception):
    """Base exception for the governance summary aggregator."""

    def __init__(self, *args: Any, reason_code: str | None = None) -> None:
        super().__init__(*args)
        self.reason_code = reason_code


@dataclass(frozen=True)
class GovernanceSummaryConfig:
    """Configuration for the governance decision summary aggregator."""

    require_review_chain: bool = DEFAULT_REQUIRE_REVIEW_CHAIN
    output_dir: Path = DEFAULT_OUTPUT_DIR
    report_output_dir: Path = DEFAULT_REPORT_OUTPUT_DIR
    json_filename: str = DEFAULT_JSON_FILENAME
    markdown_filename: str = DEFAULT_MARKDOWN_FILENAME
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.require_review_chain, bool):
            raise ValueError(
                f"require_review_chain must be a bool, got {self.require_review_chain!r}"
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
    def default(cls) -> "GovernanceSummaryConfig":
        """Return the default governance summary configuration."""
        return cls()


@dataclass(frozen=True)
class GovernanceReviewSummary:
    """Summary of the review chain state feeding into governance."""

    total_records: int
    accepted_records: int
    rejected_attempts: int
    chain_valid: bool
    latest_accepted_record_fingerprint: str | None
    latest_reviewer_identity: str | None
    latest_reviewer_decision: str | None
    latest_review_created_at: datetime | None
    open_change_request_count: int
    source_decision_fingerprints: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "total_records",
            "accepted_records",
            "rejected_attempts",
            "open_change_request_count",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer, got {value!r}")
        if not isinstance(self.chain_valid, bool):
            raise ValueError(f"chain_valid must be a bool, got {self.chain_valid!r}")
        for name in (
            "latest_accepted_record_fingerprint",
            "latest_reviewer_identity",
            "latest_reviewer_decision",
        ):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(
                    f"{name} must be a non-empty string or None, got {value!r}"
                )
        if self.latest_review_created_at is not None and (
            not isinstance(self.latest_review_created_at, datetime)
            or self.latest_review_created_at.tzinfo is None
        ):
            raise ValueError(
                "latest_review_created_at must be a timezone-aware datetime or None, "
                f"got {self.latest_review_created_at!r}"
            )
        for name in ("source_decision_fingerprints", "reason_codes"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
        for code in self.reason_codes:
            if code not in GOVERNANCE_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code!r}")


@dataclass(frozen=True)
class GovernanceDecisionSummary:
    """Immutable governance decision summary.

    Combines the research decision gate result, the human review chain, and
    chain verification into one deterministic, research-only summary. This
    summary never authorizes execution, production use, or trading.
    """

    version: str
    governance_status: Literal[
        "READY_FOR_RESEARCH_HANDOFF",
        "REVIEW_REQUIRED",
        "BLOCKED",
    ]
    governance_fingerprint: str
    evaluated_at: datetime
    gate_decision: Literal["GO", "NO_GO", "NEEDS_REVIEW"]
    gate_decision_fingerprint: str
    review_summary: GovernanceReviewSummary
    blocking_reason_codes: tuple[str, ...]
    review_reason_codes: tuple[str, ...]
    research_only: bool
    human_review_required: bool
    execution_approval_granted: bool
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_string("version", self.version)
        if self.governance_status not in GOVERNANCE_STATUSES:
            raise ValueError(
                f"governance_status must be one of {sorted(GOVERNANCE_STATUSES)}, "
                f"got {self.governance_status!r}"
            )
        _validate_non_empty_string("governance_fingerprint", self.governance_fingerprint)
        if not isinstance(self.evaluated_at, datetime) or self.evaluated_at.tzinfo is None:
            raise ValueError(
                f"evaluated_at must be a timezone-aware datetime, got {self.evaluated_at!r}"
            )
        if self.gate_decision not in {"GO", "NO_GO", "NEEDS_REVIEW"}:
            raise ValueError(
                f"gate_decision must be one of {{'GO', 'NO_GO', 'NEEDS_REVIEW'}}, "
                f"got {self.gate_decision!r}"
            )
        _validate_non_empty_string("gate_decision_fingerprint", self.gate_decision_fingerprint)
        for name in ("blocking_reason_codes", "review_reason_codes"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
        for code in self.blocking_reason_codes:
            if code not in GOVERNANCE_BLOCKING_REASON_CODES:
                raise ValueError(f"unsupported blocking reason code: {code!r}")
        for code in self.review_reason_codes:
            if code not in GOVERNANCE_REVIEW_REQUIRED_REASON_CODES:
                raise ValueError(f"unsupported review-required reason code: {code!r}")
        for name in ("research_only", "human_review_required", "execution_approval_granted"):
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")
        if not self.research_only or not self.human_review_required:
            raise ValueError("research_only and human_review_required must both be True")
        if self.execution_approval_granted is not False:
            raise ValueError("execution_approval_granted must always be False")
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))
