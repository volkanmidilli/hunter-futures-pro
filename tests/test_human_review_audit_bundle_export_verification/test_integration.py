"""Integration tests for MVP-45: MVP-40→MVP-41→MVP-42→MVP-43→MVP-44→MVP-45 end-to-end.

All MVP-44 export writes go into pytest tmp_path only. MVP-45 verification
receives caller-provided manifest objects and artifact bytes; it never reads
filesystem paths. No network, server, daemon, trading, or Freqtrade runtime
behavior is exercised.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from hunter.human_review_audit_bundle import (
    HumanReviewAuditBundleConfig,
    HumanReviewAuditBundleInput,
    HumanReviewAuditBundleState,
    build_human_review_audit_bundle,
)
from hunter.human_review_audit_bundle_export import (
    HumanReviewAuditBundleExportConfig,
    HumanReviewAuditBundleExportInput,
    HumanReviewAuditBundleExportReasonCode,
    HumanReviewAuditBundleExportState,
    export_human_review_audit_bundle_artifact,
)
from hunter.human_review_audit_bundle_export_verification import (
    HumanReviewAuditBundleExportVerificationConfig,
    HumanReviewAuditBundleExportVerificationInput,
    HumanReviewAuditBundleExportVerificationReasonCode,
    HumanReviewAuditBundleExportVerificationState,
    verify_human_review_audit_bundle_export,
    verification_report_to_dict,
    verification_report_to_json,
    verification_report_to_markdown,
)
from hunter.human_review_audit_bundle_export_verification.engine import (
    _scan_forbidden_terms,
)
from hunter.human_review_decision_log import (
    HumanReviewDecisionLogConfig,
    HumanReviewDecisionLogInput,
    HumanReviewDecisionOutcome,
    HumanReviewDecisionRecord,
    HumanReviewQueueEntryRef,
    build_human_review_decision_log_report,
)
from hunter.human_review_decision_log_consistency import (
    HumanReviewDecisionLogConsistencyConfig,
    HumanReviewDecisionLogConsistencyInput,
    build_human_review_decision_log_consistency_report,
)
from hunter.human_review_queue import (
    HumanReviewQueueConfig,
    HumanReviewQueueDataQuality,
    HumanReviewQueueEntry,
    HumanReviewQueueInput,
    HumanReviewQueueReasonCode,
    HumanReviewQueueReport,
    HumanReviewQueueSafetyFlags,
    HumanReviewQueueState,
    HumanReviewSourceRecord,
    build_human_review_queue_report,
)

NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Upstream report builders (mirror MVP-44 integration test pattern)
# ---------------------------------------------------------------------------

_QID = "int-qid-1"


def _build_ok_queue_report(now: datetime) -> HumanReviewQueueReport:
    entry = HumanReviewQueueEntry(
        queue_entry_id=_QID,
        source_id="int-src-ok",
        source_kind="issue",
        record_id="int-rec-ok",
        entry_state="not_applicable",
        priority="info",
        decision_hint="not_applicable_for_audit",
        severity="info",
        reason_codes=("not_applicable",),
        title="Integration test queue entry",
        description="Queue entry for MVP-45 integration test.",
        generated_at=now,
    )
    return HumanReviewQueueReport(
        report_id="int-queue-ok",
        generated_at=now,
        state=HumanReviewQueueState.OK,
        project_version="0.40.0-dev",
        queue_entries=(entry,),
        safety_flags=HumanReviewQueueSafetyFlags(),
        data_quality=HumanReviewQueueDataQuality(
            total_source_records=1,
            total_queue_entries=1,
            info_count=1,
            info_priority_count=1,
            sections_present=1,
        ),
        reason_codes=(HumanReviewQueueReasonCode.OK,),
    )


def _build_degraded_queue_input(now: datetime) -> HumanReviewQueueInput:
    record = HumanReviewSourceRecord(
        source_id="int-src-degraded",
        source_kind="issue",
        record_id="int-rec-degraded",
        title="Degraded integration item",
        description="Item with advisory orphan reference.",
        state="open",
        severity="advisory",
        reason_codes=("orphan_related_record", "advisory_severity"),
        related_record_ids=("int-missing-id",),
        artifact_ref="artifact://int-degraded",
        report_ref="report://int-degraded",
        generated_at=now,
    )
    return HumanReviewQueueInput(
        source_records=(record,),
        config=HumanReviewQueueConfig(),
        generated_at=now,
    )


def _build_blocked_queue_input(now: datetime) -> HumanReviewQueueInput:
    record = HumanReviewSourceRecord(
        source_id="int-src-blocked",
        source_kind="issue",
        record_id="int-rec-blocked",
        title="Integration blocking item",
        description="Blocking severity item for integration test.",
        state="blocked",
        severity="blocking",
        reason_codes=("blocking_severity",),
        artifact_ref="artifact://int-blocked",
        report_ref="report://int-blocked",
        generated_at=now,
    )
    return HumanReviewQueueInput(
        source_records=(record,),
        config=HumanReviewQueueConfig(),
        generated_at=now,
    )


def _build_decision_log_input(
    queue_report: HumanReviewQueueReport,
    now: datetime,
    queue_entry_id: str | None = None,
) -> HumanReviewDecisionLogInput:
    queue_entry = queue_report.queue_entries[0] if queue_report.queue_entries else None
    qid = queue_entry_id if queue_entry_id is not None else (queue_entry.queue_entry_id if queue_entry else _QID)
    entry_state = queue_entry.entry_state if queue_entry else "queued"
    severity = queue_entry.severity if queue_entry else "info"
    priority = queue_entry.priority if queue_entry else "info"
    source_id = queue_entry.source_id if queue_entry else "int-src-1"
    source_kind = queue_entry.source_kind if queue_entry else "issue"
    record_id = queue_entry.record_id if queue_entry else "int-rec-1"
    entry_reason_codes = queue_entry.reason_codes if queue_entry else ("info_severity",)
    outcome = (
        HumanReviewDecisionOutcome.NOT_APPLICABLE.value
        if entry_state.strip().lower() == "not_applicable"
        else HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value
    )
    ref = HumanReviewQueueEntryRef(
        queue_entry_id=qid,
        source_id=source_id,
        source_kind=source_kind,
        record_id=record_id,
        entry_state=entry_state,
        priority=priority,
        severity=severity,
        reason_codes=entry_reason_codes,
        artifact_ref="artifact://int-decision-ref",
        report_ref="report://int-decision-ref",
        generated_at=now,
    )
    decision = HumanReviewDecisionRecord(
        decision_id="int-decision-ok",
        queue_entry_id=qid,
        reviewer="int-reviewer-1",
        decided_at=now,
        outcome=outcome,
        rationale="Accepted for audit log only."
        if outcome == HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value
        else "Not applicable for audit log.",
        reason_codes=entry_reason_codes,
        artifact_ref="artifact://int-decision",
        report_ref="report://int-decision",
        generated_at=now,
    )
    return HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        decision_records=(decision,),
        config=HumanReviewDecisionLogConfig(),
        generated_at=now,
    )


def _build_consistency_input(
    queue_report: HumanReviewQueueReport,
    decision_log_report: Any,
    now: datetime,
) -> HumanReviewDecisionLogConsistencyInput:
    return HumanReviewDecisionLogConsistencyInput(
        queue_report=queue_report,
        decision_log_report=decision_log_report,
        config=HumanReviewDecisionLogConsistencyConfig(),
        generated_at=now,
    )


def _build_bundle_input(
    queue_report: HumanReviewQueueReport,
    decision_log_report: Any,
    consistency_report: Any,
    now: datetime,
) -> HumanReviewAuditBundleInput:
    return HumanReviewAuditBundleInput(
        queue_report=queue_report,
        decision_log_report=decision_log_report,
        consistency_report=consistency_report,
        config=HumanReviewAuditBundleConfig(),
        generated_at=now,
    )


def _build_ok_bundle_report(now: datetime) -> Any:
    queue_report = _build_ok_queue_report(now)
    decision_log_report = build_human_review_decision_log_report(
        _build_decision_log_input(queue_report, now)
    )
    consistency_report = build_human_review_decision_log_consistency_report(
        _build_consistency_input(queue_report, decision_log_report, now)
    )
    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    return build_human_review_audit_bundle(bundle_input)


def _build_degraded_bundle_report(now: datetime) -> Any:
    queue_report = build_human_review_queue_report(_build_degraded_queue_input(now))
    decision_log_report = build_human_review_decision_log_report(
        _build_decision_log_input(queue_report, now)
    )
    consistency_report = build_human_review_decision_log_consistency_report(
        _build_consistency_input(queue_report, decision_log_report, now)
    )
    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    return build_human_review_audit_bundle(bundle_input)


def _build_blocked_bundle_report(now: datetime) -> Any:
    queue_report = build_human_review_queue_report(_build_blocked_queue_input(now))
    qid = queue_report.queue_entries[0].queue_entry_id
    decision_log_report = build_human_review_decision_log_report(
        _build_decision_log_input(queue_report, now, queue_entry_id=qid)
    )
    consistency_report = build_human_review_decision_log_consistency_report(
        _build_consistency_input(queue_report, decision_log_report, now)
    )
    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    return build_human_review_audit_bundle(bundle_input)


def _build_not_applicable_bundle_report(now: datetime) -> Any:
    queue_input = HumanReviewQueueInput(source_records=(), generated_at=now)
    queue_report = build_human_review_queue_report(queue_input)
    decision_log_input = HumanReviewDecisionLogInput(generated_at=now)
    decision_log_report = build_human_review_decision_log_report(decision_log_input)
    consistency_report = build_human_review_decision_log_consistency_report(
        _build_consistency_input(queue_report, decision_log_report, now)
    )
    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    return build_human_review_audit_bundle(bundle_input)


# ---------------------------------------------------------------------------
# Export helper (writes to pytest tmp_path only)
# ---------------------------------------------------------------------------


def _export_artifact(
    bundle_report: Any,
    tmp_path: Path,
    *,
    format: str = "json",
    dry_run: bool = False,
    overwrite: bool = False,
    verify_hash: bool = True,
    strict: bool = False,
) -> Any:
    """Run MVP-44 export into tmp_path; return the manifest."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    export_input = HumanReviewAuditBundleExportInput(
        bundle_report=bundle_report,
        output_dir=output_dir,
        tmp_path=tmp_dir,
        config=HumanReviewAuditBundleExportConfig(
            format=format,
            dry_run=dry_run,
            overwrite=overwrite,
            verify_hash=verify_hash,
            strict=strict,
        ),
    )
    return export_human_review_audit_bundle_artifact(export_input)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestFullChainVerified:
    """Full MVP-40→45 end-to-end: OK/WRITTEN upstream → VERIFIED verification."""

    def test_written_matching_bytes_verifies(self, tmp_path: Path) -> None:
        """End-to-end verification of a WRITTEN manifest with matching bytes."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        assert manifest.state == HumanReviewAuditBundleExportState.WRITTEN

        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.VERIFIED
        assert HumanReviewAuditBundleExportVerificationReasonCode.OK in report.reason_codes
        assert report.safety_flags.hash_verified is True
        assert report.safety_flags.length_verified is True
        assert report.safety_flags.state_verifiable is True

    def test_verification_deterministic(self, tmp_path: Path) -> None:
        """Repeated verification of same bytes/manifest yields identical results."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()

        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report1 = verify_human_review_audit_bundle_export(inp)
        report2 = verify_human_review_audit_bundle_export(inp)
        assert report1.verification_id == report2.verification_id
        assert report1.report_id == report2.report_id
        assert report1.state == report2.state
        assert report1.data_quality == report2.data_quality
        assert report1.safety_flags == report2.safety_flags
        assert report1.reason_codes == report2.reason_codes
        assert report1.issues == report2.issues

    def test_writer_outputs_deterministic(self, tmp_path: Path) -> None:
        """Repeated verification + writer produces identical outputs."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()

        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)

        d1 = verification_report_to_dict(report)
        d2 = verification_report_to_dict(report)
        assert d1 == d2

        j = verification_report_to_json(report)
        md = verification_report_to_markdown(report)
        # Cross-assert: verification_id present in all outputs
        assert report.verification_id in j
        assert report.verification_id in md

    def test_manifest_hash_verified_false_still_verifies_independently(
        self, tmp_path: Path
    ) -> None:
        """When manifest.safety_flags.hash_verified is False, engine still
        recomputes hash independently and succeeds for matching bytes."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path, verify_hash=False)
        assert not manifest.safety_flags.hash_verified

        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.VERIFIED
        # Engine independently verified the hash
        assert report.safety_flags.hash_verified is True


