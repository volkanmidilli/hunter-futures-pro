"""Fixture-root validation, path containment, symlink safety, and bounded SHA-256
verification for external fixtures (Phase B.1 / SPEC-073).

Stage 4 — Root + path containment + symlink safety.
Stage 5 — Bounded SHA-256 hash verification per declared file.

See: docs/research/external_fixture_contract.md
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from hunter.research_backtest_comparison.fixture_models import (
    FIXTURE_FILE_ESCAPE,
    FIXTURE_FILE_MISSING,
    FIXTURE_FILE_NOT_REGULAR,
    FIXTURE_FILE_SYMLINK,
    FIXTURE_HASH_INVALID,
    FIXTURE_HASH_MISMATCH,
    FIXTURE_ROOT_FORBIDDEN,
    FIXTURE_ROOT_NOT_DIRECTORY,
    FIXTURE_ROOT_REQUIRED,
    FIXTURE_UNDECLARED_FILE,
    ExternalFixtureManifest,
    FixtureFileRecord,
    FixtureValidationResult,
)

# Maximum bytes to read per fixture file (Stage 5 bounded read).
# Refusing to hash extremely large files protects memory/disk.
_MAX_FIXTURE_FILE_BYTES: int = 256 * 1024 * 1024  # 256 MiB

# Repository directories that the fixture root must NOT reside within.
_FORBIDDEN_PARENTS: tuple[str, ...] = ("data", "reports")


def _repo_root() -> Path:
    """Return the absolute repository root (two levels above this file)."""
    return Path(__file__).resolve().parents[3]


def _is_inside(parent: Path, child: Path) -> bool:
    """Return True if *child* is inside *parent* (non-recursive container)."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_fixture_root(
    fixture_root: str | Path | None,
) -> tuple[Path | None, tuple[str, ...]]:
    """Validate the external fixture root directory.

    Returns (resolved_path, reason_codes).  When validation fails, the
    first element is ``None`` and the second element contains one or more
    structured reason codes.

    Args:
        fixture_root: Absolute or relative path to the fixture directory.
            Must not be ``None``, must not point inside the repository
            ``data/`` or ``reports/`` directories, and must exist as a
            real directory.

    Returns:
        Tuple of (resolved absolute Path or None, reason code tuple).
    """
    reason_codes: list[str] = []

    if fixture_root is None:
        reason_codes.append(FIXTURE_ROOT_REQUIRED)
        return None, tuple(reason_codes)

    path = Path(fixture_root)

    # Reject empty string paths.
    if str(fixture_root).strip() == "":
        reason_codes.append(FIXTURE_ROOT_REQUIRED)
        return None, tuple(reason_codes)

    # Resolve to absolute.
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        reason_codes.append(FIXTURE_ROOT_NOT_DIRECTORY)
        return None, tuple(reason_codes)

    # Reject fixture root inside repository data/ or reports/.
    repo = _repo_root()
    for forbidden in _FORBIDDEN_PARENTS:
        forbidden_path = repo / forbidden
        if _is_inside(forbidden_path, resolved):
            reason_codes.append(FIXTURE_ROOT_FORBIDDEN)
            return None, tuple(reason_codes)

    # Must exist and be a directory.
    if not resolved.exists():
        reason_codes.append(FIXTURE_ROOT_NOT_DIRECTORY)
        return None, tuple(reason_codes)

    if not resolved.is_dir():
        reason_codes.append(FIXTURE_ROOT_NOT_DIRECTORY)
        return None, tuple(reason_codes)

    return resolved, tuple(reason_codes)


