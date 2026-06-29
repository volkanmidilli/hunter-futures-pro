"""Tests for hunter.chronicle.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.chronicle.engine import (
    build_chronicle_data_quality,
    build_chronicle_entry_from_bundle,
    build_chronicle_entry_from_index,
    build_chronicle_entry_from_observation,
    build_chronicle_entry_from_review,
    build_chronicle_entry_from_search,
    build_chronicle_summary,
    build_research_chronicle,
    has_unsafe_chronicle_content,
)
from hunter.chronicle.models import (
    CHRONICLE_VERSION,
    ArtifactType,
    ChronicleEntry,
)
from hunter.observation.models import (
    ObservationDataQuality,
    ObservationReport,
    ObservationSafetyFlags,
    ObservationSignal,
    ObservationState,
    ObservationWindow,
    SignalObservation,
)
from hunter.research_bundle.models import (
    BundleDataQuality,
    BundleItem,
    BundleItemKind,
    BundleSafetyFlags,
    BundleSummary,
    BundleState,
    ResearchBundle,
)
from hunter.review.models import (
    ReviewAuditRecord,
    ReviewAuditSummary,
    ReviewDataQuality,
    ReviewRecord,
    ReviewSafetyFlags,
    ReviewState,
    ReviewStatus,
)
from hunter.review_index.models import (
    IndexDataQuality,
    IndexEntry,
    IndexEntryKind,
    IndexSafetyFlags,
    IndexState,
    IndexSummary,
    ReviewIndex,
)
from hunter.review_search.models import (
    SearchQuery,
    SearchResult,
    SearchResultEntry,
    SearchResultSummary,
    SearchSafetyFlags,
    SearchState,
)


# ---------------------------------------------------------------------------
# has_unsafe_chronicle_content
# ---------------------------------------------------------------------------


class TestHasUnsafeChronicleContent:
    """Tests for has_unsafe_chronicle_content."""

    def test_safe_text(self) -> None:
        assert has_unsafe_chronicle_content("normal research notes") is False

    def test_forbidden_term_enter_long(self) -> None:
        assert has_unsafe_chronicle_content("enter_long signal") is True

    def test_forbidden_term_api_key(self) -> None:
        assert has_unsafe_chronicle_content("contains api_key") is True

    def test_case_insensitive(self) -> None:
        assert has_unsafe_chronicle_content("ENTER_LONG") is True

    def test_empty_text(self) -> None:
        assert has_unsafe_chronicle_content("") is False

    def test_forbidden_term_leverage(self) -> None:
        assert has_unsafe_chronicle_content("high leverage") is True


# ---------------------------------------------------------------------------
# build_chronicle_entry_from_observation
# ---------------------------------------------------------------------------


class TestBuildChronicleEntryFromObservation:
    """Tests for build_chronicle_entry_from_observation."""

    def _observation(self, generated_at: datetime | None = None) -> ObservationReport:
        if generated_at is None:
            generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = SignalObservation(
            timestamp=generated_at,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="READY",
            source_signal_exposure="LONG",
            reason_codes=("READY",),
        )
        window = ObservationWindow(
            started_at=generated_at,
            ended_at=generated_at,
            observations=(obs,),
        )
        return ObservationReport(
            generated_at=generated_at,
            report_state=ObservationState.READY,
            window=window,
            reason_codes=("READY",),
            version="1.0",
        )

    def test_from_model(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        report = self._observation(generated_at)
        entry = build_chronicle_entry_from_observation(report)
        assert entry.artifact_type is ArtifactType.OBSERVATION
        assert entry.trace_id == f"observation:2025-01-01T12:00:00:1.0"
        assert entry.entry_id == f"observation:{entry.trace_id}:2025-01-01T12:00:00"
        assert entry.state == "READY"
        assert entry.version == "1.0"
        assert entry.entry_count == 1
        assert entry.reason_codes == ("READY",)

    def test_from_dict(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        report_dict = {
            "generated_at": generated_at,
            "report_state": "READY",
            "version": "1.0",
            "window": {
                "started_at": generated_at,
                "ended_at": generated_at,
                "observations": (),
            },
            "reason_codes": ("READY",),
        }
        entry = build_chronicle_entry_from_observation(report_dict)
        assert entry.artifact_type is ArtifactType.OBSERVATION
        assert entry.trace_id == "observation:2025-01-01T12:00:00:1.0"

    def test_missing_generated_at(self) -> None:
        with pytest.raises(ValueError, match="MISSING_TRACE_ID"):
            build_chronicle_entry_from_observation({})

    def test_naive_generated_at(self) -> None:
        naive = datetime(2025, 1, 1, 12, 0, 0)
        with pytest.raises(ValueError, match="MISSING_TRACE_ID"):
            build_chronicle_entry_from_observation({"generated_at": naive, "version": "1.0"})

    def test_missing_version(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="UNSUPPORTED_OBSERVATION_VERSION"):
            build_chronicle_entry_from_observation({"generated_at": generated_at})

    def test_entry_count_from_window(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs1 = SignalObservation(
            timestamp=generated_at,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="READY",
            source_signal_exposure="LONG",
            reason_codes=("READY",),
        )
        obs2 = SignalObservation(
            timestamp=generated_at,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.SHORT_RESEARCH,
            source_shell_state="READY",
            source_signal_exposure="SHORT",
            reason_codes=("READY",),
        )
        window = ObservationWindow(
            started_at=generated_at,
            ended_at=generated_at,
            observations=(obs1, obs2),
        )
        report = ObservationReport(
            generated_at=generated_at,
            report_state=ObservationState.READY,
            window=window,
            version="1.0",
        )
        entry = build_chronicle_entry_from_observation(report)
        assert entry.entry_count == 2

    def test_metadata_from_summary(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        report = self._observation(generated_at)
        object.__setattr__(report, "summary", {"count": 5})
        entry = build_chronicle_entry_from_observation(report)
        assert entry.metadata == {"count": 5}


# ---------------------------------------------------------------------------
# build_chronicle_entry_from_review
# ---------------------------------------------------------------------------


class TestBuildChronicleEntryFromReview:
    """Tests for build_chronicle_entry_from_review."""

    def _audit_record(self, generated_at: datetime | None = None) -> ReviewAuditRecord:
        if generated_at is None:
            generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        record = ReviewRecord(
            review_id="r1",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.ACCEPTED,
            reviewer="alice",
            notes="looks good",
            tags=(),
            reason_codes=("ACCEPTED",),
            reviewed_at=generated_at,
            safety_flags=ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
            ),
        )
        summary = ReviewAuditSummary(
            total_reviews=1,
            accepted_count=1,
            rejected_count=0,
            needs_investigation_count=0,
            not_reviewed_count=0,
            blocked_count=0,
            unknown_count=0,
            reason_counts={"ACCEPTED": 1},
        )
        data_quality = ReviewDataQuality(
            total_reports=1,
            valid_reports=1,
            blocked_reports=0,
            unknown_reports=0,
            unsafe_reports=0,
            missing_reports=0,
            invalid_reports=0,
        )
        safety_flags = ReviewSafetyFlags(
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            report_feedback_into_execution=False,
            operator_feedback_into_execution=False,
        )
        return ReviewAuditRecord(
            audit_id="audit-1",
            generated_at=generated_at,
            audit_state=ReviewState.READY,
            records=(record,),
            summary=summary,
            data_quality=data_quality,
            reason_codes=("READY",),
            safety_flags=safety_flags,
        )

    def test_from_model(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        audit = self._audit_record(generated_at)
        entry = build_chronicle_entry_from_review(audit)
        assert entry.artifact_type is ArtifactType.REVIEW
        assert entry.trace_id == f"review-audit:2025-01-01T12:00:00:1.0"
        assert entry.state == "READY"
        assert entry.version == "1.0"
        assert entry.entry_count == 1
        assert entry.reason_codes == ("READY",)

    def test_from_dict(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        audit_dict = {
            "generated_at": generated_at,
            "audit_state": ReviewState.READY,
            "records": (),
            "reason_codes": ("READY",),
        }
        entry = build_chronicle_entry_from_review(audit_dict)
        assert entry.artifact_type is ArtifactType.REVIEW
        assert entry.entry_count == 0

    def test_missing_generated_at(self) -> None:
        with pytest.raises(ValueError, match="INVALID_TIMESTAMP"):
            build_chronicle_entry_from_review({})

    def test_related_trace_ids(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        audit = self._audit_record(generated_at)
        entry = build_chronicle_entry_from_review(audit, related_trace_ids=("trace-a", "trace-b"))
        assert entry.related_trace_ids == ("trace-a", "trace-b")

    def test_entry_count_from_records(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        record1 = ReviewRecord(
            review_id="r1",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.ACCEPTED,
            reviewer="alice",
            notes="ok",
            tags=(),
            reason_codes=("ACCEPTED",),
            reviewed_at=generated_at,
            safety_flags=ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
            ),
        )
        record2 = ReviewRecord(
            review_id="r2",
            source_report_id="rep2",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.REJECTED,
            reviewer="bob",
            notes="bad",
            tags=(),
            reason_codes=("REJECTED",),
            reviewed_at=generated_at,
            safety_flags=ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
            ),
        )
        summary = ReviewAuditSummary(
            total_reviews=2,
            accepted_count=1,
            rejected_count=1,
            needs_investigation_count=0,
            not_reviewed_count=0,
            blocked_count=0,
            unknown_count=0,
            reason_counts={"ACCEPTED": 1, "REJECTED": 1},
        )
        data_quality = ReviewDataQuality(
            total_reports=2,
            valid_reports=2,
            blocked_reports=0,
            unknown_reports=0,
            unsafe_reports=0,
            missing_reports=0,
            invalid_reports=0,
        )
        safety_flags = ReviewSafetyFlags(
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            report_feedback_into_execution=False,
            operator_feedback_into_execution=False,
        )
        audit = ReviewAuditRecord(
            audit_id="audit-2",
            generated_at=generated_at,
            audit_state=ReviewState.READY,
            records=(record1, record2),
            summary=summary,
            data_quality=data_quality,
            reason_codes=(),
            safety_flags=safety_flags,
        )
        entry = build_chronicle_entry_from_review(audit)
        assert entry.entry_count == 2


# ---------------------------------------------------------------------------
# build_chronicle_entry_from_index
# ---------------------------------------------------------------------------


class TestBuildChronicleEntryFromIndex:
    """Tests for build_chronicle_entry_from_index."""

    def _index(self, generated_at: datetime | None = None) -> ReviewIndex:
        if generated_at is None:
            generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entry = IndexEntry(
            entry_id="ie1",
            entry_kind=IndexEntryKind.OBSERVATION_REPORT,
            index_state=IndexState.READY,
            report_id="rep1",
        )
        summary = IndexSummary(
            total_entries=1,
            observation_report_count=1,
            review_audit_count=0,
            linked_entry_count=0,
        )
        data_quality = IndexDataQuality(
            total_reports=1,
            valid_reports=1,
            invalid_reports=0,
            unsafe_reports=0,
            total_reviews=0,
            valid_reviews=0,
            invalid_reviews=0,
            unsafe_reviews=0,
            linked_records=0,
            unlinked_reports=0,
            unlinked_reviews=0,
        )
        safety_flags = IndexSafetyFlags()
        return ReviewIndex(
            index_id="index-1",
            generated_at=generated_at,
            index_state=IndexState.READY,
            entries=(entry,),
            summary=summary,
            data_quality=data_quality,
            safety_flags=safety_flags,
            reason_codes=(),
        )

    def test_from_model(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        index = self._index(generated_at)
        entry = build_chronicle_entry_from_index(index)
        assert entry.artifact_type is ArtifactType.INDEX
        assert entry.trace_id == f"index:2025-01-01T12:00:00:1.0"
        assert entry.state == "READY"
        assert entry.entry_count == 1

    def test_from_dict(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        index_dict = {
            "generated_at": generated_at,
            "index_state": IndexState.READY,
            "entries": (),
            "version": "1.0",
            "reason_codes": (),
        }
        entry = build_chronicle_entry_from_index(index_dict)
        assert entry.artifact_type is ArtifactType.INDEX

    def test_missing_generated_at(self) -> None:
        with pytest.raises(ValueError, match="INVALID_TIMESTAMP"):
            build_chronicle_entry_from_index({})

    def test_entry_count_from_entries(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        index = self._index(generated_at)
        entry = build_chronicle_entry_from_index(index)
        assert entry.entry_count == 1


# ---------------------------------------------------------------------------
# build_chronicle_entry_from_search
# ---------------------------------------------------------------------------


class TestBuildChronicleEntryFromSearch:
    """Tests for build_chronicle_entry_from_search."""

    def _search_result(self, generated_at: datetime | None = None) -> SearchResult:
        if generated_at is None:
            generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        return SearchResult(
            search_id="search-1",
            generated_at=generated_at,
            search_state=SearchState.READY,
            query=SearchQuery(),
            entries=(),
            summary=SearchResultSummary(),
            reason_codes=(),
            safety_flags=SearchSafetyFlags(),
        )

    def test_from_model(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        search = self._search_result(generated_at)
        entry = build_chronicle_entry_from_search(search)
        assert entry.artifact_type is ArtifactType.SEARCH
        assert entry.trace_id == f"search:2025-01-01T12:00:00:1.0"
        assert entry.state == "READY"
        assert entry.entry_count == 0

    def test_from_dict(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        search_dict = {
            "generated_at": generated_at,
            "search_state": SearchState.READY,
            "entries": (),
            "version": "1.0",
            "reason_codes": (),
        }
        entry = build_chronicle_entry_from_search(search_dict)
        assert entry.artifact_type is ArtifactType.SEARCH

    def test_missing_generated_at(self) -> None:
        with pytest.raises(ValueError, match="INVALID_TIMESTAMP"):
            build_chronicle_entry_from_search({})

    def test_entry_count_from_entries(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        search_entry = SearchResultEntry(
            entry_id="se1",
            score=1.0,
            index_state=IndexState.READY,
            entry_kind=IndexEntryKind.OBSERVATION_REPORT,
            report_id="rep1",
        )
        search = SearchResult(
            search_id="search-2",
            generated_at=generated_at,
            search_state=SearchState.READY,
            query=SearchQuery(),
            entries=(search_entry,),
            summary=SearchResultSummary(),
            reason_codes=(),
            safety_flags=SearchSafetyFlags(),
        )
        entry = build_chronicle_entry_from_search(search)
        assert entry.entry_count == 1


# ---------------------------------------------------------------------------
# build_chronicle_entry_from_bundle
# ---------------------------------------------------------------------------


class TestBuildChronicleEntryFromBundle:
    """Tests for build_chronicle_entry_from_bundle."""

    def _bundle(self, generated_at: datetime | None = None) -> ResearchBundle:
        if generated_at is None:
            generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        item = BundleItem(
            item_id="bi1",
            kind=BundleItemKind.OBSERVATION_REPORT,
            reference="ref1",
        )
        summary = BundleSummary(total_items=1, observation_report_count=1)
        data_quality = BundleDataQuality(total_items=1, has_observation_report=True)
        safety_flags = BundleSafetyFlags()
        return ResearchBundle(
            bundle_id="bundle-1",
            generated_at=generated_at,
            bundle_state=BundleState.READY,
            items=(item,),
            summary=summary,
            data_quality=data_quality,
            safety_flags=safety_flags,
            reason_codes=(),
        )

    def test_from_model(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        bundle = self._bundle(generated_at)
        entry = build_chronicle_entry_from_bundle(bundle)
        assert entry.artifact_type is ArtifactType.BUNDLE
        assert entry.trace_id == f"bundle:2025-01-01T12:00:00:1.0"
        assert entry.entry_count == 1

    def test_from_dict(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        bundle_dict = {
            "generated_at": generated_at,
            "bundle_state": "READY",
            "items": (),
            "version": "1.0",
            "reason_codes": (),
        }
        entry = build_chronicle_entry_from_bundle(bundle_dict)
        assert entry.artifact_type is ArtifactType.BUNDLE

    def test_missing_generated_at(self) -> None:
        with pytest.raises(ValueError, match="INVALID_TIMESTAMP"):
            build_chronicle_entry_from_bundle({})

    def test_entry_count_from_items(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        bundle = self._bundle(generated_at)
        entry = build_chronicle_entry_from_bundle(bundle)
        assert entry.entry_count == 1


# ---------------------------------------------------------------------------
# build_chronicle_summary
# ---------------------------------------------------------------------------


class TestBuildChronicleSummary:
    """Tests for build_chronicle_summary."""

    def _entry(
        self,
        artifact_type: ArtifactType,
        state: str,
        timestamp: datetime,
        tags: tuple[str, ...] = (),
        reason_codes: tuple[str, ...] = (),
        actor: str | None = None,
    ) -> ChronicleEntry:
        return ChronicleEntry(
            entry_id=f"{artifact_type.value}:trace:ts",
            timestamp=timestamp,
            artifact_type=artifact_type,
            trace_id="trace",
            state=state,
            version="1.0",
            tags=tags,
            reason_codes=reason_codes,
            actor=actor,
        )

    def test_empty_entries(self) -> None:
        summary = build_chronicle_summary([])
        assert summary.total_entries == 0
        assert summary.observation_count == 0

    def test_single_entry_counts(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entry = self._entry(ArtifactType.OBSERVATION, "READY", generated_at)
        summary = build_chronicle_summary([entry])
        assert summary.total_entries == 1
        assert summary.observation_count == 1
        assert summary.ready_count == 1
        assert summary.blocked_count == 0

    def test_multiple_types(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entries = [
            self._entry(ArtifactType.OBSERVATION, "READY", generated_at),
            self._entry(ArtifactType.REVIEW, "BLOCKED", generated_at),
            self._entry(ArtifactType.INDEX, "READY", generated_at),
        ]
        summary = build_chronicle_summary(entries)
        assert summary.total_entries == 3
        assert summary.observation_count == 1
        assert summary.review_count == 1
        assert summary.index_count == 1
        assert summary.blocked_count == 1
        assert summary.ready_count == 2

    def test_state_counts(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entries = [
            self._entry(ArtifactType.OBSERVATION, "READY", generated_at),
            self._entry(ArtifactType.REVIEW, "BLOCKED", generated_at),
            self._entry(ArtifactType.INDEX, "UNKNOWN", generated_at),
        ]
        summary = build_chronicle_summary(entries)
        assert summary.ready_count == 1
        assert summary.blocked_count == 1
        assert summary.unknown_count == 1

    def test_accepted_rejected_counts(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entries = [
            self._entry(ArtifactType.REVIEW, "ACCEPTED", generated_at),
            self._entry(ArtifactType.REVIEW, "REJECTED", generated_at),
        ]
        summary = build_chronicle_summary(entries)
        assert summary.accepted_count == 1
        assert summary.rejected_count == 1

    def test_reason_code_counts(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entries = [
            self._entry(ArtifactType.OBSERVATION, "READY", generated_at, reason_codes=("CODE_A",)),
            self._entry(ArtifactType.OBSERVATION, "READY", generated_at, reason_codes=("CODE_A", "CODE_B")),
        ]
        summary = build_chronicle_summary(entries)
        assert summary.reason_code_counts == {"CODE_A": 2, "CODE_B": 1}

    def test_tag_counts(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entries = [
            self._entry(ArtifactType.OBSERVATION, "READY", generated_at, tags=("tag1",)),
            self._entry(ArtifactType.REVIEW, "BLOCKED", generated_at, tags=("tag1", "tag2")),
        ]
        summary = build_chronicle_summary(entries)
        assert summary.tag_counts == {"tag1": 2, "tag2": 1}

    def test_actor_counts(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entries = [
            self._entry(ArtifactType.OBSERVATION, "READY", generated_at, actor="alice"),
            self._entry(ArtifactType.REVIEW, "BLOCKED", generated_at, actor="bob"),
        ]
        summary = build_chronicle_summary(entries)
        assert summary.actor_counts == {"alice": 1, "bob": 1}

    def test_timestamp_range(self) -> None:
        t1 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        entries = [
            self._entry(ArtifactType.OBSERVATION, "READY", t2),
            self._entry(ArtifactType.OBSERVATION, "READY", t1),
        ]
        summary = build_chronicle_summary(entries)
        assert summary.timestamp_range == ("2025-01-01T10:00:00", "2025-01-01T14:00:00")

    def test_daily_counts(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entries = [
            self._entry(ArtifactType.OBSERVATION, "READY", generated_at),
            self._entry(ArtifactType.OBSERVATION, "READY", generated_at),
            self._entry(ArtifactType.REVIEW, "BLOCKED", generated_at),
        ]
        summary = build_chronicle_summary(entries)
        assert summary.daily_counts == {"2025-01-01": {"observation": 2, "review": 1}}


# ---------------------------------------------------------------------------
# build_chronicle_data_quality
# ---------------------------------------------------------------------------


class TestBuildChronicleDataQuality:
    """Tests for build_chronicle_data_quality."""

    def test_empty(self) -> None:
        dq = build_chronicle_data_quality()
        assert dq.has_observations is False
        assert dq.orphan_observation_count == 0
        assert dq.trace_completeness_pct == 0.0

    def test_has_artifact_flags(self) -> None:
        obs = {"generated_at": datetime.now(timezone.utc), "version": "1.0"}
        dq = build_chronicle_data_quality(observations=(obs,))
        assert dq.has_observations is True
        assert dq.has_reviews is False

    def test_orphan_observation(self) -> None:
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs_entry = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=t1,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="obs-trace",
            state="READY",
            version="1.0",
        )
        review_entry = ChronicleEntry(
            entry_id="review:e2:ts",
            timestamp=t1,
            artifact_type=ArtifactType.REVIEW,
            trace_id="review-trace",
            state="READY",
            version="1.0",
            related_trace_ids=("different-trace",),
        )
        dq = build_chronicle_data_quality(
            observations=("dummy",),
            reviews=("dummy",),
            entries=(obs_entry, review_entry),
        )
        assert dq.orphan_observation_count == 1
        assert dq.orphan_review_count == 1

    def test_trace_completeness(self) -> None:
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        e1 = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=t1,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
            related_trace_ids=("trace-b",),
        )
        e2 = ChronicleEntry(
            entry_id="obs:e2:ts",
            timestamp=t1,
            artifact_type=ArtifactType.REVIEW,
            trace_id="trace-b",
            state="READY",
            version="1.0",
        )
        dq = build_chronicle_data_quality(entries=(e1, e2))
        assert dq.trace_completeness_pct == 50.0

    def test_gap_detection(self) -> None:
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        t2 = t1 + timedelta(hours=3)
        e1 = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=t1,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
        )
        e2 = ChronicleEntry(
            entry_id="obs:e2:ts",
            timestamp=t2,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-b",
            state="READY",
            version="1.0",
        )
        dq = build_chronicle_data_quality(
            entries=(e1, e2),
            gap_threshold_seconds=3600,
        )
        assert dq.gap_count == 1

    def test_no_gap_below_threshold(self) -> None:
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        t2 = t1 + timedelta(minutes=30)
        e1 = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=t1,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
        )
        e2 = ChronicleEntry(
            entry_id="obs:e2:ts",
            timestamp=t2,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-b",
            state="READY",
            version="1.0",
        )
        dq = build_chronicle_data_quality(
            entries=(e1, e2),
            gap_threshold_seconds=3600,
        )
        assert dq.gap_count == 0

    def test_single_entry_no_gap(self) -> None:
        t1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        e1 = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=t1,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
        )
        dq = build_chronicle_data_quality(entries=(e1,))
        assert dq.gap_count == 0

    def test_stale_detection(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(days=2)
        e1 = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=old,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
        )
        dq = build_chronicle_data_quality(
            entries=(e1,),
            stale_threshold_seconds=86400,
        )
        assert dq.stale_entry_count == 1

    def test_no_stale_within_threshold(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(hours=12)
        e1 = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=recent,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
        )
        dq = build_chronicle_data_quality(
            entries=(e1,),
            stale_threshold_seconds=86400,
        )
        assert dq.stale_entry_count == 0


# ---------------------------------------------------------------------------
# build_research_chronicle
# ---------------------------------------------------------------------------


class TestBuildResearchChronicle:
    """Tests for build_research_chronicle."""

    def _observation(self, generated_at: datetime | None = None) -> ObservationReport:
        if generated_at is None:
            generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = SignalObservation(
            timestamp=generated_at,
            observation_state=ObservationState.READY,
            signal=ObservationSignal.LONG_RESEARCH,
            source_shell_state="READY",
            source_signal_exposure="LONG",
            reason_codes=("READY",),
        )
        window = ObservationWindow(
            started_at=generated_at,
            ended_at=generated_at,
            observations=(obs,),
        )
        return ObservationReport(
            generated_at=generated_at,
            report_state=ObservationState.READY,
            window=window,
            reason_codes=("READY",),
            version="1.0",
        )

    def test_missing_artifacts_blocked(self) -> None:
        chronicle = build_research_chronicle()
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("MISSING_ARTIFACTS",)
        assert chronicle.version == CHRONICLE_VERSION

    def test_single_observation(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = self._observation(generated_at)
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.chronicle_id != "blocked"
        assert len(chronicle.entries) == 1
        assert chronicle.entries[0].artifact_type is ArtifactType.OBSERVATION
        assert chronicle.summary.total_entries == 1
        assert chronicle.summary.observation_count == 1

    def test_deterministic_sort_order(self) -> None:
        t1 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs1 = self._observation(t1)
        obs2 = self._observation(t2)
        # chronicle should be sorted by timestamp
        chronicle = build_research_chronicle(observations=(obs2, obs1))
        assert chronicle.entries[0].timestamp == t1
        assert chronicle.entries[1].timestamp == t2

    def test_fail_closed_on_invalid_observation(self) -> None:
        chronicle = build_research_chronicle(observations=({},))
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("INVALID_OBSERVATION",)

    def test_unsafe_content_blocked(self) -> None:
        obs = {"generated_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc), "version": "1.0", "notes": "enter_long"}
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("UNSAFE_CHRONICLE_CONTENT",)

    def test_unsafe_content_in_tags_blocked(self) -> None:
        obs = {"generated_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc), "version": "1.0", "tags": ("leverage",)}
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("UNSAFE_CHRONICLE_CONTENT",)

    def test_unsafe_content_in_metadata_keys_blocked(self) -> None:
        obs = {"generated_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc), "version": "1.0", "metadata": {"api_key": "secret"}}
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("UNSAFE_CHRONICLE_CONTENT",)

    def test_multiple_artifact_types(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = self._observation(generated_at)
        # Create a review audit record
        record = ReviewRecord(
            review_id="r1",
            source_report_id="rep1",
            source_report_version="1.0",
            review_state=ReviewState.READY,
            review_status=ReviewStatus.ACCEPTED,
            reviewer="alice",
            notes="ok",
            tags=(),
            reason_codes=("ACCEPTED",),
            reviewed_at=generated_at,
            safety_flags=ReviewSafetyFlags(
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                report_feedback_into_execution=False,
                operator_feedback_into_execution=False,
            ),
        )
        summary = ReviewAuditSummary(
            total_reviews=1,
            accepted_count=1,
            rejected_count=0,
            needs_investigation_count=0,
            not_reviewed_count=0,
            blocked_count=0,
            unknown_count=0,
            reason_counts={"ACCEPTED": 1},
        )
        data_quality = ReviewDataQuality(
            total_reports=1,
            valid_reports=1,
            blocked_reports=0,
            unknown_reports=0,
            unsafe_reports=0,
            missing_reports=0,
            invalid_reports=0,
        )
        safety_flags = ReviewSafetyFlags(
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            report_feedback_into_execution=False,
            operator_feedback_into_execution=False,
        )
        audit = ReviewAuditRecord(
            audit_id="audit-1",
            generated_at=generated_at,
            audit_state=ReviewState.READY,
            records=(record,),
            summary=summary,
            data_quality=data_quality,
            reason_codes=(),
            safety_flags=safety_flags,
        )
        chronicle = build_research_chronicle(observations=(obs,), reviews=(audit,))
        assert len(chronicle.entries) == 2
        assert chronicle.summary.observation_count == 1
        assert chronicle.summary.review_count == 1

    def test_safety_flags_in_output(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = self._observation(generated_at)
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.safety_flags.dry_run is True
        assert chronicle.safety_flags.live_trading_enabled is False
        assert chronicle.safety_flags.chronicle_output_is_human_audit_only is True
        assert chronicle.safety_flags.chronicle_feedback_into_execution is False

    def test_data_quality_in_output(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = self._observation(generated_at)
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.data_quality.has_observations is True
        assert chronicle.data_quality.has_reviews is False

    def test_version_in_output(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = self._observation(generated_at)
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.version == CHRONICLE_VERSION

    def test_entry_count_propagation(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        obs = self._observation(generated_at)
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.entries[0].entry_count == 1

    def test_empty_sequence_not_blocked(self) -> None:
        chronicle = build_research_chronicle(
            observations=(),
            reviews=(),
            indices=(),
            searches=(),
            bundles=(),
        )
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("MISSING_ARTIFACTS",)
