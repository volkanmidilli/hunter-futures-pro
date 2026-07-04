"""Frozen dataclasses for hunter.release_hardening package.

MVP-33 — Local Research Release Hardening / Consistency Audit.

All dataclasses are frozen. Validation runs in __post_init__. The audit only
accepts caller-provided in-memory declarations and never opens, follows,
traverses, validates, fetches, or executes file references or metadata strings.
Actual export lists, actual module presence lists, and test default paths are
provided by the caller or a trusted test harness; the engine never scans the
filesystem, imports arbitrary modules, or introspects the repository.

The release hardening audit is a human-audit / research artifact only. It is
not a production certification, not a trading readiness gate, and not a trading
signal or recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

RELEASE_HARDENING_VERSION: str = "0.33.0-dev"


class ReleaseHardeningState(Enum):
    """Normalized state of a hardening check result or report."""

    PASS = "pass"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class ReleaseHardeningReasonCode(Enum):
    """Reason codes for hardening check results and reports."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    CONSISTENCY_DEGRADED = "consistency_degraded"
    SAFETY_BLOCKED = "safety_blocked"
    MISSING_REQUIRED_DECLARATION = "missing_required_declaration"
    DUPLICATE_PACKAGE_ID = "duplicate_package_id"
    DUPLICATE_CHECK_ID = "duplicate_check_id"
    UNSAFE_CONTENT = "unsafe_content"
    MISSING_PUBLIC_EXPORT = "missing_public_export"
    MISSING_WRITER_DEFAULT = "missing_writer_default"
    MISSING_SAFETY_NOTICE = "missing_safety_notice"
    VERSION_INCONSISTENT = "version_inconsistent"
    ARTIFACT_PATH_NOT_LOCAL = "artifact_path_not_local"
    TEST_ARTIFACT_NOT_ISOLATED = "test_artifact_not_isolated"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    MISSING_MARKDOWN_DISCLAIMER = "missing_markdown_disclaimer"
    DEFAULT_PATH_NOT_LOCAL = "default_path_not_local"
    PACKAGE_NOT_PRESENT = "package_not_present"
    # Safety advisory invariants
    RESEARCH_ONLY = "research_only"
    NOT_TRADING_ADVICE = "not_trading_advice"
    NO_FILE_INGESTION = "no_file_ingestion"
    NO_NETWORK_CONNECTION = "no_network_connection"
    NO_EXCHANGE_CONNECTION = "no_exchange_connection"
    NO_FREQTRADE_INPUT = "no_freqtrade_input"
    NO_SCHEDULER = "no_scheduler"
    NO_DAEMON = "no_daemon"
    NO_WEB_UI = "no_web_ui"
    NO_DATABASE = "no_database"
    NO_ACTION_COMMANDS_EMITTED = "no_action_commands_emitted"
    HUMAN_RESEARCH_ONLY = "human_research_only"


class ReleaseHardeningSeverity(Enum):
    """Fail severity of a hardening check."""

    ADVISORY = "advisory"
    BLOCKING = "blocking"


class ReleaseHardeningCheckCategory(Enum):
    """Categories of hardening checks."""

    PUBLIC_EXPORTS = "public_exports"
    WRITER_DEFAULTS = "writer_defaults"
    SAFETY_NOTICES = "safety_notices"
    VERSION_CONSISTENCY = "version_consistency"
    ARTIFACT_PATH_POLICY = "artifact_path_policy"
    TEST_ARTIFACT_ISOLATION = "test_artifact_isolation"
    FORBIDDEN_TERM_POLICY = "forbidden_term_policy"
    MARKDOWN_DISCLAIMER_POLICY = "markdown_disclaimer_policy"
    DEFAULT_PATH_LOCALITY = "default_path_locality"
    PACKAGE_PRESENCE = "package_presence"


