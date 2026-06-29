"""Tests for hunter.research_archive_manifest.engine."""

from __future__ import annotations

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
    ArchiveArtifactFamily,
    ArchiveManifestConfig,
    ArchiveManifestSafetyFlags,
    ArchiveManifestState,
    ResearchArchiveManifest,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_safety_flags(
    *,
    dry_run: bool = True,
    live_trading_enabled: bool = False,
    archive_manifest_feedback_into_execution: bool = False,
) -> ArchiveManifestSafetyFlags:
    return ArchiveManifestSafetyFlags(
        dry_run=dry_run,
        live_trading_enabled=live_trading_enabled,
        real_orders_enabled=False,
        leverage_enabled=False,
        shorting_enabled=False,
        archive_manifest_feedback_into_execution=archive_manifest_feedback_into_execution,
        cross_layer_feedback_into_execution=False,
    )


def _make_unsafe_safety_flags(unsafe_attr: str = "live_trading_enabled") -> ArchiveManifestSafetyFlags:
    """Return a safety flags object with one unsafe flag enabled."""
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
    """Return a simple artifact-like object."""
    if generated_at is None:
        generated_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
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
    """Return a dict-based artifact."""
    if generated_at is None:
        generated_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
    if safety_flags is None:
        safety_flags = _make_safety_flags()
    return {
        "state": state,
        "reason_codes": reason_codes,
        "generated_at": generated_at,
        "safety_flags": safety_flags,
        "version": version,
    }


# ---------------------------------------------------------------------------
# has_unsafe_archive_manifest_content
# ---------------------------------------------------------------------------


class TestHasUnsafeArchiveManifestContent:
    def test_safe_text(self) -> None:
        assert has_unsafe_archive_manifest_content("normal audit notes") is False

    def test_forbidden_term_api_key(self) -> None:
        assert has_unsafe_archive_manifest_content("contains api_key") is True

    def test_forbidden_term_go_live(self) -> None:
        assert has_unsafe_archive_manifest_content("go_live now") is True

    def test_case_insensitive(self) -> None:
        assert has_unsafe_archive_manifest_content("GO_LIVE") is True
        assert has_unsafe_archive_manifest_content("API_KEY") is True

    def test_empty_text(self) -> None:
        assert has_unsafe_archive_manifest_content("") is False
        assert has_unsafe_archive_manifest_content(None) is False

    def test_unsafe_metadata(self) -> None:
        assert has_unsafe_archive_manifest_content(None, {"token": "abc"}) is True

    def test_safe_metadata(self) -> None:
        assert has_unsafe_archive_manifest_content(None, {"path": "/tmp/report.json"}) is False


# ---------------------------------------------------------------------------
# build_archive_manifest_safety_flags
# ---------------------------------------------------------------------------


