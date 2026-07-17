"""Freqtrade executable validation for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonExecutableError,
)
from hunter.research_backtest_comparison.models import (
    INVALID_EXECUTABLE,
    NONZERO_EXIT,
    TIMEOUT,
    FreqtradeExecutableInfo,
)

# Minimal environment allowlist for the --version probe.
_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "TZ",
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "LC_ALL",
        "PYTHONNOUSERSITE",
        "PYTHONPATH",
    }
)


def _build_allowlisted_env(
    extra: dict[str, str] | None = None,
    allowlist: frozenset[str] | None = None,
) -> dict[str, str]:
    """Return an environment dict containing only allowed variables.

    Secrets such as API keys are stripped. TZ is forced to UTC.
    """
    allowlist = allowlist or _ENV_ALLOWLIST
    source = dict(extra or {})
    filtered: dict[str, str] = {}
    for key, value in source.items():
        if key in allowlist:
            filtered[key] = value
    # Always force UTC for reproducibility.
    filtered["TZ"] = "UTC"
    return filtered


def validate_executable(
    path: str | Path,
    *,
    timeout_seconds: int = 60,
    env_allowlist: frozenset[str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> FreqtradeExecutableInfo:
    """Validate a Freqtrade executable by running ``<freqtrade> --version``.

    Args:
        path: Absolute path to the Freqtrade executable.
        timeout_seconds: Timeout for the version probe.
        env_allowlist: Optional override of allowed environment variables.
        extra_env: Optional extra environment variables to include.

    Returns:
        FreqtradeExecutableInfo with version and validity status.

    Raises:
        ResearchBacktestComparisonExecutableError: on validation failure.
    """
    executable_path = Path(path)

    if not executable_path.is_absolute():
        return FreqtradeExecutableInfo(
            path=executable_path,
            version="",
            is_valid=False,
            reason_codes=(INVALID_EXECUTABLE,),
            metadata={"error": "executable_path must be absolute"},
        )

    if not executable_path.exists() or not executable_path.is_file():
        return FreqtradeExecutableInfo(
            path=executable_path,
            version="",
            is_valid=False,
            reason_codes=(INVALID_EXECUTABLE,),
            metadata={"error": "executable_path is not a regular file"},
        )

    env = _build_allowlisted_env(extra_env, env_allowlist)
    command: list[str] = [str(executable_path), "--version"]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout_seconds,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return FreqtradeExecutableInfo(
            path=executable_path,
            version="",
            is_valid=False,
            reason_codes=(TIMEOUT,),
            metadata={"error": f"--version timed out after {timeout_seconds}s", "exception": str(exc)},
        )
    except OSError as exc:
        return FreqtradeExecutableInfo(
            path=executable_path,
            version="",
            is_valid=False,
            reason_codes=(INVALID_EXECUTABLE,),
            metadata={"error": f"failed to execute --version: {exc}", "exception": str(exc)},
        )

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if result.returncode != 0:
        return FreqtradeExecutableInfo(
            path=executable_path,
            version="",
            is_valid=False,
            reason_codes=(NONZERO_EXIT,),
            metadata={
                "error": "--version returned non-zero exit",
                "exit_code": result.returncode,
                "stderr": stderr,
            },
        )

    version = stdout if stdout else stderr
    return FreqtradeExecutableInfo(
        path=executable_path,
        version=version,
        is_valid=True,
        reason_codes=(),
        metadata={"exit_code": result.returncode},
    )


def verify_executable_supports_backtesting(
    executable_info: FreqtradeExecutableInfo,
) -> None:
    """Verify that the executable has been validated.

    Raises:
        ResearchBacktestComparisonExecutableError: if not valid.
    """
    if not executable_info.is_valid:
        raise ResearchBacktestComparisonExecutableError(
            f"Freqtrade executable is not valid: {executable_info.path}"
        )
