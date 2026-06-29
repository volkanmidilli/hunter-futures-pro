"""Tests for hunter.chronicle.models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from hunter.chronicle.models import (
    CHRONICLE_BLOCKING_REASON_CODES,
    CHRONICLE_REASON_CODES,
    CHRONICLE_TRACKING_REASON_CODES,
    CHRONICLE_VERSION,
    ArtifactType,
    ChronicleDataQuality,
    ChronicleEntry,
    ChronicleSafetyFlags,
    ChronicleSummary,
    FORBIDDEN_CHRONICLE_TERMS,
    ResearchChronicle,
)


# ---------------------------------------------------------------------------
# ChronicleEntry
# ---------------------------------------------------------------------------


class TestChronicleEntry:
    """Tests for ChronicleEntry frozen dataclass."""

    def test_valid_construction(self) -> None:
        now = datetime.now(timezone.utc)
        entry = ChronicleEntry(
            entry_id="obs:trace1:2025-01-01T00:00:00",
            timestamp=now,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace1",
            state="READY",
            version="1.0",
            entry_count=5,
            reason_codes=("REASON1",),
            actor="system",
            notes="test notes",
            tags=("tag1", "tag2"),
            metadata={"key": "value"},
            related_trace_ids=("trace2",),
        )
        assert entry.entry_id == "obs:trace1:2025-01-01T00:00:00"
        assert entry.timestamp == now
        assert entry.artifact_type is ArtifactType.OBSERVATION
        assert entry.trace_id == "trace1"
        assert entry.state == "READY"
        assert entry.version == "1.0"
        assert entry.entry_count == 5
        assert entry.reason_codes == ("REASON1",)
        assert entry.actor == "system"
        assert entry.notes == "test notes"
        assert entry.tags == ("tag1", "tag2")
        assert entry.metadata == {"key": "value"}
        assert entry.related_trace_ids == ("trace2",)

    def test_default_values(self) -> None:
        now = datetime.now(timezone.utc)
        entry = ChronicleEntry(
            entry_id="id1",
            timestamp=now,
            artifact_type=ArtifactType.REVIEW,
            trace_id="t1",
            state="BLOCKED",
            version="1.0",
        )
        assert entry.entry_count == 0
        assert entry.reason_codes == ()
        assert entry.actor is None
        assert entry.notes is None
        assert entry.tags == ()
        assert entry.metadata == {}
        assert entry.related_trace_ids == ()

    def test_invalid_entry_id_empty(self) -> None:
        with pytest.raises(ValueError, match="entry_id must be a non-empty string"):
            ChronicleEntry(
                entry_id="",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
            )

    def test_invalid_entry_id_type(self) -> None:
        with pytest.raises(ValueError, match="entry_id must be a non-empty string"):
            ChronicleEntry(
                entry_id=123,  # type: ignore[arg-type]
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
            )

    def test_invalid_timestamp_naive(self) -> None:
        with pytest.raises(ValueError, match="timestamp must be a timezone-aware datetime"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(),  # naive
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
            )

    def test_invalid_timestamp_none(self) -> None:
        with pytest.raises(ValueError, match="timestamp must be a timezone-aware datetime"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=None,  # type: ignore[arg-type]
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
            )

    def test_invalid_artifact_type_str(self) -> None:
        with pytest.raises(ValueError, match="artifact_type must be an ArtifactType"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type="observation",  # type: ignore[arg-type]
                trace_id="t1",
                state="READY",
                version="1.0",
            )

    def test_invalid_artifact_type_none(self) -> None:
        with pytest.raises(ValueError, match="artifact_type must be an ArtifactType"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=None,  # type: ignore[arg-type]
                trace_id="t1",
                state="READY",
                version="1.0",
            )

    def test_invalid_trace_id_empty(self) -> None:
        with pytest.raises(ValueError, match="trace_id must be a non-empty string"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="",
                state="READY",
                version="1.0",
            )

    def test_invalid_state_empty(self) -> None:
        with pytest.raises(ValueError, match="state must be a non-empty string"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="",
                version="1.0",
            )

    def test_invalid_version_empty(self) -> None:
        with pytest.raises(ValueError, match="version must be a non-empty string"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="",
            )

    def test_invalid_entry_count_negative(self) -> None:
        with pytest.raises(ValueError, match="entry_count must be >= 0"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                entry_count=-1,
            )

    def test_invalid_entry_count_type(self) -> None:
        with pytest.raises(ValueError, match="entry_count must be >= 0"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                entry_count="5",  # type: ignore[arg-type]
            )

    def test_invalid_reason_codes_type(self) -> None:
        with pytest.raises(ValueError, match="reason_codes must be a tuple"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                reason_codes=["REASON"],  # type: ignore[arg-type]
            )

    def test_invalid_reason_codes_empty_string(self) -> None:
        with pytest.raises(ValueError, match="reason_codes must contain non-empty strings"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                reason_codes=("",),
            )

    def test_invalid_actor_empty(self) -> None:
        with pytest.raises(ValueError, match="actor must be a non-empty string or None"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                actor="",
            )

    def test_invalid_notes_forbidden(self) -> None:
        with pytest.raises(ValueError, match="notes contains forbidden content"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                notes="enter_long now",
            )

    def test_invalid_tags_type(self) -> None:
        with pytest.raises(ValueError, match="tags must be a tuple"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                tags=["tag"],  # type: ignore[arg-type]
            )

    def test_invalid_tags_forbidden(self) -> None:
        with pytest.raises(ValueError, match="tags contain forbidden content"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                tags=("enter_long",),
            )

    def test_invalid_metadata_type(self) -> None:
        with pytest.raises(ValueError, match="metadata must be a Mapping"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                metadata=["not", "mapping"],  # type: ignore[arg-type]
            )

    def test_invalid_metadata_forbidden_key(self) -> None:
        with pytest.raises(ValueError, match="metadata key contains forbidden content"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                metadata={"api_key": "secret"},
            )

    def test_invalid_related_trace_ids(self) -> None:
        with pytest.raises(ValueError, match="related_trace_ids must be a tuple"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                related_trace_ids=["t2"],  # type: ignore[arg-type]
            )

    def test_invalid_related_trace_ids_empty(self) -> None:
        with pytest.raises(ValueError, match="related_trace_ids must contain non-empty strings"):
            ChronicleEntry(
                entry_id="id1",
                timestamp=datetime.now(timezone.utc),
                artifact_type=ArtifactType.OBSERVATION,
                trace_id="t1",
                state="READY",
                version="1.0",
                related_trace_ids=("",),
            )

    def test_blocked_factory(self) -> None:
        entry = ChronicleEntry.blocked()
        assert entry.state == "BLOCKED"
        assert entry.reason_codes == ("CHRONICLE_ERROR",)
        assert entry.version == CHRONICLE_VERSION
        assert entry.entry_count == 0

    def test_blocked_factory_with_custom(self) -> None:
        now = datetime.now(timezone.utc)
        entry = ChronicleEntry.blocked(
            entry_id="custom",
            timestamp=now,
            artifact_type=ArtifactType.REVIEW,
            trace_id="custom-trace",
            state="UNKNOWN",
            version="2.0",
            reason_codes=("MISSING_ARTIFACTS",),
        )
        assert entry.entry_id == "custom"
        assert entry.timestamp == now
        assert entry.artifact_type is ArtifactType.REVIEW
        assert entry.trace_id == "custom-trace"
        assert entry.state == "UNKNOWN"
        assert entry.version == "2.0"
        assert entry.reason_codes == ("MISSING_ARTIFACTS",)

    def test_immutable(self) -> None:
        entry = ChronicleEntry(
            entry_id="id1",
            timestamp=datetime.now(timezone.utc),
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="t1",
            state="READY",
            version="1.0",
        )
        with pytest.raises(FrozenInstanceError):
            entry.state = "BLOCKED"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ChronicleSummary
# ---------------------------------------------------------------------------


class TestChronicleSummary:
    """Tests for ChronicleSummary frozen dataclass."""

    def test_default_construction(self) -> None:
        summary = ChronicleSummary()
        assert summary.total_entries == 0
        assert summary.observation_count == 0

    def test_valid_construction(self) -> None:
        summary = ChronicleSummary(
            total_entries=10,
            observation_count=3,
            review_count=2,
            index_count=1,
            search_count=1,
            bundle_count=3,
            blocked_count=2,
            ready_count=7,
            unknown_count=1,
            accepted_count=2,
            rejected_count=1,
            reason_code_counts={"CODE": 5},
            tag_counts={"tag": 3},
            actor_counts={"sys": 2},
            timestamp_range=("2025-01-01T00:00:00", "2025-01-02T00:00:00"),
            daily_counts={"2025-01-01": {"observation": 3}},
        )
        assert summary.total_entries == 10
        assert summary.observation_count == 3

    def test_invalid_total_entries_negative(self) -> None:
        with pytest.raises(ValueError, match="total_entries must be >= 0"):
            ChronicleSummary(total_entries=-1)

    def test_invalid_type_counts_exceed_total(self) -> None:
        with pytest.raises(ValueError, match="type counts must not exceed total_entries"):
            ChronicleSummary(
                total_entries=1,
                observation_count=1,
                review_count=1,
            )

    def test_invalid_state_counts_exceed_total(self) -> None:
        with pytest.raises(ValueError, match="state counts must not exceed total_entries"):
            ChronicleSummary(
                total_entries=1,
                blocked_count=1,
                ready_count=1,
                unknown_count=1,
            )

    def test_invalid_status_counts_exceed_total(self) -> None:
        with pytest.raises(ValueError, match="status counts.*must not exceed total_entries"):
            ChronicleSummary(
                total_entries=1,
                accepted_count=1,
                rejected_count=1,
            )

    def test_invalid_reason_code_counts(self) -> None:
        with pytest.raises(ValueError, match="reason_code_counts keys must be non-empty strings"):
            ChronicleSummary(reason_code_counts={"": 1})

    def test_invalid_reason_code_counts_negative(self) -> None:
        with pytest.raises(ValueError, match="reason_code_counts value for 'CODE' must be >= 0"):
            ChronicleSummary(reason_code_counts={"CODE": -1})

    def test_invalid_tag_counts(self) -> None:
        with pytest.raises(ValueError, match="tag_counts keys must be non-empty strings"):
            ChronicleSummary(tag_counts={"": 1})

    def test_invalid_actor_counts(self) -> None:
        with pytest.raises(ValueError, match="actor_counts keys must be non-empty strings"):
            ChronicleSummary(actor_counts={"": 1})

    def test_invalid_timestamp_range(self) -> None:
        with pytest.raises(ValueError, match="timestamp_range must be a tuple of two strings"):
            ChronicleSummary(timestamp_range=("a",))  # type: ignore[arg-type]

    def test_invalid_timestamp_range_empty(self) -> None:
        with pytest.raises(ValueError, match="timestamp_range values must be non-empty strings"):
            ChronicleSummary(timestamp_range=("", ""))

    def test_invalid_daily_counts(self) -> None:
        with pytest.raises(ValueError, match="daily_counts keys must be non-empty strings"):
            ChronicleSummary(daily_counts={"": {}})

    def test_invalid_daily_counts_inner(self) -> None:
        with pytest.raises(ValueError, match="daily_counts inner keys must be non-empty strings"):
            ChronicleSummary(daily_counts={"2025-01-01": {"": -1}})

    def test_immutable(self) -> None:
        summary = ChronicleSummary()
        with pytest.raises(FrozenInstanceError):
            summary.total_entries = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ChronicleDataQuality
# ---------------------------------------------------------------------------


class TestChronicleDataQuality:
    """Tests for ChronicleDataQuality frozen dataclass."""

    def test_default_construction(self) -> None:
        dq = ChronicleDataQuality()
        assert dq.has_observations is False
        assert dq.orphan_observation_count == 0
        assert dq.trace_completeness_pct == 0.0

    def test_valid_construction(self) -> None:
        dq = ChronicleDataQuality(
            has_observations=True,
            has_reviews=True,
            has_index=True,
            has_search=True,
            has_bundle=True,
            orphan_observation_count=1,
            orphan_review_count=2,
            trace_completeness_pct=50.0,
            gap_count=1,
            stale_entry_count=3,
            validation_errors=("err1", "err2"),
        )
        assert dq.has_observations is True
        assert dq.orphan_observation_count == 1
        assert dq.trace_completeness_pct == 50.0

    def test_invalid_orphan_count_negative(self) -> None:
        with pytest.raises(ValueError, match="orphan_observation_count must be >= 0"):
            ChronicleDataQuality(orphan_observation_count=-1)

    def test_invalid_trace_completeness_negative(self) -> None:
        with pytest.raises(ValueError, match="trace_completeness_pct must be between 0.0 and 100.0"):
            ChronicleDataQuality(trace_completeness_pct=-1.0)

    def test_invalid_trace_completeness_over_100(self) -> None:
        with pytest.raises(ValueError, match="trace_completeness_pct must be between 0.0 and 100.0"):
            ChronicleDataQuality(trace_completeness_pct=101.0)

    def test_invalid_trace_completeness_type(self) -> None:
        with pytest.raises(ValueError, match="trace_completeness_pct must be a number"):
            ChronicleDataQuality(trace_completeness_pct="50")  # type: ignore[arg-type]

    def test_invalid_validation_errors_type(self) -> None:
        with pytest.raises(ValueError, match="validation_errors must be a tuple"):
            ChronicleDataQuality(validation_errors=["err"])  # type: ignore[arg-type]

    def test_invalid_validation_errors_empty(self) -> None:
        with pytest.raises(ValueError, match="validation_errors must contain non-empty strings"):
            ChronicleDataQuality(validation_errors=("",))

    def test_immutable(self) -> None:
        dq = ChronicleDataQuality()
        with pytest.raises(FrozenInstanceError):
            dq.has_observations = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ChronicleSafetyFlags
# ---------------------------------------------------------------------------


class TestChronicleSafetyFlags:
    """Tests for ChronicleSafetyFlags frozen dataclass."""

    def test_default_construction(self) -> None:
        flags = ChronicleSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.chronicle_output_is_human_audit_only is True
        assert flags.chronicle_feedback_into_execution is False

    def test_unsafe_live_trading(self) -> None:
        with pytest.raises(ValueError, match="unsafe chronicle safety flags are enabled"):
            ChronicleSafetyFlags(live_trading_enabled=True)

    def test_unsafe_real_orders(self) -> None:
        with pytest.raises(ValueError, match="unsafe chronicle safety flags are enabled"):
            ChronicleSafetyFlags(real_orders_enabled=True)

    def test_unsafe_leverage(self) -> None:
        with pytest.raises(ValueError, match="unsafe chronicle safety flags are enabled"):
            ChronicleSafetyFlags(leverage_enabled=True)

    def test_unsafe_shorting(self) -> None:
        with pytest.raises(ValueError, match="unsafe chronicle safety flags are enabled"):
            ChronicleSafetyFlags(shorting_enabled=True)

    def test_unsafe_feedback_into_execution(self) -> None:
        with pytest.raises(ValueError, match="unsafe chronicle safety flags are enabled"):
            ChronicleSafetyFlags(chronicle_feedback_into_execution=True)

    def test_missing_safe_flag(self) -> None:
        with pytest.raises(ValueError, match="safe chronicle output flags must be True"):
            ChronicleSafetyFlags(chronicle_output_is_human_audit_only=False)

    def test_immutable(self) -> None:
        flags = ChronicleSafetyFlags()
        with pytest.raises(FrozenInstanceError):
            flags.dry_run = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ResearchChronicle
# ---------------------------------------------------------------------------


class TestResearchChronicle:
    """Tests for ResearchChronicle frozen dataclass."""

    def test_default_construction(self) -> None:
        now = datetime.now(timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=now,
        )
        assert chronicle.chronicle_id == "chronicle-1"
        assert chronicle.generated_at == now
        assert chronicle.version == CHRONICLE_VERSION
        assert chronicle.entries == ()
        assert chronicle.reason_codes == ()

    def test_with_entries(self) -> None:
        now = datetime.now(timezone.utc)
        entry = ChronicleEntry(
            entry_id="e1",
            timestamp=now,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="t1",
            state="READY",
            version="1.0",
        )
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=now,
            entries=(entry,),
            reason_codes=("MISSING_ARTIFACTS",),
        )
        assert len(chronicle.entries) == 1
        assert chronicle.reason_codes == ("MISSING_ARTIFACTS",)

    def test_invalid_chronicle_id_empty(self) -> None:
        with pytest.raises(ValueError, match="chronicle_id must be a non-empty string"):
            ResearchChronicle(
                chronicle_id="",
                generated_at=datetime.now(timezone.utc),
            )

    def test_invalid_generated_at_naive(self) -> None:
        with pytest.raises(ValueError, match="generated_at must be a timezone-aware datetime"):
            ResearchChronicle(
                chronicle_id="c1",
                generated_at=datetime.now(),  # naive
            )

    def test_invalid_entries_type(self) -> None:
        with pytest.raises(ValueError, match="entries must be a tuple"):
            ResearchChronicle(
                chronicle_id="c1",
                generated_at=datetime.now(timezone.utc),
                entries=["not-an-entry"],  # type: ignore[arg-type]
            )

    def test_invalid_entries_element(self) -> None:
        with pytest.raises(ValueError, match="entries must contain ChronicleEntry values"):
            ResearchChronicle(
                chronicle_id="c1",
                generated_at=datetime.now(timezone.utc),
                entries=("not-an-entry",),  # type: ignore[arg-type]
            )

    def test_invalid_reason_codes(self) -> None:
        with pytest.raises(ValueError, match="reason_codes must be a tuple"):
            ResearchChronicle(
                chronicle_id="c1",
                generated_at=datetime.now(timezone.utc),
                reason_codes=["CODE"],  # type: ignore[arg-type]
            )

    def test_invalid_reason_codes_empty(self) -> None:
        with pytest.raises(ValueError, match="reason_codes must contain non-empty strings"):
            ResearchChronicle(
                chronicle_id="c1",
                generated_at=datetime.now(timezone.utc),
                reason_codes=("",),
            )

    def test_blocked_factory(self) -> None:
        chronicle = ResearchChronicle.blocked()
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("CHRONICLE_ERROR",)
        assert chronicle.version == CHRONICLE_VERSION

    def test_blocked_factory_with_custom(self) -> None:
        now = datetime.now(timezone.utc)
        chronicle = ResearchChronicle.blocked(
            reason="MISSING_ARTIFACTS",
            chronicle_id="custom-id",
            generated_at=now,
        )
        assert chronicle.chronicle_id == "custom-id"
        assert chronicle.reason_codes == ("MISSING_ARTIFACTS",)
        assert chronicle.generated_at == now

    def test_immutable(self) -> None:
        chronicle = ResearchChronicle(
            chronicle_id="c1",
            generated_at=datetime.now(timezone.utc),
        )
        with pytest.raises(FrozenInstanceError):
            chronicle.chronicle_id = "c2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestChronicleConstants:
    """Tests for chronicle constants and reason codes."""

    def test_chronicle_version(self) -> None:
        assert CHRONICLE_VERSION == "1.0"

    def test_blocking_reason_codes_are_tuple(self) -> None:
        assert isinstance(CHRONICLE_BLOCKING_REASON_CODES, tuple)
        assert all(isinstance(code, str) for code in CHRONICLE_BLOCKING_REASON_CODES)

    def test_tracking_reason_codes_are_tuple(self) -> None:
        assert isinstance(CHRONICLE_TRACKING_REASON_CODES, tuple)
        assert all(isinstance(code, str) for code in CHRONICLE_TRACKING_REASON_CODES)

    def test_combined_reason_codes(self) -> None:
        assert CHRONICLE_REASON_CODES == CHRONICLE_BLOCKING_REASON_CODES + CHRONICLE_TRACKING_REASON_CODES

    def test_forbidden_terms_is_frozenset(self) -> None:
        assert isinstance(FORBIDDEN_CHRONICLE_TERMS, frozenset)
        assert "api_key" in FORBIDDEN_CHRONICLE_TERMS
        assert "enter_long" in FORBIDDEN_CHRONICLE_TERMS

    def test_blocking_reason_codes_priority_order(self) -> None:
        assert CHRONICLE_BLOCKING_REASON_CODES[0] == "MISSING_ARTIFACTS"
        assert CHRONICLE_BLOCKING_REASON_CODES[-1] == "CHRONICLE_ERROR"
        assert CHRONICLE_BLOCKING_REASON_CODES.index("INVALID_TIMESTAMP") < CHRONICLE_BLOCKING_REASON_CODES.index("CHRONICLE_ERROR")

    def test_tracking_reason_codes_not_in_blocking(self) -> None:
        for code in CHRONICLE_TRACKING_REASON_CODES:
            assert code not in CHRONICLE_BLOCKING_REASON_CODES

    def test_invalid_timestamp_in_blocking(self) -> None:
        assert "INVALID_TIMESTAMP" in CHRONICLE_BLOCKING_REASON_CODES

    def test_missing_trace_id_in_blocking(self) -> None:
        assert "MISSING_TRACE_ID" in CHRONICLE_BLOCKING_REASON_CODES

    def test_all_reason_codes_unique(self) -> None:
        assert len(CHRONICLE_REASON_CODES) == len(set(CHRONICLE_REASON_CODES))

    def test_forbidden_terms_not_empty(self) -> None:
        assert len(FORBIDDEN_CHRONICLE_TERMS) > 0
        assert "leverage" in FORBIDDEN_CHRONICLE_TERMS

    def test_forbidden_terms_no_whitespace(self) -> None:
        for term in FORBIDDEN_CHRONICLE_TERMS:
            assert term == term.strip()
