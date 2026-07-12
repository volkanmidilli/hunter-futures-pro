"""Integration tests for hunter.human_review_audit_bundle_export end-to-end flow."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from json import loads
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
    manifest_to_dict,
    manifest_to_json,
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


NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def now() -> datetime:
    """Return a fixed timezone-aware datetime for deterministic tests."""
    return NOW


# Forbidden action phrases that must not appear in generated artifact bodies
# outside of the explicit safety notice. These mirror the production safety
# scanner and the task boundaries: no shell commands, patches, deployment,
# infrastructure, executable remediation, trading/API/Freqtrade/Binance runtime,
# or approval/readiness/recommendation/suitability claims.
_FORBIDDEN_ACTION_PHRASES: tuple[str, ...] = (
    "shell command",
    "run this command",
    "execute now",
    "execute order",
    "apply patch",
    "deploy immediately",
    "push to production",
    "release to production",
    "infrastructure change",
    "automated remediation",
    "executable remediation",
    "auto fix",
    "self healing",
    "place order",
    "buy signal",
    "sell signal",
    "hold signal",
    "live trading",
    "go live",
    "trading ready",
    "ready for trading",
    "recommendation to trade",
    "suitable for trading",
    "approved for deployment",
    "approved for production",
    "production ready",
    "certified safe",
    "decision approved",
    "decision certified",
    "binance key",
    "api key",
    "private key",
    "exchange api",
    "leverage up",
    "short squeeze",
    "margin call",
    "liquidate position",
    "close and trade",
    "close now",
    "task assignment",
    "task complete",
    "task completed",
    "auto assign",
    "create ticket",
    "open jira",
    "send email",
    "notify team",
)


# Allowed negation phrases and safety-flag names that may legitimately appear in
# artifact bodies (safety notices and JSON safety-flag fields).
_ALLOWED_NEGATION_PHRASES: tuple[str, ...] = (
    "does not imply",
    "is not a",
    "not a production",
    "not a trading",
    "does not",
    "no_executable_actions",
    "no_trading_instructions",
    "no_approval_claims",
    "no_automated_remediation",
    "no_automatic_assignment",
    "no_task_completion_claims",
    "references_opaque",
    "no_network",
    "no_server",
    "audit_only",
    "human_audit_only",
    "research_only",
)


_QID = "ok-qid-1"


# ---------------------------------------------------------------------------
# Upstream report builders
# ---------------------------------------------------------------------------


def _build_ok_queue_report(now: datetime) -> HumanReviewQueueReport:
    """Return a minimal OK queue report with a single not_applicable entry."""
    entry = HumanReviewQueueEntry(
        queue_entry_id=_QID,
        source_id="src-ok-1",
        source_kind="issue",
        record_id="rec-ok-1",
        entry_state="not_applicable",
        priority="info",
        decision_hint="not_applicable_for_audit",
        severity="info",
        reason_codes=("not_applicable",),
        title="Informational review note",
        description="A low-priority human audit note.",
        generated_at=now,
    )
    return HumanReviewQueueReport(
        report_id="queue-ok",
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
    """Build a queue input that will produce a DEGRADED queue report."""
    record = HumanReviewSourceRecord(
        source_id="src-degraded-1",
        source_kind="issue",
        record_id="rec-degraded-1",
        title="Degraded review item",
        description="Needs human review before further audit steps.",
        state="open",
        severity="advisory",
        reason_codes=("orphan_related_record", "advisory_severity"),
        related_record_ids=("missing-related-id",),
        artifact_ref="artifact://degraded-1",
        report_ref="report://degraded-1",
        generated_at=now,
    )
    return HumanReviewQueueInput(
        source_records=(record,),
        config=HumanReviewQueueConfig(),
        generated_at=now,
    )


def _build_blocked_queue_input(now: datetime) -> HumanReviewQueueInput:
    """Build a queue input that will produce a BLOCKED queue report."""
    record = HumanReviewSourceRecord(
        source_id="src-blocked-1",
        source_kind="issue",
        record_id="rec-blocked-1",
        title="Critical blocking issue",
        description="Blocking severity item.",
        state="blocked",
        severity="blocking",
        reason_codes=("blocking_severity",),
        artifact_ref="artifact://blocked-1",
        report_ref="report://blocked-1",
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
    """Build a decision log input matching the given queue report."""
    queue_entry = queue_report.queue_entries[0] if queue_report.queue_entries else None
    qid = queue_entry_id if queue_entry_id is not None else (queue_entry.queue_entry_id if queue_entry else _QID)
    entry_state = queue_entry.entry_state if queue_entry else "queued"
    severity = queue_entry.severity if queue_entry else "info"
    priority = queue_entry.priority if queue_entry else "info"
    source_id = queue_entry.source_id if queue_entry else "src-1"
    source_kind = queue_entry.source_kind if queue_entry else "issue"
    record_id = queue_entry.record_id if queue_entry else "rec-1"
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
        artifact_ref="artifact://decision-1",
        report_ref="report://decision-1",
        generated_at=now,
    )
    decision = HumanReviewDecisionRecord(
        decision_id="decision-ok-1",
        queue_entry_id=qid,
        reviewer="reviewer-1",
        decided_at=now,
        outcome=outcome,
        rationale="Accepted for audit log only."
        if outcome == HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value
        else "Not applicable for audit log.",
        reason_codes=entry_reason_codes,
        artifact_ref="artifact://decision-1",
        report_ref="report://decision-1",
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
    """Build a consistency input from the two upstream reports."""
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
    strict: bool = False,
) -> HumanReviewAuditBundleInput:
    """Build the audit bundle input from the three upstream reports."""
    return HumanReviewAuditBundleInput(
        queue_report=queue_report,
        decision_log_report=decision_log_report,
        consistency_report=consistency_report,
        config=HumanReviewAuditBundleConfig(strict=strict),
        generated_at=now,
    )


def _build_ok_bundle_report(now: datetime) -> Any:
    """Build an OK audit bundle report end-to-end."""
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
    """Build a DEGRADED audit bundle report end-to-end."""
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
    """Build a BLOCKED audit bundle report end-to-end."""
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
    """Build a NOT_APPLICABLE audit bundle report end-to-end."""
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
# Export helper
# ---------------------------------------------------------------------------


def _build_export_input(
    bundle_report: Any,
    tmp_path: Path,
    format: str = "json",
    dry_run: bool = False,
    overwrite: bool = False,
    verify_hash: bool = True,
    strict: bool = False,
) -> HumanReviewAuditBundleExportInput:
    """Build an export input using pytest tmp_path subdirectories."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    return HumanReviewAuditBundleExportInput(
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


