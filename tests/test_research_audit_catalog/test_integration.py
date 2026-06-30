"""Integration tests for hunter.research_audit_catalog.

These tests exercise the full pipeline: artifact summaries -> catalog entries ->
catalog -> JSON/Markdown output. All writes use tmp_path. No referenced files
are read. No source files are modified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter.research_audit_catalog import (
    DEFAULT_RESEARCH_AUDIT_CATALOG_JSON_PATH,
    DEFAULT_RESEARCH_AUDIT_CATALOG_MARKDOWN_PATH,
    CATALOG_VERSION,
    CatalogArtifactKind,
    CatalogConfig,
    CatalogDataQuality,
    CatalogEntry,
    CatalogSafetyFlags,
    CatalogState,
    CatalogSummary,
    ResearchCatalog,
    build_audit_catalog_entry,
    build_research_audit_catalog,
    research_audit_catalog_to_dict,
    research_audit_catalog_to_markdown,
    write_research_audit_catalog,
)
from hunter.research_audit_catalog.models import CATALOG_ARTIFACT_SPEC_REFERENCE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeArtifact:
    """Duck-typed upstream artifact for integration tests."""

    artifact_id: str
    kind: CatalogArtifactKind
    version: str = "1.0"
    generated_at: datetime | None = None
    title: str = ""
    spec_reference: str = ""
    local_reference: str = ""
    reason_codes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "generated_at",
            self.generated_at or datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


def _make_entry(
    artifact_id: str,
    kind: CatalogArtifactKind,
    *,
    state: CatalogState = CatalogState.READY,
    title: str = "",
    local_reference: str = "",
    metadata: dict[str, Any] | None = None,
    tags: tuple[str, ...] = (),
    generated_at: datetime | None = None,
) -> CatalogEntry:
    """Build a CatalogEntry with safe defaults for integration tests."""
    return build_audit_catalog_entry(
        artifact_id=artifact_id,
        artifact_kind=kind,
        catalog_state=state,
        source_version="1.0",
        generated_at=generated_at or datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        title=title,
        spec_reference=CATALOG_ARTIFACT_SPEC_REFERENCE[kind],
        local_reference=local_reference,
        tags=tags,
        metadata=metadata or {},
    )


def _mvp_number(kind: CatalogArtifactKind) -> int:
    """Return MVP number for deterministic ordering verification."""
    mapping = {
        CatalogArtifactKind.OBSERVATION_REPORT: 10,
        CatalogArtifactKind.OPERATOR_REVIEW: 11,
        CatalogArtifactKind.REVIEW_INDEX: 12,
        CatalogArtifactKind.REVIEW_SEARCH: 13,
        CatalogArtifactKind.RESEARCH_BUNDLE: 14,
        CatalogArtifactKind.RESEARCH_CHRONICLE: 15,
        CatalogArtifactKind.RESEARCH_DIGEST: 16,
        CatalogArtifactKind.RESEARCH_QUALITY_GATE: 17,
        CatalogArtifactKind.RESEARCH_HANDOFF: 18,
        CatalogArtifactKind.RESEARCH_ARCHIVE_MANIFEST: 19,
        CatalogArtifactKind.RESEARCH_RELEASE_NOTES: 20,
    }
    return mapping[kind]


# ---------------------------------------------------------------------------
# End-to-end build from duck-typed artifacts
# ---------------------------------------------------------------------------


class TestEndToEndBuild:
    def test_build_from_fake_artifacts(self, tmp_path: Path) -> None:
        artifacts = (
            FakeArtifact(
                artifact_id="obs-001",
                kind=CatalogArtifactKind.OBSERVATION_REPORT,
                title="Observation 1",
                local_reference="data/observation/obs-001.json",
                metadata={"pairs": ("BTC/USDT",)},
            ),
            FakeArtifact(
                artifact_id="review-001",
                kind=CatalogArtifactKind.OPERATOR_REVIEW,
                title="Review 1",
                local_reference="data/review/review-001.json",
                metadata={"accepted": True},
            ),
        )
        entries = tuple(
            build_audit_catalog_entry(
                artifact_id=a.artifact_id,
                artifact_kind=a.kind,
                catalog_state=CatalogState.READY,
                source_version=a.version,
                generated_at=a.generated_at,
                title=a.title,
                spec_reference=CATALOG_ARTIFACT_SPEC_REFERENCE[a.kind],
                local_reference=a.local_reference,
                metadata=a.metadata,
            )
            for a in artifacts
        )
        catalog = build_research_audit_catalog(
            entries,
            catalog_id="e2e-001",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )

        assert catalog.catalog_state is CatalogState.READY
        assert len(catalog.entries) == 2
        assert catalog.summary.total_entries == 2
        assert catalog.data_quality.total_artifacts == 2

        json_path, md_path = write_research_audit_catalog(
            catalog,
            json_path=tmp_path / "catalog.json",
            markdown_path=tmp_path / "catalog.md",
        )
        assert json_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["catalog_id"] == "e2e-001"
        assert data["catalog_state"] == "READY"
        assert len(data["entries"]) == 2


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------


class TestDeterministicOrdering:
    def test_entries_ordered_by_kind_then_artifact_id(self) -> None:
        entries = (
            _make_entry("zzz", CatalogArtifactKind.REVIEW_SEARCH),
            _make_entry("aaa", CatalogArtifactKind.RESEARCH_DIGEST),
            _make_entry("mmm", CatalogArtifactKind.OBSERVATION_REPORT),
            _make_entry("aaa", CatalogArtifactKind.REVIEW_SEARCH),
        )
        catalog = build_research_audit_catalog(entries, catalog_id="order-test")
        ids = [e.entry_id for e in catalog.entries]
        assert ids == [
            "OBSERVATION_REPORT:mmm",
            "RESEARCH_DIGEST:aaa",
            "REVIEW_SEARCH:aaa",
            "REVIEW_SEARCH:zzz",
        ]


# ---------------------------------------------------------------------------
# READY / WARN / BLOCK / UNKNOWN states
# ---------------------------------------------------------------------------


class TestCatalogStates:
    def test_ready_when_layers_present_and_valid(self) -> None:
        entries = (
            _make_entry("obs-001", CatalogArtifactKind.OBSERVATION_REPORT),
            _make_entry("rev-001", CatalogArtifactKind.OPERATOR_REVIEW),
        )
        catalog = build_research_audit_catalog(entries, catalog_id="ready-test")
        assert catalog.catalog_state is CatalogState.READY
        assert catalog.reason_codes == ()

    def test_warn_behavior_for_cross_kind_overlap_is_ready_with_advisory_flag(self) -> None:
        """Cross-kind artifact_id overlap is advisory, not blocking."""
        entries = (
            _make_entry("shared", CatalogArtifactKind.OBSERVATION_REPORT),
            _make_entry("shared", CatalogArtifactKind.OPERATOR_REVIEW),
        )
        catalog = build_research_audit_catalog(entries, catalog_id="overlap-test")
        assert catalog.catalog_state is CatalogState.READY
        assert catalog.data_quality.has_cross_kind_overlap is True
        assert catalog.data_quality.cross_kind_overlap_ids == ("shared",)

    def test_blocked_for_duplicate_entry_id(self) -> None:
        entries = (
            _make_entry("dup", CatalogArtifactKind.OBSERVATION_REPORT),
            _make_entry("dup", CatalogArtifactKind.OBSERVATION_REPORT),
        )
        catalog = build_research_audit_catalog(entries, catalog_id="dup-test")
        assert catalog.catalog_state is CatalogState.BLOCKED
        assert "DUPLICATE_ARTIFACT_ID" in catalog.reason_codes

    def test_blocked_for_missing_required_layers(self) -> None:
        entries = ()
        catalog = build_research_audit_catalog(
            entries,
            catalog_id="missing-test",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert catalog.catalog_state is CatalogState.BLOCKED
        assert "MISSING_ARTIFACTS" in catalog.reason_codes

    def test_unsafe_content_rejected_fail_closed(self) -> None:
        # Unsafe content is rejected at entry construction. The catalog-level
        # block_on_unsafe_content check is unreachable for entries built through
        # the public API because validation fires first. This still satisfies
        # the fail-closed requirement.
        with pytest.raises(ValueError, match="UNSAFE_CATALOG_CONTENT"):
            _make_entry(
                "unsafe",
                CatalogArtifactKind.OBSERVATION_REPORT,
                metadata={"note": "deploy now"},
            )

    def test_blocked_for_invalid_artifact(self) -> None:
        # Construct a valid entry then corrupt source_version to simulate an
        # invalid artifact reaching the engine.
        valid = _make_entry("valid", CatalogArtifactKind.OBSERVATION_REPORT)
        object.__setattr__(valid, "source_version", "")
        catalog = build_research_audit_catalog((valid,), catalog_id="invalid-test")
        assert catalog.catalog_state is CatalogState.BLOCKED
        assert "INVALID_ARTIFACT" in catalog.reason_codes


# ---------------------------------------------------------------------------
# Required layers customization
# ---------------------------------------------------------------------------


class TestRequiredLayersCustomization:
    def test_empty_catalog_allowed_when_block_on_empty_false(self) -> None:
        config = CatalogConfig(block_on_empty=False)
        catalog = build_research_audit_catalog(
            (),
            catalog_id="empty-allowed",
            config=config,
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert catalog.catalog_state is CatalogState.READY
        assert catalog.entries == ()
        assert catalog.data_quality.has_missing_layers is True
        assert catalog.summary.layers_missing == 11

    def test_block_on_duplicate_can_be_disabled(self) -> None:
        entries = (
            _make_entry("dup", CatalogArtifactKind.OBSERVATION_REPORT),
            _make_entry("dup", CatalogArtifactKind.OBSERVATION_REPORT),
        )
        config = CatalogConfig(block_on_duplicate_ids=False)
        catalog = build_research_audit_catalog(entries, catalog_id="dup-allowed", config=config)
        assert catalog.catalog_state is CatalogState.READY
        assert catalog.data_quality.has_duplicates is True


# ---------------------------------------------------------------------------
# Summary and data quality public fields
# ---------------------------------------------------------------------------


class TestSummaryAndDataQuality:
    def test_summary_counts_using_public_fields(self) -> None:
        entries = (
            _make_entry("a", CatalogArtifactKind.OBSERVATION_REPORT),
            _make_entry("b", CatalogArtifactKind.OBSERVATION_REPORT),
            _make_entry("c", CatalogArtifactKind.OPERATOR_REVIEW),
        )
        catalog = build_research_audit_catalog(entries, catalog_id="summary-test")
        summary = catalog.summary
        assert isinstance(summary, CatalogSummary)
        assert summary.total_entries == 3
        assert summary.ready_count == 3
        assert summary.kind_counts[CatalogArtifactKind.OBSERVATION_REPORT] == 2
        assert summary.kind_counts[CatalogArtifactKind.OPERATOR_REVIEW] == 1
        assert summary.layers_covered == 2
        assert summary.layers_missing == 9

    def test_data_quality_fields_using_public_fields(self) -> None:
        entries = (
            _make_entry("shared", CatalogArtifactKind.OBSERVATION_REPORT),
            _make_entry("shared", CatalogArtifactKind.OPERATOR_REVIEW),
            _make_entry("dup", CatalogArtifactKind.OBSERVATION_REPORT),
            _make_entry("dup", CatalogArtifactKind.OBSERVATION_REPORT),
        )
        config = CatalogConfig(block_on_duplicate_ids=False)
        catalog = build_research_audit_catalog(
            entries, catalog_id="dq-test", config=config
        )
        dq = catalog.data_quality
        assert isinstance(dq, CatalogDataQuality)
        assert dq.total_artifacts == 4
        assert dq.valid_entries == 4
        assert dq.has_duplicates is True
        assert dq.has_cross_kind_overlap is True
        assert "OBSERVATION_REPORT:dup" in dq.duplicate_artifact_ids
        assert "shared" in dq.cross_kind_overlap_ids


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


class TestSafetyFlags:
    def test_default_safety_flags_are_fail_closed(self) -> None:
        catalog = build_research_audit_catalog(
            (_make_entry("x", CatalogArtifactKind.OBSERVATION_REPORT),),
            catalog_id="safety-test",
        )
        flags = catalog.safety_flags
        assert flags.catalog_feedback_into_execution is False
        assert flags.catalog_output_not_release_approval is True
        assert flags.catalog_output_not_deployment_approval is True
        assert flags.catalog_output_not_trading_signal is True
        assert flags.catalog_output_not_trade_approval is True
        assert flags.catalog_output_not_execution_approval is True
        assert flags.catalog_output_not_strategy_approval is True
        assert flags.catalog_output_not_transaction_permission is True
        assert flags.no_action_commands_emitted is True
        assert flags.artifact_files_not_read is True

    def test_unsafe_safety_flags_rejected(self) -> None:
        with pytest.raises(ValueError):
            CatalogSafetyFlags(catalog_feedback_into_execution=True)


# ---------------------------------------------------------------------------
# Catalog notes / disclaimers
# ---------------------------------------------------------------------------


class TestCatalogNotesAndDisclaimers:
    def test_markdown_contains_all_disclaimers(self) -> None:
        catalog = build_research_audit_catalog(
            (_make_entry("x", CatalogArtifactKind.OBSERVATION_REPORT),),
            catalog_id="notes-test",
        )
        md = research_audit_catalog_to_markdown(catalog)
        assert "not release approval" in md
        assert "not deployment approval" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "not execution approval" in md
        assert "not strategy approval" in md
        assert "not transaction permission" in md
        assert "not a runtime registry" in md
        assert "indexer" in md
        assert "crawler" in md
        assert "dashboard" in md
        assert "database" in md
        assert "API" in md
        assert "must not be consumed by execution" in md
        assert "not gating criteria" in md

    def test_dict_contains_document_notes(self) -> None:
        catalog = build_research_audit_catalog(
            (_make_entry("x", CatalogArtifactKind.OBSERVATION_REPORT),),
            catalog_id="notes-test",
        )
        data = research_audit_catalog_to_dict(catalog)
        assert "document_notes" in data
        assert "human audit" in data["document_notes"].lower()


# ---------------------------------------------------------------------------
# Dict round-trip
# ---------------------------------------------------------------------------


class TestDictRoundTrip:
    def test_round_trip_preserves_fields(self) -> None:
        catalog = build_research_audit_catalog(
            (
                _make_entry(
                    "obs-001",
                    CatalogArtifactKind.OBSERVATION_REPORT,
                    metadata={"pair": "BTC/USDT"},
                ),
            ),
            catalog_id="round-trip-001",
            generated_at=datetime(2026, 6, 29, 12, 0, 0, tzinfo=timezone.utc),
        )
        data = research_audit_catalog_to_dict(catalog)
        assert data["catalog_id"] == "round-trip-001"
        assert data["version"] == CATALOG_VERSION
        assert data["catalog_state"] == "READY"
        assert data["generated_at"] == "2026-06-29T12:00:00Z"
        assert len(data["entries"]) == 1
        assert data["entries"][0]["artifact_id"] == "obs-001"
        assert data["entries"][0]["metadata"] == {"pair": "BTC/USDT"}
        assert "summary" in data
        assert "data_quality" in data
        assert "reason_codes" in data
        assert "safety_flags" in data
        assert "document_notes" in data


# ---------------------------------------------------------------------------
# Markdown content
# ---------------------------------------------------------------------------


class TestMarkdownContent:
    def test_safety_notice_before_entries_and_references(self) -> None:
        catalog = build_research_audit_catalog(
            (_make_entry("x", CatalogArtifactKind.OBSERVATION_REPORT, local_reference="data/x.json"),),
            catalog_id="md-test",
        )
        md = research_audit_catalog_to_markdown(catalog)
        notice_pos = md.find("## Safety Notice")
        entries_pos = md.find("## Entries")
        ref_pos = md.find("data/x.json")
        assert notice_pos < entries_pos
        assert notice_pos < ref_pos

    def test_markdown_includes_all_entry_fields(self) -> None:
        catalog = build_research_audit_catalog(
            (
                _make_entry(
                    "obs-001",
                    CatalogArtifactKind.OBSERVATION_REPORT,
                    title="Observation 1",
                    local_reference="data/obs.json",
                    metadata={"pair": "BTC/USDT"},
                ),
            ),
            catalog_id="md-fields-test",
        )
        md = research_audit_catalog_to_markdown(catalog)
        assert "OBSERVATION_REPORT:obs-001" in md
        assert "obs-001" in md
        assert "Observation 1" in md
        assert CATALOG_ARTIFACT_SPEC_REFERENCE[CatalogArtifactKind.OBSERVATION_REPORT] in md
        assert "data/obs.json" in md
        assert "BTC/USDT" in md


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


class TestWrites:
    def test_dual_write_uses_tmp_path(self, tmp_path: Path) -> None:
        catalog = build_research_audit_catalog(
            (_make_entry("x", CatalogArtifactKind.OBSERVATION_REPORT),),
            catalog_id="write-test",
        )
        json_out, md_out = write_research_audit_catalog(
            catalog,
            json_path=tmp_path / "out.json",
            markdown_path=tmp_path / "out.md",
        )
        assert json_out.exists()
        assert md_out.exists()
        assert not DEFAULT_RESEARCH_AUDIT_CATALOG_JSON_PATH.exists()
        assert not DEFAULT_RESEARCH_AUDIT_CATALOG_MARKDOWN_PATH.exists()

    def test_atomic_json_and_markdown_writes(self, tmp_path: Path) -> None:
        catalog = build_research_audit_catalog(
            (_make_entry("x", CatalogArtifactKind.OBSERVATION_REPORT),),
            catalog_id="atomic-test",
        )
        json_path = tmp_path / "atomic.json"
        md_path = tmp_path / "atomic.md"
        from hunter.research_audit_catalog import (
            atomic_write_json_research_audit_catalog,
            atomic_write_markdown_research_audit_catalog,
        )

        atomic_write_json_research_audit_catalog(catalog, target_path=json_path)
        atomic_write_markdown_research_audit_catalog(catalog, target_path=md_path)
        assert json_path.exists()
        assert md_path.exists()


# ---------------------------------------------------------------------------
# No file reads / no mutation
# ---------------------------------------------------------------------------


class TestNoFileReadsOrMutation:
    def test_reference_string_not_read(self, tmp_path: Path) -> None:
        suspicious_path = str(tmp_path / "does_not_exist.json")
        entry = _make_entry(
            "x",
            CatalogArtifactKind.OBSERVATION_REPORT,
            local_reference=suspicious_path,
            metadata={"path": suspicious_path},
        )
        catalog = build_research_audit_catalog((entry,), catalog_id="no-read-test")
        md = research_audit_catalog_to_markdown(catalog)
        assert suspicious_path in md
        # If the writer had tried to read the path, it would have raised.
        # The path does not exist, so success proves no read was attempted.

    def test_input_artifacts_not_mutated(self) -> None:
        entries = (
            _make_entry("x", CatalogArtifactKind.OBSERVATION_REPORT, metadata={"a": 1}),
        )
        original_metadata = entries[0].metadata
        original_entry = entries[0]
        catalog = build_research_audit_catalog(entries, catalog_id="no-mut-test")
        _ = research_audit_catalog_to_dict(catalog)
        _ = research_audit_catalog_to_markdown(catalog)
        assert entries[0] is original_entry
        assert entries[0].metadata is original_metadata


# ---------------------------------------------------------------------------
# Explicit catalog_id / generated_at
# ---------------------------------------------------------------------------


class TestExplicitIdentity:
    def test_explicit_catalog_id_preserved(self) -> None:
        catalog = build_research_audit_catalog(
            (_make_entry("x", CatalogArtifactKind.OBSERVATION_REPORT),),
            catalog_id="explicit-id",
        )
        assert catalog.catalog_id == "explicit-id"

    def test_explicit_generated_at_preserved(self) -> None:
        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        catalog = build_research_audit_catalog(
            (_make_entry("x", CatalogArtifactKind.OBSERVATION_REPORT),),
            catalog_id="explicit-time",
            generated_at=ts,
        )
        assert catalog.generated_at == ts


# ---------------------------------------------------------------------------
# No forbidden imports / paths
# ---------------------------------------------------------------------------


class TestNoForbiddenImports:
    def test_writer_and_models_have_no_forbidden_imports(self) -> None:
        import hunter.research_audit_catalog.models as models_module
        import hunter.research_audit_catalog.writer as writer_module

        for source in (models_module.__file__, writer_module.__file__):
            assert source is not None
            text = Path(source).read_text(encoding="utf-8")
            assert "import requests" not in text
            assert "import urllib" not in text
            assert "import sqlite3" not in text
            assert "from freqtrade" not in text
            assert "from binance" not in text
            assert "freqtrade_bridge" not in text
            assert "execution_bridge" not in text


# ---------------------------------------------------------------------------
# Frozen behavior
# ---------------------------------------------------------------------------


def test_catalog_object_is_frozen() -> None:
    catalog = build_research_audit_catalog(
        (_make_entry("x", CatalogArtifactKind.OBSERVATION_REPORT),),
        catalog_id="frozen-test",
    )
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        catalog.catalog_id = "mutated"


# ---------------------------------------------------------------------------
# Full layer coverage
# ---------------------------------------------------------------------------


class TestFullLayerCoverage:
    def test_all_eleven_kinds_produce_full_coverage(self) -> None:
        entries = tuple(
            _make_entry(f"id-{kind.value}", kind) for kind in CatalogArtifactKind
        )
        catalog = build_research_audit_catalog(entries, catalog_id="full-coverage")

        assert catalog.catalog_state is CatalogState.READY
        assert catalog.summary.total_entries == len(CatalogArtifactKind)
        assert catalog.summary.layers_covered == len(CatalogArtifactKind)
        assert catalog.summary.layers_missing == 0
        assert catalog.data_quality.has_missing_layers is False

        for kind in CatalogArtifactKind:
            assert catalog.summary.kind_counts[kind] == 1
            assert kind.value in catalog.data_quality.covered_layer_kinds
            assert kind.value not in catalog.data_quality.missing_layer_kinds
