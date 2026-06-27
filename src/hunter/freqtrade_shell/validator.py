"""Shell validator for Freqtrade Dry-Run Strategy Shell.

Validates runtime JSON payloads with fail-closed priority rules.
No file reading, no writing, no network calls, no Freqtrade imports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hunter.freqtrade_shell.models import (
    DRY_RUN_DISABLED,
    INVALID_SIGNAL_ACTION,
    INVALID_STRATEGY_STATE,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_METADATA_EXPOSED,
    NOT_DRY_RUN_READY,
    REAL_ORDERS_ENABLED,
    RUNTIME_JSON_INVALID,
    RUNTIME_JSON_INVALID_TIMESTAMP,
    RUNTIME_JSON_MISSING,
    RUNTIME_JSON_VERSION_MISMATCH,
    SHORTING_ENABLED,
    SHORT_RESEARCH_METADATA_EXPOSED,
    SIGNAL_BLOCKED,
    STALE_RUNTIME_CONTEXT,
    VALIDATION_ERROR,
    ShellRuntimeConfig,
    ShellSignalExposure,
    ShellState,
    ShellValidationResult,
)


# Expected signal_action values from MVP-8
_LONG_SIGNAL = "EXPOSE_LONG_RESEARCH_SIGNAL"
_SHORT_SIGNAL = "EXPOSE_SHORT_RESEARCH_SIGNAL"
_BLOCK_SIGNAL = "BLOCK_SIGNAL"
_NO_SIGNAL = "NO_SIGNAL"


def validate_runtime_payload(
    payload: dict[str, object] | None,
    config: ShellRuntimeConfig | None = None,
    now: datetime | None = None,
) -> ShellValidationResult:
    """Validate a runtime JSON payload with fail-closed priority rules.

    Returns the first blocking reason only.  On unexpected exceptions,
    returns ``VALIDATION_ERROR`` via the ``blocked()`` factory.

    Args:
        payload: The parsed runtime JSON dict, or ``None`` if the file was
            missing or unreadable.
        config: Shell configuration.  Defaults to a safe ``ShellRuntimeConfig``.
        now: Reference timestamp for staleness checks.  Defaults to UTC now.

    Returns:
        ``ShellValidationResult`` with ``shell_state`` and ``signal_exposure``
        determined by the first failing rule.
    """
    if config is None:
        config = ShellRuntimeConfig()
    if now is None:
        now = datetime.now(timezone.utc)

    try:
        return _validate_payload(payload, config, now)
    except Exception:
        return ShellValidationResult.blocked((VALIDATION_ERROR,))


def _validate_payload(
    payload: dict[str, object] | None,
    config: ShellRuntimeConfig,
    now: datetime,
) -> ShellValidationResult:
    """Internal validation — raises on unexpected errors."""

    # 1. Missing payload
    if payload is None:
        return ShellValidationResult.blocked((RUNTIME_JSON_MISSING,))

    # 2. Required fields
    required_fields = {
        "version",
        "timestamp",
        "strategy_state",
        "strategy_mode",
        "signal_action",
        "dry_run",
        "live_trading_enabled",
        "real_orders_enabled",
        "leverage_enabled",
        "shorting_enabled",
    }
    if not isinstance(payload, dict) or not required_fields.issubset(payload.keys()):
        return ShellValidationResult.blocked((RUNTIME_JSON_INVALID,))

    # 3. Version check
    if payload.get("version") != "1.0":
        return ShellValidationResult.blocked((RUNTIME_JSON_VERSION_MISMATCH,))

    # 4. dry_run must be True
    if payload.get("dry_run") is not True:
        return ShellValidationResult.blocked((DRY_RUN_DISABLED,))

    # 5. live_trading_enabled must be False
    if payload.get("live_trading_enabled") is not False:
        return ShellValidationResult.blocked((LIVE_TRADING_ENABLED,))

    # 6. real_orders_enabled must be False
    if payload.get("real_orders_enabled") is not False:
        return ShellValidationResult.blocked((REAL_ORDERS_ENABLED,))

    # 7. leverage_enabled must be False
    if payload.get("leverage_enabled") is not False:
        return ShellValidationResult.blocked((LEVERAGE_ENABLED,))

    # 8. shorting_enabled must be False
    if payload.get("shorting_enabled") is not False:
        return ShellValidationResult.blocked((SHORTING_ENABLED,))

    # 9. Timestamp validity
    ts = parse_runtime_timestamp(payload.get("timestamp"))
    if ts is None:
        return ShellValidationResult.blocked((RUNTIME_JSON_INVALID_TIMESTAMP,))

    # 10. Staleness
    if is_runtime_payload_stale(payload, config, now):
        return ShellValidationResult.blocked((STALE_RUNTIME_CONTEXT,))

    # 11. strategy_state validity
    strategy_state = payload.get("strategy_state")
    if strategy_state not in {s.value for s in ShellState}:
        return ShellValidationResult.blocked((INVALID_STRATEGY_STATE,))

    # 12. signal_action validity
    signal_action = payload.get("signal_action")
    if signal_action not in {_LONG_SIGNAL, _SHORT_SIGNAL, _BLOCK_SIGNAL, _NO_SIGNAL}:
        return ShellValidationResult.blocked((INVALID_SIGNAL_ACTION,))

    # 13. signal_action blocked
    if signal_action in (_BLOCK_SIGNAL, _NO_SIGNAL):
        return ShellValidationResult.blocked((SIGNAL_BLOCKED,))

    # 14. strategy_state readiness
    if strategy_state != ShellState.DRY_RUN_READY.value:
        return ShellValidationResult.blocked((NOT_DRY_RUN_READY,))

    # Allowed paths
    if signal_action == _LONG_SIGNAL:
        return ShellValidationResult(
            timestamp=now,
            shell_state=ShellState.DRY_RUN_READY,
            signal_exposure=ShellSignalExposure.EXPOSE_LONG_RESEARCH_METADATA,
            reason_codes=(LONG_RESEARCH_METADATA_EXPOSED,),
            runtime_json_present=True,
            runtime_json_valid=True,
            runtime_json_stale=False,
            runtime_version="1.0",
            runtime_strategy_state=str(strategy_state),
            runtime_strategy_mode=str(payload.get("strategy_mode", "")),
            runtime_signal_action=str(signal_action),
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            allow_real_trade_signals=False,
            allow_entry_columns=False,
            allow_exit_columns=False,
            version="1.0",
        )

    if signal_action == _SHORT_SIGNAL:
        return ShellValidationResult(
            timestamp=now,
            shell_state=ShellState.DRY_RUN_READY,
            signal_exposure=ShellSignalExposure.EXPOSE_SHORT_RESEARCH_METADATA,
            reason_codes=(SHORT_RESEARCH_METADATA_EXPOSED,),
            runtime_json_present=True,
            runtime_json_valid=True,
            runtime_json_stale=False,
            runtime_version="1.0",
            runtime_strategy_state=str(strategy_state),
            runtime_strategy_mode=str(payload.get("strategy_mode", "")),
            runtime_signal_action=str(signal_action),
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            allow_real_trade_signals=False,
            allow_entry_columns=False,
            allow_exit_columns=False,
            version="1.0",
        )

    # Fallback — should not reach here due to rule 12/13
    return ShellValidationResult.blocked((DEFAULT_BLOCKED,))


def is_runtime_payload_stale(
    payload: dict[str, object],
    config: ShellRuntimeConfig,
    now: datetime,
) -> bool:
    """Return ``True`` if the payload timestamp is older than the configured max age.

    Args:
        payload: Parsed runtime JSON dict (must contain ``timestamp``).
        config: Shell configuration with ``max_runtime_age_seconds``.
        now: Reference timestamp for age calculation.

    Returns:
        ``True`` if stale, ``False`` otherwise.  Returns ``True`` on any
        unexpected error (fail-closed).
    """
    try:
        ts = parse_runtime_timestamp(payload.get("timestamp"))
        if ts is None:
            return True
        age = (now - ts).total_seconds()
        return age > config.max_runtime_age_seconds
    except Exception:
        return True


def parse_runtime_timestamp(value: object) -> datetime | None:
    """Parse an ISO-8601 timestamp string into a timezone-aware ``datetime``.

    Accepts strings with ``Z`` suffix or timezone offset.  Returns ``None``
    on any parse failure or if the result is not timezone-aware.

    Args:
        value: The raw timestamp value from the JSON payload.

    Returns:
        A timezone-aware ``datetime`` or ``None``.
    """
    if not isinstance(value, str):
        return None
    try:
        # Python 3.11+ supports Z suffix directly
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt
    except Exception:
        return None


def map_signal_action_to_exposure(signal_action: str) -> ShellSignalExposure:
    """Map an MVP-8 signal action to a shell signal exposure.

    Args:
        signal_action: The ``signal_action`` string from the runtime JSON.

    Returns:
        ``ShellSignalExposure`` matching the signal action, or ``BLOCKED``
        for unknown values.
    """
    mapping = {
        _LONG_SIGNAL: ShellSignalExposure.EXPOSE_LONG_RESEARCH_METADATA,
        _SHORT_SIGNAL: ShellSignalExposure.EXPOSE_SHORT_RESEARCH_METADATA,
    }
    return mapping.get(signal_action, ShellSignalExposure.BLOCKED)