# String constants for convenient use in reason code tuples and frozensets.
OK = ReleaseHardeningReasonCode.OK.value
NOT_APPLICABLE_RC = ReleaseHardeningReasonCode.NOT_APPLICABLE.value
CONSISTENCY_DEGRADED = ReleaseHardeningReasonCode.CONSISTENCY_DEGRADED.value
SAFETY_BLOCKED = ReleaseHardeningReasonCode.SAFETY_BLOCKED.value
MISSING_REQUIRED_DECLARATION = ReleaseHardeningReasonCode.MISSING_REQUIRED_DECLARATION.value
DUPLICATE_PACKAGE_ID = ReleaseHardeningReasonCode.DUPLICATE_PACKAGE_ID.value
DUPLICATE_CHECK_ID = ReleaseHardeningReasonCode.DUPLICATE_CHECK_ID.value
UNSAFE_CONTENT = ReleaseHardeningReasonCode.UNSAFE_CONTENT.value
MISSING_PUBLIC_EXPORT = ReleaseHardeningReasonCode.MISSING_PUBLIC_EXPORT.value
MISSING_WRITER_DEFAULT = ReleaseHardeningReasonCode.MISSING_WRITER_DEFAULT.value
MISSING_SAFETY_NOTICE = ReleaseHardeningReasonCode.MISSING_SAFETY_NOTICE.value
VERSION_INCONSISTENT = ReleaseHardeningReasonCode.VERSION_INCONSISTENT.value
ARTIFACT_PATH_NOT_LOCAL = ReleaseHardeningReasonCode.ARTIFACT_PATH_NOT_LOCAL.value
TEST_ARTIFACT_NOT_ISOLATED = ReleaseHardeningReasonCode.TEST_ARTIFACT_NOT_ISOLATED.value
FORBIDDEN_TERM_PRESENT = ReleaseHardeningReasonCode.FORBIDDEN_TERM_PRESENT.value
MISSING_MARKDOWN_DISCLAIMER = ReleaseHardeningReasonCode.MISSING_MARKDOWN_DISCLAIMER.value
DEFAULT_PATH_NOT_LOCAL = ReleaseHardeningReasonCode.DEFAULT_PATH_NOT_LOCAL.value
PACKAGE_NOT_PRESENT = ReleaseHardeningReasonCode.PACKAGE_NOT_PRESENT.value
RESEARCH_ONLY = ReleaseHardeningReasonCode.RESEARCH_ONLY.value
NOT_TRADING_ADVICE = ReleaseHardeningReasonCode.NOT_TRADING_ADVICE.value
NO_FILE_INGESTION = ReleaseHardeningReasonCode.NO_FILE_INGESTION.value
NO_NETWORK_CONNECTION = ReleaseHardeningReasonCode.NO_NETWORK_CONNECTION.value
NO_EXCHANGE_CONNECTION = ReleaseHardeningReasonCode.NO_EXCHANGE_CONNECTION.value
NO_FREQTRADE_INPUT = ReleaseHardeningReasonCode.NO_FREQTRADE_INPUT.value
NO_SCHEDULER = ReleaseHardeningReasonCode.NO_SCHEDULER.value
NO_DAEMON = ReleaseHardeningReasonCode.NO_DAEMON.value
NO_WEB_UI = ReleaseHardeningReasonCode.NO_WEB_UI.value
NO_DATABASE = ReleaseHardeningReasonCode.NO_DATABASE.value
NO_ACTION_COMMANDS_EMITTED = ReleaseHardeningReasonCode.NO_ACTION_COMMANDS_EMITTED.value
HUMAN_RESEARCH_ONLY = ReleaseHardeningReasonCode.HUMAN_RESEARCH_ONLY.value

RELEASE_HARDENING_REASON_CODES: tuple[str, ...] = tuple(
    code.value for code in ReleaseHardeningReasonCode
)

RELEASE_HARDENING_BLOCKING_REASON_CODES: frozenset[str] = frozenset({
    UNSAFE_CONTENT,
    FORBIDDEN_TERM_PRESENT,
    MISSING_REQUIRED_DECLARATION,
    DUPLICATE_PACKAGE_ID,
    DUPLICATE_CHECK_ID,
    SAFETY_BLOCKED,
})

RELEASE_HARDENING_ADVISORY_REASON_CODES: frozenset[str] = frozenset(
    RELEASE_HARDENING_REASON_CODES
) - RELEASE_HARDENING_BLOCKING_REASON_CODES