class TestBuildArchiveManifestSafetyFlags:
    def test_default_config(self) -> None:
        flags = build_archive_manifest_safety_flags(ArchiveManifestConfig())
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.archive_manifest_feedback_into_execution is False

    def test_unsafe_config_rejected(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            ArchiveManifestConfig(dry_run=False)

    def test_unsafe_config_passed_directly_raises(self) -> None:
        config = object.__new__(ArchiveManifestConfig)
        object.__setattr__(config, "version", "1.0")
        object.__setattr__(config, "generated_at", None)
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
        with pytest.raises(ValueError, match="dry_run must be True"):
            build_archive_manifest_safety_flags(config)


# ---------------------------------------------------------------------------
# build_archive_artifact_entry
# ---------------------------------------------------------------------------


class TestBuildArchiveArtifactEntry:
    def test_ready_artifact_present(self) -> None:
        artifact = _make_artifact(state="READY")
        entry = build_archive_artifact_entry(
            ArchiveArtifactFamily.OBSERVATION_REPORT,
            artifact=artifact,
        )
        assert entry.state == "PRESENT"
        assert entry.artifact_family is ArchiveArtifactFamily.OBSERVATION_REPORT
        assert "data/observation/latest_observation_report.json" in entry.local_reference
        assert entry.spec_reference == "SPEC-011"

    def test_ready_artifact_dict_present(self) -> None:
        artifact = _make_artifact_dict(state="READY")
        entry = build_archive_artifact_entry(
            ArchiveArtifactFamily.OPERATOR_REVIEW,
            artifact=artifact,
        )
        assert entry.state == "PRESENT"

    def test_pass_artifact_present(self) -> None:
        artifact = _make_artifact(state="PASS")
        entry = build_archive_artifact_entry(
            ArchiveArtifactFamily.REVIEW_INDEX,
            artifact=artifact,
        )
        assert entry.state == "PRESENT"

    def test_missing_required_entry(self) -> None:
        entry = build_archive_artifact_entry(
            ArchiveArtifactFamily.REVIEW_SEARCH,
            artifact=None,
        )
        assert entry.state == "MISSING"
        assert "MISSING_REVIEW_SEARCH" in entry.reason_codes

    def test_missing_optional_entry_ready(self) -> None:
        config = ArchiveManifestConfig(required_families=())
        entry = build_archive_artifact_entry(
            ArchiveArtifactFamily.RESEARCH_BUNDLE,
            artifact=None,
            config=config,
        )
        assert entry.state == "PRESENT"
        assert entry.reason_codes == ()

    def test_stale_artifact_stale(self) -> None:
        stale = _now() - timedelta(hours=2)
        artifact = _make_artifact(state="READY", generated_at=stale)
        entry = build_archive_artifact_entry(
            ArchiveArtifactFamily.RESEARCH_CHRONICLE,
            artifact=artifact,
            reference_time=_now(),
        )
        assert entry.state == "STALE"
        assert "STALE_RESEARCH_CHRONICLE" in entry.reason_codes

    def test_unknown_artifact_block_by_default(self) -> None:
        artifact = _make_artifact(state="UNKNOWN")
        entry = build_archive_artifact_entry(
            ArchiveArtifactFamily.RESEARCH_DIGEST,
            artifact=artifact,
        )
        assert entry.state == "UNKNOWN"
        assert "UNKNOWN_RESEARCH_DIGEST" in entry.reason_codes

    def test_invalid_artifact_state_unknown(self) -> None:
        artifact = _make_artifact(state="CORRUPTED")
        entry = build_archive_artifact_entry(
            ArchiveArtifactFamily.RESEARCH_QUALITY_GATE,
            artifact=artifact,
        )
        assert entry.state == "UNKNOWN"
        assert "UNKNOWN_RESEARCH_QUALITY_GATE" in entry.reason_codes

    def test_unsafe_safety_flags_missing(self) -> None:
        flags = _make_unsafe_safety_flags("live_trading_enabled")
        artifact = _make_artifact(state="READY", safety_flags=flags)
        entry = build_archive_artifact_entry(
            ArchiveArtifactFamily.RESEARCH_HANDOFF,
            artifact=artifact,
        )
        assert entry.state == "MISSING"
        assert "UNSAFE_ARTIFACT_FLAGS" in entry.reason_codes

    def test_unresolved_blockers_missing(self) -> None:
        artifact = _make_artifact(state="READY", reason_codes=("MISSING_OBSERVATION_REPORT",))
        entry = build_archive_artifact_entry(
            ArchiveArtifactFamily.RESEARCH_QUALITY_GATE,
            artifact=artifact,
        )
        assert entry.state == "MISSING"
        assert "UNRESOLVED_BLOCKERS" in entry.reason_codes

    def test_entry_title(self) -> None:
        artifact = _make_artifact(state="READY")
        entry = build_archive_artifact_entry(
            ArchiveArtifactFamily.OBSERVATION_REPORT,
            artifact=artifact,
        )
        assert entry.title == "Observation Report"


# ---------------------------------------------------------------------------
# build_archive_manifest_summary
# ---------------------------------------------------------------------------


class TestBuildArchiveManifestSummary:
    def test_empty_entries(self) -> None:
        summary = build_archive_manifest_summary([])
        assert summary.total_families == 0
        assert summary.manifest_state == "UNKNOWN"

    def test_all_ready(self) -> None:
        entries = [
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OBSERVATION_REPORT, _make_artifact("READY")
            ),
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OPERATOR_REVIEW, _make_artifact("READY")
            ),
        ]
        summary = build_archive_manifest_summary(entries)
        assert summary.total_families == 2
        assert summary.present_count == 2
        assert summary.manifest_state == "READY"
        assert "human audit" in summary.manifest_notes
        assert "not trade approval" in summary.manifest_notes

    def test_warn_stale(self) -> None:
        stale = _now() - timedelta(hours=2)
        entries = [
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OBSERVATION_REPORT, _make_artifact("READY")
            ),
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OPERATOR_REVIEW,
                _make_artifact("READY", generated_at=stale),
                reference_time=_now(),
            ),
        ]
        summary = build_archive_manifest_summary(entries)
        assert summary.manifest_state == "WARN"
        assert "stale" in summary.manifest_notes.lower()
        assert "not execution readiness" in summary.manifest_notes

    def test_block_missing_required(self) -> None:
        entries = [
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OBSERVATION_REPORT, _make_artifact("READY")
            ),
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OPERATOR_REVIEW, None
            ),
        ]
        summary = build_archive_manifest_summary(entries)
        assert summary.manifest_state == "BLOCK"
        assert "not strategy readiness" in summary.manifest_notes

    def test_block_unknown_when_blocking(self) -> None:
        entries = [
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OBSERVATION_REPORT, _make_artifact("READY")
            ),
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OPERATOR_REVIEW, _make_artifact("UNKNOWN")
            ),
        ]
        summary = build_archive_manifest_summary(entries)
        assert summary.manifest_state == "BLOCK"

    def test_warn_unknown_when_not_blocking(self) -> None:
        config = ArchiveManifestConfig(block_on_unknown=False)
        entries = [
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OBSERVATION_REPORT, _make_artifact("READY")
            ),
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OPERATOR_REVIEW,
                _make_artifact("UNKNOWN"),
                config=config,
            ),
        ]
        summary = build_archive_manifest_summary(entries, config=config)
        assert summary.manifest_state == "WARN"

    def test_reason_code_counts(self) -> None:
        entries = [
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OBSERVATION_REPORT, _make_artifact("READY")
            ),
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OPERATOR_REVIEW, None
            ),
        ]
        summary = build_archive_manifest_summary(entries)
        assert summary.reason_code_counts.get("MISSING_OPERATOR_REVIEW") == 1


