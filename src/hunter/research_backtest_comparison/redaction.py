"""Redaction utilities for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

import re
from pathlib import Path


def _redact_secret_match(m: re.Match[str]) -> str:
    """Redact a secret match while preserving the key and its separator.

    Handles both ``key=value`` and ``key: value`` forms, including optional
    whitespace around the separator. The value is always replaced with a
    deterministic redaction token.
    """
    full = m.group(0)
    colon_pos = full.find(":")
    equal_pos = full.find("=")
    if colon_pos >= 0 and (equal_pos < 0 or colon_pos < equal_pos):
        key = full[:colon_pos].rstrip()
        return f"{key}:[REDACTED]"
    key = full[:equal_pos].rstrip()
    return f"{key}=[REDACTED]"


# Patterns that may indicate secrets or sensitive data. Each pattern allows
# both ``key=value`` and ``key: value`` forms, including optional whitespace
# and JSON-style quotes around the separator.
_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"api_?key\s*['\"]?\s*[:=]\s*['\"]?\s*([A-Za-z0-9_\-]{16,})['\"]?",
        re.IGNORECASE,
    ),
    re.compile(
        r"secret\s*['\"]?\s*[:=]\s*['\"]?\s*([A-Za-z0-9/+=_\-]{16,})['\"]?",
        re.IGNORECASE,
    ),
    re.compile(
        r"password\s*['\"]?\s*[:=]\s*['\"]?\s*([^\s'\"]+)['\"]?",
        re.IGNORECASE,
    ),
    re.compile(
        r"token\s*['\"]?\s*[:=]\s*['\"]?\s*([A-Za-z0-9_\-]{16,})['\"]?",
        re.IGNORECASE,
    ),
)

# Tokens that are likely API keys or secrets (heuristic).
_SECRET_PREFIXES: tuple[str, ...] = (
    "sk-",
    "sk_live_",
    "sk_test_",
    "AKIA",
    "ghp_",
    "glpat-",
)


def redact_text(text: str) -> str:
    """Redact sensitive content from a stdout/stderr string.

    Redactions include: API keys, secrets, home paths, absolute paths, PIDs, and
    timestamps. The result is deterministic and safe for fingerprints and reports.
    """
    if not text:
        return ""

    # Redact secrets by pattern.
    for pattern in _SECRET_VALUE_PATTERNS:
        text = pattern.sub(_redact_secret_match, text)

    # Redact lines containing secret-like prefixes.
    lines = text.splitlines()
    redacted_lines: list[str] = []
    for line in lines:
        lower = line.lower()
        if any(prefix.lower() in lower for prefix in _SECRET_PREFIXES):
            redacted_lines.append("[REDACTED: secret-like token]")
            continue
        # Redact home directory paths.
        if re.search(r"/home/[^/\s]+", line):
            line = re.sub(r"/home/[^/\s]+", "/home/[REDACTED]", line)
        # Redact absolute paths.
        line = re.sub(r"/tmp/[A-Za-z0-9_./-]+", "/tmp/[REDACTED]", line)
        # Redact PIDs, but avoid over-redacting decimal metric values such as
        # ``1.23456``.
        line = re.sub(r"(?<!\d\.)\b\d{4,}\b(?!\.\d)", "[PID]", line)
        # Redact ISO-like timestamps.
        line = re.sub(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?",
            "[TIMESTAMP]",
            line,
        )
        redacted_lines.append(line)

    return "\n".join(redacted_lines)


def redact_path(path: str | Path) -> str:
    """Return a redacted string representation of a path."""
    path_str = str(path)
    path_str = re.sub(r"/home/[^/\s]+", "/home/[REDACTED]", path_str)
    path_str = re.sub(r"/tmp/[A-Za-z0-9_./-]+", "/tmp/[REDACTED]", path_str)
    return path_str
