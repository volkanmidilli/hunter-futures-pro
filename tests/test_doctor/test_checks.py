"""Tests for the nine SPEC-077 doctor check categories."""

from __future__ import annotations

import importlib.metadata
import json
import sys
from pathlib import Path

from hunter.core.doctor.checks.configuration import check_configuration
from hunter.core.doctor.checks.editable import check_editable_install
from hunter.core.doctor.checks.feather import check_feather_inputs
from hunter.core.doctor.checks.git_checks import check_git_repository
from hunter.core.doctor.checks.outcome_store import check_outcome_store_dir
from hunter.core.doctor.checks.packages import check_package_versions
from hunter.core.doctor.checks.safety import check_safety
from hunter.core.doctor.checks.snapshot import check_snapshot_dir
from hunter.core.doctor.checks.venv import check_venv
from hunter.core.doctor.config import ConfigKey
from hunter.core.doctor.gitutil import GitResult
from hunter.core.doctor.models import CheckCategory, CheckStatus

from .conftest import clean_worktree_responses, make_context, make_git


# --- Venv -----------------------------------------------------------------


def test_venv_status_matches_process_state(tmp_path: Path) -> None:
    result = check_venv(make_context(tmp_path))[0]
    expected = CheckStatus.PASS if sys.prefix != sys.base_prefix else CheckStatus.WARNING
    assert result.status is expected
    assert result.category is CheckCategory.VENV


# --- Editable install -----------------------------------------------------


class _FakeDist:
    def __init__(self, direct_url: str | None, files: list[str] | None = None):
        self._direct_url = direct_url
        self.files = files or []

    def read_text(self, name: str) -> str | None:
        assert name == "direct_url.json"
        return self._direct_url


def _patch_dist(monkeypatch, dist) -> None:
    monkeypatch.setattr(
        importlib.metadata, "distribution", lambda name: dist
    )


def test_editable_pass_with_direct_url(tmp_path: Path, monkeypatch) -> None:
    dist = _FakeDist(
        json.dumps({"url": f"file://{tmp_path}", "dir_info": {"editable": True}})
    )
    _patch_dist(monkeypatch, dist)
    result = check_editable_install(make_context(tmp_path))[0]
    assert result.status is CheckStatus.PASS


def test_editable_warning_when_editable_from_other_location(
    tmp_path: Path, monkeypatch
) -> None:
    dist = _FakeDist(
        json.dumps({"url": "file:///somewhere/else", "dir_info": {"editable": True}})
    )
    _patch_dist(monkeypatch, dist)
    result = check_editable_install(make_context(tmp_path))[0]
    assert result.status is CheckStatus.WARNING
    assert "different location" in result.summary


def test_editable_warning_when_not_editable(tmp_path: Path, monkeypatch) -> None:
    dist = _FakeDist('{"url": "file:///repo", "dir_info": {"editable": false}}')
    _patch_dist(monkeypatch, dist)
    result = check_editable_install(make_context(tmp_path))[0]
    assert result.status is CheckStatus.WARNING


def test_editable_skipped_when_not_installed(tmp_path: Path, monkeypatch) -> None:
    def _raise(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "distribution", _raise)
    result = check_editable_install(make_context(tmp_path))[0]
    assert result.status is CheckStatus.SKIPPED


def test_editable_pass_via_setuptools_finder(tmp_path: Path, monkeypatch) -> None:
    dist = _FakeDist(None, files=["__editable___hunter_futures_pro_finder.py"])
    _patch_dist(monkeypatch, dist)
    result = check_editable_install(make_context(tmp_path))[0]
    assert result.status is CheckStatus.PASS


# --- Package versions ------------------------------------------------------


def test_packages_pass_when_minimums_met(tmp_path: Path, monkeypatch) -> None:
    versions = {
        "pydantic": "2.5.0",
        "pyyaml": "6.0.1",
        "pandas": "2.1.0",
        "pyarrow": "14.0.1",
        "numpy": "1.26.0",
    }
    monkeypatch.setattr(importlib.metadata, "version", lambda name: versions[name])
    results = check_package_versions(make_context(tmp_path))
    assert len(results) == 5
    assert all(result.status is CheckStatus.PASS for result in results)
    assert all(result.category is CheckCategory.PACKAGES for result in results)


