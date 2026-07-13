"""Validator for the Strategy Contract Consumption Adapter (MVP-57)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from hunter.strategy_contract_consumer.models import (
    CONTRADICTORY_INPUT,
    DUPLICATE_PAIR,
    INVALID_MODE,
    INVALID_PAIR,
    INVALID_SAFETY_FLAGS,
    INVALID_SCHEMA,
    INVALID_TIMESTAMP,
    MISSING_HUMAN_APPROVAL_FLAG,
    MISSING_INPUT,
    PAIR_LIST_CONFLICT,
    STALE_INPUT,
    UNSAFE_RESEARCH_FLAG,
    UNSUPPORTED_VERSION,
    VALIDATION_ACCEPTED,
    StrategyContractConsumerConfig,
    StrategyContractConsumerError,
    _coerce_json_mapping,
)

_PAIR_RE = re.compile(r"^([A-Za-z0-9]+)[/_]([A-Za-z0-9]+)$")

_ALLOWED_TOP_LEVEL_FIELDS = frozenset(
    {
        "version",
        "generated_at",
        "research_only",
        "human_approval_required",
        "mode",
        "whitelist",
        "blacklist",
        "safety_flags",
        "metadata",
    }
)

_ALLOWED_MODES = frozenset({"LONG", "SHORT", "BLOCK_ALL"})


def _canonicalize_pair(raw: Any) -> str:
    """Normalize a pair string to uppercase BASE/QUOTE.

    Raises ValueError if the string cannot be parsed as BASE/QUOTE or
    BASE_QUOTE.
    """
    if not isinstance(raw, str):
        raise ValueError(f"pair must be a string, got {type(raw).__name__}")
    match = _PAIR_RE.match(raw.strip())
    if not match:
        raise ValueError(f"pair must match BASE/QUOTE or BASE_QUOTE, got {raw!r}")
    return f"{match.group(1).upper()}/{match.group(2).upper()}"


def _parse_timestamp(value: Any, *, field: str = "generated_at") -> datetime | None:
    """Parse an ISO-8601 timestamp string into a timezone-aware datetime.

    Returns None if the value is not a valid timestamp or lacks timezone info.
    """
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _validate_safety_flags(value: Any) -> tuple[dict[str, bool], str | None]:
    """Validate and normalize safety flags.

    Every value must be a boolean. Unknown flag names are allowed and are
    preserved and deterministically sorted.

    Returns the normalized flags and an optional reason code string.
    """
    if not isinstance(value, dict):
        return {}, INVALID_SAFETY_FLAGS
    flags: dict[str, bool] = {}
    for key, val in value.items():
        if not isinstance(key, str) or not isinstance(val, bool):
            return {}, INVALID_SAFETY_FLAGS
        flags[key] = val
    return dict(sorted(flags.items())), None


def _normalize_pairs(values: Any) -> tuple[tuple[str, ...], str | None]:
    """Normalize a list of pair strings and detect invalid pairs.

    Returns the sorted tuple of canonical pairs and an optional reason code.
    """
    if not isinstance(values, (list, tuple)):
        return (), INVALID_PAIR
    try:
        canonical = [_canonicalize_pair(item) for item in values]
    except ValueError:
        return (), INVALID_PAIR
    return tuple(sorted(canonical)), None


def _detect_duplicates(pairs: tuple[str, ...]) -> bool:
    """Return True if the pair list contains duplicates before deduplication."""
    return len(pairs) != len(set(pairs))


def validate_strategy_contract_input(
    data: dict[str, Any] | None,
    config: StrategyContractConsumerConfig,
    *,
    validated_at: datetime,
) -> dict[str, Any]:
    """Validate a loaded strategy-contract input and return normalized data.

    This function is pure: it performs no file I/O, reads no clocks, and never
    mutates the caller-supplied ``data``. The ``validated_at`` timestamp must be
    injected by the caller.

    The returned mapping contains:

    - ``accepted``: bool
    - ``input_version``: str
    - ``mode``: str
    - ``whitelist``: tuple[str, ...]
    - ``blacklist``: tuple[str, ...]
    - ``safety_flags``: dict[str, bool]
    - ``metadata``: Mapping[str, object]
    - ``generated_at``: datetime | None
    - ``reason_codes``: tuple[str, ...]
    """
    if not isinstance(validated_at, datetime) or validated_at.tzinfo is None:
        raise StrategyContractConsumerError(
            "validated_at must be a timezone-aware datetime",
            reason_code=INVALID_TIMESTAMP,
        )

    if data is None:
        return {
            "accepted": False,
            "input_version": "",
            "mode": "BLOCK_ALL",
            "whitelist": (),
            "blacklist": (),
            "safety_flags": {},
            "metadata": {},
            "generated_at": None,
            "reason_codes": (MISSING_INPUT,),
        }

    reason_codes: set[str] = set()

    # Unknown top-level fields.
    extra_keys = set(data.keys()) - _ALLOWED_TOP_LEVEL_FIELDS
    if extra_keys:
        reason_codes.add(INVALID_SCHEMA)

    # Required fields and basic types.
    required_fields = {
        "version": str,
        "generated_at": str,
        "research_only": bool,
        "human_approval_required": bool,
        "mode": str,
        "whitelist": (list, tuple),
        "blacklist": (list, tuple),
        "safety_flags": dict,
    }
    for field_name, expected_types in required_fields.items():
        if field_name not in data:
            reason_codes.add(INVALID_SCHEMA)
        elif not isinstance(data[field_name], expected_types):
            reason_codes.add(INVALID_SCHEMA)

    metadata: dict[str, object] = {}
    if "metadata" in data:
        if not isinstance(data["metadata"], dict):
            reason_codes.add(INVALID_SCHEMA)
        else:
            try:
                metadata = dict(_coerce_json_mapping(data["metadata"]))
            except TypeError:
                reason_codes.add(INVALID_SCHEMA)

    # research_only flag.
    if data.get("research_only") is not True:
        reason_codes.add(UNSAFE_RESEARCH_FLAG)

    # human_approval_required flag.
    if data.get("human_approval_required") is not True:
        reason_codes.add(MISSING_HUMAN_APPROVAL_FLAG)

    # Version.
    input_version = ""
    if isinstance(data.get("version"), str):
        input_version = data["version"]
        if input_version not in config.supported_versions:
            reason_codes.add(UNSUPPORTED_VERSION)
    elif "version" in data:
        reason_codes.add(INVALID_SCHEMA)

    # Timestamp.
    generated_at = _parse_timestamp(data.get("generated_at"))
    if generated_at is None:
        reason_codes.add(INVALID_TIMESTAMP)
    else:
        if generated_at < validated_at - timedelta(seconds=config.stale_input_threshold_seconds):
            reason_codes.add(STALE_INPUT)
        if generated_at > validated_at + timedelta(seconds=config.future_input_tolerance_seconds):
            reason_codes.add(INVALID_TIMESTAMP)

    # Mode.
    mode = "BLOCK_ALL"
    if isinstance(data.get("mode"), str):
        mode = data["mode"]
        if mode not in _ALLOWED_MODES:
            reason_codes.add(INVALID_MODE)
    elif "mode" in data:
        reason_codes.add(INVALID_SCHEMA)

    # Safety flags.
    safety_flags = {}
    if "safety_flags" in data:
        safety_flags, safety_reason = _validate_safety_flags(data["safety_flags"])
        if safety_reason:
            reason_codes.add(safety_reason)

    # Pairs.
    whitelist: tuple[str, ...] = ()
    blacklist: tuple[str, ...] = ()
    if "whitelist" in data:
        whitelist, pair_reason = _normalize_pairs(data["whitelist"])
        if pair_reason:
            reason_codes.add(pair_reason)
        elif _detect_duplicates(whitelist):
            reason_codes.add(DUPLICATE_PAIR)
    if "blacklist" in data:
        blacklist, pair_reason = _normalize_pairs(data["blacklist"])
        if pair_reason:
            reason_codes.add(pair_reason)
        elif _detect_duplicates(blacklist):
            reason_codes.add(DUPLICATE_PAIR)

    # Whitelist/blacklist conflicts.
    conflicts = set(whitelist) & set(blacklist)
    if conflicts:
        reason_codes.add(PAIR_LIST_CONFLICT)
        whitelist = tuple(sorted(set(whitelist) - conflicts))

    # Contradictory inputs.
    if mode in {"LONG", "SHORT"} and not whitelist:
        reason_codes.add(CONTRADICTORY_INPUT)
    if mode == "BLOCK_ALL" and whitelist:
        reason_codes.add(CONTRADICTORY_INPUT)

    # Fail-closed normalization.
    accepted = not reason_codes
    if not accepted:
        mode = "BLOCK_ALL"
        whitelist = ()
    else:
        reason_codes.add(VALIDATION_ACCEPTED)

    return {
        "accepted": accepted,
        "input_version": input_version,
        "mode": mode,
        "whitelist": whitelist,
        "blacklist": blacklist,
        "safety_flags": safety_flags,
        "metadata": metadata,
        "generated_at": generated_at,
        "reason_codes": tuple(sorted(reason_codes)),
    }
