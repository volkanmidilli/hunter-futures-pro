"""In-memory engine for hunter.release_hardening package."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hunter.release_hardening.models import (
    FORBIDDEN_RELEASE_HARDENING_TERMS,
    RELEASE_HARDENING_VERSION,
    CompletedAuditPackage,
    PackageDeclaration,
    ReleaseHardeningCheck,
    ReleaseHardeningCheckCategory,
    ReleaseHardeningCheckResult,
    ReleaseHardeningConfig,
    ReleaseHardeningDataQuality,
    ReleaseHardeningInput,
    ReleaseHardeningReasonCode,
    ReleaseHardeningReport,
    ReleaseHardeningSafetyFlags,
    ReleaseHardeningSeverity,
    ReleaseHardeningState,
)


def has_unsafe_release_hardening_content(
    text: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    forbidden_terms: frozenset[str] | None = None,
) -> bool:
    """Return True if text, tags, or metadata contain forbidden hardening terms."""
    terms = forbidden_terms or FORBIDDEN_RELEASE_HARDENING_TERMS
    if text is not None and _has_forbidden_term(text, terms):
        return True
    if tags is not None:
        for tag in tags:
            if isinstance(tag, str) and _has_forbidden_term(tag, terms):
                return True
    if metadata is not None:
        for key, value in metadata.items():
            if isinstance(key, str) and _has_forbidden_term(key, terms):
                return True
            if isinstance(value, str) and _has_forbidden_term(value, terms):
                return True
    return False


def _has_forbidden_term(text: str, forbidden_terms: frozenset[str]) -> bool:
    if not isinstance(text, str):
        return False
    lower = text.lower()
    return any(term in lower for term in forbidden_terms)


def build_release_hardening_safety_flags(
    *,
    has_blocked: bool = False,
    has_degraded: bool = False,
    has_forbidden_terms: bool = False,
    has_missing_safety_notices: bool = False,
) -> ReleaseHardeningSafetyFlags:
    """Build hardening safety flags with observed negative states."""
    return ReleaseHardeningSafetyFlags(
        has_blocked=has_blocked,
        has_degraded=has_degraded,
        has_forbidden_terms=has_forbidden_terms,
        has_missing_safety_notices=has_missing_safety_notices,
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def build_release_hardening_report(
    input: ReleaseHardeningInput,
    config: ReleaseHardeningConfig | None = None,
) -> ReleaseHardeningReport:
    """Build a deterministic release hardening audit report from in-memory declarations."""
    if config is None:
        config = input.config

    generated_at = _resolve_generated_at(input, config)

    if has_unsafe_release_hardening_content(metadata=dict(input.metadata)):
        return ReleaseHardeningReport.blocked(
            input=input,
            reason_code=ReleaseHardeningReasonCode.UNSAFE_CONTENT,
            generated_at=generated_at,
            notes=(
                "Hardening report blocked due to unsafe content in input metadata.",
                "Release hardening output is for human audit only and is not a "
                "trading signal, recommendation, or certification of trading readiness.",
            ),
        )

    validation_result = _validate_input(input, generated_at)
    if validation_result is not None:
        return validation_result

    checks = input.checks if input.checks else _build_default_checks()
    project_version = input.project_version

    results: list[ReleaseHardeningCheckResult] = []
    for check in checks:
        results.extend(_run_check(check, input, project_version=project_version))

    results = sorted(
        results,
        key=lambda r: (r.category, r.check_id, r.package_id or "", r.state.value, r.message),
    )

    data_quality = _build_data_quality(results, input)
    safety_flags = _build_safety_flags(results)
    report_state, report_level_code = _aggregate_report_state(results, config.strict)
    reason_codes = _aggregate_reason_codes(results, report_level_code)

    notes = (
        "Release hardening output is for human audit only.",
        "This is not a trading signal, recommendation, or certification of trading readiness.",
    )

    return ReleaseHardeningReport(
        state=report_state,
        reason_codes=reason_codes,
        checks=tuple(results),
        data_quality=data_quality,
        safety_flags=safety_flags,
        generated_at=generated_at,
        project_version=input.project_version,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Validation and resolution
# ---------------------------------------------------------------------------


def _resolve_generated_at(
    input: ReleaseHardeningInput, config: ReleaseHardeningConfig
) -> datetime:
    if input.generated_at is not None:
        return input.generated_at
    if getattr(config, "generated_at", None) is not None:
        return config.generated_at
    return datetime.now(timezone.utc)


def _validate_input(
    input: ReleaseHardeningInput, generated_at: datetime
) -> ReleaseHardeningReport | None:
    if not input.packages:
        return ReleaseHardeningReport.blocked(
            input=input,
            reason_code=ReleaseHardeningReasonCode.MISSING_REQUIRED_DECLARATION,
            generated_at=generated_at,
            notes=("Input validation failed: packages tuple is empty.",),
        )

    package_ids = [pkg.package_id for pkg in input.packages]
    if len(package_ids) != len(set(package_ids)):
        return ReleaseHardeningReport.blocked(
            input=input,
            reason_code=ReleaseHardeningReasonCode.DUPLICATE_PACKAGE_ID,
            generated_at=generated_at,
            notes=("Input validation failed: duplicate package_id detected.",),
        )

    if input.checks:
        check_ids = [check.check_id for check in input.checks]
        if len(check_ids) != len(set(check_ids)):
            return ReleaseHardeningReport.blocked(
                input=input,
                reason_code=ReleaseHardeningReasonCode.DUPLICATE_CHECK_ID,
                generated_at=generated_at,
                notes=("Input validation failed: duplicate check_id detected.",),
            )

    return None


# ---------------------------------------------------------------------------
# Default checks
# ---------------------------------------------------------------------------


_COMPLETED_PACKAGE_CATEGORIES: frozenset[str] = frozenset({
    ReleaseHardeningCheckCategory.ARTIFACT_PATH_POLICY.value,
})


def _build_default_checks() -> tuple[ReleaseHardeningCheck, ...]:
    return (
        ReleaseHardeningCheck(
            check_id="public_exports",
            category=ReleaseHardeningCheckCategory.PUBLIC_EXPORTS.value,
            description="Expected public exports are present in the package.",
            required=True,
            severity=ReleaseHardeningSeverity.BLOCKING,
            policy="expected_public_exports must be a subset of actual_public_exports.",
        ),
        ReleaseHardeningCheck(
            check_id="package_presence",
            category=ReleaseHardeningCheckCategory.PACKAGE_PRESENCE.value,
            description="Expected module files are present in the package.",
            required=True,
            severity=ReleaseHardeningSeverity.BLOCKING,
            policy="expected_modules must be a subset of actual_modules_present.",
        ),
        ReleaseHardeningCheck(
            check_id="writer_defaults",
            category=ReleaseHardeningCheckCategory.WRITER_DEFAULTS.value,
            description="Package defines local writer default paths.",
            required=True,
            severity=ReleaseHardeningSeverity.ADVISORY,
            policy="writer_default_paths must be non-empty and all paths local.",
        ),
        ReleaseHardeningCheck(
            check_id="safety_notices",
            category=ReleaseHardeningCheckCategory.SAFETY_NOTICES.value,
            description="Package includes explicit research-only safety notices.",
            required=True,
            severity=ReleaseHardeningSeverity.BLOCKING,
            policy="At least one safety notice must be present and contain no forbidden terms.",
        ),
        ReleaseHardeningCheck(
            check_id="markdown_disclaimer",
            category=ReleaseHardeningCheckCategory.MARKDOWN_DISCLAIMER_POLICY.value,
            description="Package includes a research-only Markdown disclaimer.",
            required=True,
            severity=ReleaseHardeningSeverity.BLOCKING,
            policy="markdown_disclaimer must be non-empty and contain research-only language.",
        ),
        ReleaseHardeningCheck(
            check_id="forbidden_terms",
            category=ReleaseHardeningCheckCategory.FORBIDDEN_TERM_POLICY.value,
            description="Safety notices and disclaimer contain no forbidden terms.",
            required=True,
            severity=ReleaseHardeningSeverity.BLOCKING,
            policy="safety_notices and markdown_disclaimer must not contain forbidden terms.",
        ),
        ReleaseHardeningCheck(
            check_id="version_consistency",
            category=ReleaseHardeningCheckCategory.VERSION_CONSISTENCY.value,
            description="Package version is consistent with the project version.",
            required=True,
            severity=ReleaseHardeningSeverity.BLOCKING,
            policy="Patch-level mismatch -> DEGRADED; major/minor mismatch -> BLOCKED.",
        ),
        ReleaseHardeningCheck(
            check_id="default_path_locality",
            category=ReleaseHardeningCheckCategory.DEFAULT_PATH_LOCALITY.value,
            description="All default paths are relative and local.",
            required=True,
            severity=ReleaseHardeningSeverity.BLOCKING,
            policy="writer_default_paths and test_default_paths must be relative local paths.",
        ),
        ReleaseHardeningCheck(
            check_id="test_artifact_isolation",
            category=ReleaseHardeningCheckCategory.TEST_ARTIFACT_ISOLATION.value,
            description="Test default paths are isolated from production defaults.",
            required=True,
            severity=ReleaseHardeningSeverity.ADVISORY,
            policy="test_default_paths must be under tests/ or tmp_path-style and not overlap with production defaults.",
        ),
        ReleaseHardeningCheck(
            check_id="artifact_path_policy",
            category=ReleaseHardeningCheckCategory.ARTIFACT_PATH_POLICY.value,
            description="Completed audit package artifact paths are local.",
            required=True,
            severity=ReleaseHardeningSeverity.BLOCKING,
            policy="completed package artifact_paths must be local and not reference external schemes.",
        ),
    )


# ---------------------------------------------------------------------------
# Check runner
# ---------------------------------------------------------------------------


def _run_check(
    check: ReleaseHardeningCheck,
    input: ReleaseHardeningInput,
    *,
    project_version: str | None = None,
) -> tuple[ReleaseHardeningCheckResult, ...]:
    if check.category in _COMPLETED_PACKAGE_CATEGORIES:
        if not input.completed_packages:
            return (
                ReleaseHardeningCheckResult(
                    check_id=check.check_id,
                    category=check.category,
                    package_id=None,
                    state=ReleaseHardeningState.NOT_APPLICABLE,
                    reason_code=ReleaseHardeningReasonCode.NOT_APPLICABLE,
                    message="No completed packages provided; check skipped.",
                    evidence=(),
                ),
            )
        return tuple(
            _check_artifact_path_policy(check, completed)
            for completed in input.completed_packages
        )

    return tuple(
        _run_package_check(check, package, project_version=project_version)
        for package in input.packages
    )


def _run_package_check(
    check: ReleaseHardeningCheck,
    package: PackageDeclaration,
    *,
    project_version: str | None = None,
) -> ReleaseHardeningCheckResult:
    category = check.category
    if category == ReleaseHardeningCheckCategory.PUBLIC_EXPORTS.value:
        return _check_public_exports(check, package)
    if category == ReleaseHardeningCheckCategory.PACKAGE_PRESENCE.value:
        return _check_package_presence(check, package)
    if category == ReleaseHardeningCheckCategory.WRITER_DEFAULTS.value:
        return _check_writer_defaults(check, package)
    if category == ReleaseHardeningCheckCategory.SAFETY_NOTICES.value:
        return _check_safety_notices(check, package)
    if category == ReleaseHardeningCheckCategory.MARKDOWN_DISCLAIMER_POLICY.value:
        return _check_markdown_disclaimer(check, package)
    if category == ReleaseHardeningCheckCategory.FORBIDDEN_TERM_POLICY.value:
        return _check_forbidden_term_policy(check, package)
    if category == ReleaseHardeningCheckCategory.VERSION_CONSISTENCY.value:
        return _check_version_consistency(check, package, project_version)
    if category == ReleaseHardeningCheckCategory.DEFAULT_PATH_LOCALITY.value:
        return _check_default_path_locality(check, package)
    if category == ReleaseHardeningCheckCategory.TEST_ARTIFACT_ISOLATION.value:
        return _check_test_artifact_isolation(check, package)

    return ReleaseHardeningCheckResult(
        check_id=check.check_id,
        category=category,
        package_id=package.package_id,
        state=ReleaseHardeningState.BLOCKED,
        reason_code=ReleaseHardeningReasonCode.UNSAFE_CONTENT,
        message=f"Unknown check category: {category}",
        evidence=(),
    )


# ---------------------------------------------------------------------------
# Individual check implementations
# ---------------------------------------------------------------------------


def _advisory_or_blocked_result(
    check: ReleaseHardeningCheck,
    package: PackageDeclaration | None,
    reason_code: ReleaseHardeningReasonCode,
    message: str,
    evidence: tuple[str, ...] = (),
) -> ReleaseHardeningCheckResult:
    state = (
        ReleaseHardeningState.BLOCKED
        if check.severity is ReleaseHardeningSeverity.BLOCKING
        else ReleaseHardeningState.DEGRADED
    )
    return ReleaseHardeningCheckResult(
        check_id=check.check_id,
        category=check.category,
        package_id=package.package_id if package else None,
        state=state,
        reason_code=reason_code,
        message=message,
        evidence=evidence,
    )


def _pass_result(
    check: ReleaseHardeningCheck, package: PackageDeclaration | None
) -> ReleaseHardeningCheckResult:
    return ReleaseHardeningCheckResult(
        check_id=check.check_id,
        category=check.category,
        package_id=package.package_id if package else None,
        state=ReleaseHardeningState.PASS,
        reason_code=ReleaseHardeningReasonCode.OK,
        message="Check passed.",
        evidence=(),
    )


def _empty_actual_result(
    check: ReleaseHardeningCheck,
    package: PackageDeclaration,
    reason_code: ReleaseHardeningReasonCode,
    message: str,
) -> ReleaseHardeningCheckResult:
    if check.severity is ReleaseHardeningSeverity.BLOCKING:
        return _advisory_or_blocked_result(check, package, reason_code, message)
    return ReleaseHardeningCheckResult(
        check_id=check.check_id,
        category=check.category,
        package_id=package.package_id,
        state=ReleaseHardeningState.NOT_APPLICABLE,
        reason_code=ReleaseHardeningReasonCode.NOT_APPLICABLE,
        message=message,
        evidence=(),
    )


def _check_public_exports(
    check: ReleaseHardeningCheck, package: PackageDeclaration
) -> ReleaseHardeningCheckResult:
    if not package.expected_public_exports and not package.actual_public_exports:
        return ReleaseHardeningCheckResult(
            check_id=check.check_id,
            category=check.category,
            package_id=package.package_id,
            state=ReleaseHardeningState.NOT_APPLICABLE,
            reason_code=ReleaseHardeningReasonCode.NOT_APPLICABLE,
            message="No public exports declared; check not applicable.",
            evidence=(),
        )
    if not package.actual_public_exports:
        return _empty_actual_result(
            check, package, ReleaseHardeningReasonCode.MISSING_PUBLIC_EXPORT,
            "actual_public_exports is empty; cannot verify public exports.",
        )
    missing = sorted(set(package.expected_public_exports) - set(package.actual_public_exports))
    if missing:
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.MISSING_PUBLIC_EXPORT,
            f"Missing public exports: {', '.join(missing)}",
            tuple(missing),
        )
    return _pass_result(check, package)


def _check_package_presence(
    check: ReleaseHardeningCheck, package: PackageDeclaration
) -> ReleaseHardeningCheckResult:
    if not package.actual_modules_present:
        return _empty_actual_result(
            check, package, ReleaseHardeningReasonCode.PACKAGE_NOT_PRESENT,
            "actual_modules_present is empty; cannot verify package presence.",
        )
    missing = sorted(set(package.expected_modules) - set(package.actual_modules_present))
    if missing:
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.PACKAGE_NOT_PRESENT,
            f"Missing expected modules: {', '.join(missing)}",
            tuple(missing),
        )
    return _pass_result(check, package)


def _check_writer_defaults(
    check: ReleaseHardeningCheck, package: PackageDeclaration
) -> ReleaseHardeningCheckResult:
    if not package.writer_default_paths:
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.MISSING_WRITER_DEFAULT,
            "writer_default_paths is empty.",
        )
    bad = [p for p in package.writer_default_paths if not _is_local_path(p)]
    if bad:
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.DEFAULT_PATH_NOT_LOCAL,
            f"Non-local writer default paths: {', '.join(bad)}",
            tuple(bad),
        )
    return _pass_result(check, package)


def _check_safety_notices(
    check: ReleaseHardeningCheck, package: PackageDeclaration
) -> ReleaseHardeningCheckResult:
    if not package.safety_notices:
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.MISSING_SAFETY_NOTICE,
            "safety_notices is empty.",
        )
    for notice in package.safety_notices:
        if _has_forbidden_term(notice, FORBIDDEN_RELEASE_HARDENING_TERMS):
            return _advisory_or_blocked_result(
                check, package, ReleaseHardeningReasonCode.FORBIDDEN_TERM_PRESENT,
                f"Safety notice contains forbidden term: {notice!r}",
                (notice,),
            )
    return _pass_result(check, package)


def _check_markdown_disclaimer(
    check: ReleaseHardeningCheck, package: PackageDeclaration
) -> ReleaseHardeningCheckResult:
    if not package.markdown_disclaimer:
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.MISSING_MARKDOWN_DISCLAIMER,
            "markdown_disclaimer is empty.",
        )
    if _has_forbidden_term(package.markdown_disclaimer, FORBIDDEN_RELEASE_HARDENING_TERMS):
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.FORBIDDEN_TERM_PRESENT,
            "Markdown disclaimer contains forbidden term.",
        )
    lower = package.markdown_disclaimer.lower()
    if not (
        "research-only" in lower
        or "research only" in lower
        or "not trading advice" in lower
        or "not a trading signal" in lower
        or "not trading readiness" in lower
    ):
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.MISSING_MARKDOWN_DISCLAIMER,
            "Markdown disclaimer lacks research-only language.",
        )
    return _pass_result(check, package)


def _check_forbidden_term_policy(
    check: ReleaseHardeningCheck, package: PackageDeclaration
) -> ReleaseHardeningCheckResult:
    for text in list(package.safety_notices) + [package.markdown_disclaimer]:
        if text and _has_forbidden_term(text, FORBIDDEN_RELEASE_HARDENING_TERMS):
            return _advisory_or_blocked_result(
                check, package, ReleaseHardeningReasonCode.FORBIDDEN_TERM_PRESENT,
                f"Forbidden term present in: {text!r}",
                (text,),
            )
    return _pass_result(check, package)


def _check_version_consistency(
    check: ReleaseHardeningCheck,
    package: PackageDeclaration,
    project_version: str | None,
) -> ReleaseHardeningCheckResult:
    if package.version is None or project_version is None:
        return ReleaseHardeningCheckResult(
            check_id=check.check_id,
            category=check.category,
            package_id=package.package_id,
            state=ReleaseHardeningState.NOT_APPLICABLE,
            reason_code=ReleaseHardeningReasonCode.NOT_APPLICABLE,
            message="Package or project version not provided; version consistency check skipped.",
            evidence=(),
        )

    parsed_pkg = _parse_version(package.version)
    parsed_proj = _parse_version(project_version)
    if parsed_pkg is None or parsed_proj is None:
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.VERSION_INCONSISTENT,
            f"Unparseable version: package={package.version!r}, project={project_version!r}",
        )

    major_p, minor_p, patch_p = parsed_pkg
    major_j, minor_j, patch_j = parsed_proj
    if major_p != major_j or minor_p != minor_j:
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.VERSION_INCONSISTENT,
            f"Major/minor version mismatch: package {package.version} vs project {project_version}",
        )
    if patch_p != patch_j:
        return ReleaseHardeningCheckResult(
            check_id=check.check_id,
            category=check.category,
            package_id=package.package_id,
            state=ReleaseHardeningState.DEGRADED,
            reason_code=ReleaseHardeningReasonCode.VERSION_INCONSISTENT,
            message=f"Patch-level version mismatch: package {package.version} vs project {project_version}",
            evidence=(),
        )
    return _pass_result(check, package)


def _check_default_path_locality(
    check: ReleaseHardeningCheck, package: PackageDeclaration
) -> ReleaseHardeningCheckResult:
    all_paths = list(package.writer_default_paths) + list(package.test_default_paths)
    if not all_paths:
        return _pass_result(check, package)
    bad = [p for p in all_paths if not _is_local_path(p)]
    if bad:
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.DEFAULT_PATH_NOT_LOCAL,
            f"Non-local default paths: {', '.join(bad)}",
            tuple(bad),
        )
    return _pass_result(check, package)


def _check_test_artifact_isolation(
    check: ReleaseHardeningCheck, package: PackageDeclaration
) -> ReleaseHardeningCheckResult:
    if not package.test_default_paths:
        return _empty_actual_result(
            check, package, ReleaseHardeningReasonCode.TEST_ARTIFACT_NOT_ISOLATED,
            "test_default_paths is empty; cannot verify test artifact isolation.",
        )

    bad: list[str] = []
    prod_paths = {p.lower() for p in package.writer_default_paths}
    for p in package.test_default_paths:
        lower = p.lower()
        is_isolated = (
            lower.startswith("tests/")
            or "tmp_path" in lower
            or lower.startswith("tmp/")
            or "/tmp/" in lower
        )
        overlaps = lower in prod_paths or any(lower == pp for pp in prod_paths)
        if not is_isolated or overlaps:
            bad.append(p)
    if bad:
        return _advisory_or_blocked_result(
            check, package, ReleaseHardeningReasonCode.TEST_ARTIFACT_NOT_ISOLATED,
            f"Test paths not isolated: {', '.join(bad)}",
            tuple(bad),
        )
    return _pass_result(check, package)


def _check_artifact_path_policy(
    check: ReleaseHardeningCheck, completed: CompletedAuditPackage
) -> ReleaseHardeningCheckResult:
    if not completed.artifact_paths:
        return ReleaseHardeningCheckResult(
            check_id=check.check_id,
            category=check.category,
            package_id=completed.package_id,
            state=ReleaseHardeningState.NOT_APPLICABLE,
            reason_code=ReleaseHardeningReasonCode.NOT_APPLICABLE,
            message="artifact_paths is empty; check skipped.",
            evidence=(),
        )
    bad = [p for p in completed.artifact_paths if not _is_local_path(p)]
    if bad:
        return ReleaseHardeningCheckResult(
            check_id=check.check_id,
            category=check.category,
            package_id=completed.package_id,
            state=ReleaseHardeningState.BLOCKED,
            reason_code=ReleaseHardeningReasonCode.ARTIFACT_PATH_NOT_LOCAL,
            message=f"Non-local artifact paths: {', '.join(bad)}",
            evidence=tuple(bad),
        )
    return ReleaseHardeningCheckResult(
        check_id=check.check_id,
        category=check.category,
        package_id=completed.package_id,
        state=ReleaseHardeningState.PASS,
        reason_code=ReleaseHardeningReasonCode.OK,
        message="Artifact paths are local.",
        evidence=(),
    )


# ---------------------------------------------------------------------------
# Path and version utilities
# ---------------------------------------------------------------------------


def _is_local_path(path: str) -> bool:
    """Return True if path is a relative local path without external schemes or traversal.

    Paths are treated as opaque strings; no filesystem access is performed.
    """
    if not isinstance(path, str) or not path:
        return False
    if path.startswith("/") or path.startswith("\\") or path.startswith("."):
        return False
    if "://" in path or path.startswith("http") or path.startswith("ws"):
        return False
    if ".." in path or "~" in path:
        return False
    if any(path.startswith(prefix) for prefix in ("data/", "reports/", "tests/", "tmp/")):
        return True
    return "/" in path or "\\" in path


def _parse_version(version: str) -> tuple[int, int, int] | None:
    """Parse a simple major.minor.patch version string.

    Pre-release/build suffixes such as `-dev`, `-alpha`, `+build123` are
    stripped before parsing. The comparison only uses major, minor, and patch.
    """
    if not isinstance(version, str) or not version:
        return None
    core = version.lstrip("v")
    for sep in ("-", "+"):
        if sep in core:
            core = core.split(sep, 1)[0]
    parts = core.split(".")
    if len(parts) < 2:
        return None
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    return (major, minor, patch)


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _build_data_quality(
    results: list[ReleaseHardeningCheckResult], input: ReleaseHardeningInput
) -> ReleaseHardeningDataQuality:
    total = len(results)
    pass_count = sum(1 for r in results if r.state is ReleaseHardeningState.PASS)
    degraded_count = sum(1 for r in results if r.state is ReleaseHardeningState.DEGRADED)
    blocked_count = sum(1 for r in results if r.state is ReleaseHardeningState.BLOCKED)
    not_applicable_count = sum(
        1 for r in results if r.state is ReleaseHardeningState.NOT_APPLICABLE
    )
    return ReleaseHardeningDataQuality(
        total_checks=total,
        pass_count=pass_count,
        degraded_count=degraded_count,
        blocked_count=blocked_count,
        not_applicable_count=not_applicable_count,
        package_count=len(input.packages),
        completed_package_count=len(input.completed_packages),
        notes=(
            "Data quality summary counts check results by state.",
            "All values are derived from caller-provided in-memory declarations.",
        ),
    )


def _build_safety_flags(
    results: list[ReleaseHardeningCheckResult],
) -> ReleaseHardeningSafetyFlags:
    has_blocked = any(r.state is ReleaseHardeningState.BLOCKED for r in results)
    has_degraded = any(r.state is ReleaseHardeningState.DEGRADED for r in results)
    has_forbidden_terms = any(
        r.reason_code is ReleaseHardeningReasonCode.FORBIDDEN_TERM_PRESENT for r in results
    )
    has_missing_safety_notices = any(
        r.reason_code is ReleaseHardeningReasonCode.MISSING_SAFETY_NOTICE for r in results
    )
    return ReleaseHardeningSafetyFlags(
        has_blocked=has_blocked,
        has_degraded=has_degraded,
        has_forbidden_terms=has_forbidden_terms,
        has_missing_safety_notices=has_missing_safety_notices,
    )


def _aggregate_report_state(
    results: list[ReleaseHardeningCheckResult], strict: bool
) -> tuple[ReleaseHardeningState, ReleaseHardeningReasonCode]:
    has_blocked = any(r.state is ReleaseHardeningState.BLOCKED for r in results)
    has_degraded = any(r.state is ReleaseHardeningState.DEGRADED for r in results)

    if has_blocked or (strict and has_degraded):
        return (ReleaseHardeningState.BLOCKED, ReleaseHardeningReasonCode.SAFETY_BLOCKED)
    if has_degraded:
        return (ReleaseHardeningState.DEGRADED, ReleaseHardeningReasonCode.CONSISTENCY_DEGRADED)
    return (ReleaseHardeningState.PASS, ReleaseHardeningReasonCode.OK)


def _aggregate_reason_codes(
    results: list[ReleaseHardeningCheckResult],
    report_level_code: ReleaseHardeningReasonCode,
) -> tuple[ReleaseHardeningReasonCode, ...]:
    codes: list[ReleaseHardeningReasonCode] = [report_level_code]
    for r in results:
        if r.reason_code not in codes:
            codes.append(r.reason_code)
    for safety in (
        ReleaseHardeningReasonCode.RESEARCH_ONLY,
        ReleaseHardeningReasonCode.NOT_TRADING_ADVICE,
        ReleaseHardeningReasonCode.HUMAN_RESEARCH_ONLY,
        ReleaseHardeningReasonCode.NO_FILE_INGESTION,
        ReleaseHardeningReasonCode.NO_NETWORK_CONNECTION,
        ReleaseHardeningReasonCode.NO_EXCHANGE_CONNECTION,
        ReleaseHardeningReasonCode.NO_FREQTRADE_INPUT,
        ReleaseHardeningReasonCode.NO_SCHEDULER,
        ReleaseHardeningReasonCode.NO_DAEMON,
        ReleaseHardeningReasonCode.NO_WEB_UI,
        ReleaseHardeningReasonCode.NO_DATABASE,
        ReleaseHardeningReasonCode.NO_ACTION_COMMANDS_EMITTED,
    ):
        if safety not in codes:
            codes.append(safety)
    return tuple(codes)


