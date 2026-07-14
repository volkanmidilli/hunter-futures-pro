"""Engine for the Governance Handoff Package Builder (MVP-62).

The engine consumes a ``GovernanceDecisionSummary`` (MVP-61), a
``ResearchDecisionGateReport`` (MVP-59), and the latest accepted
``HumanReviewRecord`` (MVP-60), and produces one immutable, research-only
``ResearchGovernanceHandoffPackage``.

The engine does not read/write files, read the clock internally, mutate caller
input, or import real Freqtrade runtime modules.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Mapping

from hunter.governance_handoff.models import (
    GOVERNANCE_HANDOFF_VERSION,
    GovernanceHandoffConfig,
    GovernanceHandoffError,
    HandoffSourceReference,
    ResearchGovernanceHandoffPackage,
)
from hunter.governance_handoff.policy import (
    build_handoff_manifest,
    build_handoff_safety_flags,
    build_source_references,
    classify_handoff_reasons,
    resolve_handoff_allowed,
)
from hunter.governance_handoff.validator import (
    validate_all,
    validate_source_versions,
)

if TYPE_CHECKING:
    from hunter.governance_summary.models import GovernanceDecisionSummary
    from hunter.human_review_registry.models import HumanReviewRecord
    from hunter.research_decision_gate.models import ResearchDecisionGateReport


def _canonical_json(payload: object) -> str:
    """Return deterministic compact JSON for hashing."""
    return json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


def _iso(value: datetime) -> str:
    """Return an ISO-8601 string for a timezone-aware datetime."""
    return value.astimezone().isoformat()


def _serialize_config(config: GovernanceHandoffConfig) -> dict[str, Any]:
    """Serialize config into a deterministic JSON-safe dict."""
    return {
        "require_latest_accepted_review": config.require_latest_accepted_review,
        "output_dir": str(config.output_dir),
        "report_output_dir": str(config.report_output_dir),
        "json_filename": config.json_filename,
        "markdown_filename": config.markdown_filename,
    }


def compute_package_fingerprint(
    governance_status: str,
    handoff_allowed: bool,
    governance_source: object,
    gate_source: object,
    review_source: object | None,
    blocking_reason_codes: tuple[str, ...],
    review_reason_codes: tuple[str, ...],
    safety_flags: Mapping[str, bool],
    artifact_filenames: Mapping[str, str],
    source_versions: Mapping[str, str],
    config: GovernanceHandoffConfig,
    built_at: datetime,
) -> str:
    """Compute a deterministic SHA-256 fingerprint for a handoff package."""
    payload = {
        "version": GOVERNANCE_HANDOFF_VERSION,
        "governance_status": governance_status,
        "handoff_allowed": handoff_allowed,
        "governance_source": {
            "source_name": governance_source.source_name,
            "source_version": governance_source.source_version,
            "fingerprint": governance_source.fingerprint,
            "accepted": governance_source.accepted,
            "reason_codes": list(governance_source.reason_codes),
        },
        "gate_source": {
            "source_name": gate_source.source_name,
            "source_version": gate_source.source_version,
            "fingerprint": gate_source.fingerprint,
            "accepted": gate_source.accepted,
            "reason_codes": list(gate_source.reason_codes),
        },
        "review_source": None
        if review_source is None
        else {
            "source_name": review_source.source_name,
            "source_version": review_source.source_version,
            "fingerprint": review_source.fingerprint,
            "accepted": review_source.accepted,
            "reason_codes": list(review_source.reason_codes),
        },
        "blocking_reason_codes": list(blocking_reason_codes),
        "review_reason_codes": list(review_reason_codes),
        "safety_flags": dict(sorted(safety_flags.items())),
        "artifact_filenames": dict(sorted(artifact_filenames.items())),
        "source_versions": dict(sorted(source_versions.items())),
        "config": _serialize_config(config),
        "built_at": _iso(built_at),
    }
    canonical = _canonical_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_research_governance_handoff_package(
    governance_summary: GovernanceDecisionSummary | None,
    gate_report: ResearchDecisionGateReport | None,
    latest_accepted_review: HumanReviewRecord | None,
    config: GovernanceHandoffConfig,
    *,
    built_at: datetime,
    metadata: Mapping[str, object] | None = None,
) -> ResearchGovernanceHandoffPackage:
    """Build a deterministic, immutable governance handoff package.

    Pipeline:
      1. validate config
      2. validate sources and provenance links
      3. classify reasons
      4. resolve handoff_allowed
      5. build source references
      6. build manifest
      7. compute fingerprint
      8. immutable package
    """
    if not isinstance(config, GovernanceHandoffConfig):
        raise GovernanceHandoffError(
            "config must be a GovernanceHandoffConfig",
            reason_code="INVALID_CONFIG",
        )

    if metadata is None:
        metadata = {}

    # Validate all inputs and provenance links.
    blocking_validation_reasons = validate_all(
        governance_summary,
        gate_report,
        latest_accepted_review,
        config,
        built_at=built_at,
    )

    # Derive governance status; fall back to BLOCKED when summary is missing.
    governance_status = getattr(governance_summary, "governance_status", "BLOCKED")
    if governance_summary is None:
        governance_status = "BLOCKED"

    # Source-level reason split for references. Each source carries only its
    # own validation reasons.
    governance_reasons = validate_all(
        governance_summary, None, None, config, built_at=built_at
    )
    gate_reasons = validate_all(
        None, gate_report, None, config, built_at=built_at
    )
    review_reasons = validate_all(
        None, None, latest_accepted_review, config, built_at=built_at
    )

    blocking_reason_codes, review_reason_codes = classify_handoff_reasons(
        governance_summary,
        blocking_validation_reasons,
        metadata,
    )

    handoff_allowed = resolve_handoff_allowed(
        governance_status,
        blocking_reason_codes,
        review_reason_codes,
    )

    governance_source, gate_source, review_source = build_source_references(
        governance_summary,
        gate_report,
        latest_accepted_review,
        governance_reasons,
        gate_reasons,
        review_reasons,
    )

    safety_flags = build_handoff_safety_flags()
    artifact_filenames = {
        "json": config.json_filename,
        "markdown": config.markdown_filename,
    }

    source_versions = {
        governance_source.source_name: governance_source.source_version,
        gate_source.source_name: gate_source.source_version,
    }
    if review_source is not None:
        source_versions[review_source.source_name] = review_source.source_version

    source_version_errors = validate_source_versions(source_versions)
    if source_version_errors:
        blocking_reason_codes = tuple(
            sorted(set(blocking_reason_codes) | set(source_version_errors))
        )
        handoff_allowed = False
        governance_source = HandoffSourceReference(
            source_name=governance_source.source_name,
            source_version=governance_source.source_version,
            fingerprint=governance_source.fingerprint,
            accepted=False,
            reason_codes=governance_source.reason_codes,
        )
        gate_source = HandoffSourceReference(
            source_name=gate_source.source_name,
            source_version=gate_source.source_version,
            fingerprint=gate_source.fingerprint,
            accepted=False,
            reason_codes=gate_source.reason_codes,
        )
        if review_source is not None:
            review_source = HandoffSourceReference(
                source_name=review_source.source_name,
                source_version=review_source.source_version,
                fingerprint=review_source.fingerprint,
                accepted=False,
                reason_codes=review_source.reason_codes,
            )

    package_fingerprint = compute_package_fingerprint(
        governance_status=governance_status,
        handoff_allowed=handoff_allowed,
        governance_source=governance_source,
        gate_source=gate_source,
        review_source=review_source,
        blocking_reason_codes=blocking_reason_codes,
        review_reason_codes=review_reason_codes,
        safety_flags=safety_flags,
        artifact_filenames=artifact_filenames,
        source_versions=source_versions,
        config=config,
        built_at=built_at,
    )

    manifest = build_handoff_manifest(
        package_version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint=package_fingerprint,
        built_at=built_at,
        governance_source=governance_source,
        gate_source=gate_source,
        review_source=review_source,
        safety_flags=safety_flags,
        artifact_filenames=artifact_filenames,
    )

    return ResearchGovernanceHandoffPackage(
        version=GOVERNANCE_HANDOFF_VERSION,
        package_fingerprint=package_fingerprint,
        built_at=built_at,
        governance_status=governance_status,  # type: ignore[arg-type]
        handoff_allowed=handoff_allowed,
        governance_source=governance_source,
        gate_source=gate_source,
        review_source=review_source,
        blocking_reason_codes=blocking_reason_codes,
        review_reason_codes=review_reason_codes,
        manifest=manifest,
        research_only=True,
        execution_approval_granted=False,
        production_approval_granted=False,
        metadata=metadata,
    )


__all__ = [
    "build_research_governance_handoff_package",
    "compute_package_fingerprint",
]
