"""Storage tests: atomic writes, latest-pointer discipline, corrupt artifacts (SPEC-078)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hunter.explainability.models import (
    EXPLAINABILITY_SCHEMA_VERSION,
    CandidateExplanationRecord,
    ExplainabilityRunManifest,
    ExplainabilityStorageError,
)
from hunter.explainability.storage import (
    candidate_filename,
    read_candidate,
    read_latest_pointer,
    read_manifest,
    write_run,
)


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


def _record(run_id: str = "run-1", pair: str = "BTC/USDT:USDT", **overrides) -> CandidateExplanationRecord:
    kwargs = {
        "schema_version": EXPLAINABILITY_SCHEMA_VERSION,
        "run_id": run_id,
        "completed_at": "2026-07-27T00:00:00+00:00",
        "pair": pair,
        "final_rank": 1,
        "selected": True,
        "published": True,
        "final_reason_codes": ("OK",),
    }
    kwargs.update(overrides)
    return CandidateExplanationRecord(**kwargs)


def _write_success(tmp_path: Path, run_id: str = "run-1"):
    manifest = _manifest(run_id)
    records = (_record(run_id, "BTC/USDT:USDT"), _record(run_id, "ETH/USDT:USDT"))
    return write_run(tmp_path, manifest, records, update_latest=True)


class TestLayoutAndRoundTrip:
    def test_layout_matches_spec(self, tmp_path: Path) -> None:
        run_dir = _write_success(tmp_path)
        assert run_dir == tmp_path / "runs" / "run-1"
        assert (run_dir / "manifest.json").is_file()
        assert (run_dir / "candidates" / "BTC_USDT_USDT.json").is_file()
        assert (run_dir / "candidates" / "ETH_USDT_USDT.json").is_file()
        assert (tmp_path / "latest.json").is_file()

    def test_candidate_filename(self) -> None:
        assert candidate_filename("BTC/USDT:USDT") == "BTC_USDT_USDT.json"

    def test_round_trip(self, tmp_path: Path) -> None:
        manifest = _manifest()
        records = (_record(pair="BTC/USDT:USDT"),)
        write_run(tmp_path, manifest, records, update_latest=True)
        assert read_manifest(tmp_path, "run-1") == manifest
        assert read_candidate(tmp_path, "run-1", "BTC/USDT:USDT") == records[0]

    def test_latest_pointer_points_at_run(self, tmp_path: Path) -> None:
        _write_success(tmp_path)
        pointer = read_latest_pointer(tmp_path)
        assert pointer is not None
        assert pointer["run_id"] == "run-1"
        assert pointer["schema_version"] == EXPLAINABILITY_SCHEMA_VERSION


class TestAtomicWrites:
    def test_no_temp_files_left_behind(self, tmp_path: Path) -> None:
        _write_success(tmp_path)
        leftovers = [p for p in tmp_path.rglob("*") if p.name.endswith(".tmp")]
        assert leftovers == []

    def test_written_json_is_canonical(self, tmp_path: Path) -> None:
        _write_success(tmp_path)
        text = (tmp_path / "latest.json").read_text(encoding="utf-8")
        payload = json.loads(text)
        assert text == json.dumps(payload, indent=2, sort_keys=True) + "\n"


class TestLatestPointerDiscipline:
    def test_missing_latest_returns_none(self, tmp_path: Path) -> None:
        assert read_latest_pointer(tmp_path) is None

    def test_failed_run_does_not_create_latest(self, tmp_path: Path) -> None:
        write_run(tmp_path, _manifest(), (_record(),), update_latest=False)
        assert read_latest_pointer(tmp_path) is None
        # Artifacts are still persisted for forensics.
        assert (tmp_path / "runs" / "run-1" / "manifest.json").is_file()

    def test_failed_run_never_replaces_latest_successful_run(self, tmp_path: Path) -> None:
        _write_success(tmp_path, run_id="run-good")
        failed = _manifest("run-bad", gate_allowed=False, published=False,
                           gate_reason_codes=("BELOW_MIN_PAIRS",))
        write_run(tmp_path, failed, (_record("run-bad"),), update_latest=False)
        pointer = read_latest_pointer(tmp_path)
        assert pointer is not None
        assert pointer["run_id"] == "run-good"

    def test_new_successful_run_replaces_latest(self, tmp_path: Path) -> None:
        _write_success(tmp_path, run_id="run-1")
        _write_success(tmp_path, run_id="run-2")
        pointer = read_latest_pointer(tmp_path)
        assert pointer is not None
        assert pointer["run_id"] == "run-2"


class TestImmutability:
    def test_identical_rerun_is_noop(self, tmp_path: Path) -> None:
        _write_success(tmp_path)
        before = (tmp_path / "runs" / "run-1" / "manifest.json").read_text(encoding="utf-8")
        # Same content, different wall-clock completed_at: still a no-op.
        rerun = _manifest(completed_at="2026-07-28T00:00:00+00:00")
        write_run(tmp_path, rerun, (_record(completed_at="2026-07-28T00:00:00+00:00"),),
                  update_latest=True)
        after = (tmp_path / "runs" / "run-1" / "manifest.json").read_text(encoding="utf-8")
        assert before == after

    def test_conflicting_content_rejected(self, tmp_path: Path) -> None:
        _write_success(tmp_path)
        conflicting = _manifest(selected_count=99)
        with pytest.raises(ExplainabilityStorageError):
            write_run(tmp_path, conflicting, (_record(),), update_latest=False)

    def test_run_id_mismatch_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ExplainabilityStorageError):
            write_run(tmp_path, _manifest("run-1"), (_record("run-other"),),
                      update_latest=False)

    def test_unsafe_run_id_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ExplainabilityStorageError):
            write_run(tmp_path, _manifest("../evil"), (_record("../evil"),),
                      update_latest=False)


class TestCorruptArtifacts:
    def test_corrupt_latest_pointer(self, tmp_path: Path) -> None:
        (tmp_path / "latest.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(ExplainabilityStorageError):
            read_latest_pointer(tmp_path)

    def test_malformed_latest_pointer(self, tmp_path: Path) -> None:
        (tmp_path / "latest.json").write_text('{"no_run_id": true}', encoding="utf-8")
        with pytest.raises(ExplainabilityStorageError):
            read_latest_pointer(tmp_path)

    def test_missing_manifest(self, tmp_path: Path) -> None:
        with pytest.raises(ExplainabilityStorageError):
            read_manifest(tmp_path, "no-such-run")

    def test_corrupt_manifest(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "runs" / "run-1"
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text("[1,2,3]", encoding="utf-8")
        with pytest.raises(ExplainabilityStorageError):
            read_manifest(tmp_path, "run-1")

    def test_corrupt_candidate(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "runs" / "run-1" / "candidates"
        run_dir.mkdir(parents=True)
        (run_dir / "BTC_USDT_USDT.json").write_text("{corrupt", encoding="utf-8")
        with pytest.raises(ExplainabilityStorageError):
            read_candidate(tmp_path, "run-1", "BTC/USDT:USDT")

    def test_missing_candidate_returns_none(self, tmp_path: Path) -> None:
        _write_success(tmp_path)
        assert read_candidate(tmp_path, "run-1", "SOL/USDT:USDT") is None


class TestForbiddenDirs:
    def test_data_dir_rejected(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with pytest.raises(Exception):
            write_run(repo_root / "data", _manifest(), (_record(),), update_latest=False)

    def test_reports_dir_rejected(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with pytest.raises(Exception):
            write_run(repo_root / "reports", _manifest(), (_record(),), update_latest=False)
