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
    build_audit_record_v2,
    explain_audit_record,
)
from hunter.pairlist_export.feather_adapter import build_ranking_input_v2_from_feather
from hunter.pairlist_export.feather_models import FeatherAdapterError
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
from hunter.pairlist_export.ranking_adapter import rank_pairs, rank_pairs_v2
from hunter.pairlist_export.ranking_input_v2 import (
    SCHEMA_V1,
    SCHEMA_V2,
    ProfileEvidenceIncompleteError,
    ProfileFieldMismatchError,
    RankingInputV2,
    RankingInputV2Error,
    RankingProfile,
    ranking_input_v2_to_dict,
    ranking_input_v2_to_json_text,
)
from hunter.pairlist_export.snapshot import write_snapshot
from hunter.pairlist_export.validator import (
    run_publish_gate,
    run_publish_gate_v2,
    validate_pair_format,
    validate_published_pairlist,
)

__version__ = PAIRLIST_EXPORT_VERSION

__all__ = [
    "PAIRLIST_EXPORT_VERSION",
    "SPEC_074",
    "SCHEMA_V1",
    "SCHEMA_V2",
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
    "RankingInputV2",
    "RankingInputV2Error",
    "RankingProfile",
    "ProfileEvidenceIncompleteError",
    "ProfileFieldMismatchError",
    "FeatherAdapterError",
    "audit_record_to_dict",
    "build_audit_record",
    "build_audit_record_v2",
    "build_ranking_input_v2_from_feather",
    "explain_audit_record",
    "publish_pairlist",
    "rank_pairs",
    "rank_pairs_v2",
    "ranking_input_v2_to_dict",
    "ranking_input_v2_to_json_text",
    "run_publish_gate",
    "run_publish_gate_v2",
    "validate_pair_format",
    "validate_published_pairlist",
    "write_snapshot",
]
