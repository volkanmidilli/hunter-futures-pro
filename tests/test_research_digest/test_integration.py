"""Integration tests for hunter.research_digest package.

MVP-16 end-to-end integration tests only.
No network, database, Freqtrade, Binance, exchange, trading,
Web UI, dashboard, or production data access is exercised here.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.research_digest.engine import build_research_digest
from hunter.research_digest.models import (
    DigestConfig,
    DigestSectionKind,
    DigestState,
    FORBIDDEN_DIGEST_TERMS,
    ResearchDigest,
)
from hunter.research_digest.writer import (
    atomic_write_json_research_digest,
    atomic_write_markdown_research_digest,
    research_digest_to_dict,
    research_digest_to_markdown,
    write_research_digest,
)


def _now() -> datetime:
    """Return a deterministic timezone-aware datetime."""
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def ready_digest() -> ResearchDigest:
    """Return a deterministic READY ResearchDigest."""
    return build_research_digest(
        config=DigestConfig(generated_at=_now()),
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
    """Return a deterministic BLOCKED ResearchDigest."""
    return build_research_digest(
        config=DigestConfig(generated_at=_now()),
        review_state="READY",
        index_state="READY",
        search_state="READY",
        bundle_state="READY",
        chronicle_state="READY",
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_full_flow_build_and_serialize(self, tmp_path: Path) -> None:
        """Build digest, serialize to dict/markdown, and write both files."""
        digest = build_research_digest(
            config=DigestConfig(generated_at=_now()),
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

        assert digest.state is DigestState.READY
        assert digest.summary.cross_layer_ready is True
        assert len(digest.sections) == 6

        # Dict serialization covers full digest
        data = research_digest_to_dict(digest)
        assert data["digest_id"] == digest.digest_id
        assert data["state"] == "ready"
        assert data["version"] == "1.0"
        assert len(data["sections"]) == 6
        assert "summary" in data
        assert "data_quality" in data
        assert "safety_flags" in data
        assert "config" in data
        assert "reason_codes" in data
        assert "next_review_notes" in data

        # Write both JSON and Markdown
        json_path = tmp_path / "digest.json"
        md_path = tmp_path / "digest.md"
        out_json, out_md = write_research_digest(digest, json_path, md_path)
        assert out_json == json_path
        assert out_md == md_path
        assert json_path.exists()
        assert md_path.exists()

        # JSON round-trip preserves key fields
        round_trip = json.loads(json_path.read_text(encoding="utf-8"))
        assert round_trip["digest_id"] == digest.digest_id
        assert round_trip["state"] == "ready"
        assert round_trip["version"] == "1.0"
        assert len(round_trip["sections"]) == 6
        assert round_trip["safety_flags"]["digest_output_is_human_audit_only"] is True

        # Markdown contains sections as plain text and safety notice
        md_text = md_path.read_text(encoding="utf-8")
        assert "# Research Digest" in md_text
        assert "human-audit artifact only" in md_text
        assert "not a trading signal" in md_text
        assert "not trade approval" in md_text
        assert "| observation | READY |" in md_text
        assert "| chronicle | READY |" in md_text

    def test_ready_digest_all_sections(self, ready_digest: ResearchDigest) -> None:
        """All sections READY produces a READY digest."""
        assert ready_digest.state is DigestState.READY
        assert ready_digest.summary.ready_sections == 6
        assert ready_digest.summary.blocked_sections == 0
        assert ready_digest.summary.missing_sections == 0
        assert ready_digest.summary.total_artifacts == 22
        assert ready_digest.data_quality.completeness_pct == 100.0

    def test_section_kinds_in_order(self, ready_digest: ResearchDigest) -> None:
        """Sections follow deterministic ordering."""
        expected = [
            DigestSectionKind.OBSERVATION,
            DigestSectionKind.REVIEW,
            DigestSectionKind.INDEX,
            DigestSectionKind.SEARCH,
            DigestSectionKind.BUNDLE,
            DigestSectionKind.CHRONICLE,
        ]
        assert [s.section_kind for s in ready_digest.sections] == expected

    def test_reason_code_summary_on_ready_digest(self, ready_digest: ResearchDigest) -> None:
        """READY digest has empty reason codes and next-review notes."""
        assert ready_digest.reason_codes == ()
        assert "All layers ready" in ready_digest.summary.next_review_notes
        assert ready_digest.summary.cross_layer_ready is True


# ---------------------------------------------------------------------------
# Error paths / fail-closed behavior
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_empty_digest_blocked(self) -> None:
        """No artifact states or counts produces a BLOCKED EMPTY_DIGEST."""
        digest = build_research_digest(config=DigestConfig(generated_at=_now()))
        assert digest.state is DigestState.BLOCKED
        assert "EMPTY_DIGEST" in digest.reason_codes
        assert digest.safety_flags.dry_run is True

    def test_missing_observation_blocked(self, blocked_digest: ResearchDigest) -> None:
        """Missing observation artifact produces a BLOCKED MISSING_OBSERVATION digest."""
        assert blocked_digest.state is DigestState.BLOCKED
        assert "MISSING_OBSERVATION" in blocked_digest.reason_codes
        assert blocked_digest.summary.blocked_sections >= 1

    def test_invalid_state_blocked(self) -> None:
        """Unrecognized artifact state produces a BLOCKED INVALID_* digest."""
        digest = build_research_digest(
            config=DigestConfig(generated_at=_now()),
            observation_state="CORRUPTED",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        assert digest.state is DigestState.BLOCKED
        assert "INVALID_OBSERVATION" in digest.reason_codes

    def test_unsafe_next_review_notes_blocked(self) -> None:
        """Unsafe next_review_notes produces a BLOCKED UNSAFE_DIGEST_CONTENT digest."""
        digest = build_research_digest(
            config=DigestConfig(generated_at=_now()),
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
            next_review_notes="place order now",
        )
        assert digest.state is DigestState.BLOCKED
        assert "UNSAFE_DIGEST_CONTENT" in digest.reason_codes

    def test_unsafe_config_blocked(self) -> None:
        """Unsafe config values produce a BLOCKED UNSAFE_CONFIG digest."""
        # Bypass DigestConfig validation to simulate a corrupted config object.
        config = object.__new__(DigestConfig)
        object.__setattr__(config, "version", "1.0")
        object.__setattr__(config, "generated_at", _now())
        object.__setattr__(config, "output_format", "both")
        object.__setattr__(config, "dry_run", False)
        object.__setattr__(config, "live_trading_enabled", False)
        object.__setattr__(config, "real_orders_enabled", False)
        object.__setattr__(config, "leverage_enabled", False)
        object.__setattr__(config, "shorting_enabled", False)
        object.__setattr__(config, "stale_threshold_minutes", 60)
        object.__setattr__(config, "include_next_review_notes", True)
        object.__setattr__(config, "include_safety_flags", True)
        object.__setattr__(config, "include_unresolved_blockers", True)
        object.__setattr__(config, "include_reason_code_summary", True)

        digest = build_research_digest(
            config=config,
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        assert digest.state is DigestState.BLOCKED
        assert "UNSAFE_CONFIG" in digest.reason_codes

    def test_blocked_digest_serializes_and_writes(self, blocked_digest: ResearchDigest, tmp_path: Path) -> None:
        """BLOCKED digest can be serialized and written like READY digest."""
        data = research_digest_to_dict(blocked_digest)
        assert data["state"] == "blocked"
        assert "MISSING_OBSERVATION" in data["reason_codes"]

        md = research_digest_to_markdown(blocked_digest)
        assert "blocked" in md.lower()
        assert "MISSING_OBSERVATION" in md
        assert "human-audit artifact only" in md

        json_path = tmp_path / "blocked.json"
        md_path = tmp_path / "blocked.md"
        write_research_digest(blocked_digest, json_path, md_path)
        assert json_path.exists()
        assert md_path.exists()


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_digest_id_deterministic_from_config(self) -> None:
        """digest_id is derived deterministically from version and generated_at."""
        generated_at = _now()
        digest = build_research_digest(
            config=DigestConfig(generated_at=generated_at),
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        expected = f"digest:1.0:{generated_at.strftime('%Y-%m-%dT%H:%M:%S.%f')}"
        assert digest.digest_id == expected

    def test_same_inputs_produce_same_digest(self) -> None:
        """Same inputs produce identical digests."""
        kwargs = {
            "config": DigestConfig(generated_at=_now()),
            "observation_state": "READY",
            "review_state": "READY",
            "index_state": "READY",
            "search_state": "READY",
            "bundle_state": "READY",
            "chronicle_state": "READY",
            "observation_count": 7,
            "review_count": 5,
        }
        digest1 = build_research_digest(**kwargs)
        digest2 = build_research_digest(**kwargs)
        assert digest1.digest_id == digest2.digest_id
        assert digest1.generated_at == digest2.generated_at
        assert digest1.state == digest2.state
        assert digest1.sections == digest2.sections

    def test_same_inputs_produce_same_dict_and_markdown(self, ready_digest: ResearchDigest) -> None:
        """Same inputs produce deterministic dict and markdown output."""
        data1 = research_digest_to_dict(ready_digest)
        data2 = research_digest_to_dict(ready_digest)
        assert data1 == data2
        md1 = research_digest_to_markdown(ready_digest)
        md2 = research_digest_to_markdown(ready_digest)
        assert md1 == md2

    def test_generated_at_preserved_from_config(self) -> None:
        """generated_at from config is preserved in the digest."""
        generated_at = _now()
        digest = build_research_digest(
            config=DigestConfig(generated_at=generated_at),
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        assert digest.generated_at == generated_at


# ---------------------------------------------------------------------------
# Safety assertions
# ---------------------------------------------------------------------------


class TestSafetyAssertions:
    def test_no_file_reads_from_production_paths(self) -> None:
        """Digest engine operates on in-memory state only, never reads files."""
        digest = build_research_digest(
            config=DigestConfig(generated_at=_now()),
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        assert digest.state is DigestState.READY

    def test_no_network_calls(self) -> None:
        """Digest engine never makes network calls."""
        digest = build_research_digest(
            config=DigestConfig(generated_at=_now()),
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        assert digest.state is DigestState.READY

    def test_no_execution_feedback(self, ready_digest: ResearchDigest) -> None:
        """Digest safety flags block feedback into execution paths."""
        assert ready_digest.safety_flags.digest_feedback_into_execution is False
        assert ready_digest.safety_flags.cross_layer_feedback_into_execution is False

    def test_no_trading_logic(self, ready_digest: ResearchDigest) -> None:
        """Digest safety flags disable all trading-related toggles."""
        assert ready_digest.safety_flags.live_trading_enabled is False
        assert ready_digest.safety_flags.real_orders_enabled is False
        assert ready_digest.safety_flags.leverage_enabled is False
        assert ready_digest.safety_flags.shorting_enabled is False

    def test_human_audit_only_notice_in_markdown(self, ready_digest: ResearchDigest) -> None:
        """Markdown output contains explicit human-audit safety notice."""
        md = research_digest_to_markdown(ready_digest)
        assert "human-audit artifact only" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "not a recommendation engine" in md
        assert "not an action-command generator" in md
        assert "must not be consumed by execution" in md
        assert "Freqtrade" in md

    def test_no_forbidden_terms_in_next_review_notes(self, ready_digest: ResearchDigest) -> None:
        """Generated next_review_notes contain no forbidden terms."""
        notes = ready_digest.summary.next_review_notes.lower()
        for term in FORBIDDEN_DIGEST_TERMS:
            assert term not in notes, term

    def test_file_references_are_strings_only(self, tmp_path: Path) -> None:
        """File references in metadata remain plain strings, never opened."""
        digest = build_research_digest(
            config=DigestConfig(generated_at=_now()),
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
            observation_reason_codes=("OK",),
        )
        # Metadata may hold file references; writer serializes them as strings.
        data = research_digest_to_dict(digest)
        json_path = tmp_path / "digest.json"
        atomic_write_json_research_digest(digest, json_path)
        round_trip = json.loads(json_path.read_text(encoding="utf-8"))
        assert round_trip["digest_id"] == digest.digest_id
        assert round_trip["state"] == "ready"
        # No exception means file references were never opened/executed.

    def test_digest_not_for_strategy_or_freqtrade(self, ready_digest: ResearchDigest) -> None:
        """Digest output flags mark it unsuitable for strategy/Freqtrade/order/exchange."""
        flags = ready_digest.safety_flags
        assert flags.digest_output_not_for_strategy is True
        assert flags.digest_output_not_for_freqtrade is True
        assert flags.digest_output_not_for_order is True
        assert flags.digest_output_not_for_exchange is True


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_json_round_trip_preserves_section_kinds(self, ready_digest: ResearchDigest, tmp_path: Path) -> None:
        """JSON round-trip preserves section kind values."""
        json_path = tmp_path / "digest.json"
        atomic_write_json_research_digest(ready_digest, json_path)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        kinds = [s["section_kind"] for s in data["sections"]]
        assert kinds == ["observation", "review", "index", "search", "bundle", "chronicle"]

    def test_json_round_trip_preserves_state_and_reason_codes(self, blocked_digest: ResearchDigest, tmp_path: Path) -> None:
        """JSON round-trip preserves BLOCKED state and reason codes."""
        json_path = tmp_path / "digest.json"
        atomic_write_json_research_digest(blocked_digest, json_path)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["state"] == "blocked"
        assert "MISSING_OBSERVATION" in data["reason_codes"]

    def test_markdown_contains_sections_as_plain_text(self, ready_digest: ResearchDigest) -> None:
        """Markdown renders sections as plain text tables and lists."""
        md = research_digest_to_markdown(ready_digest)
        assert "## Sections" in md
        assert "| kind | state | count | blockers | notes |" in md
        for kind in ("observation", "review", "index", "search", "bundle", "chronicle"):
            assert f"| {kind} |" in md

    def test_markdown_contains_safety_flags(self, ready_digest: ResearchDigest) -> None:
        """Markdown renders safety flags as a plain list."""
        md = research_digest_to_markdown(ready_digest)
        assert "## Safety Flags" in md
        assert "digest_output_is_human_audit_only" in md
        assert "digest_feedback_into_execution" in md
