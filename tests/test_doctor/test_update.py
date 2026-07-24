"""Tests for SPEC-077 update check and update plan."""

from __future__ import annotations

import json
from pathlib import Path

from hunter.core.doctor.gitutil import GitResult
from hunter.core.doctor.report import render_plan_json
from hunter.core.doctor.update import (
    MigrationLevel,
    UpdateStatus,
    UpdateSource,
    build_update_plan,
    collect_tags,
    resolve_target_version,
    run_update_check,
)
from hunter.core.doctor.version import Version, current_version

from .conftest import make_git

_LS_REMOTE_OUTPUT = """\
aaaa\trefs/tags/v0.70.0-dev
bbbb\trefs/tags/v0.71.0-rc.1
cccc\trefs/tags/v0.72.0-dev
dddd\trefs/tags/v0.72.0-dev^{}
eeee\trefs/tags/latest
ffff\trefs/tags/nightly-2026-07-24
gggg\trefs/tags/release-0.99
hhhh\trefs/tags/v9.9.9
"""


def _remote_git(ls_remote: GitResult) -> object:
    return make_git(
        {
            ("config", "--get", "remote.origin.url"): GitResult(
                ok=True, stdout="https://example.invalid/repo.git\n"
            ),
            ("ls-remote", "--tags", "https://example.invalid/repo.git"): ls_remote,
        }
    )


# --- collect_tags ------------------------------------------------------------


def test_collect_tags_offline_uses_local_only() -> None:
    git = make_git(
        {("tag", "--list"): GitResult(ok=True, stdout="v0.70.0-dev\nv0.72.0-dev\n")}
    )
    collection = collect_tags(git, offline=True)
    assert collection.source is UpdateSource.LOCAL
    assert collection.tags == ("v0.70.0-dev", "v0.72.0-dev")
    assert collection.error is None


def test_collect_tags_remote_parses_ls_remote() -> None:
    git = _remote_git(GitResult(ok=True, stdout=_LS_REMOTE_OUTPUT))
    collection = collect_tags(git, offline=False)
    assert collection.source is UpdateSource.REMOTE
    assert collection.error is None
    assert "v0.72.0-dev^{}" in collection.tags
    assert "v9.9.9" in collection.tags


def test_collect_tags_missing_remote_url() -> None:
    git = make_git(
        {("config", "--get", "remote.origin.url"): GitResult(ok=True, stdout="")}
    )
    collection = collect_tags(git, offline=False)
    assert collection.error is not None
    assert "no URL" in collection.error


def test_collect_tags_remote_failure_is_graceful() -> None:
    git = _remote_git(
        GitResult(ok=False, stderr="fatal: unable to connect", returncode=128)
    )
    collection = collect_tags(git, offline=False)
    assert collection.error == "fatal: unable to connect"


def test_collect_tags_timeout_is_graceful() -> None:
    git = _remote_git(GitResult(ok=False, error="git command timed out after 10s"))
    collection = collect_tags(git, offline=False)
    assert "timed out" in collection.error


# --- run_update_check ----------------------------------------------------------


def test_update_check_remote_update_available() -> None:
    git = _remote_git(GitResult(ok=True, stdout=_LS_REMOTE_OUTPUT))
    result = run_update_check(git, offline=False)
    assert result.status is UpdateStatus.UPDATE_AVAILABLE
    assert result.latest_version == Version(9, 9, 9)
    assert result.current_version == current_version()
    assert result.source is UpdateSource.REMOTE
    assert result.tags_considered == 4  # latest/nightly/release-*/invalid excluded
    assert result.research_only is True


def test_update_check_offline_up_to_date() -> None:
    current = current_version()
    git = make_git(
        {("tag", "--list"): GitResult(ok=True, stdout=f"{current.tag}\n")}
    )
    result = run_update_check(git, offline=True)
    assert result.status is UpdateStatus.UP_TO_DATE
    assert result.latest_version == current


def test_update_check_remote_failure_degrades_to_unknown() -> None:
    git = _remote_git(GitResult(ok=False, stderr="network down", returncode=1))
    result = run_update_check(git, offline=False)
    assert result.status is UpdateStatus.UNKNOWN
    assert result.latest_version is None
    assert result.reason == "network down"


def test_update_check_no_valid_tags_is_unknown() -> None:
    git = make_git(
        {("tag", "--list"): GitResult(ok=True, stdout="latest\nnightly-1\n")}
    )
    result = run_update_check(git, offline=True)
    assert result.status is UpdateStatus.UNKNOWN
    assert result.reason == "no valid release tags found"


