"""Pipeline-integration and regression tests (SPEC-078).

Proves the explainability integration records real pipeline decisions and
does not change ranking, selected pairs, published pairs, or existing
output artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

from hunter.core.cli import main as core_main
from hunter.pairlist_export.cli import main as pairlist_cli_main

_PAIRS = (
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "ADA/USDT:USDT",
    "XRP/USDT:USDT",
)


def _write_ranking_input(
    path: Path,
    pairs: tuple[str, ...] = _PAIRS,
    *,
    as_of: str = "2026-07-27",
    eth_evidence: bool = True,
) -> None:
    payload = {
        "as_of_date": as_of,
        "universe_total": 100,
        "eligible_pairs": list(pairs),
        "rs_scores": {p: str(80 - i) for i, p in enumerate(pairs)},
        "oi_scores": {p: "50" for p in pairs},
        "data_quality": {p: "100" for p in pairs},
    }
    if not eth_evidence:
        payload["rs_scores"]["ETH/USDT:USDT"] = None
        payload["oi_scores"]["ETH/USDT:USDT"] = None
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build(tmp_path: Path, *, as_of: str = "2026-07-27", eth_evidence: bool = True) -> int:
    _write_ranking_input(tmp_path / "ranking_input.json", as_of=as_of, eth_evidence=eth_evidence)
    return pairlist_cli_main(
        [
            "pairlist",
            "build",
            "--as-of",
            as_of,
            "--input",
            str(tmp_path / "ranking_input.json"),
            "--output-dir",
            str(tmp_path / "out"),
            "--explainability-dir",
            str(tmp_path / "expl"),
        ]
    )


class TestRecordingIntegration:
    def test_successful_build_records_run_and_latest(self, tmp_path: Path) -> None:
        assert _build(tmp_path) == 0
        latest = json.loads((tmp_path / "expl" / "latest.json").read_text(encoding="utf-8"))
        run_id = latest["run_id"]
        run_dir = tmp_path / "expl" / "runs" / run_id
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["published"] is True
        assert manifest["gate_allowed"] is True
        assert manifest["selected_count"] == 5
        for pair in _PAIRS:
            filename = pair.replace("/", "_").replace(":", "_") + ".json"
            assert (run_dir / "candidates" / filename).is_file()

    def test_explain_reads_what_pipeline_decided(self, tmp_path: Path, capsys) -> None:
        assert _build(tmp_path) == 0
        capsys.readouterr()
        # BTC is rank 1 with default scores: selected and published.
        rc = core_main(["explain", "BTC", "--explainability-dir", str(tmp_path / "expl")])
        assert rc == 0
        out = capsys.readouterr().out
        assert "SELECTED            YES" in out
        assert "PUBLISHED           YES" in out
        # XRP is rank 5 of 5 eligible, inside the default target of 20.
        rc = core_main(["explain", "XRP", "--explainability-dir", str(tmp_path / "expl")])
        assert rc == 0
        assert "FINAL RANK          5 / 5" in capsys.readouterr().out

    def test_explain_outside_cutoff_candidate(self, tmp_path: Path, capsys) -> None:
        many = tuple(f"C{i:02d}/USDT:USDT" for i in range(1, 25)) + _PAIRS
        _write_ranking_input(tmp_path / "ranking_input.json", pairs=many)
        rc = pairlist_cli_main(
            [
                "pairlist", "build",
                "--as-of", "2026-07-27",
                "--input", str(tmp_path / "ranking_input.json"),
                "--output-dir", str(tmp_path / "out"),
                "--explainability-dir", str(tmp_path / "expl"),
            ]
        )
        assert rc == 0
        capsys.readouterr()
        # 29 eligible, target 20: the last-ranked pairs are outside the cutoff.
        rc = core_main(["explain", "XRP", "--explainability-dir", str(tmp_path / "expl")])
        assert rc == 0
        out = capsys.readouterr().out
        assert "SELECTED            NO" in out
        assert "OUTSIDE_TARGET_FINAL_PAIRS" in out
        assert "FINAL RANK          29 / 29" in out

    def test_explain_candidate_excluded_before_ranking(self, tmp_path: Path, capsys) -> None:
        # Six pairs so that ETH's exclusion still leaves min_pairs=5 selected.
        _write_ranking_input(
            tmp_path / "ranking_input.json",
            pairs=_PAIRS + ("DOGE/USDT:USDT",),
            eth_evidence=False,
        )
        rc = pairlist_cli_main(
            [
                "pairlist", "build",
                "--as-of", "2026-07-27",
                "--input", str(tmp_path / "ranking_input.json"),
                "--output-dir", str(tmp_path / "out"),
                "--explainability-dir", str(tmp_path / "expl"),
            ]
        )
        assert rc == 0
        capsys.readouterr()
        rc = core_main(["explain", "ETH", "--explainability-dir", str(tmp_path / "expl")])
        assert rc == 0
        out = capsys.readouterr().out
        assert "SELECTED            NO" in out
        assert "INSUFFICIENT_EVIDENCE" in out

    def test_explain_json_matches_human_source(self, tmp_path: Path, capsys) -> None:
        assert _build(tmp_path) == 0
        capsys.readouterr()
        rc = core_main(["explain", "BTC", "--json", "--explainability-dir", str(tmp_path / "expl")])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "OK"
        record = payload["record"]
        assert record["pair"] == "BTC/USDT:USDT"
        assert record["selected"] is True
        assert record["published"] is True
        assert [s["stage_id"] for s in record["stages"]] == [
            "universe",
            "data_quality",
            "liquidity",
            "relative_strength",
            "ranking",
            "publish",
        ]


class TestGateRejectedRun:
    def test_failed_run_does_not_replace_latest(self, tmp_path: Path, capsys) -> None:
        # First: a successful run establishes the latest pointer.
        assert _build(tmp_path) == 0
        latest_before = json.loads((tmp_path / "expl" / "latest.json").read_text(encoding="utf-8"))
        capsys.readouterr()

        # Second: a gate-rejected run (single pair < min_pairs=5) on a new date.
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        _write_ranking_input(bad_dir / "ranking_input.json", pairs=("BTC/USDT:USDT",), as_of="2026-07-28")
        rc = pairlist_cli_main(
            [
                "pairlist", "build",
                "--as-of", "2026-07-28",
                "--input", str(bad_dir / "ranking_input.json"),
                "--output-dir", str(bad_dir / "out"),
                "--explainability-dir", str(tmp_path / "expl"),
            ]
        )
        assert rc == 1  # gate rejected (BELOW_MIN_PAIRS)
        latest_after = json.loads((tmp_path / "expl" / "latest.json").read_text(encoding="utf-8"))
        assert latest_after == latest_before

        # The rejected run's artifacts still exist for forensics, and the
        # explain command keeps answering from the latest *successful* run.
        rc = core_main(["explain", "BTC", "--explainability-dir", str(tmp_path / "expl")])
        assert rc == 0
        out = capsys.readouterr().out
        assert latest_before["run_id"] in out
        assert "SELECTED            YES" in out

    def test_first_run_gate_rejected_leaves_no_latest(self, tmp_path: Path, capsys) -> None:
        _write_ranking_input(tmp_path / "ranking_input.json", pairs=("BTC/USDT:USDT",))
        rc = pairlist_cli_main(
            [
                "pairlist", "build",
                "--as-of", "2026-07-27",
                "--input", str(tmp_path / "ranking_input.json"),
                "--output-dir", str(tmp_path / "out"),
                "--explainability-dir", str(tmp_path / "expl"),
            ]
        )
        assert rc == 1
        assert not (tmp_path / "expl" / "latest.json").exists()
        capsys.readouterr()
        rc = core_main(["explain", "BTC", "--explainability-dir", str(tmp_path / "expl")])
        assert rc == 1
        assert "NO_SUCCESSFUL_RUN" in capsys.readouterr().err


class TestSharedRunId:
    def test_all_run_artifacts_share_one_run_id(self, tmp_path: Path) -> None:
        """hunter-pairs.json, audit, snapshots, and explainability artifacts
        of one run must all carry the same run_id."""
        assert _build(tmp_path) == 0

        pairlist = json.loads((tmp_path / "out" / "hunter-pairs.json").read_text(encoding="utf-8"))
        audit = json.loads((tmp_path / "out" / "hunter-pairs-audit.json").read_text(encoding="utf-8"))
        snap_pairlist = json.loads(
            (tmp_path / "out" / "hunter-pairs-20260727.json").read_text(encoding="utf-8")
        )
        snap_audit = json.loads(
            (tmp_path / "out" / "hunter-pairs-20260727-audit.json").read_text(encoding="utf-8")
        )
        latest = json.loads((tmp_path / "expl" / "latest.json").read_text(encoding="utf-8"))
        run_dir = tmp_path / "expl" / "runs" / latest["run_id"]
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        candidate = json.loads(
            (run_dir / "candidates" / "BTC_USDT_USDT.json").read_text(encoding="utf-8")
        )

        run_id = pairlist["run_id"]
        assert run_id  # non-empty
        assert audit["run_id"] == run_id
        assert snap_pairlist["run_id"] == run_id
        assert snap_audit["run_id"] == run_id
        assert manifest["run_id"] == run_id
        assert candidate["run_id"] == run_id
        assert latest["run_id"] == run_id
        # Derived from the audit fingerprint the pipeline itself computed.
        assert run_id == f"2026-07-27__V1_RS_OI__{audit['fingerprint'][:12]}"
        assert manifest["provenance_type"] == "ORIGINAL"
        assert candidate["provenance_type"] == "ORIGINAL"

    def test_run_id_is_deterministic_across_identical_reruns(self, tmp_path: Path) -> None:
        assert _build(tmp_path) == 0
        first = json.loads((tmp_path / "out" / "hunter-pairs.json").read_text(encoding="utf-8"))[
            "run_id"
        ]
        rerun = tmp_path / "rerun"
        rerun.mkdir()
        _write_ranking_input(rerun / "ranking_input.json")
        rc = pairlist_cli_main(
            [
                "pairlist", "build",
                "--as-of", "2026-07-27",
                "--input", str(rerun / "ranking_input.json"),
                "--output-dir", str(rerun / "out"),
                "--explainability-dir", str(rerun / "expl"),
            ]
        )
        assert rc == 0
        second = json.loads((rerun / "out" / "hunter-pairs.json").read_text(encoding="utf-8"))[
            "run_id"
        ]
        assert first == second

    def test_original_run_supersedes_legacy_import_pointer(self, tmp_path: Path) -> None:
        """A fresh ORIGINAL run replaces a RECONSTRUCTED latest pointer."""
        from hunter.explainability.legacy import import_legacy_run

        # Seed a legacy import (older production publish).
        src = tmp_path / "legacy"
        src.mkdir()
        (src / "hunter-pairs.json").write_text(json.dumps({"pairs": ["SOL/USDT:USDT"], "refresh_period": 3600}))
        (src / "hunter-pairs-audit.json").write_text(json.dumps({
            "as_of_date": "2026-07-21",
            "universe_total": 300,
            "eligible_count": 1,
            "selected_count": 1,
            "rejected_count": 0,
            "selected": [{
                "pair": "SOL/USDT:USDT", "rank": 1, "selected": True,
                "rs_score": "80", "oi_score": "50",
                "reason_codes": ["RS_SCORE", "OI_LIQUIDITY"], "fingerprint": "fp",
            }],
            "rejected": [],
            "reason_code_summary": {},
            "fingerprint": "c" * 64,
        }))
        result = import_legacy_run(
            tmp_path / "expl",
            pairlist_path=src / "hunter-pairs.json",
            audit_path=src / "hunter-pairs-audit.json",
        )
        assert result.pointer_advanced is True

        # A fresh instrumented run must take the pointer over as ORIGINAL.
        assert _build(tmp_path) == 0
        latest = json.loads((tmp_path / "expl" / "latest.json").read_text(encoding="utf-8"))
        assert latest["provenance_type"] == "ORIGINAL"
        assert latest["as_of_date"] == "2026-07-27"

    def test_explain_immediately_after_successful_run(self, tmp_path: Path, capsys) -> None:
        """No import step: explain works right after daily-pairlist."""
        assert _build(tmp_path) == 0
        capsys.readouterr()
        rc = core_main(["explain", "BTC", "--explainability-dir", str(tmp_path / "expl")])
        assert rc == 0
        out = capsys.readouterr().out
        assert "PROVENANCE          ORIGINAL" in out
        assert "SELECTED            YES" in out


class TestNoBehaviorChangeRegression:
    def test_published_outputs_identical_with_and_without_recording(self, tmp_path: Path) -> None:
        """Explainability recording must not change any existing artifact."""
        _write_ranking_input(tmp_path / "ranking_input.json")

        rc = pairlist_cli_main(
            [
                "pairlist", "build",
                "--as-of", "2026-07-27",
                "--input", str(tmp_path / "ranking_input.json"),
                "--output-dir", str(tmp_path / "out_plain"),
            ]
        )
        assert rc == 0
        rc = pairlist_cli_main(
            [
                "pairlist", "build",
                "--as-of", "2026-07-27",
                "--input", str(tmp_path / "ranking_input.json"),
                "--output-dir", str(tmp_path / "out_recorded"),
                "--explainability-dir", str(tmp_path / "expl"),
            ]
        )
        assert rc == 0

        for name in (
            "hunter-pairs.json",
            "hunter-pairs-audit.json",
            "hunter-pairs-20260727.json",
            "hunter-pairs-20260727-audit.json",
        ):
            plain = (tmp_path / "out_plain" / name).read_text(encoding="utf-8")
            recorded = (tmp_path / "out_recorded" / name).read_text(encoding="utf-8")
            assert plain == recorded, f"{name} differs with explainability enabled"

        # Both carry the same shared run_id derived from run content.
        plain_pairlist = json.loads(
            (tmp_path / "out_plain" / "hunter-pairs.json").read_text(encoding="utf-8")
        )
        recorded_pairlist = json.loads(
            (tmp_path / "out_recorded" / "hunter-pairs.json").read_text(encoding="utf-8")
        )
        assert plain_pairlist["run_id"] == recorded_pairlist["run_id"]

    def test_pipeline_determinism_with_recording(self, tmp_path: Path) -> None:
        """Two identical recorded runs yield identical pairlists and run ids."""
        assert _build(tmp_path) == 0
        first_pairlist = (tmp_path / "out" / "hunter-pairs.json").read_text(encoding="utf-8")
        first_latest = json.loads((tmp_path / "expl" / "latest.json").read_text(encoding="utf-8"))

        rerun = tmp_path / "rerun"
        rerun.mkdir()
        _write_ranking_input(rerun / "ranking_input.json")
        rc = pairlist_cli_main(
            [
                "pairlist", "build",
                "--as-of", "2026-07-27",
                "--input", str(rerun / "ranking_input.json"),
                "--output-dir", str(rerun / "out"),
                "--explainability-dir", str(rerun / "expl"),
            ]
        )
        assert rc == 0
        second_pairlist = (rerun / "out" / "hunter-pairs.json").read_text(encoding="utf-8")
        second_latest = json.loads((rerun / "expl" / "latest.json").read_text(encoding="utf-8"))

        assert first_pairlist == second_pairlist
        assert first_latest["run_id"] == second_latest["run_id"]

    def test_selected_pairs_match_published_pairlist(self, tmp_path: Path) -> None:
        """Recorded selected set must equal the actually published pairs."""
        assert _build(tmp_path) == 0
        published = json.loads((tmp_path / "out" / "hunter-pairs.json").read_text(encoding="utf-8"))
        latest = json.loads((tmp_path / "expl" / "latest.json").read_text(encoding="utf-8"))
        candidates_dir = tmp_path / "expl" / "runs" / latest["run_id"] / "candidates"
        ranked_records = []
        for path in sorted(candidates_dir.glob("*.json")):
            ranked_records.append(json.loads(path.read_text(encoding="utf-8")))
        selected = [
            record["pair"]
            for record in sorted(ranked_records, key=lambda r: r["final_rank"])
            if record["selected"]
        ]
        assert selected == published["pairs"]

    def test_recording_failure_does_not_change_exit_code(
        self, tmp_path: Path, capsys, monkeypatch
    ) -> None:
        """A broken explainability store must never break the pipeline."""
        _write_ranking_input(tmp_path / "ranking_input.json")

        def _boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("hunter.pairlist_export.cli.write_run", _boom)
        rc = pairlist_cli_main(
            [
                "pairlist", "build",
                "--as-of", "2026-07-27",
                "--input", str(tmp_path / "ranking_input.json"),
                "--output-dir", str(tmp_path / "out"),
                "--explainability-dir", str(tmp_path / "expl"),
            ]
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "explainability recording failed" in err
        # The real outputs were still published.
        assert (tmp_path / "out" / "hunter-pairs.json").is_file()
