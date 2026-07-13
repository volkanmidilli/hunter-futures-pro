"""Models for the Strategy Contract Consumption Adapter (MVP-57).

The adapter consumes a strategy-contract input (file or in-memory mapping) and
produces an immutable, research-only, human-approval-required validation context.
It does not integrate with Freqtrade runtime, exchanges, databases, schedulers,
or live trading systems, and never emits action commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

STRATEGY_CONTRACT_CONSUMER_VERSION: str = "0.56.0-dev"

# Reason codes — deterministic strings for every blocking or allowed decision
MISSING_INPUT = "MISSING_INPUT"
INPUT_READ_FAILED = "INPUT_READ_FAILED"
INVALID_JSON = "INVALID_JSON"
INVALID_SCHEMA = "INVALID_SCHEMA"
UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
STALE_INPUT = "STALE_INPUT"
UNSAFE_RESEARCH_FLAG = "UNSAFE_RESEARCH_FLAG"
MISSING_HUMAN_APPROVAL_FLAG = "MISSING_HUMAN_APPROVAL_FLAG"
INVALID_MODE = "INVALID_MODE"
INVALID_PAIR = "INVALID_PAIR"
DUPLICATE_PAIR = "DUPLICATE_PAIR"
PAIR_LIST_CONFLICT = "PAIR_LIST_CONFLICT"
INVALID_SAFETY_FLAGS = "INVALID_SAFETY_FLAGS"
CONTRADICTORY_INPUT = "CONTRADICTORY_INPUT"
VALIDATION_ACCEPTED = "VALIDATION_ACCEPTED"

STRATEGY_CONTRACT_CONSUMER_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_INPUT,
        INPUT_READ_FAILED,
        INVALID_JSON,
        INVALID_SCHEMA,
        UNSUPPORTED_VERSION,
        INVALID_TIMESTAMP,
        STALE_INPUT,
        UNSAFE_RESEARCH_FLAG,
        MISSING_HUMAN_APPROVAL_FLAG,
        INVALID_MODE,
        INVALID_PAIR,
        DUPLICATE_PAIR,
        PAIR_LIST_CONFLICT,
        INVALID_SAFETY_FLAGS,
        CONTRADICTORY_INPUT,
        VALIDATION_ACCEPTED,
    }
)

_ALLOWED_MODES: frozenset[str] = frozenset(
    {
        "LONG",
        "SHORT",
        "BLOCK_ALL",
    }
)

_REQUIRED_SAFETY_FLAGS: dict[str, bool] = {
    "dry_run": True,
    "live_trading_enabled": False,
    "real_orders_enabled": False,
    "leverage_enabled": False,
    "shorting_enabled": False,
    "strategy_runtime_allowed": False,
    "entry_signals_allowed": False,
    "exit_signals_allowed": False,
}


class StrategyContractConsumerError(Exception):
    """Base exception for the strategy contract consumption adapter.

    Raised for invalid configuration, invalid input, or writer failures. Not
    raised for normal fail-closed states, which are encoded in result reason
    codes.
    """

    def __init__(
        self,
        *args: Any,
        reason_code: str | None = None,
    ) -> None:
        super().__init__(*args)
        self.reason_code = reason_code


def _coerce_tuple_strs(value: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    """Coerce a sequence of strings to a tuple of strings."""
    if value is None:
        return ()
    return tuple(str(item) for item in value)


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


def _coerce_safety_flags(value: dict[str, bool] | None) -> dict[str, bool]:
    """Coerce a safety-flags mapping to a plain dict of booleans."""
    if value is None:
        return {}
    return {str(k): bool(v) for k, v in value.items()}


@dataclass(frozen=True)
class StrategyContractConsumerConfig:
    """Configuration for the strategy contract consumption adapter."""

    output_dir: str = "data/strategy_contract_validation"
    markdown_output_dir: str = "reports/strategy_contract_validation"
    json_filename: str = "latest_validation.json"
    markdown_filename: str = "latest_validation.md"
    supported_versions: frozenset[str] = field(
        default_factory=lambda: frozenset({STRATEGY_CONTRACT_CONSUMER_VERSION})
    )
    stale_input_threshold_seconds: int = 300
    future_input_tolerance_seconds: int = 60
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("output_dir", self.output_dir),
            ("markdown_output_dir", self.markdown_output_dir),
            ("json_filename", self.json_filename),
            ("markdown_filename", self.markdown_filename),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string, got {value!r}")
        if not isinstance(self.supported_versions, frozenset) or not self.supported_versions:
            raise ValueError(
                f"supported_versions must be a non-empty frozenset, got {self.supported_versions!r}"
            )
        for version in self.supported_versions:
            if not isinstance(version, str) or not version.strip():
                raise ValueError(
                    f"supported_versions must contain non-empty strings, got {version!r}"
                )
        for name, value in (
            ("stale_input_threshold_seconds", self.stale_input_threshold_seconds),
            ("future_input_tolerance_seconds", self.future_input_tolerance_seconds),
        ):
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer, got {value!r}")
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))

    @classmethod
    def default(cls) -> "StrategyContractConsumerConfig":
        """Return the default consumer configuration."""
        return cls()


@dataclass(frozen=True)
class ValidatedStrategyContext:
    """Immutable validation result produced by the strategy contract consumer.

    Every safety-critical field defaults to the most restrictive state. A result
    with ``accepted=False`` is always fail-closed: mode is ``BLOCK_ALL`` and the
    whitelist is empty.
    """

    accepted: bool
    validated_at: datetime
    source_fingerprint: str
    source_path: str
    input_version: str
    mode: str
    whitelist: tuple[str, ...]
    blacklist: tuple[str, ...]
    safety_flags: dict[str, bool]
    reason_codes: tuple[str, ...]
    version: str = STRATEGY_CONTRACT_CONSUMER_VERSION
    research_only: bool = True
    human_approval_required: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.accepted, bool):
            raise ValueError(f"accepted must be a bool, got {self.accepted!r}")
        if not isinstance(self.validated_at, datetime):
            raise ValueError(f"validated_at must be a datetime, got {self.validated_at!r}")
        if self.validated_at.tzinfo is None:
            raise ValueError("validated_at must be timezone-aware")
        if self.generated_at is not None and (
            not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None
        ):
            raise ValueError("generated_at must be a timezone-aware datetime or None")
        if not isinstance(self.source_fingerprint, str) or not self.source_fingerprint.strip():
            raise ValueError(
                f"source_fingerprint must be a non-empty string, got {self.source_fingerprint!r}"
            )
        if not isinstance(self.source_path, str) or not self.source_path.strip():
            raise ValueError(
                f"source_path must be a non-empty string, got {self.source_path!r}"
            )
        if not isinstance(self.input_version, str):
            raise ValueError(f"input_version must be a string, got {self.input_version!r}")
        if not isinstance(self.mode, str) or self.mode not in _ALLOWED_MODES:
            raise ValueError(f"mode must be one of {_ALLOWED_MODES}, got {self.mode!r}")
        for name, value in (
            ("whitelist", self.whitelist),
            ("blacklist", self.blacklist),
            ("reason_codes", self.reason_codes),
        ):
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
        if not isinstance(self.safety_flags, dict):
            raise ValueError(f"safety_flags must be a dict, got {self.safety_flags!r}")
        for key, value in self.safety_flags.items():
            if not isinstance(key, str) or not isinstance(value, bool):
                raise ValueError(
                    f"safety_flags must be a dict[str, bool], got {key!r}: {value!r}"
                )
        for name, value in (
            ("research_only", self.research_only),
            ("human_approval_required", self.human_approval_required),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")
        if not self.research_only or not self.human_approval_required:
            raise ValueError(
                "research_only and human_approval_required must both be True"
            )
        for code in self.reason_codes:
            if code not in STRATEGY_CONTRACT_CONSUMER_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        if not self.accepted:
            if self.mode != "BLOCK_ALL":
                raise ValueError(
                    "a rejected result must have mode='BLOCK_ALL', got " f"{self.mode!r}"
                )
            if self.whitelist:
                raise ValueError(
                    "a rejected result must have an empty whitelist, got "
                    f"{self.whitelist!r}"
                )
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))
