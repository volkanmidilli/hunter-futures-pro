"""In-memory engine for hunter.remediation_backlog package.

MVP-37 — Local Research Remediation Backlog Planner.

The engine receives only caller-provided in-memory input. It never inspects the
filesystem, imports prior packages, or traverses any path or reference string.
It never emits executable remediation actions, shell commands, code patches, or
infrastructure changes.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from json import dumps
from typing import Any

from hunter.remediation_backlog.models import (
    FORBIDDEN_REMEDIATION_BACKLOG_TERMS,
    REMEDIATION_BACKLOG_VERSION,
    RemediationAcknowledgement,
    RemediationBacklogConfig,
    RemediationBacklogDataQuality,
    RemediationBacklogInput,
    RemediationBacklogItem,
    RemediationBacklogItemState,
    RemediationBacklogItemType,
    RemediationBacklogPriority,
    RemediationBacklogReasonCode,
    RemediationBacklogReport,
    RemediationBacklogSafetyFlags,
    RemediationBacklogSeverity,
    RemediationBacklogState,
    RemediationDependency,
    RemediationDependencyType,
    _check_forbidden_mapping,
    _has_forbidden_term,
    has_unsafe_remediation_backlog_content,
)


# ---------------------------------------------------------------------------
# Safety scan
# ---------------------------------------------------------------------------


def _iter_text_fields(input: RemediationBacklogInput) -> list[str]:
    """Yield textual fields from all input collections for forbidden-term scanning."""
    texts: list[str] = []
    for ref in input.source_refs:
        if ref.source_type:
            texts.append(ref.source_type)
        if ref.reference:
            texts.append(ref.reference)
        if ref.label:
            texts.append(ref.label)
    for ref in input.finding_refs:
        if ref.reference:
            texts.append(ref.reference)
        if ref.label:
            texts.append(ref.label)
    for item in input.backlog_items:
        if item.title:
            texts.append(item.title)
        if item.description:
            texts.append(item.description)
    for ack in input.acknowledgements:
        if ack.note:
            texts.append(ack.note)
    return texts


def _scan_forbidden_terms(input: RemediationBacklogInput) -> tuple[str, ...]:
    """Return offending strings containing forbidden terms."""
    offenders: list[str] = []
    if _check_forbidden_mapping(input.metadata, FORBIDDEN_REMEDIATION_BACKLOG_TERMS):
        for key, value in input.metadata.items():
            if isinstance(key, str) and _has_forbidden_term(key, FORBIDDEN_REMEDIATION_BACKLOG_TERMS):
                offenders.append(key)
                break
            if isinstance(value, str) and _has_forbidden_term(value, FORBIDDEN_REMEDIATION_BACKLOG_TERMS):
                offenders.append(value)
                break
    for text in _iter_text_fields(input):
        if text and _has_forbidden_term(text, FORBIDDEN_REMEDIATION_BACKLOG_TERMS):
            offenders.append(text)
    return tuple(offenders)


def _scan_unsafe_content(input: RemediationBacklogInput) -> tuple[Any, ...]:
    """Return offending values that are not safe string types."""
    offenders: list[Any] = []
    for key, value in input.metadata.items():
        if has_unsafe_remediation_backlog_content(key):
            offenders.append(key)
        if has_unsafe_remediation_backlog_content(value):
            offenders.append(value)
    for ref in input.source_refs:
        for value in (ref.source_type, ref.reference, ref.label):
            if has_unsafe_remediation_backlog_content(value):
                offenders.append(value)
        for value in ref.metadata.values():
            if has_unsafe_remediation_backlog_content(value):
                offenders.append(value)
    for ref in input.finding_refs:
        for value in (ref.reference, ref.label):
            if has_unsafe_remediation_backlog_content(value):
                offenders.append(value)
        for value in ref.metadata.values():
            if has_unsafe_remediation_backlog_content(value):
                offenders.append(value)
    for item in input.backlog_items:
        for value in (item.title, item.description):
            if has_unsafe_remediation_backlog_content(value):
                offenders.append(value)
        for value in item.metadata.values():
            if has_unsafe_remediation_backlog_content(value):
                offenders.append(value)
    for dep in input.dependencies:
        for value in dep.metadata.values():
            if has_unsafe_remediation_backlog_content(value):
                offenders.append(value)
    for ack in input.acknowledgements:
        if has_unsafe_remediation_backlog_content(ack.note):
            offenders.append(ack.note)
        for value in ack.metadata.values():
            if has_unsafe_remediation_backlog_content(value):
                offenders.append(value)
    return tuple(offenders)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _norm_id(value: str | None) -> str:
    """Normalize an ID: strip whitespace and lower-case."""
    if value is None:
        return ""
    return value.strip().lower()


def _is_valid_id(value: str | None) -> bool:
    """Return True if the normalized ID is non-empty."""
    return _norm_id(value) != ""


def _resolve_project_version(input: RemediationBacklogInput) -> str:
    """Resolve project_version per SPEC precedence."""
    return input.project_version or REMEDIATION_BACKLOG_VERSION


def _is_truly_empty(input: RemediationBacklogInput) -> bool:
    """Return True when the input has no sources, findings, items, deps, acks, or required sources."""
    return (
        not input.source_refs
        and not input.finding_refs
        and not input.backlog_items
        and not input.dependencies
        and not input.acknowledgements
        and not input.config.required_source_ids
    )


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def _build_report_id(
    input: RemediationBacklogInput,
    generated_at: datetime,
) -> str:
    """Return a deterministic report_id from sorted IDs. No path opening."""
    payload = {
        "source_ids": sorted(_norm_id(s.source_id) for s in input.source_refs),
        "finding_ids": sorted(_norm_id(f.finding_id) for f in input.finding_refs),
        "item_ids": sorted(_norm_id(i.item_id) for i in input.backlog_items if _is_valid_id(i.item_id)),
        "dependency_ids": sorted(_norm_id(d.dependency_id) for d in input.dependencies),
        "project_version": _resolve_project_version(input),
        "generated_at": generated_at.isoformat(),
    }
    canonical = dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"remediation_backlog_{sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def _build_item_id(
    source_id: str,
    finding_id: str,
    item_type: RemediationBacklogItemType,
    severity: RemediationBacklogSeverity,
    title: str,
    description: str,
    reason_codes: tuple[RemediationBacklogReasonCode, ...],
) -> str:
    """Return a deterministic item_id from normalized item content."""
    sorted_reasons = ",".join(sorted(code.value for code in reason_codes))
    content = (
        f"{_norm_id(source_id)}|{_norm_id(finding_id)}|{item_type.value}|"
        f"{severity.value}|{title.strip().lower()}|{description.strip().lower()}|"
        f"{sorted_reasons}"
    )
    return sha256(content.encode("utf-8")).hexdigest()[:16]


def _build_item_content_hash(item: RemediationBacklogItem) -> str:
    """Return a deterministic content hash for duplicate-item detection."""
    parts = (
        _norm_id(item.source_id),
        _norm_id(item.finding_id),
        _norm_id(item.subject_id),
        item.item_type.value,
        item.severity.value,
        item.title.strip().lower(),
        item.description.strip().lower(),
    )
    return sha256("|".join(parts).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Issue builders
# ---------------------------------------------------------------------------


def _issue(
    item_type: RemediationBacklogItemType,
    severity: RemediationBacklogSeverity,
    source_id: str = "",
    finding_id: str = "",
    subject_id: str = "",
    reason_codes: tuple[RemediationBacklogReasonCode, ...] = (),
    title: str = "",
    description: str = "",
) -> RemediationBacklogItem:
    """Build a RemediationBacklogItem issue with a deterministic item_id."""
    item_id = _build_item_id(
        source_id=source_id,
        finding_id=finding_id,
        item_type=item_type,
        severity=severity,
        title=title,
        description=description,
        reason_codes=reason_codes,
    )
    return RemediationBacklogItem(
        item_id=item_id,
        subject_id=subject_id if _is_valid_id(subject_id) else None,
        source_id=source_id if _is_valid_id(source_id) else None,
        finding_id=finding_id if _is_valid_id(finding_id) else None,
        item_type=item_type,
        item_state=RemediationBacklogItemState.OPEN,
        severity=severity,
        priority=RemediationBacklogPriority.NONE,
        title=title,
        description=description,
        reason_codes=reason_codes,
    )


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _detect_duplicate_ids(
    input: RemediationBacklogInput,
    issues: list[RemediationBacklogItem],
    counters: dict[str, int],
) -> None:
    """Detect duplicate IDs within each collection."""
    collections = [
        (input.source_refs, "source_id", "duplicate source_id"),
        (input.finding_refs, "finding_id", "duplicate finding_id"),
        (input.backlog_items, "item_id", "duplicate item_id"),
        (input.dependencies, "dependency_id", "duplicate dependency_id"),
        (input.acknowledgements, "acknowledgement_id", "duplicate acknowledgement_id"),
    ]
    for collection, attr, message in collections:
        seen: dict[str, int] = {}
        for obj in collection:
            raw_id = getattr(obj, attr)
            if not _is_valid_id(raw_id):
                continue
            norm = _norm_id(raw_id)
            seen[norm] = seen.get(norm, 0) + 1
        for norm, count in seen.items():
            if count > 1:
                issues.append(_issue(
                    item_type=RemediationBacklogItemType.DUPLICATE_ID,
                    severity=RemediationBacklogSeverity.BLOCKING,
                    subject_id=norm,
                    reason_codes=(RemediationBacklogReasonCode.DUPLICATE_ID,),
                    title="Duplicate ID",
                    description=f"{message}: {norm}",
                ))
                counters["duplicate_id_count"] += 1


def _detect_required_sources(
    input: RemediationBacklogInput,
    issues: list[RemediationBacklogItem],
    counters: dict[str, int],
) -> None:
    """Detect missing required source refs."""
    source_ids = {_norm_id(s.source_id) for s in input.source_refs}
    for required in input.config.required_source_ids:
        norm = _norm_id(required)
        if not _is_valid_id(required) or norm in source_ids:
            continue
        issues.append(_issue(
            item_type=RemediationBacklogItemType.REQUIRED_SOURCE,
            severity=RemediationBacklogSeverity.BLOCKING,
            subject_id=norm,
            source_id=norm,
            reason_codes=(RemediationBacklogReasonCode.MISSING_REQUIRED_SOURCE,),
            title="Missing required source",
            description=f"required source_id missing: {required}",
        ))
        counters["total_issues"] += 1


def _detect_orphan_findings(
    input: RemediationBacklogInput,
    issues: list[RemediationBacklogItem],
    counters: dict[str, int],
) -> None:
    """Detect backlog items referencing a finding_id not present in finding_refs."""
    finding_ids = {_norm_id(f.finding_id) for f in input.finding_refs}
    seen_orphans: set[str] = set()
    for item in input.backlog_items:
        if not _is_valid_id(item.finding_id):
            continue
        norm = _norm_id(item.finding_id)
        if norm not in finding_ids and norm not in seen_orphans:
            seen_orphans.add(norm)
            issues.append(_issue(
                item_type=RemediationBacklogItemType.ORPHAN_REF,
                severity=RemediationBacklogSeverity.ADVISORY,
                subject_id=norm,
                source_id=_norm_id(item.source_id) if _is_valid_id(item.source_id) else "",
                finding_id=norm,
                reason_codes=(RemediationBacklogReasonCode.ORPHAN_FINDING_REF,),
                title="Orphan finding ref",
                description=f"finding_id {item.finding_id} not present in finding_refs",
            ))
            counters["orphan_finding_count"] += 1


def _detect_orphan_dependencies(
    input: RemediationBacklogInput,
    issues: list[RemediationBacklogItem],
    counters: dict[str, int],
) -> None:
    """Detect dependencies referencing non-existent item IDs."""
    item_ids = {_norm_id(i.item_id) for i in input.backlog_items if _is_valid_id(i.item_id)}
    for dep in input.dependencies:
        for endpoint in (dep.source_item_id, dep.target_item_id):
            if not _is_valid_id(endpoint):
                continue
            norm = _norm_id(endpoint)
            if norm not in item_ids:
                issues.append(_issue(
                    item_type=RemediationBacklogItemType.ORPHAN_REF,
                    severity=RemediationBacklogSeverity.ADVISORY,
                    subject_id=norm,
                    reason_codes=(RemediationBacklogReasonCode.ORPHAN_DEPENDENCY,),
                    title="Orphan dependency",
                    description=f"dependency endpoint {endpoint} not present in backlog_items",
                ))
                counters["orphan_dependency_count"] += 1


def _detect_dependency_cycles(
    input: RemediationBacklogInput,
    issues: list[RemediationBacklogItem],
    counters: dict[str, int],
) -> None:
    """Detect cycles in DEPENDS_ON and BLOCKS edges using DFS."""
    graph: dict[str, set[str]] = defaultdict(set)
    for dep in input.dependencies:
        if dep.dependency_type in (RemediationDependencyType.DEPENDS_ON, RemediationDependencyType.BLOCKS):
            source = _norm_id(dep.source_item_id)
            target = _norm_id(dep.target_item_id)
            if source and target:
                graph[source].add(target)

    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[list[str]] = []

    def _dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        for neighbor in sorted(graph.get(node, ())):
            if neighbor not in visited:
                _dfs(neighbor, path)
            elif neighbor in rec_stack:
                try:
                    idx = path.index(neighbor)
                    cycle = path[idx:] + [neighbor]
                    cycles.append(cycle)
                except ValueError:
                    pass
        path.pop()
        rec_stack.discard(node)

    for node in sorted(graph.keys()):
        if node not in visited:
            _dfs(node, [])

    seen_cycles: set[tuple[str, ...]] = set()
    for cycle in cycles:
        key = tuple(sorted(set(cycle)))
        if key in seen_cycles:
            continue
        seen_cycles.add(key)
        issues.append(_issue(
            item_type=RemediationBacklogItemType.DEPENDENCY_CYCLE,
            severity=RemediationBacklogSeverity.BLOCKING,
            subject_id=cycle[0] if cycle else "",
            reason_codes=(RemediationBacklogReasonCode.DEPENDENCY_CYCLE,),
            title="Dependency cycle",
            description=f"cycle detected among items: {cycle}",
        ))
        counters["cycle_count"] += 1


def _detect_stale_refs(
    input: RemediationBacklogInput,
    generated_at: datetime,
    issues: list[RemediationBacklogItem],
    counters: dict[str, int],
) -> None:
    """Detect stale source and finding refs."""
    threshold = timedelta(seconds=input.config.staleness_threshold_seconds)
    cutoff = generated_at - threshold
    for ref in input.source_refs:
        if ref.generated_at is not None and ref.generated_at < cutoff:
            sid = _norm_id(ref.source_id)
            issues.append(_issue(
                item_type=RemediationBacklogItemType.STALE_REF,
                severity=RemediationBacklogSeverity.ADVISORY,
                subject_id=sid,
                source_id=sid,
                reason_codes=(RemediationBacklogReasonCode.STALE_SOURCE_REF,),
                title="Stale source ref",
                description=f"source {ref.source_id} is older than staleness threshold",
            ))
            counters["stale_source_count"] += 1
    for ref in input.finding_refs:
        if ref.generated_at is not None and ref.generated_at < cutoff:
            fid = _norm_id(ref.finding_id)
            issues.append(_issue(
                item_type=RemediationBacklogItemType.STALE_REF,
                severity=RemediationBacklogSeverity.ADVISORY,
                subject_id=fid,
                finding_id=fid,
                reason_codes=(RemediationBacklogReasonCode.STALE_FINDING_REF,),
                title="Stale finding ref",
                description=f"finding {ref.finding_id} is older than staleness threshold",
            ))
            counters["stale_finding_count"] += 1


def _detect_conflicting_states(
    input: RemediationBacklogInput,
    issues: list[RemediationBacklogItem],
    counters: dict[str, int],
) -> None:
    """Detect conflicting item states for the same subject."""
    groups: dict[str, list[RemediationBacklogItem]] = defaultdict(list)
    for item in input.backlog_items:
        if _is_valid_id(item.subject_id):
            key = _norm_id(item.subject_id)
        elif _is_valid_id(item.source_id) or _is_valid_id(item.finding_id):
            key = f"{_norm_id(item.source_id)}:{_norm_id(item.finding_id)}"
        else:
            continue
        groups[key].append(item)

    for key, items in groups.items():
        if len(items) < 2:
            continue
        states = {item.item_state for item in items}
        if len(states) <= 1:
            continue
        any_blocked = RemediationBacklogItemState.BLOCKED in states
        severity = RemediationBacklogSeverity.BLOCKING if any_blocked else RemediationBacklogSeverity.ADVISORY
        state_list = ", ".join(sorted(s.value for s in states))
        issues.append(_issue(
            item_type=RemediationBacklogItemType.CONFLICTING_STATE,
            severity=severity,
            subject_id=key,
            reason_codes=(RemediationBacklogReasonCode.CONFLICTING_ITEM_STATE,),
            title="Conflicting item state",
            description=f"subject {key} has conflicting states: {state_list}",
        ))
        counters["conflicting_item_count"] += 1


def _detect_missing_metadata(
    input: RemediationBacklogInput,
    issues: list[RemediationBacklogItem],
    counters: dict[str, int],
) -> None:
    """Detect missing owner/reviewer/manual-review metadata when required."""
    for item in input.backlog_items:
        if input.config.require_owner and not _is_valid_id(item.owner):
            issues.append(_issue(
                item_type=RemediationBacklogItemType.MISSING_OWNER,
                severity=RemediationBacklogSeverity.ADVISORY,
                subject_id=_norm_id(item.item_id) if _is_valid_id(item.item_id) else "",
                source_id=_norm_id(item.source_id) if _is_valid_id(item.source_id) else "",
                finding_id=_norm_id(item.finding_id) if _is_valid_id(item.finding_id) else "",
                reason_codes=(RemediationBacklogReasonCode.MISSING_OWNER,),
                title="Missing owner",
                description=f"item {item.item_id} is missing owner",
            ))
            counters["missing_owner_count"] += 1
        if input.config.require_reviewer and not _is_valid_id(item.reviewer):
            issues.append(_issue(
                item_type=RemediationBacklogItemType.MISSING_REVIEWER,
                severity=RemediationBacklogSeverity.ADVISORY,
                subject_id=_norm_id(item.item_id) if _is_valid_id(item.item_id) else "",
                source_id=_norm_id(item.source_id) if _is_valid_id(item.source_id) else "",
                finding_id=_norm_id(item.finding_id) if _is_valid_id(item.finding_id) else "",
                reason_codes=(RemediationBacklogReasonCode.MISSING_REVIEWER,),
                title="Missing reviewer",
                description=f"item {item.item_id} is missing reviewer",
            ))
            counters["missing_reviewer_count"] += 1
        if (
            input.config.require_manual_review
            and item.item_state != RemediationBacklogItemState.ACKNOWLEDGED
            and item.item_type != RemediationBacklogItemType.MANUAL_REVIEW
        ):
            issues.append(_issue(
                item_type=RemediationBacklogItemType.MISSING_MANUAL_REVIEW,
                severity=RemediationBacklogSeverity.ADVISORY,
                subject_id=_norm_id(item.item_id) if _is_valid_id(item.item_id) else "",
                source_id=_norm_id(item.source_id) if _is_valid_id(item.source_id) else "",
                finding_id=_norm_id(item.finding_id) if _is_valid_id(item.finding_id) else "",
                reason_codes=(RemediationBacklogReasonCode.MISSING_MANUAL_REVIEW,),
                title="Missing manual review",
                description=f"item {item.item_id} is missing manual review",
            ))
            counters["missing_manual_review_count"] += 1


# ---------------------------------------------------------------------------
# Acknowledgement, deduplication, and ID assignment
# ---------------------------------------------------------------------------


def _apply_acknowledgements(
    input: RemediationBacklogInput,
    items: list[RemediationBacklogItem],
    counters: dict[str, int],
) -> list[RemediationBacklogItem]:
    """Reclassify acknowledged items and return the updated list."""
    ack_by_item_id: dict[str, list[RemediationAcknowledgement]] = defaultdict(list)
    for ack in input.acknowledgements:
        if _is_valid_id(ack.item_id):
            ack_by_item_id[_norm_id(ack.item_id)].append(ack)

    if not ack_by_item_id:
        return items

    result: list[RemediationBacklogItem] = []
    for item in items:
        item_norm = _norm_id(item.item_id)
        if item_norm and item_norm in ack_by_item_id:
            acknowledged = RemediationBacklogItem(
                item_id=item.item_id,
                subject_id=item.subject_id,
                source_id=item.source_id,
                finding_id=item.finding_id,
                item_type=RemediationBacklogItemType.ACKNOWLEDGED_ITEM,
                item_state=RemediationBacklogItemState.ACKNOWLEDGED,
                severity=item.severity,
                priority=RemediationBacklogPriority.P3,
                title=item.title,
                description=item.description,
                owner=item.owner,
                reviewer=item.reviewer,
                generated_at=item.generated_at,
                reason_codes=(RemediationBacklogReasonCode.ACKNOWLEDGED_ITEM,),
                metadata=item.metadata,
            )
            result.append(acknowledged)
            counters["total_acknowledgements"] += 1
        else:
            result.append(item)
    return result


def _deduplicate_items(
    items: list[RemediationBacklogItem],
    counters: dict[str, int],
) -> list[RemediationBacklogItem]:
    """Remove duplicate items by content hash; keep first occurrence."""
    seen_hashes: set[str] = set()
    result: list[RemediationBacklogItem] = []
    for item in items:
        content_hash = _build_item_content_hash(item)
        if content_hash in seen_hashes:
            duplicate_issue = _issue(
                item_type=RemediationBacklogItemType.DUPLICATE_ITEM,
                severity=RemediationBacklogSeverity.INFO,
                subject_id=_norm_id(item.item_id) if _is_valid_id(item.item_id) else "",
                source_id=_norm_id(item.source_id) if _is_valid_id(item.source_id) else "",
                finding_id=_norm_id(item.finding_id) if _is_valid_id(item.finding_id) else "",
                reason_codes=(RemediationBacklogReasonCode.DUPLICATE_ITEM,),
                title="Duplicate item",
                description=f"item {item.item_id} is a duplicate by content hash",
            )
            result.append(duplicate_issue)
            counters["duplicate_item_count"] += 1
        else:
            seen_hashes.add(content_hash)
            result.append(item)
    return result


def _assign_item_ids(items: list[RemediationBacklogItem]) -> list[RemediationBacklogItem]:
    """Generate deterministic IDs for items without a caller-provided ID."""
    result: list[RemediationBacklogItem] = []
    for item in items:
        if _is_valid_id(item.item_id):
            result.append(item)
            continue
        item_id = _build_item_id(
            source_id=item.source_id or "",
            finding_id=item.finding_id or "",
            item_type=item.item_type,
            severity=item.severity,
            title=item.title,
            description=item.description,
            reason_codes=item.reason_codes,
        )
        result.append(
            RemediationBacklogItem(
                item_id=item_id,
                subject_id=item.subject_id,
                source_id=item.source_id,
                finding_id=item.finding_id,
                item_type=item.item_type,
                item_state=item.item_state,
                severity=item.severity,
                priority=item.priority,
                title=item.title,
                description=item.description,
                owner=item.owner,
                reviewer=item.reviewer,
                generated_at=item.generated_at,
                reason_codes=item.reason_codes,
                metadata=item.metadata,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Priority and sorting
# ---------------------------------------------------------------------------


def _assign_priority(item: RemediationBacklogItem) -> RemediationBacklogItem:
    """Assign priority using first-match rule semantics."""
    priority = RemediationBacklogPriority.NONE
    if item.severity is RemediationBacklogSeverity.BLOCKING and item.item_state is RemediationBacklogItemState.OPEN:
        priority = RemediationBacklogPriority.P0
    elif item.severity is RemediationBacklogSeverity.ADVISORY and item.item_state is RemediationBacklogItemState.OPEN:
        priority = RemediationBacklogPriority.P1
    elif item.severity is RemediationBacklogSeverity.INFO and item.item_state is RemediationBacklogItemState.OPEN:
        priority = RemediationBacklogPriority.P2
    elif item.item_state in (RemediationBacklogItemState.ACKNOWLEDGED, RemediationBacklogItemState.DEFERRED):
        priority = RemediationBacklogPriority.P3
    elif item.item_state in (RemediationBacklogItemState.DUPLICATE, RemediationBacklogItemState.CONFLICTING, RemediationBacklogItemState.NOT_APPLICABLE):
        priority = RemediationBacklogPriority.NONE
    return RemediationBacklogItem(
        item_id=item.item_id,
        subject_id=item.subject_id,
        source_id=item.source_id,
        finding_id=item.finding_id,
        item_type=item.item_type,
        item_state=item.item_state,
        severity=item.severity,
        priority=priority,
        title=item.title,
        description=item.description,
        owner=item.owner,
        reviewer=item.reviewer,
        generated_at=item.generated_at,
        reason_codes=item.reason_codes,
        metadata=item.metadata,
    )


def _priority_sort_key(item: RemediationBacklogItem) -> tuple[int, int, str, str]:
    """Return a sort key for deterministic item ordering."""
    priority_order = {
        RemediationBacklogPriority.P0: 0,
        RemediationBacklogPriority.P1: 1,
        RemediationBacklogPriority.P2: 2,
        RemediationBacklogPriority.P3: 3,
        RemediationBacklogPriority.NONE: 4,
    }
    severity_order = {
        RemediationBacklogSeverity.BLOCKING: 0,
        RemediationBacklogSeverity.ADVISORY: 1,
        RemediationBacklogSeverity.INFO: 2,
    }
    generated_at_str = item.generated_at.isoformat() if item.generated_at is not None else ""
    item_id_str = item.item_id or ""
    return (
        priority_order[item.priority],
        severity_order[item.severity],
        generated_at_str,
        item_id_str,
    )


def _sort_items(items: list[RemediationBacklogItem]) -> list[RemediationBacklogItem]:
    """Sort items by priority, severity, generated_at, item_id."""
    return sorted(items, key=_priority_sort_key)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _aggregate_state(
    items: list[RemediationBacklogItem],
    safety_flags: RemediationBacklogSafetyFlags,
    strict: bool,
    is_truly_empty: bool,
) -> tuple[RemediationBacklogState, tuple[RemediationBacklogReasonCode, ...]]:
    """Compute aggregate report state and reason codes."""
    if not safety_flags.is_safe:
        return RemediationBacklogState.BLOCKED, (
            RemediationBacklogReasonCode.SAFETY_BLOCKED,
            RemediationBacklogReasonCode.UNSAFE_CONTENT,
        )

    if is_truly_empty:
        return RemediationBacklogState.NOT_APPLICABLE, (
            RemediationBacklogReasonCode.NOT_APPLICABLE,
        )

    has_blocking_open = False
    has_advisory_open = False
    for item in items:
        if item.item_state is RemediationBacklogItemState.OPEN and item.severity is RemediationBacklogSeverity.BLOCKING:
            has_blocking_open = True
        elif item.item_state is RemediationBacklogItemState.OPEN and item.severity is RemediationBacklogSeverity.ADVISORY:
            has_advisory_open = True

    if has_blocking_open:
        state = RemediationBacklogState.BLOCKED
        reason_codes = (RemediationBacklogReasonCode.CONSISTENCY_DEGRADED,)
    elif has_advisory_open:
        state = RemediationBacklogState.DEGRADED
        reason_codes = (RemediationBacklogReasonCode.CONSISTENCY_DEGRADED,)
    else:
        state = RemediationBacklogState.OK
        reason_codes = (RemediationBacklogReasonCode.OK,)

    if strict and state is RemediationBacklogState.DEGRADED:
        state = RemediationBacklogState.BLOCKED
        reason_codes = (RemediationBacklogReasonCode.SAFETY_BLOCKED,)

    return state, reason_codes


# ---------------------------------------------------------------------------
# Public engine
# ---------------------------------------------------------------------------


def build_remediation_backlog_report(
    input: RemediationBacklogInput,
) -> RemediationBacklogReport:
    """Build a deterministic remediation backlog report from caller-provided input.

    The engine never opens, follows, traverses, validates, fetches, or executes
    any path or reference string. References are treated as opaque identifiers.
    """
    generated_at = input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)

    # Safety scan.
    unsafe_offenders = _scan_unsafe_content(input)
    forbidden_offenders = _scan_forbidden_terms(input)
    has_unsafe_content = len(unsafe_offenders) > 0
    has_forbidden_terms = len(forbidden_offenders) > 0

    safety_flags = RemediationBacklogSafetyFlags(
        has_unsafe_content=has_unsafe_content,
        has_forbidden_terms=has_forbidden_terms,
    )

    counters: dict[str, int] = {
        "total_sources": len(input.source_refs),
        "total_findings": len(input.finding_refs),
        "total_backlog_items": len(input.backlog_items),
        "total_dependencies": len(input.dependencies),
        "total_acknowledgements": 0,
        "total_issues": 0,
        "duplicate_id_count": 0,
        "duplicate_item_count": 0,
        "orphan_finding_count": 0,
        "orphan_dependency_count": 0,
        "cycle_count": 0,
        "conflicting_item_count": 0,
        "stale_source_count": 0,
        "stale_finding_count": 0,
        "missing_owner_count": 0,
        "missing_reviewer_count": 0,
        "missing_manual_review_count": 0,
        "unsafe_content_count": 0,
        "forbidden_term_count": 0,
        "sections_present": 0,
    }

    issues: list[RemediationBacklogItem] = []

    if has_unsafe_content:
        issues.append(_issue(
            item_type=RemediationBacklogItemType.UNSAFE_CONTENT,
            severity=RemediationBacklogSeverity.BLOCKING,
            reason_codes=(RemediationBacklogReasonCode.UNSAFE_CONTENT,),
            title="Unsafe content detected",
            description=f"non-string values found in input: {len(unsafe_offenders)} offender(s)",
        ))
        counters["unsafe_content_count"] += 1

    if has_forbidden_terms:
        issues.append(_issue(
            item_type=RemediationBacklogItemType.UNSAFE_CONTENT,
            severity=RemediationBacklogSeverity.BLOCKING,
            reason_codes=(RemediationBacklogReasonCode.FORBIDDEN_TERM_PRESENT,),
            title="Forbidden term detected",
            description=f"forbidden terms found in caller-provided text: {len(forbidden_offenders)} offender(s)",
        ))
        counters["forbidden_term_count"] += 1

    # Detection pipeline.
    _detect_duplicate_ids(input, issues, counters)
    _detect_required_sources(input, issues, counters)
    _detect_orphan_findings(input, issues, counters)
    _detect_orphan_dependencies(input, issues, counters)
    _detect_dependency_cycles(input, issues, counters)
    _detect_stale_refs(input, generated_at, issues, counters)
    _detect_conflicting_states(input, issues, counters)
    _detect_missing_metadata(input, issues, counters)

    # Merge caller-provided items with engine-generated issues.
    all_items: list[RemediationBacklogItem] = list(input.backlog_items) + issues

    # Apply acknowledgements, deduplicate, assign IDs, assign priorities, sort.
    all_items = _apply_acknowledgements(input, all_items, counters)
    all_items = _deduplicate_items(all_items, counters)
    all_items = _assign_item_ids(all_items)
    all_items = [_assign_priority(item) for item in all_items]
    all_items = _sort_items(all_items)

    # Aggregate state.
    state, reason_codes = _aggregate_state(
        all_items,
        safety_flags,
        input.config.strict,
        _is_truly_empty(input),
    )

    # Final derived counters.
    counters["total_backlog_items"] = len(all_items)
    counters["total_issues"] = len(issues)
    counters["sections_present"] = len({_norm_id(i.subject_id) for i in all_items if _is_valid_id(i.subject_id)})

    data_quality = RemediationBacklogDataQuality(
        total_sources=counters["total_sources"],
        total_findings=counters["total_findings"],
        total_backlog_items=counters["total_backlog_items"],
        total_dependencies=counters["total_dependencies"],
        total_acknowledgements=counters["total_acknowledgements"],
        total_issues=counters["total_issues"],
        duplicate_id_count=counters["duplicate_id_count"],
        duplicate_item_count=counters["duplicate_item_count"],
        orphan_finding_count=counters["orphan_finding_count"],
        orphan_dependency_count=counters["orphan_dependency_count"],
        cycle_count=counters["cycle_count"],
        conflicting_item_count=counters["conflicting_item_count"],
        stale_source_count=counters["stale_source_count"],
        stale_finding_count=counters["stale_finding_count"],
        missing_owner_count=counters["missing_owner_count"],
        missing_reviewer_count=counters["missing_reviewer_count"],
        missing_manual_review_count=counters["missing_manual_review_count"],
        unsafe_content_count=counters["unsafe_content_count"],
        forbidden_term_count=counters["forbidden_term_count"],
        sections_present=counters["sections_present"],
    )

    # Safety notice.
    safety_notice = (
        "This remediation backlog is a local, audit-only research artifact. "
        "It is not an approval, certification, production readiness assessment, "
        "trading readiness assessment, recommendation, suitability assessment, signal, "
        "or executable remediation plan. It does not emit shell commands, code patches, "
        "deployment steps, or trading actions. All references are opaque identifiers "
        "and are never opened, followed, traversed, validated, fetched, or executed."
    )

    return RemediationBacklogReport(
        report_id=_build_report_id(input, generated_at),
        generated_at=generated_at,
        state=state,
        project_version=_resolve_project_version(input),
        source_refs=tuple(sorted(input.source_refs, key=lambda s: _norm_id(s.source_id))),
        finding_refs=tuple(sorted(input.finding_refs, key=lambda f: _norm_id(f.finding_id))),
        backlog_items=tuple(all_items),
        dependencies=tuple(sorted(input.dependencies, key=lambda d: _norm_id(d.dependency_id))),
        acknowledgements=tuple(sorted(input.acknowledgements, key=lambda a: _norm_id(a.acknowledgement_id))),
        issues=tuple(issues),
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        metadata=input.metadata,
        safety_notice=safety_notice,
    )

