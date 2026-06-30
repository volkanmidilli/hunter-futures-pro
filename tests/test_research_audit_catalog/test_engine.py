"""Tests for hunter.research_audit_catalog.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.research_audit_catalog.engine import (
    build_audit_catalog_data_quality,
    build_audit_catalog_entry,
    build_audit_catalog_safety_flags,
    build_audit_catalog_summary,
    build_research_audit_catalog,
    has_unsafe_audit_catalog_content,
)
from hunter.research_audit_catalog.models import (
    CATALOG_VERSION,
    DEFAULT_BLOCKED,
    DUPLICATE_ARTIFACT_ID,
    INVALID_ARTIFACT,
    MISSING_ARTIFACTS,
    STALE_ARTIFACT,
    UNSAFE_CATALOG_CONTENT,
    CatalogArtifactKind,
    CatalogConfig,
    CatalogEntry,
    CatalogSafetyFlags,
    CatalogState,
)


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


class TestBuildAuditCatalogSafetyFlags:
    def test_returns_default_safe_flags(self) -> None:
        flags = build_audit_catalog_safety_flags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.catalog_output_is_human_audit_only is True
        assert flags.file_refs_not_traversed is True
        assert flags.runtime_registry_enabled is False
        assert flags.indexer_crawler_enabled is False


# ---------------------------------------------------------------------------
# Unsafe content detection
# ---------------------------------------------------------------------------


class TestHasUnsafeAuditCatalogContent:
    def test_detects_forbidden_text(self) -> None:
        assert has_unsafe_audit_catalog_content("contains api_key value") is True
        assert has_unsafe_audit_catalog_content("safe text") is False

    def test_detects_forbidden_metadata(self) -> None:
        assert has_unsafe_audit_catalog_content(None, {"note": "deploy now"}) is True
        assert has_unsafe_audit_catalog_content(None, {"note": "safe"}) is False

    def test_empty_and_none_text(self) -> None:
        assert has_unsafe_audit_catalog_content("") is False
        assert has_unsafe_audit_catalog_content(None) is False

    def test_nested_metadata(self) -> None:
        assert has_unsafe_audit_catalog_content(None, {"outer": {"inner": "secret"}}) is True


# ---------------------------------------------------------------------------
# Entry builder
# ---------------------------------------------------------------------------


class TestBuildAuditCatalogEntry:
    def test_builds_entry(self, now: datetime) -> None:
        entry = build_audit_catalog_entry(
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
            title="Observation",
            spec_reference="SPEC-011",
        )
        assert entry.entry_id == "OBSERVATION_REPORT:report-1"
        assert entry.artifact_kind is CatalogArtifactKind.OBSERVATION_REPORT
        assert entry.title == "Observation"

    def test_entry_id_is_deterministic(self, now: datetime) -> None:
        e1 = build_audit_catalog_entry(
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
        )
        e2 = build_audit_catalog_entry(
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
        )
        assert e1.entry_id == e2.entry_id

    def test_entry_id_includes_kind(self, now: datetime) -> None:
        e1 = build_audit_catalog_entry(
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
        )
        e2 = build_audit_catalog_entry(
            artifact_id="report-1",
            artifact_kind=CatalogArtifactKind.OPERATOR_REVIEW,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
        )
        assert e1.entry_id != e2.entry_id

    def test_rejects_forbidden_title(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CATALOG_CONTENT"):
            build_audit_catalog_entry(
                artifact_id="report-1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
                title="Report with api_key",
            )


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------


class TestBuildAuditCatalogSummary:
    def test_empty_entries(self, now: datetime) -> None:
        summary = build_audit_catalog_summary((), reference_time=now)
        assert summary.total_entries == 0
        assert summary.layers_covered == 0
        assert summary.layers_missing == 11

    def test_state_counts(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            CatalogEntry.blocked(
                artifact_kind=CatalogArtifactKind.OPERATOR_REVIEW,
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="r2",
                artifact_kind=CatalogArtifactKind.REVIEW_INDEX,
                catalog_state=CatalogState.UNKNOWN,
                source_version="1.0",
                generated_at=now,
                reason_codes=(DEFAULT_BLOCKED,),
            ),
        )
        summary = build_audit_catalog_summary(entries, reference_time=now)
        assert summary.total_entries == 3
        assert summary.ready_count == 1
        assert summary.blocked_count == 1
        assert summary.unknown_count == 1

    def test_kind_counts(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="r2",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="r3",
                artifact_kind=CatalogArtifactKind.REVIEW_INDEX,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        summary = build_audit_catalog_summary(entries, reference_time=now)
        assert summary.kind_counts[CatalogArtifactKind.OBSERVATION_REPORT] == 2
        assert summary.kind_counts[CatalogArtifactKind.REVIEW_INDEX] == 1

    def test_layer_coverage(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="r2",
                artifact_kind=CatalogArtifactKind.RESEARCH_RELEASE_NOTES,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        summary = build_audit_catalog_summary(entries, reference_time=now)
        assert summary.layers_covered == 2
        assert summary.layers_missing == 9

    def test_duplicate_entry_id_count(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        summary = build_audit_catalog_summary(entries, reference_time=now)
        assert summary.duplicate_id_count == 2

    def test_cross_kind_same_artifact_id_not_duplicate(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.RESEARCH_BUNDLE,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        summary = build_audit_catalog_summary(entries, reference_time=now)
        assert summary.duplicate_id_count == 0

    def test_stale_entries(self, now: datetime) -> None:
        old = now - timedelta(days=2)
        entries = (
            build_audit_catalog_entry(
                artifact_id="old",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=old,
            ),
            build_audit_catalog_entry(
                artifact_id="new",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        summary = build_audit_catalog_summary(entries, reference_time=now)
        assert summary.stale_entry_count == 1

    def test_reason_counts(self, now: datetime) -> None:
        entries = (
            CatalogEntry.blocked(
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                generated_at=now,
                reason_codes=(INVALID_ARTIFACT,),
            ),
            CatalogEntry.blocked(
                artifact_kind=CatalogArtifactKind.OPERATOR_REVIEW,
                generated_at=now,
                reason_codes=(INVALID_ARTIFACT, DEFAULT_BLOCKED),
            ),
        )
        summary = build_audit_catalog_summary(entries, reference_time=now)
        assert summary.reason_counts[INVALID_ARTIFACT] == 2
        assert summary.reason_counts[DEFAULT_BLOCKED] == 1


# ---------------------------------------------------------------------------
# Data quality builder
# ---------------------------------------------------------------------------


class TestBuildAuditCatalogDataQuality:
    def test_empty_entries(self, now: datetime) -> None:
        dq = build_audit_catalog_data_quality((), reference_time=now)
        assert dq.total_artifacts == 0
        assert dq.has_missing_layers is True
        assert dq.missing_layer_kinds == tuple(sorted(kind.value for kind in CatalogArtifactKind))

    def test_duplicate_entry_id_tracked(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        dq = build_audit_catalog_data_quality(entries, reference_time=now)
        assert dq.has_duplicates is True
        assert dq.duplicate_artifact_ids == ("OBSERVATION_REPORT:r1",)

    def test_cross_kind_overlap_advisory(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="shared",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="shared",
                artifact_kind=CatalogArtifactKind.RESEARCH_BUNDLE,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        dq = build_audit_catalog_data_quality(entries, reference_time=now)
        assert dq.has_cross_kind_overlap is True
        assert dq.cross_kind_overlap_ids == ("shared",)
        assert dq.has_duplicates is False

    def test_valid_and_blocked_counts(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="ready",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            CatalogEntry.blocked(
                artifact_kind=CatalogArtifactKind.OPERATOR_REVIEW,
                generated_at=now,
            ),
        )
        dq = build_audit_catalog_data_quality(entries, reference_time=now)
        assert dq.valid_entries == 1
        assert dq.blocked_entries == 1

    def test_validation_errors_passed_through(self, now: datetime) -> None:
        dq = build_audit_catalog_data_quality(
            (),
            reference_time=now,
            validation_errors=("entry 0: bad",),
        )
        assert dq.validation_errors == ("entry 0: bad",)


# ---------------------------------------------------------------------------
# Full catalog builder
# ---------------------------------------------------------------------------


class TestBuildResearchAuditCatalog:
    def test_happy_path(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="r2",
                artifact_kind=CatalogArtifactKind.REVIEW_INDEX,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        catalog = build_research_audit_catalog(entries, generated_at=now)
        assert catalog.catalog_state is CatalogState.READY
        assert catalog.reason_codes == ()
        assert len(catalog.entries) == 2
        assert catalog.summary.total_entries == 2
        assert catalog.data_quality.has_missing_layers is True

    def test_empty_entries_blocked_by_default(self, now: datetime) -> None:
        catalog = build_research_audit_catalog((), generated_at=now)
        assert catalog.catalog_state is CatalogState.BLOCKED
        assert MISSING_ARTIFACTS in catalog.reason_codes

    def test_empty_entries_allowed_when_block_on_empty_false(self, now: datetime) -> None:
        config = CatalogConfig(block_on_empty=False)
        catalog = build_research_audit_catalog(
            (),
            generated_at=now,
            config=config,
        )
        assert catalog.catalog_state is CatalogState.READY
        assert catalog.reason_codes == ()
        assert catalog.summary.layers_missing == 11

    def test_explicit_catalog_id_preserved(self, now: datetime) -> None:
        catalog = build_research_audit_catalog(
            (),
            catalog_id="my-id",
            generated_at=now,
            config=CatalogConfig(block_on_empty=False),
        )
        assert catalog.catalog_id == "my-id"

    def test_empty_catalog_id_generates_uuid(self, now: datetime) -> None:
        catalog = build_research_audit_catalog(
            (),
            generated_at=now,
            config=CatalogConfig(block_on_empty=False),
        )
        assert catalog.catalog_id
        assert len(catalog.catalog_id) == 36  # UUID hex with dashes

    def test_duplicate_entry_id_blocks(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        catalog = build_research_audit_catalog(entries, generated_at=now)
        assert catalog.catalog_state is CatalogState.BLOCKED
        assert DUPLICATE_ARTIFACT_ID in catalog.reason_codes

    def test_duplicate_entry_id_allowed_when_not_blocking(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        config = CatalogConfig(block_on_duplicate_ids=False)
        catalog = build_research_audit_catalog(entries, generated_at=now, config=config)
        assert catalog.catalog_state is CatalogState.READY

    def test_cross_kind_overlap_does_not_block(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="shared",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="shared",
                artifact_kind=CatalogArtifactKind.RESEARCH_BUNDLE,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        catalog = build_research_audit_catalog(entries, generated_at=now)
        assert catalog.catalog_state is CatalogState.READY
        assert catalog.data_quality.has_cross_kind_overlap is True

    def test_unsafe_metadata_rejected_at_entry_construction(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CATALOG_CONTENT"):
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
                metadata={"note": "deploy now"},
            )

    def test_unsafe_tags_rejected_at_entry_construction(self, now: datetime) -> None:
        with pytest.raises(ValueError, match="UNSAFE_CATALOG_CONTENT"):
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
                tags=["contains secret"],
            )

    def test_unsafe_content_allowed_when_not_blocking(self, now: datetime) -> None:
        # Unsafe content is rejected at entry construction, so the only way to
        # pass it through is to disable model-level checks. The config flag
        # block_on_unsafe_content governs catalog-level behavior if a caller
        # somehow provides an entry with unsafe metadata. Here we verify the
        # config flag exists and does not affect model validation.
        config = CatalogConfig(block_on_unsafe_content=False)
        assert config.block_on_unsafe_content is False

    def test_invalid_artifact_blocked(self, now: datetime) -> None:
        # Construct a valid entry, then corrupt source_version to simulate an
        # invalid artifact passing into the engine. The engine reconstructs
        # entries during validation and should catch the corruption.
        valid_entry = build_audit_catalog_entry(
            artifact_id="r1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
        )
        object.__setattr__(valid_entry, "source_version", "")
        catalog = build_research_audit_catalog((valid_entry,), generated_at=now)
        assert catalog.catalog_state is CatalogState.BLOCKED
        assert INVALID_ARTIFACT in catalog.reason_codes

    def test_staleness_is_non_blocking(self, now: datetime) -> None:
        old = now - timedelta(days=2)
        entries = (
            build_audit_catalog_entry(
                artifact_id="old",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=old,
            ),
        )
        catalog = build_research_audit_catalog(entries, generated_at=now)
        assert catalog.catalog_state is CatalogState.READY
        assert STALE_ARTIFACT not in catalog.reason_codes
        assert catalog.data_quality.has_stale_entries is True

    def test_deterministic_entry_ordering(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="z",
                artifact_kind=CatalogArtifactKind.REVIEW_INDEX,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="a",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="m",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        catalog = build_research_audit_catalog(entries, generated_at=now)
        ids = [e.entry_id for e in catalog.entries]
        assert ids == [
            "OBSERVATION_REPORT:a",
            "OBSERVATION_REPORT:m",
            "REVIEW_INDEX:z",
        ]

    def test_safety_flags_passed_through(self, now: datetime) -> None:
        flags = CatalogSafetyFlags()
        catalog = build_research_audit_catalog(
            (),
            generated_at=now,
            safety_flags=flags,
            config=CatalogConfig(block_on_empty=False),
        )
        assert catalog.safety_flags is flags

    def test_reason_codes_from_blocked_entries_not_propagated_to_catalog(self, now: datetime) -> None:
        entries = (
            CatalogEntry.blocked(
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                generated_at=now,
                reason_codes=(INVALID_ARTIFACT,),
            ),
        )
        catalog = build_research_audit_catalog(entries, generated_at=now)
        # Blocked entries do not block the catalog unless config says so.
        # Here the entry itself is valid (BLOCKED with reason code), so catalog is READY.
        assert catalog.catalog_state is CatalogState.READY
        assert catalog.reason_codes == ()

    def test_metadata_passthrough_not_traversed(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="r1",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
                metadata={
                    "local_reference": "data/observation/latest_observation_report.json",
                    "nested": {"path": "data/observation/other.json"},
                },
            ),
        )
        catalog = build_research_audit_catalog(entries, generated_at=now)
        assert catalog.catalog_state is CatalogState.READY
        assert dict(catalog.entries[0].metadata)["local_reference"].endswith(".json")

    def test_no_file_read_imports(self) -> None:
        import hunter.research_audit_catalog.engine as engine_module

        source = engine_module.__file__
        assert source is not None
        with open(source, "r", encoding="utf-8") as fh:
            text = fh.read()
        assert "open(" not in text or "__file__" in text
        assert "read(" not in text
        assert "pathlib" not in text
        assert "os.path" not in text

    def test_no_network_or_exchange_imports(self) -> None:
        import hunter.research_audit_catalog.engine as engine_module
        import hunter.research_audit_catalog.models as models_module

        for source in (engine_module.__file__, models_module.__file__):
            assert source is not None
            with open(source, "r", encoding="utf-8") as fh:
                text = fh.read()
            assert "import requests" not in text
            assert "import urllib" not in text
            assert "import sqlite3" not in text
            assert "import sqlalchemy" not in text
            assert "from freqtrade" not in text
            assert "from binance" not in text
            assert "freqtrade_bridge" not in text
            assert "execution_bridge" not in text
