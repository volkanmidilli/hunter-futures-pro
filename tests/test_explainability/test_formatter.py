"""Formatter tests: human output shape and canonical JSON (SPEC-078)."""

from __future__ import annotations

import json

from hunter.explainability.formatter import format_human, format_json, lookup_result_to_dict
from hunter.explainability.models import (
    EXPLAINABILITY_SCHEMA_VERSION,
    REASON_NOT_IN_UNIVERSE,
    REASON_OUTSIDE_TARGET_FINAL_PAIRS,
    STAGE_FAIL,
    STAGE_PASS,
    CandidateExplanationRecord,
    CandidateStageDecision,
    ExplainabilityRunManifest,
)
from hunter.explainability.service import LOOKUP_OK, ExplainLookupResult


def _record() -> CandidateExplanationRecord:
    return CandidateExplanationRecord(
        schema_version=EXPLAINABILITY_SCHEMA_VERSION,
        run_id="2026-07-27__V1_RS_OI__abcdef123456",
        completed_at="2026-07-27T00:00:00+00:00",
        pair="BTC/USDT:USDT",
        stages=(
            CandidateStageDecision(
                stage_id="universe",
                stage_order=1,
                status=STAGE_PASS,
                metrics={"universe_total": 412, "eligible_count": 50},
            ),
            CandidateStageDecision(
                stage_id="ranking",
                stage_order=5,
                status=STAGE_FAIL,
                metrics={"rank": 31},
                thresholds={"target_final_pairs": 20},
                reason_codes=(REASON_OUTSIDE_TARGET_FINAL_PAIRS,),
            ),
        ),
        score_components={"rs_score": "72.30", "oi_score": "50"},
        final_rank=31,
        eligible_candidate_count=50,
        target_final_pairs=20,
        selected=False,
        published=False,
        final_reason_codes=(REASON_OUTSIDE_TARGET_FINAL_PAIRS,),
    )


def _manifest() -> ExplainabilityRunManifest:
    return ExplainabilityRunManifest(
        schema_version=EXPLAINABILITY_SCHEMA_VERSION,
        run_id="2026-07-27__V1_RS_OI__abcdef123456",
        completed_at="2026-07-27T00:00:00+00:00",
        as_of_date="2026-07-27",
        ranking_profile="V1_RS_OI",
        universe_total=412,
        eligible_count=50,
        selected_count=20,
        target_final_pairs=20,
        min_pairs=5,
        max_pairs=50,
        gate_allowed=True,
        published=True,
        eligible_pairs=("BTC/USDT:USDT",),
    )


