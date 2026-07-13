"""Models for the Freqtrade Universe Consumption Adapter (MVP-55).

The adapter consumes a `ControlledUniverseExportResult` and produces
deterministic, research-only, human-approval-required artifacts that can be
reviewed before any Freqtrade consumption. It does not integrate with Freqtrade
runtime, exchanges, databases, schedulers, or live trading systems, and never
emits action commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from hunter.controlled_universe_export_adapter.models import (
    ControlledUniversePairExportSummary,
)

FREQTRADE_UNIVERSE_ADAPTER_VERSION: str = "0.55.0-dev"

# Reason codes — deterministic strings for every blocking or allowed decision
MISSING_EXPORT_INPUT = "MISSING_EXPORT_INPUT"
BLOCKED_EXPORT_INPUT = "BLOCKED_EXPORT_INPUT"
EMPTY_WHITELIST = "EMPTY_WHITELIST"
INVALID_PAIR_FORMAT = "INVALID_PAIR_FORMAT"
DUPLICATE_PAIR = "DUPLICATE_PAIR"
CONTRADICTORY_PAIR = "CONTRADICTORY_PAIR"
EXPORT_RESEARCH_ONLY = "EXPORT_RESEARCH_ONLY"
EXPORT_HUMAN_APPROVAL_REQUIRED = "EXPORT_HUMAN_APPROVAL_REQUIRED"
NO_FREQTRADE_RUNTIME_CONNECTION = "NO_FREQTRADE_RUNTIME_CONNECTION"
NO_AUTOMATIC_CONFIG_MUTATION = "NO_AUTOMATIC_CONFIG_MUTATION"
STALE_EXPORT_INPUT = "STALE_EXPORT_INPUT"

FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_EXPORT_INPUT,
        BLOCKED_EXPORT_INPUT,
        EMPTY_WHITELIST,
        INVALID_PAIR_FORMAT,
        DUPLICATE_PAIR,
        CONTRADICTORY_PAIR,
        EXPORT_RESEARCH_ONLY,
        EXPORT_HUMAN_APPROVAL_REQUIRED,
        NO_FREQTRADE_RUNTIME_CONNECTION,
        NO_AUTOMATIC_CONFIG_MUTATION,
        STALE_EXPORT_INPUT,
    }
)


class FreqtradeUniverseAdapterError(Exception):
    """Base exception for the Freqtrade universe consumption adapter.

    Raised for invalid configuration, invalid results, or writer failures.
    Not raised for normal fail-closed states, which are encoded in result
    reason codes.
    """


def _coerce_tuple_strs(value: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    """Coerce a sequence of strings to a tuple of strings."""
    if value is None:
        return ()
    return tuple(str(item) for item in value)


def _coerce_mapping_strs(value: Mapping[str, str] | dict[str, str] | None) -> Mapping[str, str]:
    """Coerce a mapping to an immutable string mapping."""
    if value is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in value.items()})


@dataclass(frozen=True)
class FreqtradeUniverseAdapterConfig:
    """Configuration for the Freqtrade universe consumption adapter."""

    output_dir: str = "data/freqtrade_universe_adapter"
    markdown_output_dir: str = "reports/freqtrade_universe_adapter"
    pair_format: str = "base/quote"
    stale_export_threshold_seconds: int = 300
    include_blacklist: bool = True
    include_per_pair_summary: bool = True
    json_filename: str = "latest_universe.json"
    markdown_filename: str = "latest_universe.md"
    pairlist_filename: str = "pairlist.json"
    strategy_contract_input_filename: str = "strategy_contract_input.json"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.pair_format not in ("base/quote", "base_quote"):
            raise ValueError(
                f"pair_format must be 'base/quote' or 'base_quote', got {self.pair_format!r}"
            )
        for name, value in (
            ("output_dir", self.output_dir),
            ("markdown_output_dir", self.markdown_output_dir),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string, got {value!r}")
        for name, value in (
            ("json_filename", self.json_filename),
            ("markdown_filename", self.markdown_filename),
            ("pairlist_filename", self.pairlist_filename),
            ("strategy_contract_input_filename", self.strategy_contract_input_filename),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string, got {value!r}")
        if (
            not isinstance(self.stale_export_threshold_seconds, int)
            or self.stale_export_threshold_seconds < 0
        ):
            raise ValueError(
                "stale_export_threshold_seconds must be a non-negative integer, "
                f"got {self.stale_export_threshold_seconds!r}"
            )
        for name, value in (
            ("include_blacklist", self.include_blacklist),
            ("include_per_pair_summary", self.include_per_pair_summary),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))

    @classmethod
    def default(cls) -> "FreqtradeUniverseAdapterConfig":
        """Return the default adapter configuration."""
        return cls()


@dataclass(frozen=True)
class FreqtradeUniverseAdapterResult:
    """Result of transforming a ControlledUniverseExportResult into a Freqtrade-compatible,
    research-only universe packet.
    """

    report_id: str
    generated_at: datetime
    whitelist: tuple[str, ...]
    blacklist: tuple[str, ...]
    pairlist: dict[str, Any]
    strategy_contract_input: dict[str, Any]
    per_pair_summary: tuple[ControlledUniversePairExportSummary, ...]
    version: str = FREQTRADE_UNIVERSE_ADAPTER_VERSION
    research_only: bool = True
    human_approval_required: bool = True
    reason_codes: tuple[str, ...] = ()
    safety_flags: dict[str, bool] = field(default_factory=dict)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.report_id, str) or not self.report_id.strip():
            raise ValueError(f"report_id must be a non-empty string, got {self.report_id!r}")
        if not isinstance(self.generated_at, datetime):
            raise ValueError(f"generated_at must be a datetime, got {self.generated_at!r}")
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        for name, value in (
            ("whitelist", self.whitelist),
            ("blacklist", self.blacklist),
            ("per_pair_summary", self.per_pair_summary),
            ("reason_codes", self.reason_codes),
        ):
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
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
        if not isinstance(self.pairlist, dict):
            raise ValueError(f"pairlist must be a dict, got {self.pairlist!r}")
        if not isinstance(self.strategy_contract_input, dict):
            raise ValueError(
                f"strategy_contract_input must be a dict, got {self.strategy_contract_input!r}"
            )
        if not isinstance(self.safety_flags, dict):
            raise ValueError(f"safety_flags must be a dict, got {self.safety_flags!r}")
        for key, value in self.safety_flags.items():
            if not isinstance(key, str) or not isinstance(value, bool):
                raise ValueError(
                    f"safety_flags must be a dict[str, bool], got {key!r}: {value!r}"
                )
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        for pair in self.whitelist:
            if not isinstance(pair, str) or not pair.strip():
                raise ValueError(f"whitelist pairs must be non-empty strings, got {pair!r}")
        for pair in self.blacklist:
            if not isinstance(pair, str) or not pair.strip():
                raise ValueError(f"blacklist pairs must be non-empty strings, got {pair!r}")
        for code in self.reason_codes:
            if code not in FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
