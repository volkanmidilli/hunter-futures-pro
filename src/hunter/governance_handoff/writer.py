"""Writer for the Governance Handoff Package Builder (MVP-62).

Serializes ``ResearchGovernanceHandoffPackage`` to JSON, Markdown, and dict
forms. Output is local and audit-only. It never reads from ``data/`` or
``reports/``, and it never follows, traverses, validates, or executes any file
references.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.governance_handoff.models import (
    GovernanceHandoffConfig,
    ResearchGovernanceHandoffPackage,
)

DEFAULT_JSON_PATH: Path = Path("data/governance_handoff/latest_handoff_package.json")
DEFAULT_MD_PATH: Path = Path("reports/governance_handoff/latest_handoff_package.md")

_SAFETY_NOTICE = (
    "This research governance handoff package is a human-audit / research-only artifact. "
    "It is not execution approval, not production readiness, not trade approval, "
    "not strategy approval, not portfolio approval, not universe approval, "
    "and not a Freqtrade input or configuration. "
    "It does not emit action commands, suggest orders, create leverage, or create execution instructions. "
    "All artifact references are opaque identifiers and are never opened, followed, "
    "traversed, validated, fetched, or executed. "
    "Explicit human review and approval are required before any downstream use."
)


class GovernanceHandoffWriterError(Exception):
    """Base exception for the governance handoff writer."""


def _iso(value: datetime) -> str:
    """Serialize a timezone-aware datetime to ISO-8601 with UTC suffix."""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a value to JSON-safe deterministic types."""
    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_serialize_value(v) for v in value)
    if isinstance(value, (MappingProxyType, Mapping)):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if is_dataclass(value) and not isinstance(value, type):
        return _dataclass_to_dict(value)
    return str(value)


def _dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a frozen dataclass instance to a deterministic JSON-safe dict."""
    if not is_dataclass(obj) or isinstance(obj, type):
        raise TypeError(f"expected dataclass instance, got {type(obj)}")
    return {
        field: _serialize_value(getattr(obj, field))
        for field in obj.__dataclass_fields__
    }


def research_governance_handoff_package_to_dict(
    package: ResearchGovernanceHandoffPackage,
) -> dict[str, Any]:
    """Serialize a ``ResearchGovernanceHandoffPackage`` to a deterministic JSON-safe dict."""
    return {
        "version": package.version,
        "package_fingerprint": package.package_fingerprint,
        "built_at": _iso(package.built_at),
        "governance_status": package.governance_status,
        "handoff_allowed": package.handoff_allowed,
        "governance_source": _dataclass_to_dict(package.governance_source),
        "gate_source": _dataclass_to_dict(package.gate_source),
        "review_source": None
        if package.review_source is None
        else _dataclass_to_dict(package.review_source),
        "blocking_reason_codes": list(package.blocking_reason_codes),
        "review_reason_codes": list(package.review_reason_codes),
        "manifest": _dataclass_to_dict(package.manifest),
        "research_only": package.research_only,
        "execution_approval_granted": package.execution_approval_granted,
        "production_approval_granted": package.production_approval_granted,
        "metadata": _serialize_value(package.metadata),
        "safety_notice": _SAFETY_NOTICE,
    }


def research_governance_handoff_package_to_json_text(
    package: ResearchGovernanceHandoffPackage,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a ``ResearchGovernanceHandoffPackage`` to a deterministic JSON string."""
    data = research_governance_handoff_package_to_dict(package)
    return json.dumps(
        data,
        indent=indent,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":") if indent is None else None,
    )


def _source_ref_lines(ref: Any, title: str) -> list[str]:
    """Return Markdown lines describing a source reference."""
    lines = [
        f"### {title}",
        "",
        f"- **Source name:** {ref.source_name}",
        f"- **Source version:** {ref.source_version}",
        f"- **Fingerprint:** `{ref.fingerprint}`",
        f"- **Accepted:** {ref.accepted}",
    ]
    if ref.reason_codes:
        lines.append("- **Reason codes:** " + ", ".join(ref.reason_codes))
    else:
        lines.append("- **Reason codes:** _none_")
    lines.append("")
    return lines