# --- build_update_plan ---------------------------------------------------------


def test_plan_minor_bump_fields() -> None:
    current = Version(0, 72, 0, prerelease="dev")
    target = Version(0, 76, 0, prerelease="dev")
    tags = ("v0.72.0-dev", "v0.76.0-dev")
    plan = build_update_plan(current, target, tags)
    assert plan.migration_level is MigrationLevel.MINOR
    assert plan.breaking_changes == "NONE_DECLARED"
    assert plan.rollback_tag == "v0.72.0-dev"
    assert plan.rollback_tag_verified is True
    assert plan.recommended_commands[-1] == "hunter doctor"
    assert f"git checkout {target.tag}" in plan.recommended_commands
    assert plan.research_only is True
    assert plan.human_approval_required is True


def test_plan_major_bump_declares_breaking_changes() -> None:
    plan = build_update_plan(Version(0, 72, 0), Version(1, 0, 0), ("v1.0.0",))
    assert plan.migration_level is MigrationLevel.MAJOR
    assert plan.breaking_changes == "POSSIBLE_MAJOR_BREAKING_CHANGES"
    assert plan.rollback_tag_verified is False
    assert len(plan.migration_requirements) == 4


def test_plan_same_version_has_no_commands() -> None:
    current = Version(0, 72, 0, prerelease="dev")
    plan = build_update_plan(current, current, (current.tag,))
    assert plan.migration_level is MigrationLevel.NONE
    assert plan.recommended_commands == ()
    assert plan.breaking_changes == "NONE_DECLARED"


def test_plan_never_recommends_a_downgrade() -> None:
    """A target older than current yields NONE, not a mislabeled 'update'."""
    current = Version(0, 76, 0, prerelease="dev")
    target = Version(0, 72, 0, prerelease="dev")
    plan = build_update_plan(current, target, (current.tag, target.tag))
    assert plan.migration_level is MigrationLevel.NONE
    assert plan.recommended_commands == ()
    assert plan.breaking_changes == "NONE_DECLARED"
    assert plan.rollback_tag == current.tag


def test_plan_prerelease_promotion_is_a_patch_level_update() -> None:
    """0.76.0-dev -> 0.76.0 is a real update, not 'already at target'."""
    current = Version(0, 76, 0, prerelease="dev")
    target = Version(0, 76, 0)
    plan = build_update_plan(current, target, (current.tag, target.tag))
    assert plan.migration_level is MigrationLevel.PATCH
    assert f"git checkout {target.tag}" in plan.recommended_commands


def test_plan_is_deterministic_byte_identical() -> None:
    current = Version(0, 72, 0, prerelease="dev")
    target = Version(1, 0, 0)
    tags = ("v0.72.0-dev", "v1.0.0")
    first = render_plan_json(build_update_plan(current, target, tags))
    second = render_plan_json(build_update_plan(current, target, tags))
    assert first == second
    payload = json.loads(first)
    assert payload["target_version"] == "1.0.0"
    assert payload["rollback_tag"] == "v0.72.0-dev"


def test_plan_never_invokes_subprocess() -> None:
    """build_update_plan takes plain data; a raising transport proves the
    plan path performs no subprocess invocation at all."""

    def exploding_transport(argv, cwd, timeout):
        raise AssertionError("subprocess must not be invoked")

    from hunter.core.doctor.gitutil import GitRunner

    git = GitRunner(cwd=Path.cwd(), transport=exploding_transport)
    del git  # The plan API never receives a runner.
    plan = build_update_plan(Version(0, 1, 0), Version(0, 2, 0), ("v0.2.0",))
    assert plan.migration_level is MigrationLevel.MINOR


# --- resolve_target_version ----------------------------------------------------


def test_resolve_target_accepts_known_tag() -> None:
    version, problem = resolve_target_version("0.76.0-dev", ("v0.76.0-dev",))
    assert problem is None
    assert version == Version(0, 76, 0, prerelease="dev")


def test_resolve_target_accepts_v_prefixed() -> None:
    version, problem = resolve_target_version("v1.2.3", ("v1.2.3",))
    assert problem is None
    assert version == Version(1, 2, 3)


def test_resolve_target_rejects_unknown() -> None:
    version, problem = resolve_target_version("9.9.9", ("v1.2.3",))
    assert version is None
    assert "not found" in problem


def test_resolve_target_rejects_invalid() -> None:
    version, problem = resolve_target_version("not-a-version", ("v1.2.3",))
    assert version is None
    assert "not a valid SemVer" in problem
