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
    ZERO_SHA,
    _check_paths,
    _is_forbidden,
    check_pre_push,
    check_ref_tree,
    forbidden_reason,
    main,
    parse_pre_push_refs,
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


@pytest.mark.parametrize("path", [
    ".wrongstack/project.json",
    ".wrongstack/AGENTS.md",
    ".venv/bin/python",
    "src/hunter/__pycache__/x.pyc",
    "tests/__pycache__/y.pyc",
    ".pytest_cache/README.md",
    ".claude/settings.local.json",
    ".vscode/settings.json",
    ".idea/workspace.xml",
    "docs/.DS_Store",
    "Thumbs.db",
])
def test_forbidden_development_environment_paths(path: str) -> None:
    assert _is_forbidden(path) is not None


@pytest.mark.parametrize("path", [
    "src/hunter/discovery/engine.py",
    "tests/test_doctor/test_cli.py",
    "docs/development/DEVELOPER_WORKFLOW.md",
    "scripts/repository_hygiene_check.py",
    "pyproject.toml",
])
def test_legitimate_paths_are_clean(path: str) -> None:
    assert _is_forbidden(path) is None


def test_forbidden_reason_matches_is_forbidden() -> None:
    assert forbidden_reason(".wrongstack/project.json") is not None
    assert forbidden_reason("src/hunter/ok.py") is None


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
    assert main([]) == 0


@patch(
    "scripts.repository_hygiene_check._git_tracked_paths",
    return_value=["data/file.csv"],
)
@patch("scripts.repository_hygiene_check._git_staged_paths", return_value=[])
def test_main_returns_one_for_tracked_violation(
    mock_staged: object, mock_tracked: object
) -> None:
    assert main([]) == 1


@patch("scripts.repository_hygiene_check._git_tracked_paths", return_value=[])
@patch(
    "scripts.repository_hygiene_check._git_staged_paths",
    return_value=[".env.local"],
)
def test_main_returns_one_for_staged_violation(
    mock_staged: object, mock_tracked: object
) -> None:
    assert main([]) == 1


@patch(
    "scripts.repository_hygiene_check.subprocess.run",
    side_effect=subprocess.CalledProcessError(1, "git"),
)
def test_main_returns_two_on_git_error(mock_run: object) -> None:
    assert main([]) == 2


def test_script_exists() -> None:
    script = Path(__file__).parents[2] / "scripts" / "repository_hygiene_check.py"
    assert script.exists()
    assert script.is_file()


# --- Tree and pre-push modes ---------------------------------------------------


@patch(
    "scripts.repository_hygiene_check._git_tree_paths",
    return_value=["src/hunter/ok.py", "docs/ok.md"],
)
def test_check_ref_tree_clean(mock_tree: object) -> None:
    assert check_ref_tree("HEAD") == []


@patch(
    "scripts.repository_hygiene_check._git_tree_paths",
    return_value=["src/hunter/ok.py", ".wrongstack/project.json"],
)
def test_check_ref_tree_blocks_dev_env_file(mock_tree: object) -> None:
    violations = check_ref_tree("HEAD")
    assert len(violations) == 1
    assert violations[0][1] == ".wrongstack/project.json"
    assert "forbidden root directory" in violations[0][2]


@patch(
    "scripts.repository_hygiene_check._git_tree_paths",
    return_value=["src/hunter/__pycache__/engine.cpython-313.pyc"],
)
def test_check_ref_tree_blocks_nested_pycache(mock_tree: object) -> None:
    violations = check_ref_tree("HEAD")
    assert len(violations) == 1
    assert "forbidden path component" in violations[0][2]


def test_parse_pre_push_refs_skips_deletions() -> None:
    stdin = (
        "refs/heads/main aaaa1111 refs/heads/main bbbb2222\n"
        f"refs/heads/old {ZERO_SHA} refs/heads/old cccc3333\n"
        "\n"
        "not-enough-fields\n"
    )
    refs = parse_pre_push_refs(stdin)
    assert refs == [("refs/heads/main", "aaaa1111", "refs/heads/main", "bbbb2222")]


@patch(
    "scripts.repository_hygiene_check._git_tree_paths",
    return_value=["src/hunter/ok.py"],
)
def test_check_pre_push_clean(mock_tree: object) -> None:
    stdin = "refs/heads/main aaaa1111 refs/heads/main bbbb2222\n"
    assert check_pre_push(stdin) == []


@patch(
    "scripts.repository_hygiene_check._git_tree_paths",
    return_value=[".venv/bin/python"],
)
def test_check_pre_push_blocks_forbidden_tree(mock_tree: object) -> None:
    stdin = "refs/heads/main aaaa1111 refs/heads/main bbbb2222\n"
    violations = check_pre_push(stdin)
    assert len(violations) == 1
    assert violations[0][0] == "refs/heads/main"
    assert violations[0][1] == ".venv/bin/python"


@patch(
    "scripts.repository_hygiene_check._git_tree_paths",
    return_value=[".env.production"],
)
def test_check_pre_push_ignores_ref_deletions(mock_tree: object) -> None:
    stdin = f"refs/heads/old {ZERO_SHA} refs/heads/old cccc3333\n"
    assert check_pre_push(stdin) == []


@patch(
    "scripts.repository_hygiene_check._git_tree_paths",
    return_value=[".wrongstack/project.json"],
)
def test_main_pre_push_mode_blocks_push(
    mock_tree: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    stdin_text = "refs/heads/main aaaa1111 refs/heads/main bbbb2222\n"
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(stdin_text))
    assert main(["--pre-push"]) == 1
    assert "push blocked" in capsys.readouterr().out


@patch(
    "scripts.repository_hygiene_check._git_tree_paths",
    return_value=["src/hunter/ok.py"],
)
def test_main_pre_push_mode_allows_clean_push(
    mock_tree: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    stdin_text = "refs/heads/main aaaa1111 refs/heads/main bbbb2222\n"
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(stdin_text))
    assert main(["--pre-push"]) == 0


@patch(
    "scripts.repository_hygiene_check._git_tree_paths",
    return_value=["data/snapshots/x.parquet"],
)
def test_main_tree_mode_reports_violation(mock_tree: object) -> None:
    assert main(["--tree", "HEAD"]) == 1


@patch(
    "scripts.repository_hygiene_check._git_tree_paths",
    return_value=["src/hunter/ok.py"],
)
def test_main_tree_mode_clean(mock_tree: object) -> None:
    assert main(["--tree", "HEAD"]) == 0