class TestHashAndLengthMismatch:
    """Hash/length mismatch paths using real exported artifact bytes."""

    def test_hash_mismatch_fails_closed(self, tmp_path: Path) -> None:
        """Tampered bytes produce BLOCKED with HASH_MISMATCH."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()

        corrupted = bytearray(artifact_bytes)
        corrupted[-1] ^= 0xFF
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=bytes(corrupted),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
        assert HumanReviewAuditBundleExportVerificationReasonCode.HASH_MISMATCH in report.reason_codes
        assert report.safety_flags.hash_verified is False

    def test_length_mismatch_fails_closed(self, tmp_path: Path) -> None:
        """Truncated bytes produce BLOCKED with LENGTH_MISMATCH."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()

        truncated = artifact_bytes[:-5]
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=truncated,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
        assert HumanReviewAuditBundleExportVerificationReasonCode.LENGTH_MISMATCH in report.reason_codes
        assert report.safety_flags.length_verified is False

    def test_both_hash_and_length_mismatch(self, tmp_path: Path) -> None:
        """Both hash and length mismatches detected for appended bytes."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()

        extra = artifact_bytes + b"extra"
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=extra,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
        assert report.data_quality.hash_mismatch_count >= 1
        assert report.data_quality.length_mismatch_count >= 1


class TestStateSemantics:
    """PLANNED, NOT_APPLICABLE, and BLOCKED manifest handling."""

    def test_dry_run_planned_not_verified(self, tmp_path: Path) -> None:
        """PLANNED/dry-run export yields PLANNED manifest; verification yields
        NOT_APPLICABLE when allow_not_applicable is True."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path, dry_run=True)
        assert manifest.state == HumanReviewAuditBundleExportState.PLANNED

        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=b"",
            config=HumanReviewAuditBundleExportVerificationConfig(
                allow_not_applicable=True,
            ),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.NOT_APPLICABLE

    def test_blocked_manifest_not_verified(self, tmp_path: Path) -> None:
        """BLOCKED upstream path yields BLOCKED export manifest; verification
        produces BLOCKED with UPSTREAM_BLOCKED."""
        bundle_report = _build_blocked_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        assert manifest.state == HumanReviewAuditBundleExportState.BLOCKED

        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=b"any-bytes",
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
        assert HumanReviewAuditBundleExportVerificationReasonCode.UPSTREAM_BLOCKED in report.reason_codes

    def test_not_applicable_manifest_no_artifact(self, tmp_path: Path) -> None:
        """NOT_APPLICABLE export manifest yields NOT_APPLICABLE verification."""
        bundle_report = _build_not_applicable_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        assert manifest.state == HumanReviewAuditBundleExportState.NOT_APPLICABLE

        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=b"",
            config=HumanReviewAuditBundleExportVerificationConfig(
                allow_not_applicable=True,
            ),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.NOT_APPLICABLE


