"""Tests for hunter.research_audit_catalog.models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from hunter.research_audit_catalog.models import (
    CATALOG_ARTIFACT_KINDS,
    CATALOG_BLOCKING_REASON_CODES,
    CATALOG_NON_BLOCKING_REASON_CODES,
    CATALOG_REASON_CODES,
    CATALOG_VERSION,
    CATALOG_ERROR,
    DEFAULT_BLOCKED,
    DUPLICATE_ARTIFACT_ID,
    EMPTY_CATALOG,
    FORBIDDEN_CATALOG_TERMS,
    INVALID_ARTIFACT,
    MISSING_ARTIFACTS,
    STALE_ARTIFACT,
    UNSAFE_CATALOG_CONTENT,
    CatalogArtifactKind,
    CatalogConfig,
    CatalogDataQuality,
    CatalogEntry,
    CatalogSafetyFlags,
    CatalogState,
    CatalogSummary,
    ResearchCatalog,
)


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestCatalogState:
    def test_enum_values(self) -> None:
        assert CatalogState.DISABLED.value == "DISABLED"
        assert CatalogState.READY.value == "READY"
        assert CatalogState.BLOCKED.value == "BLOCKED"
        assert CatalogState.UNKNOWN.value == "UNKNOWN"


class TestCatalogArtifactKind:
    def test_enum_values(self) -> None:
        assert CatalogArtifactKind.OBSERVATION_REPORT.value == "OBSERVATION_REPORT"
        assert CatalogArtifactKind.OPERATOR_REVIEW.value == "OPERATOR_REVIEW"
        assert CatalogArtifactKind.REVIEW_INDEX.value == "REVIEW_INDEX"
        assert CatalogArtifactKind.REVIEW_SEARCH.value == "REVIEW_SEARCH"
        assert CatalogArtifactKind.RESEARCH_BUNDLE.value == "RESEARCH_BUNDLE"
        assert CatalogArtifactKind.RESEARCH_CHRONICLE.value == "RESEARCH_CHRONICLE"
        assert CatalogArtifactKind.RESEARCH_DIGEST.value == "RESEARCH_DIGEST"
        assert CatalogArtifactKind.RESEARCH_QUALITY_GATE.value == "RESEARCH_QUALITY_GATE"
        assert CatalogArtifactKind.RESEARCH_HANDOFF.value == "RESEARCH_HANDOFF"
        assert CatalogArtifactKind.RESEARCH_ARCHIVE_MANIFEST.value == "RESEARCH_ARCHIVE_MANIFEST"
        assert CatalogArtifactKind.RESEARCH_RELEASE_NOTES.value == "RESEARCH_RELEASE_NOTES"

    def test_deterministic_order(self) -> None:
        values = [kind.value for kind in CatalogArtifactKind]
        assert values == [
            "OBSERVATION_REPORT",
            "OPERATOR_REVIEW",
            "REVIEW_INDEX",
            "REVIEW_SEARCH",
            "RESEARCH_BUNDLE",
            "RESEARCH_CHRONICLE",
            "RESEARCH_DIGEST",
            "RESEARCH_QUALITY_GATE",
            "RESEARCH_HANDOFF",
            "RESEARCH_ARCHIVE_MANIFEST",
            "RESEARCH_RELEASE_NOTES",
        ]

    def test_catalog_artifact_kinds_constant(self) -> None:
        assert CATALOG_ARTIFACT_KINDS == tuple(CatalogArtifactKind)
        assert len(CATALOG_ARTIFACT_KINDS) == 11


class TestCatalogArtifactKindSpecReferences:
    def test_spec_references_present(self) -> None:
        from hunter.research_audit_catalog.models import CATALOG_ARTIFACT_SPEC_REFERENCE

        assert len(CATALOG_ARTIFACT_SPEC_REFERENCE) == 11
        assert CATALOG_ARTIFACT_SPEC_REFERENCE[CatalogArtifactKind.OBSERVATION_REPORT] == "SPEC-011"
        assert CATALOG_ARTIFACT_SPEC_REFERENCE[CatalogArtifactKind.RESEARCH_RELEASE_NOTES] == "SPEC-021"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------


class TestCatalogReasonCodes:
    def test_reason_codes_complete(self) -> None:
        assert MISSING_ARTIFACTS in CATALOG_REASON_CODES
        assert INVALID_ARTIFACT in CATALOG_REASON_CODES
        assert DUPLICATE_ARTIFACT_ID in CATALOG_REASON_CODES
        assert EMPTY_CATALOG in CATALOG_REASON_CODES
        assert UNSAFE_CATALOG_CONTENT in CATALOG_REASON_CODES
        assert STALE_ARTIFACT in CATALOG_REASON_CODES
        assert CATALOG_ERROR in CATALOG_REASON_CODES
        assert DEFAULT_BLOCKED in CATALOG_REASON_CODES

    def test_blocking_set_excludes_stale(self) -> None:
        assert STALE_ARTIFACT in CATALOG_NON_BLOCKING_REASON_CODES
        assert STALE_ARTIFACT not in CATALOG_BLOCKING_REASON_CODES
        for code in CATALOG_BLOCKING_REASON_CODES:
            assert code in CATALOG_REASON_CODES

    def test_blocking_set_includes_defaults(self) -> None:
        assert MISSING_ARTIFACTS in CATALOG_BLOCKING_REASON_CODES
        assert INVALID_ARTIFACT in CATALOG_BLOCKING_REASON_CODES
        assert DUPLICATE_ARTIFACT_ID in CATALOG_BLOCKING_REASON_CODES
        assert DEFAULT_BLOCKED in CATALOG_BLOCKING_REASON_CODES


# ---------------------------------------------------------------------------
# CatalogConfig
# ---------------------------------------------------------------------------


class TestCatalogConfig:
    def test_default_config(self) -> None:
        config = CatalogConfig()
        assert config.catalog_version == CATALOG_VERSION
        assert config.stale_threshold_seconds == 86400
        assert config.block_on_empty is True
        assert config.block_on_duplicate_ids is True
        assert config.block_on_unsafe_content is True

    def test_invalid_catalog_version(self) -> None:
        with pytest.raises(ValueError, match="catalog_version must be a non-empty string"):
            CatalogConfig(catalog_version="")

    def test_invalid_stale_threshold(self) -> None:
        with pytest.raises(ValueError, match="stale_threshold_seconds must be a positive integer"):
            CatalogConfig(stale_threshold_seconds=0)
        with pytest.raises(ValueError, match="stale_threshold_seconds must be a positive integer"):
            CatalogConfig(stale_threshold_seconds=-1)

    def test_bool_flags_validated(self) -> None:
        with pytest.raises(ValueError, match="block_on_empty must be a bool"):
            CatalogConfig(block_on_empty="yes")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CatalogSafetyFlags
# ---------------------------------------------------------------------------


class TestCatalogSafetyFlags:
    def test_default_flags_are_safe(self) -> None:
        flags = CatalogSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.catalog_feedback_into_execution is False
        assert flags.file_reference_traversal_enabled is False
        assert flags.database_persistence_enabled is False
        assert flags.web_ui_enabled is False
        assert flags.dashboard_enabled is False
        assert flags.runtime_registry_enabled is False
        assert flags.indexer_crawler_enabled is False
        assert flags.catalog_output_is_human_audit_only is True
        assert flags.catalog_output_not_trading_signal is True
        assert flags.catalog_output_not_trade_approval is True
        assert flags.catalog_output_not_release_approval is True
        assert flags.catalog_output_not_deployment_approval is True
        assert flags.catalog_output_not_execution_approval is True
        assert flags.catalog_output_not_strategy_approval is True
        assert flags.catalog_output_not_transaction_permission is True
        assert flags.file_refs_not_traversed is True
        assert flags.artifact_files_not_read is True
        assert flags.no_action_commands_emitted is True

    def test_unsafe_flag_raises(self) -> None:
        with pytest.raises(ValueError, match="unsafe catalog safety flags are enabled"):
            CatalogSafetyFlags(live_trading_enabled=True)
        with pytest.raises(ValueError, match="unsafe catalog safety flags are enabled"):
            CatalogSafetyFlags(catalog_feedback_into_execution=True)
        with pytest.raises(ValueError, match="unsafe catalog safety flags are enabled"):
            CatalogSafetyFlags(runtime_registry_enabled=True)
        with pytest.raises(ValueError, match="unsafe catalog safety flags are enabled"):
            CatalogSafetyFlags(indexer_crawler_enabled=True)
        with pytest.raises(ValueError, match="unsafe catalog safety flags are enabled"):
            CatalogSafetyFlags(file_reference_traversal_enabled=True)
        with pytest.raises(ValueError, match="unsafe catalog safety flags are enabled"):
            CatalogSafetyFlags(database_persistence_enabled=True)
        with pytest.raises(ValueError, match="unsafe catalog safety flags are enabled"):
            CatalogSafetyFlags(dashboard_enabled=True)

    def test_safe_flag_false_raises(self) -> None:
        with pytest.raises(ValueError, match="safe catalog output flags must be True"):
            CatalogSafetyFlags(catalog_output_is_human_audit_only=False)
        with pytest.raises(ValueError, match="safe catalog output flags must be True"):
            CatalogSafetyFlags(catalog_output_not_release_approval=False)
        with pytest.raises(ValueError, match="safe catalog output flags must be True"):
            CatalogSafetyFlags(file_refs_not_traversed=False)

    def test_no_feedback_into_execution_flags(self) -> None:
        flags = CatalogSafetyFlags()
        assert flags.report_feedback_into_execution is False
        assert flags.operator_feedback_into_execution is False
        assert flags.index_feedback_into_execution is False
        assert flags.search_feedback_into_execution is False
        assert flags.bundle_feedback_into_execution is False
        assert flags.chronicle_feedback_into_execution is False
        assert flags.digest_feedback_into_execution is False
        assert flags.quality_gate_feedback_into_execution is False
        assert flags.handoff_feedback_into_execution is False
        assert flags.archive_manifest_feedback_into_execution is False
        assert flags.release_notes_feedback_into_execution is False
        assert flags.catalog_feedback_into_execution is False


# ---------------------------------------------------------------------------
# CatalogEntry
# ---------------------------------------------------------------------------


class TestCatalogEntry:
    def test_valid_entry(self, now: datetime) -> None:
        entry = CatalogEntry(
            entry_id="OBSERVATION_REPORT:report-1",
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
            title="Observation Report 1",
            spec_reference="SPEC-011",
            local_reference="data/observation/latest_observation_report.json",
        )
        assert entry.entry_id == "OBSERVATION_REPORT:report-1"
        assert entry.artifact_id == "report-1"
        assert entry.metadata == {}

    def test_non_ready_requires_reason_codes(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="reason_codes must be non-empty"):
            CatalogEntry(
                entry_id="OBSERVATION_REPORT:report-1",
                artifact_id="report-1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.BLOCKED,
                source_version="1.0",
                generated_at=now,
            )

    def test_empty_entry_id(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="entry_id must be a non-empty string"):
            CatalogEntry(
                entry_id="",
                artifact_id="report-1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            )

    def test_empty_artifact_id(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="artifact_id must be a non-empty string"):
            CatalogEntry(
                entry_id="OBSERVATION_REPORT:report-1",
                artifact_id="",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            )

    def test_empty_source_version(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="source_version must be a non-empty string"):
            CatalogEntry(
                entry_id="OBSERVATION_REPORT:report-1",
                artifact_id="report-1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="",
                generated_at=now,
            )

    def test_naive_datetime(self, now: datetime) -> None:
        naive = now.replace(tzinfo=None)
        with pytest.raises(ValueError, match="generated_at must be timezone-aware"):
            CatalogEntry(
                entry_id="OBSERVATION_REPORT:report-1",
                artifact_id="report-1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=naive,
            )

    def test_invalid_artifact_kind(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="artifact_kind must be CatalogArtifactKind"):
            CatalogEntry(
                entry_id="X:report-1",
                artifact_id="report-1",
                artifact_kind="OBSERVATION_REPORT",  # type: ignore[arg-type]
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            )

    def test_invalid_catalog_state(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="catalog_state must be CatalogState"):
            CatalogEntry(
                entry_id="OBSERVATION_REPORT:report-1",
                artifact_id="report-1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state="READY",  # type: ignore[arg-type]
                source_version="1.0",
                generated_at=now,
            )

    def test_reason_codes_coerced(self, now: datetime) -> None:
        entry = CatalogEntry(
            entry_id="OBSERVATION_REPORT:report-1",
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.BLOCKED,
            source_version="1.0",
            generated_at=now,
            reason_codes=[DEFAULT_BLOCKED],
        )
        assert entry.reason_codes == (DEFAULT_BLOCKED,)

    def test_tags_coerced(self, now: datetime) -> None:
        entry = CatalogEntry(
            entry_id="OBSERVATION_REPORT:report-1",
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
            tags=["mvp-10", "observation"],
        )
        assert entry.tags == ("mvp-10", "observation")

    def test_metadata_coerced(self, now: datetime) -> None:
        entry = CatalogEntry(
            entry_id="OBSERVATION_REPORT:report-1",
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
            metadata={"foo": "bar"},
        )
        assert dict(entry.metadata) == {"foo": "bar"}

    def test_forbidden_term_in_title(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CATALOG_CONTENT"):
            CatalogEntry(
                entry_id="OBSERVATION_REPORT:report-1",
                artifact_id="report-1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
                title="Report with api_key value",
            )

    def test_forbidden_term_in_tag(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CATALOG_CONTENT"):
            CatalogEntry(
                entry_id="OBSERVATION_REPORT:report-1",
                artifact_id="report-1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
                tags=["contains secret"],
            )

    def test_forbidden_term_in_metadata(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CATALOG_CONTENT"):
            CatalogEntry(
                entry_id="OBSERVATION_REPORT:report-1",
                artifact_id="report-1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
                metadata={"note": "deploy now"},
            )

    def test_blocked_factory_does_not_crash(self, now: datetime) -> None:
        entry = CatalogEntry.blocked(
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            generated_at=now,
        )
        assert entry.catalog_state is CatalogState.BLOCKED
        assert entry.source_version == "blocked"
        assert entry.reason_codes == (DEFAULT_BLOCKED,)

    def test_frozen(self, now: datetime) -> None:
        entry = CatalogEntry(
            entry_id="OBSERVATION_REPORT:report-1",
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
        )
        with pytest.raises(FrozenInstanceError):
            entry.artifact_id = "x"  # type: ignore[misc]

    def test_local_reference_is_string_only(self, now: datetime) -> None:
        path = "data/observation/latest_observation_report.json"
        entry = CatalogEntry(
            entry_id="OBSERVATION_REPORT:report-1",
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
            local_reference=path,
        )
        assert entry.local_reference == path


# ---------------------------------------------------------------------------
# CatalogSummary
# ---------------------------------------------------------------------------


class TestCatalogSummary:
    def test_default_summary(self) -> None:
        summary = CatalogSummary(layers_missing=len(CatalogArtifactKind))
        assert summary.total_entries == 0
        assert summary.layers_covered == 0
        assert summary.layers_missing == 11

    def test_state_counts_must_not_exceed_total(self) -> None:
        with pytest.raises(ValueError, match="state counts must not exceed total_entries"):
            CatalogSummary(
                total_entries=1,
                ready_count=2,
                layers_missing=len(CatalogArtifactKind),
            )

    def test_layer_invariant(self) -> None:
        with pytest.raises(ValueError, match=r"layers_covered \+ layers_missing must equal"):
            CatalogSummary()
        with pytest.raises(ValueError, match=r"layers_covered \+ layers_missing must equal"):
            CatalogSummary(layers_covered=1, layers_missing=1)

    def test_kind_counts_keys_validated(self) -> None:
        with pytest.raises(ValueError, match="kind_counts keys must be CatalogArtifactKind"):
            CatalogSummary(
                layers_missing=len(CatalogArtifactKind),
                kind_counts={"OBSERVATION_REPORT": 1},  # type: ignore[dict-item]
            )

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValueError, match="total_entries must be a non-negative integer"):
            CatalogSummary(total_entries=-1, layers_missing=len(CatalogArtifactKind))
        with pytest.raises(ValueError, match="duplicate_id_count must be a non-negative integer"):
            CatalogSummary(duplicate_id_count=-1, layers_missing=len(CatalogArtifactKind))


# ---------------------------------------------------------------------------
# CatalogDataQuality
# ---------------------------------------------------------------------------


class TestCatalogDataQuality:
    def test_default_data_quality(self) -> None:
        dq = CatalogDataQuality()
        assert dq.total_artifacts == 0
        assert dq.has_duplicates is False
        assert dq.has_cross_kind_overlap is False
        assert dq.has_missing_layers is False
        assert dq.has_stale_entries is False

    def test_entry_counts_validated(self) -> None:
        with pytest.raises(ValueError, match="entry category counts must not exceed total_artifacts"):
            CatalogDataQuality(
                total_artifacts=1,
                valid_entries=2,
                blocked_entries=0,
            )

    def test_tuple_fields_validated(self) -> None:
        with pytest.raises(ValueError, match="duplicate_artifact_ids must contain non-empty strings"):
            CatalogDataQuality(duplicate_artifact_ids=[""])

    def test_cross_kind_overlap_fields(self) -> None:
        dq = CatalogDataQuality(
            cross_kind_overlap_ids=("shared-id",),
            has_cross_kind_overlap=True,
        )
        assert dq.cross_kind_overlap_ids == ("shared-id",)
        assert dq.has_cross_kind_overlap is True


# ---------------------------------------------------------------------------
# ResearchCatalog
# ---------------------------------------------------------------------------


class TestResearchCatalog:
    def test_blocked_factory_does_not_crash(self, now: datetime) -> None:
        catalog = ResearchCatalog.blocked(generated_at=now)
        assert catalog.catalog_state is CatalogState.BLOCKED
        assert catalog.catalog_id == "blocked"
        assert catalog.summary.layers_covered == 0
        assert catalog.summary.layers_missing == 11
        assert catalog.reason_codes == (DEFAULT_BLOCKED,)

    def test_blocked_factory_invalid_reason_code(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            ResearchCatalog.blocked(generated_at=now, reason_code="NOT_A_CODE")

    def test_ready_catalog_requires_no_reason_codes(self, now: datetime) -> None:
        entry = CatalogEntry(
            entry_id="OBSERVATION_REPORT:report-1",
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
        )
        summary = CatalogSummary(
            total_entries=1,
            ready_count=1,
            layers_covered=1,
            layers_missing=len(CatalogArtifactKind) - 1,
        )
        dq = CatalogDataQuality(total_artifacts=1, valid_entries=1)
        with pytest.raises(ValueError, match="READY catalogs must not have reason_codes"):
            ResearchCatalog(
                catalog_id="cat-1",
                generated_at=now,
                catalog_state=CatalogState.READY,
                entries=(entry,),
                summary=summary,
                data_quality=dq,
                safety_flags=CatalogSafetyFlags(),
                reason_codes=(DEFAULT_BLOCKED,),
            )

    def test_non_ready_requires_reason_codes(self, now: datetime) -> None:
        summary = CatalogSummary(layers_missing=len(CatalogArtifactKind))
        with pytest.raises(ValueError, match="reason_codes must be non-empty"):
            ResearchCatalog(
                catalog_id="cat-1",
                generated_at=now,
                catalog_state=CatalogState.BLOCKED,
                entries=(),
                summary=summary,
                data_quality=CatalogDataQuality(),
                safety_flags=CatalogSafetyFlags(),
                reason_codes=(),
            )

    def test_empty_catalog_id_rejected(self, now: datetime) -> None:
        summary = CatalogSummary(layers_missing=len(CatalogArtifactKind))
        with pytest.raises(ValueError, match="catalog_id must be a non-empty string"):
            ResearchCatalog(
                catalog_id="",
                generated_at=now,
                catalog_state=CatalogState.BLOCKED,
                entries=(),
                summary=summary,
                data_quality=CatalogDataQuality(),
                safety_flags=CatalogSafetyFlags(),
                reason_codes=(DEFAULT_BLOCKED,),
            )

    def test_naive_generated_at_rejected(self) -> None:
        summary = CatalogSummary(layers_missing=len(CatalogArtifactKind))
        naive = datetime.now().replace(tzinfo=None)
        with pytest.raises(ValueError, match="generated_at must be timezone-aware"):
            ResearchCatalog(
                catalog_id="cat-1",
                generated_at=naive,
                catalog_state=CatalogState.BLOCKED,
                entries=(),
                summary=summary,
                data_quality=CatalogDataQuality(),
                safety_flags=CatalogSafetyFlags(),
                reason_codes=(DEFAULT_BLOCKED,),
            )

    def test_entries_must_be_tuple(self, now: datetime) -> None:
        summary = CatalogSummary(layers_missing=len(CatalogArtifactKind))
        with pytest.raises(ValueError, match="entries must be a tuple"):
            ResearchCatalog(
                catalog_id="cat-1",
                generated_at=now,
                catalog_state=CatalogState.BLOCKED,
                entries=[],  # type: ignore[arg-type]
                summary=summary,
                data_quality=CatalogDataQuality(),
                safety_flags=CatalogSafetyFlags(),
                reason_codes=(DEFAULT_BLOCKED,),
            )

    def test_reason_codes_validated(self, now: datetime) -> None:
        summary = CatalogSummary(layers_missing=len(CatalogArtifactKind))
        with pytest.raises(ValueError, match="unsupported reason code"):
            ResearchCatalog(
                catalog_id="cat-1",
                generated_at=now,
                catalog_state=CatalogState.BLOCKED,
                entries=(),
                summary=summary,
                data_quality=CatalogDataQuality(),
                safety_flags=CatalogSafetyFlags(),
                reason_codes=("NOT_A_CODE",),
            )

    def test_frozen(self, now: datetime) -> None:
        catalog = ResearchCatalog.blocked(generated_at=now)
        with pytest.raises(FrozenInstanceError):
            catalog.catalog_id = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Forbidden terms
# ---------------------------------------------------------------------------


class TestForbiddenCatalogTerms:
    def test_terms_include_execution_and_approval_keywords(self) -> None:
        assert "api_key" in FORBIDDEN_CATALOG_TERMS
        assert "secret" in FORBIDDEN_CATALOG_TERMS
        assert "deploy" in FORBIDDEN_CATALOG_TERMS
        assert "execute" in FORBIDDEN_CATALOG_TERMS
        assert "leverage" in FORBIDDEN_CATALOG_TERMS
        assert "binance" in FORBIDDEN_CATALOG_TERMS

    def test_terms_are_lowercase(self) -> None:
        for term in FORBIDDEN_CATALOG_TERMS:
            assert term == term.lower()
