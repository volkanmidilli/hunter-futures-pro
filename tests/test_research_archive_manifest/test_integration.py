"""Integration tests for hunter.research_archive_manifest.

MVP-19 Step 3 — end-to-end integration tests covering engine → writer flows,
determinism, safety assertions, serialization round-trips, and fail-closed
behavior.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.research_archive_manifest.engine import (
    build_archive_artifact_entry,
    build_archive_manifest_data_quality,
    build_archive_manifest_safety_flags,
    build_archive_manifest_summary,
    build_research_archive_manifest,
    has_unsafe_archive_manifest_content,
)
from hunter.research_archive_manifest.models import (
    FORBIDDEN_ARCHIVE_MANIFEST_TERMS,
    ArchiveArtifactEntry,
    ArchiveArtifactFamily,
    ArchiveManifestConfig,
    ArchiveManifestDataQuality,
    ArchiveManifestSafetyFlags,
    ArchiveManifestState,
    ArchiveManifestSummary,
    ResearchArchiveManifest,
)
from hunter.research_archive_manifest.writer import (
    DEFAULT_ARCHIVE_MANIFEST_JSON_PATH,
    DEFAULT_ARCHIVE_MANIFEST_MARKDOWN_PATH,
    atomic_write_json_research_archive_manifest,
    atomic_write_markdown_research_archive_manifest,
    research_archive_manifest_to_dict,
    research_archive_manifest_to_markdown,
    write_research_archive_manifest,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _fresh() -> datetime:
    return datetime(2099, 1, 1, tzinfo=timezone.utc)


def _make_safety_flags(
    *,
    dry_run: bool = True,
    live_trading_enabled: bool = False,
) -> ArchiveManifestSafetyFlags:
    return ArchiveManifestSafetyFlags(
        dry_run=dry_run,
        live_trading_enabled=live_trading_enabled,
    )


def _make_unsafe_safety_flags(unsafe_attr: str = "live_trading_enabled") -> ArchiveManifestSafetyFlags:
    flags = object.__new__(ArchiveManifestSafetyFlags)
    object.__setattr__(flags, "dry_run", True)
    object.__setattr__(flags, "live_trading_enabled", False)
    object.__setattr__(flags, "real_orders_enabled", False)
    object.__setattr__(flags, "leverage_enabled", False)
    object.__setattr__(flags, "shorting_enabled", False)
    object.__setattr__(flags, "archive_output_is_human_audit_only", True)
    object.__setattr__(flags, "archive_output_not_trading_signal", True)
    object.__setattr__(flags, "archive_output_not_trade_approval", True)
    object.__setattr__(flags, "archive_output_not_execution_readiness", True)
    object.__setattr__(flags, "archive_output_not_strategy_readiness", True)
    object.__setattr__(flags, "archive_output_not_release_approval", True)
    object.__setattr__(flags, "archive_output_not_deployment_approval", True)
    object.__setattr__(flags, "archive_output_not_transaction_permission", True)
    object.__setattr__(flags, "archive_output_not_for_execution", True)
    object.__setattr__(flags, "archive_output_not_for_strategy", True)
    object.__setattr__(flags, "archive_output_not_for_freqtrade", True)
    object.__setattr__(flags, "archive_output_not_for_order", True)
    object.__setattr__(flags, "archive_output_not_for_exchange", True)
    object.__setattr__(flags, "archive_manifest_feedback_into_execution", False)
    object.__setattr__(flags, "cross_layer_feedback_into_execution", False)
    object.__setattr__(flags, "file_refs_not_traversed", True)
    object.__setattr__(flags, "artifact_files_not_read", True)
    object.__setattr__(flags, unsafe_attr, True)
    return flags


def _make_artifact(
    state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = None,
    safety_flags: ArchiveManifestSafetyFlags | None = None,
    version: str = "1.0",
) -> object:
    if generated_at is None:
        generated_at = _fresh()
    if safety_flags is None:
        safety_flags = _make_safety_flags()

    class Artifact:
        pass

    artifact = Artifact()
    artifact.state = state
    artifact.reason_codes = reason_codes
    artifact.generated_at = generated_at
    artifact.safety_flags = safety_flags
    artifact.version = version
    return artifact


def _make_artifact_dict(
    state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = None,
    safety_flags: ArchiveManifestSafetyFlags | None = None,
    version: str = "1.0",
) -> dict[str, object]:
    if generated_at is None:
        generated_at = _fresh()
    if safety_flags is None:
        safety_flags = _make_safety_flags()
    return {
        "state": state,
        "reason_codes": reason_codes,
        "generated_at": generated_at,
        "safety_flags": safety_flags,
        "version": version,
    }


def _all_ready_artifacts() -> dict[str, object]:
    """Return kwargs with all nine artifact families in READY state."""
    return {
        "observation_artifact": _make_artifact("READY"),
        "review_artifact": _make_artifact("READY"),
        "index_artifact": _make_artifact_dict("READY"),
        "search_artifact": _make_artifact_dict("READY"),
        "bundle_artifact": _make_artifact("READY"),
        "chronicle_artifact": _make_artifact("READY"),
        "digest_artifact": _make_artifact("READY"),
        "quality_gate_artifact": _make_artifact("READY"),
        "handoff_artifact": _make_artifact("READY"),
    }


# ---------------------------------------------------------------------------
# 1. End-to-end build
# ---------------------------------------------------------------------------


class TestEndToEndBuild:
    def test_build_from_loaded_artifacts(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        assert manifest.manifest_state is ArchiveManifestState.READY
        assert len(manifest.entries) == 9

    def test_build_from_dict_artifacts(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact_dict("READY"),
            review_artifact=_make_artifact_dict("READY"),
        )
        assert len(manifest.entries) == 9


# ---------------------------------------------------------------------------
# 2. Deterministic artifact family ordering
# ---------------------------------------------------------------------------


class TestDeterministicFamilyOrdering:
    def test_family_order(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        families = [e.artifact_family for e in manifest.entries]
        assert families == list(ArchiveArtifactFamily)

    def test_order_independent_of_input(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            handoff_artifact=_make_artifact("READY"),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict("READY"),
            search_artifact=_make_artifact_dict("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
        )
        families = [e.artifact_family for e in manifest.entries]
        assert families == list(ArchiveArtifactFamily)


# ---------------------------------------------------------------------------
# 3. READY manifest
# ---------------------------------------------------------------------------


class TestReadyManifest:
    def test_all_present_ready(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        assert manifest.manifest_state is ArchiveManifestState.READY
        assert manifest.summary.present_count == 9
        assert manifest.summary.missing_count == 0
        assert manifest.summary.unknown_count == 0
        assert manifest.summary.stale_count == 0


# ---------------------------------------------------------------------------
# 4. STALE / BLOCK
# ---------------------------------------------------------------------------


class TestStaleBehavior:
    def test_stale_required_warns(self) -> None:
        stale = _now() - timedelta(hours=2)
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict("READY"),
            search_artifact=_make_artifact_dict("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY", generated_at=stale),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        assert manifest.manifest_state is ArchiveManifestState.WARN
        assert manifest.summary.stale_count >= 1


# ---------------------------------------------------------------------------
# 5. MISSING / BLOCK
# ---------------------------------------------------------------------------


class TestMissingBehavior:
    def test_missing_required_blocks(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict("READY"),
            search_artifact=_make_artifact_dict("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        assert manifest.manifest_state is ArchiveManifestState.BLOCK
        assert manifest.summary.missing_count >= 1
        assert any("MISSING_OBSERVATION_REPORT" in rc for rc in manifest.reason_codes)


# ---------------------------------------------------------------------------
# 6. UNKNOWN behavior
# ---------------------------------------------------------------------------


class TestUnknownBehavior:
    def test_unknown_artifact_state(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("UNKNOWN"),
            index_artifact=_make_artifact_dict("READY"),
            search_artifact=_make_artifact_dict("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        assert manifest.summary.unknown_count >= 1


# ---------------------------------------------------------------------------
# 7. block_on_unknown
# ---------------------------------------------------------------------------


class TestBlockOnUnknown:
    def test_block_on_unknown_true(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now(), block_on_unknown=True),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("UNKNOWN"),
            index_artifact=_make_artifact_dict("READY"),
            search_artifact=_make_artifact_dict("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        assert manifest.manifest_state is ArchiveManifestState.BLOCK

    def test_block_on_unknown_false(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now(), block_on_unknown=False),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("UNKNOWN"),
            index_artifact=_make_artifact_dict("READY"),
            search_artifact=_make_artifact_dict("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        assert manifest.manifest_state is ArchiveManifestState.WARN


# ---------------------------------------------------------------------------
# 8. required_families customization
# ---------------------------------------------------------------------------


class TestRequiredFamiliesCustomization:
    def test_custom_required_families(self) -> None:
        config = ArchiveManifestConfig(
            generated_at=_now(),
            required_families=(
                ArchiveArtifactFamily.OBSERVATION_REPORT,
                ArchiveArtifactFamily.OPERATOR_REVIEW,
            ),
        )
        manifest = build_research_archive_manifest(
            config=config,
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
        )
        assert manifest.manifest_state is ArchiveManifestState.READY
        assert manifest.summary.total_families == 9
        assert manifest.summary.present_count >= 2


# ---------------------------------------------------------------------------
# 9. Optional family None handling
# ---------------------------------------------------------------------------


class TestOptionalFamilyNone:
    def test_optional_missing_not_blocking(self) -> None:
        config = ArchiveManifestConfig(
            generated_at=_now(),
            required_families=(ArchiveArtifactFamily.OBSERVATION_REPORT,),
        )
        manifest = build_research_archive_manifest(
            config=config,
            observation_artifact=_make_artifact("READY"),
        )
        assert manifest.manifest_state is ArchiveManifestState.READY


# ---------------------------------------------------------------------------
# 10. Summary counts
# ---------------------------------------------------------------------------


class TestSummaryCounts:
    def test_counts_add_up(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict("READY"),
            search_artifact=_make_artifact_dict("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        s = manifest.summary
        assert s.present_count + s.stale_count + s.missing_count + s.unknown_count == s.total_families


# ---------------------------------------------------------------------------
# 11. Data quality public fields
# ---------------------------------------------------------------------------


class TestDataQuality:
    def test_completeness_pct(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict("READY"),
            search_artifact=_make_artifact_dict("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        dq = manifest.data_quality
        assert dq.completeness_pct == 100.0
        assert dq.total_families == 9
        assert dq.missing_count == 0

    def test_coverage_pct(self) -> None:
        stale = _now() - timedelta(hours=2)
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict("READY"),
            search_artifact=_make_artifact_dict("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY", generated_at=stale),
            handoff_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        assert manifest.data_quality.coverage_pct == 100.0


# ---------------------------------------------------------------------------
# 12. Safety flags
# ---------------------------------------------------------------------------


class TestSafetyFlags:
    def test_all_safety_flags(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        sf = manifest.safety_flags
        assert sf.archive_manifest_feedback_into_execution is False
        assert sf.cross_layer_feedback_into_execution is False
        assert sf.archive_output_not_trading_signal is True
        assert sf.archive_output_not_trade_approval is True
        assert sf.archive_output_not_execution_readiness is True
        assert sf.archive_output_not_strategy_readiness is True
        assert sf.archive_output_not_release_approval is True
        assert sf.archive_output_not_transaction_permission is True
        assert sf.file_refs_not_traversed is True
        assert sf.artifact_files_not_read is True


# ---------------------------------------------------------------------------
# 13. Manifest notes disclaimers
# ---------------------------------------------------------------------------


class TestManifestNotesDisclaimers:
    def test_ready_notes(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        notes = manifest.manifest_notes.lower()
        assert "not trade approval" in notes
        assert "not execution readiness" in notes
        assert "not strategy readiness" in notes
        assert "not release/deployment approval" in notes
        assert "not transaction permission" in notes

    def test_block_notes(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            review_artifact=_make_artifact("READY"),
        )
        notes = manifest.manifest_notes.lower()
        assert "not trade approval" in notes
        assert "not execution readiness" in notes
        assert "not strategy readiness" in notes
        assert "not release/deployment approval" in notes
        assert "not transaction permission" in notes


# ---------------------------------------------------------------------------
# 14. Dict serialization round-trip
# ---------------------------------------------------------------------------


class TestDictSerializationRoundTrip:
    def test_round_trip(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        data = research_archive_manifest_to_dict(manifest)
        assert data["manifest_id"] == manifest.manifest_id
        assert data["manifest_state"] == "ready"
        assert data["generated_at"] == manifest.generated_at.isoformat()
        assert data["summary"]["present_count"] == 9
        assert data["data_quality"]["completeness_pct"] == 100.0
        assert len(data["entries"]) == 9
        assert "safety_flags" in data
        assert "manifest_notes" in data
        assert "reason_codes" in data


# ---------------------------------------------------------------------------
# 15-16. Markdown output
# ---------------------------------------------------------------------------


class TestMarkdownOutput:
    def test_safety_notice_before_entries(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        md = research_archive_manifest_to_markdown(manifest)
        notice_idx = md.index("## Safety Notice")
        families_idx = md.index("## Artifact Families")
        assert notice_idx < families_idx

    def test_family_names_present(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        md = research_archive_manifest_to_markdown(manifest)
        for family in ArchiveArtifactFamily:
            assert family.value in md

    def test_reference_strings_present(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        md = research_archive_manifest_to_markdown(manifest)
        assert "data/observation/latest_observation_report.json" in md
        assert "SPEC-011" in md

    def test_states_and_reason_codes_present(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            review_artifact=_make_artifact("READY"),
        )
        md = research_archive_manifest_to_markdown(manifest)
        assert "MISSING" in md
        assert "MISSING_OBSERVATION_REPORT" in md

    def test_markdown_determinism(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        md1 = research_archive_manifest_to_markdown(manifest)
        md2 = research_archive_manifest_to_markdown(manifest)
        assert md1 == md2


# ---------------------------------------------------------------------------
# 17-19. Write tests
# ---------------------------------------------------------------------------


class TestWriteSafety:
    def test_dual_write_tmp_path(self, tmp_path: Path) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        json_path = tmp_path / "manifest.json"
        md_path = tmp_path / "manifest.md"
        write_research_archive_manifest(manifest, json_path=json_path, markdown_path=md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_atomic_json_tmp_path(self, tmp_path: Path) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        json_path = tmp_path / "manifest.json"
        atomic_write_json_research_archive_manifest(manifest, target_path=json_path)
        assert json_path.exists()

    def test_atomic_markdown_tmp_path(self, tmp_path: Path) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        md_path = tmp_path / "manifest.md"
        atomic_write_markdown_research_archive_manifest(manifest, target_path=md_path)
        assert md_path.exists()

    def test_no_production_default_writes(self, tmp_path: Path) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        write_research_archive_manifest(
            manifest,
            json_path=tmp_path / "manifest.json",
            markdown_path=tmp_path / "manifest.md",
        )
        assert not Path(DEFAULT_ARCHIVE_MANIFEST_JSON_PATH).exists()
        assert not Path(DEFAULT_ARCHIVE_MANIFEST_MARKDOWN_PATH).exists()


# ---------------------------------------------------------------------------
# 20-21. Reference strings and metadata strings remain plain strings
# ---------------------------------------------------------------------------


class TestReferenceStringsAsStrings:
    def test_file_reference_strings_not_opened(self, tmp_path: Path) -> None:
        entry = ArchiveArtifactEntry(
            artifact_family=ArchiveArtifactFamily.OBSERVATION_REPORT,
            local_reference="data/observation/latest_observation_report.json",
            metadata={"report_path": "reports/2025/btc.md"},
        )
        manifest = ResearchArchiveManifest(
            manifest_id="test:metadata",
            generated_at=_now(),
            entries=(entry,),
            summary=ArchiveManifestSummary(total_families=1, present_count=1),
            data_quality=ArchiveManifestDataQuality(total_families=1),
        )
        json_path = tmp_path / "manifest.json"
        md_path = tmp_path / "manifest.md"
        write_research_archive_manifest(manifest, json_path=json_path, markdown_path=md_path)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        observation_entry = next(
            e for e in data["entries"] if e["artifact_family"] == "observation_report"
        )
        assert observation_entry["metadata"]["report_path"] == "reports/2025/btc.md"
        md_text = md_path.read_text(encoding="utf-8")
        assert "reports/2025/btc.md" in md_text


# ---------------------------------------------------------------------------
# 22. No forbidden imports
# ---------------------------------------------------------------------------


class TestNoForbiddenImports:
    def test_no_forbidden_imports(self) -> None:
        base = Path(__file__).parent.parent.parent / "src" / "hunter" / "research_archive_manifest"
        for path in (base / "models.py", base / "engine.py", base / "writer.py"):
            text = path.read_text(encoding="utf-8").lower()
            for term in ("freqtrade", "binance", "requests", "sqlite"):
                assert f"import {term}" not in text, f"{path}: import {term}"
                assert f"from {term}" not in text, f"{path}: from {term}"


# ---------------------------------------------------------------------------
# 23. Fail-closed
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_unsafe_config_blocked(self) -> None:
        config = object.__new__(ArchiveManifestConfig)
        object.__setattr__(config, "version", "1.0")
        object.__setattr__(config, "generated_at", _now())
        object.__setattr__(config, "output_format", "both")
        object.__setattr__(config, "dry_run", False)
        object.__setattr__(config, "live_trading_enabled", False)
        object.__setattr__(config, "real_orders_enabled", False)
        object.__setattr__(config, "leverage_enabled", False)
        object.__setattr__(config, "shorting_enabled", False)
        object.__setattr__(config, "block_on_unknown", True)
        object.__setattr__(config, "required_families", ())
        object.__setattr__(config, "max_staleness_minutes", 60)
        object.__setattr__(config, "include_manifest_notes", True)

        manifest = build_research_archive_manifest(
            config=config,
            observation_artifact=_make_artifact("READY"),
        )
        assert manifest.manifest_state is ArchiveManifestState.BLOCK
        assert "UNSAFE_CONFIG" in manifest.reason_codes

    def test_empty_manifest_blocked(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now(), required_families=()),
        )
        assert manifest.manifest_state is ArchiveManifestState.BLOCK
        assert "EMPTY_MANIFEST" in manifest.reason_codes

    def test_unsafe_artifact_flags_blocked(self) -> None:
        flags = _make_unsafe_safety_flags("live_trading_enabled")
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY", safety_flags=flags),
        )
        assert "UNSAFE_ARTIFACT_FLAGS" in manifest.reason_codes


# ---------------------------------------------------------------------------
# 24. Deterministic manifest_id / generated_at
# ---------------------------------------------------------------------------


class TestDeterministicIds:
    def test_manifest_id_from_generated_at(self) -> None:
        generated_at = _now()
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=generated_at),
            observation_artifact=_make_artifact("READY"),
        )
        expected = f"archive:1.0:{generated_at.strftime('%Y-%m-%dT%H:%M:%S.%f')}"
        assert manifest.manifest_id == expected

    def test_same_generated_at_same_manifest_id(self) -> None:
        generated_at = _now()
        m1 = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=generated_at),
            **_all_ready_artifacts(),
        )
        m2 = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=generated_at),
            **_all_ready_artifacts(),
        )
        assert m1.manifest_id == m2.manifest_id


# ---------------------------------------------------------------------------
# 25. No mutation of input artifacts or manifest objects
# ---------------------------------------------------------------------------


class TestNoMutation:
    def test_manifest_not_mutated(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        original_id = manifest.manifest_id
        original_count = len(manifest.entries)
        research_archive_manifest_to_dict(manifest)
        research_archive_manifest_to_markdown(manifest)
        assert manifest.manifest_id == original_id
        assert len(manifest.entries) == original_count


# ---------------------------------------------------------------------------
# 26-27. Human-audit / inventory only
# ---------------------------------------------------------------------------


class TestHumanAuditOnly:
    def test_not_runtime_registry(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        # No registration/lookup API; manifest is a static snapshot.
        assert not hasattr(manifest, "register")
        assert not hasattr(manifest, "lookup")

    def test_no_forbidden_terms_in_notes(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        notes = manifest.manifest_notes.lower()
        for term in FORBIDDEN_ARCHIVE_MANIFEST_TERMS:
            assert term not in notes, term

    def test_not_release_or_deployment_approval(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            **_all_ready_artifacts(),
        )
        sf = manifest.safety_flags
        assert sf.archive_output_not_release_approval is True
        assert sf.archive_output_not_deployment_approval is True
        assert sf.archive_output_not_transaction_permission is True


# ---------------------------------------------------------------------------
# JSON round-trip with stale and missing entries
# ---------------------------------------------------------------------------


class TestJsonRoundTripMixedStates:
    def test_mixed_states_round_trip(self, tmp_path: Path) -> None:
        stale = _now() - timedelta(hours=2)
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict("READY"),
            search_artifact=_make_artifact_dict("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY", generated_at=stale),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        data = research_archive_manifest_to_dict(manifest)
        assert data["manifest_state"] == "warn"
        assert data["summary"]["stale_count"] >= 1

    def test_blocked_round_trip(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            review_artifact=_make_artifact("READY"),
        )
        data = research_archive_manifest_to_dict(manifest)
        assert data["manifest_state"] == "block"
        assert data["summary"]["missing_count"] >= 1


# ---------------------------------------------------------------------------
# Markdown blocked manifest
# ---------------------------------------------------------------------------


class TestBlockedMarkdown:
    def test_blocked_manifest_markdown(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            review_artifact=_make_artifact("READY"),
        )
        md = research_archive_manifest_to_markdown(manifest)
        assert "BLOCK" in md
        assert "MISSING" in md
        assert "## Safety Notice" in md
