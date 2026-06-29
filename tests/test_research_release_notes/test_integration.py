"""Integration tests for hunter.research_release_notes.

MVP-20 Step 3 — end-to-end integration tests covering engine → writer flows,
determinism, safety assertions, serialization round-trips, and fail-closed
behavior.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from hunter.research_release_notes.engine import (
    build_release_notes_change_item,
    build_release_notes_data_quality,
    build_release_notes_safety_flags,
    build_release_notes_section,
    build_release_notes_summary,
    build_research_release_notes,
    has_unsafe_release_notes_content,
)
from hunter.research_release_notes.models import (
    FORBIDDEN_RELEASE_NOTES_TERMS,
    RELEASE_NOTES_ARTIFACT_INFO,
    RELEASE_NOTES_REASON_CODES,
    ReleaseNotesChangeItem,
    ReleaseNotesChangeSeverity,
    ReleaseNotesConfig,
    ReleaseNotesSafetyFlags,
    ReleaseNotesSection,
    ReleaseNotesSectionKind,
    ReleaseNotesState,
    ResearchReleaseNotes,
)
from hunter.research_release_notes.writer import (
    DEFAULT_RESEARCH_RELEASE_NOTES_JSON_PATH,
    DEFAULT_RESEARCH_RELEASE_NOTES_MARKDOWN_PATH,
    atomic_write_json_research_release_notes,
    atomic_write_markdown_research_release_notes,
    research_release_notes_to_dict,
    research_release_notes_to_markdown,
    write_research_release_notes,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_safety_flags(*, dry_run: bool = True) -> ReleaseNotesSafetyFlags:
    return ReleaseNotesSafetyFlags(dry_run=dry_run)


def _make_unsafe_safety_flags(unsafe_attr: str = "live_trading_enabled") -> ReleaseNotesSafetyFlags:
    flags = object.__new__(ReleaseNotesSafetyFlags)
    object.__setattr__(flags, "dry_run", True)
    object.__setattr__(flags, "live_trading_enabled", False)
    object.__setattr__(flags, "real_orders_enabled", False)
    object.__setattr__(flags, "leverage_enabled", False)
    object.__setattr__(flags, "shorting_enabled", False)
    object.__setattr__(flags, "release_notes_output_is_human_audit_only", True)
    object.__setattr__(flags, "release_notes_output_not_trading_signal", True)
    object.__setattr__(flags, "release_notes_output_not_trade_approval", True)
    object.__setattr__(flags, "release_notes_output_not_execution_readiness", True)
    object.__setattr__(flags, "release_notes_output_not_strategy_readiness", True)
    object.__setattr__(flags, "release_notes_output_not_release_approval", True)
    object.__setattr__(flags, "release_notes_output_not_deployment_approval", True)
    object.__setattr__(flags, "release_notes_output_not_transaction_permission", True)
    object.__setattr__(flags, "release_notes_output_not_for_execution", True)
    object.__setattr__(flags, "release_notes_output_not_for_strategy", True)
    object.__setattr__(flags, "release_notes_output_not_for_freqtrade", True)
    object.__setattr__(flags, "release_notes_output_not_for_order", True)
    object.__setattr__(flags, "release_notes_output_not_for_exchange", True)
    object.__setattr__(flags, "release_notes_feedback_into_execution", False)
    object.__setattr__(flags, "cross_layer_feedback_into_execution", False)
    object.__setattr__(flags, "file_refs_not_traversed", True)
    object.__setattr__(flags, "artifact_files_not_read", True)
    object.__setattr__(flags, "no_action_commands_emitted", True)
    object.__setattr__(flags, unsafe_attr, True)
    return flags


def _make_artifact(
    state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    safety_flags: ReleaseNotesSafetyFlags | None = None,
    version: str = "1.0",
) -> object:
    if safety_flags is None:
        safety_flags = _make_safety_flags()

    class Artifact:
        pass

    artifact = Artifact()
    artifact.state = state
    artifact.reason_codes = reason_codes
    artifact.safety_flags = safety_flags
    artifact.version = version
    return artifact


def _make_artifact_dict(
    state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    safety_flags: ReleaseNotesSafetyFlags | None = None,
    version: str = "1.0",
) -> dict[str, object]:
    if safety_flags is None:
        safety_flags = _make_safety_flags()
    return {
        "state": state,
        "reason_codes": reason_codes,
        "safety_flags": safety_flags,
        "version": version,
    }


def _make_change_item(
    *,
    title: str = "Change",
    severity: str = "INFO",
    related_mvp: str = "MVP-20",
    change_kind: str = "feature",
) -> ReleaseNotesChangeItem:
    return build_release_notes_change_item(
        title=title,
        description="Description.",
        change_kind=change_kind,
        severity=severity,
        related_mvp=related_mvp,
        spec_reference="SPEC-021",
    )


def _ready_kwargs() -> dict[str, object]:
    """Return kwargs for a READY release notes with all required sections."""
    return {
        "release_version": "0.20.0-dev",
        "release_title": "MVP-20 Research Release Notes",
        "change_items_by_section": {
            ReleaseNotesSectionKind.COMPLETED_MVPS: (
                _make_change_item(title="Completed MVP-19", related_mvp="MVP-19"),
                _make_change_item(title="Completed MVP-18", related_mvp="MVP-18"),
            ),
            ReleaseNotesSectionKind.KNOWN_GAPS: (
                _make_change_item(
                    title="Future integration review",
                    severity="MEDIUM",
                    change_kind="gap",
                ),
            ),
        },
        "config": ReleaseNotesConfig(generated_at=_now()),
        "reference_time": _now(),
    }


# ---------------------------------------------------------------------------
# 1. End-to-end build
# ---------------------------------------------------------------------------


class TestEndToEndBuild:
    def test_build_from_loaded_artifacts(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        assert rn.release_notes_state is ReleaseNotesState.READY
        assert rn.summary.total_sections >= 6
        assert rn.summary.total_change_items >= 3

    def test_build_from_dict_artifacts(self) -> None:
        artifacts = {
            "manifest": _make_artifact_dict("READY"),
            "handoff": _make_artifact_dict("READY"),
        }
        rn = build_research_release_notes(
            **_ready_kwargs(),
            input_artifacts=artifacts,
        )
        assert rn.release_notes_state is ReleaseNotesState.READY


# ---------------------------------------------------------------------------
# 2. Deterministic section ordering
# ---------------------------------------------------------------------------


class TestDeterministicSectionOrdering:
    def test_section_order(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        kinds = [s.section_kind for s in rn.sections]
        expected = [
            ReleaseNotesSectionKind.OVERVIEW,
            ReleaseNotesSectionKind.VERSION_AND_SCOPE,
            ReleaseNotesSectionKind.ARTIFACT_CHAIN,
            ReleaseNotesSectionKind.COMPLETED_MVPS,
            ReleaseNotesSectionKind.KNOWN_GAPS,
            ReleaseNotesSectionKind.SAFETY_BOUNDARIES,
            ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE,
            ReleaseNotesSectionKind.APPENDIX_REFERENCES,
        ]
        assert kinds == expected

    def test_order_independent_of_input(self) -> None:
        rn = build_research_release_notes(
            change_items_by_section={
                ReleaseNotesSectionKind.KNOWN_GAPS: (_make_change_item(),),
                ReleaseNotesSectionKind.COMPLETED_MVPS: (_make_change_item(),),
            },
            config=ReleaseNotesConfig(generated_at=_now()),
            reference_time=_now(),
        )
        kinds = [s.section_kind for s in rn.sections]
        completed_idx = kinds.index(ReleaseNotesSectionKind.COMPLETED_MVPS)
        gaps_idx = kinds.index(ReleaseNotesSectionKind.KNOWN_GAPS)
        assert completed_idx < gaps_idx


# ---------------------------------------------------------------------------
# 3. Deterministic change item ordering
# ---------------------------------------------------------------------------


class TestDeterministicChangeItemOrdering:
    def test_order_by_severity_then_mvp(self) -> None:
        rn = build_research_release_notes(
            change_items_by_section={
                ReleaseNotesSectionKind.COMPLETED_MVPS: (
                    _make_change_item(
                        title="Low older",
                        severity="LOW",
                        related_mvp="MVP-10",
                    ),
                    _make_change_item(
                        title="Critical newer",
                        severity="CRITICAL",
                        related_mvp="MVP-20",
                    ),
                    _make_change_item(
                        title="High older",
                        severity="HIGH",
                        related_mvp="MVP-15",
                    ),
                )
            },
            config=ReleaseNotesConfig(generated_at=_now()),
            reference_time=_now(),
        )
        section = next(
            s for s in rn.sections
            if s.section_kind is ReleaseNotesSectionKind.COMPLETED_MVPS
        )
        titles = [item.title for item in section.change_items]
        assert titles == [
            "Critical newer",
            "High older",
            "Low older",
        ]

    def test_insertion_order_tiebreak(self) -> None:
        rn = build_research_release_notes(
            change_items_by_section={
                ReleaseNotesSectionKind.COMPLETED_MVPS: (
                    _make_change_item(title="First", severity="INFO", related_mvp="MVP-20"),
                    _make_change_item(title="Second", severity="INFO", related_mvp="MVP-20"),
                    _make_change_item(title="Third", severity="INFO", related_mvp="MVP-20"),
                )
            },
            config=ReleaseNotesConfig(generated_at=_now()),
            reference_time=_now(),
        )
        section = next(
            s for s in rn.sections
            if s.section_kind is ReleaseNotesSectionKind.COMPLETED_MVPS
        )
        titles = [item.title for item in section.change_items]
        assert titles == ["First", "Second", "Third"]


# ---------------------------------------------------------------------------
# 4. READY state
# ---------------------------------------------------------------------------


class TestReadyState:
    def test_all_required_sections_present(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        assert rn.release_notes_state is ReleaseNotesState.READY
        assert rn.summary.release_notes_state == "READY"
        assert "EMPTY_SECTION" not in rn.reason_codes
        for prefix in ("MISSING_COMPLETED_MVPS", "MISSING_KNOWN_GAPS"):
            assert prefix not in rn.reason_codes


# ---------------------------------------------------------------------------
# 5. WARN state
# ---------------------------------------------------------------------------


class TestWarnState:
    def test_warn_for_explicitly_empty_required_section(self) -> None:
        # Caller explicitly provides an empty required section.
        rn = build_research_release_notes(
            change_items_by_section={
                ReleaseNotesSectionKind.COMPLETED_MVPS: (),
                ReleaseNotesSectionKind.KNOWN_GAPS: (_make_change_item(),),
            },
            config=ReleaseNotesConfig(generated_at=_now()),
            reference_time=_now(),
        )
        assert rn.release_notes_state is ReleaseNotesState.WARN
        assert "EMPTY_SECTION" in rn.reason_codes


# ---------------------------------------------------------------------------
# 6. BLOCK state for missing required sections
# ---------------------------------------------------------------------------


class TestBlockState:
    def test_block_for_missing_completed_mvps(self) -> None:
        rn = build_research_release_notes(
            change_items_by_section={
                ReleaseNotesSectionKind.KNOWN_GAPS: (_make_change_item(),),
            },
            config=ReleaseNotesConfig(generated_at=_now()),
            reference_time=_now(),
        )
        assert rn.release_notes_state is ReleaseNotesState.BLOCK
        assert "MISSING_COMPLETED_MVPS" in rn.reason_codes

    def test_block_for_missing_known_gaps(self) -> None:
        rn = build_research_release_notes(
            change_items_by_section={
                ReleaseNotesSectionKind.COMPLETED_MVPS: (_make_change_item(),),
            },
            config=ReleaseNotesConfig(generated_at=_now()),
            reference_time=_now(),
        )
        assert rn.release_notes_state is ReleaseNotesState.BLOCK
        assert "MISSING_KNOWN_GAPS" in rn.reason_codes


# ---------------------------------------------------------------------------
# 7. BLOCK state for unsafe content
# ---------------------------------------------------------------------------


class TestUnsafeContent:
    def test_block_for_unsafe_release_title(self) -> None:
        rn = build_research_release_notes(
            release_title="Deploy now to production",
            change_items_by_section={
                ReleaseNotesSectionKind.COMPLETED_MVPS: (_make_change_item(),),
                ReleaseNotesSectionKind.KNOWN_GAPS: (_make_change_item(),),
            },
            config=ReleaseNotesConfig(generated_at=_now()),
            reference_time=_now(),
        )
        assert rn.release_notes_state is ReleaseNotesState.BLOCK
        assert "UNSAFE_RELEASE_NOTES_CONTENT" in rn.reason_codes

    def test_has_unsafe_release_notes_content_detects_terms(self) -> None:
        assert has_unsafe_release_notes_content("Place an order now")
        assert has_unsafe_release_notes_content("deploy immediately")
        assert not has_unsafe_release_notes_content("Local research summary.")


# ---------------------------------------------------------------------------
# 8. BLOCK state for unresolved blockers in input artifacts
# ---------------------------------------------------------------------------


class TestUnresolvedBlockers:
    def test_block_for_blocking_reason_codes_in_object(self) -> None:
        artifact = _make_artifact(reason_codes=("MISSING_OBSERVATION_REPORT",))
        rn = build_research_release_notes(
            **_ready_kwargs(),
            input_artifacts={"manifest": artifact},
        )
        assert rn.release_notes_state is ReleaseNotesState.BLOCK
        assert "UNRESOLVED_BLOCKERS" in rn.reason_codes

    def test_block_for_blocking_reason_codes_in_dict(self) -> None:
        artifact = _make_artifact_dict(reason_codes=("STALE_RESEARCH_HANDOFF",))
        rn = build_research_release_notes(
            **_ready_kwargs(),
            input_artifacts={"manifest": artifact},
        )
        assert rn.release_notes_state is ReleaseNotesState.BLOCK
        assert "UNRESOLVED_BLOCKERS" in rn.reason_codes

    def test_block_for_unsafe_safety_flags(self) -> None:
        artifact = _make_artifact(safety_flags=_make_unsafe_safety_flags())
        rn = build_research_release_notes(
            **_ready_kwargs(),
            input_artifacts={"manifest": artifact},
        )
        assert rn.release_notes_state is ReleaseNotesState.BLOCK
        assert "UNSAFE_ARTIFACT_FLAGS" in rn.reason_codes


# ---------------------------------------------------------------------------
# 9. UNKNOWN / fail-closed behavior
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_block_on_unknown_is_fail_closed(self) -> None:
        # Unknown is not exposed as a top-level state by the public engine; an
        # invalid section kind would be rejected earlier. Missing required state
        # always falls back to BLOCK.
        rn = build_research_release_notes(
            config=ReleaseNotesConfig(
                generated_at=_now(),
                required_sections=(ReleaseNotesSectionKind.COMPLETED_MVPS,),
            ),
            reference_time=_now(),
        )
        assert rn.release_notes_state is ReleaseNotesState.BLOCK


# ---------------------------------------------------------------------------
# 10. required_sections customization
# ---------------------------------------------------------------------------


class TestRequiredSectionsCustomization:
    def test_custom_required_sections(self) -> None:
        rn = build_research_release_notes(
            change_items_by_section={
                ReleaseNotesSectionKind.COMPLETED_MVPS: (_make_change_item(),),
            },
            config=ReleaseNotesConfig(
                generated_at=_now(),
                required_sections=(ReleaseNotesSectionKind.COMPLETED_MVPS,),
            ),
            reference_time=_now(),
        )
        assert rn.release_notes_state is ReleaseNotesState.READY
        assert "MISSING_KNOWN_GAPS" not in rn.reason_codes


# ---------------------------------------------------------------------------
# 11. Human review guide advisory-only semantics
# ---------------------------------------------------------------------------


class TestHumanReviewGuide:
    def test_guide_items_are_advisory(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        guide = next(
            s for s in rn.sections
            if s.section_kind is ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE
        )
        assert guide.section_notes
        notes_lower = guide.section_notes.lower()
        assert "advisory" in notes_lower or "suggestion" in notes_lower
        assert "not a gating checklist" in notes_lower

    def test_guide_does_not_authorize_action(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        guide = next(
            s for s in rn.sections
            if s.section_kind is ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE
        )
        for item in guide.change_items:
            assert item.severity != "CRITICAL"


# ---------------------------------------------------------------------------
# 12-13. Summary and data quality public fields
# ---------------------------------------------------------------------------


class TestSummaryAndDataQuality:
    def test_summary_counts(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        assert rn.summary.total_sections >= 6
        assert rn.summary.total_change_items >= 3
        total = (
            rn.summary.critical_count
            + rn.summary.high_count
            + rn.summary.medium_count
            + rn.summary.low_count
            + rn.summary.info_count
        )
        assert total == rn.summary.total_change_items

    def test_data_quality_fields(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        assert 0.0 <= rn.data_quality.completeness_pct <= 100.0
        assert 0.0 <= rn.data_quality.coverage_pct <= 100.0
        assert rn.data_quality.sections_present >= 0
        assert rn.data_quality.total_sections >= rn.data_quality.sections_present


# ---------------------------------------------------------------------------
# 14. Safety flags
# ---------------------------------------------------------------------------


class TestSafetyFlags:
    def test_all_safety_flags(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        flags = rn.safety_flags
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.release_notes_output_is_human_audit_only is True
        assert flags.release_notes_output_not_trading_signal is True
        assert flags.release_notes_output_not_trade_approval is True
        assert flags.release_notes_output_not_execution_readiness is True
        assert flags.release_notes_output_not_strategy_readiness is True
        assert flags.release_notes_output_not_release_approval is True
        assert flags.release_notes_output_not_deployment_approval is True
        assert flags.release_notes_output_not_transaction_permission is True
        assert flags.release_notes_output_not_for_execution is True
        assert flags.release_notes_output_not_for_strategy is True
        assert flags.release_notes_output_not_for_freqtrade is True
        assert flags.release_notes_output_not_for_order is True
        assert flags.release_notes_output_not_for_exchange is True
        assert flags.release_notes_feedback_into_execution is False
        assert flags.cross_layer_feedback_into_execution is False
        assert flags.file_refs_not_traversed is True
        assert flags.artifact_files_not_read is True
        assert flags.no_action_commands_emitted is True


# ---------------------------------------------------------------------------
# 15. Document notes preserve disclaimers
# ---------------------------------------------------------------------------


class TestDocumentNotes:
    def test_disclaimers_present(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        notes = rn.document_notes.lower()
        assert "not release approval" in notes
        assert "not publish approval" in notes or "not deployment approval" in notes
        assert "not trade approval" in notes
        assert "not execution" in notes
        assert "not strategy" in notes
        assert "not transaction permission" in notes

    def test_markdown_safety_notice_disclaimers(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        md = research_release_notes_to_markdown(rn).lower()
        assert "not release approval" in md
        assert "not deployment approval" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "not execution approval" in md
        assert "not strategy approval" in md
        assert "not transaction permission" in md


# ---------------------------------------------------------------------------
# 16. Dict serialization round-trip
# ---------------------------------------------------------------------------


class TestDictSerializationRoundTrip:
    def test_round_trip(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        data = research_release_notes_to_dict(rn)
        assert data["release_notes_id"] == rn.release_notes_id
        assert data["version"] == rn.version
        assert data["kind"] == rn.kind.value
        assert data["release_notes_state"] == rn.release_notes_state.value
        assert data["release_version"] == rn.release_version
        assert data["release_title"] == rn.release_title
        assert "sections" in data
        assert "summary" in data
        assert "data_quality" in data
        assert "safety_flags" in data
        assert "reason_codes" in data
        assert "document_notes" in data
        assert isinstance(data["sections"], list)
        assert data["sections"][0]["section_kind"] == "overview"


# ---------------------------------------------------------------------------
# 17-18. Markdown output
# ---------------------------------------------------------------------------


class TestMarkdownOutput:
    def test_safety_notice_first(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        md = research_release_notes_to_markdown(rn)
        safety_idx = md.lower().find("## safety notice")
        overview_idx = md.lower().find("## overview")
        assert safety_idx >= 0
        assert overview_idx > safety_idx

    def test_contains_sections_and_change_items(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        md = research_release_notes_to_markdown(rn)
        assert "## Summary" in md
        assert "## Data Quality" in md
        assert "### Completed MVPs" in md
        assert "### Known Gaps" in md
        assert "MVP-19" in md or "MVP-18" in md
        assert "SPEC-021" in md

    def test_reference_strings_plain_text(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        md = research_release_notes_to_markdown(rn)
        assert "data/research_archive_manifest/" in md
        assert "data/research_bundle/" in md
        for local_ref, _spec_ref in RELEASE_NOTES_ARTIFACT_INFO.values():
            assert local_ref in md

    def test_markdown_determinism(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        assert research_release_notes_to_markdown(rn) == research_release_notes_to_markdown(rn)


# ---------------------------------------------------------------------------
# 19-21. Dual write and atomic write behavior
# ---------------------------------------------------------------------------


class TestDualWrite:
    def test_write_research_release_notes(self, tmp_path: Path) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        json_path = tmp_path / "rn.json"
        md_path = tmp_path / "rn.md"
        out_json, out_md = write_research_release_notes(
            rn, json_path=json_path, markdown_path=md_path
        )
        assert out_json == json_path
        assert out_md == md_path
        assert json_path.exists()
        assert md_path.exists()
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["release_notes_id"] == rn.release_notes_id

    def test_atomic_json_write(self, tmp_path: Path) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        target = tmp_path / "subdir" / "rn.json"
        atomic_write_json_research_release_notes(rn, target)
        assert target.exists()

    def test_atomic_markdown_write(self, tmp_path: Path) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        target = tmp_path / "subdir" / "rn.md"
        atomic_write_markdown_research_release_notes(rn, target)
        assert target.exists()

    def test_no_production_default_writes(self, tmp_path: Path) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        write_research_release_notes(
            rn,
            json_path=tmp_path / "rn.json",
            markdown_path=tmp_path / "rn.md",
        )
        assert not Path(DEFAULT_RESEARCH_RELEASE_NOTES_JSON_PATH).exists()
        assert not Path(DEFAULT_RESEARCH_RELEASE_NOTES_MARKDOWN_PATH).exists()


# ---------------------------------------------------------------------------
# 22-24. Reference string safety
# ---------------------------------------------------------------------------


class TestReferenceStringSafety:
    def test_reference_strings_remain_strings(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        data = research_release_notes_to_dict(rn)
        appendix = next(
            s for s in data["sections"]
            if s["section_kind"] == "appendix_references"
        )
        for item in appendix["change_items"]:
            for ref in item.get("related_references", []):
                assert isinstance(ref, str)

    def test_no_reference_files_read(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        md = research_release_notes_to_markdown(rn)
        # Reference strings appear as plain text; no file I/O occurred.
        assert "data/research_archive_manifest/" in md
        assert "data/research_bundle/" in md

    def test_no_forbidden_imports(self) -> None:
        package_dir = Path(__file__).parents[2] / "src" / "hunter" / "research_release_notes"
        for source_file in ("models.py", "engine.py", "writer.py"):
            text = (package_dir / source_file).read_text(encoding="utf-8").lower()
            for term in ("freqtrade", "binance"):
                assert f"import {term}" not in text, f"forbidden import {term} in {source_file}"
                assert f"from {term}" not in text, f"forbidden from-import {term} in {source_file}"


# ---------------------------------------------------------------------------
# 25. Fail-closed invalid input
# ---------------------------------------------------------------------------


class TestFailClosedInvalidInput:
    def test_empty_release_notes_blocked(self) -> None:
        rn = build_research_release_notes(
            config=ReleaseNotesConfig(
                generated_at=_now(),
                required_sections=(),
            ),
            reference_time=_now(),
        )
        assert rn.release_notes_state is ReleaseNotesState.BLOCK
        assert "EMPTY_RELEASE_NOTES" in rn.reason_codes


# ---------------------------------------------------------------------------
# 26. Deterministic id and generated_at
# ---------------------------------------------------------------------------


class TestDeterministicIds:
    def test_explicit_generated_at_used(self) -> None:
        t = _now()
        rn = build_research_release_notes(
            reference_time=t,
            change_items_by_section={
                ReleaseNotesSectionKind.COMPLETED_MVPS: (_make_change_item(),),
                ReleaseNotesSectionKind.KNOWN_GAPS: (_make_change_item(),),
            },
        )
        assert rn.generated_at == t
        assert t.strftime("%Y-%m-%dT%H:%M:%S.%f") in rn.release_notes_id

    def test_build_is_repeatable(self) -> None:
        kwargs = _ready_kwargs()
        rn1 = build_research_release_notes(**kwargs)
        rn2 = build_research_release_notes(**kwargs)
        assert rn1.release_notes_id == rn2.release_notes_id
        assert rn1.summary.total_change_items == rn2.summary.total_change_items


# ---------------------------------------------------------------------------
# 27. No mutation of inputs
# ---------------------------------------------------------------------------


class TestNoMutation:
    def test_input_artifacts_not_mutated(self) -> None:
        artifact = _make_artifact("READY")
        original_reason_codes = artifact.reason_codes
        build_research_release_notes(
            **_ready_kwargs(),
            input_artifacts={"manifest": artifact},
        )
        assert artifact.reason_codes is original_reason_codes

    def test_release_notes_frozen(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        with pytest.raises(AttributeError):
            rn.release_version = "mutated"


# ---------------------------------------------------------------------------
# 28-29. Artifact semantics
# ---------------------------------------------------------------------------


class TestArtifactSemantics:
    def test_human_audit_only(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        assert rn.safety_flags.release_notes_output_is_human_audit_only is True

    def test_not_release_or_deployment_approval(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        assert rn.safety_flags.release_notes_output_not_release_approval is True
        assert rn.safety_flags.release_notes_output_not_deployment_approval is True

    def test_not_runtime_registry_or_scheduler(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        # No register/lookup API exists on the release notes object.
        assert not hasattr(rn, "register")
        assert not hasattr(rn, "lookup")
        assert not hasattr(rn, "schedule")


# ---------------------------------------------------------------------------
# 30. No action commands emitted
# ---------------------------------------------------------------------------


class TestNoActionCommands:
    def test_markdown_contains_no_action_commands(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        md = research_release_notes_to_markdown(rn).lower()
        for term in ("deploy now", "execute now", "run now", "start now", "trigger"):
            assert term not in md, f"action command {term!r} found in markdown"

    def test_safety_flag_no_action_commands(self) -> None:
        rn = build_research_release_notes(**_ready_kwargs())
        assert rn.safety_flags.no_action_commands_emitted is True