def test_packages_blocker_when_missing(tmp_path: Path, monkeypatch) -> None:
    def _raise(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", _raise)
    results = check_package_versions(make_context(tmp_path))
    assert all(result.status is CheckStatus.BLOCKER for result in results)


def test_packages_blocker_when_below_minimum(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "1.0.0")
    results = check_package_versions(make_context(tmp_path))
    assert all(result.status is CheckStatus.BLOCKER for result in results)


def test_packages_skipped_when_version_unparseable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "unknown")
    results = check_package_versions(make_context(tmp_path))
    assert all(result.status is CheckStatus.SKIPPED for result in results)


# --- Git -------------------------------------------------------------------


def test_git_pass_on_clean_branch(tmp_path: Path) -> None:
    context = make_context(tmp_path, git=make_git(clean_worktree_responses()))
    result = check_git_repository(context)[0]
    assert result.status is CheckStatus.PASS


def test_git_warning_on_dirty_worktree(tmp_path: Path) -> None:
    responses = clean_worktree_responses()
    responses[("status", "--porcelain")] = GitResult(ok=True, stdout=" M file.py\n")
    context = make_context(tmp_path, git=make_git(responses))
    result = check_git_repository(context)[0]
    assert result.status is CheckStatus.WARNING


def test_git_warning_on_detached_head(tmp_path: Path) -> None:
    responses = clean_worktree_responses()
    responses[("branch", "--show-current")] = GitResult(ok=True, stdout="")
    context = make_context(tmp_path, git=make_git(responses))
    result = check_git_repository(context)[0]
    assert result.status is CheckStatus.WARNING


def test_git_warning_outside_worktree(tmp_path: Path) -> None:
    responses = {
        ("rev-parse", "--is-inside-work-tree"): GitResult(
            ok=False, stderr="fatal: not a git repository", returncode=128
        )
    }
    context = make_context(tmp_path, git=make_git(responses))
    result = check_git_repository(context)[0]
    assert result.status is CheckStatus.WARNING
    assert "Not a Git work tree" in result.summary
    assert "Git clone" in result.summary
    assert "git clone" in (result.remediation or "")


def test_git_skipped_when_binary_missing(tmp_path: Path) -> None:
    responses = {
        ("rev-parse", "--is-inside-work-tree"): GitResult(
            ok=False, error="git binary not found"
        )
    }
    context = make_context(tmp_path, git=make_git(responses))
    result = check_git_repository(context)[0]
    assert result.status is CheckStatus.SKIPPED


# --- Snapshot / Outcome store ----------------------------------------------


def test_snapshot_dir_pass_and_warning(tmp_path: Path) -> None:
    snap = tmp_path / "data" / "snapshots"
    snap.mkdir(parents=True)
    result = check_snapshot_dir(make_context(tmp_path))[0]
    assert result.status is CheckStatus.PASS

    missing = check_snapshot_dir(make_context(tmp_path / "elsewhere"))[0]
    assert missing.status is CheckStatus.WARNING


def test_outcome_store_pass_and_warning(tmp_path: Path) -> None:
    store = tmp_path / "data" / "outcome_store"
    store.mkdir(parents=True)
    result = check_outcome_store_dir(make_context(tmp_path))[0]
    assert result.status is CheckStatus.PASS

    missing = check_outcome_store_dir(make_context(tmp_path / "elsewhere"))[0]
    assert missing.status is CheckStatus.WARNING


# --- Feather -----------------------------------------------------------------


def test_feather_pass_with_spec075_file(tmp_path: Path) -> None:
    data = tmp_path / "data" / "feather"
    data.mkdir(parents=True)
    (data / "BTC_USDT_USDT-1h-futures.feather").write_bytes(b"placeholder")
    result = check_feather_inputs(make_context(tmp_path))[0]
    assert result.status is CheckStatus.PASS
    assert "BTC_USDT_USDT-1h-futures.feather" in result.details


