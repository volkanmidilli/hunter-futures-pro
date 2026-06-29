"""Frozen dataclasses for hunter.research_release_notes package.

MVP-20 — Local Research Release Notes / Audit Change Summary.

All dataclasses are frozen. Validation runs in __post_init__.
File references and metadata strings are local strings only and are never
traversed, opened, followed, validated, or executed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any


RELEASE_NOTES_VERSION = "1.0"

_MVP_NUMBER_RE = re.compile(r"MVP-(\d+)")


class ReleaseNotesState(Enum):
    """Overall release notes state."""

    READY = "ready"
    WARN = "warn"
    BLOCK = "block"
    UNKNOWN = "unknown"


class ReleaseNotesKind(Enum):
    """Kind of release notes document."""

    RESEARCH_RELEASE_NOTES = "research_release_notes"


class ReleaseNotesSectionKind(Enum):
    """Deterministic section ordering."""

    OVERVIEW = "overview"
    VERSION_AND_SCOPE = "version_and_scope"
    ARTIFACT_CHAIN = "artifact_chain"
    COMPLETED_MVPS = "completed_mvps"
    KNOWN_GAPS = "known_gaps"
    SAFETY_BOUNDARIES = "safety_boundaries"
    HUMAN_REVIEW_GUIDE = "human_review_guide"
    APPENDIX_REFERENCES = "appendix_references"


class ReleaseNotesChangeSeverity(Enum):
    """Severity of a release notes change item."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


RELEASE_NOTES_REASON_CODES = (
    "EMPTY_RELEASE_NOTES",
    "INVALID_CONFIG",
    "UNSAFE_CONFIG",
    "MISSING_OVERVIEW",
    "MISSING_VERSION_AND_SCOPE",
    "MISSING_ARTIFACT_CHAIN",
    "MISSING_COMPLETED_MVPS",
    "MISSING_KNOWN_GAPS",
    "MISSING_SAFETY_BOUNDARIES",
    "MISSING_HUMAN_REVIEW_GUIDE",
    "MISSING_APPENDIX_REFERENCES",
    "EMPTY_SECTION",
    "INVALID_CHANGE_ITEM",
    "UNSAFE_CHANGE_ITEM_CONTENT",
    "UNSAFE_SECTION_CONTENT",
    "MISSING_SPEC_REFERENCE",
    "UNRESOLVED_BLOCKERS",
    "UNSAFE_RELEASE_NOTES_CONTENT",
    "RELEASE_NOTES_ERROR",
)

RELEASE_NOTES_BLOCKING_REASON_CODES = tuple(
    rc for rc in RELEASE_NOTES_REASON_CODES if rc != "EMPTY_RELEASE_NOTES"
)

# Superset of FORBIDDEN_ARCHIVE_MANIFEST_TERMS from MVP-19 plus action-command
# and release/deployment-approval keywords. Generated safety notices are not
# subjected to this check; it applies only to caller-provided content.
FORBIDDEN_RELEASE_NOTES_TERMS = frozenset({
    # Credential / secret terms (from MVP-19)
    "api_key",
    "secret",
    "exchange_credentials",
    "executable_instructions",
    "private_key",
    "password",
    "token",
    "auth",
    # Trading execution terms (from MVP-19)
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
    "order",
    "position",
    "leverage",
    "margin",
    "liquidation",
    # Additional trading terms (from MVP-19)
    "live_trade",
    "real_order",
    "market_order",
    "limit_order",
    "position_size",
    # Release/deployment readiness terms (must not imply approval)
    "go_live",
    "production_ready",
    "execution_ready",
    "strategy_ready",
    "deployment_ready",
    "release_ready",
    "launch_live",
    # Action-command keywords (must not emit action commands)
    "deploy",
    "execute",
    "run",
    "start",
    "stop",
    "trigger",
})


_RELEASE_NOTES_ARTIFACT_LOCAL_REFERENCE = {
    "OBSERVATION_REPORT": "data/observation/latest_observation_report.json",
    "OPERATOR_REVIEW": "data/review/latest_review_audit_record.json",
    "REVIEW_INDEX": "data/review_index/latest_review_index.json",
    "REVIEW_SEARCH": "data/review_search/latest_search_result.json",
    "RESEARCH_BUNDLE": "data/research_bundle/latest_research_bundle.json",
    "RESEARCH_CHRONICLE": "data/chronicle/latest_research_chronicle.json",
    "RESEARCH_DIGEST": "data/research_digest/latest_research_digest.json",
    "RESEARCH_QUALITY_GATE": "data/research_quality_gate/latest_research_quality_gate.json",
    "RESEARCH_HANDOFF": "data/research_handoff/latest_research_handoff_packet.json",
    "RESEARCH_ARCHIVE_MANIFEST": "data/research_archive_manifest/latest_research_archive_manifest.json",
}