def validate_file_containment(
    fixture_root: Path,
    file_record: FixtureFileRecord,
) -> tuple[Path | None, tuple[str, ...]]:
    """Validate that a declared fixture file is safely contained within the fixture root.

    Checks:
    - Path resolution (OS-level errors)
    - Path traversal / escape (resolved path must be under fixture_root)
    - Existence
    - Regular-file type
    - Symlink (symlinks are rejected)

    Args:
        fixture_root: Already-validated absolute fixture root path.
        file_record: Declared file record from the manifest.

    Returns:
        Tuple of (resolved absolute Path or None, reason code tuple).
        When the path is invalid the first element is ``None``.
    """
    reason_codes: list[str] = []
    relative = file_record.relative_path

    # Build the absolute path by joining the validated root.
    # Note: FixtureFileRecord.__post_init__ already rejects absolute
    # paths and ".." components, so `relative` is guaranteed to be a
    # safe relative path at this point.  However, we still validate
    # the resolved path to defend against symlink escapes.
    candidate = fixture_root / relative

    # ---- Symlink check (pre-resolve) ----
    # Check BEFORE resolve() because resolve() follows symlinks and
    # returns the target path, which hides the symlink fact.
    if candidate.is_symlink():
        reason_codes.append(FIXTURE_FILE_SYMLINK)
        return None, tuple(reason_codes)

    # ---- Existence check (pre-resolve) ----
    # Also check existence before resolve() so we can distinguish
    # "missing file" from "symlink" errors.
    if not candidate.exists():
        reason_codes.append(FIXTURE_FILE_MISSING)
        return None, tuple(reason_codes)

    # Resolve the actual filesystem path (follows directory-symlink
    # components to detect intermediate symlink escapes).
    try:
        real_path = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        reason_codes.append(FIXTURE_FILE_MISSING)
        return None, tuple(reason_codes)

    # ---- Escape check ----
    # The real path (after resolving any intermediate symlink components)
    # must still be under the fixture root.  This catches intermediate
    # directory symlinks that redirect outside the root.
    if not _is_inside(fixture_root, real_path):
        reason_codes.append(FIXTURE_FILE_ESCAPE)
        return None, tuple(reason_codes)

    # ---- Regular-file check ----
    if not real_path.is_file():
        reason_codes.append(FIXTURE_FILE_NOT_REGULAR)
        return None, tuple(reason_codes)

    return real_path, tuple(reason_codes)


def validate_fixture_containment(
    fixture_root: str | Path | None,
    manifest: ExternalFixtureManifest,
) -> tuple[Path | None, dict[str, Path], tuple[str, ...]]:
    """Validate fixture root + path containment for every declared file.

    This is the public entry point for Stage 4: root validation and
    path-containment safety.  It does **not** hash file contents.

    Args:
        fixture_root: Absolute or relative path to the fixture directory.
        manifest: Validated ExternalFixtureManifest.

    Returns:
        A 3-tuple of (resolved root Path or None, dict mapping relative_path
        → resolved absolute Path, reason codes in insertion order).  When
        the root is invalid the first element is ``None`` and the dict is
        empty.
    """
    # Step 1 — Validate the root.
    resolved_root, root_reasons = validate_fixture_root(fixture_root)
    if resolved_root is None:
        return None, {}, root_reasons

    # Step 2 — Validate every declared file.
    resolved_paths: dict[str, Path] = {}
    all_reasons: list[str] = list(root_reasons)

    for record in manifest.files:
        resolved_file, file_reasons = validate_file_containment(resolved_root, record)
        if resolved_file is None:
            all_reasons.extend(file_reasons)
        else:
            resolved_paths[record.relative_path] = resolved_file

    return resolved_root, resolved_paths, tuple(all_reasons)


# ---------------------------------------------------------------------------
# Stage 5 — Bounded SHA-256 hash verification
# ---------------------------------------------------------------------------


_CHUNK_SIZE: int = 65536  # 64 KiB read chunks


def _hash_file_bytes(path: Path, max_bytes: int = _MAX_FIXTURE_FILE_BYTES) -> str:
    """Compute the lowercase hexadecimal SHA-256 digest of a file's content.

    Reads the file in bounded 64 KiB chunks up to *max_bytes*.  If the file
    exceeds *max_bytes* a :exc:`ValueError` is raised.

    Args:
        path: Resolved absolute path to a regular file.
        max_bytes: Maximum bytes to read before refusing.

    Returns:
        Lowercase 64-character hexadecimal SHA-256 digest.

    Raises:
        ValueError: If the file exceeds *max_bytes*.
    """
    sha = hashlib.sha256()
    total: int = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(
                    f"File exceeds maximum size: {path} ({total} > {max_bytes} bytes)"
                )
            sha.update(chunk)
    return sha.hexdigest()


