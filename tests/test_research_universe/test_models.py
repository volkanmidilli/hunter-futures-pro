"""Tests for research_universe models (MVP-64 Stage 1)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from hunter.research_universe.models import (
    RESEARCH_UNIVERSE_VERSION,
    SPEC_VERSION,
    BaselineUniverseResult,
    CandidateUniverseResult,
    PairEligibilityResult,
    ResearchUniverseComparison,
    ResearchUniverseConfig,
    ResearchUniverseManifest,
    ResearchUniverseReport,
    ResearchUniverseSafetyFlags,
    ResearchUniverseWriterError,
    SelectionWindow,
    UniversePairClassification,
    UniversePairDecision,
    UniversePairDecisionKind,
    UniversePairState,
    EMPTY_CANDIDATE_UNIVERSE,
)


class TestSelectionWindow:
    def test_valid_window(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 10, tzinfo=timezone.utc)
        w = SelectionWindow(start=start, end=end)
        assert w.start == start
        assert w.end == end
        assert start in w

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValueError):
            SelectionWindow(
                start=datetime(2024, 1, 1),
                end=datetime(2024, 1, 10),
            )

    def test_end_before_start_rejected(self) -> None:
        with pytest.raises(ValueError):
            SelectionWindow(
                start=datetime(2024, 1, 10, tzinfo=timezone.utc),
                end=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )


class TestResearchUniverseConfig:
    def test_default_config(self) -> None:
        w = SelectionWindow(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 10, tzinfo=timezone.utc),
        )
        config = ResearchUniverseConfig(selection_window=w)
        assert config.quote_currency == "USDT"
        assert config.min_coverage_ratio == 0.8

    def test_invalid_coverage_rejected(self) -> None:
        w = SelectionWindow(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 10, tzinfo=timezone.utc),
        )
        with pytest.raises(ValueError):
            ResearchUniverseConfig(selection_window=w, min_coverage_ratio=1.5)


class TestSafetyFlags:
    def test_defaults(self) -> None:
        flags = ResearchUniverseSafetyFlags()
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False

    def test_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            ResearchUniverseSafetyFlags(research_only=False)


class TestPairEligibilityResult:
    def test_eligible(self) -> None:
        r = PairEligibilityResult(
            pair="SOL/USDT",
            is_eligible=True,
            coverage=0.95,
            source_fingerprint="abc",
        )
        assert r.is_eligible is True

    def test_invalid_coverage(self) -> None:
        with pytest.raises(ValueError):
            PairEligibilityResult(
                pair="SOL/USDT",
                is_eligible=True,
                coverage=1.5,
                source_fingerprint="abc",
            )


class TestUniversePairDecision:
    def test_decision(self) -> None:
        d = UniversePairDecision(
            pair="SOL/USDT",
            decision=UniversePairDecisionKind.INCLUDED,
            state=UniversePairState.CANDIDATE,
            classification=UniversePairClassification.LONG_RESEARCH,
            rank=1,
            score=80.0,
            coverage=0.95,
            estimated_quote_volume=Decimal("1000000"),
            source_fingerprint="abc",
        )
        assert d.pair == "SOL/USDT"


class TestUniverseResults:
    def _make_pairlist(self, pairs: tuple[str, ...]) -> dict:
        return {"method": "StaticPairList", "pairs": list(pairs)}

    def _make_candidate(self, pairs: tuple[str, ...]) -> CandidateUniverseResult:
        decisions = tuple(
            UniversePairDecision(
                pair=p,
                decision=UniversePairDecisionKind.INCLUDED,
                state=UniversePairState.CANDIDATE,
                classification=UniversePairClassification.LONG_RESEARCH,
                rank=i + 1,
            )
            for i, p in enumerate(pairs)
        )
        return CandidateUniverseResult(
            decisions=decisions,
            pairlist=self._make_pairlist(pairs),
            fingerprint="fp-candidate",
            safety_flags=ResearchUniverseSafetyFlags(),
            reason_codes=(EMPTY_CANDIDATE_UNIVERSE,),
        )

    def _make_baseline(self, pairs: tuple[str, ...]) -> BaselineUniverseResult:
        decisions = tuple(
            UniversePairDecision(
                pair=p,
                decision=UniversePairDecisionKind.INCLUDED,
                state=UniversePairState.BASELINE,
                classification=UniversePairClassification.BASELINE_VOLUME,
                rank=i + 1,
            )
            for i, p in enumerate(pairs)
        )
        return BaselineUniverseResult(
            decisions=decisions,
            pairlist=self._make_pairlist(pairs),
            fingerprint="fp-baseline",
            safety_flags=ResearchUniverseSafetyFlags(),
            reason_codes=(),
        )

    def test_candidate_pairs(self) -> None:
        c = self._make_candidate(("SOL/USDT", "BTC/USDT"))
        assert c.pairs == ("SOL/USDT", "BTC/USDT")

    def test_comparison(self) -> None:
        c = self._make_candidate(("SOL/USDT",))
        b = self._make_baseline(("SOL/USDT", "ETH/USDT"))
        comp = ResearchUniverseComparison(
            overlap=("SOL/USDT",),
            candidate_only=(),
            baseline_only=("ETH/USDT",),
            union_count=2,
            jaccard_similarity=0.5,
            fingerprint="fp-comp",
            safety_flags=ResearchUniverseSafetyFlags(),
            reason_codes=(),
        )
        assert comp.jaccard_similarity == 0.5


class TestManifestAndReport:
    def test_manifest(self) -> None:
        w = SelectionWindow(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 10, tzinfo=timezone.utc),
        )
        m = ResearchUniverseManifest(
            version=RESEARCH_UNIVERSE_VERSION,
            spec_version=SPEC_VERSION,
            research_universe_version=RESEARCH_UNIVERSE_VERSION,
            generated_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
            bundle_fingerprint="fp-bundle",
            policy_fingerprint="fp-policy",
            selection_window=w,
            candidate_fingerprint="fp-candidate",
            baseline_fingerprint="fp-baseline",
            comparison_fingerprint="fp-comp",
            safety_flags=ResearchUniverseSafetyFlags(),
            reason_codes=(),
        )
        assert m.version == RESEARCH_UNIVERSE_VERSION

    def test_writer_error(self) -> None:
        err = ResearchUniverseWriterError("write failed", reason_code="FILE_EXISTS")
        assert err.reason_code == "FILE_EXISTS"
