"""Engine for the Freqtrade Universe Consumption Adapter (MVP-55).

Deterministic, fail-closed transformation from `ControlledUniverseExportResult`
to a Freqtrade-compatible, research-only universe packet. No external side effects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hunter.controlled_universe_export_adapter.models import (
    BLOCKED_EXPORT,
    MISSING_REPORT_INPUT,
    ControlledUniverseExportResult,
    ControlledUniversePairExportSummary,
)
from hunter.freqtrade_universe_adapter.models import (
    BLOCKED_EXPORT_INPUT,
    CONTRADICTORY_PAIR,
    DUPLICATE_PAIR,
    EMPTY_WHITELIST,
    EXPORT_HUMAN_APPROVAL_REQUIRED,
    EXPORT_RESEARCH_ONLY,
    INVALID_PAIR_FORMAT,
    MISSING_EXPORT_INPUT,
    NO_AUTOMATIC_CONFIG_MUTATION,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    STALE_EXPORT_INPUT,
    FreqtradeUniverseAdapterConfig,
    FreqtradeUniverseAdapterResult,
)
from hunter.strategy_contract import StrategyContractMode


_LONG_CLASSIFICATION = "LONG_RESEARCH"
_SHORT_CLASSIFICATION = "SHORT_RESEARCH"
_NEUTRAL_CLASSIFICATION = "NEUTRAL_RESEARCH"
_WATCHLIST_CLASSIFICATION = "WATCHLIST_RESEARCH"


def _now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def _normalize_pair(pair: str, target_format: str) -> str | None:
    """Normalize a pair string to the configured output format.

    Returns None if the pair is not a valid base/quote or base_quote string.
    """
    if not isinstance(pair, str) or not pair.strip():
        return None
    raw = pair.strip()
    if "/" in raw:
        parts = raw.split("/")
    elif "_" in raw:
        parts = raw.split("_")
    else:
        return None
    if len(parts) != 2:
        return None
    base = parts[0].strip().upper()
    quote = parts[1].strip().upper()
    if not base or not quote:
        return None
    if target_format == "base/quote":
        return f"{base}/{quote}"
    return f"{base}_{quote}"


def _deduplicate_pairs(pairs: tuple[str, ...]) -> tuple[str, ...]:
    """Deduplicate pairs preserving first-occurrence order."""
    seen: set[str] = set()
    result: list[str] = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            result.append(pair)
    return tuple(result)


def _sort_pairs(pairs: tuple[str, ...]) -> tuple[str, ...]:
    """Return pairs sorted lexicographically."""
    return tuple(sorted(pairs))


def _normalize_pair_list(
    pairs: tuple[str, ...],
    target_format: str,
) -> tuple[tuple[str, ...], bool]:
    """Normalize a list of pairs, returning (normalized_pairs, had_invalid).

    Invalid pairs are excluded and the flag is set to True.
    """
    normalized: list[str] = []
    had_invalid = False
    for pair in pairs:
        normalized_pair = _normalize_pair(pair, target_format)
        if normalized_pair is None:
            had_invalid = True
        else:
            normalized.append(normalized_pair)
    return tuple(normalized), had_invalid


def _apply_deduplication_and_contradiction(
    whitelist: tuple[str, ...],
    blacklist: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], bool, bool]:
    """Deduplicate lists and resolve contradictions.

    Returns (final_whitelist, final_blacklist, had_duplicate, had_contradiction).
    """
    whitelist_dedup = _deduplicate_pairs(whitelist)
    blacklist_dedup = _deduplicate_pairs(blacklist)
    had_duplicate = len(whitelist_dedup) != len(whitelist) or len(blacklist_dedup) != len(blacklist)

    whitelist_set = set(whitelist_dedup)
    blacklist_set = set(blacklist_dedup)
    contradictions = whitelist_set & blacklist_set
    had_contradiction = bool(contradictions)

    final_whitelist = _sort_pairs(tuple(p for p in whitelist_dedup if p not in contradictions))
    final_blacklist = _sort_pairs(tuple(set(blacklist_dedup) | contradictions))

    return final_whitelist, final_blacklist, had_duplicate, had_contradiction


def _derive_mode(
    whitelist: tuple[str, ...],
    summary_by_pair: dict[str, ControlledUniversePairExportSummary],
) -> str:
    """Derive the strategy-contract mode from the classifications of included pairs."""
    classifications: set[str] = set()
    for pair in whitelist:
        summary = summary_by_pair.get(pair)
        if summary is not None:
            classification = summary.classification
            if classification in (_LONG_CLASSIFICATION, _SHORT_CLASSIFICATION):
                classifications.add(classification)
    if classifications == {_LONG_CLASSIFICATION}:
        return StrategyContractMode.LONG_RESEARCH_ONLY.value
    if classifications == {_SHORT_CLASSIFICATION}:
        return StrategyContractMode.SHORT_RESEARCH_ONLY.value
    return StrategyContractMode.BLOCK_ALL.value


def _build_pairlist(whitelist: tuple[str, ...]) -> dict[str, Any]:
    """Build a Freqtrade-compatible StaticPairList fragment."""
    return {"method": "StaticPairList", "pairs": list(whitelist)}


def _build_strategy_contract_input(
    whitelist: tuple[str, ...],
    blacklist: tuple[str, ...],
    mode: str,
    metadata: dict[str, str],
) -> dict[str, Any]:
    """Build a strategy-contract-compatible input representation."""
    return {
        "whitelist": list(whitelist),
        "blacklist": list(blacklist),
        "mode": mode,
        "safety_flags": {
            "dry_run": True,
            "live_trading_enabled": False,
            "real_orders_enabled": False,
            "leverage_enabled": False,
            "shorting_enabled": False,
            "strategy_runtime_allowed": False,
            "entry_signals_allowed": False,
            "exit_signals_allowed": False,
        },
        "metadata": dict(metadata),
    }


def _build_safety_flags(export_result: ControlledUniverseExportResult | None) -> dict[str, bool]:
    """Build deterministic safety flags for the adapter result."""
    flags: dict[str, bool] = {
        "research_only": True,
        "human_approval_required": True,
        "no_freqtrade_runtime_connection": True,
        "no_automatic_config_mutation": True,
    }
    if export_result is not None and isinstance(export_result.safety_flags, dict):
        for key, value in export_result.safety_flags.items():
            if isinstance(key, str) and isinstance(value, bool):
                flags[key] = value
    return flags


def _build_reason_codes(
    had_invalid: bool,
    had_duplicate: bool,
    had_contradiction: bool,
    final_whitelist: tuple[str, ...],
    blocked_reason: str | None,
) -> tuple[str, ...]:
    """Build deterministic adapter-specific reason codes."""
    codes: set[str] = {
        EXPORT_RESEARCH_ONLY,
        EXPORT_HUMAN_APPROVAL_REQUIRED,
        NO_FREQTRADE_RUNTIME_CONNECTION,
        NO_AUTOMATIC_CONFIG_MUTATION,
    }
    if blocked_reason is not None:
        codes.add(blocked_reason)
    elif not final_whitelist:
        codes.add(EMPTY_WHITELIST)
    if had_invalid:
        codes.add(INVALID_PAIR_FORMAT)
    if had_duplicate:
        codes.add(DUPLICATE_PAIR)
    if had_contradiction:
        codes.add(CONTRADICTORY_PAIR)
    return tuple(sorted(codes))


def _detect_blocked_reason(
    export_result: ControlledUniverseExportResult | None,
    config: FreqtradeUniverseAdapterConfig,
    now: datetime,
) -> str | None:
    """Return the primary blocking reason, or None if the input can proceed."""
    if export_result is None:
        return MISSING_EXPORT_INPUT
    if not export_result.research_only or not export_result.human_approval_required:
        return BLOCKED_EXPORT_INPUT
    upstream_blocked_codes = {BLOCKED_EXPORT, MISSING_REPORT_INPUT}
    if any(code in upstream_blocked_codes for code in export_result.reason_codes):
        return BLOCKED_EXPORT_INPUT
    age_seconds = (now - export_result.generated_at).total_seconds()
    if age_seconds > config.stale_export_threshold_seconds:
        return STALE_EXPORT_INPUT
    return None


def _build_summary_by_pair(
    per_pair_summary: tuple[ControlledUniversePairExportSummary, ...],
    target_format: str,
) -> dict[str, ControlledUniversePairExportSummary]:
    """Build a lookup from normalized pair to summary."""
    lookup: dict[str, ControlledUniversePairExportSummary] = {}
    for summary in per_pair_summary:
        normalized = _normalize_pair(summary.pair, target_format)
        if normalized is not None:
            lookup[normalized] = summary
    return lookup


def build_freqtrade_universe_adapter_result(
    export_result: ControlledUniverseExportResult | None,
    config: FreqtradeUniverseAdapterConfig | None = None,
) -> FreqtradeUniverseAdapterResult:
    """Build a Freqtrade-compatible universe packet from a controlled export.

    The transformation is deterministic, fail-closed, and research-only. It does
    not integrate with Freqtrade runtime, exchanges, databases, schedulers, or
    live trading systems, and never emits action commands.
    """
    effective_config = config or FreqtradeUniverseAdapterConfig.default()
    now = _now_utc()

    blocked_reason = _detect_blocked_reason(export_result, effective_config, now)

    if export_result is None:
        generated_at = now
        report_id = "missing"
        per_pair_summary: tuple[ControlledUniversePairExportSummary, ...] = ()
        final_whitelist: tuple[str, ...] = ()
        final_blacklist: tuple[str, ...] = ()
        had_invalid = False
        had_duplicate = False
        had_contradiction = False
        metadata: dict[str, str] = {}
    else:
        generated_at = export_result.generated_at
        report_id = export_result.report_id
        metadata = dict(export_result.metadata)
        per_pair_summary = tuple(sorted(export_result.per_pair_summary, key=lambda s: s.pair))

        target_format = effective_config.pair_format

        normalized_blacklist, had_invalid_blacklist = _normalize_pair_list(
            export_result.blacklist, target_format
        )
        final_blacklist = _sort_pairs(_deduplicate_pairs(normalized_blacklist))
        had_duplicate = len(final_blacklist) != len(normalized_blacklist)
        had_contradiction = False
        had_invalid = had_invalid_blacklist

        if blocked_reason is not None:
            final_whitelist = ()
        else:
            normalized_whitelist, had_invalid_whitelist = _normalize_pair_list(
                export_result.whitelist, target_format
            )
            final_whitelist, final_blacklist, dup, contra = _apply_deduplication_and_contradiction(
                normalized_whitelist, final_blacklist
            )
            had_invalid = had_invalid or had_invalid_whitelist
            had_duplicate = had_duplicate or dup
            had_contradiction = contra

    summary_by_pair = _build_summary_by_pair(per_pair_summary, effective_config.pair_format)
    mode = _derive_mode(final_whitelist, summary_by_pair)
    pairlist = _build_pairlist(final_whitelist)
    strategy_contract_input = _build_strategy_contract_input(
        final_whitelist, final_blacklist, mode, metadata
    )
    safety_flags = _build_safety_flags(export_result)
    reason_codes = _build_reason_codes(
        had_invalid,
        had_duplicate,
        had_contradiction,
        final_whitelist,
        blocked_reason,
    )

    return FreqtradeUniverseAdapterResult(
        report_id=report_id,
        generated_at=generated_at,
        whitelist=final_whitelist,
        blacklist=final_blacklist,
        pairlist=pairlist,
        strategy_contract_input=strategy_contract_input,
        per_pair_summary=per_pair_summary,
        research_only=True,
        human_approval_required=True,
        reason_codes=reason_codes,
        safety_flags=safety_flags,
        metadata=metadata,
    )
