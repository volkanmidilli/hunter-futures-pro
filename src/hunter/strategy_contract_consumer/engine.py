"""Engine for the Strategy Contract Consumption Adapter (MVP-57)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from hunter.strategy_contract_consumer.loader import load_strategy_contract_input
from hunter.strategy_contract_consumer.models import (
    INVALID_TIMESTAMP,
    MISSING_INPUT,
    StrategyContractConsumerConfig,
    StrategyContractConsumerError,
    ValidatedStrategyContext,
)
from hunter.strategy_contract_consumer.validator import validate_strategy_contract_input


def _json_default(value: Any) -> Any:
    """Fallback JSON encoder for deterministic canonicalization.

    Converts sequences to lists.  Everything else is left to raise a
    serialization error so the caller receives a deterministic failure.
    """
    if isinstance(value, (list, tuple)):
        return list(value)
    raise TypeError(f"object of type {type(value).__name__} is not JSON serializable")


def _canonical_json(data: Any) -> str:
    """Return a deterministic, compact canonical JSON representation."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_json_default)


def _source_fingerprint(loaded: dict[str, Any] | None, source_path: str, reason_code: str | None) -> str:
    """Compute a SHA-256 fingerprint from the canonical JSON of the loaded data.

    When the loader succeeded, the fingerprint is computed from the canonical
    JSON of the loaded dict.  When the loader failed, a canonical diagnostic
    envelope ``{"reason": ..., "source_path": ...}`` is hashed instead — this
    is deterministic and does **not** falsely represent an empty payload as the
    original source content.  No file reads occur here (SPEC-057 §Integration).
    """
    if loaded is not None:
        payload = _canonical_json(loaded)
    else:
        envelope: dict[str, Any] = {
            "reason": reason_code or MISSING_INPUT,
            "source_path": source_path,
        }
        payload = _canonical_json(envelope)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_path(source: Any) -> str:
    """Return a stable source-path string for audit metadata."""
    if source is None:
        return "<missing>"
    if isinstance(source, (str, Path)):
        return str(source)
    if isinstance(source, Mapping):
        return "<mapping>"
    return str(source)


def _validated_context_from_result(
    *,
    accepted: bool,
    input_version: str,
    mode: str,
    whitelist: tuple[str, ...],
    blacklist: tuple[str, ...],
    safety_flags: dict[str, bool],
    metadata: Mapping[str, object],
    reason_codes: tuple[str, ...],
    source_path: str,
    source_fingerprint: str,
    validated_at: datetime,
    generated_at: datetime | None,
) -> ValidatedStrategyContext:
    """Construct a fail-closed immutable context from validation results."""
    if not accepted:
        mode = "BLOCK_ALL"
        whitelist = ()
    return ValidatedStrategyContext(
        accepted=accepted,
        validated_at=validated_at,
        source_fingerprint=source_fingerprint,
        source_path=source_path,
        input_version=input_version if input_version is not None else "",
        mode=mode,
        whitelist=whitelist,
        blacklist=blacklist,
        safety_flags=safety_flags,
        metadata=metadata,
        reason_codes=reason_codes,
        generated_at=generated_at,
    )


def build_validated_strategy_context(
    source: Path | str | Mapping[str, Any] | None,
    config: StrategyContractConsumerConfig,
    *,
    validated_at: datetime,
) -> ValidatedStrategyContext:
    """Load, validate, and build an immutable research-only strategy context.

    This is the main research-only entry point. It is pure: it performs no
    file writes, reads no hidden clocks, and does not integrate with Freqtrade
    runtime, exchanges, databases, schedulers, or live trading systems.
    """
    if not isinstance(validated_at, datetime) or validated_at.tzinfo is None:
        raise StrategyContractConsumerError(
            "validated_at must be a timezone-aware datetime",
            reason_code=INVALID_TIMESTAMP,
        )

    source_path = _source_path(source)
    loaded: dict[str, Any] | None
    loader_reason_code: str | None = None

    try:
        loaded = load_strategy_contract_input(source)
    except StrategyContractConsumerError as exc:
        loaded = None
        loader_reason_code = exc.reason_code

    if loaded is None:
        if loader_reason_code is None:
            loader_reason_code = MISSING_INPUT
        source_fingerprint = _source_fingerprint(loaded, source_path, loader_reason_code)
        return _validated_context_from_result(
            accepted=False,
            input_version="",
            mode="BLOCK_ALL",
            whitelist=(),
            blacklist=(),
            safety_flags={},
            metadata={},
            reason_codes=(loader_reason_code,),
            source_path=source_path,
            source_fingerprint=source_fingerprint,
            validated_at=validated_at,
            generated_at=None,
        )

    source_fingerprint = _source_fingerprint(loaded, source_path, None)

    result = validate_strategy_contract_input(
        loaded,
        config,
        validated_at=validated_at,
    )

    return _validated_context_from_result(
        accepted=result["accepted"],
        input_version=result["input_version"],
        mode=result["mode"],
        whitelist=result["whitelist"],
        blacklist=result["blacklist"],
        safety_flags=result["safety_flags"],
        metadata=result["metadata"],
        reason_codes=result["reason_codes"],
        source_path=source_path,
        source_fingerprint=source_fingerprint,
        validated_at=validated_at,
        generated_at=result["generated_at"],
    )
