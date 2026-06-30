"""Tests for hunter.research_audit_snapshot.models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from hunter.research_audit_snapshot.models import (
    AUDIT_SNAPSHOT_ADVISORY_REASON_CODES,
    AUDIT_SNAPSHOT_BLOCKING_REASON_CODES,
    AUDIT_SNAPSHOT_INCOMPLETE_REASON_CODES,
    AUDIT_SNAPSHOT_REASON_CODES,
    AUDIT_SNAPSHOT_STALE_REASON_CODES,
    BLOCKED_ARTIFACT_ITEM,
    CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER,
    FILE_REFS_NOT_TRAVERSED,
    FORBIDDEN_SNAPSHOT_TERMS,
    HUMAN_AUDIT_GUIDE_NON_GATING,
    INCOMPLETE_ARTIFACT_ITEM,
    INVALID_SNAPSHOT_CONFIG,
    MISSING_ARTIFACT_SUMMARIES,
    MISSING_REQUIRED_SECTION,
    NO_ACTION_COMMANDS_EMITTED,
    OPEN_ITEMS_PRESENT,
    SNAPSHOT_VERSION,
    STALE_ARTIFACT_DETECTED,
    UNSAFE_SNAPSHOT_CONTENT,
    UNKNOWN_SNAPSHOT_STATE,
    AuditSnapshotConfig,
    AuditSnapshotDataQuality,
    AuditSnapshotItem,
    AuditSnapshotItemSeverity,
    AuditSnapshotKind,
    AuditSnapshotSafetyFlags,
    AuditSnapshotSection,
    AuditSnapshotSectionKind,
    AuditSnapshotState,
    AuditSnapshotSummary,
    ResearchAuditSnapshot,
)


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestAuditSnapshotState:
    def test_enum_values(self) -> None:
        assert AuditSnapshotState.CURRENT.value == "current"
        assert AuditSnapshotState.STALE.value == "stale"
        assert AuditSnapshotState.INCOMPLETE.value == "incomplete"
        assert AuditSnapshotState.BLOCK.value == "block"
        assert AuditSnapshotState.UNKNOWN.value == "unknown"


class TestAuditSnapshotKind:
    def test_enum_values(self) -> None:
        assert AuditSnapshotKind.RESEARCH_AUDIT_SNAPSHOT.value == "research_audit_snapshot"


class TestAuditSnapshotSectionKind:
    def test_enum_values(self) -> None:
        assert AuditSnapshotSectionKind.OVERVIEW.value == "overview"
        assert AuditSnapshotSectionKind.VERSION_STATE.value == "version_state"
        assert AuditSnapshotSectionKind.ARTIFACT_STATE.value == "artifact_state"
        assert AuditSnapshotSectionKind.QUALITY_STATE.value == "quality_state"
        assert AuditSnapshotSectionKind.OPEN_ITEMS.value == "open_items"
        assert AuditSnapshotSectionKind.SAFETY_BOUNDARIES.value == "safety_boundaries"
        assert AuditSnapshotSectionKind.HUMAN_AUDIT_GUIDE.value == "human_audit_guide"
        assert AuditSnapshotSectionKind.APPENDIX_REFERENCES.value == "appendix_references"

    def test_deterministic_order(self) -> None:
        values = [kind.value for kind in CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER]
        assert values == [
            "overview",
            "version_state",
            "artifact_state",
            "quality_state",
            "open_items",
            "safety_boundaries",
            "human_audit_guide",
            "appendix_references",
        ]


class TestAuditSnapshotItemSeverity:
    def test_enum_values(self) -> None:
        assert AuditSnapshotItemSeverity.CRITICAL.value == "critical"
        assert AuditSnapshotItemSeverity.HIGH.value == "high"
        assert AuditSnapshotItemSeverity.MEDIUM.value == "medium"
        assert AuditSnapshotItemSeverity.LOW.value == "low"
        assert AuditSnapshotItemSeverity.INFO.value == "info"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

class TestAuditSnapshotReasonCodes:
    def test_reason_codes_complete(self) -> None:
        assert UNSAFE_SNAPSHOT_CONTENT in AUDIT_SNAPSHOT_REASON_CODES
        assert INVALID_SNAPSHOT_CONFIG in AUDIT_SNAPSHOT_REASON_CODES
        assert MISSING_REQUIRED_SECTION in AUDIT_SNAPSHOT_REASON_CODES
        assert MISSING_ARTIFACT_SUMMARIES in AUDIT_SNAPSHOT_REASON_CODES
        assert BLOCKED_ARTIFACT_ITEM in AUDIT_SNAPSHOT_REASON_CODES
        assert STALE_ARTIFACT_DETECTED in AUDIT_SNAPSHOT_REASON_CODES
        assert OPEN_ITEMS_PRESENT in AUDIT_SNAPSHOT_REASON_CODES
        assert INCOMPLETE_ARTIFACT_ITEM in AUDIT_SNAPSHOT_REASON_CODES
        assert UNKNOWN_SNAPSHOT_STATE in AUDIT_SNAPSHOT_REASON_CODES
        assert FILE_REFS_NOT_TRAVERSED in AUDIT_SNAPSHOT_REASON_CODES
        assert NO_ACTION_COMMANDS_EMITTED in AUDIT_SNAPSHOT_REASON_CODES
        assert HUMAN_AUDIT_GUIDE_NON_GATING in AUDIT_SNAPSHOT_REASON_CODES

    def test_blocking_partition(self) -> None:
        assert UNSAFE_SNAPSHOT_CONTENT in AUDIT_SNAPSHOT_BLOCKING_REASON_CODES
        assert BLOCKED_ARTIFACT_ITEM in AUDIT_SNAPSHOT_BLOCKING_REASON_CODES
        assert STALE_ARTIFACT_DETECTED not in AUDIT_SNAPSHOT_BLOCKING_REASON_CODES

    def test_incomplete_partition(self) -> None:
        assert OPEN_ITEMS_PRESENT in AUDIT_SNAPSHOT_INCOMPLETE_REASON_CODES
        assert INCOMPLETE_ARTIFACT_ITEM in AUDIT_SNAPSHOT_INCOMPLETE_REASON_CODES

    def test_stale_partition(self) -> None:
        assert STALE_ARTIFACT_DETECTED in AUDIT_SNAPSHOT_STALE_REASON_CODES

    def test_advisory_partition(self) -> None:
        assert FILE_REFS_NOT_TRAVERSED in AUDIT_SNAPSHOT_ADVISORY_REASON_CODES
        assert NO_ACTION_COMMANDS_EMITTED in AUDIT_SNAPSHOT_ADVISORY_REASON_CODES
        assert HUMAN_AUDIT_GUIDE_NON_GATING in AUDIT_SNAPSHOT_ADVISORY_REASON_CODES


# ---------------------------------------------------------------------------
# Forbidden terms
# ---------------------------------------------------------------------------

class TestForbiddenSnapshotTerms:
    def test_terms_are_lowercase(self) -> None:
        for term in FORBIDDEN_SNAPSHOT_TERMS:
            assert term == term.lower(), f"{term} is not lowercase"

    def test_dangerous_terms_present(self) -> None:
        assert "api_key" in FORBIDDEN_SNAPSHOT_TERMS
        assert "binance" in FORBIDDEN_SNAPSHOT_TERMS
        assert "execute_trade" in FORBIDDEN_SNAPSHOT_TERMS
        assert "release_approval" in FORBIDDEN_SNAPSHOT_TERMS
        assert "deploy" in FORBIDDEN_SNAPSHOT_TERMS
        assert "runtime_registry" in FORBIDDEN_SNAPSHOT_TERMS
        assert "index_files" in FORBIDDEN_SNAPSHOT_TERMS
        assert "transaction_permission" in FORBIDDEN_SNAPSHOT_TERMS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestEnsureTupleOfStr:
    def test_accepts_tuple(self) -> None:
        from hunter.research_audit_snapshot.models import _ensure_tuple_of_str
        assert _ensure_tuple_of_str(("a", "b"), "x") == ("a", "b")

    def test_accepts_list(self) -> None:
        from hunter.research_audit_snapshot.models import _ensure_tuple_of_str
        assert _ensure_tuple_of_str(["a", "b"], "x") == ("a", "b")

    def test_rejects_non_string_items(self) -> None:
        from hunter.research_audit_snapshot.models import _ensure_tuple_of_str
        with pytest.raises(ValueError, match="x must contain non-empty strings"):
            _ensure_tuple_of_str(("a", 1), "x")  # type: ignore[arg-type]

    def test_rejects_empty_strings(self) -> None:
        from hunter.research_audit_snapshot.models import _ensure_tuple_of_str
        with pytest.raises(ValueError, match="x must contain non-empty strings"):
            _ensure_tuple_of_str(("a", ""), "x")


class TestHasForbiddenSnapshotTerm:
    def test_detects_forbidden_term(self) -> None:
        from hunter.research_audit_snapshot.models import _has_forbidden_snapshot_term
        assert _has_forbidden_snapshot_term("contains api_key value") is True

    def test_case_insensitive(self) -> None:
        from hunter.research_audit_snapshot.models import _has_forbidden_snapshot_term
        assert _has_forbidden_snapshot_term("Contains API_KEY Value") is True

    def test_safe_text(self) -> None:
        from hunter.research_audit_snapshot.models import _has_forbidden_snapshot_term
        assert _has_forbidden_snapshot_term("safe text") is False


class TestCheckForbiddenSnapshotContent:
    def test_raises_on_forbidden_text(self) -> None:
        from hunter.research_audit_snapshot.models import _check_forbidden_snapshot_content
        with pytest.raises(ValueError, match="UNSAFE_SNAPSHOT_CONTENT"):
            _check_forbidden_snapshot_content(("api_key",), (), {})

    def test_raises_on_forbidden_metadata(self) -> None:
        from hunter.research_audit_snapshot.models import _check_forbidden_snapshot_content
        with pytest.raises(ValueError, match="UNSAFE_SNAPSHOT_CONTENT"):
            _check_forbidden_snapshot_content((), (), {"note": "deploy now"})

    def test_raises_on_nested_metadata(self) -> None:
        from hunter.research_audit_snapshot.models import _check_forbidden_snapshot_content
        with pytest.raises(ValueError, match="UNSAFE_SNAPSHOT_CONTENT"):
            _check_forbidden_snapshot_content((), (), {"outer": {"inner": "secret"}})


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestAuditSnapshotConfig:
    def test_defaults_are_safe(self) -> None:
        config = AuditSnapshotConfig()
        assert config.dry_run is True
        assert config.live_trading_enabled is False
        assert config.block_on_unknown is True
        assert config.block_on_incomplete is False
        assert config.block_on_stale is False
        assert config.expected_artifact_count == 13

    def test_dry_run_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            AuditSnapshotConfig(dry_run=False)

    def test_live_trading_flags_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="live trading flags must be False"):
            AuditSnapshotConfig(real_orders_enabled=True)

    def test_invalid_output_format(self) -> None:
        with pytest.raises(ValueError, match="output_format must be json, markdown, or both"):
            AuditSnapshotConfig(output_format="xml")

    def test_negative_freshness(self) -> None:
        with pytest.raises(ValueError, match="freshness_threshold_seconds must be a non-negative integer"):
            AuditSnapshotConfig(freshness_threshold_seconds=-1)


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------

class TestAuditSnapshotSafetyFlags:
    def test_defaults_are_safe(self) -> None:
        flags = AuditSnapshotSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.snapshot_output_is_human_audit_only is True
        assert flags.snapshot_output_not_transaction_permission is True
        assert flags.file_refs_not_traversed is True
        assert flags.artifact_files_not_read is True
        assert flags.no_action_commands_emitted is True
        assert flags.human_audit_guide_is_non_gating is True

    def test_feedback_flag_unsafe(self) -> None:
        with pytest.raises(ValueError, match="unsafe audit snapshot safety flags are enabled"):
            AuditSnapshotSafetyFlags(snapshot_feedback_into_execution=True)

    def test_runtime_registry_flag_unsafe(self) -> None:
        with pytest.raises(ValueError, match="unsafe audit snapshot safety flags are enabled"):
            AuditSnapshotSafetyFlags(runtime_registry_enabled=True)

    def test_output_flag_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="safe audit snapshot output flags must be True"):
            AuditSnapshotSafetyFlags(snapshot_output_not_transaction_permission=False)


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------

class TestAuditSnapshotDataQuality:
    def test_default_is_valid(self) -> None:
        dq = AuditSnapshotDataQuality()
        assert dq.total_artifacts_expected == 13
        assert dq.total_artifacts_present == 0
        assert dq.total_artifacts_missing == 13
        assert dq.total_artifacts_present + dq.total_artifacts_missing == dq.total_artifacts_expected
        assert dq.sections_expected == 8
        assert dq.sections_present == 0
        assert dq.sections_missing == 8
        assert dq.sections_present + dq.sections_missing == dq.sections_expected

    def test_invalid_artifact_arithmetic(self) -> None:
        with pytest.raises(ValueError, match=r"present \+ missing must equal expected"):
            AuditSnapshotDataQuality(total_artifacts_expected=13, total_artifacts_present=5, total_artifacts_missing=5)

    def test_invalid_section_arithmetic(self) -> None:
        with pytest.raises(ValueError, match=r"sections_present \+ sections_missing must equal sections_expected"):
            AuditSnapshotDataQuality(sections_expected=8, sections_present=3, sections_missing=3)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestAuditSnapshotSummary:
    def test_default_is_valid(self) -> None:
        summary = AuditSnapshotSummary()
        assert summary.snapshot_state == "UNKNOWN"
        assert summary.total_items == 0

    def test_severity_counts_must_sum(self) -> None:
        with pytest.raises(ValueError, match="severity counts must sum to total_items"):
            AuditSnapshotSummary(
                total_items=2,
                critical_count=1,
                high_count=0,
                current_count=2,  # state counts are valid
                snapshot_state="CURRENT",
            )

    def test_state_counts_must_sum(self) -> None:
        with pytest.raises(ValueError, match="state counts must sum to total_items"):
            AuditSnapshotSummary(
                total_items=2,
                critical_count=1,
                high_count=1,  # severity counts are valid
                current_count=1,
                stale_count=2,  # state counts are invalid: 1+2 != 2
                snapshot_state="STALE",
            )


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

class TestAuditSnapshotItem:
    def test_builds_item(self) -> None:
        item = AuditSnapshotItem(item_id="i-1", title="Title")
        assert item.item_id == "i-1"
        assert item.title == "Title"
        assert item.severity == "INFO"
        assert item.state == "UNKNOWN"

    def test_severity_normalized_to_upper(self) -> None:
        item = AuditSnapshotItem(item_id="i-1", title="Title", severity="high")
        assert item.severity == "HIGH"

    def test_invalid_severity(self) -> None:
        with pytest.raises(ValueError, match="unsupported severity"):
            AuditSnapshotItem(item_id="i-1", title="Title", severity="urgent")

    def test_empty_item_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="item_id must be a non-empty string"):
            AuditSnapshotItem(item_id="", title="Title")

    def test_invalid_reason_code(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            AuditSnapshotItem(item_id="i-1", title="Title", reason_codes=("BAD_CODE",))

    def test_forbidden_content_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_SNAPSHOT_CONTENT"):
            AuditSnapshotItem(item_id="i-1", title="deploy now")

    def test_frozen(self) -> None:
        item = AuditSnapshotItem(item_id="i-1", title="Title")
        with pytest.raises(FrozenInstanceError):
            item.title = "New"  # type: ignore[misc]

    def test_metadata_is_mapping_proxy(self) -> None:
        item = AuditSnapshotItem(item_id="i-1", title="Title", metadata={"x": 1})
        assert isinstance(item.metadata, MappingProxyType)


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------

class TestAuditSnapshotSection:
    def test_builds_section(self) -> None:
        section = AuditSnapshotSection(
            section_kind=AuditSnapshotSectionKind.OVERVIEW,
            title="Overview",
        )
        assert section.section_kind == AuditSnapshotSectionKind.OVERVIEW

    def test_items_ordered(self) -> None:
        item_high = AuditSnapshotItem(item_id="h", title="H", severity="HIGH")
        item_info = AuditSnapshotItem(item_id="i", title="I", severity="INFO")
        section = AuditSnapshotSection(
            section_kind=AuditSnapshotSectionKind.ARTIFACT_STATE,
            title="Artifacts",
            items=(item_info, item_high),
        )
        assert section.items[0].severity == "HIGH"
        assert section.items[1].severity == "INFO"


# ---------------------------------------------------------------------------
# ResearchAuditSnapshot
# ---------------------------------------------------------------------------

class TestResearchAuditSnapshot:
    def test_requires_snapshot_id(self) -> None:
        with pytest.raises(ValueError, match="snapshot_id must be a non-empty string"):
            ResearchAuditSnapshot(snapshot_id="")

    def test_empty_snapshot_id_default_rejected(self) -> None:
        # snapshot_id has no default, so this is a TypeError at construction time.
        with pytest.raises(TypeError):
            ResearchAuditSnapshot()  # type: ignore[call-arg]

    def test_valid_minimal(self) -> None:
        snap = ResearchAuditSnapshot(snapshot_id="snap-1")
        assert snap.snapshot_id == "snap-1"
        assert snap.kind == AuditSnapshotKind.RESEARCH_AUDIT_SNAPSHOT

    def test_block_requires_reason_codes(self) -> None:
        summary = AuditSnapshotSummary(snapshot_state="BLOCK")
        with pytest.raises(ValueError, match="reason_codes must be non-empty when snapshot_state is BLOCK or UNKNOWN"):
            ResearchAuditSnapshot(
                snapshot_id="snap-1",
                summary=summary,
                reason_codes=(),
            )

    def test_blocked_factory(self) -> None:
        snap = ResearchAuditSnapshot.blocked(reason_code=UNSAFE_SNAPSHOT_CONTENT)
        assert snap.snapshot_id == "blocked"
        assert snap.summary.snapshot_state == "BLOCK"
        assert UNSAFE_SNAPSHOT_CONTENT in snap.reason_codes
        assert snap.data_quality.total_artifacts_missing == 13
        assert snap.data_quality.sections_missing == 8

    def test_blocked_factory_invalid_reason_code(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            ResearchAuditSnapshot.blocked(reason_code="NOT_A_CODE")

    def test_frozen(self) -> None:
        snap = ResearchAuditSnapshot(snapshot_id="snap-1")
        with pytest.raises(FrozenInstanceError):
            snap.snapshot_id = "other"  # type: ignore[misc]

    def test_no_path_traversal(self) -> None:
        snap = ResearchAuditSnapshot(
            snapshot_id="snap-1",
            metadata={
                "local_reference": "data/observation/latest_observation_report.json",
                "spec_reference": "SPEC-011",
            },
        )
        assert snap.metadata["local_reference"] == "data/observation/latest_observation_report.json"

    def test_suspicious_path_string_is_not_opened(self) -> None:
        # Local references are plain strings; the model does not open them.
        snap = ResearchAuditSnapshot(
            snapshot_id="snap-1",
            metadata={"ref": "rm -rf /"},
        )
        assert snap.metadata["ref"] == "rm -rf /"

    def test_no_action_command_in_metadata(self) -> None:
        # The forbidden-term scanner will reject action-command terms in metadata values.
        with pytest.raises(ValueError, match="UNSAFE_SNAPSHOT_CONTENT"):
            ResearchAuditSnapshot(
                snapshot_id="snap-1",
                metadata={"command": "trigger deployment"},
            )

    def test_no_release_approval_semantics(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_SNAPSHOT_CONTENT"):
            ResearchAuditSnapshot(
                snapshot_id="snap-1",
                metadata={"note": "release approval granted"},
            )

    def test_no_trading_semantics(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_SNAPSHOT_CONTENT"):
            ResearchAuditSnapshot(
                snapshot_id="snap-1",
                metadata={"note": "place a live trade"},
            )

    def test_invalid_reason_code(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            ResearchAuditSnapshot(snapshot_id="snap-1", reason_codes=("BAD",))
