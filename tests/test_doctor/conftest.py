"""Shared helpers for SPEC-077 doctor tests."""

from __future__ import annotations

from pathlib import Path

from hunter.core.doctor.config import ResolvedConfig, resolve_config
from hunter.core.doctor.gitutil import GitResult, GitRunner
from hunter.core.doctor.models import DoctorContext


def make_git(responses: dict[tuple[str, ...], GitResult]) -> GitRunner:
    """Build a GitRunner with a fake transport keyed by git arguments."""

    def transport(argv, cwd, timeout):  # noqa: ANN001, ANN202 - test fake
        key = tuple(argv[1:])  # strip the leading "git"
        return responses.get(key, GitResult(ok=False, stderr=f"unexpected: {key}"))

    return GitRunner(cwd=Path.cwd(), transport=transport)


def make_context(
    project_root: Path,
    git: GitRunner | None = None,
    environ: dict[str, str] | None = None,
    cli_overrides: dict | None = None,
) -> DoctorContext:
    """Build a DoctorContext rooted at a tmp project directory."""
    config: ResolvedConfig = resolve_config(
        project_root, environ if environ is not None else {}, cli_overrides
    )
    return DoctorContext(
        project_root=project_root,
        config=config,
        git=git if git is not None else make_git({}),
    )


def clean_worktree_responses(branch: str = "main") -> dict[tuple[str, ...], GitResult]:
    """Fake git responses for a clean worktree on a branch."""
    return {
        ("rev-parse", "--is-inside-work-tree"): GitResult(ok=True, stdout="true\n"),
        ("branch", "--show-current"): GitResult(ok=True, stdout=f"{branch}\n"),
        ("status", "--porcelain"): GitResult(ok=True, stdout=""),
    }
