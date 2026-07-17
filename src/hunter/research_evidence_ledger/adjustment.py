"""Multiple-testing adjustment for the research evidence ledger (MVP-68 / SPEC-069).

Implements deterministic Benjamini-Hochberg FDR and Bonferroni correction.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from hunter.research_evidence_ledger.fingerprint import adjusted_evidence_fingerprint
from hunter.research_evidence_ledger.models import (
    ADJUSTMENT_INVALID_INPUT,
    AdjustedEvidence,
    AdjustmentConfig,
    AdjustmentMethod,
    EvidenceLedgerAdjustmentError,
)


def _validate_raw_values(
    raw_values: list[tuple[str, str, Decimal]],
) -> None:
    """Validate all raw values are in [0, 1]."""
    for experiment_id, metric_name, val in raw_values:
        if val < Decimal("0") or val > Decimal("1"):
            raise EvidenceLedgerAdjustmentError(
                f"Raw value {val} for {experiment_id}/{metric_name} is outside [0, 1]",
                reason_code=ADJUSTMENT_INVALID_INPUT,
            )


def _get_effective_family_size(config: AdjustmentConfig, n: int) -> int:
    """Return the effective family size for adjustment."""
    if config.family_size > 0:
        return config.family_size
    return n


def adjust_benjamini_hochberg(
    raw_values: list[tuple[str, str, Decimal]],
    config: AdjustmentConfig,
) -> list[AdjustedEvidence]:
    """Apply Benjamini-Hochberg FDR adjustment.

    Args:
        raw_values: List of (experiment_id, metric_name, raw_value) tuples.
        config: Adjustment configuration with family_id, family_size, and alpha.

    Returns:
        List of AdjustedEvidence in canonical order (original input order).

    The algorithm:
    1. Validate raw values are in [0, 1].
    2. Sort by raw value ascending, then canonical evidence ID (experiment_id + metric_name).
    3. Compute adjusted = raw * family_size / rank for each.
    4. Enforce monotonicity from largest rank backward.
    5. Clamp to 1.
    6. Restore canonical ordering.
    7. Preserve raw values.
    """
    _validate_raw_values(raw_values)

    n = len(raw_values)
    if n == 0:
        return []

    effective_family_size = _get_effective_family_size(config, n)
    if effective_family_size < n:
        raise EvidenceLedgerAdjustmentError(
            f"family_size ({effective_family_size}) cannot be less than value count ({n})",
            reason_code=ADJUSTMENT_INVALID_INPUT,
        )

    # Build list with canonical IDs for sorting
    items: list[dict[str, Any]] = []
    for experiment_id, metric_name, raw_value in raw_values:
        canonical_id = f"{experiment_id}:{metric_name}"
        items.append({
            "experiment_id": experiment_id,
            "metric_name": metric_name,
            "raw_value": raw_value,
            "canonical_id": canonical_id,
        })

    # Step 2: Sort by raw value ascending, then by canonical ID for determinism
    sorted_items = sorted(items, key=lambda x: (x["raw_value"], x["canonical_id"]))

    # Step 3: Compute initial adjusted values
    family_size_dec = Decimal(str(effective_family_size))

    for rank, item in enumerate(sorted_items, start=1):
        raw = item["raw_value"]
        adjusted = raw * family_size_dec / Decimal(str(rank))
        item["adjusted_value"] = adjusted
        item["sorted_rank"] = rank

    # Step 4: Enforce monotonicity from largest rank backward
    for i in range(n - 2, -1, -1):
        if sorted_items[i]["adjusted_value"] > sorted_items[i + 1]["adjusted_value"]:
            sorted_items[i]["adjusted_value"] = sorted_items[i + 1]["adjusted_value"]

    # Step 5: Clamp to 1
    for item in sorted_items:
        if item["adjusted_value"] > Decimal("1"):
            item["adjusted_value"] = Decimal("1")

    # Step 6: Restore canonical ordering (original input order)
    # Build lookup by canonical_id
    adjusted_by_canonical: dict[str, Decimal] = {}
    rank_by_canonical: dict[str, int] = {}
    for item in sorted_items:
        adjusted_by_canonical[item["canonical_id"]] = item["adjusted_value"]
        rank_by_canonical[item["canonical_id"]] = item["sorted_rank"]

    # Reconstruct in original order
    result: list[AdjustedEvidence] = []
    for experiment_id, metric_name, raw_value in raw_values:
        canonical_id = f"{experiment_id}:{metric_name}"
        adjusted = adjusted_by_canonical[canonical_id]
        rank = rank_by_canonical[canonical_id]

        ev = AdjustedEvidence(
            experiment_id=experiment_id,
            metric_name=metric_name,
            raw_value=raw_value,
            adjusted_value=adjusted,
            family_id=config.family_id,
            family_type=config.family_type,
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            rank=rank,
            family_size=effective_family_size,
            alpha=config.alpha,
        )
        fp = adjusted_evidence_fingerprint(ev)
        object.__setattr__(ev, "fingerprint", fp)
        result.append(ev)

    return result


def adjust_bonferroni(
    raw_values: list[tuple[str, str, Decimal]],
    config: AdjustmentConfig,
) -> list[AdjustedEvidence]:
    """Apply Bonferroni correction.

    Args:
        raw_values: List of (experiment_id, metric_name, raw_value) tuples.
        config: Adjustment configuration.

    Returns:
        List of AdjustedEvidence in canonical order.
    """
    _validate_raw_values(raw_values)

    n = len(raw_values)
    if n == 0:
        return []

    effective_family_size = _get_effective_family_size(config, n)
    if effective_family_size < n:
        raise EvidenceLedgerAdjustmentError(
            f"family_size ({effective_family_size}) cannot be less than value count ({n})",
            reason_code=ADJUSTMENT_INVALID_INPUT,
        )

    family_size_dec = Decimal(str(effective_family_size))

    result: list[AdjustedEvidence] = []
    for rank, (experiment_id, metric_name, raw_value) in enumerate(raw_values, start=1):
        adjusted = raw_value * family_size_dec
        if adjusted > Decimal("1"):
            adjusted = Decimal("1")

        ev = AdjustedEvidence(
            experiment_id=experiment_id,
            metric_name=metric_name,
            raw_value=raw_value,
            adjusted_value=adjusted,
            family_id=config.family_id,
            family_type=config.family_type,
            method=AdjustmentMethod.BONFERRONI,
            rank=rank,
            family_size=effective_family_size,
            alpha=config.alpha,
        )
        fp = adjusted_evidence_fingerprint(ev)
        object.__setattr__(ev, "fingerprint", fp)
        result.append(ev)

    return result


def adjust(
    raw_values: list[tuple[str, str, Decimal]],
    config: AdjustmentConfig,
) -> list[AdjustedEvidence]:
    """Apply the configured adjustment method to raw evidence values."""
    if config.method == AdjustmentMethod.BENJAMINI_HOCHBERG:
        return adjust_benjamini_hochberg(raw_values, config)
    if config.method == AdjustmentMethod.BONFERRONI:
        return adjust_bonferroni(raw_values, config)
    raise EvidenceLedgerAdjustmentError(
        f"Unknown adjustment method: {config.method}",
        reason_code=ADJUSTMENT_INVALID_INPUT,
    )