_RELEASE_NOTES_ARTIFACT_SPEC_REFERENCE = {
    "OBSERVATION_REPORT": "SPEC-011",
    "OPERATOR_REVIEW": "SPEC-012",
    "REVIEW_INDEX": "SPEC-013",
    "REVIEW_SEARCH": "SPEC-014",
    "RESEARCH_BUNDLE": "SPEC-015",
    "RESEARCH_CHRONICLE": "SPEC-016",
    "RESEARCH_DIGEST": "SPEC-017",
    "RESEARCH_QUALITY_GATE": "SPEC-018",
    "RESEARCH_HANDOFF": "SPEC-019",
    "RESEARCH_ARCHIVE_MANIFEST": "SPEC-020",
}

RELEASE_NOTES_ARTIFACT_INFO: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        family: (
            _RELEASE_NOTES_ARTIFACT_LOCAL_REFERENCE[family],
            _RELEASE_NOTES_ARTIFACT_SPEC_REFERENCE[family],
        )
        for family in _RELEASE_NOTES_ARTIFACT_LOCAL_REFERENCE
    }
)

_VALID_OUTPUT_FORMATS = ("json", "markdown", "both")
_VALID_RELEASE_NOTES_STATES = ("READY", "WARN", "BLOCK", "UNKNOWN")
_VALID_CHANGE_SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")

_SECTION_TITLES = {
    ReleaseNotesSectionKind.OVERVIEW: "Overview",
    ReleaseNotesSectionKind.VERSION_AND_SCOPE: "Version and Scope",
    ReleaseNotesSectionKind.ARTIFACT_CHAIN: "Artifact Chain",
    ReleaseNotesSectionKind.COMPLETED_MVPS: "Completed MVPs",
    ReleaseNotesSectionKind.KNOWN_GAPS: "Known Gaps",
    ReleaseNotesSectionKind.SAFETY_BOUNDARIES: "Safety Boundaries",
    ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE: "Human Review Guide",
    ReleaseNotesSectionKind.APPENDIX_REFERENCES: "Appendix References",
}


def _has_unsafe_release_notes_content(text: str | None) -> bool:
    """Case-insensitive check for forbidden terms.

    Does not open, traverse, validate, follow, or execute file references.
    """
    if not isinstance(text, str):
        return False
    lower = text.lower()
    for term in FORBIDDEN_RELEASE_NOTES_TERMS:
        if term in lower:
            return True
    return False


def _check_unsafe_mapping(mapping: Mapping[str, Any]) -> bool:
    """Return True if any key or string value contains forbidden terms."""
    for key, value in mapping.items():
        if isinstance(key, str) and _has_unsafe_release_notes_content(key):
            return True
        if isinstance(value, str) and _has_unsafe_release_notes_content(value):
            return True
        if isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, str) and _has_unsafe_release_notes_content(item):
                    return True
        if isinstance(value, Mapping):
            if _check_unsafe_mapping(value):
                return True
    return False


def _validate_no_unsafe_content(
    text: str | None,
    metadata: Mapping[str, Any] | None,
) -> None:
    """Raise ValueError if text or metadata contain forbidden terms."""
    if text is not None and _has_unsafe_release_notes_content(text):
        raise ValueError("UNSAFE_RELEASE_NOTES_CONTENT")
    if metadata is not None and _check_unsafe_mapping(metadata):
        raise ValueError("UNSAFE_RELEASE_NOTES_CONTENT")


