"""CLI smoke and dispatch tests for SPEC-077."""

from __future__ import annotations

import json

from hunter.core import cli as core_cli
from hunter.core.doctor.cli import doctor_main, update_main
from hunter.core.doctor.update import UpdateStatus


def test_core_cli_routes_doctor_and_update(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        core_cli, "doctor_main", lambda argv: calls.append(("doctor", argv)) or 0
    )
    monkeypatch.setattr(
        core_cli, "update_main", lambda argv: calls.append(("update", argv)) or 0
    )
    assert core_cli.main(["doctor", "--verbose"]) == 0
    assert core_cli.main(["update", "check", "--offline"]) == 0
    assert calls == [
        ("doctor", ["--verbose"]),
        ("update", ["check", "--offline"]),
    ]


def test_unified_help_lists_doctor_and_update(capsys) -> None:
    assert core_cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "doctor" in out
    assert "update check" in out
    assert "update plan" in out


def test_doctor_smoke_json(capsys) -> None:
    exit_code = doctor_main(["--json"])
    assert exit_code in (0, 1, 2)
    payload = json.loads(capsys.readouterr().out)
    assert payload["research_only"] is True
    assert payload["human_approval_required"] is True
    assert payload["exit_code"] == exit_code
    statuses = {result["status"] for result in payload["results"]}
    assert statuses <= {"PASS", "WARNING", "BLOCKER", "SKIPPED"}
    categories = {result["category"] for result in payload["results"]}
    assert categories == {
        "Venv",
        "Editable install",
        "Package versions",
        "Git",
        "Snapshot",
        "Feather",
        "Outcome Store",
        "Safety",
        "Configuration",
    }
    config_keys = set(payload["config"].keys())
    assert config_keys == {"snapshot_dir", "data_dir", "store_dir", "pairlist_output_dir"}
    for entry in payload["config"].values():
        assert entry["source"] in {
            "DEFAULT",
            "PROJECT_CONFIG",
            "USER_CONFIG",
            "ENVIRONMENT",
            "CLI",
        }


def test_doctor_verbose_shows_provenance(capsys) -> None:
    doctor_main(["--verbose"])
    out = capsys.readouterr().out
    assert "Resolved configuration:" in out
    assert "snapshot_dir" in out
    assert "source:" in out


def test_doctor_cli_flags_override_and_show_provenance(capsys, tmp_path) -> None:
    doctor_main(["--verbose", "--snapshot-dir", str(tmp_path / "custom_snap")])
    out = capsys.readouterr().out
    assert str(tmp_path / "custom_snap") in out
    assert "CLI" in out


def test_update_check_offline_smoke(capsys) -> None:
    assert update_main(["check", "--offline"]) == 0
    out = capsys.readouterr().out
    assert "current version:" in out
    assert "tag source:       local" in out


def test_update_check_offline_json(capsys) -> None:
    assert update_main(["check", "--offline", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] == "local"
    assert payload["status"] in {status.value for status in UpdateStatus}
    assert payload["research_only"] is True


def test_update_plan_offline_smoke(capsys) -> None:
    exit_code = update_main(["plan", "--offline"])
    assert exit_code in (0, 2)  # 2 only if no valid release tags exist locally.
    out = capsys.readouterr().out
    if exit_code == 0:
        assert "Hunter Update Plan" in out
        assert "non-executing" in out
        assert "rollback tag:" in out


def test_update_plan_rejects_unknown_target(capsys) -> None:
    exit_code = update_main(["plan", "--offline", "--target", "99.99.99"])
    assert exit_code == 2
    assert "not found" in capsys.readouterr().err


def test_update_plan_rejects_invalid_target(capsys) -> None:
    exit_code = update_main(["plan", "--offline", "--target", "bogus"])
    assert exit_code == 2
    assert "not a valid SemVer" in capsys.readouterr().err
