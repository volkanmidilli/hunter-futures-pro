"""Chronicle engine for hunter.chronicle package.

Builds ChronicleEntry objects from MVP-10–MVP-14 artifacts, aggregates summaries,
and assembles ResearchChronicle containers.

All functions are pure: no file I/O, no network, no database, no side effects.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from hunter.chronicle.models import (
    ArtifactType,
    CHRONICLE_VERSION,
    ChronicleDataQuality,
    ChronicleEntry,
    ChronicleSafetyFlags,
    ChronicleSummary,
    ResearchChronicle,
    _has_unsafe_chronicle_content,
)


def has_unsafe_chronicle_content(text: str) -> bool:
    """Return True if text contains forbidden chronicle terms."""
    return _has_unsafe_chronicle_content(text)


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Get attribute from object or dict."""
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _iso_str(dt: datetime) -> str:
    """ISO format string for a datetime including microseconds for uniqueness."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")


def _get_timestamp(obj: Any) -> datetime | None:
    """Extract a timezone-aware timestamp from an object or dict."""
    raw = _get_attr(obj, "generated_at")
    if raw is None:
        raw = _get_attr(obj, "timestamp")
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return None
        return raw
    return None


def _get_version(obj: Any) -> str | None:
    """Extract version string from an object or dict."""
    raw = _get_attr(obj, "version")
    if isinstance(raw, str) and raw:
        return raw
    return None


def _get_state(obj: Any, default: str = "UNKNOWN") -> str:
    """Extract state string from an object or dict."""
    raw = _get_attr(obj, "report_state")
    if raw is None:
        raw = _get_attr(obj, "audit_state")
    if raw is None:
        raw = _get_attr(obj, "index_state")
    if raw is None:
        raw = _get_attr(obj, "search_state")
    if raw is None:
        raw = _get_attr(obj, "bundle_state")
    if raw is None:
        raw = _get_attr(obj, "state")
    if isinstance(raw, str):
        return raw
    if hasattr(raw, "value"):
        return str(raw.value)
    return default


def _get_reason_codes(obj: Any) -> tuple[str, ...]:
    """Extract reason codes from an object or dict."""
    raw = _get_attr(obj, "reason_codes")
    if isinstance(raw, tuple):
        return raw
    if isinstance(raw, list):
        return tuple(str(x) for x in raw if x)
    return ()


# ---------------------------------------------------------------------------
# Entry builders
# ---------------------------------------------------------------------------


def build_chronicle_entry_from_observation(report: Any) -> ChronicleEntry:
    """Build a ChronicleEntry from an ObservationReport.

    ObservationReport has no report_id field. The trace_id is synthesized
    deterministically from generated_at and version:

        trace_id = "observation:{generated_at_iso}:{version}"

    If generated_at is missing, raises ValueError with MISSING_TRACE_ID.
    If generated_at is naive (not timezone-aware), raises ValueError with INVALID_TIMESTAMP.
    If version is missing, raises ValueError with UNSUPPORTED_OBSERVATION_VERSION.
    """
    raw_generated_at = _get_attr(report, "generated_at")
    if raw_generated_at is None:
        raise ValueError("MISSING_TRACE_ID")
    if isinstance(raw_generated_at, datetime) and raw_generated_at.tzinfo is None:
        raise ValueError("INVALID_TIMESTAMP")
    generated_at = raw_generated_at if isinstance(raw_generated_at, datetime) else _get_timestamp(report)
    if generated_at is None:
        raise ValueError("INVALID_TIMESTAMP")
    version = _get_version(report)
    if version is None:
        raise ValueError("UNSUPPORTED_OBSERVATION_VERSION")

    trace_id = f"observation:{_iso_str(generated_at)}:{version}"
    state = _get_state(report, "UNKNOWN")
    entry_id = f"{ArtifactType.OBSERVATION.value}:{trace_id}:{_iso_str(generated_at)}"
    reason_codes = _get_reason_codes(report)
    window = _get_attr(report, "window")
    entry_count = 0
    if window is not None:
        observations = _get_attr(window, "observations")
        if isinstance(observations, tuple):
            entry_count = len(observations)
    summary = _get_attr(report, "summary")
    metadata: dict[str, Any] = {}
    if isinstance(summary, Mapping):
        metadata = dict(summary)

    return ChronicleEntry(
        entry_id=entry_id,
        timestamp=generated_at,
        artifact_type=ArtifactType.OBSERVATION,
        trace_id=trace_id,
        state=state,
        version=version,
        entry_count=entry_count,
        reason_codes=reason_codes,
        metadata=metadata,
    )


def build_chronicle_entry_from_review(
    audit_record: Any,
    related_trace_ids: tuple[str, ...] = (),
) -> ChronicleEntry:
    """Build a ChronicleEntry from a ReviewAuditRecord at the container level.

    ReviewAuditRecord is a container of ReviewRecord child objects.
    The chronicle entry represents the container, not individual records.

    Fields used:
        trace_id = "review-audit:{generated_at_iso}:{version}"
        timestamp = audit_record.generated_at
        state = audit_record.audit_state
        version = audit_record.version (defaults to "1.0")

    Raises ValueError with INVALID_TIMESTAMP if generated_at is missing/naive.
    """
    generated_at = _get_timestamp(audit_record)
    if generated_at is None:
        raise ValueError("INVALID_TIMESTAMP")
    version = _get_version(audit_record)
    if version is None:
        version = "1.0"
    trace_id = f"review-audit:{_iso_str(generated_at)}:{version}"
    state = _get_state(audit_record, "UNKNOWN")
    entry_id = f"{ArtifactType.REVIEW.value}:{trace_id}:{_iso_str(generated_at)}"
    reason_codes = _get_reason_codes(audit_record)
    records = _get_attr(audit_record, "records")
    entry_count = 0
    if isinstance(records, tuple):
        entry_count = len(records)
    summary = _get_attr(audit_record, "summary")
    metadata: dict[str, Any] = {}
    if isinstance(summary, Mapping):
        metadata["audit_summary"] = dict(summary)

    return ChronicleEntry(
        entry_id=entry_id,
        timestamp=generated_at,
        artifact_type=ArtifactType.REVIEW,
        trace_id=trace_id,
        state=state,
        version=version,
        entry_count=entry_count,
        reason_codes=reason_codes,
        metadata=metadata,
        related_trace_ids=related_trace_ids,
    )


def build_chronicle_entry_from_index(index: Any) -> ChronicleEntry:
    """Build a ChronicleEntry from a ReviewIndex.

    The entry_count field is derived as len(index.entries).

    Raises ValueError with INVALID_TIMESTAMP if generated_at is missing/naive.
    """
    generated_at = _get_timestamp(index)
    if generated_at is None:
        raise ValueError("INVALID_TIMESTAMP")
    version = _get_version(index)
    if version is None:
        version = "1.0"
    trace_id = f"index:{_iso_str(generated_at)}:{version}"
    state = _get_state(index, "UNKNOWN")
    entry_id = f"{ArtifactType.INDEX.value}:{trace_id}:{_iso_str(generated_at)}"
    reason_codes = _get_reason_codes(index)
    entries = _get_attr(index, "entries")
    entry_count = 0
    if isinstance(entries, tuple):
        entry_count = len(entries)

    return ChronicleEntry(
        entry_id=entry_id,
        timestamp=generated_at,
        artifact_type=ArtifactType.INDEX,
        trace_id=trace_id,
        state=state,
        version=version,
        entry_count=entry_count,
        reason_codes=reason_codes,
    )


def build_chronicle_entry_from_search(search_result: Any) -> ChronicleEntry:
    """Build a ChronicleEntry from a SearchResult.

    Raises ValueError with INVALID_TIMESTAMP if generated_at is missing/naive.
    """
    generated_at = _get_timestamp(search_result)
    if generated_at is None:
        raise ValueError("INVALID_TIMESTAMP")
    version = _get_version(search_result)
    if version is None:
        version = "1.0"
    trace_id = f"search:{_iso_str(generated_at)}:{version}"
    state = _get_state(search_result, "UNKNOWN")
    entry_id = f"{ArtifactType.SEARCH.value}:{trace_id}:{_iso_str(generated_at)}"
    reason_codes = _get_reason_codes(search_result)
    entries = _get_attr(search_result, "entries")
    entry_count = 0
    if isinstance(entries, tuple):
        entry_count = len(entries)
    query = _get_attr(search_result, "query")
    metadata: dict[str, Any] = {}
    if query is not None:
        query_text = _get_attr(query, "query_text")
        if query_text is not None:
            metadata["query_text"] = str(query_text)

    return ChronicleEntry(
        entry_id=entry_id,
        timestamp=generated_at,
        artifact_type=ArtifactType.SEARCH,
        trace_id=trace_id,
        state=state,
        version=version,
        entry_count=entry_count,
        reason_codes=reason_codes,
        metadata=metadata,
    )


def build_chronicle_entry_from_bundle(bundle: Any) -> ChronicleEntry:
    """Build a ChronicleEntry from a ResearchBundle.

    Raises ValueError with INVALID_TIMESTAMP if generated_at is missing/naive.
    """
    generated_at = _get_timestamp(bundle)
    if generated_at is None:
        raise ValueError("INVALID_TIMESTAMP")
    version = _get_version(bundle)
    if version is None:
        version = "1.0"
    trace_id = f"bundle:{_iso_str(generated_at)}:{version}"
    state = _get_state(bundle, "UNKNOWN")
    entry_id = f"{ArtifactType.BUNDLE.value}:{trace_id}:{_iso_str(generated_at)}"
    reason_codes = _get_reason_codes(bundle)
    items = _get_attr(bundle, "items")
    entry_count = 0
    if isinstance(items, tuple):
        entry_count = len(items)

    return ChronicleEntry(
        entry_id=entry_id,
        timestamp=generated_at,
        artifact_type=ArtifactType.BUNDLE,
        trace_id=trace_id,
        state=state,
        version=version,
        entry_count=entry_count,
        reason_codes=reason_codes,
    )


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------


def build_chronicle_summary(entries: Sequence[ChronicleEntry]) -> ChronicleSummary:
    """Build a ChronicleSummary from a sequence of entries."""
    total = len(entries)
    observation_count = 0
    review_count = 0
    index_count = 0
    search_count = 0
    bundle_count = 0
    blocked_count = 0
    ready_count = 0
    unknown_count = 0
    accepted_count = 0
    rejected_count = 0
    reason_code_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    actor_counts: dict[str, int] = {}
    daily_counts: dict[str, dict[str, int]] = {}

    timestamps: list[str] = []

    for entry in entries:
        if entry.artifact_type is ArtifactType.OBSERVATION:
            observation_count += 1
        elif entry.artifact_type is ArtifactType.REVIEW:
            review_count += 1
        elif entry.artifact_type is ArtifactType.INDEX:
            index_count += 1
        elif entry.artifact_type is ArtifactType.SEARCH:
            search_count += 1
        elif entry.artifact_type is ArtifactType.BUNDLE:
            bundle_count += 1

        state_upper = entry.state.upper()
        if state_upper == "BLOCKED":
            blocked_count += 1
        elif state_upper == "READY":
            ready_count += 1
        elif state_upper == "UNKNOWN":
            unknown_count += 1

        if state_upper == "ACCEPTED":
            accepted_count += 1
        elif state_upper == "REJECTED":
            rejected_count += 1

        for code in entry.reason_codes:
            reason_code_counts[code] = reason_code_counts.get(code, 0) + 1

        for tag in entry.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        if entry.actor:
            actor_counts[entry.actor] = actor_counts.get(entry.actor, 0) + 1

        ts_str = entry.timestamp.strftime("%Y-%m-%dT%H:%M:%S")
        timestamps.append(ts_str)
        day = entry.timestamp.strftime("%Y-%m-%d")
        if day not in daily_counts:
            daily_counts[day] = {}
        type_key = entry.artifact_type.value
        daily_counts[day][type_key] = daily_counts[day].get(type_key, 0) + 1

    timestamp_range: tuple[str, str] | None = None
    if timestamps:
        sorted_ts = sorted(timestamps)
        timestamp_range = (sorted_ts[0], sorted_ts[-1])

    return ChronicleSummary(
        total_entries=total,
        observation_count=observation_count,
        review_count=review_count,
        index_count=index_count,
        search_count=search_count,
        bundle_count=bundle_count,
        blocked_count=blocked_count,
        ready_count=ready_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        unknown_count=unknown_count,
        reason_code_counts=reason_code_counts,
        tag_counts=tag_counts,
        actor_counts=actor_counts,
        timestamp_range=timestamp_range,
        daily_counts=daily_counts,
    )


# ---------------------------------------------------------------------------
# Data quality builder
# ---------------------------------------------------------------------------


def build_chronicle_data_quality(
    observations: Sequence[Any] = (),
    reviews: Sequence[Any] = (),
    indices: Sequence[Any] = (),
    searches: Sequence[Any] = (),
    bundles: Sequence[Any] = (),
    entries: Sequence[ChronicleEntry] = (),
    stale_threshold_seconds: int = 86400,
    gap_threshold_seconds: int = 3600,
) -> ChronicleDataQuality:
    """Build ChronicleDataQuality from raw artifacts and built entries."""
    has_observations = len(observations) > 0
    has_reviews = len(reviews) > 0
    has_index = len(indices) > 0
    has_search = len(searches) > 0
    has_bundle = len(bundles) > 0

    # Orphan detection: only count when at least one entry has explicit
    # related_trace_ids. Without explicit cross-links, orphan counts remain 0.
    all_trace_ids: set[str] = set()
    for entry in entries:
        all_trace_ids.add(entry.trace_id)

    has_any_related = any(e.related_trace_ids for e in entries)
    orphan_observation_count = 0
    orphan_review_count = 0
    if has_any_related:
        for entry in entries:
            if entry.artifact_type is ArtifactType.OBSERVATION:
                has_related = any(
                    e.trace_id != entry.trace_id and entry.trace_id in e.related_trace_ids
                    for e in entries
                )
                if not has_related:
                    orphan_observation_count += 1
            elif entry.artifact_type is ArtifactType.REVIEW:
                has_related = any(
                    e.trace_id != entry.trace_id and entry.trace_id in e.related_trace_ids
                    for e in entries
                )
                if not has_related:
                    orphan_review_count += 1

    # Trace completeness: how many entries have at least one related entry
    entries_with_related = 0
    for entry in entries:
        if entry.related_trace_ids:
            entries_with_related += 1
    trace_completeness_pct = 0.0
    if len(entries) > 0:
        trace_completeness_pct = (entries_with_related / len(entries)) * 100.0

    # Gap detection: time gaps between consecutive entries > threshold
    gap_count = 0
    sorted_entries = sorted(entries, key=lambda e: e.timestamp)
    if len(sorted_entries) >= 2:
        for i in range(1, len(sorted_entries)):
            delta = sorted_entries[i].timestamp - sorted_entries[i - 1].timestamp
            if delta.total_seconds() > gap_threshold_seconds:
                gap_count += 1

    # Stale detection: entries older than threshold
    stale_entry_count = 0
    now = datetime.now(timezone.utc)
    for entry in entries:
        age = (now - entry.timestamp).total_seconds()
        if age > stale_threshold_seconds:
            stale_entry_count += 1

    return ChronicleDataQuality(
        has_observations=has_observations,
        has_reviews=has_reviews,
        has_index=has_index,
        has_search=has_search,
        has_bundle=has_bundle,
        orphan_observation_count=orphan_observation_count,
        orphan_review_count=orphan_review_count,
        trace_completeness_pct=trace_completeness_pct,
        gap_count=gap_count,
        stale_entry_count=stale_entry_count,
        validation_errors=(),
    )


# ---------------------------------------------------------------------------
# Main chronicle builder
# ---------------------------------------------------------------------------


def build_research_chronicle(
    observations: Sequence[Any] = (),
    reviews: Sequence[Any] = (),
    indices: Sequence[Any] = (),
    searches: Sequence[Any] = (),
    bundles: Sequence[Any] = (),
    stale_threshold_seconds: int = 86400,
    gap_threshold_seconds: int = 3600,
) -> ResearchChronicle:
    """Build a ResearchChronicle from MVP-10–MVP-14 artifacts.

    Fail-closed priority:
    1. MISSING_ARTIFACTS → blocked
    2. INVALID_* → blocked
    3. UNSUPPORTED_*_VERSION → blocked
    4. UNSAFE_CHRONICLE_CONTENT → blocked
    5. CHRONICLE_ERROR → blocked
    """
    # Collect all artifacts
    all_artifacts = [*observations, *reviews, *indices, *searches, *bundles]
    if not all_artifacts:
        return ResearchChronicle.blocked("MISSING_ARTIFACTS")

    # Check for unsafe content in any artifact
    for artifact in all_artifacts:
        for field_name in ("notes", "tags", "metadata"):
            value = _get_attr(artifact, field_name)
            if isinstance(value, str) and has_unsafe_chronicle_content(value):
                return ResearchChronicle.blocked("UNSAFE_CHRONICLE_CONTENT")
            if isinstance(value, (tuple, list)):
                for item in value:
                    if isinstance(item, str) and has_unsafe_chronicle_content(item):
                        return ResearchChronicle.blocked("UNSAFE_CHRONICLE_CONTENT")
            if isinstance(value, Mapping):
                for key in value:
                    if has_unsafe_chronicle_content(key):
                        return ResearchChronicle.blocked("UNSAFE_CHRONICLE_CONTENT")

    # Build entries from each artifact type. Preserve distinct UNSUPPORTED_*_VERSION
    # reason codes instead of collapsing them into INVALID_*.
    entries: list[ChronicleEntry] = []

    for obs in observations:
        try:
            entries.append(build_chronicle_entry_from_observation(obs))
        except ValueError as e:
            msg = str(e)
            if msg == "UNSUPPORTED_OBSERVATION_VERSION":
                return ResearchChronicle.blocked("UNSUPPORTED_OBSERVATION_VERSION")
            return ResearchChronicle.blocked("INVALID_OBSERVATION")

    for rev in reviews:
        try:
            entries.append(build_chronicle_entry_from_review(rev))
        except ValueError as e:
            msg = str(e)
            if msg == "UNSUPPORTED_REVIEW_VERSION":
                return ResearchChronicle.blocked("UNSUPPORTED_REVIEW_VERSION")
            return ResearchChronicle.blocked("INVALID_REVIEW")

    for idx in indices:
        try:
            entries.append(build_chronicle_entry_from_index(idx))
        except ValueError as e:
            msg = str(e)
            if msg == "UNSUPPORTED_INDEX_VERSION":
                return ResearchChronicle.blocked("UNSUPPORTED_INDEX_VERSION")
            return ResearchChronicle.blocked("INVALID_INDEX")

    for srch in searches:
        try:
            entries.append(build_chronicle_entry_from_search(srch))
        except ValueError as e:
            msg = str(e)
            if msg == "UNSUPPORTED_SEARCH_VERSION":
                return ResearchChronicle.blocked("UNSUPPORTED_SEARCH_VERSION")
            return ResearchChronicle.blocked("INVALID_SEARCH")

    for bndl in bundles:
        try:
            entries.append(build_chronicle_entry_from_bundle(bndl))
        except ValueError as e:
            msg = str(e)
            if msg == "UNSUPPORTED_BUNDLE_VERSION":
                return ResearchChronicle.blocked("UNSUPPORTED_BUNDLE_VERSION")
            return ResearchChronicle.blocked("INVALID_BUNDLE")

    # Sort by deterministic sort key
    entries.sort(key=lambda e: (e.timestamp, e.artifact_type.value, e.trace_id))

    # Build summary and data quality
    summary = build_chronicle_summary(entries)
    data_quality = build_chronicle_data_quality(
        observations=observations,
        reviews=reviews,
        indices=indices,
        searches=searches,
        bundles=bundles,
        entries=entries,
        stale_threshold_seconds=stale_threshold_seconds,
        gap_threshold_seconds=gap_threshold_seconds,
    )

    return ResearchChronicle(
        chronicle_id=f"chronicle:{_iso_str(datetime.now(timezone.utc))}",
        generated_at=datetime.now(timezone.utc),
        version=CHRONICLE_VERSION,
        entries=tuple(entries),
        summary=summary,
        data_quality=data_quality,
        safety_flags=ChronicleSafetyFlags(),
        reason_codes=(),
    )
