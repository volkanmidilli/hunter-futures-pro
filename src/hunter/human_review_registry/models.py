"""Models for the Human Review Decision Registry (MVP-60).

The registry consumes a ``ResearchDecisionGateReport`` (MVP-59) and a human
review input, and produces an immutable, append-only ``HumanReviewRecord``.
All records are research-only; ``execution_approval_granted`` is always False.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping

HUMAN_REVIEW_REGISTRY_VERSION: str = "0.60.0-dev"

# Reviewer decisions
APPROVE_FOR_RESEARCH: Literal["APPROVE_FOR_RESEARCH"] = "APPROVE_FOR_RESEARCH"
REJECT: Literal["REJECT"] = "REJECT"
REQUEST_CHANGES: Literal["REQUEST_CHANGES"] = "REQUEST_CHANGES"

REVIEWER_DECISIONS: frozenset[str] = frozenset(
    {APPROVE_FOR_RESEARCH, REJECT, REQUEST_CHANGES}
)

# Source decisions (from ResearchDecisionGateReport)
GO = "GO"
NO_GO = "NO_GO"
NEEDS_REVIEW = "NEEDS_REVIEW"

SOURCE_DECISIONS: frozenset[str] = frozenset({GO, NO_GO, NEEDS_REVIEW})

# Blocking reason codes
MISSING_DECISION_REPORT = "MISSING_DECISION_REPORT"
MISSING_REVIEW_INPUT = "MISSING_REVIEW_INPUT"
INVALID_REVIEWER_IDENTITY = "INVALID_REVIEWER_IDENTITY"
INVALID_REVIEW_DECISION = "INVALID_REVIEW_DECISION"
REVIEW_NOTE_TOO_SHORT = "REVIEW_NOTE_TOO_SHORT"
MISSING_REQUIRED_REVIEW_NOTE = "MISSING_REQUIRED_REVIEW_NOTE"
SOURCE_FINGERPRINT_MISSING = "SOURCE_FINGERPRINT_MISSING"
NO_GO_APPROVAL_FORBIDDEN = "NO_GO_APPROVAL_FORBIDDEN"
BROKEN_REVIEW_CHAIN = "BROKEN_REVIEW_CHAIN"
PREVIOUS_RECORD_MISMATCH = "PREVIOUS_RECORD_MISMATCH"
DUPLICATE_REVIEW = "DUPLICATE_REVIEW"
INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
CONTRADICTORY_REVIEW = "CONTRADICTORY_REVIEW"

# Accepted reason codes
REVIEW_APPROVED_FOR_RESEARCH = "REVIEW_APPROVED_FOR_RESEARCH"
REVIEW_REJECTED = "REVIEW_REJECTED"
REVIEW_CHANGES_REQUESTED = "REVIEW_CHANGES_REQUESTED"

BLOCKING_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_DECISION_REPORT,
        MISSING_REVIEW_INPUT,
        INVALID_REVIEWER_IDENTITY,
        INVALID_REVIEW_DECISION,
        REVIEW_NOTE_TOO_SHORT,
        MISSING_REQUIRED_REVIEW_NOTE,
        SOURCE_FINGERPRINT_MISSING,
        NO_GO_APPROVAL_FORBIDDEN,
        BROKEN_REVIEW_CHAIN,
        PREVIOUS_RECORD_MISMATCH,
        DUPLICATE_REVIEW,
        INVALID_TIMESTAMP,
        CONTRADICTORY_REVIEW,
    }
)

ACCEPTED_REASON_CODES: frozenset[str] = frozenset(
    {
        REVIEW_APPROVED_FOR_RESEARCH,
        REVIEW_REJECTED,
        REVIEW_CHANGES_REQUESTED,
    }
)

HUMAN_REVIEW_REGISTRY_REASON_CODES: frozenset[str] = (
    BLOCKING_REASON_CODES | ACCEPTED_REASON_CODES
)

DEFAULT_MIN_REVIEW_NOTE_LENGTH: int = 12
DEFAULT_OUTPUT_DIR: Path = Path("data/human_review_registry")
DEFAULT_REPORT_OUTPUT_DIR: Path = Path("reports/human_review_registry")
DEFAULT_JSON_FILENAME: str = "latest_review.json"
DEFAULT_MARKDOWN_FILENAME: str = "latest_review.md"


class HumanReviewRegistryError(Exception):
    """Base exception for the human review registry."""

    def __init__(self, *args: Any, reason_code: str | None = None) -> None:
        super().__init__(*args)
        self.reason_code = reason_code


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


def _validate_non_negative_int(name: str, value: int) -> None:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {value!r}")


@dataclass(frozen=True)
class HumanReviewRegistryConfig:
    """Configuration for the human review registry."""

    min_review_note_length: int = DEFAULT_MIN_REVIEW_NOTE_LENGTH
    output_dir: Path = DEFAULT_OUTPUT_DIR
    report_output_dir: Path = DEFAULT_REPORT_OUTPUT_DIR
    json_filename: str = DEFAULT_JSON_FILENAME
    markdown_filename: str = DEFAULT_MARKDOWN_FILENAME
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_negative_int("min_review_note_length", self.min_review_note_length)
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(str(self.output_dir)))
        if not isinstance(self.report_output_dir, Path):
            object.__setattr__(self, "report_output_dir", Path(str(self.report_output_dir)))
        _validate_non_empty_string("json_filename", self.json_filename)
        _validate_non_empty_string("markdown_filename", self.markdown_filename)
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))

    @classmethod
    def default(cls) -> "HumanReviewRegistryConfig":
        """Return the default registry configuration."""
        return cls()


@dataclass(frozen=True)
class HumanReviewInput:
    """A single human review input."""

    reviewer_identity: str
    reviewer_decision: Literal[
        "APPROVE_FOR_RESEARCH",
        "REJECT",
        "REQUEST_CHANGES",
    ]
    review_note: str

    def __post_init__(self) -> None:
        _validate_non_empty_string("reviewer_identity", self.reviewer_identity)
        if self.reviewer_decision not in REVIEWER_DECISIONS:
            raise ValueError(
                f"reviewer_decision must be one of {sorted(REVIEWER_DECISIONS)}, "
                f"got {self.reviewer_decision!r}"
            )
        if not isinstance(self.review_note, str):
            raise ValueError(f"review_note must be a string, got {self.review_note!r}")


@dataclass(frozen=True)
class HumanReviewRecord:
    """Immutable human review record.

    ``execution_approval_granted`` is always ``False``. ``accepted`` indicates
    whether the review is a valid chain entry; it never authorizes execution.
    """

    version: str
    source_decision_fingerprint: str
    source_decision: Literal["GO", "NO_GO", "NEEDS_REVIEW"]
    reviewer_identity: str
    reviewer_decision: Literal[
        "APPROVE_FOR_RESEARCH",
        "REJECT",
        "REQUEST_CHANGES",
    ]
    review_note: str
    created_at: datetime
    previous_record_fingerprint: str | None
    record_fingerprint: str
    accepted: bool
    human_approval_recorded: bool
    execution_approval_granted: bool
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_string("version", self.version)
        _validate_non_empty_string("source_decision_fingerprint", self.source_decision_fingerprint)
        if self.source_decision not in SOURCE_DECISIONS:
            raise ValueError(
                f"source_decision must be one of {sorted(SOURCE_DECISIONS)}, "
                f"got {self.source_decision!r}"
            )
        _validate_non_empty_string("reviewer_identity", self.reviewer_identity)
        if self.reviewer_decision not in REVIEWER_DECISIONS:
            raise ValueError(
                f"reviewer_decision must be one of {sorted(REVIEWER_DECISIONS)}, "
                f"got {self.reviewer_decision!r}"
            )
        if not isinstance(self.review_note, str):
            raise ValueError(f"review_note must be a string, got {self.review_note!r}")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError(
                f"created_at must be a timezone-aware datetime, got {self.created_at!r}"
            )
        if self.previous_record_fingerprint is not None:
            _validate_non_empty_string(
                "previous_record_fingerprint", self.previous_record_fingerprint
            )
        _validate_non_empty_string("record_fingerprint", self.record_fingerprint)
        for name in ("accepted", "human_approval_recorded", "execution_approval_granted"):
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")
        if self.execution_approval_granted is not False:
            raise ValueError("execution_approval_granted must always be False")
        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        for code in self.reason_codes:
            if code not in HUMAN_REVIEW_REGISTRY_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code!r}")
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))
