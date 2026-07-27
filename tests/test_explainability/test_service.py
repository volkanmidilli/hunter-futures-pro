"""Lookup-service tests: fail-closed states (SPEC-078)."""

from __future__ import annotations

import json
from pathlib import Path

from hunter.explainability.models import (
    EXPLAINABILITY_SCHEMA_VERSION,
    REASON_ARTIFACT_INVALID,
    REASON_NO_SUCCESSFUL_RUN,
    REASON_NOT_IN_UNIVERSE,
    REASON_NOT_RECORDED,
    CandidateExplanationRecord,
    ExplainabilityRunManifest,
)
from hunter.explainability.service import LOOKUP_OK, explain_candidate
from hunter.explainability.storage import write_run


def _manifest(run_id: str = "run-1", **overrides) -> ExplainabilityRunManifest:
    kwargs = {
        "schema_version": EXPLAINABILITY_SCHEMA_VERSION,
        "run_id": run_id,
        "completed_at": "2026-07-27T00:00:00+00:00",
        "as_of_date": "2026-07-27",
        "ranking_profile": "V1_RS_OI",
        "universe_total": 412,
        "eligible_count": 2,
        "selected_count": 1,
        "target_final_pairs": 20,
        "min_pairs": 5,
        "max_pairs": 50,
        "gate_allowed": True,
        "published": True,
        "eligible_pairs": ("BTC/USDT:USDT", "ETH/USDT:USDT"),
    }
    kwargs.update(overrides)
    return ExplainabilityRunManifest(**kwargs)


def _record(run_id: str = "run-1", pair: str = "BTC/USDT:USDT") -> CandidateExplanationRecord:
    return CandidateExplanationRecord(
        schema_version=EXPLAINABILITY_SCHEMA_VERSION,
        run_id=run_id,
        completed_at="2026-07-27T00:00:00+00:00",
        pair=pair,
        final_rank=1,
        selected=True,
        published=True,
        final_reason_codes=("OK",),
    )


def _seed(tmp_path: Path) -> None:
    write_run(
        tmp_path,
        _manifest(),
        (_record(pair="BTC/USDT:USDT"), _record(pair="ETH/USDT:USDT")),
        update_latest=True,
    )


class TestSuccessfulLookup:
    def test_ok_result_carries_record_and_manifest(self, tmp_path: Path) -> None:
        _seed(tmp_path)
        result = explain_candidate("BTC/USDT:USDT", tmp_path)
        assert result.status == LOOKUP_OK
        assert result.record is not None
        assert result.record.pair == "BTC/USDT:USDT"
        assert result.manifest is not None
        assert result.manifest.run_id == "run-1"


class TestFailClosedStates:
    def test_no_successful_run(self, tmp_path: Path) -> None:
        result = explain_candidate("BTC/USDT:USDT", tmp_path)
        assert result.status == REASON_NO_SUCCESSFUL_RUN
        assert result.record is None
        assert result.manifest is None

    def test_not_in_universe(self, tmp_path: Path) -> None:
        _seed(tmp_path)
        result = explain_candidate("SOL/USDT:USDT", tmp_path)
        assert result.status == REASON_NOT_IN_UNIVERSE
        assert result.record is None
        # The run itself is real and reported.
        assert result.manifest is not None
        assert result.manifest.run_id == "run-1"

    def test_not_recorded(self, tmp_path: Path) -> None:
        _seed(tmp_path)
        # In the eligible universe per the manifest, but the candidate
        # artifact is missing: NOT_RECORDED, never inferred.
        orphan = tmp_path / "runs" / "run-1" / "candidates" / "ETH_USDT_USDT.json"
        orphan.unlink()
        result = explain_candidate("ETH/USDT:USDT", tmp_path)
        assert result.status == REASON_NOT_RECORDED
        assert result.record is None

    def test_corrupt_latest_pointer_is_artifact_invalid(self, tmp_path: Path) -> None:
        _seed(tmp_path)
        (tmp_path / "latest.json").write_text("{corrupt", encoding="utf-8")
        result = explain_candidate("BTC/USDT:USDT", tmp_path)
        assert result.status == REASON_ARTIFACT_INVALID

    def test_corrupt_candidate_is_artifact_invalid(self, tmp_path: Path) -> None:
        _seed(tmp_path)
        target = tmp_path / "runs" / "run-1" / "candidates" / "BTC_USDT_USDT.json"
        target.write_text(json.dumps({"schema_version": "x"}), encoding="utf-8")
        result = explain_candidate("BTC/USDT:USDT", tmp_path)
        assert result.status == REASON_ARTIFACT_INVALID

    def test_latest_pointing_at_missing_run_is_artifact_invalid(self, tmp_path: Path) -> None:
        _seed(tmp_path)
        pointer = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
        pointer["run_id"] = "missing-run"
        (tmp_path / "latest.json").write_text(json.dumps(pointer), encoding="utf-8")
        result = explain_candidate("BTC/USDT:USDT", tmp_path)
        assert result.status == REASON_ARTIFACT_INVALID


class TestDirResolution:
    def test_env_var_used_when_no_arg(self, tmp_path: Path, monkeypatch) -> None:
        _seed(tmp_path)
        monkeypatch.setenv("HUNTER_EXPLAINABILITY_DIR", str(tmp_path))
        result = explain_candidate("BTC/USDT:USDT")
        assert result.status == LOOKUP_OK

    def test_explicit_arg_beats_env_var(self, tmp_path: Path, monkeypatch) -> None:
        _seed(tmp_path)
        monkeypatch.setenv("HUNTER_EXPLAINABILITY_DIR", str(tmp_path / "elsewhere"))
        result = explain_candidate("BTC/USDT:USDT", tmp_path)
        assert result.status == LOOKUP_OK
