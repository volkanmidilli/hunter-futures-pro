"""End-to-end CLI tests for `pairlist feather-input` / `pairlist from-feather` (SPEC-075)."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from hunter.pairlist_export import cli, publisher

from tests.test_pairlist_export._feather_fixtures import write_full_history_pair

AS_OF = "2026-07-21"

# The one real Freqtrade-produced 1h-futures Feather fixture available on
# this machine (freqtrade's own test data, single XRP/USDT:USDT pair,
# ~100 hourly rows from 2021-11-17 to 2021-11-21). Used for a genuine
# real-file acceptance smoke test in addition to synthetic fixtures.
_REAL_XRP_FIXTURE = Path(
    "/home/volkan/Apps/freqtrade strategy/freqtrade_src/tests/testdata/futures/"
    "XRP_USDT_USDT-1h-futures.feather"
)


def test_coins_rank_rejects_v2_schema_ranking_input(tmp_path: Path, capsys) -> None:
    """`coins rank`/`pairlist build` are v1-only; a v2-schema file must be a
    clear rejection, not a silent v1-shaped mis-rank (liquidity_scores ignored)."""
    payload = {
        "schema_version": "hunter-ranking-input-v2",
        "ranking_profile": "V2_RS_LIQUIDITY",
        "as_of_date": AS_OF,
        "universe_total": 1,
        "eligible_pairs": ["BTC/USDT:USDT"],
        "rs_scores": {"BTC/USDT:USDT": "80"},
        "liquidity_scores": {"BTC/USDT:USDT": "70"},
        "oi_scores": {},
        "data_quality": {"BTC/USDT:USDT": "100"},
    }
    input_path = tmp_path / "ranking_input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    output_path = tmp_path / "ranked.json"

    exit_code = cli.main(
        ["coins", "rank", "--as-of", AS_OF, "--input", str(input_path), "--output", str(output_path)]
    )

    assert exit_code == 1
    assert not output_path.exists()
    assert "schema_version" in capsys.readouterr().err


def test_feather_input_writes_ranking_input_v2(tmp_path: Path) -> None:
    write_full_history_pair(tmp_path, "BTC", date.fromisoformat(AS_OF))
    write_full_history_pair(tmp_path, "XRP", date.fromisoformat(AS_OF), close_step=0.001)
    output_path = tmp_path / "ranking-input.json"

    exit_code = cli.main(
        [
            "pairlist",
            "feather-input",
            "--data-dir",
            str(tmp_path),
            "--output",
            str(output_path),
            "--as-of",
            AS_OF,
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "hunter-ranking-input-v2"
    assert payload["ranking_profile"] == "V2_RS_LIQUIDITY"
    assert payload["eligible_pairs"] == ["XRP/USDT:USDT"]
    assert payload["oi_scores"] == {}
    assert payload["source_metadata"]["oi_available"] is False


def test_feather_input_is_byte_deterministic(tmp_path: Path) -> None:
    write_full_history_pair(tmp_path, "BTC", date.fromisoformat(AS_OF))
    write_full_history_pair(tmp_path, "XRP", date.fromisoformat(AS_OF), close_step=0.001)

    out1 = tmp_path / "one.json"
    out2 = tmp_path / "two.json"
    for out in (out1, out2):
        exit_code = cli.main(
            ["pairlist", "feather-input", "--data-dir", str(tmp_path), "--output", str(out), "--as-of", AS_OF]
        )
        assert exit_code == 0

    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")


def test_feather_input_fails_without_btc_benchmark(tmp_path: Path, capsys) -> None:
    write_full_history_pair(tmp_path, "XRP", date.fromisoformat(AS_OF))
    output_path = tmp_path / "ranking-input.json"

    exit_code = cli.main(
        ["pairlist", "feather-input", "--data-dir", str(tmp_path), "--output", str(output_path), "--as-of", AS_OF]
    )

    assert exit_code == 1
    assert not output_path.exists()
    assert "Error" in capsys.readouterr().err


def test_from_feather_single_pair_fails_below_min_pairs(tmp_path: Path, capsys) -> None:
    write_full_history_pair(tmp_path, "BTC", date.fromisoformat(AS_OF))
    write_full_history_pair(tmp_path, "XRP", date.fromisoformat(AS_OF), close_step=0.001)
    output_dir = tmp_path / "out"

    exit_code = cli.main(
        [
            "pairlist",
            "from-feather",
            "--data-dir",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--as-of",
            AS_OF,
        ]
    )

    assert exit_code == 1
    assert not (output_dir / publisher.PAIRLIST_FILENAME).exists()
    assert "BELOW_MIN_PAIRS" in capsys.readouterr().err


def test_from_feather_publishes_and_snapshots_with_enough_pairs(tmp_path: Path) -> None:
    as_of = date.fromisoformat(AS_OF)
    write_full_history_pair(tmp_path, "BTC", as_of)
    for i, base in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE"]):
        write_full_history_pair(tmp_path, base, as_of, close_step=0.001 * (i + 1))
    output_dir = tmp_path / "out"

    exit_code = cli.main(
        [
            "pairlist",
            "from-feather",
            "--data-dir",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--as-of",
            AS_OF,
        ]
    )

    assert exit_code == 0
    assert (output_dir / publisher.PAIRLIST_FILENAME).exists()
    assert (output_dir / publisher.AUDIT_FILENAME).exists()
    assert (output_dir / "hunter-pairs-20260721.json").exists()
    assert (output_dir / "hunter-pairs-20260721-audit.json").exists()

    audit_payload = json.loads((output_dir / publisher.AUDIT_FILENAME).read_text(encoding="utf-8"))
    assert audit_payload["schema_version"] == "hunter-ranking-input-v2"
    assert audit_payload["ranking_profile"] == "V2_RS_LIQUIDITY"
    assert audit_payload["oi_available"] is False
    assert audit_payload["universe_fingerprint"]


# ---------------------------------------------------------------------------
# Real-server acceptance: genuine Freqtrade-produced 1h-futures Feather file.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _REAL_XRP_FIXTURE.exists(), reason="real external Feather fixture not present on this machine")
def test_real_freqtrade_fixture_discovered_and_source_hash_unchanged(tmp_path: Path) -> None:
    """Copy the one real 1h-futures Feather file available on this machine into a
    directory alongside a synthetic BTC benchmark, and confirm: (a) our discovery
    correctly identifies it by its real Freqtrade-produced filename/schema, (b) it
    flows through validation/windowing without error, and (c) the source bytes are
    never mutated. This is real production-shaped data (real freqtrade dtypes/tz),
    even though the BTC benchmark and the as-of date are synthetic (the real fixture's
    own history is from November 2021, far outside any realistic current as-of window).
    """
    real_copy = tmp_path / _REAL_XRP_FIXTURE.name
    shutil.copyfile(_REAL_XRP_FIXTURE, real_copy)
    before_hash = hashlib.sha256(real_copy.read_bytes()).hexdigest()
    assert before_hash == hashlib.sha256(_REAL_XRP_FIXTURE.read_bytes()).hexdigest()

    # Use the real fixture's own as-of window so its 2021 rows actually land in-window.
    real_as_of = "2021-11-21"
    write_full_history_pair(tmp_path, "BTC", date.fromisoformat(real_as_of))

    output_path = tmp_path / "ranking-input.json"
    exit_code = cli.main(
        [
            "pairlist",
            "feather-input",
            "--data-dir",
            str(tmp_path),
            "--output",
            str(output_path),
            "--as-of",
            real_as_of,
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    # ~4 days of real history is below RS's default min_required_rows=30 (daily
    # rows), so XRP is windowed and counted but correctly not RS-eligible --
    # that is the honest, non-crashing acceptance outcome for this fixture.
    assert payload["universe_total"] == 1
    assert payload["eligible_pairs"] == []
    assert payload["rs_scores"] == {}

    after_hash = hashlib.sha256(real_copy.read_bytes()).hexdigest()
    assert before_hash == after_hash
