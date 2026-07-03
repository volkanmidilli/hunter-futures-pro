"""Tests for hunter.final_audit_pack.models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from hunter.final_audit_pack import (
    DEFAULT_OPTIONAL_SECTION_KINDS,
    DEFAULT_REQUIRED_SECTION_KINDS,
    DUPLICATE_SECTION_ID,
    FINAL_AUDIT_PACK_ADVISORY_REASON_CODES,
    FINAL_AUDIT_PACK_BLOCKING_REASON_CODES,
    FINAL_AUDIT_PACK_REASON_CODES,
    FINAL_AUDIT_PACK_VERSION,
    FORBIDDEN_FINAL_AUDIT_PACK_TERMS,
    INVALID_SECTION,
    MISSING_REQUIRED_FIELDS,
    MISSING_REQUIRED_SECTIONS,
    OK,
    UNSAFE_CONTENT,
    FinalAuditPackArtifact,
    FinalAuditPackConfig,
    FinalAuditPackCompleteness,
    FinalAuditPackDataQuality,
    FinalAuditPackInput,
    FinalAuditPackReasonCode,
    FinalAuditPackReport,
    FinalAuditPackSafetyFlags,
    FinalAuditPackSection,
    FinalAuditPackState,
    has_unsafe_final_audit_pack_content,
)


@pytest.fixture
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


class TestEnums:
    def test_final_audit_pack_state_values(self) -> None:
        assert FinalAuditPackState.INCLUDED.value == "included"
        assert FinalAuditPackState.EXCLUDED.value == "excluded"
        assert FinalAuditPackState.BLOCKED.value == "blocked"
        assert FinalAuditPackState.INSUFFICIENT_DATA.value == "insufficient_data"

    def test_final_audit_pack_reason_code_values(self) -> None:
        assert FinalAuditPackReasonCode.OK.value == "OK"
        assert FinalAuditPackReasonCode.MISSING_REQUIRED_SECTIONS.value == "MISSING_REQUIRED_SECTIONS"
        assert FinalAuditPackReasonCode.DUPLICATE_SECTION_ID.value == "DUPLICATE_SECTION_ID"
        assert FinalAuditPackReasonCode.UNSAFE_CONTENT.value == "UNSAFE_CONTENT"
        assert FinalAuditPackReasonCode.INVALID_SECTION.value == "INVALID_SECTION"
        assert FinalAuditPackReasonCode.MISSING_REQUIRED_FIELDS.value == "MISSING_REQUIRED_FIELDS"

    def test_reason_code_constants(self) -> None:
        assert OK == "OK"
        assert MISSING_REQUIRED_SECTIONS == "MISSING_REQUIRED_SECTIONS"
        assert DUPLICATE_SECTION_ID == "DUPLICATE_SECTION_ID"
        assert UNSAFE_CONTENT == "UNSAFE_CONTENT"
        assert INVALID_SECTION == "INVALID_SECTION"
        assert MISSING_REQUIRED_FIELDS == "MISSING_REQUIRED_FIELDS"
        assert all(
            code in FINAL_AUDIT_PACK_REASON_CODES
            for code in (
                OK,
                MISSING_REQUIRED_SECTIONS,
                DUPLICATE_SECTION_ID,
                UNSAFE_CONTENT,
                INVALID_SECTION,
                MISSING_REQUIRED_FIELDS,
            )
        )
        assert UNSAFE_CONTENT in FINAL_AUDIT_PACK_BLOCKING_REASON_CODES
        assert DUPLICATE_SECTION_ID in FINAL_AUDIT_PACK_BLOCKING_REASON_CODES
        assert OK in FINAL_AUDIT_PACK_ADVISORY_REASON_CODES

    def test_default_section_kinds(self) -> None:
        assert DEFAULT_REQUIRED_SECTION_KINDS == (
            "backtest",
            "run_orchestrator",
            "experiment_ledger",
        )
        assert DEFAULT_OPTIONAL_SECTION_KINDS == (
            "discovery",
            "portfolio_construction",
            "reporting_cli",
        )

    def test_forbidden_terms(self) -> None:
        assert "binance" in FORBIDDEN_FINAL_AUDIT_PACK_TERMS
        assert "leverage" in FORBIDDEN_FINAL_AUDIT_PACK_TERMS
        assert "freqtrade" in FORBIDDEN_FINAL_AUDIT_PACK_TERMS
        assert "scheduler" in FORBIDDEN_FINAL_AUDIT_PACK_TERMS


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


class TestFinalAuditPackSafetyFlags:
    def test_default_is_safe(self) -> None:
        flags = FinalAuditPackSafetyFlags()
        assert flags.is_safe is True

    def test_unsafe_content_breaks_is_safe(self) -> None:
        flags = FinalAuditPackSafetyFlags(has_unsafe_content=True)
        assert flags.is_safe is False

    def test_blocked_section_breaks_is_safe(self) -> None:
        flags = FinalAuditPackSafetyFlags(has_blocked_section=True)
        assert flags.is_safe is False

    def test_missing_required_sections_breaks_is_safe(self) -> None:
        flags = FinalAuditPackSafetyFlags(has_missing_required_sections=True)
        assert flags.is_safe is False

    def test_positive_invariants_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="baseline safety invariants"):
            FinalAuditPackSafetyFlags(no_network_connection=False)

    def test_build_safety_flags_helper(self) -> None:
        from hunter.final_audit_pack import build_final_audit_pack_safety_flags

        flags = build_final_audit_pack_safety_flags(has_blocked_section=True)
        assert flags.has_blocked_section is True
        assert flags.is_safe is False


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


class TestFinalAuditPackInput:
    def test_default_input(self) -> None:
        inp = FinalAuditPackInput()
        assert inp.backtest_reports == ()
        assert inp.run_results == ()
        assert inp.experiment_ledger_reports == ()
        assert inp.portfolio_construction_reports == ()
        assert inp.discovery_reports == ()
        assert inp.cli_command_results == ()
        assert inp.artifact_references == ()
        assert isinstance(inp.metadata, MappingProxyType)

    def test_input_coerces_tuples(self) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=[],
            run_results=[],
            artifact_references=["ref-1"],
        )
        assert isinstance(inp.backtest_reports, tuple)
        assert isinstance(inp.artifact_references, tuple)
        assert inp.artifact_references == ("ref-1",)

    def test_naive_generated_at_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            FinalAuditPackInput(generated_at=datetime(2024, 1, 1))

    def test_tags_must_be_strings(self) -> None:
        with pytest.raises(ValueError, match="tags"):
            FinalAuditPackInput(tags=[1])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# Artifact
# ---------------------------------------------------------------------------


class TestFinalAuditPackArtifact:
    def test_valid_artifact(self) -> None:
        artifact = FinalAuditPackArtifact(
            kind="artifact",
            reference="data/file.json",
            display_name="My artifact",
        )
        assert artifact.kind == "artifact"
        assert artifact.reference == "data/file.json"
        assert isinstance(artifact.metadata, MappingProxyType)

    def test_empty_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            FinalAuditPackArtifact(kind="", reference="ref")


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------


class TestFinalAuditPackSection:
    def test_valid_section(self, utcnow: datetime) -> None:
        section = FinalAuditPackSection(
            section_id="s-1",
            section_kind="backtest",
            report_id="r-1",
            run_id="run-1",
            name="Section 1",
            state=FinalAuditPackState.INCLUDED,
            reason_codes=(OK,),
            generated_at=utcnow,
        )
        assert section.section_id == "s-1"
        assert section.section_kind == "backtest"

    def test_blocked_section_requires_reason_codes(self) -> None:
        with pytest.raises(ValueError, match="BLOCKED sections must have reason_codes"):
            FinalAuditPackSection(
                section_id="s-1",
                section_kind="backtest",
                state=FinalAuditPackState.BLOCKED,
                reason_codes=(),
            )

    def test_unsupported_reason_code_rejected(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            FinalAuditPackSection(
                section_id="s-1",
                section_kind="backtest",
                reason_codes=("INVALID_CODE",),
            )

    def test_blocked_factory(self, utcnow: datetime) -> None:
        section = FinalAuditPackSection.blocked(
            section_id="s-1",
            section_kind="backtest",
            reason_codes=(MISSING_REQUIRED_FIELDS,),
            generated_at=utcnow,
        )
        assert section.state is FinalAuditPackState.BLOCKED
        assert MISSING_REQUIRED_FIELDS in section.reason_codes

    def test_frozen_section_cannot_be_modified(self) -> None:
        section = FinalAuditPackSection(
            section_id="s-1",
            section_kind="backtest",
        )
        with pytest.raises(FrozenInstanceError):
            section.name = "New Name"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestFinalAuditPackConfig:
    def test_default_config(self) -> None:
        config = FinalAuditPackConfig()
        assert config.required_section_kinds == DEFAULT_REQUIRED_SECTION_KINDS
        assert config.optional_section_kinds == DEFAULT_OPTIONAL_SECTION_KINDS
        assert config.block_on_missing_required is False

    def test_empty_required_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="required_section_kinds"):
            FinalAuditPackConfig(required_section_kinds=[""])

    def test_optional_kinds_allow_empty(self) -> None:
        config = FinalAuditPackConfig(optional_section_kinds=[])
        assert config.optional_section_kinds == ()

    def test_naive_generated_at_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            FinalAuditPackConfig(generated_at=datetime(2024, 1, 1))


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------


class TestFinalAuditPackCompleteness:
    def test_valid_completeness(self) -> None:
        comp = FinalAuditPackCompleteness(
            required_sections_present=2,
            required_sections_missing=1,
            optional_sections_present=1,
            artifact_reference_count=2,
            blocked_section_count=0,
            insufficient_section_count=0,
            total_sections=4,
            sections_expected=6,
            sections_present=4,
        )
        assert comp.required_sections_present == 2
        assert comp.sections_expected == 6

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="required_sections_present"):
            FinalAuditPackCompleteness(required_sections_present=-1)

    def test_present_plus_missing_exceeds_expected_rejected(self) -> None:
        with pytest.raises(ValueError, match="required present"):
            FinalAuditPackCompleteness(
                required_sections_present=2,
                required_sections_missing=2,
                sections_expected=3,
            )


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------


class TestFinalAuditPackDataQuality:
    def test_valid_data_quality(self) -> None:
        dq = FinalAuditPackDataQuality(
            total_inputs=5,
            normalized_sections=4,
            blocked_sections=1,
            insufficient_sections=0,
            excluded_sections=0,
            included_sections=3,
            sections_present=3,
            sections_expected=6,
            artifact_references=1,
        )
        assert dq.total_inputs == 5

    def test_state_counts_exceed_normalized_rejected(self) -> None:
        with pytest.raises(ValueError, match="state counts"):
            FinalAuditPackDataQuality(
                total_inputs=1,
                normalized_sections=1,
                blocked_sections=1,
                insufficient_sections=1,
                excluded_sections=0,
                included_sections=0,
            )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class TestFinalAuditPackReport:
    def test_valid_report(self, utcnow: datetime) -> None:
        inp = FinalAuditPackInput()
        section = FinalAuditPackSection(
            section_id="s-1",
            section_kind="backtest",
            reason_codes=(OK,),
            generated_at=utcnow,
        )
        report = FinalAuditPackReport(
            report_id="r-1",
            version=FINAL_AUDIT_PACK_VERSION,
            generated_at=utcnow,
            sections=(section,),
            reason_codes=(OK,),
        )
        assert report.version == FINAL_AUDIT_PACK_VERSION

    def test_empty_report_id_rejected(self, utcnow: datetime) -> None:
        with pytest.raises(ValueError, match="report_id"):
            FinalAuditPackReport(
                report_id="",
                generated_at=utcnow,
            )

    def test_naive_generated_at_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            FinalAuditPackReport(
                report_id="r-1",
                generated_at=datetime(2024, 1, 1),
            )

    def test_blocked_report_factory(self, utcnow: datetime) -> None:
        inp = FinalAuditPackInput()
        report = FinalAuditPackReport.blocked(
            input=inp,
            reason_code=UNSAFE_CONTENT,
            generated_at=utcnow,
        )
        assert report.reason_codes == (UNSAFE_CONTENT,)
        assert report.safety_flags.has_unsafe_content is True

    def test_unsupported_reason_code_rejected(self, utcnow: datetime) -> None:
        inp = FinalAuditPackInput()
        with pytest.raises(ValueError, match="unsupported reason code"):
            FinalAuditPackReport.blocked(
                input=inp,
                reason_code="INVALID_CODE",
                generated_at=utcnow,
            )


# ---------------------------------------------------------------------------
# Unsafe content detection
# ---------------------------------------------------------------------------


class TestUnsafeContentDetection:
    def test_detects_trading_term(self) -> None:
        assert has_unsafe_final_audit_pack_content(text="buy_signal") is True

    def test_detects_exchange_term(self) -> None:
        assert has_unsafe_final_audit_pack_content(text="binance_api") is True

    def test_detects_tag_term(self) -> None:
        assert has_unsafe_final_audit_pack_content(tags=["leverage_10x"]) is True

    def test_safe_content_returns_false(self) -> None:
        assert has_unsafe_final_audit_pack_content(text="research_audit") is False

    def test_custom_forbidden_terms(self) -> None:
        assert has_unsafe_final_audit_pack_content(
            text="xyz", forbidden_terms=frozenset({"xyz"})
        ) is True

    def test_empty_text_is_safe(self) -> None:
        assert has_unsafe_final_audit_pack_content(text="") is False

    def test_none_text_is_safe(self) -> None:
        assert has_unsafe_final_audit_pack_content(text=None) is False

    def test_metadata_not_scanned(self) -> None:
        # has_unsafe_final_audit_pack_content does not accept metadata; this
        # documents that only text and tags are scanned.
        assert has_unsafe_final_audit_pack_content(text="") is False
