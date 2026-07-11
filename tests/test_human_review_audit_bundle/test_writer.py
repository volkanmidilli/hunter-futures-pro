"""Unit tests for hunter.human_review_audit_bundle writer."""

from __future__ import annotations

from datetime import datetime, timezone
from json import loads
from typing import Any

import pytest

from hunter.human_review_audit_bundle.engine import build_human_review_audit_bundle
from hunter.human_review_audit_bundle.models import (
    HumanReviewAuditBundleConfig,
    HumanReviewAuditBundleInput,
    HumanReviewAuditBundleReasonCode,
    HumanReviewAuditBundleReport,
    HumanReviewAuditBundleState,
    SAFETY_NOTICE,
)
from hunter.human_review_audit_bundle.writer import (
    bundle_report_to_dict,
    bundle_report_to_json,
    bundle_report_to_markdown,
)
from hunter.human_review_decision_log.models import (
    HumanReviewDecisionLogDataQuality,
    HumanReviewDecisionLogReport,
    HumanReviewDecisionLogState,
    HumanReviewDecisionReasonCode,
)
from hunter.human_review_decision_log_consistency.models import (
    HumanReviewDecisionLogConsistencyDataQuality,
    HumanReviewDecisionLogConsistencyReport,
    HumanReviewDecisionLogConsistencyState,
)
from hunter.human_review_queue.models import (
    HumanReviewQueueDataQuality,
    HumanReviewQueueIssue,
    HumanReviewQueueReport,
    HumanReviewQueueState,
)


NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)


def _queue_report_ok() -> HumanReviewQueueReport:
    return HumanReviewQueueReport(
        report_id="queue-ok-1",
        state=HumanReviewQueueState.OK,
        generated_at=NOW,
        data_quality=HumanReviewQueueDataQuality(
            total_source_records=1,
            total_queue_entries=1,
            total_issues=0,
            sections_present=1,
        ),
    )


def _decision_log_report_ok() -> HumanReviewDecisionLogReport:
    return HumanReviewDecisionLogReport(
        report_id="decision-log-ok-1",
        state=HumanReviewDecisionLogState.OK,
        generated_at=NOW,
        data_quality=HumanReviewDecisionLogDataQuality(
            total_queue_entry_refs=1,
            total_decision_records=1,
            total_decision_results=1,
            total_issues=0,
        ),
    )


def _consistency_report_ok() -> HumanReviewDecisionLogConsistencyReport:
    return HumanReviewDecisionLogConsistencyReport(
        report_id="consistency-ok-1",
        state=HumanReviewDecisionLogConsistencyState.OK,
        generated_at=NOW,
        data_quality=HumanReviewDecisionLogConsistencyDataQuality(
            total_queue_entries=1,
            total_decision_log_refs=1,
            matched_refs=1,
        ),
    )


def _bundle_report_ok() -> HumanReviewAuditBundleReport:
    return build_human_review_audit_bundle(
        HumanReviewAuditBundleInput(
            queue_report=_queue_report_ok(),
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            generated_at=NOW,
        )
    )


def _bundle_report_not_applicable() -> HumanReviewAuditBundleReport:
    return build_human_review_audit_bundle(
        HumanReviewAuditBundleInput(generated_at=NOW)
    )


def _bundle_report_blocked() -> HumanReviewAuditBundleReport:
    decision_log = HumanReviewDecisionLogReport(
        report_id="decision-log-blocked-1",
        state=HumanReviewDecisionLogState.BLOCKED,
        generated_at=NOW,
        data_quality=HumanReviewDecisionLogDataQuality(
            unsafe_content_count=1,
            total_decision_records=1,
        ),
        reason_codes=(HumanReviewDecisionReasonCode.UNSAFE_CONTENT,),
    )
    return build_human_review_audit_bundle(
        HumanReviewAuditBundleInput(
            queue_report=_queue_report_ok(),
            decision_log_report=decision_log,
            consistency_report=_consistency_report_ok(),
            generated_at=NOW,
        )
    )


