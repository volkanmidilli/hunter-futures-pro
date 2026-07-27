"""Recorder tests: stage decisions derived from real pipeline outputs (SPEC-078)."""

from __future__ import annotations

from decimal import Decimal

from hunter.explainability.models import (
    REASON_OUTSIDE_TARGET_FINAL_PAIRS,
    REASON_PUBLISH_BLOCKED,
    STAGE_FAIL,
    STAGE_PASS,
    STAGE_SKIP,
)
from hunter.explainability.recorder import (
    PairlistRunObservation,
    build_run_id,
    build_run_records,
)
from hunter.pairlist_export.models import (
    REASON_BELOW_MIN_PAIRS,
    REASON_DATA_SUFFICIENCY,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_OI_LIQUIDITY,
    REASON_PROFILE_EVIDENCE_INCOMPLETE,
    REASON_RS_SCORE,
    RankedPair,
)

_COMPLETED_AT = "2026-07-27T00:00:00+00:00"


def _ranked(
    pair: str,
    rank: int,
    selected: bool,
    reason_codes: tuple[str, ...] = (REASON_RS_SCORE, REASON_OI_LIQUIDITY),
    rs: str | None = "80",
    oi: str | None = "50",
    dq: str | None = None,
) -> RankedPair:
    return RankedPair(
        pair=pair,
        rank=rank,
        selected=selected,
        rs_score=Decimal(rs) if rs is not None else None,
        oi_score=Decimal(oi) if oi is not None else None,
        data_quality_pct=Decimal(dq) if dq is not None else None,
        reason_codes=reason_codes,
        fingerprint=f"fp-{pair}",
    )


def _observation(
    ranked: tuple[RankedPair, ...],
    *,
    profile: str = "V1_RS_OI",
    gate_allowed: bool = True,
    gate_reason_codes: tuple[str, ...] = ("OK",),
    published: bool = True,
    target: int = 20,
    dq_scores: dict | None = None,
) -> PairlistRunObservation:
    return PairlistRunObservation(
        as_of_date="2026-07-27",
        ranking_profile=profile,
        universe_total=412,
        eligible_pairs=tuple(p.pair for p in ranked),
        ranked_pairs=ranked,
        target_final_pairs=target,
        min_pairs=5,
        max_pairs=50,
        gate_allowed=gate_allowed,
        gate_reason_codes=gate_reason_codes,
        published=published,
        data_quality_scores=dq_scores,
    )


def _build(observation: PairlistRunObservation):
    return build_run_records(observation, completed_at=_COMPLETED_AT)


def _stage_map(record):
    return {stage.stage_id: stage for stage in record.stages}


class TestStageOrdering:
    def test_six_stages_in_pipeline_order(self) -> None:
        _, records = _build(_observation((_ranked("BTC/USDT:USDT", 1, True),)))
        stages = records[0].stages
        assert [s.stage_id for s in stages] == [
            "universe",
            "data_quality",
            "liquidity",
            "relative_strength",
            "ranking",
            "publish",
        ]
        assert [s.stage_order for s in stages] == [1, 2, 3, 4, 5, 6]


class TestSelectedCandidate:
    def test_selected_published_candidate(self) -> None:
        _, records = _build(_observation((_ranked("BTC/USDT:USDT", 1, True),)))
        record = records[0]
        assert record.selected is True
        assert record.published is True
        assert record.final_reason_codes == ("OK",)
        assert record.final_rank == 1
        stages = _stage_map(record)
        assert stages["universe"].status == STAGE_PASS
        assert stages["relative_strength"].status == STAGE_PASS
        assert stages["liquidity"].status == STAGE_PASS
        assert stages["ranking"].status == STAGE_PASS
        assert stages["publish"].status == STAGE_PASS
        assert stages["ranking"].thresholds["target_final_pairs"] == 20


class TestOutsideCutoffCandidate:
    def test_outside_target_final_pairs(self) -> None:
        obs = _observation((_ranked("BTC/USDT:USDT", 31, False),), target=20)
        _, records = _build(obs)
        record = records[0]
        assert record.selected is False
        assert record.published is False
        assert record.final_reason_codes == (REASON_OUTSIDE_TARGET_FINAL_PAIRS,)
        stages = _stage_map(record)
        assert stages["ranking"].status == STAGE_FAIL
        assert stages["ranking"].reason_codes == (REASON_OUTSIDE_TARGET_FINAL_PAIRS,)
        assert stages["ranking"].metrics["rank"] == 31
        assert stages["publish"].status == STAGE_SKIP


class TestExcludedBeforeRanking:
    def test_insufficient_evidence_uses_real_pipeline_code(self) -> None:
        pair = _ranked(
            "ETH/USDT:USDT",
            50,
            False,
            reason_codes=(REASON_INSUFFICIENT_EVIDENCE,),
            rs=None,
            oi=None,
        )
        _, records = _build(_observation((pair,)))
        record = records[0]
        assert record.final_reason_codes == (REASON_INSUFFICIENT_EVIDENCE,)
        stages = _stage_map(record)
        assert stages["relative_strength"].status == STAGE_FAIL
        assert stages["liquidity"].status == STAGE_FAIL
        assert stages["ranking"].status == STAGE_FAIL
        assert stages["ranking"].reason_codes == (REASON_INSUFFICIENT_EVIDENCE,)
        assert REASON_OUTSIDE_TARGET_FINAL_PAIRS not in stages["ranking"].reason_codes

    def test_v2_profile_incomplete_evidence(self) -> None:
        pair = _ranked(
            "ETH/USDT:USDT",
            50,
            False,
            reason_codes=(REASON_RS_SCORE, REASON_PROFILE_EVIDENCE_INCOMPLETE),
            oi=None,
        )
        _, records = _build(_observation((pair,), profile="V2_RS_LIQUIDITY"))
        record = records[0]
        assert record.final_reason_codes == (REASON_PROFILE_EVIDENCE_INCOMPLETE,)
        stages = _stage_map(record)
        # RS is present and required under v2: PASS; liquidity missing: FAIL.
        assert stages["relative_strength"].status == STAGE_PASS
        assert stages["liquidity"].status == STAGE_FAIL


