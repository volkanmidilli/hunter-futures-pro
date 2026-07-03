"""Pure engine for hunter.run_orchestrator.

MVP-30 — Local Research Run Orchestrator.

The engine executes a deterministic, caller-provided research run plan against
existing local engine public APIs. It does not start services, schedule jobs,
read arbitrary files, or connect to networks, exchanges, databases, or external
services. It never emits trading or execution commands.

All inputs are provided by the caller in-memory. File paths and metadata are
opaque local strings; the engine never opens, follows, traverses, validates,
fetches, or executes them except when passing an explicit local path to an
existing writer module.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.backtest import (
    BacktestInput,
    BacktestRunConfig,
    build_backtest_report,
    write_backtest_report,
)
from hunter.discovery import (
    DiscoveryConfig,
    DiscoveryInput,
    build_discovery_report,
    write_discovery_report,
)
from hunter.portfolio_construction import (
    PortfolioConstructionConfig,
    PortfolioConstructionInput,
    build_portfolio_construction_report,
    write_portfolio_construction_report,
)
from hunter.reporting_cli import CLIInvocation, run_render_sample_command
from hunter.research_audit_catalog import (
    CatalogConfig,
    CatalogEntry,
    build_research_audit_catalog,
)
from hunter.research_audit_closure import (
    AuditClosureConfig,
    AuditClosureFinding,
    build_research_audit_closure_report,
)
from hunter.research_audit_snapshot import (
    AuditSnapshotConfig,
    build_research_audit_snapshot,
)

from hunter.run_orchestrator.models import (
    EMPTY_RUN_ID,
    EMPTY_RUN_PLAN,
    FORBIDDEN_RUN_ORCHESTRATOR_TERMS,
    INVALID_OUTPUT_DIR,
    INVALID_RUN_CONFIG,
    INVALID_RUN_PLAN,
    INVALID_STEP_INPUTS,
    NETWORK_REFERENCE_DETECTED,
    NO_ACTION_COMMANDS_EMITTED,
    NO_DATABASE,
    NO_EXCHANGE_CONNECTION,
    NO_FILE_INGESTION,
    NO_FREQTRADE_INPUT,
    NO_NETWORK_CONNECTION,
    NO_SCHEDULER,
    NO_WEB_UI,
    NOT_TRADING_ADVICE,
    OK,
    PATH_TRAVERSAL_DETECTED,
    RESEARCH_ONLY,
    RUN_BLOCKED,
    RUN_ORCHESTRATOR_VERSION,
    ResearchRunArtifact,
    ResearchRunConfig,
    ResearchRunDataQuality,
    ResearchRunPlan,
    ResearchRunResult,
    ResearchRunSafetyFlags,
    ResearchRunState,
    ResearchRunStep,
    ResearchRunStepKind,
    ResearchRunStepResult,
    ResearchRunStepState,
    STEP_BLOCKED,
    STEP_FAILED,
    STEP_SKIPPED,
    UNSAFE_RUN_CONTENT,
    UNKNOWN_STEP_KIND,
    UNSUPPORTED_STEP_KIND,
    _coerce_mapping_any,
    _coerce_mapping_strs,
    _coerce_tuple_strs,
    _utc_now,
)


# ---------------------------------------------------------------------------
# Safety / path helpers
# ---------------------------------------------------------------------------


def _is_safe_local_path(value: str, cwd: str | None = None) -> tuple[bool, str]:
    """Validate a path string as a safe local path without filesystem access.

    This is a string-only validator. It does not open, read, follow, traverse,
    or execute the path. It mirrors the safe-local-path behavior used by the
    reporting CLI.
    """
    if not isinstance(value, str) or not value.strip():
        return False, "INVALID_PATH"

    # Reject network / URL-like strings.
    if "//" in value or "://" in value:
        return False, "NETWORK_REFERENCE_DETECTED"
    lower = value.lower()
    if lower.startswith(("http://", "https://", "ftp://", "ftps://", "sftp://")):
        return False, "NETWORK_REFERENCE_DETECTED"

    # Reject parent traversal segments. Normalization is string-only.
    normalized = os.path.normpath(value)
    parts = normalized.split(os.sep)
    if ".." in parts:
        return False, "PATH_TRAVERSAL_DETECTED"

    # Reject absolute paths outside the current working directory.
    if os.path.isabs(value):
        if cwd is None:
            cwd = os.getcwd()
        norm_cwd = os.path.normpath(cwd)
        norm_value = os.path.normpath(value)
        if norm_value != norm_cwd and not norm_value.startswith(norm_cwd + os.sep):
            return False, "INVALID_PATH"

    return True, ""


def _has_forbidden_terms(obj: Any) -> bool:
    """Return True if any string under obj contains a forbidden term.

    Only string values are inspected. Mappings and sequences are traversed
    shallowly. This is a content guard, not a semantic validator.
    """
    seen: set[int] = set()

    def _scan(value: Any) -> bool:
        obj_id = id(value)
        if obj_id in seen:
            return False
        seen.add(obj_id)

        if isinstance(value, str):
            lower = value.lower()
            for term in FORBIDDEN_RUN_ORCHESTRATOR_TERMS:
                if term in lower:
                    return True
            return False
        if isinstance(value, Mapping):
            for k, v in value.items():
                if _scan(k) or _scan(v):
                    return True
            return False
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                if _scan(item):
                    return True
            return False
        if is_dataclass(value):
            for field_name in value.__dataclass_fields__:
                if _scan(getattr(value, field_name)):
                    return True
            return False
        return False

    return _scan(obj)


# ---------------------------------------------------------------------------
# Plan validation
# ---------------------------------------------------------------------------


def _validate_plan(
    plan: ResearchRunPlan,
    config: ResearchRunConfig,
) -> tuple[bool, str, tuple[str, ...]]:
    """Validate plan and config without filesystem access.

    Returns (ok, reason, reason_codes). If not ok, the run is blocked.
    """
    reason_codes: list[str] = [RESEARCH_ONLY, NOT_TRADING_ADVICE]

    if not plan.run_id or not plan.run_id.strip():
        return False, "run_id must be non-empty", (EMPTY_RUN_ID, RUN_BLOCKED)

    if not isinstance(plan.steps, tuple) or len(plan.steps) == 0:
        return False, "plan must contain at least one step", (
            EMPTY_RUN_PLAN,
            RUN_BLOCKED,
        )

    for step in plan.steps:
        if not isinstance(step.kind, ResearchRunStepKind):
            return False, "step kind must be a ResearchRunStepKind", (
                UNKNOWN_STEP_KIND,
                RUN_BLOCKED,
            )
        if step.kind not in ResearchRunStepKind:
            return False, f"unsupported step kind: {step.kind}", (
                UNSUPPORTED_STEP_KIND,
                RUN_BLOCKED,
            )

    if _has_forbidden_terms(plan) or _has_forbidden_terms(config):
        return False, "forbidden content detected in plan or config", (
            UNSAFE_RUN_CONTENT,
            RUN_BLOCKED,
        )

    ok, reason = _is_safe_local_path(config.output_dir)
    if not ok:
        return False, f"invalid output_dir: {reason}", (INVALID_OUTPUT_DIR, reason, RUN_BLOCKED)

    return True, "", tuple(reason_codes)


# ---------------------------------------------------------------------------
# Step dispatch
# ---------------------------------------------------------------------------


def _build_step_output_dir(
    output_dir: str,
    step_index: int,
    step_kind: ResearchRunStepKind,
) -> str:
    """Return a deterministic local subdirectory for a step.

    The path is an opaque local string. No filesystem access is performed.
    """
    return str(Path(output_dir) / f"{step_index}_{step_kind.value}")


# Input-key contracts documented in the dispatch layer below.
# - BACKTEST: {"inputs": Sequence[BacktestInput], "config": BacktestRunConfig}
# - PORTFOLIO_CONSTRUCTION: {"inputs": Sequence[PortfolioConstructionInput], "config": PortfolioConstructionConfig}
# - DISCOVERY: {"inputs": Sequence[DiscoveryInput], "config": DiscoveryConfig}
# - REPORTING_CLI_SAMPLE: {"output_dir": str} (optional, default constructed)
# - AUDIT_SNAPSHOT_SUMMARY: {"artifact_summaries": Sequence[Mapping[str, Any]]}
# - AUDIT_CATALOG_SUMMARY: {"entries": Sequence[CatalogEntry]}
# - AUDIT_CLOSURE_SUMMARY: {"artifact_summaries": Sequence[Mapping[str, Any]]}


def _dispatch_step(
    step: ResearchRunStep,
    step_index: int,
    config: ResearchRunConfig,
) -> ResearchRunStepResult:
    """Dispatch a single step to an existing local engine.

    Returns a ResearchRunStepResult. No step dispatch reaches network, exchange,
    database, scheduler, daemon, or Freqtrade.
    """
    kind = step.kind
    inputs = step.inputs
    step_output_dir = _build_step_output_dir(config.output_dir, step_index, kind)
    generated_at = config.generated_at or _utc_now()

    try:
        if kind == ResearchRunStepKind.BACKTEST:
            step_inputs = tuple(inputs.get("inputs", ()))
            step_config = inputs.get("config") or BacktestRunConfig()
            if not step_inputs:
                return _step_blocked(
                    step_index,
                    step,
                    INVALID_STEP_INPUTS,
                    "backtest inputs missing",
                )
            report = build_backtest_report(
                step_inputs,
                step_config,
                report_id=step.step_id or f"backtest-{step_index}",
                generated_at=generated_at,
            )
            output_paths: tuple[str, ...] = ()
            if config.write_artifacts:
                json_path, csv_path, md_path = write_backtest_report(
                    report,
                    json_path=f"{step_output_dir}/backtest_report.json",
                    csv_path=f"{step_output_dir}/backtest_report.csv",
                    md_path=f"{step_output_dir}/backtest_report.md",
                )
                output_paths = tuple(
                    str(p) for p in (json_path, csv_path, md_path) if p is not None
                )
            return _step_success(
                step_index,
                step,
                {"report_id": report.report_id},
                output_paths,
            )

        if kind == ResearchRunStepKind.PORTFOLIO_CONSTRUCTION:
            step_inputs = tuple(inputs.get("inputs", ()))
            step_config = inputs.get("config") or PortfolioConstructionConfig()
            if not step_inputs:
                return _step_blocked(
                    step_index,
                    step,
                    INVALID_STEP_INPUTS,
                    "portfolio_construction inputs missing",
                )
            report = build_portfolio_construction_report(
                inputs=step_inputs,
                config=step_config,
                report_id=step.step_id or f"portfolio-construction-{step_index}",
                generated_at=generated_at,
            )
            output_paths = ()
            if config.write_artifacts:
                json_path, csv_path, md_path = write_portfolio_construction_report(
                    report,
                    json_path=f"{step_output_dir}/portfolio_construction_report.json",
                    csv_path=f"{step_output_dir}/portfolio_construction_report.csv",
                    md_path=f"{step_output_dir}/portfolio_construction_report.md",
                )
                output_paths = tuple(
                    str(p) for p in (json_path, csv_path, md_path) if p is not None
                )
            return _step_success(
                step_index,
                step,
                {"report_id": report.report_id},
                output_paths,
            )

        if kind == ResearchRunStepKind.DISCOVERY:
            step_inputs = tuple(inputs.get("inputs", ()))
            step_config = inputs.get("config") or DiscoveryConfig()
            if not step_inputs:
                return _step_blocked(
                    step_index,
                    step,
                    INVALID_STEP_INPUTS,
                    "discovery inputs missing",
                )
            report = build_discovery_report(
                inputs=step_inputs,
                config=step_config,
                report_id=step.step_id or f"discovery-{step_index}",
                generated_at=generated_at,
            )
            output_paths = ()
            if config.write_artifacts:
                json_path, csv_path, md_path = write_discovery_report(
                    report,
                    json_path=f"{step_output_dir}/discovery_report.json",
                    csv_path=f"{step_output_dir}/discovery_report.csv",
                    md_path=f"{step_output_dir}/discovery_report.md",
                )
                output_paths = tuple(
                    str(p) for p in (json_path, csv_path, md_path) if p is not None
                )
            return _step_success(
                step_index,
                step,
                {"report_id": report.report_id},
                output_paths,
            )

        if kind == ResearchRunStepKind.REPORTING_CLI_SAMPLE:
            sample_output_dir = inputs.get("output_dir") or step_output_dir
            invocation = CLIInvocation(
                command="render-sample",
                output_dir=sample_output_dir,
            )
            result = run_render_sample_command(invocation)
            state = (
                ResearchRunStepState.SUCCESS
                if result.exit_code.value == 0
                else ResearchRunStepState.FAILED
            )
            return ResearchRunStepResult(
                step_index=step_index,
                step_id=step.step_id,
                kind=kind,
                state=state,
                reason_codes=_coerce_tuple_strs(
                    result.reason_codes or (OK,),
                ),
                data=_coerce_mapping_any({
                    "exit_code": result.exit_code.value,
                    **dict(result.data),
                }),
                output_paths=result.output_paths,
                notes=result.notes,
                error_message=result.stderr if state != ResearchRunStepState.SUCCESS else "",
            )

        if kind == ResearchRunStepKind.AUDIT_SNAPSHOT_SUMMARY:
            artifact_summaries = tuple(inputs.get("artifact_summaries", ()))
            step_config = inputs.get("config") or AuditSnapshotConfig()
            snapshot = build_research_audit_snapshot(
                artifact_summaries=artifact_summaries,
                snapshot_id=step.step_id or f"snapshot-{step_index}",
                generated_at=generated_at,
                config=step_config,
            )
            return _step_success(
                step_index,
                step,
                {
                    "snapshot_id": snapshot.snapshot_id,
                    "reason_codes": tuple(snapshot.reason_codes),
                },
                (),
            )

        if kind == ResearchRunStepKind.AUDIT_CATALOG_SUMMARY:
            entries = tuple(inputs.get("entries", ()))
            step_config = inputs.get("config") or CatalogConfig()
            if not entries:
                return _step_blocked(
                    step_index,
                    step,
                    INVALID_STEP_INPUTS,
                    "audit catalog entries missing",
                )
            catalog = build_research_audit_catalog(
                entries=entries,
                catalog_id=step.step_id or f"catalog-{step_index}",
                generated_at=generated_at,
                config=step_config,
            )
            return _step_success(
                step_index,
                step,
                {
                    "catalog_id": catalog.catalog_id,
                    "catalog_state": catalog.catalog_state.value,
                },
                (),
            )

        if kind == ResearchRunStepKind.AUDIT_CLOSURE_SUMMARY:
            artifact_summaries = tuple(inputs.get("artifact_summaries", ()))
            step_config = inputs.get("config") or AuditClosureConfig()
            findings = tuple(inputs.get("findings", ()))
            report = build_research_audit_closure_report(
                artifact_summaries=artifact_summaries,
                closure_id=step.step_id or f"closure-{step_index}",
                generated_at=generated_at,
                config=step_config,
                findings=findings,
            )
            return _step_success(
                step_index,
                step,
                {"closure_id": report.closure_id, "state": report.closure_state.value},
                (),
            )

    except Exception as exc:  # noqa: BLE001
        return _step_failed(
            step_index,
            step,
            f"step execution error: {exc}",
        )

    return _step_blocked(
        step_index,
        step,
        UNSUPPORTED_STEP_KIND,
        f"unsupported step kind: {kind.value}",
    )


def _step_success(
    step_index: int,
    step: ResearchRunStep,
    data: Mapping[str, Any],
    output_paths: tuple[str, ...],
) -> ResearchRunStepResult:
    return ResearchRunStepResult(
        step_index=step_index,
        step_id=step.step_id,
        kind=step.kind,
        state=ResearchRunStepState.SUCCESS,
        reason_codes=(OK, RESEARCH_ONLY, NOT_TRADING_ADVICE),
        data=_coerce_mapping_any(data),
        output_paths=output_paths,
        notes=(),
    )


def _step_blocked(
    step_index: int,
    step: ResearchRunStep,
    reason_code: str,
    error_message: str,
) -> ResearchRunStepResult:
    return ResearchRunStepResult(
        step_index=step_index,
        step_id=step.step_id,
        kind=step.kind,
        state=ResearchRunStepState.BLOCKED,
        reason_codes=(reason_code, STEP_BLOCKED),
        data=_coerce_mapping_any({}),
        output_paths=(),
        notes=(),
        error_message=error_message,
    )


def _step_failed(
    step_index: int,
    step: ResearchRunStep,
    error_message: str,
) -> ResearchRunStepResult:
    return ResearchRunStepResult(
        step_index=step_index,
        step_id=step.step_id,
        kind=step.kind,
        state=ResearchRunStepState.FAILED,
        reason_codes=(STEP_FAILED,),
        data=_coerce_mapping_any({}),
        output_paths=(),
        notes=(),
        error_message=error_message,
    )


def _step_skipped(
    step_index: int,
    step: ResearchRunStep,
    reason: str = "prior step failed with fail_fast=True",
) -> ResearchRunStepResult:
    return ResearchRunStepResult(
        step_index=step_index,
        step_id=step.step_id,
        kind=step.kind,
        state=ResearchRunStepState.SKIPPED,
        reason_codes=(STEP_SKIPPED,),
        data=_coerce_mapping_any({"skip_reason": reason}),
        output_paths=(),
        notes=(),
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _build_artifacts(
    step_results: Sequence[ResearchRunStepResult],
) -> tuple[ResearchRunArtifact, ...]:
    """Build artifact references from step output paths."""
    artifacts: list[ResearchRunArtifact] = []
    for result in step_results:
        for path in result.output_paths:
            artifacts.append(
                ResearchRunArtifact(
                    step_index=result.step_index,
                    step_id=result.step_id,
                    kind=result.kind.value,
                    path=path,
                )
            )
    return tuple(artifacts)


def _build_data_quality(
    step_results: Sequence[ResearchRunStepResult],
) -> ResearchRunDataQuality:
    """Aggregate data quality from step results."""
    total = len(step_results)
    successful = sum(1 for r in step_results if r.state == ResearchRunStepState.SUCCESS)
    failed = sum(1 for r in step_results if r.state == ResearchRunStepState.FAILED)
    blocked = sum(1 for r in step_results if r.state == ResearchRunStepState.BLOCKED)
    skipped = sum(1 for r in step_results if r.state == ResearchRunStepState.SKIPPED)
    sections_expected = ["RUN_ID", "STEPS", "DATA_QUALITY", "SAFETY_FLAGS"]
    sections_present = ["RUN_ID", "STEPS", "DATA_QUALITY", "SAFETY_FLAGS"]
    if total > 0:
        sections_present.append("STEP_STATES")
    notes = [f"Run executed {total} step(s): {successful} success, {failed} failed, {blocked} blocked, {skipped} skipped."]
    return ResearchRunDataQuality(
        total_steps=total,
        successful_steps=successful,
        failed_steps=failed,
        blocked_steps=blocked,
        skipped_steps=skipped,
        sections_present=tuple(sections_present),
        sections_expected=tuple(sections_expected),
        notes=tuple(notes),
    )


def _build_safety_flags(
    step_results: Sequence[ResearchRunStepResult],
    plan_blocked: bool,
    unsafe_content: bool,
    traversal: bool,
    network_reference: bool,
) -> ResearchRunSafetyFlags:
    """Build safety flags from run state."""
    has_failed = any(r.state == ResearchRunStepState.FAILED for r in step_results)
    has_blocked = any(r.state == ResearchRunStepState.BLOCKED for r in step_results)
    has_invalid = plan_blocked or has_blocked
    return ResearchRunSafetyFlags(
        has_failed_step=has_failed,
        has_blocked_step=has_blocked,
        has_invalid_step=has_invalid,
        has_unsafe_content=unsafe_content,
        has_traversal_attempt=traversal,
        has_network_reference=network_reference,
    )


def _build_reason_codes(
    step_results: Sequence[ResearchRunStepResult],
    base_reason_codes: Sequence[str],
) -> tuple[str, ...]:
    """Aggregate reason codes from the run and all steps, deduplicated and sorted."""
    codes: set[str] = set(base_reason_codes)
    for result in step_results:
        codes.update(result.reason_codes)
    return tuple(sorted(codes))


def _build_run_state(
    step_results: Sequence[ResearchRunStepResult],
    plan_blocked: bool,
) -> ResearchRunState:
    """Determine the overall run state from step results."""
    if plan_blocked:
        return ResearchRunState.BLOCKED
    states = [r.state for r in step_results]
    if all(s == ResearchRunStepState.SUCCESS for s in states):
        return ResearchRunState.COMPLETED
    if all(s == ResearchRunStepState.FAILED for s in states):
        return ResearchRunState.FAILED
    if all(s in (ResearchRunStepState.BLOCKED, ResearchRunStepState.SKIPPED) for s in states):
        return ResearchRunState.BLOCKED
    return ResearchRunState.PARTIAL


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_research_run_result(
    plan: ResearchRunPlan,
    config: ResearchRunConfig | None = None,
) -> ResearchRunResult:
    """Execute a deterministic local research run and return the result.

    The orchestrator validates the plan, executes each step in order against the
    appropriate existing local engine, aggregates results, and returns a
    ResearchRunResult. No network, exchange, database, scheduler, daemon, or
    trading runtime is invoked.
    """
    config = config or ResearchRunConfig()
    generated_at = config.generated_at or _utc_now()
    base_reason_codes = [
        RESEARCH_ONLY,
        NOT_TRADING_ADVICE,
        NO_FILE_INGESTION,
        NO_NETWORK_CONNECTION,
        NO_EXCHANGE_CONNECTION,
        NO_FREQTRADE_INPUT,
        NO_SCHEDULER,
        NO_WEB_UI,
        NO_DATABASE,
        NO_ACTION_COMMANDS_EMITTED,
    ]

    ok, message, validation_codes = _validate_plan(plan, config)
    if not ok:
        safety_flags = _build_safety_flags(
            step_results=(),
            plan_blocked=True,
            unsafe_content=UNSAFE_RUN_CONTENT in validation_codes,
            traversal=PATH_TRAVERSAL_DETECTED in validation_codes,
            network_reference=NETWORK_REFERENCE_DETECTED in validation_codes,
        )
        data_quality = ResearchRunDataQuality(
            notes=(f"Run blocked: {message}",),
        )
        reason_codes = _build_reason_codes((), validation_codes)
        return ResearchRunResult(
            run_id=plan.run_id,
            config=config,
            plan=plan,
            steps=(),
            artifacts=(),
            data_quality=data_quality,
            safety_flags=safety_flags,
            reason_codes=reason_codes,
            generated_at=generated_at,
            state=ResearchRunState.BLOCKED,
            metadata=_coerce_mapping_strs(plan.metadata),
            notes=(f"Run blocked: {message}",),
        )

    step_results: list[ResearchRunStepResult] = []
    fail_fast = config.fail_fast

    for step_index, step in enumerate(plan.steps):
        if fail_fast and any(
            r.state in (ResearchRunStepState.FAILED, ResearchRunStepState.BLOCKED)
            for r in step_results
        ):
            step_results.append(_step_skipped(step_index, step))
            continue

        result = _dispatch_step(step, step_index, config)
        step_results.append(result)

    step_results_tuple = tuple(step_results)
    artifacts = _build_artifacts(step_results_tuple)
    data_quality = _build_data_quality(step_results_tuple)
    safety_flags = _build_safety_flags(
        step_results=step_results_tuple,
        plan_blocked=False,
        unsafe_content=False,
        traversal=False,
        network_reference=False,
    )
    reason_codes = _build_reason_codes(step_results_tuple, base_reason_codes)
    state = _build_run_state(step_results_tuple, plan_blocked=False)
    notes = (data_quality.notes[0] if data_quality.notes else "",)

    return ResearchRunResult(
        run_id=plan.run_id,
        config=config,
        plan=plan,
        steps=step_results_tuple,
        artifacts=artifacts,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        generated_at=generated_at,
        state=state,
        metadata=_coerce_mapping_strs(plan.metadata),
        notes=notes,
    )