class TestFormatAndSafety:
    """Format classification and safety notice behavior."""

    def test_expected_format_json_matches(self, tmp_path: Path) -> None:
        """JSON format manifest + expected_format='json' => VERIFIED."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path, format="json")
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
            expected_format="json",
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.VERIFIED

    def test_unsupported_format_strict_fails_closed(self, tmp_path: Path) -> None:
        """Expected format not in allowlist with strict=True => BLOCKED."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path, format="json")
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
            expected_format="xml",
            config=HumanReviewAuditBundleExportVerificationConfig(strict=True),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
        assert HumanReviewAuditBundleExportVerificationReasonCode.UNSUPPORTED_FORMAT in report.reason_codes

    def test_unsupported_format_non_strict_degraded(self, tmp_path: Path) -> None:
        """Expected format not in allowlist with strict=False => DEGRADED."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path, format="json")
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
            expected_format="xml",
            config=HumanReviewAuditBundleExportVerificationConfig(strict=False),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.DEGRADED
        assert HumanReviewAuditBundleExportVerificationReasonCode.UNSUPPORTED_FORMAT in report.reason_codes

    def test_safety_notice_missing_degraded(self, tmp_path: Path) -> None:
        """Export without safety notice in body => DEGRADED."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path, format="json")
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()
        # Build a manifest pointing to different bytes without safety notice
        from json import dumps
        unsafe_bytes = dumps({"data": "no safety notice here"}).encode("utf-8")
        from hashlib import sha256 as _sha256
        unsafe_manifest = manifest.__class__(
            manifest_id=manifest.manifest_id,
            report_id=manifest.report_id,
            bundle_report_id=manifest.bundle_report_id,
            filename=manifest.filename,
            output_path=manifest.output_path,
            format=manifest.format,
            content_hash=_sha256(unsafe_bytes).hexdigest(),
            content_length=len(unsafe_bytes),
            state=manifest.state,
            safety_flags=manifest.safety_flags,
            reason_codes=manifest.reason_codes,
            issues=manifest.issues,
            metadata=manifest.metadata,
            notes=manifest.notes,
        )
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=unsafe_manifest,
            artifact_bytes=unsafe_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.DEGRADED
        assert HumanReviewAuditBundleExportVerificationReasonCode.SAFETY_NOTICE_MISSING in report.reason_codes