# Superset of forbidden terms for hardening content. Keep all prior safety terms
# (exchange, trading, execution, network, Freqtrade) plus action and approval
# keywords, and explicit certification / trading-readiness phrases.
FORBIDDEN_RELEASE_HARDENING_TERMS: frozenset[str] = frozenset({
    # Explicit certification / readiness phrases required by SPEC-034
    "production ready",
    "live trading",
    "trade approval",
    "execute orders",
    "place orders",
    "buy signal",
    "sell signal",
    "go long",
    "go short",
    "certified",
    # Exchange / network / live data
    "binance",
    "exchange",
    "api_key",
    "secret",
    "token",
    "password",
    "private_key",
    "webhook",
    "url",
    "http",
    "https",
    "ws",
    "wss",
    # Trading / execution
    "buy",
    "buy_now",
    "sell",
    "sell_now",
    "order",
    "orders",
    "position",
    "positions",
    "leverage",
    "shorting",
    "short",
    "margin",
    "liquidation",
    "fill",
    "slippage",
    "fee",
    "market_order",
    "limit_order",
    "stop_loss",
    "take_profit",
    "execute_trade",
    "place_order",
    "live_trade",
    "real_order",
    "position_size",
    "trade_size",
    # Freqtrade
    "freqtrade",
    # Action / approval keywords
    "action_command",
    "action",
    "deploy",
    "execute",
    "start",
    "stop",
    "trigger",
    "approve",
    "approval",
    "go_live",
    "production_ready",
    "execution_ready",
    "strategy_ready",
    "deployment_ready",
    "release_ready",
    "launch_live",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_timezone_aware(value: datetime | None, field_name: str) -> datetime | None:
    """Raise ValueError if value is a naive datetime (tzinfo is None)."""
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _ensure_tuple_of_str(
    value: Iterable[str] | tuple[str, ...] | list[str] | None,
    field_name: str,
) -> tuple[str, ...]:
    """Validate that value is a tuple/list of strings."""
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"{field_name} must contain strings")
        return tuple(value)
    raise ValueError(f"{field_name} must be a tuple or list of strings")


def _ensure_non_empty_str(value: Any | None, field_name: str) -> str:
    """Validate that value is a non-empty string."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _ensure_str_or_none(value: Any | None, field_name: str) -> str | None:
    """Validate that value is a non-empty string or None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or None")
    if not value:
        return None
    return value


def _coerce_str_mapping(value: Mapping[str, str] | dict[str, str] | None) -> Mapping[str, str]:
    """Coerce a string mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        for key, val in value.items():
            if not isinstance(key, str) or not isinstance(val, str):
                raise ValueError("metadata must be a mapping of strings")
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


def _has_forbidden_term(text: str, forbidden_terms: frozenset[str]) -> bool:
    """Case-insensitive substring check for forbidden terms in a single string."""
    if not isinstance(text, str):
        return False
    lower = text.lower()
    return any(term in lower for term in forbidden_terms)


def _check_forbidden_mapping(
    mapping: Mapping[str, Any], forbidden_terms: frozenset[str]
) -> bool:
    """Return True if any key or string value in mapping contains forbidden terms."""
    for key, value in mapping.items():
        if isinstance(key, str) and _has_forbidden_term(key, forbidden_terms):
            return True
        if isinstance(value, str) and _has_forbidden_term(value, forbidden_terms):
            return True
        if isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, str) and _has_forbidden_term(item, forbidden_terms):
                    return True
        if isinstance(value, Mapping):
            if _check_forbidden_mapping(value, forbidden_terms):
                return True
    return False


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReleaseHardeningSafetyFlags:
    """Safety invariants for the release hardening audit."""

    has_blocked: bool = False
    has_degraded: bool = False
    has_forbidden_terms: bool = False
    has_missing_safety_notices: bool = False
    research_only: bool = True
    not_trading_advice: bool = True
    no_trading_signal: bool = True
    no_trade_approval: bool = True
    no_strategy_approval: bool = True
    no_execution_approval: bool = True
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
    not_production_certification: bool = True
    not_trading_readiness_gate: bool = True

    def __post_init__(self) -> None:
        positive_flags = (
            self.research_only,
            self.not_trading_advice,
            self.no_trading_signal,
            self.no_trade_approval,
            self.no_strategy_approval,
            self.no_execution_approval,
            self.no_order_sizing,
            self.no_position_sizing,
            self.no_leverage,
            self.no_shorting,
            self.no_action_commands,
            self.no_network_connection,
            self.no_file_read_in_engine,
            self.no_database,
            self.no_exchange_connection,
            self.no_freqtrade_input,
            self.no_scheduler,
            self.no_web_ui,
            self.no_daemon,
            self.no_rest_api,
            self.not_production_certification,
            self.not_trading_readiness_gate,
        )
        if not all(positive_flags):
            raise ValueError("baseline safety invariants must be True")

    @property
    def is_safe(self) -> bool:
        """Return True when all positive invariants hold and all negative flags are False."""
        return (
            self.research_only
            and self.not_trading_advice
            and self.no_trading_signal
            and self.no_trade_approval
            and self.no_strategy_approval
            and self.no_execution_approval
            and self.no_order_sizing
            and self.no_position_sizing
            and self.no_leverage
            and self.no_shorting
            and self.no_action_commands
            and self.no_network_connection
            and self.no_file_read_in_engine
            and self.no_database
            and self.no_exchange_connection
            and self.no_freqtrade_input
            and self.no_scheduler
            and self.no_web_ui
            and self.no_daemon
            and self.no_rest_api
            and self.not_production_certification
            and self.not_trading_readiness_gate
            and not self.has_blocked
            and not self.has_degraded
            and not self.has_forbidden_terms
            and not self.has_missing_safety_notices
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackageDeclaration:
    """Caller-provided declaration of an existing local research package.

    Expected fields describe the conventions the package should follow. Actual
    fields describe what the caller (or a trusted test harness) observes. The
    release hardening engine never scans the filesystem or imports modules to
    obtain actuals; it only compares caller-provided expected values against
    caller-provided actual values.
    """

    package_id: str
    package_name: str
    module_path: str
    expected_public_exports: tuple[str, ...] = ()
    actual_public_exports: tuple[str, ...] = ()
    expected_modules: tuple[str, ...] = (
        "__init__.py",
        "models.py",
        "engine.py",
        "writer.py",
    )
    actual_modules_present: tuple[str, ...] = ()
    writer_default_paths: tuple[str, ...] = ()
    test_default_paths: tuple[str, ...] = ()
    safety_notices: tuple[str, ...] = ()
    markdown_disclaimer: str = ""
    version: str | None = None

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.package_id, "package_id")
        _ensure_non_empty_str(self.package_name, "package_name")
        _ensure_non_empty_str(self.module_path, "module_path")
        object.__setattr__(
            self, "expected_public_exports", _ensure_tuple_of_str(self.expected_public_exports, "expected_public_exports")
        )
        object.__setattr__(
            self, "actual_public_exports", _ensure_tuple_of_str(self.actual_public_exports, "actual_public_exports")
        )
        object.__setattr__(
            self, "expected_modules", _ensure_tuple_of_str(self.expected_modules, "expected_modules")
        )
        object.__setattr__(
            self, "actual_modules_present", _ensure_tuple_of_str(self.actual_modules_present, "actual_modules_present")
        )
        object.__setattr__(
            self, "writer_default_paths", _ensure_tuple_of_str(self.writer_default_paths, "writer_default_paths")
        )
        object.__setattr__(
            self, "test_default_paths", _ensure_tuple_of_str(self.test_default_paths, "test_default_paths")
        )
        object.__setattr__(
            self, "safety_notices", _ensure_tuple_of_str(self.safety_notices, "safety_notices")
        )
        object.__setattr__(self, "version", _ensure_str_or_none(self.version, "version"))


@dataclass(frozen=True)
class CompletedAuditPackage:
    """Caller-provided reference to an already-produced local audit package.

    Artifact paths and metadata are opaque local strings only. The engine never
    opens, follows, traverses, validates, fetches, or executes them.
    """

    package_id: str
    package_name: str
    artifact_paths: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.package_id, "package_id")
        _ensure_non_empty_str(self.package_name, "package_name")
        object.__setattr__(
            self, "artifact_paths", _ensure_tuple_of_str(self.artifact_paths, "artifact_paths")
        )
        metadata: tuple[tuple[str, str], ...] = ()
        if self.metadata:
            validated: list[tuple[str, str]] = []
            for item in self.metadata:
                if not isinstance(item, (tuple, list)) or len(item) != 2:
                    raise ValueError("metadata must contain key-value pairs")
                key, value = item
                if not isinstance(key, str) or not isinstance(value, str):
                    raise ValueError("metadata keys and values must be strings")
                validated.append((key, value))
            metadata = tuple(validated)
        object.__setattr__(self, "metadata", metadata)


@dataclass(frozen=True)
class ReleaseHardeningCheck:
    """Definition of a single release hardening check.

    `required` only determines whether the check applies to every declared
    package. `severity` is the single fail-severity knob: advisory failures
    produce DEGRADED results, blocking failures produce BLOCKED results.
    """

    check_id: str
    category: str
    description: str
    required: bool
    severity: ReleaseHardeningSeverity
    policy: str

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.check_id, "check_id")
        _ensure_non_empty_str(self.category, "category")
        _ensure_non_empty_str(self.description, "description")
        _ensure_non_empty_str(self.policy, "policy")
        if not isinstance(self.required, bool):
            raise ValueError("required must be a bool")
        if not isinstance(self.severity, ReleaseHardeningSeverity):
            raise ValueError("severity must be a ReleaseHardeningSeverity")
        if self.category not in RELEASE_HARDENING_CHECK_CATEGORIES:
            raise ValueError(f"unsupported category: {self.category}")


@dataclass(frozen=True)
class ReleaseHardeningCheckResult:
    """Result of running one hardening check against one target."""

    check_id: str
    category: str
    package_id: str | None
    state: ReleaseHardeningState
    reason_code: ReleaseHardeningReasonCode
    message: str
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.check_id, "check_id")
        _ensure_non_empty_str(self.category, "category")
        _ensure_non_empty_str(self.message, "message")
        if self.package_id is not None and not isinstance(self.package_id, str):
            raise ValueError("package_id must be a string or None")
        if not isinstance(self.state, ReleaseHardeningState):
            raise ValueError("state must be a ReleaseHardeningState")
        if not isinstance(self.reason_code, ReleaseHardeningReasonCode):
            raise ValueError("reason_code must be a ReleaseHardeningReasonCode")
        object.__setattr__(self, "evidence", _ensure_tuple_of_str(self.evidence, "evidence"))


@dataclass(frozen=True)
class ReleaseHardeningDataQuality:
    """Summary data quality for the release hardening audit."""

    total_checks: int
    pass_count: int
    degraded_count: int
    blocked_count: int
    not_applicable_count: int
    package_count: int
    completed_package_count: int
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for attr in (
            "total_checks",
            "pass_count",
            "degraded_count",
            "blocked_count",
            "not_applicable_count",
            "package_count",
            "completed_package_count",
        ):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if self.total_checks != (
            self.pass_count + self.degraded_count + self.blocked_count + self.not_applicable_count
        ):
            raise ValueError("state counts must sum to total_checks")
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))


@dataclass(frozen=True)
class ReleaseHardeningConfig:
    """Configuration for the release hardening audit."""

    strict: bool = False
    default_json_path: str = "data/release_hardening/release_hardening.json"
    default_csv_path: str = "data/release_hardening/release_hardening_checks.csv"
    default_markdown_path: str = "reports/release_hardening/release_hardening.md"

    def __post_init__(self) -> None:
        if not isinstance(self.strict, bool):
            raise ValueError("strict must be a bool")
        _ensure_non_empty_str(self.default_json_path, "default_json_path")
        _ensure_non_empty_str(self.default_csv_path, "default_csv_path")
        _ensure_non_empty_str(self.default_markdown_path, "default_markdown_path")


@dataclass(frozen=True)
class ReleaseHardeningInput:
    """Caller-provided in-memory inputs for the release hardening audit."""

    packages: tuple[PackageDeclaration, ...]
    completed_packages: tuple[CompletedAuditPackage, ...] = ()
    checks: tuple[ReleaseHardeningCheck, ...] = ()
    project_version: str | None = None
    generated_at: datetime | None = None
    config: ReleaseHardeningConfig = field(default_factory=ReleaseHardeningConfig)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "packages", tuple(self.packages))
        object.__setattr__(self, "completed_packages", tuple(self.completed_packages))
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "project_version", _ensure_str_or_none(self.project_version, "project_version"))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        for pkg in self.packages:
            if not isinstance(pkg, PackageDeclaration):
                raise ValueError("packages must contain PackageDeclaration objects")
        for cp in self.completed_packages:
            if not isinstance(cp, CompletedAuditPackage):
                raise ValueError("completed_packages must contain CompletedAuditPackage objects")
        for check in self.checks:
            if not isinstance(check, ReleaseHardeningCheck):
                raise ValueError("checks must contain ReleaseHardeningCheck objects")
        if not isinstance(self.config, ReleaseHardeningConfig):
            raise ValueError("config must be a ReleaseHardeningConfig")


@dataclass(frozen=True)
class ReleaseHardeningReport:
    """Top-level release hardening audit report."""

    state: ReleaseHardeningState
    reason_codes: tuple[ReleaseHardeningReasonCode, ...]
    checks: tuple[ReleaseHardeningCheckResult, ...]
    data_quality: ReleaseHardeningDataQuality
    safety_flags: ReleaseHardeningSafetyFlags
    generated_at: datetime
    project_version: str | None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.state, ReleaseHardeningState):
            raise ValueError("state must be a ReleaseHardeningState")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "project_version", _ensure_str_or_none(self.project_version, "project_version"))
        if not isinstance(self.checks, tuple):
            raise ValueError("checks must be a tuple")
        if not isinstance(self.data_quality, ReleaseHardeningDataQuality):
            raise ValueError("data_quality must be a ReleaseHardeningDataQuality")
        if not isinstance(self.safety_flags, ReleaseHardeningSafetyFlags):
            raise ValueError("safety_flags must be a ReleaseHardeningSafetyFlags")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        for code in self.reason_codes:
            if not isinstance(code, ReleaseHardeningReasonCode):
                raise ValueError("reason_codes must contain ReleaseHardeningReasonCode values")
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))

    @classmethod
    def blocked(
        cls,
        *,
        input: ReleaseHardeningInput,
        reason_code: ReleaseHardeningReasonCode = ReleaseHardeningReasonCode.UNSAFE_CONTENT,
        generated_at: datetime | None = None,
        safety_flags: ReleaseHardeningSafetyFlags | None = None,
        notes: tuple[str, ...] = (),
    ) -> "ReleaseHardeningReport":
        """Create a deterministic fail-closed blocked hardening report."""
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)
        if safety_flags is None:
            safety_flags = ReleaseHardeningSafetyFlags()
        if reason_code is ReleaseHardeningReasonCode.UNSAFE_CONTENT:
            safety_flags = ReleaseHardeningSafetyFlags(has_forbidden_terms=True)
        data_quality = ReleaseHardeningDataQuality(
            total_checks=0,
            pass_count=0,
            degraded_count=0,
            blocked_count=0,
            not_applicable_count=0,
            package_count=len(input.packages),
            completed_package_count=len(input.completed_packages),
            notes=(),
        )
        return cls(
            state=ReleaseHardeningState.BLOCKED,
            reason_codes=(
                ReleaseHardeningReasonCode.SAFETY_BLOCKED,
                reason_code,
            ),
            checks=(),
            data_quality=data_quality,
            safety_flags=safety_flags,
            generated_at=generated_at,
            project_version=input.project_version,
            notes=notes,
        )


RELEASE_HARDENING_CHECK_CATEGORIES: frozenset[str] = frozenset(
    category.value for category in ReleaseHardeningCheckCategory
)
