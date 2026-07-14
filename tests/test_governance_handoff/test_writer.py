"""Tests for governance handoff writer (MVP-62 Step 5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.governance_handoff.engine import build_research_governance_handoff_package
from hunter.governance_handoff.models import (
    GOVERNANCE_HANDOFF_VERSION,
    READY_FOR_RESEARCH_HANDOFF,
    GovernanceHandoffConfig,
    GovernanceHandoffError,
    HandoffSourceReference,
    ResearchGovernanceHandoffManifest,
    ResearchGovernanceHandoffPackage,
)
from hunter.governance_handoff.writer import (
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    GovernanceHandoffWriterError,
    atomic_write_json_research_governance_handoff_package,
    atomic_write_markdown_research_governance_handoff_package,
    research_governance_handoff_package_to_dict,
    research_governance_handoff_package_to_json_text,
    research_governance_handoff_package_to_markdown_text,
    write_research_governance_handoff_package,
)


@dataclass(frozen=True)
class FakeReviewSummary:
    latest_accepted_record_fingerprint: str | None


@dataclass(frozen=True)
class FakeGovernanceSummary:
    version: str
    governance_fingerprint: str
    gate_decision_fingerprint: str
    governance_status: str
    review_summary: object
    research_only: bool = True
    execution_approval_granted: bool = False


@dataclass(frozen=True)
class FakeGateReport:
    version: str
    decision: str
    decision_fingerprint: str


@dataclass(frozen=True)
class FakeReviewRecord:
    version: str
    record_fingerprint: str
    source_decision_fingerprint: str
    accepted: bool
    human_approval_recorded: bool
    execution_approval_granted: bool
    reviewer_decision: str
    created_at: datetime


def _build_package():
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
        review_summary=FakeReviewSummary("review1"),
    )
    gate = FakeGateReport(
        version="0.59.0-dev",
        decision="GO",
        decision_fingerprint="gate1",
    )
    review = FakeReviewRecord(
        version="0.60.0-dev",
        record_fingerprint="review1",
        source_decision_fingerprint="gate1",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reviewer_decision="APPROVE_FOR_RESEARCH",
        created_at=datetime.now(timezone.utc),
    )
    return build_research_governance_handoff_package(
        summary,
        gate,
        review,
        GovernanceHandoffConfig(),
        built_at=datetime.fromisoformat("2026-07-14T12:00:00+00:00"),
        metadata={"run_id": "r1"},
    )


def test_to_dict_roundtrip():
    package = _build_package()
    data = research_governance_handoff_package_to_dict(package)
    assert data["version"] == GOVERNANCE_HANDOFF_VERSION
    assert data["package_fingerprint"] == package.package_fingerprint
    assert data["governance_status"] == READY_FOR_RESEARCH_HANDOFF
    assert data["handoff_allowed"] is True
    assert data["research_only"] is True
    assert data["execution_approval_granted"] is False
    assert data["production_approval_granted"] is False
    assert "safety_notice" in data
    assert data["manifest"]["package_fingerprint"] == package.package_fingerprint


def test_to_json_text_deterministic():
    package = _build_package()
    text1 = research_governance_handoff_package_to_json_text(package)
    text2 = research_governance_handoff_package_to_json_text(package)
    assert text1 == text2
    assert "safety_notice" in text1
    assert "0.62.0-dev" in text1


def test_to_markdown_text_contains_key_info():
    package = _build_package()
    text = research_governance_handoff_package_to_markdown_text(package)
    assert package.package_fingerprint in text
    assert READY_FOR_RESEARCH_HANDOFF in text
    assert "Safety Notice" in text
    assert "research_only" in text
    assert "execution_approval_granted" in text
    assert "production_approval_granted" in text


def test_writer_uses_default_paths():
    assert DEFAULT_JSON_PATH == Path("data/governance_handoff/latest_handoff_package.json")
    assert DEFAULT_MD_PATH == Path("reports/governance_handoff/latest_handoff_package.md")


def test_atomic_write_json(tmp_path):
    package = _build_package()
    path = tmp_path / "pkg.json"
    result = atomic_write_json_research_governance_handoff_package(package, path)
    assert result == path
    assert path.exists()
    assert package.package_fingerprint in path.read_text()


def test_atomic_write_markdown(tmp_path):
    package = _build_package()
    path = tmp_path / "pkg.md"
    result = atomic_write_markdown_research_governance_handoff_package(package, path)
    assert result == path
    assert path.exists()
    assert "# Research Governance Handoff Package" in path.read_text()


def test_write_package(tmp_path):
    package = _build_package()
    cfg = GovernanceHandoffConfig(
        output_dir=tmp_path / "out",
        report_output_dir=tmp_path / "reports",
    )
    json_path, md_path = write_research_governance_handoff_package(package, cfg)
    assert json_path.exists()
    assert md_path.exists()
    assert json_path.name == "latest_handoff_package.json"
    assert md_path.name == "latest_handoff_package.md"


def test_dict_rejects_non_dataclass():
    with pytest.raises(AttributeError):
        research_governance_handoff_package_to_dict("not-a-package")  # type: ignore[arg-type]


def test_rejects_naive_built_at():
    source = HandoffSourceReference(
        source_name="x",
        source_version="0.61.0-dev",
        fingerprint="abc",
        accepted=True,
        reason_codes=(),
    )
    manifest = ResearchGovernanceHandoffManifest(
        package_version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint="fp",
        built_at=datetime.now(timezone.utc),
        governance_fingerprint="gov1",
        gate_fingerprint="gate1",
        review_record_fingerprint=None,
        source_versions={},
        artifact_filenames={},
        safety_flags={"research_only": True},
    )
    with pytest.raises(ValueError):
        ResearchGovernanceHandoffPackage(
            version=GOVERNANCE_HANDOFF_VERSION,
            package_fingerprint="fp",
            built_at=datetime.utcnow(),
            governance_status=READY_FOR_RESEARCH_HANDOFF,
            handoff_allowed=True,
            governance_source=source,
            gate_source=source,
            review_source=None,
            blocking_reason_codes=(),
            review_reason_codes=(),
            manifest=manifest,
            research_only=True,
            execution_approval_granted=False,
            production_approval_granted=False,
            metadata={},
        )
