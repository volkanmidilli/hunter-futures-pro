"""Writer for the Human Review Decision Registry (MVP-60)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from hunter.human_review_registry.models import (
    HUMAN_REVIEW_REGISTRY_VERSION,
    HumanReviewRecord,
    HumanReviewRegistryConfig,
)


SAFETY_NOTICE = (
    "This human review record is research-only. It does not authorize execution, "
    "trading, position changes, or any live market behavior."
)


def _deep_copy(value: Mapping[str, object] | tuple[Any, ...]) -> Any:
    """Return a JSON-roundtripped deep copy to avoid caller mutation."""
    return json.loads(json.dumps(value, default=str))


def human_review_record_to_dict(record: HumanReviewRecord) -> dict[str, Any]:
    """Serialize a review record to a deterministic dictionary."""
    return {
        "version": record.version,
        "source_decision_fingerprint": record.source_decision_fingerprint,
        "source_decision": record.source_decision,
        "reviewer_identity": record.reviewer_identity,
        "reviewer_decision": record.reviewer_decision,
        "review_note": record.review_note,
        "created_at": record.created_at.isoformat(),
        "previous_record_fingerprint": record.previous_record_fingerprint,
        "record_fingerprint": record.record_fingerprint,
        "accepted": record.accepted,
        "human_approval_recorded": record.human_approval_recorded,
        "execution_approval_granted": record.execution_approval_granted,
        "reason_codes": list(record.reason_codes),
        "safety_notice": SAFETY_NOTICE,
        "metadata": _deep_copy(record.metadata),
    }


def human_review_record_to_json_text(record: HumanReviewRecord) -> str:
    """Serialize a review record to deterministic JSON text."""
    return json.dumps(
        human_review_record_to_dict(record),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


def human_review_record_to_markdown_text(record: HumanReviewRecord) -> str:
    """Serialize a review record to a deterministic Markdown report."""
    lines = [
        "# Human Review Record",
        "",
        "## Safety Notice",
        "",
        SAFETY_NOTICE,
        "",
        "## Record Details",
        "",
        f"- **version**: {record.version}",
        f"- **source_decision_fingerprint**: {record.source_decision_fingerprint}",
        f"- **source_decision**: {record.source_decision}",
        f"- **reviewer_identity**: {record.reviewer_identity}",
        f"- **reviewer_decision**: {record.reviewer_decision}",
        f"- **review_note**: {record.review_note}",
        f"- **created_at**: {record.created_at.isoformat()}",
        f"- **previous_record_fingerprint**: {record.previous_record_fingerprint}",
        f"- **record_fingerprint**: {record.record_fingerprint}",
        f"- **accepted**: {record.accepted}",
        f"- **human_approval_recorded**: {record.human_approval_recorded}",
        f"- **execution_approval_granted**: {record.execution_approval_granted}",
        "",
        "## Reason Codes",
        "",
    ]
    if record.reason_codes:
        for code in record.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Metadata", "", json.dumps(_deep_copy(record.metadata), indent=2, sort_keys=True, default=str)])
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> Path:
    """Write ``content`` to ``path`` atomically via a temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)
    return path


def atomic_write_json_human_review_record(
    record: HumanReviewRecord,
    path: Path,
) -> Path:
    """Atomically write a JSON review record to ``path``."""
    return _atomic_write(path, human_review_record_to_json_text(record))


def atomic_write_markdown_human_review_record(
    record: HumanReviewRecord,
    path: Path,
) -> Path:
    """Atomically write a Markdown review record to ``path``."""
    return _atomic_write(path, human_review_record_to_markdown_text(record))


def _record_artifact_path(
    record: HumanReviewRecord,
    config: HumanReviewRegistryConfig,
    filename: str,
) -> Path:
    return config.output_dir / filename


def _report_artifact_path(
    record: HumanReviewRecord,
    config: HumanReviewRegistryConfig,
    filename: str,
) -> Path:
    return config.report_output_dir / filename


def write_human_review_record(
    record: HumanReviewRecord,
    config: HumanReviewRegistryConfig,
) -> tuple[Path, Path, Path, Path]:
    """Write immutable JSON/Markdown artifacts and convenience latest copies.

    Returns ``(json_path, md_path, latest_json_path, latest_md_path)``.
    """
    json_path = _record_artifact_path(record, config, f"{record.record_fingerprint}.json")
    md_path = _report_artifact_path(record, config, f"{record.record_fingerprint}.md")
    latest_json_path = _record_artifact_path(record, config, config.json_filename)
    latest_md_path = _report_artifact_path(record, config, config.markdown_filename)

    atomic_write_json_human_review_record(record, json_path)
    atomic_write_markdown_human_review_record(record, md_path)
    atomic_write_json_human_review_record(record, latest_json_path)
    atomic_write_markdown_human_review_record(record, latest_md_path)

    return json_path, md_path, latest_json_path, latest_md_path


__all__ = [
    "SAFETY_NOTICE",
    "human_review_record_to_dict",
    "human_review_record_to_json_text",
    "human_review_record_to_markdown_text",
    "atomic_write_json_human_review_record",
    "atomic_write_markdown_human_review_record",
    "write_human_review_record",
]
