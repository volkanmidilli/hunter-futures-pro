"""Immutable-model and deterministic-serialization tests (SPEC-078)."""

from __future__ import annotations

import dataclasses
import json
from types import MappingProxyType

import pytest

from hunter.explainability.models import (
    EXPLAINABILITY_SCHEMA_VERSION,
    STAGE_FAIL,
    STAGE_PASS,
    STAGE_SKIP,
    STAGE_UNKNOWN,
    CandidateExplanationRecord,
    CandidateStageDecision,
    ExplainabilityModelError,
    ExplainabilityRunManifest,
)


def _stage(**overrides) -> CandidateStageDecision:
    kwargs = {
        "stage_id": "ranking",
        "stage_order": 5,
        "status": STAGE_FAIL,
        "metrics": {"rank": 31},
        "thresholds": {"target_final_pairs": 20},
        "reason_codes": ("OUTSIDE_TARGET_FINAL_PAIRS",),
        "metadata": {"selected": False},
    }
    kwargs.update(overrides)
    return CandidateStageDecision(**kwargs)


def _record(**overrides) -> CandidateExplanationRecord:
    kwargs = {
        "schema_version": EXPLAINABILITY_SCHEMA_VERSION,
        "run_id": "2026-07-27__V1_RS_OI__abcdef123456",
        "completed_at": "2026-07-27T00:00:00+00:00",
        "pair": "BTC/USDT:USDT",
        "stages": (_stage(),),
        "score_components": {"rs_score": "72.30", "oi_score": None},
        "final_rank": 31,
        "eligible_candidate_count": 50,
        "target_final_pairs": 20,
        "selected": False,
        "published": False,
        "final_reason_codes": ("OUTSIDE_TARGET_FINAL_PAIRS",),
    }
    kwargs.update(overrides)
    return CandidateExplanationRecord(**kwargs)


class TestStageStatuses:
    @pytest.mark.parametrize("status", [STAGE_PASS, STAGE_FAIL, STAGE_SKIP, STAGE_UNKNOWN])
    def test_all_statuses_accepted(self, status: str) -> None:
        assert _stage(status=status).status == status

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ExplainabilityModelError):
            _stage(status="MAYBE")


class TestImmutability:
    def test_stage_is_frozen(self) -> None:
        stage = _stage()
        with pytest.raises(dataclasses.FrozenInstanceError):
            stage.status = STAGE_PASS  # type: ignore[misc]

    def test_record_is_frozen(self) -> None:
        record = _record()
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.selected = True  # type: ignore[misc]

    def test_metrics_mapping_is_immutable(self) -> None:
        stage = _stage()
        assert isinstance(stage.metrics, MappingProxyType)
        with pytest.raises(TypeError):
            stage.metrics["rank"] = 1  # type: ignore[index]

    def test_score_components_mapping_is_immutable(self) -> None:
        record = _record()
        assert isinstance(record.score_components, MappingProxyType)
        with pytest.raises(TypeError):
            record.score_components["rs_score"] = "0"  # type: ignore[index]

    def test_caller_mutation_after_construction_does_not_leak(self) -> None:
        metrics = {"rank": 31}
        stage = _stage(metrics=metrics)
        metrics["rank"] = 999
        assert stage.metrics["rank"] == 31

    def test_duplicate_stage_order_rejected(self) -> None:
        with pytest.raises(ExplainabilityModelError):
            _record(stages=(_stage(stage_order=1), _stage(stage_id="other", stage_order=1)))

    def test_invalid_final_score_rejected(self) -> None:
        with pytest.raises(ExplainabilityModelError):
            _record(final_score="high")  # type: ignore[arg-type]


class TestDeterministicSerialization:
    def test_stage_round_trip(self) -> None:
        stage = _stage()
        assert CandidateStageDecision.from_dict(stage.to_dict()) == stage

    def test_record_round_trip(self) -> None:
        record = _record()
        assert CandidateExplanationRecord.from_dict(record.to_dict()) == record

    def test_serialization_is_byte_stable(self) -> None:
        record = _record()
        text1 = json.dumps(record.to_dict(), indent=2, sort_keys=True)
        text2 = json.dumps(_record().to_dict(), indent=2, sort_keys=True)
        assert text1 == text2

    def test_arbitrary_metrics_and_thresholds_preserved(self) -> None:
        stage = _stage(
            metrics={"rank": 31, "custom_metric": "0.123456789", "flag": True, "missing": None},
            thresholds={"cutoff": 20, "min_pairs": 5, "note": "exact-target"},
        )
        restored = CandidateStageDecision.from_dict(stage.to_dict())
        assert restored.metrics == stage.metrics
        assert restored.thresholds == stage.thresholds

    def test_from_dict_rejects_missing_required_field(self) -> None:
        payload = _record().to_dict()
        del payload["run_id"]
        with pytest.raises(ExplainabilityModelError):
            CandidateExplanationRecord.from_dict(payload)

    def test_from_dict_rejects_non_mapping(self) -> None:
        with pytest.raises(ExplainabilityModelError):
            CandidateExplanationRecord.from_dict(["not", "a", "mapping"])  # type: ignore[arg-type]


class TestManifest:
    def _manifest(self, **overrides) -> ExplainabilityRunManifest:
        kwargs = {
            "schema_version": EXPLAINABILITY_SCHEMA_VERSION,
            "run_id": "run-1",
            "completed_at": "2026-07-27T00:00:00+00:00",
            "as_of_date": "2026-07-27",
            "ranking_profile": "V1_RS_OI",
            "universe_total": 412,
            "eligible_count": 50,
            "selected_count": 20,
            "target_final_pairs": 20,
            "min_pairs": 5,
            "max_pairs": 50,
            "gate_allowed": True,
            "gate_reason_codes": ("OK",),
            "published": True,
            "eligible_pairs": ("BTC/USDT:USDT", "ETH/USDT:USDT"),
        }
        kwargs.update(overrides)
        return ExplainabilityRunManifest(**kwargs)

    def test_round_trip(self) -> None:
        manifest = self._manifest()
        assert ExplainabilityRunManifest.from_dict(manifest.to_dict()) == manifest

    def test_frozen(self) -> None:
        manifest = self._manifest()
        with pytest.raises(dataclasses.FrozenInstanceError):
            manifest.published = False  # type: ignore[misc]

    def test_non_int_count_rejected(self) -> None:
        with pytest.raises(ExplainabilityModelError):
            self._manifest(eligible_count="50")
