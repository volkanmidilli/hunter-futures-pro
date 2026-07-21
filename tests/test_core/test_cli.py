"""Focused tests for the hunter.core.cli routing shim (SPEC-074)."""

from __future__ import annotations

from hunter.core import cli


def test_pairlist_export_groups_route_to_pairlist_export_cli(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(cli, "pairlist_export_cli_main", lambda argv: calls.append(("pairlist_export", argv)) or 0)
    monkeypatch.setattr(cli, "reporting_cli_main", lambda argv: calls.append(("reporting", argv)) or 0)

    for group in ("universe", "coins", "pairlist", "daily-pairlist"):
        calls.clear()
        exit_code = cli.main([group, "--help"])
        assert exit_code == 0
        assert calls == [("pairlist_export", [group, "--help"])]


def test_other_commands_still_route_to_reporting_cli(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(cli, "pairlist_export_cli_main", lambda argv: calls.append(("pairlist_export", argv)) or 0)
    monkeypatch.setattr(cli, "reporting_cli_main", lambda argv: calls.append(("reporting", argv)) or 0)

    exit_code = cli.main(["version"])

    assert exit_code == 0
    assert calls == [("reporting", ["version"])]


def test_empty_argv_prints_unified_help_and_does_not_dispatch(monkeypatch, capsys) -> None:
    """Bare `hunter` is a usage error (conventional: missing required
    subcommand) -- it prints the unified help to stderr and exits 2,
    without dispatching to either sub-CLI (Stage 3 remediation)."""
    calls = []
    monkeypatch.setattr(cli, "pairlist_export_cli_main", lambda argv: calls.append(("pairlist_export", argv)) or 0)
    monkeypatch.setattr(cli, "reporting_cli_main", lambda argv: calls.append(("reporting", argv)) or 0)

    exit_code = cli.main([])

    assert exit_code == 2
    assert calls == []
    err = capsys.readouterr().err
    assert "Error: No command provided." in err
    for command in ("universe", "coins", "pairlist", "daily-pairlist", "version", "safety-summary"):
        assert command in err


def test_help_flag_prints_unified_help_and_exits_zero(capsys) -> None:
    for flag in ("--help", "-h"):
        exit_code = cli.main([flag])
        assert exit_code == 0
        out = capsys.readouterr().out
        for command in (
            "version",
            "safety-summary",
            "list-artifacts",
            "validate-artifact-paths",
            "render-sample",
            "universe",
            "coins",
            "pairlist",
            "daily-pairlist",
        ):
            assert command in out


def test_help_flag_does_not_dispatch_to_either_sub_cli(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(cli, "pairlist_export_cli_main", lambda argv: calls.append(("pairlist_export", argv)) or 0)
    monkeypatch.setattr(cli, "reporting_cli_main", lambda argv: calls.append(("reporting", argv)) or 0)

    for flag in ("--help", "-h"):
        calls.clear()
        cli.main([flag])
        assert calls == []


def test_unknown_command_still_exits_two(capsys) -> None:
    exit_code = cli.main(["notacommand"])
    assert exit_code == 2
    assert "Unknown command: notacommand" in capsys.readouterr().err
