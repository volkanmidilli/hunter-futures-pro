"""Publish gate for daily pairlist export (SPEC-074).

The gate is the single fail-closed checkpoint between deterministic ranking
and atomic publish.  It performs no I/O itself: callers pass ranked pairs
and the config, and receive a :class:`PublishGateResult` indicating whether
publish is allowed.  Publish is rejected when the shortlist is empty, below
``min_pairs``, above ``max_pairs``, contains duplicates, or has invalid
pair format -- matching the SPEC-074 daily gate exactly.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from hunter.pairlist_export.audit import build_audit_record, build_audit_record_v2
from hunter.pairlist_export.fingerprint import compute_pairlist_fingerprint
from hunter.pairlist_export.models import (
    REASON_ABOVE_MAX_PAIRS,
    REASON_BELOW_MIN_PAIRS,
    REASON_DUPLICATE_PAIR,
    REASON_EMPTY_UNIVERSE,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_INVALID_PAIR_FORMAT,
    REASON_VALIDATION_FAILED,
    PairlistExportSafetyFlags,
    PairlistOutput,
    PairlistRankingConfig,
    PublishGateResult,
    RankedPair,
)
from hunter.pairlist_export.ranking_input_v2 import RankingProfile

# BASE/USDT:USDT -- Binance USDT-M linear futures pair shape (SPEC-074).
_PAIR_FORMAT_RE = re.compile(r"^[A-Z0-9]{2,20}/USDT:USDT$")


def validate_pair_format(pair: str) -> bool:
    """Return True if ``pair`` matches the required ``BASE/USDT:USDT`` shape."""
    return bool(_PAIR_FORMAT_RE.match(pair))


def find_duplicate_pairs(pairs: tuple[str, ...]) -> tuple[str, ...]:
    """Return the sorted, deduplicated set of pairs appearing more than once."""
    seen: set[str] = set()
    dupes: set[str] = set()
    for pair in pairs:
        if pair in seen:
            dupes.add(pair)
        seen.add(pair)
    return tuple(sorted(dupes))


def run_publish_gate(
    config: PairlistRankingConfig,
    as_of_date: str,
    universe_total: int,
    ranked_pairs: tuple[RankedPair, ...],
) -> PublishGateResult:
    """Run the daily publish gate over a ranked pair set.

    Checks -- all reason codes accumulated, none short-circuiting the
    others -- are: non-empty selection, complete evidence, valid pair
    format, no duplicates, and count within ``[min_pairs, max_pairs]``.
    Only when every check passes is a :class:`PairlistOutput` built and
    ``allow_publish`` set.

    The evidence-completeness check is independent of (and does not
    merely trust) the ranking adapter's own ``selected`` flag: it is the
    gate's own fail-closed re-validation that no pair carrying
    ``INSUFFICIENT_EVIDENCE`` was selected.

    Args:
        config: Ranking and publishing thresholds.
        as_of_date: The ranking's as-of date, ``YYYY-MM-DD``.
        universe_total: Size of the full research universe considered
            before eligibility filtering (for the audit record).
        ranked_pairs: All ranked pairs (both selected and rejected), as
            returned by :func:`hunter.pairlist_export.ranking_adapter.rank_pairs`.

    Returns:
        A :class:`PublishGateResult`.  When ``allow_publish`` is False,
        ``pairlist_output`` is ``None`` and the previous valid pairlist
        must be preserved by the caller (no write should be attempted).
    """
    selected = tuple(p for p in ranked_pairs if p.selected)
    reason_codes: list[str] = []

    if not selected:
        reason_codes.append(REASON_EMPTY_UNIVERSE)

    incomplete_evidence = [
        p.pair for p in selected if REASON_INSUFFICIENT_EVIDENCE in p.reason_codes
    ]
    if incomplete_evidence:
        reason_codes.append(REASON_INSUFFICIENT_EVIDENCE)

    pair_strings = tuple(p.pair for p in selected)

    invalid = [p for p in pair_strings if not validate_pair_format(p)]
    if invalid:
        reason_codes.append(REASON_INVALID_PAIR_FORMAT)

    if find_duplicate_pairs(pair_strings):
        reason_codes.append(REASON_DUPLICATE_PAIR)

    if selected and len(selected) < config.min_pairs:
        reason_codes.append(REASON_BELOW_MIN_PAIRS)
    if len(selected) > config.max_pairs:
        reason_codes.append(REASON_ABOVE_MAX_PAIRS)

    if reason_codes:
        return PublishGateResult(
            allow_publish=False,
            reason_codes=tuple(reason_codes),
            pairlist_output=None,
            error_message="Publish gate rejected pairlist: " + ", ".join(reason_codes),
        )

    audit = build_audit_record(
        as_of_date=as_of_date,
        universe_total=universe_total,
        ranked_pairs=ranked_pairs,
    )

    pairlist_fingerprint = compute_pairlist_fingerprint(
        pairs=pair_strings, refresh_period=config.refresh_period
    )

    output = PairlistOutput(
        pairs=pair_strings,
        refresh_period=config.refresh_period,
        audit=audit,
        fingerprint=pairlist_fingerprint,
        audit_fingerprint=audit.fingerprint,
        safety_flags=PairlistExportSafetyFlags(),
    )

    return PublishGateResult(
        allow_publish=True,
        reason_codes=("OK",),
        pairlist_output=output,
        error_message=None,
    )


def run_publish_gate_v2(
    config: PairlistRankingConfig,
    as_of_date: str,
    universe_total: int,
    ranked_pairs: tuple[RankedPair, ...],
    *,
    ranking_profile: RankingProfile,
    universe_size_at_scoring: int,
    universe_fingerprint: str,
    oi_available: bool,
    source_metadata: Mapping[str, Any] | None = None,
    per_pair_evidence: Mapping[str, tuple[str, ...]] | None = None,
) -> PublishGateResult:
    """Run the SPEC-075 v2 publish gate over a profile-ranked pair set.

    Identical empty/evidence/format/duplicate/count checks to
    :func:`run_publish_gate` -- a single-pair ranking input still passes
    ranking-input generation, but the default ``min_pairs=5`` config
    rejects it here with ``BELOW_MIN_PAIRS``, exactly as under v1.
    """
    selected = tuple(p for p in ranked_pairs if p.selected)
    reason_codes: list[str] = []

    if not selected:
        reason_codes.append(REASON_EMPTY_UNIVERSE)

    incomplete_evidence = [p.pair for p in selected if REASON_INSUFFICIENT_EVIDENCE in p.reason_codes]
    if incomplete_evidence:
        reason_codes.append(REASON_INSUFFICIENT_EVIDENCE)

    pair_strings = tuple(p.pair for p in selected)

    invalid = [p for p in pair_strings if not validate_pair_format(p)]
    if invalid:
        reason_codes.append(REASON_INVALID_PAIR_FORMAT)

    if find_duplicate_pairs(pair_strings):
        reason_codes.append(REASON_DUPLICATE_PAIR)

    if selected and len(selected) < config.min_pairs:
        reason_codes.append(REASON_BELOW_MIN_PAIRS)
    if len(selected) > config.max_pairs:
        reason_codes.append(REASON_ABOVE_MAX_PAIRS)

    if reason_codes:
        return PublishGateResult(
            allow_publish=False,
            reason_codes=tuple(reason_codes),
            pairlist_output=None,
            error_message="Publish gate rejected pairlist: " + ", ".join(reason_codes),
        )

    audit = build_audit_record_v2(
        as_of_date=as_of_date,
        universe_total=universe_total,
        ranked_pairs=ranked_pairs,
        ranking_profile=ranking_profile,
        universe_size_at_scoring=universe_size_at_scoring,
        universe_fingerprint=universe_fingerprint,
        oi_available=oi_available,
        source_metadata=source_metadata,
        per_pair_evidence=per_pair_evidence,
    )

    pairlist_fingerprint = compute_pairlist_fingerprint(pairs=pair_strings, refresh_period=config.refresh_period)

    output = PairlistOutput(
        pairs=pair_strings,
        refresh_period=config.refresh_period,
        audit=audit,
        fingerprint=pairlist_fingerprint,
        audit_fingerprint=audit.fingerprint,
        safety_flags=PairlistExportSafetyFlags(),
    )

    return PublishGateResult(
        allow_publish=True,
        reason_codes=("OK",),
        pairlist_output=output,
        error_message=None,
    )


def validate_published_pairlist(
    payload: dict,
    config: PairlistRankingConfig | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Validate an already-published RemotePairList JSON payload.

    Checks schema shape (``pairs``: list[str], ``refresh_period``: int),
    pair format, and uniqueness unconditionally; count thresholds are
    checked only when ``config`` is supplied (a bare structural check has
    no thresholds to compare against).

    Returns:
        ``(is_valid, reason_codes)``.  ``reason_codes`` is empty iff
        ``is_valid`` is True.
    """
    if not isinstance(payload, dict):
        return False, (REASON_VALIDATION_FAILED,)

    pairs = payload.get("pairs")
    refresh_period = payload.get("refresh_period")

    if not isinstance(pairs, list) or not all(isinstance(p, str) for p in pairs):
        return False, (REASON_VALIDATION_FAILED,)

    reason_codes: list[str] = []

    if not isinstance(refresh_period, int) or isinstance(refresh_period, bool):
        reason_codes.append(REASON_VALIDATION_FAILED)

    if not pairs:
        reason_codes.append(REASON_EMPTY_UNIVERSE)

    if [p for p in pairs if not validate_pair_format(p)]:
        reason_codes.append(REASON_INVALID_PAIR_FORMAT)

    if find_duplicate_pairs(tuple(pairs)):
        reason_codes.append(REASON_DUPLICATE_PAIR)

    if config is not None:
        if len(pairs) < config.min_pairs:
            reason_codes.append(REASON_BELOW_MIN_PAIRS)
        if len(pairs) > config.max_pairs:
            reason_codes.append(REASON_ABOVE_MAX_PAIRS)

    return (not reason_codes), tuple(reason_codes)
