"""Tests for hunter.research_digest.writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.research_digest.engine import build_research_digest
from hunter.research_digest.models import (
    DigestConfig,
    DigestDataQuality,
    DigestSafetyFlags,
    DigestSection,
    DigestSectionKind,
    DigestState,
    DigestSummary,
    ResearchDigest,
)
from hunter.research_digest.writer import (
    DEFAULT_DIGEST_JSON_PATH,
    DEFAULT_DIGEST_MARKDOWN_PATH,
    atomic_write_json_research_digest,
    atomic_write_markdown_research_digest,
    digest_config_to_dict,
    digest_data_quality_to_dict,
    digest_safety_flags_to_dict,
    digest_section_to_dict,
    digest_summary_to_dict,
    research_digest_to_dict,
    research_digest_to_markdown,
    write_research_digest,
)


@pytest.fixture
def sample_digest() -> ResearchDigest:
    """Return a deterministic sample ResearchDigest."""
    generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return build_research_digest(
        config=DigestConfig(generated_at=generated_at),
        observation_state="READY",
        review_state="READY",
        index_state="READY",
        search_state="READY",
        bundle_state="READY",
        chronicle_state="READY",
        observation_count=10,
        review_count=5,
        index_count=3,
        search_count=2,
        bundle_count=1,
        chronicle_count=1,
    )


@pytest.fixture
def blocked_digest() -> ResearchDigest:
    """Return a deterministic blocked ResearchDigest."""
    generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return ResearchDigest.blocked("MISSING_OBSERVATION", generated_at=generated_at)


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


class TestDigestSafetyFlagsToDict:
    def test_all_fields_present(self) -> None:
        flags = DigestSafetyFlags()
        data = digest_safety_flags_to_dict(flags)
        assert data["dry_run"] is True
        assert data["live_trading_enabled"] is False
        assert data["digest_feedback_into_execution"] is False
        assert data["cross_layer_feedback_into_execution"] is False
        assert data["digest_output_is_human_audit_only"] is True
        assert data["file_refs_not_traversed"] is True

    def test_unsafe_flag_serialized(self) -> None:
        # Construct via object.__new__ to bypass __post_init__ for serialization test.
        flags = object.__new__(DigestSafetyFlags)
        object.__setattr__(flags, "dry_run", True)
        object.__setattr__(flags, "live_trading_enabled", True)
        object.__setattr__(flags, "real_orders_enabled", False)
        object.__setattr__(flags, "leverage_enabled", False)
        object.__setattr__(flags, "shorting_enabled", False)
        object.__setattr__(flags, "digest_output_is_human_audit_only", True)
        object.__setattr__(flags, "digest_output_not_trading_signal", True)
        object.__setattr__(flags, "digest_output_not_trade_approval", True)
        object.__setattr__(flags, "digest_output_not_for_execution", True)
        object.__setattr__(flags, "digest_output_not_for_strategy", True)
        object.__setattr__(flags, "digest_output_not_for_freqtrade", True)
        object.__setattr__(flags, "digest_output_not_for_order", True)
        object.__setattr__(flags, "digest_output_not_for_exchange", True)
        object.__setattr__(flags, "digest_feedback_into_execution", True)
        object.__setattr__(flags, "cross_layer_feedback_into_execution", False)
        object.__setattr__(flags, "trace_linkage_advisory_only", True)
        object.__setattr__(flags, "file_refs_not_traversed", True)
        data = digest_safety_flags_to_dict(flags)
        assert data["live_trading_enabled"] is True
        assert data["digest_feedback_into_execution"] is True


class TestDigestConfigToDict:
    def test_all_fields_present(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        config = DigestConfig(generated_at=generated_at)
        data = digest_config_to_dict(config)
        assert data["version"] == "1.0"
        assert data["generated_at"] == "2025-01-01T12:00:00+00:00"
        assert data["output_format"] == "both"
        assert data["dry_run"] is True
        assert data["stale_threshold_minutes"] == 60

    def test_none_generated_at(self) -> None:
        config = DigestConfig(generated_at=None)
        data = digest_config_to_dict(config)
        assert data["generated_at"] is None


class TestDigestSectionToDict:
    def test_basic_section(self) -> None:
        section = DigestSection(
            section_kind=DigestSectionKind.OBSERVATION,
            state="READY",
            count=5,
        )
        data = digest_section_to_dict(section)
        assert data["section_kind"] == "observation"
        assert data["state"] == "READY"
        assert data["count"] == 5
        assert data["reason_codes"] == []
        assert data["metadata"] == {}

    def test_section_with_metadata(self) -> None:
        section = DigestSection(
            section_kind=DigestSectionKind.BUNDLE,
            state="BLOCKED",
            reason_codes=("MISSING_BUNDLE",),
            metadata={"path": "/tmp/bundle.json"},
        )
        data = digest_section_to_dict(section)
        assert data["reason_codes"] == ["MISSING_BUNDLE"]
        assert data["metadata"] == {"path": "/tmp/bundle.json"}


class TestDigestSummaryToDict:
    def test_basic_summary(self) -> None:
        summary = DigestSummary(
            total_sections=6,
            ready_sections=4,
            blocked_sections=2,
            total_artifacts=42,
            reason_code_counts={"MISSING_REVIEW": 1},
        )
        data = digest_summary_to_dict(summary)
        assert data["total_sections"] == 6
        assert data["ready_sections"] == 4
        assert data["total_artifacts"] == 42
        assert data["reason_code_counts"] == {"MISSING_REVIEW": 1}


class TestDigestDataQualityToDict:
    def test_basic_data_quality(self) -> None:
        dq = DigestDataQuality(
            completeness_pct=75.0,
            missing_count=1,
            stale_count=1,
            total_sections=4,
        )
        data = digest_data_quality_to_dict(dq)
        assert data["completeness_pct"] == 75.0
        assert data["missing_count"] == 1
        assert data["total_sections"] == 4


class TestResearchDigestToDict:
    def test_all_top_level_fields(self, sample_digest: ResearchDigest) -> None:
        data = research_digest_to_dict(sample_digest)
        assert data["digest_id"].startswith("digest:1.0:")
        assert data["version"] == "1.0"
        assert data["state"] == "ready"
        assert len(data["sections"]) == 6
        assert "summary" in data
        assert "data_quality" in data
        assert "safety_flags" in data
        assert "config" in data
        assert "reason_codes" in data
        assert "next_review_notes" in data

    def test_deterministic_json(self, sample_digest: ResearchDigest) -> None:
        data1 = research_digest_to_dict(sample_digest)
        data2 = research_digest_to_dict(sample_digest)
        assert json.dumps(data1, sort_keys=True) == json.dumps(data2, sort_keys=True)

    def test_blocked_digest(self, blocked_digest: ResearchDigest) -> None:
        data = research_digest_to_dict(blocked_digest)
        assert data["state"] == "blocked"
        assert data["reason_codes"] == ["MISSING_OBSERVATION"]
        assert data["sections"] == []

    def test_safety_flags_included(self, sample_digest: ResearchDigest) -> None:
        data = research_digest_to_dict(sample_digest)
        flags = data["safety_flags"]
        assert flags["digest_feedback_into_execution"] is False
        assert flags["digest_output_is_human_audit_only"] is True


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


class TestResearchDigestToMarkdown:
    def test_contains_safety_notice(self, sample_digest: ResearchDigest) -> None:
        markdown = research_digest_to_markdown(sample_digest)
        assert "human-audit artifact only" in markdown
        assert "not a trading signal" in markdown
        assert "not trade approval" in markdown
        assert "not a recommendation engine" in markdown
        assert "not an action-command generator" in markdown
        assert "not be consumed by execution" in markdown
        assert "not traversed, opened, followed, validated, or executed" in markdown

    def test_contains_digest_info(self, sample_digest: ResearchDigest) -> None:
        markdown = research_digest_to_markdown(sample_digest)
        assert "# Research Digest" in markdown
        assert "digest_id" in markdown
        assert "generated_at" in markdown
        assert "state" in markdown

    def test_contains_sections_table(self, sample_digest: ResearchDigest) -> None:
        markdown = research_digest_to_markdown(sample_digest)
        assert "## Sections" in markdown
        assert "| observation | READY |" in markdown
        assert "| chronicle | READY |" in markdown

    def test_contains_summary(self, sample_digest: ResearchDigest) -> None:
        markdown = research_digest_to_markdown(sample_digest)
        assert "## Summary" in markdown
        assert "cross_layer_ready" in markdown

    def test_contains_data_quality(self, sample_digest: ResearchDigest) -> None:
        markdown = research_digest_to_markdown(sample_digest)
        assert "## Data Quality" in markdown
        assert "completeness_pct" in markdown

    def test_contains_safety_flags(self, sample_digest: ResearchDigest) -> None:
        markdown = research_digest_to_markdown(sample_digest)
        assert "## Safety Flags" in markdown
        assert "digest_feedback_into_execution" in markdown

    def test_contains_next_review_notes(self, sample_digest: ResearchDigest) -> None:
        markdown = research_digest_to_markdown(sample_digest)
        assert "## Next Review Notes" in markdown
        assert "All layers ready" in markdown

    def test_blocked_digest_markdown(self, blocked_digest: ResearchDigest) -> None:
        markdown = research_digest_to_markdown(blocked_digest)
        assert "- **state**: blocked" in markdown
        assert "MISSING_OBSERVATION" in markdown


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


class TestAtomicWriteJsonResearchDigest:
    def test_writes_json(self, sample_digest: ResearchDigest, tmp_path: Path) -> None:
        target = tmp_path / "digest.json"
        path = atomic_write_json_research_digest(sample_digest, target)
        assert path == target
        assert target.exists()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["state"] == "ready"
        assert data["version"] == "1.0"

    def test_default_path(self, sample_digest: ResearchDigest, tmp_path: Path) -> None:
        # Override cwd so default path resolves under tmp_path.
        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            path = atomic_write_json_research_digest(sample_digest)
            assert path == DEFAULT_DIGEST_JSON_PATH
            assert DEFAULT_DIGEST_JSON_PATH.exists()
        finally:
            os.chdir(original_cwd)


class TestAtomicWriteMarkdownResearchDigest:
    def test_writes_markdown(self, sample_digest: ResearchDigest, tmp_path: Path) -> None:
        target = tmp_path / "digest.md"
        path = atomic_write_markdown_research_digest(sample_digest, target)
        assert path == target
        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "# Research Digest" in content

    def test_default_path(self, sample_digest: ResearchDigest, tmp_path: Path) -> None:
        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            path = atomic_write_markdown_research_digest(sample_digest)
            assert path == DEFAULT_DIGEST_MARKDOWN_PATH
            assert DEFAULT_DIGEST_MARKDOWN_PATH.exists()
        finally:
            os.chdir(original_cwd)


class TestWriteResearchDigest:
    def test_writes_both(self, sample_digest: ResearchDigest, tmp_path: Path) -> None:
        json_path = tmp_path / "digest.json"
        md_path = tmp_path / "digest.md"
        out_json, out_md = write_research_digest(sample_digest, json_path, md_path)
        assert out_json == json_path
        assert out_md == md_path
        assert json_path.exists()
        assert md_path.exists()


# ---------------------------------------------------------------------------
# Determinism and safety
# ---------------------------------------------------------------------------


class TestDeterminismAndSafety:
    def test_json_sorted_keys(self, sample_digest: ResearchDigest, tmp_path: Path) -> None:
        target = tmp_path / "digest.json"
        atomic_write_json_research_digest(sample_digest, target)
        text = target.read_text(encoding="utf-8")
        data = json.loads(text)
        # Top-level keys must be sorted alphabetically.
        assert list(data.keys()) == sorted(data.keys())
        # Nested dicts also sorted.
        assert list(data["safety_flags"].keys()) == sorted(data["safety_flags"].keys())

    def test_no_forbidden_terms_in_next_review_notes(self, sample_digest: ResearchDigest) -> None:
        markdown = research_digest_to_markdown(sample_digest)
        # Extract the Next Review Notes section only; the safety notice may
        # legitimately contain words like "order" in a safety context.
        notes_start = markdown.find("## Next Review Notes")
        assert notes_start != -1
        notes_section = markdown[notes_start:].lower()
        for term in ("api_key", "secret", "enter_long", "live_trade"):
            assert term not in notes_section

    def test_metadata_strings_not_traversed(self, sample_digest: ResearchDigest, tmp_path: Path) -> None:
        # Add a section with a file-path string in metadata.
        section = DigestSection(
            section_kind=DigestSectionKind.OBSERVATION,
            state="READY",
            metadata={"path": "/tmp/external.json"},
        )
        digest = ResearchDigest(
            digest_id="d1",
            generated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            state=DigestState.READY,
            sections=(section,),
        )
        target = tmp_path / "digest.json"
        atomic_write_json_research_digest(digest, target)
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["sections"][0]["metadata"]["path"] == "/tmp/external.json"