# ---------------------------------------------------------------------------
# Safety sweep helpers
# ---------------------------------------------------------------------------


def _artifact_body_without_safety(output: str) -> str:
    """Return the artifact body with safety notices and allowed phrases removed."""
    from hunter.human_review_audit_bundle.models import SAFETY_NOTICE as BUNDLE_SAFETY_NOTICE
    from hunter.human_review_audit_bundle_export.models import SAFETY_NOTICE as EXPORT_SAFETY_NOTICE

    body = output.replace(BUNDLE_SAFETY_NOTICE, "")
    body = body.replace(EXPORT_SAFETY_NOTICE, "")
    for allowed in _ALLOWED_NEGATION_PHRASES:
        body = body.replace(allowed, "")
    return body


def _forbidden_phrases_found(output: str) -> list[str]:
    """Return any forbidden action phrases found outside allowed contexts."""
    body = _artifact_body_without_safety(output).lower()
    return [phrase for phrase in _FORBIDDEN_ACTION_PHRASES if phrase in body]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


def test_ok_written_path(now: datetime, tmp_path: Path) -> None:
    """OK/WRITTEN path: end-to-end export succeeds into tmp_path."""
    bundle_report = _build_ok_bundle_report(now)
    assert bundle_report.state == HumanReviewAuditBundleState.OK

    export_input = _build_export_input(bundle_report, tmp_path)
    manifest = export_human_review_audit_bundle_artifact(export_input)

    assert manifest.state == HumanReviewAuditBundleExportState.WRITTEN
    assert manifest.safety_flags.hash_verified
    assert Path(manifest.output_path).exists()
    assert Path(manifest.output_path).parent == tmp_path / "output"
    written_bytes = Path(manifest.output_path).read_bytes()
    assert sha256(written_bytes).hexdigest() == manifest.content_hash
    assert len(written_bytes) == manifest.content_length