def verify_file_hash(
    path: Path,
    declared_sha256: str,
) -> tuple[str | None, tuple[str, ...]]:
    """Verify the SHA-256 hash of a single fixture file.

    Args:
        path: Resolved absolute path to a regular file (must already pass
            containment validation).
        declared_sha256: Lowercase 64-character SHA-256 from the manifest.

    Returns:
        A 2-tuple of (computed lowercase hex digest or None, reason codes).
        On success the first element is the computed digest and the second
        is an empty tuple.  On failure the first element is ``None``.
    """
    try:
        computed = _hash_file_bytes(path)
    except (OSError, ValueError) as exc:
        return (
            None,
            (FIXTURE_HASH_INVALID,),
        )

    if computed != declared_sha256:
        return (
            None,
            (FIXTURE_HASH_MISMATCH,),
        )

    return computed, ()


def validate_fixture_hashes(
    resolved_root: Path,
    manifest: ExternalFixtureManifest,
    resolved_paths: dict[str, Path],
) -> tuple[dict[str, str], tuple[str, ...]]:
    """Verify SHA-256 hashes for every file that passed containment validation.

    Files that failed containment are NOT hashed — their absence from
    *resolved_paths* means they are silently skipped.

    Args:
        resolved_root: Already-validated absolute fixture root path.
        manifest: Validated ExternalFixtureManifest.
        resolved_paths: Dict mapping ``relative_path`` → absolute ``Path``
            from :func:`validate_fixture_containment`.

    Returns:
        A 2-tuple of (dict mapping ``relative_path`` → computed hex digest,
        reason codes for hash failures in insertion order).
    """
    computed_hashes: dict[str, str] = {}
    all_reasons: list[str] = []

    # Build an index of file records by relative_path for O(1) lookup.
    record_by_path: dict[str, FixtureFileRecord] = {
        r.relative_path: r for r in manifest.files
    }

    for rel_path, abs_path in sorted(resolved_paths.items()):
        record = record_by_path.get(rel_path)
        if record is None:
            # Should not happen: resolved paths are derived from manifest
            # files.  Fail closed if it does.
            all_reasons.append(FIXTURE_HASH_INVALID)
            continue

        computed, reasons = verify_file_hash(abs_path, record.sha256)
        if computed is not None:
            computed_hashes[rel_path] = computed
        else:
            all_reasons.extend(reasons)

    return computed_hashes, tuple(all_reasons)


# ---------------------------------------------------------------------------
# Stage 6 — Strict / non-strict undeclared-file policy
# ---------------------------------------------------------------------------


def check_undeclared_files(
    fixture_root: Path,
    manifest: ExternalFixtureManifest,
    *,
    strict: bool = True,
) -> tuple[str, ...]:
    """Detect undeclared files in the fixture root directory.

    In **strict** mode, any regular file found under *fixture_root* that is
    NOT declared in the manifest is a violation, emitting
    ``FIXTURE_UNDECLARED_FILE`` for each offending path.

    In **non-strict** mode, extra files are silently ignored.

    Only regular files are checked — directories, symlinks, and special
    files are skipped.  The scan is shallow-one-level: only immediate children
    of the fixture root and their recursive descendants are enumerated via
    :meth:`Path.rglob`.

    Args:
        fixture_root: Already-validated absolute fixture root path.
        manifest: Validated ExternalFixtureManifest.
        strict: If True (default), undeclared files are violations.

    Returns:
        Tuple of reason codes (empty when non-strict or no violations).
    """
    if not strict:
        return ()

    declared: frozenset[str] = frozenset(r.relative_path for r in manifest.files)
    reasons: list[str] = []

    try:
        for entry in fixture_root.rglob("*"):
            # Skip directories and special files.
            if not entry.is_file():
                continue
            # Skip symlinks (already caught by Stage 4).
            if entry.is_symlink():
                continue
            # Compute relative path.
            try:
                rel = entry.relative_to(fixture_root).as_posix()
            except ValueError:
                continue
            if rel not in declared:
                reasons.append(FIXTURE_UNDECLARED_FILE)
    except OSError:
        # Filesystem error during enumeration → fail closed.
        reasons.append(FIXTURE_UNDECLARED_FILE)

    return tuple(reasons)


