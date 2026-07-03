"""Frozen models and enums for the hunter.reporting_cli package.

MVP-29 — Local Research Reporting CLI.

All models are frozen. Validation runs in __post_init__. Inputs are already-loaded
local values; the CLI model layer never opens files, follows paths, validates
paths, calls network endpoints, or accesses external resources.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any


REPORTING_CLI_VERSION: str = "0.29.0-dev"


class CLIExitCode(Enum):
    """Deterministic exit codes for the reporting CLI."""

    OK = 0
    USAGE_ERROR = 2
    VALIDATION_ERROR = 3
    UNSAFE_CONTENT = 4
    INTERNAL_ERROR = 5


class CLIOutputFormat(Enum):
    """Supported output formats for command results."""

    JSON = "JSON"
    MARKDOWN = "MARKDOWN"
    TEXT = "TEXT"


class CLICommandKind(Enum):
    """Known command names for the reporting CLI."""

    VERSION = "version"
    SAFETY_SUMMARY = "safety-summary"
    LIST_ARTIFACTS = "list-artifacts"
    RENDER_SAMPLE = "render-sample"
    VALIDATE_ARTIFACT_PATHS = "validate-artifact-paths"


REPORTING_CLI_REASON_CODES: frozenset[str] = frozenset({
    "OK",
    "UNKNOWN_COMMAND",
    "USAGE_ERROR",
    "VALIDATION_ERROR",
    "UNSAFE_CONTENT",
    "INVALID_PATH",
    "PATH_TRAVERSAL_DETECTED",
    "NETWORK_REFERENCE_DETECTED",
    "RESEARCH_ONLY",
    "NOT_TRADING_ADVICE",
    "NO_FILE_INGESTION",
    "OPAQUE_PATH_ONLY",
})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _coerce_tuple_strs(value: Sequence[str] | None) -> tuple[str, ...]:
    """Return a deduplicated tuple of strings."""
    if value is None:
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        s = str(item)
        if s not in seen:
            seen.add(s)
            result.append(s)
    return tuple(result)


def _coerce_mapping_strs(value: Mapping[str, str] | None) -> Mapping[str, str]:
    """Return a MappingProxyType of string key-value pairs."""
    if value is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in value.items()})


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CLISafetyFlags:
    """Safety invariants for the reporting CLI."""

    no_trading_signal: bool = True
    no_trade_approval: bool = True
    no_strategy_approval: bool = True
    no_execution_approval: bool = True
    no_portfolio_approval: bool = True
    no_universe_approval: bool = True
    no_order_sizing: bool = True
    no_position_sizing: bool = True
    no_leverage: bool = True
    no_shorting: bool = True
    no_action_commands: bool = True
    no_network_connection: bool = True
    no_file_read_in_engine: bool = True
    no_database: bool = True
    no_exchange_connection: bool = True
    no_freqtrade_input: bool = True
    no_scheduler: bool = True
    no_web_ui: bool = True
    no_daemon: bool = True
    no_rest_api: bool = True
    research_only: bool = True
    not_trading_advice: bool = True
    has_unsafe_content: bool = False
    has_invalid_path: bool = False
    has_traversal_attempt: bool = False
    has_network_reference: bool = False

    @property
    def is_safe(self) -> bool:
        """True iff all positive safety invariants hold and no negative flags are set."""
        fields = self.__dataclass_fields__
        no_flags = [getattr(self, name) for name in fields if name.startswith("no_")]
        not_flags = [getattr(self, name) for name in fields if name.startswith("not_")]
        has_flags = [getattr(self, name) for name in fields if name.startswith("has_")]
        research_only = [getattr(self, "research_only", True)]
        return all(no_flags) and all(not_flags) and all(research_only) and not any(has_flags)


# ---------------------------------------------------------------------------
# Artifact / invocation / result models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CLIArtifactSummary:
    """Summary of an engine artifact path as an opaque local string."""

    engine_id: str
    artifact_kind: str
    default_path: str
    path_is_opaque_string: bool = True
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.engine_id, str) or not self.engine_id.strip():
            raise ValueError("engine_id must be a non-empty string")
        if not isinstance(self.artifact_kind, str) or not self.artifact_kind.strip():
            raise ValueError("artifact_kind must be a non-empty string")
        if not isinstance(self.default_path, str):
            raise ValueError("default_path must be a string")
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class CLIInvocation:
    """A parsed CLI invocation."""

    command: str
    args: tuple[str, ...] = ()
    output_dir: str | None = None
    output_format: CLIOutputFormat = CLIOutputFormat.TEXT
    dry_run: bool = False
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.command, str) or not self.command.strip():
            raise ValueError("command must be a non-empty string")
        object.__setattr__(self, "args", _coerce_tuple_strs(self.args))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class CLICommandResult:
    """Structured result returned by every command function."""

    command: str
    exit_code: CLIExitCode
    stdout: str
    stderr: str
    output_paths: tuple[str, ...] = ()
    data: Mapping[str, Any] = field(default_factory=dict)
    safety_flags: CLISafetyFlags = field(default_factory=CLISafetyFlags)
    reason_codes: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.command, str) or not self.command.strip():
            raise ValueError("command must be a non-empty string")
        if not isinstance(self.exit_code, CLIExitCode):
            raise ValueError("exit_code must be a CLIExitCode")
        object.__setattr__(self, "output_paths", _coerce_tuple_strs(self.output_paths))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "notes", _coerce_tuple_strs(self.notes))
        if isinstance(self.data, Mapping):
            object.__setattr__(self, "data", MappingProxyType(dict(self.data)))
        else:
            raise ValueError("data must be a Mapping")