def _coerce_tuple_of_str(value: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Coerce a tuple or list of items into a tuple of non-empty strings."""
    if isinstance(value, tuple):
        return tuple(str(x) for x in value if x)
    if isinstance(value, list):
        return tuple(str(x) for x in value if x)
    raise ValueError("reason_codes must be a tuple or list of strings")


def _coerce_tuple_of_change_items(
    value: tuple[ReleaseNotesChangeItem, ...] | list[ReleaseNotesChangeItem],
) -> tuple[ReleaseNotesChangeItem, ...]:
    """Coerce a tuple or list into a tuple of ReleaseNotesChangeItem instances."""
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    raise ValueError("change_items must be a tuple or list of ReleaseNotesChangeItem")


def _coerce_tuple_of_sections(
    value: tuple[ReleaseNotesSectionKind, ...] | list[ReleaseNotesSectionKind],
) -> tuple[ReleaseNotesSectionKind, ...]:
    """Coerce a tuple or list into a tuple of ReleaseNotesSectionKind enum instances."""
    if isinstance(value, (tuple, list)):
        result = []
        for item in value:
            if not isinstance(item, ReleaseNotesSectionKind):
                raise ValueError(
                    "required_sections must contain ReleaseNotesSectionKind enum instances"
                )
            result.append(item)
        return tuple(result)
    raise ValueError("required_sections must be a tuple or list of ReleaseNotesSectionKind")


def _coerce_mapping(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


def _normalize_change_severity(raw: str | None) -> str:
    """Normalize a change severity string to one of the valid values."""
    if raw is None:
        return "INFO"
    normalized = str(raw).strip().upper()
    if normalized not in _VALID_CHANGE_SEVERITIES:
        raise ValueError(
            f"severity must be one of {_VALID_CHANGE_SEVERITIES}, got {raw!r}"
        )
    return normalized


def _severity_priority(severity: str) -> int:
    """Return sort priority for a severity string (lower = higher priority)."""
    return {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
        "INFO": 4,
    }.get(severity, 5)


def _extract_mvp_number(related_mvp: str) -> int:
    """Extract MVP number from a string like 'MVP-15'. Returns 0 if not found."""
    if not isinstance(related_mvp, str):
        return 0
    match = _MVP_NUMBER_RE.search(related_mvp)
    if match:
        return int(match.group(1))
    return 0


@dataclass(frozen=True)
class ReleaseNotesConfig:
    """Configuration for release notes generation.

    Unsafe flags must remain False. dry_run must remain True.
    """

    version: str = RELEASE_NOTES_VERSION
    generated_at: datetime | None = None
    output_format: str = "both"
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    block_on_unknown: bool = True
    release_version: str = ""
    release_title: str = ""
    required_sections: tuple[ReleaseNotesSectionKind, ...] = field(
        default_factory=lambda: tuple(ReleaseNotesSectionKind)
    )
    include_release_notes: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")
        if self.output_format not in _VALID_OUTPUT_FORMATS:
            raise ValueError(
                f"output_format must be one of {_VALID_OUTPUT_FORMATS}"
            )
        if self.dry_run is not True:
            raise ValueError("dry_run must be True")
        for attr in (
            "live_trading_enabled",
            "real_orders_enabled",
            "leverage_enabled",
            "shorting_enabled",
        ):
            if getattr(self, attr) is not False:
                raise ValueError(f"{attr} must be False")
        if not isinstance(self.block_on_unknown, bool):
            raise ValueError("block_on_unknown must be a bool")
        _coerce_tuple_of_sections(self.required_sections)
        if self.release_version != "" and (
            not isinstance(self.release_version, str) or not self.release_version.strip()
        ):
            raise ValueError("release_version must be a non-empty string when provided")
        if not isinstance(self.release_title, str):
            raise ValueError("release_title must be a string")
        _validate_no_unsafe_content(self.release_title, None)


@dataclass(frozen=True)
class ReleaseNotesSafetyFlags:
    """Fail-closed safety flags for release notes output."""

    # Runtime safety flags
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False

    # Output safety flags
    release_notes_output_is_human_audit_only: bool = True
    release_notes_output_not_trading_signal: bool = True
    release_notes_output_not_trade_approval: bool = True
    release_notes_output_not_execution_readiness: bool = True
    release_notes_output_not_strategy_readiness: bool = True
    release_notes_output_not_release_approval: bool = True
    release_notes_output_not_deployment_approval: bool = True
    release_notes_output_not_transaction_permission: bool = True
    release_notes_output_not_for_execution: bool = True
    release_notes_output_not_for_strategy: bool = True
    release_notes_output_not_for_freqtrade: bool = True
    release_notes_output_not_for_order: bool = True
    release_notes_output_not_for_exchange: bool = True

    # Feedback safety flags
    release_notes_feedback_into_execution: bool = False
    cross_layer_feedback_into_execution: bool = False

    # Advisory flags
    file_refs_not_traversed: bool = True
    artifact_files_not_read: bool = True
    no_action_commands_emitted: bool = True

    def __post_init__(self) -> None:
        if self.dry_run is not True:
            raise ValueError("dry_run must be True")
        for attr in (
            "live_trading_enabled",
            "real_orders_enabled",
            "leverage_enabled",
            "shorting_enabled",
            "release_notes_feedback_into_execution",
            "cross_layer_feedback_into_execution",
        ):
            if getattr(self, attr) is not False:
                raise ValueError("unsafe release notes safety flags are enabled")
        for attr in (
            "release_notes_output_is_human_audit_only",
            "release_notes_output_not_trading_signal",
            "release_notes_output_not_trade_approval",
            "release_notes_output_not_execution_readiness",
            "release_notes_output_not_strategy_readiness",
            "release_notes_output_not_release_approval",
            "release_notes_output_not_deployment_approval",
            "release_notes_output_not_transaction_permission",
            "release_notes_output_not_for_execution",
            "release_notes_output_not_for_strategy",
            "release_notes_output_not_for_freqtrade",
            "release_notes_output_not_for_order",
            "release_notes_output_not_for_exchange",
            "file_refs_not_traversed",
            "artifact_files_not_read",
            "no_action_commands_emitted",
        ):
            if getattr(self, attr) is not True:
                raise ValueError("safe release notes output flags must be True")


@dataclass(frozen=True)
class ReleaseNotesChangeItem:
    """One change item in the release notes."""

    title: str
    description: str = ""
    change_kind: str = ""
    severity: str = "INFO"
    related_mvp: str = ""
    spec_reference: str = ""
    related_references: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a non-empty string")
        object.__setattr__(
            self, "severity", _normalize_change_severity(self.severity)
        )
        object.__setattr__(
            self, "related_references", _coerce_tuple_of_str(self.related_references)
        )
        object.__setattr__(
            self, "metadata", _coerce_mapping(self.metadata)
        )
        _validate_no_unsafe_content(self.title, None)
        _validate_no_unsafe_content(self.description, None)
        _validate_no_unsafe_content(self.change_kind, None)
        _validate_no_unsafe_content(self.related_mvp, None)
        _validate_no_unsafe_content(self.spec_reference, None)
        _validate_no_unsafe_content(None, self.metadata)


@dataclass(frozen=True)
class ReleaseNotesSection:
    """One section in the release notes."""

    section_kind: ReleaseNotesSectionKind
    title: str = ""
    section_notes: str = ""
    change_items: tuple[ReleaseNotesChangeItem, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.section_kind, ReleaseNotesSectionKind):
            raise ValueError("section_kind must be a ReleaseNotesSectionKind")
        object.__setattr__(
            self, "change_items", _coerce_tuple_of_change_items(self.change_items)
        )
        object.__setattr__(
            self, "metadata", _coerce_mapping(self.metadata)
        )
        if self.title == "":
            object.__setattr__(self, "title", _SECTION_TITLES.get(self.section_kind, ""))
        if not isinstance(self.title, str):
            raise ValueError("title must be a string")
        _validate_no_unsafe_content(self.title, None)
        _validate_no_unsafe_content(self.section_notes, None)
        _validate_no_unsafe_content(None, self.metadata)


@dataclass(frozen=True)
class ReleaseNotesSummary:
    """Aggregated summary across all release notes sections."""

    total_sections: int = 0
    total_change_items: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    release_notes_state: str = "UNKNOWN"
    reason_code_counts: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType({})
    )
    release_notes: str = ""

    def __post_init__(self) -> None:
        for attr in (
            "total_sections",
            "total_change_items",
            "critical_count",
            "high_count",
            "medium_count",
            "low_count",
            "info_count",
        ):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if (
            self.critical_count
            + self.high_count
            + self.medium_count
            + self.low_count
            + self.info_count
            != self.total_change_items
        ):
            raise ValueError(
                "critical_count + high_count + medium_count + low_count + info_count must equal total_change_items"
            )
        if self.release_notes_state not in _VALID_RELEASE_NOTES_STATES:
            raise ValueError(
                f"release_notes_state must be one of {_VALID_RELEASE_NOTES_STATES}"
            )
        object.__setattr__(
            self, "reason_code_counts", _coerce_mapping(self.reason_code_counts)
        )
        _validate_no_unsafe_content(self.release_notes, None)


@dataclass(frozen=True)
class ReleaseNotesDataQuality:
    """Data-quality metrics for the release notes."""

    completeness_pct: float = 0.0
    coverage_pct: float = 0.0
    sections_present: int = 0
    sections_missing: int = 0
    total_sections: int = 0
    change_items_with_specs: int = 0
    change_items_without_specs: int = 0
    reason: str = ""

    def __post_init__(self) -> None:
        for attr in ("completeness_pct", "coverage_pct"):
            value = getattr(self, attr)
            if not isinstance(value, (int, float)) or value < 0.0 or value > 100.0:
                raise ValueError(f"{attr} must be between 0.0 and 100.0")
        for attr in (
            "sections_present",
            "sections_missing",
            "total_sections",
            "change_items_with_specs",
            "change_items_without_specs",
        ):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if self.sections_present + self.sections_missing != self.total_sections:
            raise ValueError(
                "sections_present + sections_missing must equal total_sections"
            )
        _validate_no_unsafe_content(self.reason, None)


@dataclass(frozen=True)
class ResearchReleaseNotes:
    """Full research release notes container."""

    release_notes_id: str
    generated_at: datetime
    version: str = RELEASE_NOTES_VERSION
    release_version: str = ""
    release_title: str = ""
    kind: ReleaseNotesKind = field(
        default_factory=lambda: ReleaseNotesKind.RESEARCH_RELEASE_NOTES
    )
    release_notes_state: ReleaseNotesState = field(
        default_factory=lambda: ReleaseNotesState.UNKNOWN
    )
    sections: tuple[ReleaseNotesSection, ...] = ()
    summary: ReleaseNotesSummary = field(default_factory=ReleaseNotesSummary)
    data_quality: ReleaseNotesDataQuality = field(
        default_factory=ReleaseNotesDataQuality
    )
    safety_flags: ReleaseNotesSafetyFlags = field(
        default_factory=ReleaseNotesSafetyFlags
    )
    config: ReleaseNotesConfig = field(default_factory=ReleaseNotesConfig)
    reason_codes: tuple[str, ...] = ()
    document_notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.release_notes_id, str) or not self.release_notes_id:
            raise ValueError("release_notes_id must be a non-empty string")
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        if not isinstance(self.kind, ReleaseNotesKind):
            raise ValueError("kind must be a ReleaseNotesKind")
        if not isinstance(self.release_notes_state, ReleaseNotesState):
            raise ValueError("release_notes_state must be a ReleaseNotesState")
        if not isinstance(self.sections, tuple):
            raise ValueError("sections must be a tuple")
        for section in self.sections:
            if not isinstance(section, ReleaseNotesSection):
                raise ValueError("sections must contain ReleaseNotesSection instances")
        object.__setattr__(
            self, "reason_codes", _coerce_tuple_of_str(self.reason_codes)
        )
        _validate_no_unsafe_content(self.document_notes, None)

    @classmethod
    def blocked(
        cls,
        reason: str,
        generated_at: datetime,
        *,
        config: ReleaseNotesConfig | None = None,
    ) -> "ResearchReleaseNotes":
        """Factory for a blocked release notes with safe notes."""
        if config is None:
            config = ReleaseNotesConfig()
        safe_note = (
            f"Release notes blocked: {reason}. "
            "This release notes document is a human-audit / contractor-handoff artifact only. "
            "It is not release approval, not publish approval, not a trading signal, "
            "not trade approval, not execution readiness, not strategy readiness, "
            "and not transaction permission."
        )
        return cls(
            release_notes_id=f"release-notes:{config.version}:{generated_at.strftime('%Y-%m-%dT%H:%M:%S.%f')}",
            generated_at=generated_at,
            version=config.version,
            release_version=config.release_version,
            release_title=config.release_title,
            kind=ReleaseNotesKind.RESEARCH_RELEASE_NOTES,
            release_notes_state=ReleaseNotesState.BLOCK,
            summary=ReleaseNotesSummary(
                release_notes_state="BLOCK",
                release_notes=safe_note,
            ),
            config=config,
            reason_codes=(reason,),
            document_notes=safe_note,
        )
