"""Models for the Research Decision Gate Engine (MVP-59).

The engine consumes a ``ValidatedPortfolioRiskContext`` (MVP-58), a
``ControlledUniverseReport`` (MVP-51/MVP-52), and an optional strategy-contract
mapping, and produces an immutable, research-only, human-approval-required
``ResearchDecisionGateReport``. It does not emit trading signals, orders, or
execution commands, and does not integrate with Freqtrade runtime, exchanges,
databases, schedulers, or live trading systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping

RESEARCH_DECISION_GATE_VERSION: str = "0.59.0-dev"

# Strategy contract policies
ALLOW_WITH_REVIEW: Literal["ALLOW_WITH_REVIEW"] = "ALLOW_WITH_REVIEW"
REQUIRE: Literal["REQUIRE"] = "REQUIRE"
IGNORE: Literal["IGNORE"] = "IGNORE"

STRATEGY_CONTRACT_POLICIES: frozenset[str] = frozenset({ALLOW_WITH_REVIEW, REQUIRE, IGNORE})

# Blocking reason codes
MISSING_RISK_CONTEXT = "MISSING_RISK_CONTEXT"
REJECTED_RISK_CONTEXT = "REJECTED_RISK_CONTEXT"
RISK_GATE_CLOSED = "RISK_GATE_CLOSED"
BLOCK_ALL_RISK_CONTEXT = "BLOCK_ALL_RISK_CONTEXT"
MISSING_UNIVERSE_REPORT = "MISSING_UNIVERSE_REPORT"
REJECTED_UNIVERSE_REPORT = "REJECTED_UNIVERSE_REPORT"
STALE_RISK_CONTEXT = "STALE_RISK_CONTEXT"
STALE_UNIVERSE_REPORT = "STALE_UNIVERSE_REPORT"
INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
UNSAFE_RESEARCH_FLAG = "UNSAFE_RESEARCH_FLAG"
MISSING_HUMAN_APPROVAL_FLAG = "MISSING_HUMAN_APPROVAL_FLAG"
MISSING_REQUIRED_FINGERPRINT = "MISSING_REQUIRED_FINGERPRINT"
MISSING_STRATEGY_CONTRACT = "MISSING_STRATEGY_CONTRACT"
INVALID_STRATEGY_CONTRACT = "INVALID_STRATEGY_CONTRACT"
UNSAFE_STRATEGY_CONTRACT = "UNSAFE_STRATEGY_CONTRACT"
CONTRADICTORY_SAFETY_FLAGS = "CONTRADICTORY_SAFETY_FLAGS"
CONTRADICTORY_INPUTS = "CONTRADICTORY_INPUTS"

# Review reason codes
OPTIONAL_STRATEGY_CONTRACT_MISSING = "OPTIONAL_STRATEGY_CONTRACT_MISSING"
STRATEGY_CONTRACT_MODE_MISMATCH = "STRATEGY_CONTRACT_MODE_MISMATCH"
STRATEGY_CONTRACT_SCOPE_MISMATCH = "STRATEGY_CONTRACT_SCOPE_MISMATCH"
INCOMPLETE_PROVENANCE = "INCOMPLETE_PROVENANCE"
UNKNOWN_NON_BLOCKING_FIELD = "UNKNOWN_NON_BLOCKING_FIELD"
UPSTREAM_REVIEW_REQUIRED = "UPSTREAM_REVIEW_REQUIRED"

# Decision reason codes
DECISION_GO = "DECISION_GO"
DECISION_NO_GO = "DECISION_NO_GO"
DECISION_NEEDS_REVIEW = "DECISION_NEEDS_REVIEW"

BLOCKING_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_RISK_CONTEXT,
        REJECTED_RISK_CONTEXT,
        RISK_GATE_CLOSED,
        BLOCK_ALL_RISK_CONTEXT,
        MISSING_UNIVERSE_REPORT,
        REJECTED_UNIVERSE_REPORT,
        STALE_RISK_CONTEXT,
        STALE_UNIVERSE_REPORT,
        INVALID_TIMESTAMP,
        UNSAFE_RESEARCH_FLAG,
        MISSING_HUMAN_APPROVAL_FLAG,
        MISSING_REQUIRED_FINGERPRINT,
        MISSING_STRATEGY_CONTRACT,
        INVALID_STRATEGY_CONTRACT,
        UNSAFE_STRATEGY_CONTRACT,
        CONTRADICTORY_SAFETY_FLAGS,
        CONTRADICTORY_INPUTS,
    }
)

REVIEW_REASON_CODES: frozenset[str] = frozenset(
    {
        OPTIONAL_STRATEGY_CONTRACT_MISSING,
        STRATEGY_CONTRACT_MODE_MISMATCH,
        STRATEGY_CONTRACT_SCOPE_MISMATCH,
        INCOMPLETE_PROVENANCE,
        UNKNOWN_NON_BLOCKING_FIELD,
        UPSTREAM_REVIEW_REQUIRED,
    }
)

DECISION_REASON_CODES: frozenset[str] = frozenset(
    {
        DECISION_GO,
        DECISION_NO_GO,
        DECISION_NEEDS_REVIEW,
    }
)

RESEARCH_DECISION_GATE_REASON_CODES: frozenset[str] = (
    BLOCKING_REASON_CODES | REVIEW_REASON_CODES | DECISION_REASON_CODES
)

_DECISIONS: frozenset[str] = frozenset({"GO", "NO_GO", "NEEDS_REVIEW"})

DEFAULT_OUTPUT_DIR: Path = Path("data/research_decision_gate")
DEFAULT_REPORT_OUTPUT_DIR: Path = Path("reports/research_decision_gate")
DEFAULT_JSON_FILENAME: str = "latest_decision.json"
DEFAULT_MARKDOWN_FILENAME: str = "latest_decision.md"
DEFAULT_MAX_UNIVERSE_AGE_SECONDS: int = 300
DEFAULT_MAX_RISK_CONTEXT_AGE_SECONDS: int = 300
DEFAULT_ALLOWED_FUTURE_SKEW_SECONDS: int = 60


class ResearchDecisionGateError(Exception):
    """Base exception for the research decision gate engine.

    Raised for invalid configuration or invalid input. Not raised for normal
    fail-closed states, which are encoded in result reason codes.
    """

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


def _validate_non_negative_int(name: str, value: int) -> None:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {value!r}")


@dataclass(frozen=True)
class ResearchDecisionGateConfig:
    """Configuration for the research decision gate engine."""

    strategy_contract_policy: Literal["ALLOW_WITH_REVIEW", "REQUIRE", "IGNORE"] = ALLOW_WITH_REVIEW
    max_universe_age_seconds: int = DEFAULT_MAX_UNIVERSE_AGE_SECONDS
    max_risk_context_age_seconds: int = DEFAULT_MAX_RISK_CONTEXT_AGE_SECONDS
    allowed_future_skew_seconds: int = DEFAULT_ALLOWED_FUTURE_SKEW_SECONDS
    output_dir: Path = DEFAULT_OUTPUT_DIR
    report_output_dir: Path = DEFAULT_REPORT_OUTPUT_DIR
    json_filename: str = DEFAULT_JSON_FILENAME
    markdown_filename: str = DEFAULT_MARKDOWN_FILENAME
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.strategy_contract_policy not in STRATEGY_CONTRACT_POLICIES:
            raise ValueError(
                f"strategy_contract_policy must be one of {sorted(STRATEGY_CONTRACT_POLICIES)}, "
                f"got {self.strategy_contract_policy!r}"
            )
        _validate_non_negative_int("max_universe_age_seconds", self.max_universe_age_seconds)
        _validate_non_negative_int("max_risk_context_age_seconds", self.max_risk_context_age_seconds)
        _validate_non_negative_int("allowed_future_skew_seconds", self.allowed_future_skew_seconds)
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(str(self.output_dir)))
        if not isinstance(self.report_output_dir, Path):
            object.__setattr__(self, "report_output_dir", Path(str(self.report_output_dir)))
        for name, value in (
            ("json_filename", self.json_filename),
            ("markdown_filename", self.markdown_filename),
        ):
            _validate_non_empty_string(name, value)
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))

    @classmethod
    def default(cls) -> "ResearchDecisionGateConfig":
        """Return the default research-only decision gate configuration."""
        return cls()


@dataclass(frozen=True)
class DecisionSourceSummary:
    """Summary of one upstream source's contribution to the decision."""

    source_name: str
    present: bool
    accepted: bool
    fresh: bool
    fingerprint: str | None
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_non_empty_string("source_name", self.source_name)
        for name in ("present", "accepted", "fresh"):
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")
        if self.fingerprint is not None and (
            not isinstance(self.fingerprint, str) or not self.fingerprint.strip()
        ):
            raise ValueError(
                f"fingerprint must be a non-empty string or None, got {self.fingerprint!r}"
            )
        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        for code in self.reason_codes:
            if not isinstance(code, str) or not code.strip():
                raise ValueError(f"reason_codes must contain non-empty strings, got {code!r}")