# ---------------------------------------------------------------------------
# build_archive_manifest_data_quality
# ---------------------------------------------------------------------------


class TestBuildArchiveManifestDataQuality:
    def test_empty_entries(self) -> None:
        dq = build_archive_manifest_data_quality([])
        assert dq.completeness_pct == 0.0
        assert dq.total_families == 0

    def test_completeness(self) -> None:
        entries = [
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OBSERVATION_REPORT, _make_artifact("READY")
            ),
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OPERATOR_REVIEW, None
            ),
        ]
        dq = build_archive_manifest_data_quality(entries)
        assert dq.completeness_pct == 50.0
        assert dq.present_pct == 50.0
        assert dq.total_families == 2

    def test_coverage(self) -> None:
        stale = _now() - timedelta(hours=2)
        entries = [
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OBSERVATION_REPORT, _make_artifact("READY")
            ),
            build_archive_artifact_entry(
                ArchiveArtifactFamily.OPERATOR_REVIEW,
                _make_artifact("READY", generated_at=stale),
                reference_time=_now(),
            ),
        ]
        dq = build_archive_manifest_data_quality(entries)
        assert dq.coverage_pct == 100.0


# ---------------------------------------------------------------------------
# build_research_archive_manifest
# ---------------------------------------------------------------------------