class TestHumanFormat:
    def test_full_record_shape(self) -> None:
        result = ExplainLookupResult(
            status=LOOKUP_OK,
            reason_codes=(REASON_OUTSIDE_TARGET_FINAL_PAIRS,),
            pair="BTC/USDT:USDT",
            record=_record(),
            manifest=_manifest(),
        )
        text = format_human(result)
        lines = text.splitlines()
        assert lines[0] == f"{'PAIR':<20}BTC/USDT:USDT"
        assert f"{'RUN':<20}2026-07-27__V1_RS_OI__abcdef123456" in lines
        assert f"{'SELECTED':<20}NO" in lines
        assert f"{'PUBLISHED':<20}NO" in lines
        assert f"{'FINAL RANK':<20}31 / 50" in lines
        assert f"{'TARGET':<20}20" in lines
        assert f"{'FINAL REASON':<20}{REASON_OUTSIDE_TARGET_FINAL_PAIRS}" in lines
        assert "STAGES" in lines
        assert any(line.startswith("01  universe") and "PASS" in line for line in lines)
        ranking_line = next(line for line in lines if line.startswith("05  ranking"))
        assert "FAIL" in ranking_line
        assert "rank=31" in ranking_line
        assert "target_final_pairs=20" in ranking_line
        assert REASON_OUTSIDE_TARGET_FINAL_PAIRS in ranking_line

    def test_missing_values_rendered_unknown(self) -> None:
        record = CandidateExplanationRecord(
            schema_version=EXPLAINABILITY_SCHEMA_VERSION,
            run_id="run-1",
            completed_at="2026-07-27T00:00:00+00:00",
            pair="BTC/USDT:USDT",
        )
        result = ExplainLookupResult(
            status=LOOKUP_OK, reason_codes=(), pair="BTC/USDT:USDT", record=record
        )
        text = format_human(result)
        assert f"{'SELECTED':<20}UNKNOWN" in text.splitlines()
        assert f"{'FINAL SCORE':<20}UNKNOWN" in text.splitlines()
        assert f"{'FINAL RANK':<20}UNKNOWN" in text.splitlines()

    def test_not_in_universe_reports_run_and_reason(self) -> None:
        result = ExplainLookupResult(
            status=REASON_NOT_IN_UNIVERSE,
            reason_codes=(REASON_NOT_IN_UNIVERSE,),
            pair="SOL/USDT:USDT",
            manifest=_manifest(),
        )
        text = format_human(result)
        assert "SOL/USDT:USDT" in text
        assert "2026-07-27__V1_RS_OI__abcdef123456" in text
        assert REASON_NOT_IN_UNIVERSE in text
        assert "NOT_RECORDED" in text  # selected/published are not recorded

    def test_no_manifest_renders_unknown_run(self) -> None:
        result = ExplainLookupResult(
            status="NO_SUCCESSFUL_RUN",
            reason_codes=("NO_SUCCESSFUL_RUN",),
            pair="BTC/USDT:USDT",
        )
        text = format_human(result)
        assert f"{'RUN':<20}UNKNOWN" in text.splitlines()


class TestJsonFormat:
    def test_json_contains_canonical_record(self) -> None:
        record = _record()
        result = ExplainLookupResult(
            status=LOOKUP_OK,
            reason_codes=(REASON_OUTSIDE_TARGET_FINAL_PAIRS,),
            pair="BTC/USDT:USDT",
            record=record,
            manifest=_manifest(),
        )
        payload = json.loads(format_json(result))
        assert payload["schema_version"] == EXPLAINABILITY_SCHEMA_VERSION
        assert payload["status"] == LOOKUP_OK
        assert payload["pair"] == "BTC/USDT:USDT"
        assert payload["run_id"] == "2026-07-27__V1_RS_OI__abcdef123456"
        # The record inside the envelope is exactly the canonical model.
        assert payload["record"] == record.to_dict()
        assert payload["record"]["stages"][1]["reason_codes"] == [
            REASON_OUTSIDE_TARGET_FINAL_PAIRS
        ]

    def test_json_fail_closed_has_null_record(self) -> None:
        result = ExplainLookupResult(
            status=REASON_NOT_IN_UNIVERSE,
            reason_codes=(REASON_NOT_IN_UNIVERSE,),
            pair="SOL/USDT:USDT",
            manifest=_manifest(),
        )
        payload = json.loads(format_json(result))
        assert payload["record"] is None
        assert payload["status"] == REASON_NOT_IN_UNIVERSE
        assert payload["reason_codes"] == [REASON_NOT_IN_UNIVERSE]

    def test_json_is_deterministic(self) -> None:
        result = ExplainLookupResult(
            status=LOOKUP_OK,
            reason_codes=("OK",),
            pair="BTC/USDT:USDT",
            record=_record(),
            manifest=_manifest(),
        )
        assert format_json(result) == format_json(result)

    def test_lookup_envelope_round_trips_through_dict(self) -> None:
        result = ExplainLookupResult(
            status=LOOKUP_OK,
            reason_codes=("OK",),
            pair="BTC/USDT:USDT",
            record=_record(),
            manifest=_manifest(),
        )
        payload = lookup_result_to_dict(result)
        json.dumps(payload)  # must be JSON-serializable
