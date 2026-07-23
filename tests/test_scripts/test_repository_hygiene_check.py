"""Tests for scripts/repository_hygiene_check.py."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.repository_hygiene_check import (
    ALLOWED_EXACT_PATHS,
    FORBIDDEN_EXACT_FILES,
    FORBIDDEN_ROOT_DIRS,
    FORBIDDEN_SUFFIXES,
    _check_paths,
    _is_forbidden,
    main,
)


@pytest.mark.parametrize("path", sorted(ALLOWED_EXACT_PATHS))
def test_allowed_exact_paths_are_clean(path: str) -> None:
    assert _is_forbidden(path) is None


@pytest.mark.parametrize("prefix", FORBIDDEN_ROOT_DIRS)
def test_forbidden_root_dirs(prefix: str) -> None:
    assert _is_forbidden(f"{prefix}file.txt") is not None
    assert _is_forbidden(prefix.rstrip("/")) is not None


@pytest.mark.parametrize("filename", FORBIDDEN_EXACT_FILES)
def test_forbidden_exact_files(filename: str) -> None:
    assert _is_forbidden(filename) is not None


@pytest.mark.parametrize("suffix", FORBIDDEN_SUFFIXES)
def test_forbidden_suffixes(suffix: str) -> None:
    assert _is_forbidden(f"some/path/file{suffix}") is not None


@pytest.mark.parametrize("filename", [
    ".env.local",
    ".env.secret",
    ".env.development",
])
def test_forbidden_env_overrides(filename: str) -> None:
    assert _is_forbidden(filename) is not None


@pytest.mark.parametrize("filename", [
    ".env.example",
    ".env.template",
    ".env.sample",
])
def test_allowed_env_templates(filename: str) -> None:
    assert _is_forbidden(filename) is None


@pytest.mark.parametrize("filename", [
    "hunter-pairs.json",
    "hunter-pairs-backup.json",
    "hunter-pairs-2026.json",
])
def test_forbidden_generated_pairlists(filename: str) -> None:
    assert _is_forbidden(filename) is not None


def test_allowed_example_pairlist() -> None:
    assert _is_forbidden("examples/hunter-pairs.json") is None


def test_check_paths_returns_sorted_unique_violations() -> None:
    paths = ["data/file.csv", "data/file.csv", "reports/out.html"]
    violations = _check_paths(paths, "tracked")
    assert len(violations) == 2
    assert violations[0][1] == "data/file.csv"
    assert violations[1][1] == "reports/out.html"


@patch("scripts.repository_hygiene_check._git_tracked_paths", return_value=[])
@patch("scripts.repository_hygiene_check._git_staged_paths", return_value=[])
def test_main_returns_zero_when_clean(
    mock_staged: object, mock_tracked: object
) -> None:
    assert main() == 0


@patch(
    "scripts.repository_hygiene_check._git_tracked_paths",
    return_value=["data/file.csv"],
)
@patch("scripts.repository_hygiene_check._git_staged_paths", return_value=[])
def test_main_returns_one_for_tracked_violation(
    mock_staged: object, mock_tracked: object
) -> None:
    assert main() == 1


@patch("scripts.repository_hygiene_check._git_tracked_paths", return_value=[])
@patch(
    "scripts.repository_hygiene_check._git_staged_paths",
    return_value=[".env.local"],
)
def test_main_returns_one_for_staged_violation(
    mock_staged: object, mock_tracked: object
) -> None:
    assert main() == 1


@patch(
    "scripts.repository_hygiene_check.subprocess.run",
    side_effect=subprocess.CalledProcessError(1, "git"),
)
def test_main_returns_two_on_git_error(mock_run: object) -> None:
    assert main() == 2


def test_script_exists() -> None:
    script = Path(__file__).parents[2] / "scripts" / "repository_hygiene_check.py"
    assert script.exists()
    assert script.is_file()
