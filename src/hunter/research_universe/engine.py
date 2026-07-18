"""Research universe engine (MVP-64 / SPEC-065 Stage 5)."""

from __future__ import annotations

from datetime import datetime, timezone

from hunter.controlled_universe.models import ControlledUniverseReport
from hunter.portfolio_construction.models import PortfolioConstructionReport
from hunter.research_market_data.models import ResearchMarketDataBundle
from hunter.research_universe.baseline import build_baseline_universe
from hunter.research_universe.candidate import build_candidate_universe
from hunter.research_universe.comparison import compare_universes
from hunter.research_universe.eligibility import build_eligibility_policy_fingerprint
from hunter.research_universe.errors import ResearchUniverseConfigError, ResearchUniverseValidationError
from hunter.research_universe.fingerprint import (
    report_fingerprint,
    universe_comparison_fingerprint,
)
from hunter.research_universe.models import (
    INVALID_BUNDLE,
    MISSING_BUNDLE,
    ResearchUniverseConfig,
    ResearchUniverseManifest,
    ResearchUniverseReport,
    ResearchUniverseSafetyFlags,
    RESEARCH_UNIVERSE_VERSION,
    SPEC_VERSION,
)


def _validate_inputs(
    bundle: ResearchMarketDataBundle | None,
    controlled_report: ControlledUniverseReport | None,
    portfolio_report: PortfolioConstructionReport | None,
    config: ResearchUniverseConfig | None,
) -> tuple[str, ...]:
    """Structural validation of required inputs."""
    reasons: list[str] = []
    if config is None:
        raise ResearchUniverseConfigError("config is required")
    if bundle is None:
        reasons.append(MISSING_BUNDLE)
    elif not isinstance(bundle, ResearchMarketDataBundle):
        reasons.append(INVALID_BUNDLE)
    if controlled_report is None:
        reasons.append(MISSING_BUNDLE)
    elif not isinstance(controlled_report, ControlledUniverseReport):
        reasons.append(INVALID_BUNDLE)
    if portfolio_report is not None and not isinstance(portfolio_report, PortfolioConstructionReport):
        reasons.append(INVALID_BUNDLE)
    return tuple(reasons)


def build_research_universe_report(
    *,
    bundle: ResearchMarketDataBundle | None,
    controlled_report: ControlledUniverseReport | None,
    portfolio_report: PortfolioConstructionReport | None,
    config: ResearchUniverseConfig | None,
) -> ResearchUniverseReport:
    """Build the research universe report.

    This is the top-level orchestrator. It produces a deterministic, research-only
    report containing candidate universe, baseline universe, and their comparison.
    No Freqtrade runtime integration, no action commands, no config mutation.
    """
    structural_reasons = _validate_inputs(bundle, controlled_report, portfolio_report, config)
    if structural_reasons:
        raise ResearchUniverseValidationError(
            f"Research universe inputs invalid: {', '.join(structural_reasons)}"
        )
    assert config is not None
    assert bundle is not None
    assert controlled_report is not None

    policy_fingerprint = build_eligibility_policy_fingerprint(config)
    baseline = build_baseline_universe(bundle, config)
    candidate = build_candidate_universe(controlled_report, portfolio_report, config)
    comparison = compare_universes(candidate, baseline)

    safety_flags = ResearchUniverseSafetyFlags()

    manifest = ResearchUniverseManifest(
        version=RESEARCH_UNIVERSE_VERSION,
        spec_version=SPEC_VERSION,
        research_universe_version=RESEARCH_UNIVERSE_VERSION,
        generated_at=datetime.now(timezone.utc),
        bundle_fingerprint=bundle.manifest.bundle_fingerprint,
        policy_fingerprint=policy_fingerprint,
        selection_window=config.selection_window,
        candidate_fingerprint=candidate.fingerprint,
        baseline_fingerprint=baseline.fingerprint,
        comparison_fingerprint=universe_comparison_fingerprint(comparison),
        safety_flags=safety_flags,
        reason_codes=(),
        metadata={
            "controlled_universe_version": controlled_report.version,
            "portfolio_construction_version": portfolio_report.version if portfolio_report else "",
        },
    )

    metadata: dict[str, str] = {
        "generated_at": manifest.generated_at.isoformat(),
        "bundle_candidate_count": str(len(bundle.candidates)),
        "controlled_universe_count": str(len(controlled_report.universe)),
    }

    report_payload = {
        "version": manifest.version,
        "spec_version": manifest.spec_version,
        "config": config,
        "manifest": manifest,
        "candidate": candidate,
        "baseline": baseline,
        "comparison": comparison,
        "safety_flags": safety_flags,
        "metadata": metadata,
    }
    fingerprint = report_fingerprint(report_payload)

    return ResearchUniverseReport(
        version=manifest.version,
        spec_version=manifest.spec_version,
        config=config,
        manifest=manifest,
        candidate=candidate,
        baseline=baseline,
        comparison=comparison,
        safety_flags=safety_flags,
        metadata=metadata,
        fingerprint=fingerprint,
        human_approval_required=True,
        research_only=True,
        reason_codes=(),
    )
