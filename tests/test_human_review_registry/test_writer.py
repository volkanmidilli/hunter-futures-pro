"""Tests for the human review registry writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from hunter.human_review_registry import (
    APPROVE_FOR_RESEARCH,
    GO,
    HUMAN_REVIEW_REGISTRY_VERSION,
    REVIEW_APPROVED_FOR_RESEARCH,
    HumanReviewInput,
    HumanReviewRecord,
    HumanReviewRegistryConfig,
    SAFETY_NOTICE,
    atomic_write_json_human_review_record,
    atomic_write_markdown_human_review_record,
    build_human_review_record,
    human_review_record_to_dict,
    human_review_record_to_json_text,
    human_review_record_to_markdown_text,
    write_human_review_record,
)


def _build_record(tmp_path: Path) -> HumanReviewRecord:
    config = HumanReviewRegistryConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
    )
    report = SimpleNamespace(decision=GO, decision_fingerprint="src-fp")
    inp = HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="Approved for research only.",
    )
    return build_human_review_record(report, inp, config, created_at=datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc))


def test_record_to_dict_contains_required_fields(tmp_path: Path) -> None:
    record = _build_record(tmp_path)
    data = human_review_record_to_dict(record)
    assert data["version"] == HUMAN_REVIEW_REGISTRY_VERSION
    assert data["source_decision_fingerprint"] == "src-fp"
    assert data["source_decision"] == GO
    assert data["reviewer_identity"] == "alice"
    assert data["accepted"] is True
    assert data["execution_approval_granted"] is False
    assert data["safety_notice"] == SAFETY_NOTICE


def test_record_to_json_text_is_valid_json(tmp_path: Path) -> None:
    record = _build_record(tmp_path)
    text = human_review_record_to_json_text(record)
    parsed = json.loads(text)
    assert parsed["record_fingerprint"] == record.record_fingerprint


def test_record_to_markdown_text_contains_sections(tmp_path: Path) -> None:
    record = _build_record(tmp_path)
    text = human_review_record_to_markdown_text(record)
    assert "# Human Review Record" in text
    assert "## Safety Notice" in text
    assert SAFETY_NOTICE in text
    assert record.record_fingerprint in text
    assert REVIEW_APPROVED_FOR_RESEARCH in text


def test_write_record_creates_files(tmp_path: Path) -> None:
    config = HumanReviewRegistryConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
    )
    record = _build_record(tmp_path)
    json_path, md_path, latest_json, latest_md = write_human_review_record(record, config)
    assert json_path.exists()
    assert md_path.exists()
    assert latest_json.exists()
    assert latest_md.exists()
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["record_fingerprint"] == record.record_fingerprint


def test_atomic_json_writer(tmp_path: Path) -> None:
    record = _build_record(tmp_path)
    path = tmp_path / "custom.json"
    result = atomic_write_json_human_review_record(record, path)
    assert result == path
    assert path.exists()


def test_atomic_markdown_writer(tmp_path: Path) -> None:
    record = _build_record(tmp_path)
    path = tmp_path / "custom.md"
    result = atomic_write_markdown_human_review_record(record, path)
    assert result == path
    assert path.exists()