class TestWriterOutputSafety:
    """Writer output must be free of forbidden phrases."""

    @pytest.fixture
    def verified_report(self, tmp_path: Path) -> Any:
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        return verify_human_review_audit_bundle_export(inp)

    @pytest.fixture
    def blocked_report(self, tmp_path: Path) -> Any:
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()
        corrupted = bytearray(artifact_bytes)
        corrupted[-1] ^= 0xFF
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=bytes(corrupted),
        )
        return verify_human_review_audit_bundle_export(inp)

    def test_json_no_forbidden_terms(self, verified_report: Any) -> None:
        j = verification_report_to_json(verified_report)
        found = _scan_forbidden_terms(j)
        assert found == [], f"Forbidden terms in JSON: {found}"

    def test_markdown_no_forbidden_terms_verified(self, verified_report: Any) -> None:
        md = verification_report_to_markdown(verified_report)
        found = _scan_forbidden_terms(md)
        assert found == [], f"Forbidden terms in Markdown: {found}"

    def test_markdown_no_forbidden_terms_blocked(self, blocked_report: Any) -> None:
        md = verification_report_to_markdown(blocked_report)
        found = _scan_forbidden_terms(md)
        assert found == [], f"Forbidden terms in Markdown (blocked): {found}"

    def test_dict_no_forbidden_terms(self, verified_report: Any) -> None:
        from json import dumps as _dumps
        d = verification_report_to_dict(verified_report)
        text = _dumps(d, ensure_ascii=True, sort_keys=True)
        found = _scan_forbidden_terms(text)
        assert found == [], f"Forbidden terms in dict: {found}"


