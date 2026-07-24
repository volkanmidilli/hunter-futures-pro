"""Shared configuration resolution for SPEC-077.

Resolves the four supported path keys (``snapshot_dir``, ``data_dir``,
``store_dir``, ``pairlist_output_dir``) with the precedence order:

    defaults < project config (<repo>/hunter.yaml)
             < user config (~/.config/hunter/config.yaml)
             < environment < CLI

Every resolved value carries explicit provenance.  Resolution is a pure
function of its inputs; config-file problems are captured as issues and
never raised.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping

import yaml


class ConfigKey(str, Enum):
    """Supported shared configuration keys."""

    SNAPSHOT_DIR = "snapshot_dir"
    DATA_DIR = "data_dir"
    STORE_DIR = "store_dir"
    PAIRLIST_OUTPUT_DIR = "pairlist_output_dir"


class ConfigSource(str, Enum):
    """Provenance of a resolved configuration value."""

    DEFAULT = "DEFAULT"
    PROJECT_CONFIG = "PROJECT_CONFIG"
    USER_CONFIG = "USER_CONFIG"
    ENVIRONMENT = "ENVIRONMENT"
    CLI = "CLI"


#: Precedence order, lowest to highest.
SOURCE_PRECEDENCE: tuple[ConfigSource, ...] = (
    ConfigSource.DEFAULT,
    ConfigSource.PROJECT_CONFIG,
    ConfigSource.USER_CONFIG,
    ConfigSource.ENVIRONMENT,
    ConfigSource.CLI,
)

#: Environment variable mapping per key.
ENV_VAR_MAP: Mapping[ConfigKey, str] = {
    ConfigKey.SNAPSHOT_DIR: "HUNTER_SNAPSHOT_DIR",
    ConfigKey.DATA_DIR: "HUNTER_DATA_DIR",
    ConfigKey.STORE_DIR: "HUNTER_STORE_DIR",
    ConfigKey.PAIRLIST_OUTPUT_DIR: "HUNTER_PAIRLIST_OUTPUT_DIR",
}

#: Repo-relative defaults per key.
_DEFAULT_PATHS: Mapping[ConfigKey, str] = {
    ConfigKey.SNAPSHOT_DIR: "data/snapshots",
    ConfigKey.DATA_DIR: "data/feather",
    ConfigKey.STORE_DIR: "data/outcome_store",
    ConfigKey.PAIRLIST_OUTPUT_DIR: "data/pairlists",
}

PROJECT_CONFIG_FILENAME = "hunter.yaml"
USER_CONFIG_RELATIVE = Path("hunter") / "config.yaml"


@dataclass(frozen=True)
class ResolvedValue:
    """A single resolved configuration value with provenance."""

    key: ConfigKey
    value: Path
    source: ConfigSource


@dataclass(frozen=True)
class ConfigFileIssue:
    """A non-fatal problem observed while resolving configuration."""

    path: Path
    reason: str


@dataclass(frozen=True)
class ResolvedConfig:
    """Fully resolved shared configuration with per-key provenance."""

    snapshot_dir: ResolvedValue
    data_dir: ResolvedValue
    store_dir: ResolvedValue
    pairlist_output_dir: ResolvedValue
    issues: tuple[ConfigFileIssue, ...] = field(default_factory=tuple)

    def get(self, key: ConfigKey) -> ResolvedValue:
        """Return the resolved value for ``key``."""
        return {
            ConfigKey.SNAPSHOT_DIR: self.snapshot_dir,
            ConfigKey.DATA_DIR: self.data_dir,
            ConfigKey.STORE_DIR: self.store_dir,
            ConfigKey.PAIRLIST_OUTPUT_DIR: self.pairlist_output_dir,
        }[key]

    def all(self) -> tuple[ResolvedValue, ...]:
        """Return all resolved values in canonical key order."""
        return (self.snapshot_dir, self.data_dir, self.store_dir, self.pairlist_output_dir)


def user_config_path(environ: Mapping[str, str] | None = None) -> Path:
    """Return the user-level config path.

    Honors ``XDG_CONFIG_HOME`` when set, otherwise defaults to
    ``~/.config/hunter/config.yaml``.
    """
    env = os.environ if environ is None else environ
    xdg = env.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / USER_CONFIG_RELATIVE


def _load_yaml_mapping(path: Path) -> tuple[dict, str | None]:
    """Load a YAML file as a top-level mapping.

    Returns ``(mapping, None)`` on success or ``({}, reason)`` on any
    failure.  Missing files are not an issue and return ``({}, None)``.
    """
    if not path.is_file():
        return {}, None
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        return {}, f"failed to parse YAML: {exc}"
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return {}, "top-level YAML value must be a mapping"
    return data, None


def _layer_from_file(
    path: Path,
) -> tuple[dict[ConfigKey, str], tuple[ConfigFileIssue, ...]]:
    """Extract supported keys from a config file, recording issues."""
    raw, problem = _load_yaml_mapping(path)
    issues: list[ConfigFileIssue] = []
    if problem is not None:
        issues.append(ConfigFileIssue(path=path, reason=problem))
        return {}, tuple(issues)
    supported = {key.value: key for key in ConfigKey}
    layer: dict[ConfigKey, str] = {}
    for name, value in raw.items():
        key = supported.get(str(name))
        if key is None:
            issues.append(
                ConfigFileIssue(path=path, reason=f"unknown key ignored: {name!r}")
            )
            continue
        if not isinstance(value, str) or not value.strip():
            issues.append(
                ConfigFileIssue(
                    path=path,
                    reason=f"key {name!r} must be a non-empty string path",
                )
            )
            continue
        layer[key] = value
    return layer, tuple(issues)


def resolve_config(
    project_root: Path,
    environ: Mapping[str, str] | None = None,
    cli_overrides: Mapping[ConfigKey, str | Path | None] | None = None,
) -> ResolvedConfig:
    """Resolve all supported keys with full precedence and provenance.

    Args:
        project_root: Repository root used for defaults and the project
            config file (``<repo>/hunter.yaml``).
        environ: Environment mapping; defaults to ``os.environ``.
        cli_overrides: Optional per-key CLI values; ``None`` entries are
            treated as absent.

    Returns:
        A :class:`ResolvedConfig` with per-key provenance and any
        non-fatal issues encountered while reading config files.
    """
    env = os.environ if environ is None else environ
    cli = dict(cli_overrides or {})
    issues: list[ConfigFileIssue] = []

    layers: dict[ConfigSource, dict[ConfigKey, str]] = {
        source: {} for source in ConfigSource
    }

    project_layer, project_issues = _layer_from_file(project_root / PROJECT_CONFIG_FILENAME)
    layers[ConfigSource.PROJECT_CONFIG] = project_layer
    issues.extend(project_issues)

    user_layer, user_issues = _layer_from_file(user_config_path(env))
    layers[ConfigSource.USER_CONFIG] = user_layer
    issues.extend(user_issues)

    env_layer: dict[ConfigKey, str] = {}
    for key, var in ENV_VAR_MAP.items():
        raw = env.get(var)
        if raw is not None and raw.strip():
            env_layer[key] = raw
    layers[ConfigSource.ENVIRONMENT] = env_layer

    cli_layer: dict[ConfigKey, str] = {}
    for key, value in cli.items():
        if value is not None and str(value).strip():
            cli_layer[key] = str(value)
    layers[ConfigSource.CLI] = cli_layer

    resolved: dict[ConfigKey, ResolvedValue] = {}
    for key in ConfigKey:
        source = ConfigSource.DEFAULT
        raw_value: str | None = None
        for candidate in SOURCE_PRECEDENCE:
            if key in layers[candidate]:
                raw_value = layers[candidate][key]
                source = candidate
        if raw_value is None:
            path = (project_root / _DEFAULT_PATHS[key]).resolve()
        else:
            path = Path(raw_value).expanduser()
            if not path.is_absolute():
                path = (project_root / path).resolve()
        resolved[key] = ResolvedValue(key=key, value=path, source=source)

    return ResolvedConfig(
        snapshot_dir=resolved[ConfigKey.SNAPSHOT_DIR],
        data_dir=resolved[ConfigKey.DATA_DIR],
        store_dir=resolved[ConfigKey.STORE_DIR],
        pairlist_output_dir=resolved[ConfigKey.PAIRLIST_OUTPUT_DIR],
        issues=tuple(issues),
    )


def find_project_root(start: Path | None = None) -> Path:
    """Discover the project root without any git mutation.

    Walks upward from ``start`` (default: current working directory)
    looking for a ``pyproject.toml``; falls back to the package checkout
    root derived from this file's location.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    # Fallback: <repo>/src/hunter/core/doctor/config.py -> parents[4]
    return Path(__file__).resolve().parents[4]