# ---------------------------------------------------------------------------
# Stage 5+6 combined validation → FixtureValidationResult
# ---------------------------------------------------------------------------


def compute_fixture_fingerprint(manifest: ExternalFixtureManifest) -> str:
    """Compute the deterministic SHA-256 fingerprint of a fixture manifest.

    Uses :meth:`ExternalFixtureManifest.canonical_fingerprint_payload` to
    produce a deterministic JSON payload, then hashes it with SHA-256.

    The payload excludes runtime-only fields (absolute paths, timestamps,
    PID, hostname, mtime, inode) and is deterministically sorted so that
    different input orderings produce identical fingerprints.

    Args:
        manifest: Validated ExternalFixtureManifest.

    Returns:
        Lowercase 64-character hexadecimal SHA-256 digest of the canonical
        serialised manifest payload.
    """
    import json

    payload = manifest.canonical_fingerprint_payload()
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=None)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Stage 4+5+6+7 combined validation → FixtureValidationResult
# ---------------------------------------------------------------------------


def validate_external_fixture(
    fixture_root: str | Path | None,
    manifest: ExternalFixtureManifest,
    *,
    fixture_fingerprint: str = "",
    strict: bool = True,
) -> FixtureValidationResult:
    """Run the full external fixture validation pipeline (Stages 4, 5, 6).

    Validates:
    1. Fixture root (existence, directory, not under data/ or reports/)
    2. Per-file path containment and symlink safety
    3. Per-file bounded SHA-256 hash verification
    4. Undeclared-file policy (strict / non-strict)

    Args:
        fixture_root: Absolute or relative path to the fixture directory.
        manifest: Validated ExternalFixtureManifest.
        fixture_fingerprint: Optional deterministic fingerprint of the
            canonical manifest payload (Stage 7).  An empty string is
            used when fingerprinting has not yet been performed.
        strict: If True (default), undeclared files in the fixture root
            are violations.  If False, extra files are silently ignored.

    Returns:
        An immutable :class:`FixtureValidationResult` with the complete
        validation outcome.
    """
    # Stage 4 — Root + path containment.
    root, paths, reasons = validate_fixture_containment(fixture_root, manifest)
    all_reasons: list[str] = list(reasons)

    if root is None:
        return FixtureValidationResult(
            valid=False,
            fixture_fingerprint=fixture_fingerprint,
            validated_file_count=0,
            declared_file_count=len(manifest.files),
            validated_relative_paths=(),
            reason_codes=tuple(all_reasons),
            safety_invariants={"research_only": True},
        )

    # Stage 5 — Hash verification for contained files.
    computed, hash_reasons = validate_fixture_hashes(root, manifest, paths)
    all_reasons.extend(hash_reasons)

    # Stage 6 — Undeclared-file policy (strict / non-strict).
    undeclared_reasons = check_undeclared_files(root, manifest, strict=strict)
    all_reasons.extend(undeclared_reasons)

    # Collect paths that passed both containment AND hash verification.
    validated_paths: tuple[str, ...] = tuple(
        sorted(p for p in paths if p in computed)
    )

    valid = len(all_reasons) == 0

    return FixtureValidationResult(
        valid=valid,
        fixture_fingerprint=fixture_fingerprint,
        validated_file_count=len(validated_paths),
        declared_file_count=len(manifest.files),
        validated_relative_paths=validated_paths,
        reason_codes=tuple(all_reasons),
        safety_invariants={"research_only": True},
    )
