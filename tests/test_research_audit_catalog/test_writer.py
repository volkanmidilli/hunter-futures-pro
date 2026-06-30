"""Tests for hunter.research_audit_catalog.writer."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter.research_audit_catalog import (
    DEFAULT_RESEARCH_AUDIT_CATALOG_JSON_PATH,
    DEFAULT_RESEARCH_AUDIT_CATALOG_MARKDOWN_PATH,
    CatalogArtifactKind,
    CatalogConfig,
    CatalogDataQuality,
    CatalogEntry,
    CatalogSafetyFlags,
    CatalogState,
    CatalogSummary,
    ResearchCatalog,
    atomic_write_json_research_audit_catalog,
    atomic_write_markdown_research_audit_catalog,
    catalog_config_to_dict,
    catalog_data_quality_to_dict,
    catalog_entry_to_dict,
    catalog_safety_flags_to_dict,
    catalog_summary_to_dict,
    research_audit_catalog_to_dict,
    research_audit_catalog_to_markdown,
    write_research_audit_catalog,
)
from hunter.research_audit_catalog.engine import build_audit_catalog_entry, build_research_audit_catalog


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_entry(now: datetime) -> CatalogEntry:
    return build_audit_catalog_entry(
        artifact_id="obs-001",
        artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
        catalog_state=CatalogState.READY,
        source_version="1.0",
        generated_at=now,
        title="Observation report 1",
        spec_reference="SPEC-011",
        local_reference="data/observation/latest_observation_report.json",
        tags=["observed", "snapshot"],
        metadata={"pair": "BTC/USDT", "mode": "simulated"},
    )


@pytest.fixture
def sample_catalog(now: datetime, sample_entry: CatalogEntry) -> ResearchCatalog:
    entries = (
        sample_entry,
        build_audit_catalog_entry(
            artifact_id="rev-001",
            artifact_kind=CatalogArtifactKind.OPERATOR_REVIEW,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
            title="Operator review 1",
            spec_reference="SPEC-012",
            local_reference="data/review/latest_review_audit_record.json",
            metadata={"reviewer": "operator-1", "accepted": True},
        ),
    )
    return build_research_audit_catalog(entries, catalog_id="cat-test-001", generated_at=now)


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


class TestCatalogConfigToDict:
    def test_round_trip_values(self) -> None:
        config = CatalogConfig()
        data = catalog_config_to_dict(config)
        assert data["catalog_version"] == "1.0"
        assert data["stale_threshold_seconds"] == 86400
        assert data["block_on_empty"] is True
        assert data["block_on_duplicate_ids"] is True
        assert data["block_on_unsafe_content"] is True


class TestCatalogSafetyFlagsToDict:
    def test_all_flags_present(self) -> None:
        flags = CatalogSafetyFlags()
        data = catalog_safety_flags_to_dict(flags)
        assert data["catalog_output_is_human_audit_only"] is True
        assert data["catalog_output_not_trade_approval"] is True
        assert data["catalog_output_not_release_approval"] is True
        assert data["catalog_output_not_deployment_approval"] is True
        assert data["catalog_output_not_execution_approval"] is True
        assert data["live_trading_enabled"] is False
        assert data["database_persistence_enabled"] is False
        assert data["runtime_registry_enabled"] is False
        assert data["indexer_crawler_enabled"] is False


class TestCatalogEntryToDict:
    def test_enum_values_are_strings(self, sample_entry: CatalogEntry) -> None:
        data = catalog_entry_to_dict(sample_entry)
        assert data["artifact_kind"] == "OBSERVATION_REPORT"
        assert data["catalog_state"] == "READY"

    def test_metadata_passthrough(self, sample_entry: CatalogEntry) -> None:
        data = catalog_entry_to_dict(sample_entry)
        assert data["metadata"] == {"pair": "BTC/USDT", "mode": "simulated"}
        assert isinstance(data["metadata"], dict)

    def test_reference_strings_remain_strings(self, sample_entry: CatalogEntry) -> None:
        data = catalog_entry_to_dict(sample_entry)
        assert data["local_reference"] == "data/observation/latest_observation_report.json"
        assert isinstance(data["local_reference"], str)
        assert data["spec_reference"] == "SPEC-011"

    def test_tuples_become_lists(self, sample_entry: CatalogEntry) -> None:
        data = catalog_entry_to_dict(sample_entry)
        assert data["reason_codes"] == []
        assert data["tags"] == ["observed", "snapshot"]
        assert isinstance(data["reason_codes"], list)
        assert isinstance(data["tags"], list)

    def test_datetime_to_iso(self, sample_entry: CatalogEntry) -> None:
        data = catalog_entry_to_dict(sample_entry)
        assert data["generated_at"] == "2026-06-29T12:00:00Z"


class TestCatalogSummaryToDict:
    def test_kind_counts_use_string_keys(self, now: datetime) -> None:
        summary = CatalogSummary(
            total_entries=2,
            ready_count=2,
            layers_covered=1,
            layers_missing=10,
            kind_counts={CatalogArtifactKind.OBSERVATION_REPORT: 1},
        )
        data = catalog_summary_to_dict(summary)
        assert data["kind_counts"] == {"OBSERVATION_REPORT": 1}


class TestCatalogDataQualityToDict:
    def test_overlap_fields_serializable(self) -> None:
        dq = CatalogDataQuality(
            duplicate_artifact_ids=("OBSERVATION_REPORT:obs-001",),
            cross_kind_overlap_ids=("shared-001",),
        )
        data = catalog_data_quality_to_dict(dq)
        assert data["duplicate_artifact_ids"] == ["OBSERVATION_REPORT:obs-001"]
        assert data["cross_kind_overlap_ids"] == ["shared-001"]


class TestResearchAuditCatalogToDict:
    def test_top_level_keys(self, sample_catalog: ResearchCatalog) -> None:
        data = research_audit_catalog_to_dict(sample_catalog)
        assert data["catalog_id"] == "cat-test-001"
        assert data["version"] == "1.0"
        assert data["catalog_state"] == "READY"
        assert data["reason_codes"] == []
        assert "document_notes" in data

    def test_entries_are_list_of_dicts(self, sample_catalog: ResearchCatalog) -> None:
        data = research_audit_catalog_to_dict(sample_catalog)
        assert isinstance(data["entries"], list)
        assert len(data["entries"]) == 2
        assert data["entries"][0]["artifact_kind"] == "OBSERVATION_REPORT"
        assert data["entries"][1]["artifact_kind"] == "OPERATOR_REVIEW"

    def test_metadata_in_entries_is_plain_dict(self, sample_catalog: ResearchCatalog) -> None:
        data = research_audit_catalog_to_dict(sample_catalog)
        entry_metadata = data["entries"][0]["metadata"]
        assert isinstance(entry_metadata, dict)
        assert entry_metadata["pair"] == "BTC/USDT"

    def test_no_mutation(self, sample_catalog: ResearchCatalog) -> None:
        original_entries = sample_catalog.entries
        original_metadata = sample_catalog.entries[0].metadata
        research_audit_catalog_to_dict(sample_catalog)
        assert sample_catalog.entries is original_entries
        assert sample_catalog.entries[0].metadata is original_metadata

    def test_blocked_catalog_serializes(self, now: datetime) -> None:
        catalog = ResearchCatalog.blocked(reason_code="MISSING_ARTIFACTS")
        data = research_audit_catalog_to_dict(catalog)
        assert data["catalog_state"] == "BLOCKED"
        assert data["reason_codes"] == ["MISSING_ARTIFACTS"]


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_json_determinism(self, sample_catalog: ResearchCatalog) -> None:
        data1 = research_audit_catalog_to_dict(sample_catalog)
        data2 = research_audit_catalog_to_dict(sample_catalog)
        assert json.dumps(data1, sort_keys=True) == json.dumps(data2, sort_keys=True)

    def test_markdown_determinism(self, sample_catalog: ResearchCatalog) -> None:
        md1 = research_audit_catalog_to_markdown(sample_catalog)
        md2 = research_audit_catalog_to_markdown(sample_catalog)
        assert md1 == md2


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


class TestMarkdownOutput:
    def test_safety_notice_before_entries(self, sample_catalog: ResearchCatalog) -> None:
        md = research_audit_catalog_to_markdown(sample_catalog)
        notice_pos = md.find("## Safety Notice")
        entries_pos = md.find("## Entries")
        assert notice_pos != -1
        assert entries_pos != -1
        assert notice_pos < entries_pos

    def test_safety_notice_contains_required_statements(self, sample_catalog: ResearchCatalog) -> None:
        md = research_audit_catalog_to_markdown(sample_catalog)
        assert "human-audit / contractor-handoff artifact only" in md
        assert "not release approval" in md
        assert "not deployment approval" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "not execution approval" in md
        assert "not strategy approval" in md
        assert "not transaction permission" in md
        assert "not a runtime registry" in md
        assert "not traversed, opened, followed, validated, or executed" in md
        assert "Referenced artifact files are not read" in md
        assert "advisory only" in md
        assert "not gating criteria" in md

    def test_markdown_entry_ordering(self, now: datetime) -> None:
        entries = (
            build_audit_catalog_entry(
                artifact_id="zzz",
                artifact_kind=CatalogArtifactKind.REVIEW_SEARCH,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="aaa",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        catalog = build_research_audit_catalog(entries, catalog_id="order-test", generated_at=now)
        md = research_audit_catalog_to_markdown(catalog)
        obs_pos = md.find("### OBSERVATION_REPORT:aaa")
        search_pos = md.find("### REVIEW_SEARCH:zzz")
        assert obs_pos != -1
        assert search_pos != -1
        assert obs_pos < search_pos

    def test_markdown_includes_catalog_notes(self, sample_catalog: ResearchCatalog) -> None:
        md = research_audit_catalog_to_markdown(sample_catalog)
        assert "## Catalog Notes" in md
        assert "static snapshot" in md
        assert "does not scan directories" in md

    def test_markdown_no_action_commands(self, sample_catalog: ResearchCatalog) -> None:
        md = research_audit_catalog_to_markdown(sample_catalog)
        assert "run(" not in md
        assert "execute(" not in md
        assert "deploy(" not in md

    def test_reference_strings_plain_text(self, sample_catalog: ResearchCatalog) -> None:
        md = research_audit_catalog_to_markdown(sample_catalog)
        assert "data/observation/latest_observation_report.json" in md
        # Should appear as plain text, not as a link or code that implies following
        assert "[data/observation" not in md


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


class TestAtomicWrites:
    def test_atomic_json_write(self, tmp_path: Path, sample_catalog: ResearchCatalog) -> None:
        target = tmp_path / "catalog.json"
        result = atomic_write_json_research_audit_catalog(sample_catalog, target_path=target)
        assert result == target
        assert target.exists()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["catalog_id"] == "cat-test-001"
        assert data["catalog_state"] == "READY"

    def test_atomic_markdown_write(self, tmp_path: Path, sample_catalog: ResearchCatalog) -> None:
        target = tmp_path / "catalog.md"
        result = atomic_write_markdown_research_audit_catalog(sample_catalog, target_path=target)
        assert result == target
        assert target.exists()
        md = target.read_text(encoding="utf-8")
        assert "# Local Research Audit Catalog" in md
        assert "## Safety Notice" in md

    def test_dual_write(self, tmp_path: Path, sample_catalog: ResearchCatalog) -> None:
        json_path = tmp_path / "dual.json"
        md_path = tmp_path / "dual.md"
        json_out, md_out = write_research_audit_catalog(
            sample_catalog,
            json_path=json_path,
            markdown_path=md_path,
        )
        assert json_out == json_path
        assert md_out == md_path
        assert json_path.exists()
        assert md_path.exists()

    def test_parent_directories_created(self, tmp_path: Path, sample_catalog: ResearchCatalog) -> None:
        target = tmp_path / "nested" / "dir" / "catalog.json"
        atomic_write_json_research_audit_catalog(sample_catalog, target_path=target)
        assert target.exists()

    def test_default_paths_are_research_audit_catalog(self) -> None:
        assert DEFAULT_RESEARCH_AUDIT_CATALOG_JSON_PATH == Path(
            "data/research_audit_catalog/latest_research_audit_catalog.json"
        )
        assert DEFAULT_RESEARCH_AUDIT_CATALOG_MARKDOWN_PATH == Path(
            "reports/research_audit_catalog/latest_research_audit_catalog.md"
        )


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


class TestWriterSafety:
    def test_no_production_default_path_writes(self, tmp_path: Path, sample_catalog: ResearchCatalog) -> None:
        # All writer tests above use tmp_path. This test explicitly verifies
        # that passing a tmp_path does not write to production defaults.
        target = tmp_path / "explicit.json"
        atomic_write_json_research_audit_catalog(sample_catalog, target_path=target)
        assert not DEFAULT_RESEARCH_AUDIT_CATALOG_JSON_PATH.exists()
        assert not DEFAULT_RESEARCH_AUDIT_CATALOG_MARKDOWN_PATH.exists()

    def test_metadata_strings_not_traversed(self, tmp_path: Path, now: datetime) -> None:
        entry = build_audit_catalog_entry(
            artifact_id="r1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=now,
            local_reference="/tmp/missing_file.json",
            metadata={"path": "/tmp/missing_file.json"},
        )
        catalog = build_research_audit_catalog((entry,), catalog_id="cat-001", generated_at=now)
        md = research_audit_catalog_to_markdown(catalog)
        assert "/tmp/missing_file.json" in md
        # No attempt to open the path during markdown rendering
        assert "No such file" not in md

    def test_markdown_contains_no_release_ready_language(self, sample_catalog: ResearchCatalog) -> None:
        md = research_audit_catalog_to_markdown(sample_catalog)
        assert "release ready" not in md.lower()
        assert "deployment ready" not in md.lower()
        assert "execution ready" not in md.lower()
        assert "strategy ready" not in md.lower()
        assert "go live" not in md.lower()

    def test_json_sort_keys(self, sample_catalog: ResearchCatalog) -> None:
        # JSON serialization sorts keys at the string level.
        data = research_audit_catalog_to_dict(sample_catalog)
        json_text = json.dumps(data, sort_keys=True)
        # Verify deterministic by parsing and re-serializing.
        reparsed = json.loads(json_text)
        assert json.dumps(reparsed, sort_keys=True) == json_text

    def test_writer_does_not_mutate_metadata_type(self, sample_catalog: ResearchCatalog) -> None:
        original = sample_catalog.entries[0].metadata
        research_audit_catalog_to_dict(sample_catalog)
        assert sample_catalog.entries[0].metadata is original


# ---------------------------------------------------------------------------
# Cross-kind overlap serialization
# ---------------------------------------------------------------------------


class TestOverlapSerialization:
    def test_duplicate_and_overlap_in_markdown(self, now: datetime) -> None:
        # Build with duplicates disabled so cross-kind overlap remains visible.
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
                artifact_kind=CatalogArtifactKind.OPERATOR_REVIEW,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="dup",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
            build_audit_catalog_entry(
                artifact_id="dup",
                artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        config = CatalogConfig(block_on_duplicate_ids=False)
        catalog = build_research_audit_catalog(
            entries, catalog_id="overlap-test", generated_at=now, config=config
        )
        md = research_audit_catalog_to_markdown(catalog)
        assert "### Cross-kind artifact_id overlap" in md
        assert "`shared`" in md
        assert "### Duplicate entry_ids" in md
        assert "OBSERVATION_REPORT:dup" in md

    def test_overlap_advisory_does_not_block(self, now: datetime) -> None:
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
                artifact_kind=CatalogArtifactKind.OPERATOR_REVIEW,
                catalog_state=CatalogState.READY,
                source_version="1.0",
                generated_at=now,
            ),
        )
        catalog = build_research_audit_catalog(entries, catalog_id="overlap-test", generated_at=now)
        assert catalog.catalog_state is CatalogState.READY
        assert catalog.data_quality.has_cross_kind_overlap is True
        assert catalog.data_quality.cross_kind_overlap_ids == ("shared",)


# ---------------------------------------------------------------------------
# Frozen imports
# ---------------------------------------------------------------------------


def test_frozen_catalog_cannot_be_mutated(sample_catalog: ResearchCatalog) -> None:
    with pytest.raises(FrozenInstanceError):
        sample_catalog.catalog_id = "mutated"