def _bundle_report_strict_promoted() -> HumanReviewAuditBundleReport:
    queue = HumanReviewQueueReport(
        report_id="queue-degraded-1",
        state=HumanReviewQueueState.DEGRADED,
        generated_at=NOW,
        data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
    )
    return build_human_review_audit_bundle(
        HumanReviewAuditBundleInput(
            queue_report=queue,
            decision_log_report=_decision_log_report_ok(),
            consistency_report=_consistency_report_ok(),
            config=HumanReviewAuditBundleConfig(strict=True),
            generated_at=NOW,
        )
    )


class TestDictOutput:
    def test_dict_is_json_compatible(self) -> None:
        report = _bundle_report_ok()
        data = bundle_report_to_dict(report)
        json_text = bundle_report_to_json(report)
        assert loads(json_text) == data

    def test_dict_top_level_order(self) -> None:
        report = _bundle_report_ok()
        data = bundle_report_to_dict(report)
        expected_keys = [
            "safety_notice",
            "bundle_id",
            "report_id",
            "generated_at",
            "state",
            "project_version",
            "sections",
            "issues",
            "data_quality",
            "safety_flags",
            "reason_codes",
            "metadata",
            "notes",
        ]
        assert list(data.keys()) == expected_keys

    def test_dict_state_as_string(self) -> None:
        report = _bundle_report_ok()
        data = bundle_report_to_dict(report)
        assert data["state"] == "ok"
        assert isinstance(data["state"], str)

    def test_dict_reason_codes_are_strings(self) -> None:
        report = _bundle_report_ok()
        data = bundle_report_to_dict(report)
        assert all(isinstance(rc, str) for rc in data["reason_codes"])
        assert "ok" in data["reason_codes"]
        assert "research_only" in data["reason_codes"]

    def test_dict_sections_order(self) -> None:
        report = _bundle_report_ok()
        data = bundle_report_to_dict(report)
        kinds = [s["section_kind"] for s in data["sections"]]
        assert kinds == sorted(kinds)

    def test_dict_data_quality_keys(self) -> None:
        report = _bundle_report_ok()
        data = bundle_report_to_dict(report)
        dq = data["data_quality"]
        expected_keys = [
            "section_count",
            "upstream_issue_count",
            "blocking_issues",
            "advisory_issues",
            "info_findings",
            "queue_entry_count",
            "decision_result_count",
            "consistency_cross_reference_count",
            "unsafe_content_count",
            "forbidden_term_count",
        ]
        assert list(dq.keys()) == expected_keys


class TestJsonOutput:
    def test_json_deterministic(self) -> None:
        report1 = _bundle_report_ok()
        report2 = _bundle_report_ok()
        assert bundle_report_to_json(report1) == bundle_report_to_json(report2)

    def test_json_contains_safety_notice(self) -> None:
        report = _bundle_report_ok()
        json_text = bundle_report_to_json(report)
        assert SAFETY_NOTICE in json_text

    def test_json_no_random_indent(self) -> None:
        report = _bundle_report_ok()
        json_text = bundle_report_to_json(report)
        assert json_text.startswith("{")
        assert json_text.endswith("}")


class TestMarkdownOutput:
    def test_markdown_deterministic(self) -> None:
        report1 = _bundle_report_ok()
        report2 = _bundle_report_ok()
        assert bundle_report_to_markdown(report1) == bundle_report_to_markdown(report2)

    def test_markdown_safety_notice_at_top(self) -> None:
        report = _bundle_report_ok()
        md = bundle_report_to_markdown(report)
        assert md.startswith(
            "This bundle is a local, audit-only, human-audit research artifact."
        )
        assert SAFETY_NOTICE in md

    def test_markdown_contains_state(self) -> None:
        report = _bundle_report_ok()
        md = bundle_report_to_markdown(report)
        assert "state" in md