def test_feather_warning_on_empty_dir(tmp_path: Path) -> None:
    data = tmp_path / "data" / "feather"
    data.mkdir(parents=True)
    (data / "notes.txt").write_text("not a feather file")
    result = check_feather_inputs(make_context(tmp_path))[0]
    assert result.status is CheckStatus.WARNING


def test_feather_warning_on_missing_dir(tmp_path: Path) -> None:
    result = check_feather_inputs(make_context(tmp_path))[0]
    assert result.status is CheckStatus.WARNING


# --- Safety ------------------------------------------------------------------


def test_safety_pass_with_default_safe_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # No configs/ dir -> safe defaults.
    result = check_safety(make_context(tmp_path))[0]
    assert result.status is CheckStatus.PASS
    assert "research_only=True" in result.summary


def test_safety_blocker_when_trading_enabled(tmp_path: Path, monkeypatch) -> None:
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "data.yaml").write_text("trading:\n  enabled: true\n")
    monkeypatch.chdir(tmp_path)
    result = check_safety(make_context(tmp_path))[0]
    assert result.status is CheckStatus.BLOCKER


def test_safety_blocker_on_secret_keys(tmp_path: Path, monkeypatch) -> None:
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "data.yaml").write_text("api_key: supersecret\n")
    monkeypatch.chdir(tmp_path)
    result = check_safety(make_context(tmp_path))[0]
    assert result.status is CheckStatus.BLOCKER


def test_safety_anchors_to_project_root_not_cwd(tmp_path: Path, monkeypatch) -> None:
    """Safety config is read from context.project_root, not the process cwd."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "configs").mkdir()
    (project / "configs" / "data.yaml").write_text("trading:\n  enabled: false\n")

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / "configs").mkdir()
    (cwd / "configs" / "data.yaml").write_text("trading:\n  enabled: true\n")
    monkeypatch.chdir(cwd)

    result = check_safety(make_context(project))[0]
    assert result.status is CheckStatus.PASS


def test_safety_blocker_when_project_root_unsafe(tmp_path: Path, monkeypatch) -> None:
    """Unsafe config in project_root is detected even when cwd is safe."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "configs").mkdir()
    (project / "configs" / "data.yaml").write_text("trading:\n  enabled: true\n")

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    result = check_safety(make_context(project))[0]
    assert result.status is CheckStatus.BLOCKER


# --- Configuration ------------------------------------------------------------


def test_configuration_pass_when_clean(tmp_path: Path) -> None:
    environ = {"XDG_CONFIG_HOME": str(tmp_path / "no-xdg")}
    result = check_configuration(make_context(tmp_path, environ=environ))[0]
    assert result.status is CheckStatus.PASS


def test_configuration_warning_on_issues(tmp_path: Path) -> None:
    (tmp_path / "hunter.yaml").write_text("bogus_key: 1\n")
    result = check_configuration(make_context(tmp_path))[0]
    assert result.status is CheckStatus.WARNING
    assert any("unknown key" in detail for detail in result.details)


def test_configuration_warning_on_non_distinct_dirs(tmp_path: Path) -> None:
    (tmp_path / "hunter.yaml").write_text(
        "snapshot_dir: same\ndata_dir: same\nstore_dir: same\n"
    )
    result = check_configuration(make_context(tmp_path))[0]
    assert result.status is CheckStatus.WARNING
    assert any("pairwise distinct" in detail for detail in result.details)


def test_configuration_distinct_default_dirs_pass(tmp_path: Path) -> None:
    overrides = {
        ConfigKey.SNAPSHOT_DIR: "a",
        ConfigKey.DATA_DIR: "b",
        ConfigKey.STORE_DIR: "c",
    }
    result = check_configuration(make_context(tmp_path, cli_overrides=overrides))[0]
    assert result.status is CheckStatus.PASS
