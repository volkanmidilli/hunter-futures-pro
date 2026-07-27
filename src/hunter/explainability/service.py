"""Lookup service for SPEC-078 ``hunter explain <SYMBOL>``.

Resolves a user-supplied symbol to the canonical Binance USDT perpetual
Freqtrade form (``BTC`` -> ``BTC/USDT:USDT``), loads the latest
*successful* recorded run, and returns a fail-closed lookup result.  The
service never infers missing information and never recomputes any
selection decision: every answer comes from the recorded artifacts or is
an explicit fail-closed status (``NO_SUCCESSFUL_RUN``, ``NOT_IN_UNIVERSE``,
``NOT_RECORDED``, ``ARTIFACT_INVALID``).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from hunter.explainability.models import (
    CandidateExplanationRecord,
    ExplainabilityRunManifest,
    ExplainabilityStorageError,
    ExplainabilitySymbolError,
    REASON_ARTIFACT_INVALID,
    REASON_LEGACY_RUN_INCOMPLETE,
    REASON_NO_SUCCESSFUL_RUN,
    REASON_NOT_IN_UNIVERSE,
    REASON_NOT_RECORDED,
)
from hunter.explainability.storage import (
    default_explainability_dir,
    read_candidate,
    read_latest_pointer,
    read_manifest,
)

LOOKUP_OK = "OK"

ENV_EXPLAINABILITY_DIR = "HUNTER_EXPLAINABILITY_DIR"

_BASE_RE = re.compile(r"^[A-Z0-9]{2,20}$")
_FULL_RE = re.compile(r"^([A-Z0-9]{2,20})/USDT(?::USDT)?$")


def normalize_explain_symbol(symbol: str) -> str:
    """Normalize a CLI symbol to ``BASE/USDT:USDT``.

    Accepts a bare base (``BTC``), a spot-style pair (``BTC/USDT``), or the
    full futures form (``BTC/USDT:USDT``); all normalize to the Binance
    USDT-M perpetual Freqtrade format.  Anything else -- empty, whitespace,
    path-traversal or otherwise unsafe content, unsupported quotes -- is
    rejected with :class:`ExplainabilitySymbolError` (fail closed).
    """
    if not isinstance(symbol, str) or not symbol.strip():
        raise ExplainabilitySymbolError("symbol must be a non-empty string")
    cleaned = symbol.strip().upper()
    if any(ch.isspace() for ch in cleaned):
        raise ExplainabilitySymbolError(f"symbol contains whitespace: {symbol!r}")
    if ".." in cleaned or "\\" in cleaned or cleaned.startswith(("/", "~")):
        raise ExplainabilitySymbolError(f"unsafe symbol content: {symbol!r}")
    if _BASE_RE.match(cleaned):
        return f"{cleaned}/USDT:USDT"
    match = _FULL_RE.match(cleaned)
    if match:
        return f"{match.group(1)}/USDT:USDT"
    raise ExplainabilitySymbolError(
        f"symbol {symbol!r} is not a valid base or BASE/USDT[:USDT] pair"
    )


def resolve_explainability_dir(explainability_dir: str | Path | None = None) -> Path:
    """Resolve the artifact root: CLI argument > env var > repo default."""
    if explainability_dir is not None:
        return Path(explainability_dir)
    env_value = os.environ.get(ENV_EXPLAINABILITY_DIR)
    if env_value:
        return Path(env_value)
    return default_explainability_dir()


@dataclass(frozen=True)
class ExplainLookupResult:
    """Fail-closed result of an explain lookup.

    ``status`` is ``OK`` only when a validated canonical record was loaded.
    ``record`` is None for every non-OK status; ``manifest`` is present
    whenever the latest successful run could be read (so ``NOT_IN_UNIVERSE``
    still reports the real run id).
    """

    status: str
    reason_codes: tuple[str, ...]
    pair: str
    record: CandidateExplanationRecord | None = None
    manifest: ExplainabilityRunManifest | None = None


def explain_candidate(
    pair: str,
    explainability_dir: str | Path | None = None,
) -> ExplainLookupResult:
    """Look up the explanation for a canonical pair in the latest run.

    ``pair`` must already be normalized (see :func:`normalize_explain_symbol`).
    """
    root = resolve_explainability_dir(explainability_dir)

    try:
        pointer = read_latest_pointer(root)
    except ExplainabilityStorageError:
        return ExplainLookupResult(
            status=REASON_ARTIFACT_INVALID,
            reason_codes=(REASON_ARTIFACT_INVALID,),
            pair=pair,
        )
    if pointer is None:
        return ExplainLookupResult(
            status=REASON_NO_SUCCESSFUL_RUN,
            reason_codes=(REASON_NO_SUCCESSFUL_RUN,),
            pair=pair,
        )

    try:
        manifest = read_manifest(root, pointer["run_id"])
    except ExplainabilityStorageError:
        return ExplainLookupResult(
            status=REASON_ARTIFACT_INVALID,
            reason_codes=(REASON_ARTIFACT_INVALID,),
            pair=pair,
        )

    if not manifest.decision_records_complete:
        # The run is identified, but the original run did not record enough
        # information to explain any candidate. Fail closed -- never guess.
        return ExplainLookupResult(
            status=REASON_LEGACY_RUN_INCOMPLETE,
            reason_codes=(REASON_LEGACY_RUN_INCOMPLETE,),
            pair=pair,
            manifest=manifest,
        )

    if pair not in manifest.eligible_pairs:
        return ExplainLookupResult(
            status=REASON_NOT_IN_UNIVERSE,
            reason_codes=(REASON_NOT_IN_UNIVERSE,),
            pair=pair,
            manifest=manifest,
        )

    try:
        record = read_candidate(root, manifest.run_id, pair)
    except ExplainabilityStorageError:
        return ExplainLookupResult(
            status=REASON_ARTIFACT_INVALID,
            reason_codes=(REASON_ARTIFACT_INVALID,),
            pair=pair,
            manifest=manifest,
        )
    if record is None:
        return ExplainLookupResult(
            status=REASON_NOT_RECORDED,
            reason_codes=(REASON_NOT_RECORDED,),
            pair=pair,
            manifest=manifest,
        )

    return ExplainLookupResult(
        status=LOOKUP_OK,
        reason_codes=tuple(record.final_reason_codes),
        pair=pair,
        record=record,
        manifest=manifest,
    )