class TestStateSerialization:
    def test_ok_serialization(self) -> None:
        report = _bundle_report_ok()
        assert report.state == HumanReviewAuditBundleState.OK
        data = bundle_report_to_dict(report)
        assert data["state"] == "ok"
        assert data["data_quality"]["section_count"] == 3
        assert data["data_quality"]["blocking_issues"] == 0

    def test_blocked_serialization(self) -> None:
        report = _bundle_report_blocked()
        assert report.state == HumanReviewAuditBundleState.BLOCKED
        data = bundle_report_to_dict(report)
        assert data["state"] == "blocked"
        assert HumanReviewAuditBundleReasonCode.UPSTREAM_BLOCKED.value in data["reason_codes"]
        assert data["safety_flags"]["is_safe"] is False
        md = bundle_report_to_markdown(report)
        assert "blocked" in md.lower()

    def test_not_applicable_serialization(self) -> None:
        report = _bundle_report_not_applicable()
        assert report.state == HumanReviewAuditBundleState.NOT_APPLICABLE
        data = bundle_report_to_dict(report)
        assert data["state"] == "not_applicable"
        assert HumanReviewAuditBundleReasonCode.NOT_APPLICABLE.value in data["reason_codes"]
        assert data["sections"] == []
        assert data["issues"] == []

    def test_strict_promoted_serialization(self) -> None:
        report = _bundle_report_strict_promoted()
        assert report.state == HumanReviewAuditBundleState.BLOCKED
        data = bundle_report_to_dict(report)
        assert data["state"] == "blocked"
        md = bundle_report_to_markdown(report)
        assert "blocked" in md.lower()


class TestEmptyAndUpstreamIssues:
    def test_empty_sections_and_issues(self) -> None:
        report = _bundle_report_not_applicable()
        data = bundle_report_to_dict(report)
        assert data["sections"] == []
        assert data["issues"] == []
        assert data["data_quality"]["section_count"] == 0

    def test_upstream_carried_forward_issue(self) -> None:
        queue = HumanReviewQueueReport(
            report_id="queue-issues-1",
            state=HumanReviewQueueState.OK,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
            issues=(
                HumanReviewQueueIssue(
                    issue_id="q-iss-1",
                    issue_type="duplicate_source_id",
                    severity="advisory",
                    title="dup",
                    description="d",
                    generated_at=NOW,
                ),
            ),
        )
        report = build_human_review_audit_bundle(
            HumanReviewAuditBundleInput(
                queue_report=queue,
                decision_log_report=_decision_log_report_ok(),
                consistency_report=_consistency_report_ok(),
                generated_at=NOW,
            )
        )
        data = bundle_report_to_dict(report)
        assert len(data["issues"]) == 1
        issue = data["issues"][0]
        assert issue["source_section_kind"] == "queue"
        assert issue["source_id"] == "q-iss-1"
        assert issue["severity"] == "advisory"


class TestSafetyBoundaryInArtifact:
    _FORBIDDEN_PHRASES = (
        "shell command",
        "run this",
        "execute this",
        "execute the",
        "deployment steps",
        "deploy to",
        "infrastructure steps",
        "server setup",
        "database setup",
        "scheduler",
        "dashboard",
        "trading signal",
        "trade this",
        "freqtrade",
        "runtime strategy",
        "production-ready",
        "production ready",
        "ready for production",
        "certified",
        "approval claim",
        "suitability assessment",
        "recommendation",
        "executable remediation",
        "remediation plan",
        "patch and deploy",
        "binance",
        "api key",
        "network request",
        "filesystem access",
    )

    def _artifact_body_without_safety_notice(self, text: str) -> str:
        """Return artifact text with the safety notice removed."""
        return text.replace(SAFETY_NOTICE, "")

    @pytest.mark.parametrize("artifact", [bundle_report_to_json, bundle_report_to_markdown])
    def test_no_forbidden_action_phrases_outside_safety_notice(
        self, artifact: Any
    ) -> None:
        report = _bundle_report_ok()
        text = artifact(report)
        body = self._artifact_body_without_safety_notice(text)
        lower_body = body.lower()
        for phrase in self._FORBIDDEN_PHRASES:
            assert phrase not in lower_body, f"forbidden phrase {phrase!r} found in artifact body"

    @pytest.mark.parametrize("artifact", [bundle_report_to_json, bundle_report_to_markdown])
    def test_safety_notice_negations_are_allowed(self, artifact: Any) -> None:
        report = _bundle_report_ok()
        text = artifact(report)
        # The safety notice must remain intact and contain explicit negations.
        assert SAFETY_NOTICE in text
        assert "does not imply" in text


