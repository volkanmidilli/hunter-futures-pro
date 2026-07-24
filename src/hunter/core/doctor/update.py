"""Update check and update plan for SPEC-077 (architecture-only).

The update check is strictly read-only: it queries remote tags via
``git ls-remote --tags`` (which only *reads* the remote advertisement and
never alters local refs, the object database, or the worktree) or, in
``--offline`` mode, reads local tags via ``git tag --list``.  Any remote
failure degrades gracefully to ``UpdateStatus.UNKNOWN`` — no exception
escapes, and no fetch, checkout, or pull is ever performed.

The update plan is a deterministic, non-executing report: the
recommended commands are data, and no code path in this module can
execute them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from hunter.core.doctor.gitutil import GitRunner
from hunter.core.doctor.version import (
    Version,
    current_version,
    filter_release_tags,
    parse_version,
)


class UpdateStatus(str, Enum):
    """Outcome of an update check."""

    UP_TO_DATE = "UP_TO_DATE"
    UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
    UNKNOWN = "UNKNOWN"


class UpdateSource(str, Enum):
    """Where the tag information came from."""

    REMOTE = "remote"
    LOCAL = "local"


class MigrationLevel(str, Enum):
    """SemVer delta classification between current and target."""

    MAJOR = "MAJOR"
    MINOR = "MINOR"
    PATCH = "PATCH"
    NONE = "NONE"


@dataclass(frozen=True)
class TagCollection:
    """Tags gathered from a remote or local source."""

    source: UpdateSource
    tags: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None


@dataclass(frozen=True)
class UpdateCheckResult:
    """Result of ``hunter update check``."""

    current_version: Version
    latest_version: Version | None
    status: UpdateStatus
    source: UpdateSource
    tags_considered: int
    reason: str | None = None
    research_only: bool = True
    human_approval_required: bool = True


@dataclass(frozen=True)
class UpdatePlan:
    """Deterministic, non-executing update plan."""

    current_version: Version
    target_version: Version
    rollback_tag: str
    rollback_tag_verified: bool
    migration_level: MigrationLevel
    migration_requirements: tuple[str, ...]
    breaking_changes: str
    recommended_commands: tuple[str, ...]
    research_only: bool = True
    human_approval_required: bool = True


def _parse_ls_remote_tags(stdout: str) -> tuple[str, ...]:
    """Extract tag names from ``git ls-remote --tags`` output."""
    tags: list[str] = []
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[-1]
        if not ref.startswith("refs/tags/"):
            continue
        tags.append(ref[len("refs/tags/"):])
    return tuple(tags)


def collect_tags(
    git: GitRunner,
    *,
    offline: bool,
    remote: str = "origin",
) -> TagCollection:
    """Collect release tag names without any git mutation.

    Offline mode uses local tags only.  Online mode resolves the remote
    URL and runs ``git ls-remote --tags``.  Every failure mode returns a
    :class:`TagCollection` with ``error`` set; nothing is raised.
    """
    source = UpdateSource.LOCAL if offline else UpdateSource.REMOTE
    inside = git.run("rev-parse", "--is-inside-work-tree")
    if inside.error is not None:
        return TagCollection(source=source, error=inside.error)
    if not inside.ok or inside.stdout.strip() != "true":
        return TagCollection(
            source=source,
            error=(
                "Git metadata is unavailable (not a Git work tree); "
                "update check requires a Git clone."
            ),
        )
    if offline:
        result = git.run("tag", "--list")
        if result.error is not None:
            return TagCollection(source=UpdateSource.LOCAL, error=result.error)
        if not result.ok:
            reason = result.stderr.strip() or f"git tag exited with {result.returncode}"
            return TagCollection(source=UpdateSource.LOCAL, error=reason)
        tags = tuple(line.strip() for line in result.stdout.splitlines() if line.strip())
        return TagCollection(source=UpdateSource.LOCAL, tags=tags)

    url_result = git.run("config", "--get", f"remote.{remote}.url")
    if url_result.error is not None:
        return TagCollection(source=UpdateSource.REMOTE, error=url_result.error)
    url = url_result.stdout.strip()
    if not url_result.ok or not url:
        return TagCollection(
            source=UpdateSource.REMOTE,
            error=f"remote {remote!r} has no URL configured",
        )

    remote_result = git.run("ls-remote", "--tags", url)
    if remote_result.error is not None:
        return TagCollection(source=UpdateSource.REMOTE, error=remote_result.error)
    if not remote_result.ok:
        reason = (
            remote_result.stderr.strip()
            or f"git ls-remote exited with {remote_result.returncode}"
        )
        return TagCollection(source=UpdateSource.REMOTE, error=reason)
    return TagCollection(
        source=UpdateSource.REMOTE,
        tags=_parse_ls_remote_tags(remote_result.stdout),
    )


def run_update_check(
    git: GitRunner,
    *,
    offline: bool = False,
    remote: str = "origin",
) -> UpdateCheckResult:
    """Check whether a newer released version is available (read-only)."""
    current = current_version()
    collection = collect_tags(git, offline=offline, remote=remote)
    if collection.error is not None:
        return UpdateCheckResult(
            current_version=current,
            latest_version=None,
            status=UpdateStatus.UNKNOWN,
            source=collection.source,
            tags_considered=0,
            reason=collection.error,
        )
    parsed = filter_release_tags(collection.tags)
    if not parsed:
        return UpdateCheckResult(
            current_version=current,
            latest_version=None,
            status=UpdateStatus.UNKNOWN,
            source=collection.source,
            tags_considered=0,
            reason="no valid release tags found",
        )
    latest_tag, latest = parsed[-1]
    del latest_tag  # The version carries the identity.
    status = (
        UpdateStatus.UPDATE_AVAILABLE if latest > current else UpdateStatus.UP_TO_DATE
    )
    return UpdateCheckResult(
        current_version=current,
        latest_version=latest,
        status=status,
        source=collection.source,
        tags_considered=len(parsed),
    )


def classify_migration(current: Version, target: Version) -> MigrationLevel:
    """Classify the SemVer delta between current and target."""
    if target.major != current.major:
        return MigrationLevel.MAJOR
    if target.minor != current.minor:
        return MigrationLevel.MINOR
    if target.patch != current.patch:
        return MigrationLevel.PATCH
    return MigrationLevel.NONE


_MIGRATION_REQUIREMENTS: dict[MigrationLevel, tuple[str, ...]] = {
    MigrationLevel.MAJOR: (
        "MAJOR version bump: a full changelog audit is required.",
        "Review all breaking changes between the current and target versions.",
        "Verify configuration keys and CLI flags after updating.",
        "Run the full test suite before resuming research workflows.",
    ),
    MigrationLevel.MINOR: (
        "MINOR version bump: review the changelog for new features and deprecations.",
        "Run hunter doctor after updating.",
    ),
    MigrationLevel.PATCH: ("PATCH version bump: no migration steps expected.",),
    MigrationLevel.NONE: (
        "Current version is already at or beyond the target version; "
        "no update required.",
    ),
}


def build_update_plan(
    current: Version,
    target: Version,
    known_tags: tuple[str, ...] | list[str],
) -> UpdatePlan:
    """Build a deterministic, non-executing update plan.

    The recommended commands are human-readable data only; this function
    has no capability to execute them.
    """
    level = classify_migration(current, target)
    if target <= current:
        # Never produce a "downgrade plan" mislabeled as an update.
        level = MigrationLevel.NONE
    elif level is MigrationLevel.NONE:
        # Same core version but a newer target: a pre-release promotion
        # (e.g. 0.76.0-dev -> 0.76.0), which is a real (minor-risk) update.
        level = MigrationLevel.PATCH
    rollback_tag = current.tag
    verified = rollback_tag in set(known_tags)
    breaking = (
        "POSSIBLE_MAJOR_BREAKING_CHANGES"
        if level is MigrationLevel.MAJOR
        else "NONE_DECLARED"
    )
    if level is MigrationLevel.NONE:
        commands: tuple[str, ...] = ()
    else:
        commands = (
            f"Review the changelog and release notes for {target.tag}.",
            "git fetch --tags",
            f"git checkout {target.tag}",
            "pip install -e .",
            "hunter doctor",
        )
    return UpdatePlan(
        current_version=current,
        target_version=target,
        rollback_tag=rollback_tag,
        rollback_tag_verified=verified,
        migration_level=level,
        migration_requirements=_MIGRATION_REQUIREMENTS[level],
        breaking_changes=breaking,
        recommended_commands=commands,
    )


def resolve_target_version(
    target_text: str,
    known_tags: tuple[str, ...] | list[str],
) -> tuple[Version | None, str | None]:
    """Resolve and validate an explicit ``--target`` against known tags.

    Returns ``(version, None)`` on success or ``(None, reason)`` when the
    target is invalid or not present among the known release tags.
    """
    version = parse_version(target_text)
    if version is None:
        return None, f"target {target_text!r} is not a valid SemVer version"
    parsed = dict(filter_release_tags(tuple(known_tags)))
    for tag, tag_version in parsed.items():
        if tag_version == version:
            return tag_version, None
    return None, (
        f"target {version.tag} was not found among the known release tags; "
        "run hunter update check to list availability"
    )