def test_degraded_upstream_path(now: datetime, tmp_path: Path) -> None:
    """DEGRADED upstream path: bundle/export handles DEGRADED safely."""
    bundle_report = _build_degraded_bundle_report(now)
    assert bundle_report.state == HumanReviewAuditBundleState.DEGRADED

    export_input = _build_export_input(bundle_report, tmp_path)
    manifest = export_human_review_audit_bundle_artifact(export_input)

    assert manifest.state == HumanReviewAuditBundleExportState.WRITTEN
    assert HumanReviewAuditBundleExportReasonCode.UPSTREAM_DEGRADED.value in [
        rc.value for rc in manifest.reason_codes
    ]
    assert Path(manifest.output_path).exists()


def test_blocked_upstream_path(now: datetime, tmp_path: Path) -> None:
    """BLOCKED upstream path: no artifact write; manifest is safe blocked state."""
    bundle_report = _build_blocked_bundle_report(now)
    assert bundle_report.state == HumanReviewAuditBundleState.BLOCKED

    export_input = _build_export_input(bundle_report, tmp_path)
    manifest = export_human_review_audit_bundle_artifact(export_input)

    assert manifest.state == HumanReviewAuditBundleExportState.BLOCKED
    assert HumanReviewAuditBundleExportReasonCode.UPSTREAM_BLOCKED.value in [
        rc.value for rc in manifest.reason_codes
    ]
    assert not Path(manifest.output_path).exists()
    assert (tmp_path / "output").exists()
    # Temp directory should be empty (no temp file left behind).
    assert not any((tmp_path / "tmp").iterdir())


def test_not_applicable_path(now: datetime, tmp_path: Path) -> None:
    """NOT_APPLICABLE path: no artifact write."""
    bundle_report = _build_not_applicable_bundle_report(now)
    assert bundle_report.state == HumanReviewAuditBundleState.NOT_APPLICABLE

    export_input = _build_export_input(bundle_report, tmp_path)
    manifest = export_human_review_audit_bundle_artifact(export_input)

    assert manifest.state == HumanReviewAuditBundleExportState.NOT_APPLICABLE
    assert HumanReviewAuditBundleExportReasonCode.NOT_APPLICABLE.value in [
        rc.value for rc in manifest.reason_codes
    ]
    assert not Path(manifest.output_path).exists()
    assert not any((tmp_path / "tmp").iterdir())


def test_dry_run_path(now: datetime, tmp_path: Path) -> None:
    """Dry-run path: plan/export returns planned/no-write result."""
    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path, dry_run=True)
    manifest = export_human_review_audit_bundle_artifact(export_input)

    assert manifest.state == HumanReviewAuditBundleExportState.PLANNED
    assert not Path(manifest.output_path).exists()
    assert not any((tmp_path / "tmp").iterdir())


def test_overwrite_denied_and_allowed(now: datetime, tmp_path: Path) -> None:
    """Overwrite denied/allowed path using tmp_path."""
    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path)

    # First write succeeds.
    manifest1 = export_human_review_audit_bundle_artifact(export_input)
    assert manifest1.state == HumanReviewAuditBundleExportState.WRITTEN

    # Second write without overwrite is BLOCKED.
    export_input_denied = _build_export_input(bundle_report, tmp_path, overwrite=False)
    manifest2 = export_human_review_audit_bundle_artifact(export_input_denied)
    assert manifest2.state == HumanReviewAuditBundleExportState.BLOCKED
    assert HumanReviewAuditBundleExportReasonCode.OUTPUT_EXISTS.value in [
        rc.value for rc in manifest2.reason_codes
    ]

    # Third write with overwrite succeeds.
    export_input_allowed = _build_export_input(bundle_report, tmp_path, overwrite=True)
    manifest3 = export_human_review_audit_bundle_artifact(export_input_allowed)
    assert manifest3.state == HumanReviewAuditBundleExportState.WRITTEN