class TestEvidenceSkipStates:
    def test_v1_missing_oi_is_skip_not_fail_when_rs_present(self) -> None:
        pair = _ranked(
            "BTC/USDT:USDT", 1, True, reason_codes=(REASON_RS_SCORE,), oi=None
        )
        _, records = _build(_observation((pair,)))
        stages = _stage_map(records[0])
        assert stages["liquidity"].status == STAGE_SKIP
        assert stages["relative_strength"].status == STAGE_PASS

    def test_v1_missing_data_quality_is_skip(self) -> None:
        _, records = _build(_observation((_ranked("BTC/USDT:USDT", 1, True),)))
        assert _stage_map(records[0])["data_quality"].status == STAGE_SKIP

    def test_v2_missing_data_quality_is_fail(self) -> None:
        pair = _ranked(
            "BTC/USDT:USDT",
            1,
            True,
            reason_codes=(REASON_RS_SCORE, REASON_PROFILE_EVIDENCE_INCOMPLETE),
        )
        _, records = _build(_observation((pair,), profile="V2_RS_LIQUIDITY"))
        assert _stage_map(records[0])["data_quality"].status == STAGE_FAIL


class TestMetricsPreservation:
    def test_real_scores_recorded_as_strings(self) -> None:
        _, records = _build(_observation((_ranked("BTC/USDT:USDT", 1, True, rs="82.5", oi="71.0"),)))
        record = records[0]
        assert record.score_components["rs_score"] == "82.5"
        assert record.score_components["oi_score"] == "71.0"
        assert record.score_components["liquidity_score"] is None
        stages = _stage_map(record)
        assert stages["relative_strength"].metrics["rs_score"] == "82.5"

    def test_data_quality_falls_back_to_observed_input_map(self) -> None:
        # v1 RankedPair does not carry data_quality_pct; the recorder must
        # record the genuine value the ranking consumed from the input map.
        pair = _ranked(
            "BTC/USDT:USDT",
            1,
            True,
            reason_codes=(REASON_RS_SCORE, REASON_OI_LIQUIDITY, REASON_DATA_SUFFICIENCY),
        )
        obs = _observation((pair,), dq_scores={"BTC/USDT:USDT": Decimal("97.5")})
        _, records = _build(obs)
        record = records[0]
        assert record.score_components["data_quality_pct"] == "97.5"
        stage = _stage_map(record)["data_quality"]
        assert stage.status == STAGE_PASS
        assert stage.metrics["data_quality_pct"] == "97.5"
        assert REASON_DATA_SUFFICIENCY in stage.reason_codes

    def test_run_level_metrics_recorded(self) -> None:
        _, records = _build(_observation((_ranked("BTC/USDT:USDT", 1, True),)))
        stage = _stage_map(records[0])["universe"]
        assert stage.metrics["universe_total"] == 412
        assert stage.metrics["eligible_count"] == 1


class TestPublishBlocked:
    def test_gate_rejected_run_marks_selected_pair_publish_blocked(self) -> None:
        obs = _observation(
            (_ranked("BTC/USDT:USDT", 1, True),),
            gate_allowed=False,
            gate_reason_codes=(REASON_BELOW_MIN_PAIRS,),
            published=False,
        )
        _, records = _build(obs)
        record = records[0]
        assert record.selected is True
        assert record.published is False
        assert record.final_reason_codes == (
            REASON_PUBLISH_BLOCKED,
            REASON_BELOW_MIN_PAIRS,
        )
        stage = _stage_map(record)["publish"]
        assert stage.status == STAGE_FAIL
        assert stage.reason_codes == (REASON_PUBLISH_BLOCKED, REASON_BELOW_MIN_PAIRS)


class TestManifestAndRunId:
    def test_manifest_records_run_level_truth(self) -> None:
        ranked = (
            _ranked("BTC/USDT:USDT", 1, True),
            _ranked("ETH/USDT:USDT", 2, False),
        )
        manifest, records = _build(_observation(ranked, target=1))
        assert manifest.eligible_count == 2
        assert manifest.selected_count == 1
        assert manifest.target_final_pairs == 1
        assert manifest.gate_allowed is True
        assert manifest.published is True
        assert manifest.eligible_pairs == ("BTC/USDT:USDT", "ETH/USDT:USDT")
        assert all(r.run_id == manifest.run_id for r in records)

    def test_run_id_is_deterministic_for_identical_output(self) -> None:
        ranked = (_ranked("BTC/USDT:USDT", 1, True),)
        assert build_run_id(_observation(ranked)) == build_run_id(_observation(ranked))

    def test_run_id_changes_with_pipeline_output(self) -> None:
        assert build_run_id(_observation((_ranked("BTC/USDT:USDT", 1, True),))) != build_run_id(
            _observation((_ranked("BTC/USDT:USDT", 2, False),))
        )
