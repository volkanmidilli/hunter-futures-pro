"""Public API for the research universe builder (MVP-64 / SPEC-065)."""

from __future__ import annotations

from hunter.research_universe.baseline import build_baseline_universe
from hunter.research_universe.candidate import build_candidate_universe
from hunter.research_universe.comparison import compare_universes
from hunter.research_universe.eligibility import (
    assess_pair_eligibility,
    build_eligibility_policy_fingerprint,
)
from hunter.research_universe.engine import build_research_universe_report
from hunter.research_universe.errors import (
    ResearchUniverseBundleError,
    ResearchUniverseConfigError,
    ResearchUniverseError,
    ResearchUniverseValidationError,
    ResearchUniverseWriterError,
)
from hunter.research_universe.fingerprint import (
    baseline_universe_fingerprint,
    candidate_universe_fingerprint,
    policy_fingerprint,
    report_fingerprint,
    universe_comparison_fingerprint,
)
from hunter.research_universe.models import (
    BaselineUniverseResult,
    CandidateUniverseResult,
    PairEligibilityResult,
    ResearchUniverseComparison,
    ResearchUniverseConfig,
    ResearchUniverseManifest,
    ResearchUniverseReport,
    ResearchUniverseSafetyFlags,
    SelectionWindow,
    UniversePairClassification,
    UniversePairDecision,
    UniversePairDecisionKind,
    UniversePairState,
)
from hunter.research_universe.writer import (
    ResearchUniverseWriter,
    write_all_research_universe_artifacts,
    write_research_universe_report,
)

__all__ = [
    "assess_pair_eligibility",
    "baseline_universe_fingerprint",
    "build_baseline_universe",
    "build_candidate_universe",
    "build_eligibility_policy_fingerprint",
    "build_research_universe_report",
    "candidate_universe_fingerprint",
    "compare_universes",
    "policy_fingerprint",
    "report_fingerprint",
    "universe_comparison_fingerprint",
    "BaselineUniverseResult",
    "CandidateUniverseResult",
    "PairEligibilityResult",
    "ResearchUniverseComparison",
    "ResearchUniverseConfig",
    "ResearchUniverseError",
    "ResearchUniverseConfigError",
    "ResearchUniverseBundleError",
    "ResearchUniverseValidationError",
    "ResearchUniverseWriterError",
    "ResearchUniverseManifest",
    "ResearchUniverseReport",
    "ResearchUniverseSafetyFlags",
    "ResearchUniverseWriter",
    "SelectionWindow",
    "UniversePairClassification",
    "UniversePairDecision",
    "UniversePairDecisionKind",
    "UniversePairState",
    "write_all_research_universe_artifacts",
    "write_research_universe_report",
]

RESEARCH_UNIVERSE_VERSION: str = "0.64.0-dev"
SPEC_VERSION: str = "SPEC-065"
