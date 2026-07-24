"""Package-versions category check for SPEC-077."""

from __future__ import annotations

import importlib.metadata
import re

from hunter.core.doctor.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DoctorContext,
)

#: (distribution name, minimum version) aligned with pyproject.toml.
MINIMUM_VERSIONS: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("pydantic", (2, 0, 0)),
    ("pyyaml", (6, 0, 0)),
    ("pandas", (2, 0, 0)),
    ("pyarrow", (14, 0, 0)),
    ("numpy", (1, 24, 0)),
)

_VERSION_PART_RE = re.compile(r"\d+")


def _parse_version_parts(raw: str) -> tuple[int, ...] | None:
    """Extract leading numeric version parts; None when unparseable."""
    parts = _VERSION_PART_RE.findall(raw.split("-", 1)[0].split("+", 1)[0])
    if not parts:
        return None
    return tuple(int(part) for part in parts)


def _satisfies(found: tuple[int, ...], minimum: tuple[int, ...]) -> bool:
    width = max(len(found), len(minimum))
    padded_found = found + (0,) * (width - len(found))
    padded_min = minimum + (0,) * (width - len(minimum))
    return padded_found >= padded_min


def check_package_versions(context: DoctorContext) -> tuple[CheckResult, ...]:
    """Verify runtime dependencies import at or above minimum versions."""
    del context  # Dependency state is a property of this environment.
    results: list[CheckResult] = []
    for dist_name, minimum in MINIMUM_VERSIONS:
        check_id = f"packages.{dist_name}"
        minimum_text = ".".join(str(part) for part in minimum)
        try:
            raw_version = importlib.metadata.version(dist_name)
        except importlib.metadata.PackageNotFoundError:
            results.append(
                CheckResult(
                    check_id=check_id,
                    category=CheckCategory.PACKAGES,
                    status=CheckStatus.BLOCKER,
                    summary=f"Required dependency {dist_name!r} is not installed.",
                    remediation=f"Install project dependencies: pip install -e . "
                    f"(requires {dist_name}>={minimum_text})",
                )
            )
            continue
        found = _parse_version_parts(raw_version)
        if found is None:
            results.append(
                CheckResult(
                    check_id=check_id,
                    category=CheckCategory.PACKAGES,
                    status=CheckStatus.SKIPPED,
                    summary=(
                        f"Could not parse {dist_name} version {raw_version!r}."
                    ),
                )
            )
            continue
        if _satisfies(found, minimum):
            results.append(
                CheckResult(
                    check_id=check_id,
                    category=CheckCategory.PACKAGES,
                    status=CheckStatus.PASS,
                    summary=f"{dist_name} {raw_version} satisfies >={minimum_text}.",
                )
            )
        else:
            results.append(
                CheckResult(
                    check_id=check_id,
                    category=CheckCategory.PACKAGES,
                    status=CheckStatus.BLOCKER,
                    summary=(
                        f"{dist_name} {raw_version} is below the required "
                        f"minimum >={minimum_text}."
                    ),
                    remediation=f"Upgrade {dist_name}: pip install -U "
                    f"'{dist_name}>={minimum_text}'",
                )
            )
    return tuple(results)
