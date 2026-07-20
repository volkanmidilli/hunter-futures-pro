"""SPEC-074 -- Daily Coin Universe Ranking and Native Freqtrade RemotePairList Export.

Transforms existing Hunter research outputs (relative strength, open
interest, eligible universe) into a deterministic, explainable pairlist
published as native RemotePairList JSON for Freqtrade ``file:///``
consumption.  Freqtrade remains solely responsible for strategy execution,
orders, positions, leverage, and entry/exit logic; Hunter is stateless
regarding Freqtrade positions and trades.
"""

from __future__ import annotations

from hunter.pairlist_export.audit import (
    audit_record_to_dict,
    build_audit_record,
    explain_audit_record,
)
from hunter.pairlist_export.models import (
    PAIRLIST_EXPORT_VERSION,
    SPEC_074,
    AuditRecord,
    PairlistExportError,
    PairlistExportSafetyFlags,
    PairlistFingerprintError,
    PairlistOutput,
    PairlistPublishError,
    PairlistRankingConfig,
    PairlistRankingError,
    PairlistValidationError,
    PairScore,
    PublishGateResult,
    RankedPair,
)
from hunter.pairlist_export.publisher import publish_pairlist
from hunter.pairlist_export.ranking_adapter import rank_pairs
from hunter.pairlist_export.snapshot import write_snapshot
from hunter.pairlist_export.validator import (
    run_publish_gate,
    validate_pair_format,
    validate_published_pairlist,
)

__version__ = PAIRLIST_EXPORT_VERSION

__all__ = [
    "PAIRLIST_EXPORT_VERSION",
    "SPEC_074",
    "AuditRecord",
    "PairScore",
    "PairlistExportError",
    "PairlistExportSafetyFlags",
    "PairlistFingerprintError",
    "PairlistOutput",
    "PairlistPublishError",
    "PairlistRankingConfig",
    "PairlistRankingError",
    "PairlistValidationError",
    "PublishGateResult",
    "RankedPair",
    "audit_record_to_dict",
    "build_audit_record",
    "explain_audit_record",
    "publish_pairlist",
    "rank_pairs",
    "run_publish_gate",
    "validate_pair_format",
    "validate_published_pairlist",
    "write_snapshot",
]