def test_hash_verification(now: datetime, tmp_path: Path) -> None:
    """Hash verification: written bytes match manifest hash/length."""
    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path, verify_hash=True)
    manifest = export_human_review_audit_bundle_artifact(export_input)

    assert manifest.state == HumanReviewAuditBundleExportState.WRITTEN
    assert manifest.safety_flags.hash_verified
    written_bytes = Path(manifest.output_path).read_bytes()
    assert sha256(written_bytes).hexdigest() == manifest.content_hash
    assert len(written_bytes) == manifest.content_length


def test_hash_verification_disabled(now: datetime, tmp_path: Path) -> None:
    """Hash verification disabled: write succeeds without hash_verified flag."""
    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path, verify_hash=False)
    manifest = export_human_review_audit_bundle_artifact(export_input)

    assert manifest.state == HumanReviewAuditBundleExportState.WRITTEN
    assert not manifest.safety_flags.hash_verified
    assert Path(manifest.output_path).exists()


def test_determinism(now: datetime, tmp_path: Path) -> None:
    """Repeated end-to-end calls produce identical body/hash/manifest fields."""
    def export() -> Any:
        bundle_report = _build_ok_bundle_report(now)
        export_input = _build_export_input(bundle_report, tmp_path, overwrite=True)
        return export_human_review_audit_bundle_artifact(export_input)

    manifest1 = export()
    manifest2 = export()

    assert manifest1.content_hash == manifest2.content_hash
    assert manifest1.content_length == manifest2.content_length
    assert manifest1.manifest_id == manifest2.manifest_id
    assert manifest1.filename == manifest2.filename
    assert manifest1.report_id == manifest2.report_id
    assert manifest_to_json(manifest1) == manifest_to_json(manifest2)

    written1 = Path(manifest1.output_path).read_bytes()
    written2 = Path(manifest2.output_path).read_bytes()
    assert sha256(written1).hexdigest() == sha256(written2).hexdigest()


def test_opaque_refs_not_opened(now: datetime, tmp_path: Path) -> None:
    """Opaque refs remain strings and are not opened/resolved/fetched."""
    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path)
    manifest = export_human_review_audit_bundle_artifact(export_input)

    body = Path(manifest.output_path).read_text()
    assert "file://" not in body
    assert "http://" not in body
    assert "https://" not in body
    assert "ftp://" not in body

    # Manifest output_path and tmp_path are absolute tmp_path subdirectories.
    assert Path(manifest.output_path).is_absolute()
    assert Path(manifest.output_path).resolve().is_relative_to(tmp_path.resolve())


def test_generated_artifact_safety_json(now: datetime, tmp_path: Path) -> None:
    """Generated JSON artifact body contains no forbidden action phrases."""
    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path, format="json")
    manifest = export_human_review_audit_bundle_artifact(export_input)

    body = Path(manifest.output_path).read_text()
    found = _forbidden_phrases_found(body)
    assert not found, f"Found forbidden phrases in JSON body: {found}"

    # Also verify the manifest JSON itself.
    manifest_text = manifest_to_json(manifest)
    found_manifest = _forbidden_phrases_found(manifest_text)
    assert not found_manifest, f"Found forbidden phrases in manifest JSON: {found_manifest}"


def test_generated_artifact_safety_markdown(now: datetime, tmp_path: Path) -> None:
    """Generated Markdown artifact body contains no forbidden action phrases."""
    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path, format="markdown")
    manifest = export_human_review_audit_bundle_artifact(export_input)

    body = Path(manifest.output_path).read_text()
    found = _forbidden_phrases_found(body)
    assert not found, f"Found forbidden phrases in Markdown body: {found}"


