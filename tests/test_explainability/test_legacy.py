"""Legacy-import tests: provenance-labeled migration, no reranking (SPEC-078)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hunter.explainability.legacy import LegacyImportError, import_legacy_run
from hunter.explainability.models import (
    PROVENANCE_ORIGINAL,
    PROVENANCE_RECONSTRUCTED,
    REASON_LEGACY_RUN_INCOMPLETE,
    REASON_NOT_IN_UNIVERSE,
)
from hunter.explainability.service import LOOKUP_OK, explain_candidate
from hunter.explainability.storage import read_latest_pointer, read_manifest

_PAIRS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]


def _write_production_artifacts(
    directory: Path,
    *,
    pairs: list[str] | None = None,
    rejected: list[dict] | None = None,
    with_audit: bool = True,
) -> tuple[Path, Path | None]:
    pairs = pairs if pairs is not None else list(_PAIRS)
    pairlist_path = directory / "hunter-pairs.json"
    pairlist_path.write_text(
        json.dumps({"pairs": pairs, "refresh_period": 3600}), encoding="utf-8"
    )
    if not with_audit:
        return pairlist_path, None
    selected = [
        {
            "pair": p,
            "rank": i + 1,
            "selected": True,
            "rs_score": str(90 - i * 5),
            "oi_score": "50",
            "reason_codes": ["RS_SCORE", "OI_LIQUIDITY"],
            "fingerprint": f"fp-{i}",
        }
        for i, p in enumerate(pairs)
    ]
    audit = {
        "as_of_date": "2026-07-21",
        "universe_total": 312,
        "eligible_count": len(selected) + len(rejected or []),
        "selected_count": len(selected),
        "rejected_count": len(rejected or []),
        "selected": selected,
        "rejected": rejected or [],
        "reason_code_summary": {},
        "fingerprint": "a" * 64,
    }
    audit_path = directory / "hunter-pairs-audit.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    return pairlist_path, audit_path


class TestImportWithAudit:
    def test_import_builds_provenance_labeled_records(self, tmp_path: Path) -> None:
        src = tmp_path / "prod"
        src.mkdir()
        pairlist, audit = _write_production_artifacts(src)
        store = tmp_path / "expl"

        result = import_legacy_run(store, pairlist_path=pairlist, audit_path=audit)
        assert result.provenance_type == PROVENANCE_RECONSTRUCTED
        assert result.candidate_count == 3
        assert result.decision_records_complete is True
        assert result.pointer_advanced is True
        assert str(pairlist) in result.source_artifact_paths
        assert str(audit) in result.source_artifact_paths
        assert "data-quality values not recorded" in result.reconstruction_notes

        manifest = read_manifest(store, result.run_id)
        assert manifest.provenance_type == PROVENANCE_RECONSTRUCTED
        assert manifest.source_run_id == result.run_id
        assert manifest.as_of_date == "2026-07-21"
        assert manifest.universe_total == 312
        # The exact cutoff is not recorded in the legacy audit: UNKNOWN.
        assert manifest.target_final_pairs is None

    def test_explain_resolves_imported_run_from_audit_evidence(self, tmp_path: Path) -> None:
        src = tmp_path / "prod"
        src.mkdir()
        pairlist, audit = _write_production_artifacts(src)
        store = tmp_path / "expl"
        import_legacy_run(store, pairlist_path=pairlist, audit_path=audit)

        result = explain_candidate("BTC/USDT:USDT", store)
        assert result.status == LOOKUP_OK
        record = result.record
        assert record is not None
        assert record.provenance_type == PROVENANCE_RECONSTRUCTED
        assert record.selected is True
        assert record.published is True
        assert record.final_rank == 1
        assert record.score_components["rs_score"] == "90"
        stages = {s.stage_id: s for s in record.stages}
        assert stages["relative_strength"].metrics["rs_score"] == "90"
        assert stages["data_quality"].status == "UNKNOWN"  # never invented
        assert stages["publish"].status == "PASS"  # evidenced by the pairlist

    def test_pair_not_in_audit_universe_is_not_in_universe(self, tmp_path: Path) -> None:
        src = tmp_path / "prod"
        src.mkdir()
        pairlist, audit = _write_production_artifacts(src)
        store = tmp_path / "expl"
        import_legacy_run(store, pairlist_path=pairlist, audit_path=audit)

        result = explain_candidate("DOGE/USDT:USDT", store)
        assert result.status == REASON_NOT_IN_UNIVERSE
        assert result.manifest is not None
        assert result.manifest.provenance_type == PROVENANCE_RECONSTRUCTED

    def test_rejected_pair_explained_from_audit_codes(self, tmp_path: Path) -> None:
        src = tmp_path / "prod"
        src.mkdir()
        rejected = [
            {
                "pair": "DOGE/USDT:USDT",
                "rank": 4,
                "selected": False,
                "rs_score": None,
                "oi_score": None,
                "reason_codes": ["INSUFFICIENT_EVIDENCE"],
                "fingerprint": "fp-x",
            }
        ]
        pairlist, audit = _write_production_artifacts(src, rejected=rejected)
        store = tmp_path / "expl"
        import_legacy_run(store, pairlist_path=pairlist, audit_path=audit)

        result = explain_candidate("DOGE/USDT:USDT", store)
        assert result.status == LOOKUP_OK
        assert result.record is not None
        assert result.record.selected is False
        assert result.record.final_reason_codes == ("INSUFFICIENT_EVIDENCE",)


class TestImportWithoutAudit:
    def test_lookup_fails_closed_legacy_run_incomplete(self, tmp_path: Path) -> None:
        src = tmp_path / "prod"
        src.mkdir()
        pairlist, _ = _write_production_artifacts(src, with_audit=False)
        store = tmp_path / "expl"
        result = import_legacy_run(store, pairlist_path=pairlist)
        assert result.decision_records_complete is False
        assert result.pointer_advanced is True

        lookup = explain_candidate("BTC/USDT:USDT", store)
        assert lookup.status == REASON_LEGACY_RUN_INCOMPLETE
        assert lookup.record is None
        assert lookup.manifest is not None
        assert lookup.manifest.run_id == result.run_id


class TestImportConsistency:
    def test_audit_pairlist_mismatch_rejected(self, tmp_path: Path) -> None:
        src = tmp_path / "prod"
        src.mkdir()
        pairlist, audit = _write_production_artifacts(src)
        # Tamper: pairlist no longer matches the audit's selected set.
        pairlist.write_text(json.dumps({"pairs": ["BTC/USDT:USDT"], "refresh_period": 3600}))
        with pytest.raises(LegacyImportError):
            import_legacy_run(tmp_path / "expl", pairlist_path=pairlist, audit_path=audit)

    def test_missing_pairlist_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(LegacyImportError):
            import_legacy_run(tmp_path / "expl", pairlist_path=tmp_path / "nope.json")


class TestImportPointerDiscipline:
    def test_import_does_not_replace_original_latest(self, tmp_path: Path) -> None:
        from hunter.explainability.models import (
            EXPLAINABILITY_SCHEMA_VERSION,
            CandidateExplanationRecord,
            ExplainabilityRunManifest,
        )
        from hunter.explainability.storage import write_run

        store = tmp_path / "expl"
        manifest = ExplainabilityRunManifest(
            schema_version=EXPLAINABILITY_SCHEMA_VERSION,
            run_id="original-run",
            completed_at="2026-07-27T00:00:00+00:00",
            as_of_date="2026-07-27",
            ranking_profile="V1_RS_OI",
            universe_total=1,
            eligible_count=1,
            selected_count=1,
            target_final_pairs=20,
            min_pairs=5,
            max_pairs=50,
            gate_allowed=True,
            published=True,
            eligible_pairs=("BTC/USDT:USDT",),
            provenance_type=PROVENANCE_ORIGINAL,
        )
        record = CandidateExplanationRecord(
            schema_version=EXPLAINABILITY_SCHEMA_VERSION,
            run_id="original-run",
            completed_at="2026-07-27T00:00:00+00:00",
            pair="BTC/USDT:USDT",
            selected=True,
            published=True,
        )
        write_run(store, manifest, (record,), update_latest=True)

        src = tmp_path / "prod"
        src.mkdir()
        pairlist, audit = _write_production_artifacts(src)
        result = import_legacy_run(store, pairlist_path=pairlist, audit_path=audit)
        assert result.pointer_advanced is False
        pointer = read_latest_pointer(store)
        assert pointer["run_id"] == "original-run"

    def test_newer_production_publish_replaces_older_import(self, tmp_path: Path) -> None:
        store = tmp_path / "expl"
        src1 = tmp_path / "prod1"
        src1.mkdir()
        pairlist1, audit1 = _write_production_artifacts(src1)
        first = import_legacy_run(store, pairlist_path=pairlist1, audit_path=audit1)
        assert first.pointer_advanced is True

        # A newer production publish (2026-07-27) without BTC/ETH.
        src2 = tmp_path / "prod2"
        src2.mkdir()
        pairlist2, audit2 = _write_production_artifacts(
            src2, pairs=["SOL/USDT:USDT", "DOGE/USDT:USDT"]
        )
        payload = json.loads(audit2.read_text())
        payload["as_of_date"] = "2026-07-27"
        audit2.write_text(json.dumps(payload))
        second = import_legacy_run(store, pairlist_path=pairlist2, audit_path=audit2)
        assert second.pointer_advanced is True
        pointer = read_latest_pointer(store)
        assert pointer["run_id"] == second.run_id
        assert pointer["as_of_date"] == "2026-07-27"

        # BTC is now explainable against the newer publish: not in its universe.
        lookup = explain_candidate("BTC/USDT:USDT", store)
        assert lookup.status == REASON_NOT_IN_UNIVERSE

        # An older import must not displace the newer production publish.
        third = import_legacy_run(store, pairlist_path=pairlist1, audit_path=audit1)
        assert third.pointer_advanced is False
        assert read_latest_pointer(store)["run_id"] == second.run_id