class TestOpaqueRefs:
    """MVP-45 verification never dereferences refs."""

    def test_manifest_refs_are_opaque_strings(self, tmp_path: Path) -> None:
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()
        # Inject a suspicious ref into manifest metadata
        from hunter.human_review_audit_bundle_export.models import (
            HumanReviewAuditBundleExportManifest,
            HumanReviewAuditBundleExportSafetyFlags,
        )
        evil_manifest = HumanReviewAuditBundleExportManifest(
            manifest_id=manifest.manifest_id,
            report_id=manifest.report_id,
            bundle_report_id=manifest.bundle_report_id,
            filename=manifest.filename,
            output_path="/etc/passwd",
            format=manifest.format,
            content_hash=manifest.content_hash,
            content_length=manifest.content_length,
            state=manifest.state,
            safety_flags=manifest.safety_flags,
            reason_codes=manifest.reason_codes,
            issues=manifest.issues,
            metadata={"ref": "http://malicious.example.com/token"},
            notes=manifest.notes,
        )
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=evil_manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        # Engine must not have crashed, not have followed refs.
        # It treats all refs as opaque strings and does not open/traverse them.
        assert report.state == HumanReviewAuditBundleExportVerificationState.VERIFIED
        # The suspicious output_path and metadata ref are opaque strings in the
        # manifest but are not stored in the verification report's metadata.
        # The engine never opened, followed, or traversed the ref.
        assert "/etc/passwd" not in str(report.input_summary)

    def test_verification_does_not_traverse_path(self, tmp_path: Path) -> None:
        """Verification uses caller-provided bytes, not output_path."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        # Instead of reading from output_path, provide matching bytes
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.VERIFIED
        # If we provide different bytes, verification must fail
        wrong = b"these bytes do not match the manifest"
        inp_wrong = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=wrong,
        )
        report_wrong = verify_human_review_audit_bundle_export(inp_wrong)
        assert report_wrong.state == HumanReviewAuditBundleExportVerificationState.BLOCKED


class TestReadOnlyBoundary:
    """MVP-45 verification performs no filesystem writes or reads."""

    def test_verification_no_filesystem_writes(self, tmp_path: Path) -> None:
        """Verify no new files are created outside tmp_path by verification."""
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()

        # Snapshot the project root for new files
        import os
        project_root = Path(__file__).resolve().parent.parent.parent
        proj_before = set(project_root.rglob("*")) if project_root.exists() else set()

        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        verification_report_to_dict(report)
        verification_report_to_json(report)
        verification_report_to_markdown(report)

        proj_after = set(project_root.rglob("*")) if project_root.exists() else set()
        new_files = proj_after - proj_before
        # Filter for .pyc caches that Python creates
        pyc_new = {
            f for f in new_files
            if "__pycache__" in str(f) or f.suffix in (".pyc", ".pyo")
        }
        new_files -= pyc_new
        assert len(new_files) == 0, f"Unexpected new files: {new_files}"

    def test_verification_no_network_calls(self, tmp_path: Path, monkeypatch: Any) -> None:
        """Block socket and urllib; verification must succeed without them."""
        import socket
        bundle_report = _build_ok_bundle_report(now=NOW)
        manifest = _export_artifact(bundle_report, tmp_path)
        artifact_bytes = (tmp_path / "output" / manifest.filename).read_bytes()
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )

        calls: list[Any] = []

        class BlockSocket:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                calls.append(("socket", args, kwargs))

            def __enter__(self) -> Any:
                return self

            def __exit__(self, *args: Any) -> None:
                pass

            def connect(self, *args: Any, **kwargs: Any) -> None:
                calls.append(("connect", args, kwargs))

        monkeypatch.setattr(socket, "socket", BlockSocket)
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.VERIFIED
        assert calls == [], f"Socket calls detected in verification: {calls}"


class TestEndToEndDeterminism:
    """Determinism across the full chain: export → verification → writer."""

    def test_full_chain_deterministic(self, tmp_path: Path) -> None:
        """Repeated full chain with same parameters yields identical results."""
        bundle_report = _build_ok_bundle_report(now=NOW)

        def run() -> tuple[Any, str, str]:
            m = _export_artifact(bundle_report, tmp_path, overwrite=True)
            b = (tmp_path / "output" / m.filename).read_bytes()
            inp = HumanReviewAuditBundleExportVerificationInput(
                manifest=m,
                artifact_bytes=b,
            )
            r = verify_human_review_audit_bundle_export(inp)
            j = verification_report_to_json(r)
            md = verification_report_to_markdown(r)
            return r, j, md

        r1, j1, md1 = run()
        r2, j2, md2 = run()
        assert j1 == j2
        assert md1 == md2
        assert r1.verification_id == r2.verification_id
        assert r1.report_id == r2.report_id
        assert r1.state == r2.state
        assert r1.reason_codes == r2.reason_codes
        assert r1.data_quality == r2.data_quality
