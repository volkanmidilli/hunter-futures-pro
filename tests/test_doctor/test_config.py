"""Tests for SPEC-077 shared configuration resolution."""

from __future__ import annotations

from pathlib import Path

from hunter.core.doctor.config import (
    ConfigKey,
    ConfigSource,
    find_project_root,
    resolve_config,
    user_config_path,
)


def test_defaults_resolve_under_project_root(tmp_path: Path) -> None:
    config = resolve_config(tmp_path, {}, None)
    assert config.snapshot_dir.value == (tmp_path / "data/snapshots").resolve()
    assert config.data_dir.value == (tmp_path / "data/feather").resolve()
    assert config.store_dir.value == (tmp_path / "data/outcome_store").resolve()
    assert config.pairlist_output_dir.value == (tmp_path / "data/pairlists").resolve()
    for resolved in config.all():
        assert resolved.source is ConfigSource.DEFAULT
    assert config.issues == ()


def test_full_precedence_chain(tmp_path: Path, monkeypatch) -> None:
    """defaults < project < user < environment < CLI (per key)."""
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    (tmp_path / "hunter.yaml").write_text(
        "snapshot_dir: project_snap\n"
        "data_dir: project_data\n"
        "store_dir: project_store\n"
        "pairlist_output_dir: project_pairs\n"
    )
    user_dir = xdg / "hunter"
    user_dir.mkdir(parents=True)
    (user_dir / "config.yaml").write_text(
        "snapshot_dir: user_snap\n"
        "data_dir: user_data\n"
        "store_dir: user_store\n"
    )
    environ = {
        "XDG_CONFIG_HOME": str(xdg),
        "HUNTER_SNAPSHOT_DIR": "env_snap",
        "HUNTER_DATA_DIR": "env_data",
    }
    cli = {ConfigKey.SNAPSHOT_DIR: "cli_snap"}

    config = resolve_config(tmp_path, environ, cli)

    assert config.snapshot_dir.value == (tmp_path / "cli_snap").resolve()
    assert config.snapshot_dir.source is ConfigSource.CLI
    assert config.data_dir.value == (tmp_path / "env_data").resolve()
    assert config.data_dir.source is ConfigSource.ENVIRONMENT
    assert config.store_dir.value == (tmp_path / "user_store").resolve()
    assert config.store_dir.source is ConfigSource.USER_CONFIG
    assert config.pairlist_output_dir.value == (tmp_path / "project_pairs").resolve()
    assert config.pairlist_output_dir.source is ConfigSource.PROJECT_CONFIG


def test_project_config_beats_default_and_user_beats_project(tmp_path: Path, monkeypatch) -> None:
    xdg = tmp_path / "xdg"
    user_dir = xdg / "hunter"
    user_dir.mkdir(parents=True)
    (tmp_path / "hunter.yaml").write_text("snapshot_dir: project_snap\n")
    (user_dir / "config.yaml").write_text("snapshot_dir: user_snap\n")
    environ = {"XDG_CONFIG_HOME": str(xdg)}

    project_only = resolve_config(tmp_path, environ, None)
    assert project_only.snapshot_dir.source is ConfigSource.USER_CONFIG
    assert project_only.snapshot_dir.value == (tmp_path / "user_snap").resolve()

    # Removing the user file falls back to the project layer.
    (user_dir / "config.yaml").unlink()
    project_layer = resolve_config(tmp_path, environ, None)
    assert project_layer.snapshot_dir.source is ConfigSource.PROJECT_CONFIG
    assert project_layer.snapshot_dir.value == (tmp_path / "project_snap").resolve()


def test_environment_variables_map_per_key(tmp_path: Path) -> None:
    environ = {
        "HUNTER_SNAPSHOT_DIR": "/abs/snap",
        "HUNTER_DATA_DIR": "/abs/data",
        "HUNTER_STORE_DIR": "/abs/store",
        "HUNTER_PAIRLIST_OUTPUT_DIR": "/abs/pairs",
    }
    config = resolve_config(tmp_path, environ, None)
    for resolved in config.all():
        assert resolved.source is ConfigSource.ENVIRONMENT
        assert resolved.value.is_absolute()
    assert config.snapshot_dir.value == Path("/abs/snap")


def test_invalid_yaml_degrades_to_issue_not_exception(tmp_path: Path) -> None:
    (tmp_path / "hunter.yaml").write_text("snapshot_dir: [unclosed\n")
    config = resolve_config(tmp_path, {}, None)
    assert config.snapshot_dir.source is ConfigSource.DEFAULT
    assert len(config.issues) == 1
    assert "failed to parse YAML" in config.issues[0].reason


def test_non_mapping_yaml_is_an_issue(tmp_path: Path) -> None:
    (tmp_path / "hunter.yaml").write_text("- just\n- a\n- list\n")
    config = resolve_config(tmp_path, {}, None)
    assert config.snapshot_dir.source is ConfigSource.DEFAULT
    assert any("mapping" in issue.reason for issue in config.issues)


def test_unknown_keys_recorded_and_ignored(tmp_path: Path) -> None:
    (tmp_path / "hunter.yaml").write_text(
        "snapshot_dir: snap\nunknown_key: value\n"
    )
    config = resolve_config(tmp_path, {}, None)
    assert config.snapshot_dir.value == (tmp_path / "snap").resolve()
    assert config.snapshot_dir.source is ConfigSource.PROJECT_CONFIG
    assert any("unknown key" in issue.reason for issue in config.issues)


def test_empty_and_nonstring_values_are_issues(tmp_path: Path) -> None:
    (tmp_path / "hunter.yaml").write_text("snapshot_dir: 42\nstore_dir: ''\n")
    config = resolve_config(tmp_path, {}, None)
    assert config.snapshot_dir.source is ConfigSource.DEFAULT
    assert config.store_dir.source is ConfigSource.DEFAULT
    assert len(config.issues) == 2


def test_relative_cli_override_resolves_against_project_root(tmp_path: Path) -> None:
    config = resolve_config(tmp_path, {}, {ConfigKey.DATA_DIR: "rel/data"})
    assert config.data_dir.value == (tmp_path / "rel/data").resolve()
    assert config.data_dir.source is ConfigSource.CLI


def test_user_config_path_honors_xdg(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "custom"))
    assert user_config_path() == tmp_path / "custom" / "hunter" / "config.yaml"


def test_find_project_root_discovers_pyproject(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert find_project_root(nested) == tmp_path.resolve()


def test_find_project_root_fallback_without_pyproject(tmp_path: Path) -> None:
    root = find_project_root(tmp_path)
    assert (root / "pyproject.toml").is_file() or root == Path(
        __import__("hunter.core.doctor.config", fromlist=["x"]).__file__
    ).resolve().parents[4]
