"""Tests for governance handoff policy (MVP-62 Step 3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from hunter.governance_handoff.models import (
    BLOCKED,
    CANONICAL_SAFETY_FLAGS,
    GOVERNANCE_REVIEW_REQUIRED,
    INCOMPLETE_PROVENANCE,
    MISSING_GOVERNANCE_SUMMARY,
    MISSING_OPTIONAL_METADATA,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_REQUIRED,
    GovernanceHandoffConfig,
    HandoffSourceReference,
)
from hunter.governance_handoff.policy import (
    build_handoff_manifest,
    build_handoff_safety_flags,
    build_source_references,
    classify_handoff_reasons,
    resolve_handoff_allowed,
)


@dataclass(frozen=True)
class FakeGovernanceSummary:
    version: str
    governance_fingerprint: str
    gate_decision_fingerprint: str
    governance_status: str


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


def test_build_handoff_safety_flags():
    assert build_handoff_safety_flags() == CANONICAL_SAFETY_FLAGS


def test_build_source_references():
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
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
    )
    gov_ref, gate_ref, review_ref = build_source_references(
        summary,
        gate,
        review,
        governance_reasons=(),
        gate_reasons=(),
        review_reasons=(),
    )
    assert gov_ref.source_name == "governance_summary"
    assert gov_ref.source_version == "0.61.0-dev"
    assert gov_ref.fingerprint == "gov1"
    assert gov_ref.accepted is True
    assert gate_ref.source_name == "research_decision_gate"
    assert gate_ref.source_version == "0.59.0-dev"
    assert gate_ref.fingerprint == "gate1"
    assert review_ref is not None
    assert review_ref.source_name == "human_review_registry"
    assert review_ref.source_version == "0.60.0-dev"
    assert review_ref.fingerprint == "review1"


def test_build_source_references_missing_sources():
    gov_ref, gate_ref, review_ref = build_source_references(
        None,
        None,
        None,
        governance_reasons=(MISSING_GOVERNANCE_SUMMARY,),
        gate_reasons=(MISSING_GOVERNANCE_SUMMARY,),
        review_reasons=(),
    )
    assert gov_ref.fingerprint == "MISSING"
    assert gov_ref.source_version == "unknown"
    assert gov_ref.accepted is False
    assert gate_ref.fingerprint == "MISSING"
    assert review_ref is None


def test_classify_handoff_reasons_ready():
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
    )
    blocking, review = classify_handoff_reasons(summary, (), {"key": "value"})
    assert blocking == ()
    assert review == ()


def test_classify_handoff_reasons_blocked():
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=BLOCKED,
    )
    blocking, review = classify_handoff_reasons(
        summary, (MISSING_GOVERNANCE_SUMMARY,), {"key": "value"}
    )
    assert blocking == (MISSING_GOVERNANCE_SUMMARY,)
    assert review == ()


def test_classify_handoff_reasons_review_required():
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=REVIEW_REQUIRED,
    )
    blocking, review = classify_handoff_reasons(summary, (), {"key": "value"})
    assert blocking == ()
    assert GOVERNANCE_REVIEW_REQUIRED in review


def test_classify_handoff_reasons_incomplete_metadata():
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
    )
    blocking, review = classify_handoff_reasons(summary, (), None)
    assert INCOMPLETE_PROVENANCE in review


def test_classify_handoff_reasons_deduplicates():
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
    )
    blocking, review = classify_handoff_reasons(
        summary,
        (MISSING_GOVERNANCE_SUMMARY, MISSING_GOVERNANCE_SUMMARY),
        {},
    )
    assert blocking == (MISSING_GOVERNANCE_SUMMARY,)
    assert review == (MISSING_OPTIONAL_METADATA,)


def test_classify_handoff_reasons_empty_metadata():
    summary = FakeGovernanceSummary(
        version="0.61.0-dev",
        governance_fingerprint="gov1",
        gate_decision_fingerprint="gate1",
        governance_status=READY_FOR_RESEARCH_HANDOFF,
    )
    blocking, review = classify_handoff_reasons(summary, (), {})
    assert blocking == ()
    assert review == (MISSING_OPTIONAL_METADATA,)


def test_resolve_handoff_allowed_ready():
    assert resolve_handoff_allowed(READY_FOR_RESEARCH_HANDOFF, (), ()) is True


def test_resolve_handoff_allowed_blocked():
    assert resolve_handoff_allowed(BLOCKED, (), ()) is False


def test_resolve_handoff_allowed_review_required():
    assert resolve_handoff_allowed(REVIEW_REQUIRED, (), ()) is False


def test_resolve_handoff_allowed_ready_with_blocking_reason():
    assert resolve_handoff_allowed(READY_FOR_RESEARCH_HANDOFF, (MISSING_GOVERNANCE_SUMMARY,), ()) is False


def test_resolve_handoff_allowed_ready_with_review_reason():
    assert resolve_handoff_allowed(READY_FOR_RESEARCH_HANDOFF, (), (GOVERNANCE_REVIEW_REQUIRED,)) is False


def test_build_handoff_manifest():
    gov_ref = HandoffSourceReference(
        source_name="governance_summary",
        source_version="0.61.0-dev",
        fingerprint="gov1",
        accepted=True,
        reason_codes=(),
    )
    gate_ref = HandoffSourceReference(
        source_name="research_decision_gate",
        source_version="0.59.0-dev",
        fingerprint="gate1",
        accepted=True,
        reason_codes=(),
    )
    review_ref = HandoffSourceReference(
        source_name="human_review_registry",
        source_version="0.60.0-dev",
        fingerprint="review1",
        accepted=True,
        reason_codes=(),
    )
    manifest = build_handoff_manifest(
        package_version="0.62.0-dev",
        package_fingerprint="pkg1",
        built_at=datetime.now(timezone.utc),
        governance_source=gov_ref,
        gate_source=gate_ref,
        review_source=review_ref,
        safety_flags=CANONICAL_SAFETY_FLAGS,
        artifact_filenames={"json": "x.json", "markdown": "x.md"},
    )
    assert manifest.package_version == "0.62.0-dev"
    assert manifest.governance_fingerprint == "gov1"
    assert manifest.gate_fingerprint == "gate1"
    assert manifest.review_record_fingerprint == "review1"
    assert manifest.source_versions == {
        "governance_summary": "0.61.0-dev",
        "research_decision_gate": "0.59.0-dev",
        "human_review_registry": "0.60.0-dev",
    }
    assert manifest.artifact_filenames == {"json": "x.json", "markdown": "x.md"}
    assert manifest.safety_flags == CANONICAL_SAFETY_FLAGS


def test_build_handoff_manifest_no_review():
    gov_ref = HandoffSourceReference(
        source_name="governance_summary",
        source_version="0.61.0-dev",
        fingerprint="gov1",
        accepted=True,
        reason_codes=(),
    )
    gate_ref = HandoffSourceReference(
        source_name="research_decision_gate",
        source_version="0.59.0-dev",
        fingerprint="gate1",
        accepted=True,
        reason_codes=(),
    )
    manifest = build_handoff_manifest(
        package_version="0.62.0-dev",
        package_fingerprint="pkg1",
        built_at=datetime.now(timezone.utc),
        governance_source=gov_ref,
        gate_source=gate_ref,
        review_source=None,
        safety_flags=CANONICAL_SAFETY_FLAGS,
        artifact_filenames={"json": "x.json", "markdown": "x.md"},
    )
    assert manifest.review_record_fingerprint is None
    assert "human_review_registry" not in manifest.source_versions
