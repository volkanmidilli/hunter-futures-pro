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


def test_empty_argv_routes_to_reporting_cli(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(cli, "pairlist_export_cli_main", lambda argv: calls.append(("pairlist_export", argv)) or 0)
    monkeypatch.setattr(cli, "reporting_cli_main", lambda argv: calls.append(("reporting", argv)) or 0)

    exit_code = cli.main([])

    assert exit_code == 0
    assert calls == [("reporting", [])]
