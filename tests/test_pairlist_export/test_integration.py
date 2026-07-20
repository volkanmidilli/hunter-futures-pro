"""End-to-end SPEC-074 pairlist-export pipeline test.

Exercises rank -> gate -> publish -> snapshot -> validate -> explain through
the public CLI entry point, plus the "reject before ever touching the live
files" guarantee on a subsequent bad build.
"""

from __future__ import annotations

import json
from pathlib import Path

from hunter.pairlist_export import cli, publisher


def _write_ranking_input(path: Path, pairs, rs_start=90) -> None:
    payload = {
        "as_of_date": "2026-07-21",
        "universe_total": 200,
        "eligible_pairs": list(pairs),
        "rs_scores": {p: str(rs_start - i) for i, p in enumerate(pairs)},
        "oi_scores": {p: str(60 - i) for i, p in enumerate(pairs)},
        "data_quality": {p: "100" for p in pairs},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_full_pipeline_build_then_validate_then_explain(tmp_path: Path, capsys) -> None:
    good_pairs = [f"COIN{i}/USDT:USDT" for i in range(8)]
    input_path = tmp_path / "ranking_input.json"
    _write_ranking_input(input_path, good_pairs)
    output_dir = tmp_path / "deploy"

    build_exit = cli.main(
        [
            "pairlist",
            "build",
            "--as-of",
            "2026-07-21",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert build_exit == 0
    capsys.readouterr()

    pairlist_path = output_dir / publisher.PAIRLIST_FILENAME
    audit_path = output_dir / publisher.AUDIT_FILENAME
    original_pairlist_text = pairlist_path.read_text(encoding="utf-8")
    original_audit_text = audit_path.read_text(encoding="utf-8")

    validate_exit = cli.main(["pairlist", "validate", str(pairlist_path)])
    assert validate_exit == 0
    assert "valid: True" in capsys.readouterr().out

    explain_exit = cli.main(["pairlist", "explain", str(audit_path)])
    assert explain_exit == 0
    explain_out = capsys.readouterr().out
    assert "Selected: 8" in explain_out
    assert "Rejected: 0" in explain_out

    # A subsequent bad build (too few pairs) must be rejected by the gate
    # before ever touching the live pairlist/audit files.
    bad_input_path = tmp_path / "bad_ranking_input.json"
    _write_ranking_input(bad_input_path, good_pairs[:1])

    bad_exit = cli.main(
        [
            "pairlist",
            "build",
            "--as-of",
            "2026-07-22",
            "--input",
            str(bad_input_path),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert bad_exit == 1
    assert pairlist_path.read_text(encoding="utf-8") == original_pairlist_text
    assert audit_path.read_text(encoding="utf-8") == original_audit_text

    # The prior day's static snapshot must also be untouched.
    snapshot_pairlist = output_dir / "hunter-pairs-20260721.json"
    assert json.loads(snapshot_pairlist.read_text(encoding="utf-8"))["pairs"] == good_pairs


def test_rerunning_same_day_build_with_identical_input_is_idempotent(
    tmp_path: Path, capsys
) -> None:
    pairs = [f"COIN{i}/USDT:USDT" for i in range(6)]
    input_path = tmp_path / "ranking_input.json"
    _write_ranking_input(input_path, pairs)
    output_dir = tmp_path / "deploy"

    args = [
        "pairlist",
        "build",
        "--as-of",
        "2026-07-21",
        "--input",
        str(input_path),
        "--output-dir",
        str(output_dir),
    ]
    assert cli.main(args) == 0
    capsys.readouterr()
    assert cli.main(args) == 0
    capsys.readouterr()
