"""CLI tests for ``hunter explain`` (SPEC-078)."""

from __future__ import annotations

import json
from pathlib import Path

from hunter.explainability.cli import explain_cli_main
from hunter.explainability.models import (
    EXPLAINABILITY_SCHEMA_VERSION,
    CandidateExplanationRecord,
    ExplainabilityRunManifest,
)
from hunter.explainability.storage import write_run


def _seed(tmp_path: Path, pair: str = "BTC/USDT:USDT") -> None:
    manifest = ExplainabilityRunManifest(
        schema_version=EXPLAINABILITY_SCHEMA_VERSION,
        run_id="run-1",
        completed_at="2026-07-27T00:00:00+00:00",
        as_of_date="2026-07-27",
        ranking_profile="V1_RS_OI",
        universe_total=412,
        eligible_count=1,
        selected_count=1,
        target_final_pairs=20,
        min_pairs=5,
        max_pairs=50,
        gate_allowed=True,
        published=True,
        eligible_pairs=(pair,),
    )
    record = CandidateExplanationRecord(
        schema_version=EXPLAINABILITY_SCHEMA_VERSION,
        run_id="run-1",
        completed_at="2026-07-27T00:00:00+00:00",
        pair=pair,
        final_rank=1,
        selected=True,
        published=True,
        final_reason_codes=("OK",),
    )
    write_run(tmp_path, manifest, (record,), update_latest=True)


class TestHumanOutput:
    def test_short_symbol(self, tmp_path: Path, capsys) -> None:
        _seed(tmp_path)
        rc = explain_cli_main(["BTC", "--explainability-dir", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "BTC/USDT:USDT" in out
        assert "SELECTED            YES" in out

    def test_full_pair_symbol(self, tmp_path: Path, capsys) -> None:
        _seed(tmp_path)
        rc = explain_cli_main(["BTC/USDT:USDT", "--explainability-dir", str(tmp_path)])
        assert rc == 0
        assert "BTC/USDT:USDT" in capsys.readouterr().out

    def test_not_in_universe_is_success_with_reason(self, tmp_path: Path, capsys) -> None:
        _seed(tmp_path)
        rc = explain_cli_main(["SOL", "--explainability-dir", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "SOL/USDT:USDT" in out
        assert "NOT_IN_UNIVERSE" in out


class TestJsonOutput:
    def test_json_matches_human_lookup(self, tmp_path: Path, capsys) -> None:
        _seed(tmp_path)
        rc = explain_cli_main(["BTC", "--json", "--explainability-dir", str(tmp_path)])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "OK"
        assert payload["record"]["pair"] == "BTC/USDT:USDT"
        assert payload["record"]["selected"] is True
        assert payload["record"]["final_reason_codes"] == ["OK"]


class TestExitCodes:
    def test_no_successful_run_exits_1(self, tmp_path: Path, capsys) -> None:
        rc = explain_cli_main(["BTC", "--explainability-dir", str(tmp_path)])
        assert rc == 1
        assert "NO_SUCCESSFUL_RUN" in capsys.readouterr().err

    def test_invalid_symbol_exits_2(self, tmp_path: Path, capsys) -> None:
        rc = explain_cli_main(["../etc/passwd", "--explainability-dir", str(tmp_path)])
        assert rc == 2
        assert "Error" in capsys.readouterr().err

    def test_empty_symbol_exits_2(self, tmp_path: Path, capsys) -> None:
        rc = explain_cli_main(["  ", "--explainability-dir", str(tmp_path)])
        assert rc == 2

    def test_corrupt_artifact_exits_1(self, tmp_path: Path, capsys) -> None:
        _seed(tmp_path)
        (tmp_path / "latest.json").write_text("{corrupt", encoding="utf-8")
        rc = explain_cli_main(["BTC", "--explainability-dir", str(tmp_path)])
        assert rc == 1
        assert "ARTIFACT_INVALID" in capsys.readouterr().err

    def test_json_failure_still_emits_json(self, tmp_path: Path, capsys) -> None:
        rc = explain_cli_main(["BTC", "--json", "--explainability-dir", str(tmp_path)])
        assert rc == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "NO_SUCCESSFUL_RUN"
        assert payload["record"] is None


class TestCoreDispatch:
    def test_hunter_explain_routes_through_core_cli(self, tmp_path: Path, capsys) -> None:
        from hunter.core.cli import main

        _seed(tmp_path)
        rc = main(["explain", "BTC", "--explainability-dir", str(tmp_path)])
        assert rc == 0
        assert "BTC/USDT:USDT" in capsys.readouterr().out
