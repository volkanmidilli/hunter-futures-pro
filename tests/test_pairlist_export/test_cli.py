"""Focused tests for hunter.pairlist_export.cli (SPEC-074)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hunter.pairlist_export import cli, publisher


_DEFAULT_PAIRS = (
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "ADA/USDT:USDT",
    "XRP/USDT:USDT",
)


def _write_ranking_input(path: Path, pairs=_DEFAULT_PAIRS) -> None:
    payload = {
        "as_of_date": "2026-07-21",
        "universe_total": 100,
        "eligible_pairs": list(pairs),
        "rs_scores": {p: str(80 - i) for i, p in enumerate(pairs)},
        "oi_scores": {p: "50" for p in pairs},
        "data_quality": {p: "100" for p in pairs},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_universe_refresh_canonicalizes_and_dedupes(tmp_path: Path) -> None:
    input_path = tmp_path / "universe.json"
    input_path.write_text(
        json.dumps({"pairs": ["ETH/USDT:USDT", "BTC/USDT:USDT", "BTC/USDT:USDT"]}),
        encoding="utf-8",
    )
    output_path = tmp_path / "canonical.json"

    exit_code = cli.main(["universe", "refresh", "--input", str(input_path), "--output", str(output_path)])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["pairs"] == ["BTC/USDT:USDT", "ETH/USDT:USDT"]


def test_universe_refresh_rejects_invalid_pair_format(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "universe.json"
    input_path.write_text(json.dumps({"pairs": ["BTC-USDT"]}), encoding="utf-8")
    output_path = tmp_path / "canonical.json"

    exit_code = cli.main(["universe", "refresh", "--input", str(input_path), "--output", str(output_path)])

    assert exit_code == 2
    assert not output_path.exists()


def test_coins_rank_writes_ranked_pairs_json(tmp_path: Path) -> None:
    input_path = tmp_path / "ranking_input.json"
    _write_ranking_input(input_path)
    output_path = tmp_path / "ranked.json"

    exit_code = cli.main(
        ["coins", "rank", "--as-of", "2026-07-21", "--input", str(input_path), "--output", str(output_path)]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["as_of_date"] == "2026-07-21"
    assert [p["pair"] for p in payload["ranked"]] == list(_DEFAULT_PAIRS)


def test_pairlist_build_publishes_and_snapshots(tmp_path: Path) -> None:
    input_path = tmp_path / "ranking_input.json"
    _write_ranking_input(input_path)
    output_dir = tmp_path / "out"

    exit_code = cli.main(
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

    assert exit_code == 0
    assert (output_dir / publisher.PAIRLIST_FILENAME).exists()
    assert (output_dir / publisher.AUDIT_FILENAME).exists()
    assert (output_dir / "hunter-pairs-20260721.json").exists()
    assert (output_dir / "hunter-pairs-20260721-audit.json").exists()


def test_pairlist_build_rejects_when_below_min_pairs(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "ranking_input.json"
    # Only one pair with evidence, but the default config requires min_pairs=5.
    _write_ranking_input(input_path, pairs=("BTC/USDT:USDT",))
    output_dir = tmp_path / "out"

    exit_code = cli.main(
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

    assert exit_code == 1
    assert not (output_dir / publisher.PAIRLIST_FILENAME).exists()
    captured = capsys.readouterr()
    assert "BELOW_MIN_PAIRS" in captured.err


def test_pairlist_validate_reports_valid_and_invalid(tmp_path: Path, capsys) -> None:
    valid_path = tmp_path / "valid.json"
    valid_path.write_text(
        json.dumps({"pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "ADA/USDT:USDT", "XRP/USDT:USDT"], "refresh_period": 3600}),
        encoding="utf-8",
    )
    exit_code = cli.main(["pairlist", "validate", str(valid_path)])
    assert exit_code == 0
    assert "valid: True" in capsys.readouterr().out

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps({"pairs": [], "refresh_period": 3600}), encoding="utf-8")
    exit_code = cli.main(["pairlist", "validate", str(invalid_path)])
    assert exit_code == 1
    assert "valid: False" in capsys.readouterr().out


def test_pairlist_explain_renders_human_readable_text(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "ranking_input.json"
    _write_ranking_input(input_path)
    output_dir = tmp_path / "out"
    cli.main(
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
    capsys.readouterr()  # discard build output

    exit_code = cli.main(["pairlist", "explain", str(output_dir / publisher.AUDIT_FILENAME)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Pairlist audit" in out
    assert "Selected: 5" in out


def test_coins_rank_rejects_non_numeric_score_cleanly(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "ranking_input.json"
    payload = {
        "as_of_date": "2026-07-21",
        "universe_total": 100,
        "eligible_pairs": ["BTC/USDT:USDT"],
        "rs_scores": {"BTC/USDT:USDT": True},
        "oi_scores": {"BTC/USDT:USDT": "50"},
    }
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    output_path = tmp_path / "ranked.json"

    exit_code = cli.main(
        ["coins", "rank", "--as-of", "2026-07-21", "--input", str(input_path), "--output", str(output_path)]
    )

    assert exit_code == 1
    assert "Error" in capsys.readouterr().err
    assert not output_path.exists()


def test_pairlist_build_preserves_explicit_zero_universe_total(tmp_path: Path) -> None:
    input_path = tmp_path / "ranking_input.json"
    payload = {
        "as_of_date": "2026-07-21",
        "universe_total": 0,
        "eligible_pairs": list(_DEFAULT_PAIRS),
        "rs_scores": {p: str(80 - i) for i, p in enumerate(_DEFAULT_PAIRS)},
        "oi_scores": {p: "50" for p in _DEFAULT_PAIRS},
    }
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    output_dir = tmp_path / "out"

    exit_code = cli.main(
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

    assert exit_code == 0
    audit_payload = json.loads((output_dir / publisher.AUDIT_FILENAME).read_text(encoding="utf-8"))
    assert audit_payload["universe_total"] == 0


def test_deployment_profile_prints_to_stdout(capsys) -> None:
    exit_code = cli.main(["pairlist", "deployment-profile", "--target", "container"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["pairlists"][0]["pairlist_url"].startswith("file:///freqtrade")


def test_output_dir_targeting_repo_data_tree_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    fake_data = tmp_path / "data"
    monkeypatch.setattr(publisher, "_FORBIDDEN_DIRS", (fake_data, tmp_path / "reports"))

    input_path = tmp_path / "ranking_input.json"
    _write_ranking_input(input_path)

    exit_code = cli.main(
        [
            "pairlist",
            "build",
            "--as-of",
            "2026-07-21",
            "--input",
            str(input_path),
            "--output-dir",
            str(fake_data),
        ]
    )

    assert exit_code == 1
    assert not fake_data.exists()
    assert "Error" in capsys.readouterr().err