def research_governance_handoff_package_to_markdown_text(
    package: ResearchGovernanceHandoffPackage,
    *,
    json_path: Path | str | None = None,
    markdown_path: Path | str | None = None,
) -> str:
    """Serialize a ``ResearchGovernanceHandoffPackage`` to a Markdown string."""
    manifest = package.manifest
    lines: list[str] = [
        "# Research Governance Handoff Package",
        "",
        f"**Version:** {package.version}",
        f"**Package fingerprint:** `{package.package_fingerprint}`",
        f"**Built at:** {_iso(package.built_at)}",
        f"**Governance status:** `{package.governance_status}`",
        f"**Handoff allowed:** {package.handoff_allowed}",
        f"**Research only:** {package.research_only}",
        f"**Execution approval granted:** {package.execution_approval_granted}",
        f"**Production approval granted:** {package.production_approval_granted}",
        "",
        "## Safety Notice",
        "",
        _SAFETY_NOTICE,
        "",
        "## Source References",
        "",
    ]
    lines.extend(_source_ref_lines(package.governance_source, "Governance Summary"))
    lines.extend(_source_ref_lines(package.gate_source, "Gate Report"))
    if package.review_source is not None:
        lines.extend(_source_ref_lines(package.review_source, "Latest Accepted Review"))
    else:
        lines.extend(["### Latest Accepted Review", "", "- _No review attached._", ""])

    lines.extend(
        [
            "## Manifest",
            "",
            f"- **Package version:** {manifest.package_version}",
            f"- **Package fingerprint:** `{manifest.package_fingerprint}`",
            f"- **Built at:** {_iso(manifest.built_at)}",
            f"- **Governance fingerprint:** `{manifest.governance_fingerprint}`",
            f"- **Gate fingerprint:** `{manifest.gate_fingerprint}`",
            f"- **Review record fingerprint:** {manifest.review_record_fingerprint or '_none_'}",
            "",
            "### Source versions",
            "",
        ]
    )
    if manifest.source_versions:
        for name, version in sorted(manifest.source_versions.items()):
            lines.append(f"- {name}: {version}")
    else:
        lines.append("- _No source versions._")
    lines.append("")

    lines.extend(["### Artifact filenames", ""])
    if manifest.artifact_filenames:
        for key, filename in sorted(manifest.artifact_filenames.items()):
            lines.append(f"- {key}: `{filename}`")
    else:
        lines.append("- _No artifact filenames._")
    lines.append("")

    lines.extend(["### Safety flags", ""])
    safety_flags = _serialize_value(manifest.safety_flags)
    if safety_flags:
        for key, value in sorted(safety_flags.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- _No safety flags._")
    lines.append("")

    lines.extend(["## Blocking Reason Codes", ""])
    if package.blocking_reason_codes:
        for code in package.blocking_reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("_None._")
    lines.append("")

    lines.extend(["## Review-Required Reason Codes", ""])
    if package.review_reason_codes:
        for code in package.review_reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("_None._")
    lines.append("")

    lines.extend(["## Artifacts", ""])
    if json_path is not None:
        lines.append(f"- JSON: `{json_path}`")
    if markdown_path is not None:
        lines.append(f"- Markdown: `{markdown_path}`")
    lines.append("")

    lines.extend(["## Metadata", ""])
    metadata = _serialize_value(package.metadata)
    if metadata:
        for key, value in sorted(metadata.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("_No metadata._")
    lines.append("")
    return "\n".join(lines)


def _resolve_path(config: GovernanceHandoffConfig, filename_attr: str) -> Path:
    """Resolve a writer path from config attributes."""
    output_dir = config.output_dir
    if filename_attr == "markdown_filename":
        output_dir = config.report_output_dir
    return output_dir / getattr(config, filename_attr)


def _atomic_write_text(path: Path, content: str) -> Path:
    """Write ``content`` to ``path`` atomically via a temporary file."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise GovernanceHandoffWriterError(
            f"cannot create directory {path.parent}: {exc}"
        ) from exc
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        temp_path.write_text(content, encoding="utf-8")
        os.replace(temp_path, path)
    except OSError as exc:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise GovernanceHandoffWriterError(f"cannot write {path}: {exc}") from exc
    return path


def write_research_governance_handoff_package(
    package: ResearchGovernanceHandoffPackage,
    config: GovernanceHandoffConfig,
) -> tuple[Path, Path]:
    """Write JSON and Markdown artifacts for ``package``.

    Returns ``(json_path, markdown_path)``.
    """
    json_path = _resolve_path(config, "json_filename")
    markdown_path = _resolve_path(config, "markdown_filename")
    json_text = research_governance_handoff_package_to_json_text(package)
    markdown_text = research_governance_handoff_package_to_markdown_text(
        package,
        json_path=json_path,
        markdown_path=markdown_path,
    )
    _atomic_write_text(json_path, json_text)
    _atomic_write_text(markdown_path, markdown_text)
    return json_path, markdown_path


def atomic_write_json_research_governance_handoff_package(
    package: ResearchGovernanceHandoffPackage,
    path: Path | str,
) -> Path:
    """Write the JSON representation of ``package`` to ``path``."""
    return _atomic_write_text(
        Path(path), research_governance_handoff_package_to_json_text(package)
    )


def atomic_write_markdown_research_governance_handoff_package(
    package: ResearchGovernanceHandoffPackage,
    path: Path | str,
) -> Path:
    """Write the Markdown representation of ``package`` to ``path``."""
    return _atomic_write_text(
        Path(path), research_governance_handoff_package_to_markdown_text(package)
    )


__all__ = [
    "DEFAULT_JSON_PATH",
    "DEFAULT_MD_PATH",
    "GovernanceHandoffWriterError",
    "atomic_write_json_research_governance_handoff_package",
    "atomic_write_markdown_research_governance_handoff_package",
    "research_governance_handoff_package_to_dict",
    "research_governance_handoff_package_to_json_text",
    "research_governance_handoff_package_to_markdown_text",
    "write_research_governance_handoff_package",
]