@dataclass(frozen=True)
class ResearchDecisionGateReport:
    """Immutable research-only decision gate report.

    The decision is one of ``GO``, ``NO_GO``, or ``NEEDS_REVIEW``. ``GO`` only
    indicates that upstream research artifacts are internally consistent and
    safe enough for human review; it is never execution approval, production
    readiness, or authorization to trade.
    """

    version: str
    decision: Literal["GO", "NO_GO", "NEEDS_REVIEW"]
    decision_fingerprint: str
    evaluated_at: datetime
    risk_context_summary: DecisionSourceSummary
    universe_summary: DecisionSourceSummary
    strategy_contract_summary: DecisionSourceSummary
    blocking_reason_codes: tuple[str, ...]
    review_reason_codes: tuple[str, ...]
    safety_flags: Mapping[str, bool]
    research_only: bool
    human_approval_required: bool
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_string("version", self.version)
        if self.decision not in _DECISIONS:
            raise ValueError(f"decision must be one of {sorted(_DECISIONS)}, got {self.decision!r}")
        _validate_non_empty_string("decision_fingerprint", self.decision_fingerprint)
        if not isinstance(self.evaluated_at, datetime) or self.evaluated_at.tzinfo is None:
            raise ValueError(
                f"evaluated_at must be a timezone-aware datetime, got {self.evaluated_at!r}"
            )
        for name in ("research_only", "human_approval_required"):
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")
        if not self.research_only or not self.human_approval_required:
            raise ValueError("research_only and human_approval_required must both be True")
        for name in ("blocking_reason_codes", "review_reason_codes"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
        for code in self.blocking_reason_codes:
            if code not in BLOCKING_REASON_CODES:
                raise ValueError(f"unsupported blocking reason code: {code!r}")
        for code in self.review_reason_codes:
            if code not in REVIEW_REASON_CODES:
                raise ValueError(f"unsupported review reason code: {code!r}")
        if not isinstance(self.safety_flags, Mapping):
            raise ValueError(f"safety_flags must be a Mapping, got {self.safety_flags!r}")
        for key, value in self.safety_flags.items():
            if not isinstance(key, str) or not isinstance(value, bool):
                raise ValueError(
                    f"safety_flags must be Mapping[str, bool], got {key!r}: {value!r}"
                )
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))
