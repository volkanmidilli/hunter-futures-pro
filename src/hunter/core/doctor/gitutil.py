"""Read-only Git subprocess wrapper for SPEC-077.

All Git interaction in the doctor/update framework goes through
:class:`GitRunner`, which enforces an allowlist of read-only subcommands,
never uses a shell, applies a hard timeout, and converts every failure
mode into a :class:`GitResult` instead of an exception.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from hunter.core.doctor.errors import DoctorError

#: Read-only git subcommands permitted in the doctor/update framework.
ALLOWED_SUBCOMMANDS: frozenset[str] = frozenset(
    {"rev-parse", "status", "branch", "config", "tag", "ls-remote"}
)

#: Subcommands that are inherently read-only regardless of arguments.
_SAFE_SUBCOMMANDS: frozenset[str] = frozenset({"rev-parse", "status", "ls-remote"})


def _is_read_only_invocation(args: tuple[str, ...]) -> bool:
    """Return True only for provably read-only git invocations.

    ``rev-parse``, ``status``, and ``ls-remote`` are read-only with any
    arguments.  ``branch``, ``tag``, and ``config`` also have mutating
    forms, so they are permitted only in their read-only flag forms.
    """
    subcommand, rest = args[0], args[1:]
    if subcommand in _SAFE_SUBCOMMANDS:
        return True
    if subcommand == "branch":
        return "--show-current" in rest or "--list" in rest
    if subcommand == "tag":
        return "--list" in rest or "-l" in rest
    if subcommand == "config":
        return bool(rest) and rest[0] in ("--get", "--list", "-l")
    return False

DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class GitResult:
    """Outcome of a read-only git invocation.

    ``ok`` is True only when the command ran and exited with code 0.
    ``error`` carries infrastructure failures (timeout, missing binary,
    disallowed subcommand); ``stderr`` carries process-level diagnostics.
    """

    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    error: str | None = None


#: Transport signature: (argv, cwd, timeout) -> GitResult.
Transport = Callable[[Sequence[str], Path, float], GitResult]


def _subprocess_transport(argv: Sequence[str], cwd: Path, timeout: float) -> GitResult:
    """Default transport using ``subprocess.run`` with ``shell=False``."""
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return GitResult(ok=False, error="git binary not found")
    except subprocess.TimeoutExpired:
        return GitResult(ok=False, error=f"git command timed out after {timeout:.0f}s")
    except OSError as exc:
        return GitResult(ok=False, error=f"git invocation failed: {exc}")
    return GitResult(
        ok=completed.returncode == 0,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        returncode=completed.returncode,
    )


class GitRunner:
    """Runs allowlisted read-only git commands.

    The transport is constructor-injected so tests can supply a fake;
    no global mutable state is used.
    """

    def __init__(
        self,
        cwd: Path,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: Transport | None = None,
    ) -> None:
        self._cwd = Path(cwd)
        self._timeout = timeout
        self._transport = transport or _subprocess_transport

    @property
    def cwd(self) -> Path:
        return self._cwd

    def run(self, *args: str) -> GitResult:
        """Run ``git <args...>`` after allowlist validation.

        Raises:
            DoctorError: If the subcommand is not on the read-only
                allowlist.  This is a programming error, not an
                environmental condition.

        Returns:
            A :class:`GitResult`; environmental failures are reported,
            never raised.
        """
        if not args:
            raise DoctorError("git invocation requires a subcommand")
        subcommand = args[0]
        if subcommand not in ALLOWED_SUBCOMMANDS:
            raise DoctorError(
                f"git subcommand {subcommand!r} is not on the read-only allowlist"
            )
        if not _is_read_only_invocation(tuple(args)):
            raise DoctorError(
                f"git {subcommand} is only permitted in its read-only flag form"
            )
        return self._transport(("git", *args), self._cwd, self._timeout)
