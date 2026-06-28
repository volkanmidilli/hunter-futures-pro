"""Engine for hunter.research_bundle package.

In-memory functions for building bundle items, summaries, data quality, safety
flags, and full research bundles. No file I/O, no network, no database.

MVP-14 bundles are human-audit artifacts only.
They are not trading signals, not trade approvals, and must not be consumed by
execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    DEFAULT_BLOCKED,
    EMPTY_BUNDLE,
    INVALID_BUNDLE,
    INVALID_ITEM,
    INVALID_REFERENCE,
    MISSING_ITEMS,
    MISSING_REFERENCE,
    UNSAFE_BUNDLE_CONTENT,
    UNSAFE_ITEM_CONTENT,
    UNSAFE_SAFETY_FLAGS,
    BUNDLE_ERROR,
    MAX_ITEMS_EXCEEDED,
    FORBIDDEN_BUNDLE_TERMS,
    BundleConfig,
    BundleDataQuality,
    BundleItem,
    BundleItemKind,
    BundleSafetyFlags,
    BundleState,
    BundleSummary,
    ResearchBundle,
)


def has_unsafe_bundle_content(text: str) -> bool:
    """Case-insensitive check for forbidden terms in bundle text.

    Does not open, traverse, validate, follow, or execute file references.
    """
    if not text:
        return False
    lower = text.lower()
    for term in FORBIDDEN_BUNDLE_TERMS:
        if term in lower:
            return True
    return False


def build_bundle_safety_flags(config: BundleConfig | None = None) -> BundleSafetyFlags:
    """Build safety flags from config. Config is advisory only."""
    return BundleSafetyFlags()


def validate_bundle_item(
    item: Any,
    safety_flags: BundleSafetyFlags | None = None,
) -> tuple[bool, str]:
    """Validate a single bundle item. Returns (is_valid, reason_code).

    Fail-closed: returns False on any invalid or unsafe input.
    """
    if not isinstance(item, BundleItem):
        return False, INVALID_ITEM

    if not item.item_id:
        return False, MISSING_REFERENCE

    if not item.reference:
        return False, MISSING_REFERENCE

    if not isinstance(item.kind, BundleItemKind):
        return False, INVALID_ITEM

    # Check for unsafe content in label, note, reference
    for text in (item.label, item.note, item.reference):
        if has_unsafe_bundle_content(text):
            return False, UNSAFE_ITEM_CONTENT

    return True, ""


def build_bundle_item(
    kind: BundleItemKind,
    reference: str,
    item_id: str = "",
    label: str = "",
    note: str = "",
    sort_order: int = 0,
    metadata: dict[str, Any] | None = None,
) -> BundleItem:
    """Build a single bundle item with validation.

    Args:
        kind: The kind of artifact being referenced.
        reference: A local string reference (file path or artifact ID).
        item_id: Unique identifier for this item. Defaults to a hash of reference.
        label: Optional human-readable label.
        note: Optional human-readable note.
        sort_order: Deterministic ordering within the bundle.
        metadata: Optional key-value metadata (immutable).

    Returns:
        A validated BundleItem.

    Raises:
        ValueError: If forbidden content is detected in label, note, reference, or metadata keys.
    """
    if not item_id:
        item_id = f"item-{kind.value}-{hash(reference) & 0xFFFFFFFF:08x}"

    # Validate forbidden content before construction
    for text in (label, note, reference):
        if has_unsafe_bundle_content(text):
            raise ValueError(f"forbidden term in {text!r}")
    if metadata:
        for key in metadata:
            if has_unsafe_bundle_content(key):
                raise ValueError(f"forbidden term in metadata key {key!r}")

    return BundleItem(
        item_id=item_id,
        kind=kind,
        reference=reference,
        label=label,
        note=note,
        sort_order=sort_order,
        metadata=metadata if metadata is not None else {},
    )


def build_bundle_summary(items: tuple[BundleItem, ...]) -> BundleSummary:
    """Build summary from items, counting by kind.

    Items are sorted by sort_order then item_id for deterministic output.
    """
    sorted_items = sorted(items, key=lambda i: (i.sort_order, i.item_id))

    counts = {kind: 0 for kind in BundleItemKind}
    for item in sorted_items:
        counts[item.kind] += 1

    return BundleSummary(
        total_items=len(sorted_items),
        observation_report_count=counts[BundleItemKind.OBSERVATION_REPORT],
        review_audit_count=counts[BundleItemKind.REVIEW_AUDIT],
        review_index_count=counts[BundleItemKind.REVIEW_INDEX],
        search_result_count=counts[BundleItemKind.SEARCH_RESULT],
        human_note_count=sum(1 for i in sorted_items if i.note),
    )


def build_bundle_data_quality(items: tuple[BundleItem, ...]) -> BundleDataQuality:
    """Build data quality metrics from items.

    Tracks which artifact kinds are present and counts invalid references.
    """
    has = {kind: False for kind in BundleItemKind}
    missing_refs = 0
    invalid_refs = 0

    for item in items:
        has[item.kind] = True
        if not item.reference:
            missing_refs += 1
        if not item.item_id:
            invalid_refs += 1

    return BundleDataQuality(
        total_items=len(items),
        missing_references=missing_refs,
        invalid_references=invalid_refs,
        has_observation_report=has[BundleItemKind.OBSERVATION_REPORT],
        has_review_audit=has[BundleItemKind.REVIEW_AUDIT],
        has_review_index=has[BundleItemKind.REVIEW_INDEX],
        has_search_result=has[BundleItemKind.SEARCH_RESULT],
        has_human_note=has[BundleItemKind.HUMAN_NOTE],
    )


def build_research_bundle(
    items: tuple[BundleItem, ...],
    config: BundleConfig | None = None,
    now: datetime | None = None,
) -> ResearchBundle:
    """Fail-closed bundle builder. Returns BLOCKED bundle on any error.

    Args:
        items: Tuple of BundleItem references to include.
        config: Optional configuration. Uses defaults if not provided.
        now: Optional timestamp. Uses UTC now if not provided.

    Returns:
        A ResearchBundle, either READY or BLOCKED.
    """
    if config is None:
        config = BundleConfig()

    if now is None:
        now = datetime.now(timezone.utc)

    # Determine bundle ID from items + timestamp for reproducibility
    item_ids = ",".join(sorted(item.item_id for item in items))
    bundle_hash = hash(item_ids + now.isoformat()) & 0xFFFFFFFF
    bundle_id = f"bundle-{bundle_hash:08x}-{now.strftime('%Y%m%d-%H%M%S')}"

    # Fail-closed checks
    reason_codes: tuple[str, ...] = ()
    state = BundleState.READY
    truncated_items = items

    if not items:
        reason_codes = (EMPTY_BUNDLE,)
        state = BundleState.BLOCKED
    elif len(items) > config.max_items:
        reason_codes = (MAX_ITEMS_EXCEEDED,)
        state = BundleState.BLOCKED
        truncated_items = ()  # Truncate to avoid __post_init__ rejection
    else:
        # Validate each item
        for item in items:
            is_valid, reason = validate_bundle_item(item)
            if not is_valid:
                reason_codes = (reason,)
                state = BundleState.BLOCKED
                break

    # Build safety flags (always safe)
    safety_flags = build_bundle_safety_flags(config)

    # Build summary and data quality
    summary = build_bundle_summary(truncated_items)
    data_quality = build_bundle_data_quality(truncated_items)

    return ResearchBundle(
        bundle_id=bundle_id,
        generated_at=now,
        bundle_state=state,
        items=truncated_items,
        summary=summary,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        config=config,
    )
