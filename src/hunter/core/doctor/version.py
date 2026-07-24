"""SemVer versioning for SPEC-077.

Tags follow ``vMAJOR.MINOR.PATCH`` with optional SemVer pre-release and
build metadata (e.g. ``v0.72.0-dev``, ``v0.71.0-rc.1``).  Tags named
``latest``, ``nightly*``, or ``release-*`` are always ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering

import hunter

_TAG_RE = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

#: Literal tag names and prefixes that are never considered releases.
_IGNORED_EXACT = frozenset({"latest", "nightly"})
_IGNORED_PREFIXES = ("nightly-", "nightly_", "release-")


@total_ordering
@dataclass(frozen=True)
class Version:
    """A Semantic Versioning 2.0.0 version."""

    major: int
    minor: int
    patch: int
    prerelease: str = ""
    build: str = ""

    def __str__(self) -> str:
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += f"-{self.prerelease}"
        if self.build:
            text += f"+{self.build}"
        return text

    @property
    def tag(self) -> str:
        """Canonical tag form (``v``-prefixed, build metadata dropped)."""
        text = f"v{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += f"-{self.prerelease}"
        return text

    def _precedence_key(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (
            self._precedence_key() == other._precedence_key()
            and _compare_prerelease(self.prerelease, other.prerelease) == 0
        )

    def __lt__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        if self._precedence_key() != other._precedence_key():
            return self._precedence_key() < other._precedence_key()
        return _compare_prerelease(self.prerelease, other.prerelease) < 0

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch, self.prerelease))


def _compare_prerelease(left: str, right: str) -> int:
    """Compare pre-release strings per SemVer 2.0.0 precedence rules."""
    if left == right:
        return 0
    if not left:
        return 1  # A release outranks any of its pre-releases.
    if not right:
        return -1
    left_parts = left.split(".")
    right_parts = right.split(".")
    for lpart, rpart in zip(left_parts, right_parts):
        if lpart == rpart:
            continue
        lnum = lpart.isdigit()
        rnum = rpart.isdigit()
        if lnum and rnum:
            return -1 if int(lpart) < int(rpart) else 1
        if lnum:
            return -1  # Numeric identifiers sort before alphanumeric.
        if rnum:
            return 1
        return -1 if lpart < rpart else 1
    if len(left_parts) == len(right_parts):
        return 0
    return -1 if len(left_parts) < len(right_parts) else 1


def is_ignored_tag(tag: str) -> bool:
    """Return True when ``tag`` is on the mandatory ignore list."""
    if tag in _IGNORED_EXACT:
        return True
    return tag.startswith(_IGNORED_PREFIXES)


def parse_version(text: str) -> Version | None:
    """Parse a SemVer string (optionally ``v``-prefixed).

    Returns ``None`` for invalid input.  Never raises.
    """
    match = _TAG_RE.match(text.strip())
    if match is None:
        return None
    return Version(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=match.group("prerelease") or "",
        build=match.group("build") or "",
    )


def parse_version_tag(tag: str) -> Version | None:
    """Parse a release tag, applying the ignore list.

    ``^{}`` dereference suffixes from ``git ls-remote`` are stripped.
    Returns ``None`` for ignored or invalid tags.
    """
    cleaned = tag.strip()
    if cleaned.endswith("^{}"):
        cleaned = cleaned[:-3]
    if is_ignored_tag(cleaned):
        return None
    return parse_version(cleaned)


def filter_release_tags(tags: list[str] | tuple[str, ...]) -> tuple[tuple[str, Version], ...]:
    """Filter and sort release tags.

    Drops ignored/invalid tags, collapses duplicates by tag name, and
    returns ``(tag, version)`` pairs sorted by SemVer precedence.
    """
    seen: dict[str, Version] = {}
    for tag in tags:
        cleaned = tag.strip()
        if cleaned.endswith("^{}"):
            cleaned = cleaned[:-3]
        if cleaned in seen:
            continue
        version = parse_version_tag(cleaned)
        if version is not None:
            seen[cleaned] = version
    return tuple(sorted(seen.items(), key=lambda item: item[1]))


def current_version() -> Version:
    """Return the current Hunter version from ``hunter.__version__``."""
    version = parse_version(hunter.__version__)
    if version is None:  # pragma: no cover - defensive; __version__ is SemVer
        raise ValueError(f"hunter.__version__ is not valid SemVer: {hunter.__version__!r}")
    return version
