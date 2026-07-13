"""Models for the Controlled Universe Export Adapter (MVP-53).

The adapter consumes a `ControlledUniverseReport` and produces deterministic,
research-only artifacts representing allowed and blocked pair sets. It never
integrates with Freqtrade runtime, exchanges, databases, schedulers, or live
trading systems, and never emits action commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

CONTROLLED_UNIVERSE_EXPORT_VERSION: str = "0.53.0-dev"

# Reason codes
MISSING_REPORT_INPUT = "MISSING_REPORT_INPUT"
BLOCKED_EXPORT = "BLOCKED_EXPORT"
NO_INCLUDED_PAIRS = "NO_INCLUDED_PAIRS"
EXPORT_RESEARCH_ONLY = "EXPORT_RESEARCH_ONLY"
EXPORT_HUMAN_APPROVAL_REQUIRED = "EXPORT_HUMAN_APPROVAL_REQUIRED"
NO_FREQTRADE_RUNTIME_CONNECTION = "NO_FREQTRADE_RUNTIME_CONNECTION"
NO_AUTOMATIC_CONFIG_MUTATION = "NO_AUTOMATIC_CONFIG_MUTATION"

CONTROLLED_UNIVERSE_EXPORT_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_REPORT_INPUT,
        BLOCKED_EXPORT,
        NO_INCLUDED_PAIRS,
        EXPORT_RESEARCH_ONLY,
        EXPORT_HUMAN_APPROVAL_REQUIRED,
        NO_FREQTRADE_RUNTIME_CONNECTION,
        NO_AUTOMATIC_CONFIG_MUTATION,
    }
)


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
class ControlledUniverseExportConfig:
    """Configuration for the controlled universe export adapter."""

    pair_format: str = "base/quote"
    output_dir: str = "data/controlled_universe_export"
    markdown_output_dir: str = "reports/controlled_universe_export"
    json_filename: str = "latest_export.json"
    markdown_filename: str = "latest_export.md"
    include_watchlist_in_whitelist: bool = False
    include_reason_codes_in_summary: bool = True

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
        ):
            if not isinstance(value, str):
                raise ValueError(f"{name} must be a string, got {value!r}")
        for name, value in (
            ("include_watchlist_in_whitelist", self.include_watchlist_in_whitelist),
            ("include_reason_codes_in_summary", self.include_reason_codes_in_summary),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")

    @classmethod
    def default(cls) -> "ControlledUniverseExportConfig":
        """Return the default export configuration."""
        return cls()


@dataclass(frozen=True)
class ControlledUniversePairExportSummary:
    """Human-readable per-pair inclusion/exclusion summary."""

    pair: str
    state: str
    classification: str
    reason_codes: tuple[str, ...] = ()
    human_note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError(f"pair must be a non-empty string, got {self.pair!r}")
        for name, value in (
            ("state", self.state),
            ("classification", self.classification),
            ("human_note", self.human_note),
        ):
            if not isinstance(value, str):
                raise ValueError(f"{name} must be a string, got {value!r}")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


@dataclass(frozen=True)
class ControlledUniverseExportResult:
    """Result of transforming a ControlledUniverseReport into a research-only export."""

    report_id: str
    generated_at: datetime
    whitelist: tuple[str, ...]
    blacklist: tuple[str, ...]
    per_pair_summary: tuple[ControlledUniversePairExportSummary, ...]
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
        if not isinstance(self.safety_flags, dict):
            raise ValueError(f"safety_flags must be a dict, got {self.safety_flags!r}")
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        for code in self.reason_codes:
            if code not in CONTROLLED_UNIVERSE_EXPORT_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")


class ControlledUniverseExportError(Exception):
    """Base exception for the controlled universe export adapter."""
