"""Tests for governance handoff models (MVP-62 Step 1)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.governance_handoff.models import (
    BLOCKED,
    CANONICAL_SAFETY_FLAGS,
    CONTRADICTORY_HANDOFF_STATE,
    DEFAULT_JSON_FILENAME,
    DEFAULT_MARKDOWN_FILENAME,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_OUTPUT_DIR,
    DEFAULT_REQUIRE_LATEST_ACCEPTED_REVIEW,
    GATE_FINGERPRINT_MISMATCH,
    GOVERNANCE_FINGERPRINT_MISMATCH,
    GOVERNANCE_HANDOFF_VERSION,
    GOVERNANCE_REVIEW_REQUIRED,
    GOVERNANCE_STATUSES,
    HANDOFF_BLOCKING_REASON_CODES,
    HANDOFF_PACKAGE_READY,
    HANDOFF_REASON_CODES,
    HANDOFF_REVIEW_REQUIRED_REASON_CODES,
    INCOMPLETE_PROVENANCE,
    INVALID_GATE_REPORT,
    INVALID_GOVERNANCE_SUMMARY,
    INVALID_REVIEW_RECORD,
    INVALID_TIMESTAMP,
    MISSING_GATE_REPORT,
    MISSING_GOVERNANCE_SUMMARY,
    MISSING_LATEST_ACCEPTED_REVIEW,
    MISSING_OPTIONAL_METADATA,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_FINGERPRINT_MISMATCH,
    REVIEW_REQUIRED,
    SOURCE_VERSION_MISMATCH,
    UNSAFE_HANDOFF_FLAG,
    UNKNOWN_NON_BLOCKING_FIELD,
    GovernanceHandoffConfig,
    GovernanceHandoffError,
    HandoffSourceReference,
    ResearchGovernanceHandoffManifest,
    ResearchGovernanceHandoffPackage,
)


def test_version_constant():
    assert GOVERNANCE_HANDOFF_VERSION == "0.62.0-dev"


def test_status_constants():
    assert READY_FOR_RESEARCH_HANDOFF == "READY_FOR_RESEARCH_HANDOFF"
    assert REVIEW_REQUIRED == "REVIEW_REQUIRED"
    assert BLOCKED == "BLOCKED"
    assert GOVERNANCE_STATUSES == {
        READY_FOR_RESEARCH_HANDOFF,
        REVIEW_REQUIRED,
        BLOCKED,
    }


def test_blocking_reason_codes():
    assert MISSING_GOVERNANCE_SUMMARY in HANDOFF_BLOCKING_REASON_CODES
    assert MISSING_GATE_REPORT in HANDOFF_BLOCKING_REASON_CODES
    assert MISSING_LATEST_ACCEPTED_REVIEW in HANDOFF_BLOCKING_REASON_CODES
    assert INVALID_GOVERNANCE_SUMMARY in HANDOFF_BLOCKING_REASON_CODES
    assert INVALID_GATE_REPORT in HANDOFF_BLOCKING_REASON_CODES
    assert INVALID_REVIEW_RECORD in HANDOFF_BLOCKING_REASON_CODES
    assert GOVERNANCE_FINGERPRINT_MISMATCH in HANDOFF_BLOCKING_REASON_CODES
    assert GATE_FINGERPRINT_MISMATCH in HANDOFF_BLOCKING_REASON_CODES
    assert REVIEW_FINGERPRINT_MISMATCH in HANDOFF_BLOCKING_REASON_CODES
    assert SOURCE_VERSION_MISMATCH in HANDOFF_BLOCKING_REASON_CODES
    assert CONTRADICTORY_HANDOFF_STATE in HANDOFF_BLOCKING_REASON_CODES
    assert UNSAFE_HANDOFF_FLAG in HANDOFF_BLOCKING_REASON_CODES
    assert INVALID_TIMESTAMP in HANDOFF_BLOCKING_REASON_CODES


def test_review_required_reason_codes():
    assert GOVERNANCE_REVIEW_REQUIRED in HANDOFF_REVIEW_REQUIRED_REASON_CODES
    assert INCOMPLETE_PROVENANCE in HANDOFF_REVIEW_REQUIRED_REASON_CODES
    assert UNKNOWN_NON_BLOCKING_FIELD in HANDOFF_REVIEW_REQUIRED_REASON_CODES
    assert MISSING_OPTIONAL_METADATA in HANDOFF_REVIEW_REQUIRED_REASON_CODES


def test_reason_code_sets_disjoint():
    assert not HANDOFF_BLOCKING_REASON_CODES & HANDOFF_REVIEW_REQUIRED_REASON_CODES
    assert (
        HANDOFF_BLOCKING_REASON_CODES | HANDOFF_REVIEW_REQUIRED_REASON_CODES
        == HANDOFF_REASON_CODES
    )


def test_ready_marker():
    assert HANDOFF_PACKAGE_READY == "HANDOFF_PACKAGE_READY"


def test_canonical_safety_flags():
    assert CANONICAL_SAFETY_FLAGS == {
        "research_only": True,
        "execution_approval_granted": False,
        "production_approval_granted": False,
        "live_trading_allowed": False,
        "automatic_execution_allowed": False,
    }


def test_default_constants():
    assert DEFAULT_REQUIRE_LATEST_ACCEPTED_REVIEW is True
    assert DEFAULT_OUTPUT_DIR == Path("data/governance_handoff")
    assert DEFAULT_REPORT_OUTPUT_DIR == Path("reports/governance_handoff")
    assert DEFAULT_JSON_FILENAME == "latest_handoff_package.json"
    assert DEFAULT_MARKDOWN_FILENAME == "latest_handoff_package.md"


def test_config_defaults():
    cfg = GovernanceHandoffConfig()
    assert cfg.require_latest_accepted_review is True
    assert cfg.output_dir == DEFAULT_OUTPUT_DIR
    assert cfg.report_output_dir == DEFAULT_REPORT_OUTPUT_DIR
    assert cfg.json_filename == DEFAULT_JSON_FILENAME
    assert cfg.markdown_filename == DEFAULT_MARKDOWN_FILENAME
    assert dict(cfg.metadata) == {}


def test_config_coerces_path_strings():
    cfg = GovernanceHandoffConfig(
        output_dir="out",
        report_output_dir="reports/out",
    )
    assert isinstance(cfg.output_dir, Path)
    assert cfg.output_dir == Path("out")
    assert cfg.report_output_dir == Path("reports/out")


def test_config_rejects_empty_filename():
    with pytest.raises(ValueError):
        GovernanceHandoffConfig(json_filename="")
    with pytest.raises(ValueError):
        GovernanceHandoffConfig(markdown_filename="  ")


def test_config_rejects_non_bool_require_review():
    with pytest.raises(ValueError):
        GovernanceHandoffConfig(require_latest_accepted_review="yes")


def test_config_metadata_defensive_copy():
    meta = {"key": [1, 2, {"nested": True}]}
    cfg = GovernanceHandoffConfig(metadata=meta)
    assert dict(cfg.metadata) == meta
    meta["key"].append(3)
    assert list(cfg.metadata["key"]) == [1, 2, {"nested": True}]


def test_config_default_classmethod():
    assert GovernanceHandoffConfig.default() == GovernanceHandoffConfig()


def test_source_reference_ok():
    ref = HandoffSourceReference(
        source_name="governance_summary",
        source_version="0.61.0-dev",
        fingerprint="abc123",
        accepted=True,
        reason_codes=("HANDOFF_PACKAGE_READY",),
    )
    assert ref.source_name == "governance_summary"
    assert ref.accepted is True
    assert ref.reason_codes == ("HANDOFF_PACKAGE_READY",)


def test_source_reference_coerces_reason_codes():
    ref = HandoffSourceReference(
        source_name="gate",
        source_version="0.59.0-dev",
        fingerprint="def456",
        accepted=False,
        reason_codes=["MISSING_GATE_REPORT"],
    )
    assert ref.reason_codes == ("MISSING_GATE_REPORT",)


def test_source_reference_rejects_empty_fields():
    with pytest.raises(ValueError):
        HandoffSourceReference(
            source_name="",
            source_version="0.61.0-dev",
            fingerprint="abc",
            accepted=True,
            reason_codes=(),
        )
    with pytest.raises(ValueError):
        HandoffSourceReference(
            source_name="x",
            source_version="",
            fingerprint="abc",
            accepted=True,
            reason_codes=(),
        )
    with pytest.raises(ValueError):
        HandoffSourceReference(
            source_name="x",
            source_version="0.61.0-dev",
            fingerprint="  ",
            accepted=True,
            reason_codes=(),
        )


def test_source_reference_rejects_non_bool_accepted():
    with pytest.raises(ValueError):
        HandoffSourceReference(
            source_name="x",
            source_version="0.61.0-dev",
            fingerprint="abc",
            accepted="yes",
            reason_codes=(),
        )


def test_manifest_ok():
    built_at = datetime.now(timezone.utc)
    manifest = ResearchGovernanceHandoffManifest(
        package_version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint="pkg123",
        built_at=built_at,
        governance_fingerprint="gov123",
        gate_fingerprint="gate123",
        review_record_fingerprint="review123",
        source_versions={"governance_summary": "0.61.0-dev", "gate": "0.59.0-dev"},
        artifact_filenames={"json": DEFAULT_JSON_FILENAME, "markdown": DEFAULT_MARKDOWN_FILENAME},
        safety_flags=dict(CANONICAL_SAFETY_FLAGS),
    )
    assert manifest.package_version == GOVERNANCE_HANDOFF_VERSION
    assert manifest.review_record_fingerprint == "review123"
    assert manifest.built_at == built_at


def test_manifest_allows_none_review_fingerprint():
    manifest = ResearchGovernanceHandoffManifest(
        package_version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint="pkg123",
        built_at=datetime.now(timezone.utc),
        governance_fingerprint="gov123",
        gate_fingerprint="gate123",
        review_record_fingerprint=None,
        source_versions={},
        artifact_filenames={},
        safety_flags=dict(CANONICAL_SAFETY_FLAGS),
    )
    assert manifest.review_record_fingerprint is None


def test_manifest_rejects_naive_built_at():
    with pytest.raises(ValueError):
        ResearchGovernanceHandoffManifest(
            package_version=GOVERNANCE_HANDOFF_VERSION,
            package_fingerprint="pkg123",
            built_at=datetime.utcnow(),
            governance_fingerprint="gov123",
            gate_fingerprint="gate123",
            review_record_fingerprint=None,
            source_versions={},
            artifact_filenames={},
            safety_flags=dict(CANONICAL_SAFETY_FLAGS),
        )


def test_manifest_rejects_empty_fingerprints():
    built_at = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        ResearchGovernanceHandoffManifest(
            package_version=GOVERNANCE_HANDOFF_VERSION,
            package_fingerprint="",
            built_at=built_at,
            governance_fingerprint="gov123",
            gate_fingerprint="gate123",
            review_record_fingerprint=None,
            source_versions={},
            artifact_filenames={},
            safety_flags=dict(CANONICAL_SAFETY_FLAGS),
        )


def test_package_ok():
    built_at = datetime.now(timezone.utc)
    manifest = ResearchGovernanceHandoffManifest(
        package_version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint="pkg123",
        built_at=built_at,
        governance_fingerprint="gov123",
        gate_fingerprint="gate123",
        review_record_fingerprint="review123",
        source_versions={"governance_summary": "0.61.0-dev"},
        artifact_filenames={"json": DEFAULT_JSON_FILENAME},
        safety_flags=dict(CANONICAL_SAFETY_FLAGS),
    )
    gov_source = HandoffSourceReference(
        source_name="governance_summary",
        source_version="0.61.0-dev",
        fingerprint="gov123",
        accepted=True,
        reason_codes=(HANDOFF_PACKAGE_READY,),
    )
    gate_source = HandoffSourceReference(
        source_name="research_decision_gate",
        source_version="0.59.0-dev",
        fingerprint="gate123",
        accepted=True,
        reason_codes=(HANDOFF_PACKAGE_READY,),
    )
    review_source = HandoffSourceReference(
        source_name="human_review_registry",
        source_version="0.60.0-dev",
        fingerprint="review123",
        accepted=True,
        reason_codes=(HANDOFF_PACKAGE_READY,),
    )
    package = ResearchGovernanceHandoffPackage(
        version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint="pkg123",
        built_at=built_at,
        governance_status=READY_FOR_RESEARCH_HANDOFF,
        handoff_allowed=True,
        governance_source=gov_source,
        gate_source=gate_source,
        review_source=review_source,
        blocking_reason_codes=(),
        review_reason_codes=(),
        manifest=manifest,
        research_only=True,
        execution_approval_granted=False,
        production_approval_granted=False,
        metadata={"run_id": "r1"},
    )
    assert package.handoff_allowed is True
    assert package.governance_status == READY_FOR_RESEARCH_HANDOFF
    assert package.review_source is not None


def test_package_rejects_invalid_status():
    built_at = datetime.now(timezone.utc)
    manifest = ResearchGovernanceHandoffManifest(
        package_version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint="pkg123",
        built_at=built_at,
        governance_fingerprint="gov123",
        gate_fingerprint="gate123",
        review_record_fingerprint=None,
        source_versions={},
        artifact_filenames={},
        safety_flags=dict(CANONICAL_SAFETY_FLAGS),
    )
    source = HandoffSourceReference(
        source_name="x",
        source_version="0.61.0-dev",
        fingerprint="abc",
        accepted=True,
        reason_codes=(),
    )
    with pytest.raises(ValueError):
        ResearchGovernanceHandoffPackage(
            version=GOVERNANCE_HANDOFF_VERSION,
            package_fingerprint="pkg123",
            built_at=built_at,
            governance_status="INVALID",
            handoff_allowed=False,
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


def test_package_rejects_naive_built_at():
    manifest = ResearchGovernanceHandoffManifest(
        package_version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint="pkg123",
        built_at=datetime.now(timezone.utc),
        governance_fingerprint="gov123",
        gate_fingerprint="gate123",
        review_record_fingerprint=None,
        source_versions={},
        artifact_filenames={},
        safety_flags=dict(CANONICAL_SAFETY_FLAGS),
    )
    source = HandoffSourceReference(
        source_name="x",
        source_version="0.61.0-dev",
        fingerprint="abc",
        accepted=True,
        reason_codes=(),
    )
    with pytest.raises(ValueError):
        ResearchGovernanceHandoffPackage(
            version=GOVERNANCE_HANDOFF_VERSION,
            package_fingerprint="pkg123",
            built_at=datetime.utcnow(),
            governance_status=BLOCKED,
            handoff_allowed=False,
            governance_source=source,
            gate_source=source,
            review_source=None,
            blocking_reason_codes=(MISSING_GOVERNANCE_SUMMARY,),
            review_reason_codes=(),
            manifest=manifest,
            research_only=True,
            execution_approval_granted=False,
            production_approval_granted=False,
            metadata={},
        )


def test_package_coerces_reason_lists():
    built_at = datetime.now(timezone.utc)
    manifest = ResearchGovernanceHandoffManifest(
        package_version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint="pkg123",
        built_at=built_at,
        governance_fingerprint="gov123",
        gate_fingerprint="gate123",
        review_record_fingerprint=None,
        source_versions={},
        artifact_filenames={},
        safety_flags=dict(CANONICAL_SAFETY_FLAGS),
    )
    source = HandoffSourceReference(
        source_name="x",
        source_version="0.61.0-dev",
        fingerprint="abc",
        accepted=True,
        reason_codes=(),
    )
    package = ResearchGovernanceHandoffPackage(
        version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint="pkg123",
        built_at=built_at,
        governance_status=BLOCKED,
        handoff_allowed=False,
        governance_source=source,
        gate_source=source,
        review_source=None,
        blocking_reason_codes=[MISSING_GOVERNANCE_SUMMARY],
        review_reason_codes=[INCOMPLETE_PROVENANCE],
        manifest=manifest,
        research_only=True,
        execution_approval_granted=False,
        production_approval_granted=False,
        metadata={},
    )
    assert package.blocking_reason_codes == (MISSING_GOVERNANCE_SUMMARY,)
    assert package.review_reason_codes == (INCOMPLETE_PROVENANCE,)


def test_package_rejects_non_bool_safety_fields():
    built_at = datetime.now(timezone.utc)
    manifest = ResearchGovernanceHandoffManifest(
        package_version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint="pkg123",
        built_at=built_at,
        governance_fingerprint="gov123",
        gate_fingerprint="gate123",
        review_record_fingerprint=None,
        source_versions={},
        artifact_filenames={},
        safety_flags=dict(CANONICAL_SAFETY_FLAGS),
    )
    source = HandoffSourceReference(
        source_name="x",
        source_version="0.61.0-dev",
        fingerprint="abc",
        accepted=True,
        reason_codes=(),
    )
    base = {
        "version": GOVERNANCE_HANDOFF_VERSION,
        "package_fingerprint": "pkg123",
        "built_at": built_at,
        "governance_status": BLOCKED,
        "handoff_allowed": False,
        "governance_source": source,
        "gate_source": source,
        "review_source": None,
        "blocking_reason_codes": (),
        "review_reason_codes": (),
        "manifest": manifest,
        "research_only": True,
        "execution_approval_granted": False,
        "production_approval_granted": False,
        "metadata": {},
    }
    with pytest.raises(ValueError):
        ResearchGovernanceHandoffPackage(**{**base, "research_only": "yes"})
    with pytest.raises(ValueError):
        ResearchGovernanceHandoffPackage(**{**base, "execution_approval_granted": "yes"})
    with pytest.raises(ValueError):
        ResearchGovernanceHandoffPackage(**{**base, "production_approval_granted": "yes"})


def test_governance_handoff_error_reason_code():
    err = GovernanceHandoffError("boom", reason_code="INVALID_REVIEW_RECORD")
    assert err.reason_code == "INVALID_REVIEW_RECORD"
