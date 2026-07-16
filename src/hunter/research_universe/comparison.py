"""Universe comparison utilities (MVP-64 / SPEC-065 Stage 6)."""

from __future__ import annotations

from hunter.research_universe.models import (
    BaselineUniverseResult,
    CandidateUniverseResult,
    ResearchUniverseComparison,
    ResearchUniverseSafetyFlags,
)
from hunter.research_universe.fingerprint import universe_comparison_fingerprint


def compare_universes(
    candidate: CandidateUniverseResult,
    baseline: BaselineUniverseResult,
) -> ResearchUniverseComparison:
    """Compare candidate and baseline universes deterministically."""
    candidate_set = set(candidate.pairs)
    baseline_set = set(baseline.pairs)

    overlap = tuple(sorted(candidate_set & baseline_set))
    candidate_only = tuple(sorted(candidate_set - baseline_set))
    baseline_only = tuple(sorted(baseline_set - candidate_set))
    union = candidate_set | baseline_set

    union_count = len(union)
    jaccard = 0.0
    if union_count:
        jaccard = len(candidate_set & baseline_set) / union_count

    safety_flags = ResearchUniverseSafetyFlags()
    comparison = ResearchUniverseComparison(
        overlap=overlap,
        candidate_only=candidate_only,
        baseline_only=baseline_only,
        union_count=union_count,
        jaccard_similarity=jaccard,
        safety_flags=safety_flags,
        fingerprint="PENDING",
        reason_codes=(),
    )
    object.__setattr__(comparison, "fingerprint", universe_comparison_fingerprint(comparison))
    return comparison
