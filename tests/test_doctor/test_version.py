"""Tests for SPEC-077 SemVer versioning and tag filtering."""

from __future__ import annotations

import hunter
from hunter.core.doctor.version import (
    Version,
    current_version,
    filter_release_tags,
    is_ignored_tag,
    parse_version,
    parse_version_tag,
)


def test_parse_valid_versions() -> None:
    assert parse_version("v1.2.3") == Version(1, 2, 3)
    assert parse_version("1.2.3") == Version(1, 2, 3)
    assert parse_version("0.72.0-dev") == Version(0, 72, 0, prerelease="dev")
    assert parse_version("v0.71.0-rc.1") == Version(0, 71, 0, prerelease="rc.1")
    assert parse_version("v1.0.0+build.5") == Version(1, 0, 0, build="build.5")


def test_parse_rejects_invalid_versions() -> None:
    for text in ("", "1.2", "v1.2.3.4", "foo", "v1.02.3", "1.0.0-rc..1"):
        assert parse_version(text) is None


def test_ignored_tags() -> None:
    for tag in ("latest", "nightly", "nightly-2026-07-24", "nightly_2026", "release-1.0"):
        assert is_ignored_tag(tag)
        assert parse_version_tag(tag) is None
    assert not is_ignored_tag("v1.0.0")


def test_semver_ordering_with_prereleases() -> None:
    assert Version(1, 0, 0, prerelease="rc.1") < Version(1, 0, 0)
    assert Version(0, 72, 0, prerelease="dev") < Version(0, 72, 0)
    assert Version(0, 71, 0, prerelease="rc.1") < Version(0, 71, 0, prerelease="rc.2")
    assert Version(1, 0, 0, prerelease="1") < Version(1, 0, 0, prerelease="alpha")
    assert Version(0, 72, 0, prerelease="dev") < Version(0, 76, 0, prerelease="dev")
    assert Version(2, 0, 0) > Version(1, 99, 99)


def test_version_tag_round_trip() -> None:
    assert Version(0, 72, 0, prerelease="dev").tag == "v0.72.0-dev"
    assert Version(1, 2, 3).tag == "v1.2.3"


def test_filter_release_tags_dedupes_strips_deref_and_sorts() -> None:
    tags = (
        "v0.71.0-rc.1",
        "v0.72.0-dev",
        "v0.72.0-dev^{}",
        "latest",
        "nightly-2026",
        "release-0.99",
        "not-a-version",
        "v0.70.0-dev",
    )
    filtered = filter_release_tags(tags)
    names = tuple(name for name, _ in filtered)
    assert names == ("v0.70.0-dev", "v0.71.0-rc.1", "v0.72.0-dev")
    versions = tuple(version for _, version in filtered)
    assert versions == tuple(sorted(versions))


def test_current_version_matches_package_version() -> None:
    version = current_version()
    assert str(version) == hunter.__version__
    assert parse_version(hunter.__version__) is not None
