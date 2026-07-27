"""Provenance and pointer-policy tests (SPEC-078 provenance update)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hunter.explainability.models import (
    EXPLAINABILITY_SCHEMA_VERSION,
    PROVENANCE_ORIGINAL,
    PROVENANCE_RECONSTRUCTED,
    CandidateExplanationRecord,
    ExplainabilityModelError,
    ExplainabilityRunManifest,
)
from hunter.explainability.storage import (
    read_latest_pointer,
    should_advance_reconstructed_pointer,
    write_latest_pointer,
    write_run,
)


def _manifest(run_id: str = "run-1", as_of: str = "2026-07-27", **overrides) -> ExplainabilityRunManifest:
    kwargs = {
        "schema_version": EXPLAINABILITY_SCHEMA_VERSION,
        "run_id": run_id,
        "completed_at": "2026-07-27T00:00:00+00:00",
        "as_of_date": as_of,
        "ranking_profile": "V1_RS_OI",
        "universe_total": 412,
        "eligible_count": 1,
        "selected_count": 1,
        "target_final_pairs": 20,
        "min_pairs": 5,
        "max_pairs": 50,
        "gate_allowed": True,
        "published": True,
        "eligible_pairs": ("BTC/USDT:USDT",),
    }
    kwargs.update(overrides)
    return ExplainabilityRunManifest(**kwargs)


def _record(run_id: str = "run-1", **overrides) -> CandidateExplanationRecord:
    kwargs = {
        "schema_version": EXPLAINABILITY_SCHEMA_VERSION,
        "run_id": run_id,
        "completed_at": "2026-07-27T00:00:00+00:00",
        "pair": "BTC/USDT:USDT",
        "final_rank": 1,
        "selected": True,
        "published": True,
        "final_reason_codes": ("OK",),
    }
    kwargs.update(overrides)
    return CandidateExplanationRecord(**kwargs)


class TestProvenanceDefaults:
    def test_new_models_default_to_original(self) -> None:
        assert _manifest().provenance_type == PROVENANCE_ORIGINAL
        assert _record().provenance_type == PROVENANCE_ORIGINAL

    def test_missing_provenance_deserializes_as_reconstructed(self) -> None:
        """Pre-provenance artifacts must never imply ORIGINAL provenance."""
        manifest_payload = _manifest().to_dict()
        del manifest_payload["provenance_type"]
        manifest = ExplainabilityRunManifest.from_dict(manifest_payload)
        assert manifest.provenance_type == PROVENANCE_RECONSTRUCTED

        record_payload = _record().to_dict()
        del record_payload["provenance_type"]
        record = CandidateExplanationRecord.from_dict(record_payload)
        assert record.provenance_type == PROVENANCE_RECONSTRUCTED

    def test_invalid_provenance_rejected(self) -> None:
        with pytest.raises(ExplainabilityModelError):
            _manifest(provenance_type="GUESSED")
        with pytest.raises(ExplainabilityModelError):
            _record(provenance_type="ORIGINAL-ish")

    def test_provenance_round_trip(self) -> None:
        manifest = _manifest(
            provenance_type=PROVENANCE_RECONSTRUCTED,
            source_run_id="legacy-run",
            source_artifact_paths=("/opt/x/hunter-pairs.json",),
            reconstruction_notes="migrated",
            decision_records_complete=False,
        )
        restored = ExplainabilityRunManifest.from_dict(manifest.to_dict())
        assert restored == manifest
        assert restored.decision_records_complete is False
        assert restored.source_artifact_paths == ("/opt/x/hunter-pairs.json",)

    def test_nullable_counts(self) -> None:
        manifest = _manifest(target_final_pairs=None, min_pairs=None, max_pairs=None)
        assert ExplainabilityRunManifest.from_dict(manifest.to_dict()) == manifest

    def test_runtime_records_carry_original_provenance(self) -> None:
        from decimal import Decimal

        from hunter.explainability.recorder import PairlistRunObservation, build_run_records
        from hunter.pairlist_export.models import RankedPair

        obs = PairlistRunObservation(
            as_of_date="2026-07-27",
            ranking_profile="V1_RS_OI",
            universe_total=100,
            eligible_pairs=("BTC/USDT:USDT",),
            ranked_pairs=(
                RankedPair(
                    pair="BTC/USDT:USDT",
                    rank=1,
                    selected=True,
                    rs_score=Decimal("80"),
                    oi_score=Decimal("50"),
                    reason_codes=("RS_SCORE", "OI_LIQUIDITY"),
                    fingerprint="fp",
                ),
            ),
            target_final_pairs=20,
            min_pairs=5,
            max_pairs=50,
            gate_allowed=True,
            gate_reason_codes=("OK",),
            published=True,
        )
        manifest, records = build_run_records(obs, completed_at="2026-07-27T00:00:00+00:00")
        assert manifest.provenance_type == PROVENANCE_ORIGINAL
        assert manifest.decision_records_complete is True
        assert records[0].provenance_type == PROVENANCE_ORIGINAL


class TestPointerPolicy:
    def _write_original(self, tmp_path: Path, run_id: str = "orig-run") -> None:
        write_run(tmp_path, _manifest(run_id), (_record(run_id),), update_latest=True)

    def test_runtime_pointer_carries_provenance_and_date(self, tmp_path: Path) -> None:
        self._write_original(tmp_path)
        pointer = read_latest_pointer(tmp_path)
        assert pointer["provenance_type"] == PROVENANCE_ORIGINAL
        assert pointer["as_of_date"] == "2026-07-27"

    def test_reconstructed_never_replaces_original(self, tmp_path: Path) -> None:
        self._write_original(tmp_path)
        assert should_advance_reconstructed_pointer(tmp_path, new_as_of_date="2999-01-01") is False

    def test_no_pointer_advances(self, tmp_path: Path) -> None:
        assert should_advance_reconstructed_pointer(tmp_path, new_as_of_date="2026-07-21") is True

    def test_newer_reconstructed_replaces_older(self, tmp_path: Path) -> None:
        write_latest_pointer(tmp_path, _manifest("old", as_of="2026-07-21",
                                                 provenance_type=PROVENANCE_RECONSTRUCTED))
        assert should_advance_reconstructed_pointer(tmp_path, new_as_of_date="2026-07-27") is True

    def test_older_or_equal_reconstructed_does_not_replace(self, tmp_path: Path) -> None:
        write_latest_pointer(tmp_path, _manifest("new", as_of="2026-07-27",
                                                 provenance_type=PROVENANCE_RECONSTRUCTED))
        assert should_advance_reconstructed_pointer(tmp_path, new_as_of_date="2026-07-27") is False
        assert should_advance_reconstructed_pointer(tmp_path, new_as_of_date="2026-07-21") is False

    def test_pre_provenance_pointer_is_advanced(self, tmp_path: Path) -> None:
        # A pointer written before provenance tracking (no provenance/as_of
        # keys) must not block the actual production publish.
        (tmp_path / "latest.json").write_text(
            json.dumps({"schema_version": "spec-078-explainability-v1", "run_id": "old",
                        "completed_at": "2026-07-27T00:00:00+00:00"}),
            encoding="utf-8",
        )
        assert should_advance_reconstructed_pointer(tmp_path, new_as_of_date="2026-07-21") is True

    def test_corrupt_pointer_is_advanced(self, tmp_path: Path) -> None:
        (tmp_path / "latest.json").write_text("{corrupt", encoding="utf-8")
        assert should_advance_reconstructed_pointer(tmp_path, new_as_of_date="2026-07-21") is True