class TestOpaqueRefs:
    def test_refs_emitted_only_as_strings(self) -> None:
        path_ref = "/data/queue-2026-01-01.json"
        queue = HumanReviewQueueReport(
            report_id=path_ref,
            state=HumanReviewQueueState.OK,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
        )
        report = build_human_review_audit_bundle(
            HumanReviewAuditBundleInput(
                queue_report=queue,
                decision_log_report=HumanReviewDecisionLogReport(
                    report_id="decision-log-with-path",
                    state=HumanReviewDecisionLogState.OK,
                    generated_at=NOW,
                    data_quality=HumanReviewDecisionLogDataQuality(total_decision_records=1),
                ),
                consistency_report=HumanReviewDecisionLogConsistencyReport(
                    report_id="consistency-with-path",
                    state=HumanReviewDecisionLogConsistencyState.OK,
                    generated_at=NOW,
                    data_quality=HumanReviewDecisionLogConsistencyDataQuality(
                        total_queue_entries=1,
                        matched_refs=1,
                    ),
                ),
                generated_at=NOW,
            )
        )
        data = bundle_report_to_dict(report)
        # Refs are strings; they are not opened or parsed into structures.
        section = data["sections"][2]
        assert section["upstream_report_id"] == path_ref
        assert isinstance(section["upstream_report_id"], str)

    def test_bundle_id_is_hash_not_path(self) -> None:
        path_ref = "/path/to/queue.json"
        queue = HumanReviewQueueReport(
            report_id=path_ref,
            state=HumanReviewQueueState.OK,
            generated_at=NOW,
            data_quality=HumanReviewQueueDataQuality(total_queue_entries=1),
        )
        report = build_human_review_audit_bundle(
            HumanReviewAuditBundleInput(
                queue_report=queue,
                decision_log_report=_decision_log_report_ok(),
                consistency_report=_consistency_report_ok(),
                generated_at=NOW,
            )
        )
        data = bundle_report_to_dict(report)
        assert path_ref not in data["bundle_id"]
        assert data["bundle_id"].startswith("bundle-")


class TestNoFilesystemOrNetwork:
    def test_no_filesystem_access(self, monkeypatch: Any) -> None:
        def _fake_open(*args: Any, **kwargs: Any) -> Any:
            pytest.fail("open called unexpectedly")

        monkeypatch.setattr("builtins.open", _fake_open)
        report = _bundle_report_ok()
        bundle_report_to_dict(report)
        bundle_report_to_json(report)
        bundle_report_to_markdown(report)

    def test_no_network_access(self, monkeypatch: Any) -> None:
        def _fake_urlopen(*args: Any, **kwargs: Any) -> Any:
            pytest.fail("urlopen called unexpectedly")

        urllib = pytest.importorskip("urllib.request")
        monkeypatch.setattr(urllib, "urlopen", _fake_urlopen)
        report = _bundle_report_ok()
        bundle_report_to_dict(report)
        bundle_report_to_json(report)
        bundle_report_to_markdown(report)


class TestWriterAPI:
    def test_all_functions_return_content_only(self) -> None:
        report = _bundle_report_ok()
        data = bundle_report_to_dict(report)
        json_text = bundle_report_to_json(report)
        md_text = bundle_report_to_markdown(report)
        assert isinstance(data, dict)
        assert isinstance(json_text, str)
        assert isinstance(md_text, str)
        assert len(json_text) > 0
        assert len(md_text) > 0

    def test_json_indent_none(self) -> None:
        report = _bundle_report_ok()
        compact = bundle_report_to_json(report, indent=None)
        assert "\n" not in compact
