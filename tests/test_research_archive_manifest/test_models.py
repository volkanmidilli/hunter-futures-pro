"""Tests for hunter.research_archive_manifest.models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from hunter.research_archive_manifest.models import (
    ARCHIVE_BLOCKING_REASON_CODES,
    ARCHIVE_MANIFEST_VERSION,
    ARCHIVE_REASON_CODES,
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


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestArchiveManifestState:
    def test_enum_values(self) -> None:
        assert ArchiveManifestState.READY.value == "ready"
        assert ArchiveManifestState.WARN.value == "warn"
        assert ArchiveManifestState.BLOCK.value == "block"
        assert ArchiveManifestState.UNKNOWN.value == "unknown"


class TestArchiveArtifactFamily:
    def test_enum_values(self) -> None:
        assert ArchiveArtifactFamily.OBSERVATION_REPORT.value == "observation_report"
        assert ArchiveArtifactFamily.RESEARCH_HANDOFF.value == "research_handoff"

    def test_deterministic_order(self) -> None:
        values = [kind.value for kind in ArchiveArtifactFamily]
        assert values == [
            "observation_report",
            "operator_review",
            "review_index",
            "review_search",
            "research_bundle",
            "research_chronicle",
            "research_digest",
            "research_quality_gate",
            "research_handoff",
        ]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_archive_manifest_version(self) -> None:
        assert ARCHIVE_MANIFEST_VERSION == "1.0"

    def test_reason_codes(self) -> None:
        assert len(ARCHIVE_REASON_CODES) == 34
        assert "EMPTY_MANIFEST" in ARCHIVE_REASON_CODES
        assert "INVALID_CONFIG" in ARCHIVE_REASON_CODES
        assert "UNSAFE_CONFIG" in ARCHIVE_REASON_CODES
        assert "MISSING_OBSERVATION_REPORT" in ARCHIVE_REASON_CODES
        assert "MISSING_RESEARCH_HANDOFF" in ARCHIVE_REASON_CODES
        assert "STALE_OBSERVATION_REPORT" in ARCHIVE_REASON_CODES
        assert "STALE_RESEARCH_HANDOFF" in ARCHIVE_REASON_CODES
        assert "UNKNOWN_OBSERVATION_REPORT" in ARCHIVE_REASON_CODES
        assert "UNKNOWN_RESEARCH_HANDOFF" in ARCHIVE_REASON_CODES
        assert "UNSAFE_ARTIFACT_FLAGS" in ARCHIVE_REASON_CODES
        assert "UNRESOLVED_BLOCKERS" in ARCHIVE_REASON_CODES
        assert "UNSAFE_MANIFEST_CONTENT" in ARCHIVE_REASON_CODES
        assert "ARCHIVE_ERROR" in ARCHIVE_REASON_CODES

    def test_blocking_reason_codes(self) -> None:
        assert "EMPTY_MANIFEST" not in ARCHIVE_BLOCKING_REASON_CODES
        assert "INVALID_CONFIG" in ARCHIVE_BLOCKING_REASON_CODES
        assert "MISSING_OBSERVATION_REPORT" in ARCHIVE_BLOCKING_REASON_CODES
        assert "STALE_OBSERVATION_REPORT" in ARCHIVE_BLOCKING_REASON_CODES
        assert "UNRESOLVED_BLOCKERS" in ARCHIVE_BLOCKING_REASON_CODES

    def test_forbidden_terms_superset_of_handoff(self) -> None:
        from hunter.research_handoff.models import FORBIDDEN_HANDOFF_TERMS

        for term in FORBIDDEN_HANDOFF_TERMS:
            # "deploy" is omitted because the required safety disclaimer uses
            # "release/deployment approval", which contains "deploy" as a substring.
            if term == "deploy":
                continue
            assert term in FORBIDDEN_ARCHIVE_MANIFEST_TERMS, term

    def test_forbidden_terms_include_archive_specific(self) -> None:
        for term in ("go_live", "production_ready", "execution_ready"):
            assert term in FORBIDDEN_ARCHIVE_MANIFEST_TERMS


# ---------------------------------------------------------------------------
# ArchiveManifestConfig
# ---------------------------------------------------------------------------


class TestArchiveManifestConfig:
    def test_default_construction(self) -> None:
        config = ArchiveManifestConfig()
        assert config.version == "1.0"
        assert config.output_format == "both"
        assert config.dry_run is True
        assert config.live_trading_enabled is False
        assert config.block_on_unknown is True
        assert config.max_staleness_minutes == 60
        assert len(config.required_families) == 9

    def test_invalid_version_empty(self) -> None:
        with pytest.raises(ValueError, match="version must be a non-empty string"):
            ArchiveManifestConfig(version="")

    def test_invalid_output_format(self) -> None:
        with pytest.raises(ValueError, match="output_format must be one of"):
            ArchiveManifestConfig(output_format="xml")

    def test_invalid_dry_run_false(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            ArchiveManifestConfig(dry_run=False)

    @pytest.mark.parametrize("attr", [
        "live_trading_enabled",
        "real_orders_enabled",
        "leverage_enabled",
        "shorting_enabled",
    ])
    def test_invalid_unsafe_flags_true(self, attr: str) -> None:
        with pytest.raises(ValueError, match=f"{attr} must be False"):
            ArchiveManifestConfig(**{attr: True})

    def test_invalid_block_on_unknown_non_bool(self) -> None:
        with pytest.raises(ValueError, match="block_on_unknown must be a bool"):
            ArchiveManifestConfig(block_on_unknown="yes")  # type: ignore[arg-type]

    def test_invalid_required_families(self) -> None:
        with pytest.raises(
            ValueError, match="required_families must contain ArchiveArtifactFamily"
        ):
            ArchiveManifestConfig(required_families=("observation_report",))  # type: ignore[arg-type]

    def test_invalid_staleness_zero(self) -> None:
        with pytest.raises(
            ValueError, match="max_staleness_minutes must be a positive integer"
        ):
            ArchiveManifestConfig(max_staleness_minutes=0)

    def test_frozen(self) -> None:
        config = ArchiveManifestConfig()
        with pytest.raises(FrozenInstanceError):
            config.dry_run = False


# ---------------------------------------------------------------------------
# ArchiveManifestSafetyFlags
# ---------------------------------------------------------------------------


class TestArchiveManifestSafetyFlags:
    def test_default_construction(self) -> None:
        flags = ArchiveManifestSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.archive_output_is_human_audit_only is True
        assert flags.archive_output_not_execution_readiness is True
        assert flags.archive_output_not_strategy_readiness is True
        assert flags.archive_manifest_feedback_into_execution is False
        assert flags.cross_layer_feedback_into_execution is False
        assert flags.file_refs_not_traversed is True
        assert flags.artifact_files_not_read is True

    def test_unsafe_flag_true_raises(self) -> None:
        with pytest.raises(ValueError, match="unsafe archive manifest safety flags are enabled"):
            ArchiveManifestSafetyFlags(live_trading_enabled=True)
        with pytest.raises(ValueError, match="unsafe archive manifest safety flags are enabled"):
            ArchiveManifestSafetyFlags(archive_manifest_feedback_into_execution=True)
        with pytest.raises(ValueError, match="unsafe archive manifest safety flags are enabled"):
            ArchiveManifestSafetyFlags(cross_layer_feedback_into_execution=True)

    def test_dry_run_false_raises(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            ArchiveManifestSafetyFlags(dry_run=False)

    def test_safe_output_flag_false_raises(self) -> None:
        with pytest.raises(ValueError, match="safe archive manifest output flags must be True"):
            ArchiveManifestSafetyFlags(archive_output_is_human_audit_only=False)

    def test_advisory_flag_false_raises(self) -> None:
        with pytest.raises(ValueError, match="safe archive manifest output flags must be True"):
            ArchiveManifestSafetyFlags(file_refs_not_traversed=False)

    def test_frozen(self) -> None:
        flags = ArchiveManifestSafetyFlags()
        with pytest.raises(FrozenInstanceError):
            flags.dry_run = False


# ---------------------------------------------------------------------------
# ArchiveArtifactEntry
# ---------------------------------------------------------------------------


class TestArchiveArtifactEntry:
    def test_valid_construction(self) -> None:
        entry = ArchiveArtifactEntry(
            artifact_family=ArchiveArtifactFamily.OBSERVATION_REPORT,
            state="PRESENT",
        )
        assert entry.artifact_family is ArchiveArtifactFamily.OBSERVATION_REPORT
        assert entry.state == "PRESENT"

    def test_state_normalized(self) -> None:
        entry = ArchiveArtifactEntry(
            artifact_family=ArchiveArtifactFamily.REVIEW_INDEX,
            state="stale",
        )
        assert entry.state == "STALE"

    def test_invalid_family(self) -> None:
        with pytest.raises(ValueError, match="artifact_family must be an ArchiveArtifactFamily"):
            ArchiveArtifactEntry(artifact_family="observation_report")  # type: ignore[arg-type]

    def test_invalid_state(self) -> None:
        with pytest.raises(ValueError, match="state must be one of"):
            ArchiveArtifactEntry(
                artifact_family=ArchiveArtifactFamily.RESEARCH_BUNDLE,
                state="CORRUPTED",
            )

    def test_unsafe_spec_reference_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_MANIFEST_CONTENT"):
            ArchiveArtifactEntry(
                artifact_family=ArchiveArtifactFamily.OBSERVATION_REPORT,
                spec_reference="go_live now",
            )

    def test_unsafe_local_reference_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_MANIFEST_CONTENT"):
            ArchiveArtifactEntry(
                artifact_family=ArchiveArtifactFamily.OBSERVATION_REPORT,
                local_reference="path/to/secret api_key",
            )

    def test_unsafe_metadata_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_MANIFEST_CONTENT"):
            ArchiveArtifactEntry(
                artifact_family=ArchiveArtifactFamily.OBSERVATION_REPORT,
                metadata={"go_live": "true"},
            )

    def test_file_reference_not_traversed(self) -> None:
        entry = ArchiveArtifactEntry(
            artifact_family=ArchiveArtifactFamily.OBSERVATION_REPORT,
            local_reference="data/observation/latest_observation_report.json",
        )
        assert entry.local_reference == "data/observation/latest_observation_report.json"

    def test_reason_codes_coerced(self) -> None:
        entry = ArchiveArtifactEntry(
            artifact_family=ArchiveArtifactFamily.OBSERVATION_REPORT,
            reason_codes=["MISSING_OBSERVATION_REPORT"],
        )
        assert entry.reason_codes == ("MISSING_OBSERVATION_REPORT",)


# ---------------------------------------------------------------------------
# ArchiveManifestSummary
# ---------------------------------------------------------------------------


class TestArchiveManifestSummary:
    def test_default_construction(self) -> None:
        summary = ArchiveManifestSummary()
        assert summary.total_families == 0
        assert summary.manifest_state == "UNKNOWN"

    def test_valid_construction(self) -> None:
        summary = ArchiveManifestSummary(
            total_families=4,
            present_count=2,
            stale_count=1,
            missing_count=1,
            unknown_count=0,
            manifest_state="WARN",
        )
        assert summary.present_count + summary.stale_count + summary.missing_count == 4

    def test_count_mismatch_raises(self) -> None:
        with pytest.raises(
            ValueError, match=r"present_count \+ stale_count \+ missing_count \+ unknown_count"
        ):
            ArchiveManifestSummary(
                total_families=4,
                present_count=2,
                stale_count=0,
                missing_count=0,
                unknown_count=0,
            )

    def test_invalid_manifest_state(self) -> None:
        with pytest.raises(ValueError, match="manifest_state must be one of"):
            ArchiveManifestSummary(manifest_state="CORRUPTED")

    def test_unsafe_manifest_notes_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_MANIFEST_CONTENT"):
            ArchiveManifestSummary(manifest_notes="go_live now")


# ---------------------------------------------------------------------------
# ArchiveManifestDataQuality
# ---------------------------------------------------------------------------


class TestArchiveManifestDataQuality:
    def test_default_construction(self) -> None:
        dq = ArchiveManifestDataQuality()
        assert dq.completeness_pct == 0.0
        assert dq.total_families == 0

    def test_completeness_pct_range(self) -> None:
        with pytest.raises(ValueError, match="completeness_pct must be between"):
            ArchiveManifestDataQuality(completeness_pct=101.0)

    def test_coverage_pct_range(self) -> None:
        with pytest.raises(ValueError, match="coverage_pct must be between"):
            ArchiveManifestDataQuality(coverage_pct=-1.0)

    def test_unsafe_reason_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_MANIFEST_CONTENT"):
            ArchiveManifestDataQuality(reason="contains secret api_key")


# ---------------------------------------------------------------------------
# ResearchArchiveManifest
# ---------------------------------------------------------------------------


class TestResearchArchiveManifest:
    def test_valid_construction(self) -> None:
        now = datetime.now(timezone.utc)
        manifest = ResearchArchiveManifest(
            manifest_id="archive:1.0:2025-01-01T00:00:00",
            generated_at=now,
            manifest_state=ArchiveManifestState.READY,
        )
        assert manifest.manifest_id == "archive:1.0:2025-01-01T00:00:00"
        assert manifest.generated_at == now
        assert manifest.manifest_state is ArchiveManifestState.READY

    def test_default_manifest_state(self) -> None:
        now = datetime.now(timezone.utc)
        manifest = ResearchArchiveManifest(manifest_id="m1", generated_at=now)
        assert manifest.manifest_state is ArchiveManifestState.UNKNOWN

    def test_invalid_manifest_id_empty(self) -> None:
        with pytest.raises(ValueError, match="manifest_id must be a non-empty string"):
            ResearchArchiveManifest(manifest_id="", generated_at=datetime.now(timezone.utc))

    def test_invalid_generated_at_naive(self) -> None:
        with pytest.raises(ValueError, match="generated_at must be a timezone-aware datetime"):
            ResearchArchiveManifest(manifest_id="m1", generated_at=datetime.now())

    def test_invalid_manifest_state_type(self) -> None:
        with pytest.raises(ValueError, match="manifest_state must be an ArchiveManifestState"):
            ResearchArchiveManifest(
                manifest_id="m1",
                generated_at=datetime.now(timezone.utc),
                manifest_state="READY",  # type: ignore[arg-type]
            )

    def test_blocked_factory(self) -> None:
        now = datetime.now(timezone.utc)
        manifest = ResearchArchiveManifest.blocked("INVALID_CONFIG", generated_at=now)
        assert manifest.manifest_state is ArchiveManifestState.BLOCK
        assert manifest.reason_codes == ("INVALID_CONFIG",)
        assert "Archive manifest blocked: INVALID_CONFIG" in manifest.summary.manifest_notes
        assert "not trade approval" in manifest.summary.manifest_notes

    def test_frozen(self) -> None:
        now = datetime.now(timezone.utc)
        manifest = ResearchArchiveManifest(manifest_id="m1", generated_at=now)
        with pytest.raises(FrozenInstanceError):
            manifest.manifest_id = "m2"

    def test_unsafe_manifest_notes_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_MANIFEST_CONTENT"):
            ResearchArchiveManifest(
                manifest_id="m1",
                generated_at=datetime.now(timezone.utc),
                manifest_notes="go_live now",
            )