def test_path_safety_traversal_blocked(now: datetime, tmp_path: Path, monkeypatch: Any) -> None:
    """Path traversal in output path fails closed."""
    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path)

    # Monkeypatch the filename builder to inject a traversal attempt. The Step 1
    # planner will catch it during filename validation.
    from hunter.human_review_audit_bundle_export import engine as export_engine

    def _evil_filename(*args: Any, **kwargs: Any) -> str:
        return "../other.json"

    monkeypatch.setattr(export_engine, "_build_filename", _evil_filename)

    manifest = export_human_review_audit_bundle_artifact(export_input)

    assert manifest.state == HumanReviewAuditBundleExportState.BLOCKED
    assert HumanReviewAuditBundleExportReasonCode.PATH_TRAVERSAL_ATTEMPT.value in [
        rc.value for rc in manifest.reason_codes
    ]
    # No file outside tmp_path should be created.
    output_path = tmp_path / "output" / "other.json"
    assert not output_path.exists()


def test_path_safety_url_like_blocked(now: datetime, tmp_path: Path, monkeypatch: Any) -> None:
    """URL-like output path fails closed."""
    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path)

    from hunter.human_review_audit_bundle_export import engine as export_engine

    def _evil_filename(*args: Any, **kwargs: Any) -> str:
        return "http://example.com/test.json"

    monkeypatch.setattr(export_engine, "_build_filename", _evil_filename)

    manifest = export_human_review_audit_bundle_artifact(export_input)

    assert manifest.state == HumanReviewAuditBundleExportState.BLOCKED
    assert HumanReviewAuditBundleExportReasonCode.PATH_TRAVERSAL_ATTEMPT.value in [
        rc.value for rc in manifest.reason_codes
    ]
    assert not any((tmp_path / "output").iterdir())


def test_no_writes_outside_tmp_path(now: datetime, tmp_path: Path) -> None:
    """No writes occur outside the pytest-provided tmp_path."""
    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path)

    before = set(tmp_path.rglob("*"))
    manifest = export_human_review_audit_bundle_artifact(export_input)
    after = set(tmp_path.rglob("*"))

    new_files = after - before
    assert manifest.state == HumanReviewAuditBundleExportState.WRITTEN
    assert len(new_files) == 1
    new_file = new_files.pop()
    assert new_file.is_relative_to(tmp_path / "output")


def test_no_network_or_runtime_behavior(now: datetime, tmp_path: Path, monkeypatch: Any) -> None:
    """Export does not perform network, server, or trading runtime calls."""
    import socket
    import urllib.request

    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path)

    socket_calls: list[Any] = []
    urllib_calls: list[Any] = []

    class RaisingSocket:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            socket_calls.append((args, kwargs))
            raise RuntimeError("socket disabled")

    class RaisingUrlopen:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            urllib_calls.append((args, kwargs))
            raise RuntimeError("urlopen disabled")

    monkeypatch.setattr(socket, "socket", RaisingSocket)
    monkeypatch.setattr(urllib.request, "urlopen", RaisingUrlopen)

    manifest = export_human_review_audit_bundle_artifact(export_input)
    assert manifest.state == HumanReviewAuditBundleExportState.WRITTEN
    assert socket_calls == []
    assert urllib_calls == []


def test_manifest_json_shape(now: datetime, tmp_path: Path) -> None:
    """Manifest dict/JSON shape is correct and deterministic."""
    bundle_report = _build_ok_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path)
    manifest = export_human_review_audit_bundle_artifact(export_input)

    d = manifest_to_dict(manifest)
    assert d["manifest_id"].startswith("hra-bundle-export-manifest-")
    assert d["report_id"].startswith("hra-bundle-export-report-")
    assert d["state"] == HumanReviewAuditBundleExportState.WRITTEN.value
    assert d["safety_flags"]["hash_verified"] is True
    assert d["content_length"] > 0

    parsed = loads(manifest_to_json(manifest))
    assert parsed == d


def test_blocked_no_temp_file_left_behind(now: datetime, tmp_path: Path) -> None:
    """BLOCKED export leaves no temp file behind."""
    bundle_report = _build_blocked_bundle_report(now)
    export_input = _build_export_input(bundle_report, tmp_path)
    manifest = export_human_review_audit_bundle_artifact(export_input)

    assert manifest.state == HumanReviewAuditBundleExportState.BLOCKED
    assert not any((tmp_path / "tmp").iterdir())
    assert not any((tmp_path / "output").iterdir())