class TestBuildResearchArchiveManifest:
    def test_all_ready_ready(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        assert manifest.manifest_state is ArchiveManifestState.READY
        assert manifest.summary.manifest_state == "READY"
        assert manifest.summary.present_count == 9
        assert "human audit" in manifest.manifest_notes
        assert "not trade approval" in manifest.manifest_notes
        assert manifest.safety_flags.archive_output_not_execution_readiness is True
        assert manifest.safety_flags.archive_manifest_feedback_into_execution is False

    def test_missing_observation_blocked(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        assert manifest.manifest_state is ArchiveManifestState.BLOCK
        assert "MISSING_OBSERVATION_REPORT" in manifest.reason_codes

    def test_stale_digest_warn(self) -> None:
        stale = _now() - timedelta(hours=2)
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY", generated_at=stale),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        assert manifest.manifest_state is ArchiveManifestState.WARN
        assert "STALE_RESEARCH_DIGEST" in manifest.reason_codes

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
            config=ArchiveManifestConfig(
                generated_at=_now(),
                required_families=(),
            ),
        )
        assert manifest.manifest_state is ArchiveManifestState.BLOCK
        assert "EMPTY_MANIFEST" in manifest.reason_codes

    def test_deterministic_family_ordering(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        families = [e.artifact_family for e in manifest.entries]
        expected = [
            ArchiveArtifactFamily.OBSERVATION_REPORT,
            ArchiveArtifactFamily.OPERATOR_REVIEW,
            ArchiveArtifactFamily.REVIEW_INDEX,
            ArchiveArtifactFamily.REVIEW_SEARCH,
            ArchiveArtifactFamily.RESEARCH_BUNDLE,
            ArchiveArtifactFamily.RESEARCH_CHRONICLE,
            ArchiveArtifactFamily.RESEARCH_DIGEST,
            ArchiveArtifactFamily.RESEARCH_QUALITY_GATE,
            ArchiveArtifactFamily.RESEARCH_HANDOFF,
        ]
        assert families == expected

    def test_deterministic_manifest_id(self) -> None:
        generated_at = _now()
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=generated_at),
            observation_artifact=_make_artifact("READY"),
        )
        expected = f"archive:1.0:{generated_at.strftime('%Y-%m-%dT%H:%M:%S.%f')}"
        assert manifest.manifest_id == expected

    def test_ready_not_execution_or_strategy_approval(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        assert manifest.manifest_state is ArchiveManifestState.READY
        assert manifest.safety_flags.archive_output_not_trade_approval is True
        assert manifest.safety_flags.archive_output_not_execution_readiness is True
        assert manifest.safety_flags.archive_output_not_strategy_readiness is True
        assert "not execution readiness" in manifest.manifest_notes
        assert "not strategy readiness" in manifest.manifest_notes
        assert "not release/deployment approval" in manifest.manifest_notes

    def test_required_families_customization(self) -> None:
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
# Safety invariants
# ---------------------------------------------------------------------------


class TestSafetyInvariants:
    def test_no_execution_feedback(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        assert manifest.safety_flags.archive_manifest_feedback_into_execution is False
        assert manifest.safety_flags.cross_layer_feedback_into_execution is False

    def test_no_forbidden_terms_in_manifest_notes(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
        notes = manifest.manifest_notes.lower()
        for term in FORBIDDEN_ARCHIVE_MANIFEST_TERMS:
            assert term not in notes, term

    def test_file_references_are_strings_only(self) -> None:
        manifest = build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
        )
        assert manifest.manifest_id.startswith("archive:1.0:")
        observation_entry = next(
            e for e in manifest.entries if e.artifact_family is ArchiveArtifactFamily.OBSERVATION_REPORT
        )
        assert "data/observation/" in observation_entry.local_reference

    def test_no_forbidden_imports(self) -> None:
        engine_path = Path(__file__).parent.parent.parent / "src" / "hunter" / "research_archive_manifest" / "engine.py"
        models_path = Path(__file__).parent.parent.parent / "src" / "hunter" / "research_archive_manifest" / "models.py"
        for path in (engine_path, models_path):
            text = path.read_text(encoding="utf-8").lower()
            # Disallow actual imports of forbidden packages, not attribute names.
            for term in ("freqtrade", "binance", "requests", "sqlite"):
                assert f"import {term}" not in text, f"{path}: import {term}"
                assert f"from {term}" not in text, f"{path}: from {term}"
