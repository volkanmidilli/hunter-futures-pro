"""In-memory engine for hunter.cross_pack_consistency package.

MVP-36 — Local Research Cross-Pack Consistency Validator.

The engine receives only caller-provided in-memory input. It never inspects the
filesystem, imports prior packages, or traverses any path or reference string.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from json import dumps
from typing import Any

from hunter.cross_pack_consistency.models import (
    FORBIDDEN_CROSS_PACK_CONSISTENCY_TERMS,
    CrossPackArtifactRef,
    CrossPackConsistencyConfig,
    CrossPackConsistencyDataQuality,
    CrossPackConsistencyIssue,
    CrossPackConsistencyIssueType,
    CrossPackConsistencyReasonCode,
    CrossPackConsistencyReport,
    CrossPackConsistencyRule,
    CrossPackConsistencyRuleType,
    CrossPackConsistencySafetyFlags,
    CrossPackConsistencySeverity,
    CrossPackConsistencyState,
    CrossPackDeclaration,
    CrossPackRequirementRef,
    CrossPackSectionRef,
    CrossPackStateClaim,
    CrossPackConsistencyInput,
    _has_forbidden_term,
    _has_forbidden_terms_in_text_fields,
    has_unsafe_cross_pack_consistency_content,
)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _norm_id(value: str | None) -> str:
    """Normalize an ID: strip whitespace and lower-case."""
    if value is None:
        return ""
    return value.strip().lower()


def _norm_state(value: str | None) -> str:
    """Normalize a state label for comparison: strip and lower-case."""
    if value is None:
        return ""
    return value.strip().lower()


def _resolve_project_version(input: CrossPackConsistencyInput) -> str:
    """Resolve project_version per SPEC precedence."""
    return input.project_version or input.config.project_version or ""


def _is_truly_empty(input: CrossPackConsistencyInput) -> bool:
    """Return True when the input has no declarations, refs, claims, or rules."""
    return (
        not input.declarations
        and not input.artifact_refs
        and not input.section_refs
        and not input.requirement_refs
        and not input.state_claims
        and not input.rules
    )


def _build_report_id(
    input: CrossPackConsistencyInput,
    generated_at: datetime,
) -> str:
    """Return a deterministic report_id from sorted IDs. No path opening."""
    payload = {
        "pack_ids": sorted(_norm_id(d.pack_id) for d in input.declarations),
        "artifact_ref_ids": sorted(_norm_id(r.ref_id) for r in input.artifact_refs),
        "section_ref_ids": sorted(_norm_id(r.ref_id) for r in input.section_refs),
        "requirement_ref_ids": sorted(_norm_id(r.ref_id) for r in input.requirement_refs),
        "subject_ids": sorted(_norm_id(c.subject_id) for c in input.state_claims),
        "rule_ids": sorted(_norm_id(r.source_pack_id) for r in input.rules),
        "project_version": _resolve_project_version(input),
        "generated_at": generated_at.isoformat(),
    }
    canonical = dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"cross_pack_consistency_{sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def _build_issue_id(
    issue_type: CrossPackConsistencyIssueType,
    severity: CrossPackConsistencySeverity,
    subject_id: str,
    source_pack_id: str,
    target_pack_id: str,
    reason_codes: tuple[CrossPackConsistencyReasonCode, ...],
    message: str,
) -> str:
    """Return a deterministic issue_id from normalized issue content."""
    sorted_reasons = ",".join(sorted(code.value for code in reason_codes))
    content = (
        f"{issue_type.value}|{severity.value}|{_norm_id(subject_id)}|"
        f"{_norm_id(source_pack_id)}|{_norm_id(target_pack_id)}|"
        f"{sorted_reasons}|{_norm_id(message)}"
    )
    return sha256(content.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Issue builders
# ---------------------------------------------------------------------------


def _issue(
    issue_type: CrossPackConsistencyIssueType,
    severity: CrossPackConsistencySeverity,
    subject_id: str,
    source_pack_id: str,
    target_pack_id: str = "",
    reason_codes: tuple[CrossPackConsistencyReasonCode, ...] = (),
    message: str = "",
) -> CrossPackConsistencyIssue:
    """Build a CrossPackConsistencyIssue with a deterministic issue_id."""
    issue_id = _build_issue_id(
        issue_type=issue_type,
        severity=severity,
        subject_id=subject_id,
        source_pack_id=source_pack_id,
        target_pack_id=target_pack_id,
        reason_codes=reason_codes,
        message=message,
    )
    return CrossPackConsistencyIssue(
        issue_id=issue_id,
        issue_type=issue_type,
        severity=severity,
        subject_id=subject_id,
        source_pack_id=source_pack_id,
        target_pack_id=target_pack_id,
        reason_codes=reason_codes,
        message=message,
    )


def _evaluate_rule(
    *,
    rule: CrossPackConsistencyRule,
    input: CrossPackConsistencyInput,
    pack_by_id: dict[str, CrossPackDeclaration],
    artifact_by_id: dict[str, CrossPackArtifactRef],
    section_by_id: dict[str, CrossPackSectionRef],
    requirement_by_id: dict[str, CrossPackRequirementRef],
    state_claims_by_subject: dict[str, list[CrossPackStateClaim]],
    generated_at: datetime,
    issues: list[CrossPackConsistencyIssue],
) -> None:
    """Evaluate a single rule-driven check."""
    source_norm = _norm_id(rule.source_pack_id)
    target_norm = _norm_id(rule.target_pack_id) if rule.target_pack_id else None
    subject_norm = _norm_id(rule.subject_id) if rule.subject_id else None
    severity = rule.severity

    if rule.rule_type == CrossPackConsistencyRuleType.REQUIRED_PACK:
        if source_norm and source_norm not in pack_by_id:
            issues.append(_issue(
                issue_type=CrossPackConsistencyIssueType.MISSING_REQUIRED_PACK,
                severity=severity,
                subject_id=source_norm,
                source_pack_id=source_norm,
                reason_codes=(CrossPackConsistencyReasonCode.MISSING_REQUIRED_PACK,),
                message=rule.message or f"rule requires pack '{rule.source_pack_id}'",
            ))

    elif rule.rule_type == CrossPackConsistencyRuleType.EXPECTED_REF:
        if source_norm and source_norm in pack_by_id:
            declaration = pack_by_id[source_norm]
            ref_id = _norm_id(rule.ref_id) if rule.ref_id else None
            ref_kind = _norm_id(rule.ref_kind) if rule.ref_kind else None
            if ref_id and ref_kind == "artifact" and ref_id not in artifact_by_id:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.MISSING_EXPECTED_REF,
                    severity=severity,
                    subject_id=ref_id,
                    source_pack_id=source_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.MISSING_EXPECTED_ARTIFACT_REF,),
                    message=rule.message or f"missing expected artifact ref '{rule.ref_id}'",
                ))
            elif ref_id and ref_kind == "section" and ref_id not in section_by_id:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.MISSING_EXPECTED_REF,
                    severity=severity,
                    subject_id=ref_id,
                    source_pack_id=source_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.MISSING_EXPECTED_SECTION_REF,),
                    message=rule.message or f"missing expected section ref '{rule.ref_id}'",
                ))
            elif ref_id and ref_kind == "requirement" and ref_id not in requirement_by_id:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.MISSING_EXPECTED_REF,
                    severity=severity,
                    subject_id=ref_id,
                    source_pack_id=source_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.MISSING_EXPECTED_REQUIREMENT_REF,),
                    message=rule.message or f"missing expected requirement ref '{rule.ref_id}'",
                ))

    elif rule.rule_type == CrossPackConsistencyRuleType.COMPATIBLE_VERSION:
        if source_norm and source_norm in pack_by_id:
            source_pack = pack_by_id[source_norm]
            expected = rule.expected_version
            if target_norm and target_norm in pack_by_id:
                target_pack = pack_by_id[target_norm]
                if source_pack.version != target_pack.version:
                    issues.append(_issue(
                        issue_type=CrossPackConsistencyIssueType.INCOMPATIBLE_VERSION,
                        severity=severity,
                        subject_id=source_norm,
                        source_pack_id=source_norm,
                        target_pack_id=target_norm,
                        reason_codes=(CrossPackConsistencyReasonCode.INCOMPATIBLE_VERSION,),
                        message=rule.message or f"version mismatch: {source_pack.version} vs {target_pack.version}",
                    ))
            elif expected is not None and source_pack.version != expected:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.INCOMPATIBLE_VERSION,
                    severity=severity,
                    subject_id=source_norm,
                    source_pack_id=source_norm,
                    target_pack_id=target_norm or "",
                    reason_codes=(CrossPackConsistencyReasonCode.INCOMPATIBLE_VERSION,),
                    message=rule.message or f"version mismatch: {source_pack.version} vs expected {expected}",
                ))

    elif rule.rule_type == CrossPackConsistencyRuleType.STALE_DECLARATION:
        if source_norm and source_norm in pack_by_id:
            declaration = pack_by_id[source_norm]
            if declaration.generated_at is not None:
                age = generated_at - declaration.generated_at
                if age.total_seconds() > input.config.staleness_threshold_seconds:
                    issues.append(_issue(
                        issue_type=CrossPackConsistencyIssueType.STALE_DECLARATION,
                        severity=severity,
                        subject_id=source_norm,
                        source_pack_id=source_norm,
                        reason_codes=(CrossPackConsistencyReasonCode.STALE_PACK_DECLARATION,),
                        message=rule.message or f"pack '{rule.source_pack_id}' is stale",
                    ))

    elif rule.rule_type == CrossPackConsistencyRuleType.COMPATIBLE_STATE:
        if source_norm and source_norm in pack_by_id:
            source_state = _norm_state(pack_by_id[source_norm].declared_state)
            forbidden = {_norm_state(s) for s in rule.forbidden_states}
            if source_state and forbidden and source_state in forbidden:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.INCOMPATIBLE_STATE_COMBINATION,
                    severity=severity,
                    subject_id=source_norm,
                    source_pack_id=source_norm,
                    target_pack_id=target_norm or "",
                    reason_codes=(CrossPackConsistencyReasonCode.INCOMPATIBLE_STATE_COMBINATION,),
                    message=rule.message or f"pack '{rule.source_pack_id}' has forbidden state",
                ))
        if target_norm and target_norm in pack_by_id:
            target_state = _norm_state(pack_by_id[target_norm].declared_state)
            forbidden = {_norm_state(s) for s in rule.forbidden_states}
            expected = _norm_state(rule.expected_state) if rule.expected_state else None
            if target_state and forbidden and target_state in forbidden:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.INCOMPATIBLE_STATE_COMBINATION,
                    severity=severity,
                    subject_id=target_norm,
                    source_pack_id=source_norm,
                    target_pack_id=target_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.INCOMPATIBLE_STATE_COMBINATION,),
                    message=rule.message or f"pack '{rule.target_pack_id}' has forbidden state",
                ))
            if expected is not None and target_state != expected:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.INCOMPATIBLE_STATE_COMBINATION,
                    severity=severity,
                    subject_id=target_norm,
                    source_pack_id=source_norm,
                    target_pack_id=target_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.INCOMPATIBLE_STATE_COMBINATION,),
                    message=rule.message or f"pack '{rule.target_pack_id}' expected state '{rule.expected_state}'",
                ))
        if subject_norm and subject_norm in state_claims_by_subject:
            forbidden = {_norm_state(s) for s in rule.forbidden_states}
            for claim in state_claims_by_subject[subject_norm]:
                claim_state = _norm_state(claim.state_label)
                if claim_state and forbidden and claim_state in forbidden:
                    issues.append(_issue(
                        issue_type=CrossPackConsistencyIssueType.INCOMPATIBLE_STATE_COMBINATION,
                        severity=severity,
                        subject_id=subject_norm,
                        source_pack_id=source_norm,
                        target_pack_id=_norm_id(claim.pack_id),
                        reason_codes=(CrossPackConsistencyReasonCode.INCOMPATIBLE_STATE_COMBINATION,),
                        message=rule.message or f"subject '{rule.subject_id}' has forbidden state",
                    ))

    elif rule.rule_type == CrossPackConsistencyRuleType.CONFLICTING_STATE:
        if subject_norm and subject_norm in state_claims_by_subject:
            claims = state_claims_by_subject[subject_norm]
            labels = {_norm_state(c.state_label) for c in claims}
            if len(labels) > 1:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.CONFLICTING_STATE,
                    severity=severity,
                    subject_id=subject_norm,
                    source_pack_id=source_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.CONFLICTING_STATE_CLAIM,),
                    message=rule.message or f"conflicting state claims for subject '{rule.subject_id}'",
                ))

    elif rule.rule_type == CrossPackConsistencyRuleType.MANUAL_REVIEW:
        if source_norm and source_norm in pack_by_id:
            declaration = pack_by_id[source_norm]
            if not declaration.requires_manual_review:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.MISSING_MANUAL_REVIEW,
                    severity=severity,
                    subject_id=source_norm,
                    source_pack_id=source_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.MISSING_MANUAL_REVIEW,),
                    message=rule.message or f"pack '{rule.source_pack_id}' requires manual review",
                ))

    elif rule.rule_type == CrossPackConsistencyRuleType.UNKNOWN_STATE:
        if subject_norm and subject_norm in state_claims_by_subject:
            allowed = {_norm_state(s) for s in rule.forbidden_states}
            for claim in state_claims_by_subject[subject_norm]:
                claim_state = _norm_state(claim.state_label)
                if claim_state and allowed and claim_state not in allowed:
                    issues.append(_issue(
                        issue_type=CrossPackConsistencyIssueType.UNKNOWN_UPSTREAM_STATE,
                        severity=severity,
                        subject_id=subject_norm,
                        source_pack_id=source_norm,
                        target_pack_id=_norm_id(claim.pack_id),
                        reason_codes=(CrossPackConsistencyReasonCode.UNKNOWN_UPSTREAM_STATE,),
                        message=rule.message or f"subject '{rule.subject_id}' has unknown state",
                    ))


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------


def build_cross_pack_consistency_report(
    inp: CrossPackConsistencyInput,
) -> CrossPackConsistencyReport:
    """Build a deterministic cross-pack consistency report from caller input."""
    if inp.generated_at is not None:
        generated_at = inp.generated_at
    else:
        generated_at = datetime.now(timezone.utc)

    forbidden_terms = frozenset(inp.config.forbidden_terms)
    issues: list[CrossPackConsistencyIssue] = []
    safety_flags = CrossPackConsistencySafetyFlags()

    # 2. Safety checks run first.
    if has_unsafe_cross_pack_consistency_content(inp.metadata):
        safety_flags = CrossPackConsistencySafetyFlags(has_unsafe_content=True)
        issues.append(_issue(
            issue_type=CrossPackConsistencyIssueType.UNSAFE_CONTENT,
            severity=CrossPackConsistencySeverity.BLOCKING,
            subject_id="metadata",
            source_pack_id="",
            reason_codes=(CrossPackConsistencyReasonCode.UNSAFE_CONTENT,),
            message="metadata contains unsafe non-string values",
        ))

    offenders = _has_forbidden_terms_in_text_fields(
        declarations=inp.declarations,
        artifact_refs=inp.artifact_refs,
        section_refs=inp.section_refs,
        requirement_refs=inp.requirement_refs,
        state_claims=inp.state_claims,
        rules=inp.rules,
        forbidden_terms=forbidden_terms,
    )
    if offenders:
        safety_flags = CrossPackConsistencySafetyFlags(has_forbidden_terms=True)
        issues.append(_issue(
            issue_type=CrossPackConsistencyIssueType.UNSAFE_CONTENT,
            severity=CrossPackConsistencySeverity.BLOCKING,
            subject_id="forbidden_terms",
            source_pack_id="",
            reason_codes=(CrossPackConsistencyReasonCode.FORBIDDEN_TERM_PRESENT,),
            message=f"forbidden terms found in caller-provided text fields",
        ))

    # 1. Normalized lookups.
    pack_by_id: dict[str, CrossPackDeclaration] = {}
    for declaration in inp.declarations:
        norm = _norm_id(declaration.pack_id)
        if norm:
            pack_by_id[norm] = declaration

    artifact_by_id: dict[str, CrossPackArtifactRef] = {}
    for ref in inp.artifact_refs:
        norm = _norm_id(ref.ref_id)
        if norm:
            artifact_by_id[norm] = ref

    section_by_id: dict[str, CrossPackSectionRef] = {}
    for ref in inp.section_refs:
        norm = _norm_id(ref.ref_id)
        if norm:
            section_by_id[norm] = ref

    requirement_by_id: dict[str, CrossPackRequirementRef] = {}
    for ref in inp.requirement_refs:
        norm = _norm_id(ref.ref_id)
        if norm:
            requirement_by_id[norm] = ref

    state_claims_by_subject: dict[str, list[CrossPackStateClaim]] = defaultdict(list)
    for claim in inp.state_claims:
        norm = _norm_id(claim.subject_id)
        if norm:
            state_claims_by_subject[norm].append(claim)

    # 3. Duplicate ID detection.
    duplicate_reason_counts: dict[str, int] = defaultdict(int)
    seen_pack_ids: set[str] = set()
    for declaration in inp.declarations:
        norm = _norm_id(declaration.pack_id)
        if norm and norm in seen_pack_ids:
            duplicate_reason_counts["pack"] += 1
        elif norm:
            seen_pack_ids.add(norm)

    seen_artifact_ids: set[str] = set()
    for ref in inp.artifact_refs:
        norm = _norm_id(ref.ref_id)
        if norm and norm in seen_artifact_ids:
            duplicate_reason_counts["artifact"] += 1
        elif norm:
            seen_artifact_ids.add(norm)

    seen_section_ids: set[str] = set()
    for ref in inp.section_refs:
        norm = _norm_id(ref.ref_id)
        if norm and norm in seen_section_ids:
            duplicate_reason_counts["section"] += 1
        elif norm:
            seen_section_ids.add(norm)

    seen_requirement_ids: set[str] = set()
    for ref in inp.requirement_refs:
        norm = _norm_id(ref.ref_id)
        if norm and norm in seen_requirement_ids:
            duplicate_reason_counts["requirement"] += 1
        elif norm:
            seen_requirement_ids.add(norm)

    if duplicate_reason_counts.get("pack", 0) > 0:
        issues.append(_issue(
            issue_type=CrossPackConsistencyIssueType.DUPLICATE_ID,
            severity=CrossPackConsistencySeverity.BLOCKING,
            subject_id="duplicate_pack_id",
            source_pack_id="",
            reason_codes=(CrossPackConsistencyReasonCode.DUPLICATE_PACK_ID,),
            message=f"{duplicate_reason_counts['pack']} duplicate pack ID(s) detected",
        ))
    if duplicate_reason_counts.get("artifact", 0) > 0:
        issues.append(_issue(
            issue_type=CrossPackConsistencyIssueType.DUPLICATE_ID,
            severity=CrossPackConsistencySeverity.ADVISORY,
            subject_id="duplicate_artifact_id",
            source_pack_id="",
            reason_codes=(CrossPackConsistencyReasonCode.DUPLICATE_ARTIFACT_ID,),
            message=f"{duplicate_reason_counts['artifact']} duplicate artifact ref ID(s) detected",
        ))
    if duplicate_reason_counts.get("section", 0) > 0:
        issues.append(_issue(
            issue_type=CrossPackConsistencyIssueType.DUPLICATE_ID,
            severity=CrossPackConsistencySeverity.ADVISORY,
            subject_id="duplicate_section_id",
            source_pack_id="",
            reason_codes=(CrossPackConsistencyReasonCode.DUPLICATE_SECTION_ID,),
            message=f"{duplicate_reason_counts['section']} duplicate section ref ID(s) detected",
        ))
    if duplicate_reason_counts.get("requirement", 0) > 0:
        issues.append(_issue(
            issue_type=CrossPackConsistencyIssueType.DUPLICATE_ID,
            severity=CrossPackConsistencySeverity.ADVISORY,
            subject_id="duplicate_requirement_id",
            source_pack_id="",
            reason_codes=(CrossPackConsistencyReasonCode.DUPLICATE_REQUIREMENT_ID,),
            message=f"{duplicate_reason_counts['requirement']} duplicate requirement ref ID(s) detected",
        ))

    # 4. Required packs.
    for required_pack_id in inp.config.required_pack_ids:
        norm = _norm_id(required_pack_id)
        if not norm:
            continue
        if norm not in pack_by_id:
            issues.append(_issue(
                issue_type=CrossPackConsistencyIssueType.MISSING_REQUIRED_PACK,
                severity=CrossPackConsistencySeverity.BLOCKING,
                subject_id=norm,
                source_pack_id=norm,
                reason_codes=(CrossPackConsistencyReasonCode.MISSING_REQUIRED_PACK,),
                message=f"required pack '{required_pack_id}' is missing",
            ))

    # 5. Expected refs (BLOCKING per SPEC).
    expected_artifact_ids: set[str] = set()
    expected_section_ids: set[str] = set()
    expected_requirement_ids: set[str] = set()
    for declaration in inp.declarations:
        pack_norm = _norm_id(declaration.pack_id)
        for ref_id in declaration.artifact_ref_ids:
            norm = _norm_id(ref_id)
            if norm:
                expected_artifact_ids.add(norm)
            if norm and norm not in artifact_by_id:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.MISSING_EXPECTED_REF,
                    severity=CrossPackConsistencySeverity.BLOCKING,
                    subject_id=norm,
                    source_pack_id=pack_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.MISSING_EXPECTED_ARTIFACT_REF,),
                    message=f"missing expected artifact ref '{ref_id}' in pack '{declaration.pack_id}'",
                ))
        for ref_id in declaration.section_ref_ids:
            norm = _norm_id(ref_id)
            if norm:
                expected_section_ids.add(norm)
            if norm and norm not in section_by_id:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.MISSING_EXPECTED_REF,
                    severity=CrossPackConsistencySeverity.BLOCKING,
                    subject_id=norm,
                    source_pack_id=pack_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.MISSING_EXPECTED_SECTION_REF,),
                    message=f"missing expected section ref '{ref_id}' in pack '{declaration.pack_id}'",
                ))
        for ref_id in declaration.requirement_ref_ids:
            norm = _norm_id(ref_id)
            if norm:
                expected_requirement_ids.add(norm)
            if norm and norm not in requirement_by_id:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.MISSING_EXPECTED_REF,
                    severity=CrossPackConsistencySeverity.BLOCKING,
                    subject_id=norm,
                    source_pack_id=pack_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.MISSING_EXPECTED_REQUIREMENT_REF,),
                    message=f"missing expected requirement ref '{ref_id}' in pack '{declaration.pack_id}'",
                ))

    # 6. Orphan refs.
    for ref in inp.artifact_refs:
        ref_norm = _norm_id(ref.ref_id)
        if ref_norm and ref_norm not in expected_artifact_ids:
            issues.append(_issue(
                issue_type=CrossPackConsistencyIssueType.ORPHAN_REF,
                severity=CrossPackConsistencySeverity.ADVISORY,
                subject_id=ref_norm,
                source_pack_id=_norm_id(ref.pack_id),
                reason_codes=(CrossPackConsistencyReasonCode.ORPHAN_ARTIFACT_REF,),
                message=f"artifact ref '{ref.ref_id}' is not expected by any declaration",
            ))
    for ref in inp.section_refs:
        ref_norm = _norm_id(ref.ref_id)
        if ref_norm and ref_norm not in expected_section_ids:
            issues.append(_issue(
                issue_type=CrossPackConsistencyIssueType.ORPHAN_REF,
                severity=CrossPackConsistencySeverity.ADVISORY,
                subject_id=ref_norm,
                source_pack_id=_norm_id(ref.pack_id),
                reason_codes=(CrossPackConsistencyReasonCode.ORPHAN_SECTION_REF,),
                message=f"section ref '{ref.ref_id}' is not expected by any declaration",
            ))
    for ref in inp.requirement_refs:
        ref_norm = _norm_id(ref.ref_id)
        if ref_norm and ref_norm not in expected_requirement_ids:
            issues.append(_issue(
                issue_type=CrossPackConsistencyIssueType.ORPHAN_REF,
                severity=CrossPackConsistencySeverity.ADVISORY,
                subject_id=ref_norm,
                source_pack_id=_norm_id(ref.pack_id),
                reason_codes=(CrossPackConsistencyReasonCode.ORPHAN_REQUIREMENT_REF,),
                message=f"requirement ref '{ref.ref_id}' is not expected by any declaration",
            ))

    # 7. Unknown declaration states (built-in, per config.allowed_state_labels).
    allowed_labels = {_norm_id(label) for label in inp.config.allowed_state_labels}
    if allowed_labels:
        for declaration in inp.declarations:
            pack_norm = _norm_id(declaration.pack_id)
            norm_state = _norm_state(declaration.declared_state)
            if norm_state and norm_state not in allowed_labels:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.UNKNOWN_UPSTREAM_STATE,
                    severity=CrossPackConsistencySeverity.ADVISORY,
                    subject_id=pack_norm,
                    source_pack_id=pack_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.UNKNOWN_UPSTREAM_STATE,),
                    message=f"unknown declared state '{declaration.declared_state}' for pack '{declaration.pack_id}'",
                ))

    # 8. Staleness (built-in).
    threshold = inp.config.staleness_threshold_seconds
    for declaration in inp.declarations:
        if declaration.generated_at is not None:
            age = generated_at - declaration.generated_at
            if age.total_seconds() > threshold:
                pack_norm = _norm_id(declaration.pack_id)
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.STALE_DECLARATION,
                    severity=CrossPackConsistencySeverity.ADVISORY,
                    subject_id=pack_norm,
                    source_pack_id=pack_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.STALE_PACK_DECLARATION,),
                    message=f"pack '{declaration.pack_id}' declaration is stale",
                ))

    # 10. Conflicting state claims and unknown upstream states.
    allowed_labels = {_norm_id(label) for label in inp.config.allowed_state_labels}
    for subject_id, claims in state_claims_by_subject.items():
        labels = {_norm_state(c.state_label) for c in claims}
        if len(labels) > 1:
            severity = CrossPackConsistencySeverity.ADVISORY
            if "blocked" in labels or "missing" in labels:
                severity = CrossPackConsistencySeverity.BLOCKING
            issues.append(_issue(
                issue_type=CrossPackConsistencyIssueType.CONFLICTING_STATE,
                severity=severity,
                subject_id=subject_id,
                source_pack_id=_norm_id(claims[0].pack_id),
                reason_codes=(CrossPackConsistencyReasonCode.CONFLICTING_STATE_CLAIM,),
                message=f"conflicting state claims for subject '{subject_id}'",
            ))
        if allowed_labels:
            for claim in claims:
                norm_label = _norm_state(claim.state_label)
                if norm_label and norm_label not in allowed_labels:
                    issues.append(_issue(
                        issue_type=CrossPackConsistencyIssueType.UNKNOWN_UPSTREAM_STATE,
                        severity=CrossPackConsistencySeverity.ADVISORY,
                        subject_id=subject_id,
                        source_pack_id=_norm_id(claim.pack_id),
                        reason_codes=(CrossPackConsistencyReasonCode.UNKNOWN_UPSTREAM_STATE,),
                        message=f"unknown upstream state '{claim.state_label}' for subject '{subject_id}'",
                    ))

    # 11. Missing manual review.
    for declaration in inp.declarations:
        if declaration.requires_manual_review:
            pack_norm = _norm_id(declaration.pack_id)
            has_manual_review_claim = any(
                _norm_id(c.pack_id) == pack_norm and _norm_state(c.state_label) == "manually_reviewed"
                for c in inp.state_claims
            )
            if not has_manual_review_claim:
                issues.append(_issue(
                    issue_type=CrossPackConsistencyIssueType.MISSING_MANUAL_REVIEW,
                    severity=CrossPackConsistencySeverity.ADVISORY,
                    subject_id=pack_norm,
                    source_pack_id=pack_norm,
                    reason_codes=(CrossPackConsistencyReasonCode.MISSING_MANUAL_REVIEW,),
                    message=f"pack '{declaration.pack_id}' requires manual review",
                ))

    # 12. Rule-driven checks.
    for rule in inp.rules:
        _evaluate_rule(
            rule=rule,
            input=inp,
            pack_by_id=pack_by_id,
            artifact_by_id=artifact_by_id,
            section_by_id=section_by_id,
            requirement_by_id=requirement_by_id,
            state_claims_by_subject=state_claims_by_subject,
            generated_at=generated_at,
            issues=issues,
        )

    # 15. Deduplicate issues. First by deterministic content hash (issue_id).
    # Then by (issue_type, subject, source, target) to collapse any built-in + rule-driven overlap.
    unique_by_id: dict[str, CrossPackConsistencyIssue] = {}
    for issue in issues:
        unique_by_id.setdefault(issue.issue_id, issue)
    issues = list(unique_by_id.values())
    unique_by_subject: dict[
        tuple[str, str, str, str], CrossPackConsistencyIssue
    ] = {}
    for issue in issues:
        key = (
            issue.issue_type.value,
            _norm_id(issue.subject_id),
            _norm_id(issue.source_pack_id),
            _norm_id(issue.target_pack_id),
        )
        unique_by_subject.setdefault(key, issue)
    issues = list(unique_by_subject.values())

    # 13. Aggregate overall state.
    if safety_flags.has_unsafe_content or safety_flags.has_forbidden_terms:
        state = CrossPackConsistencyState.BLOCKED
    elif any(issue.severity == CrossPackConsistencySeverity.BLOCKING for issue in issues):
        state = CrossPackConsistencyState.BLOCKED
    elif any(issue.severity == CrossPackConsistencySeverity.ADVISORY for issue in issues):
        state = CrossPackConsistencyState.DEGRADED
    elif _is_truly_empty(inp):
        state = CrossPackConsistencyState.NOT_APPLICABLE
    else:
        state = CrossPackConsistencyState.OK

    if inp.config.strict and state == CrossPackConsistencyState.DEGRADED:
        state = CrossPackConsistencyState.BLOCKED

    # Determine reason codes.
    if state == CrossPackConsistencyState.OK:
        reason_codes = (CrossPackConsistencyReasonCode.OK,)
    elif state == CrossPackConsistencyState.NOT_APPLICABLE:
        reason_codes = (CrossPackConsistencyReasonCode.NOT_APPLICABLE,)
    elif safety_flags.has_unsafe_content or safety_flags.has_forbidden_terms:
        reason_codes = (CrossPackConsistencyReasonCode.SAFETY_BLOCKED,)
    else:
        reason_codes = (CrossPackConsistencyReasonCode.CONSISTENCY_DEGRADED,)
    if state == CrossPackConsistencyState.BLOCKED and inp.config.strict and any(
        issue.severity == CrossPackConsistencySeverity.ADVISORY for issue in issues
    ):
        reason_codes = (CrossPackConsistencyReasonCode.SAFETY_BLOCKED,)

    # 14. Data quality.
    blocking = sum(1 for i in issues if i.severity == CrossPackConsistencySeverity.BLOCKING)
    advisory = sum(1 for i in issues if i.severity == CrossPackConsistencySeverity.ADVISORY)
    info = sum(1 for i in issues if i.severity == CrossPackConsistencySeverity.INFO)
    data_quality = CrossPackConsistencyDataQuality(
        total_packs=len(inp.declarations),
        total_artifact_refs=len(inp.artifact_refs),
        total_section_refs=len(inp.section_refs),
        total_requirement_refs=len(inp.requirement_refs),
        total_state_claims=len(inp.state_claims),
        total_rules=len(inp.rules),
        total_issues=len(issues),
        blocking_issue_count=blocking,
        advisory_issue_count=advisory,
        info_issue_count=info,
        duplicate_id_count=sum(1 for i in issues if i.issue_type == CrossPackConsistencyIssueType.DUPLICATE_ID),
        orphan_ref_count=sum(1 for i in issues if i.issue_type == CrossPackConsistencyIssueType.ORPHAN_REF),
        stale_declaration_count=sum(1 for i in issues if i.issue_type == CrossPackConsistencyIssueType.STALE_DECLARATION),
        sections_present=len({rid for d in inp.declarations for rid in d.section_ref_ids}),
    )

    # 16. Sort all output tuples.
    declarations = tuple(sorted(inp.declarations, key=lambda d: _norm_id(d.pack_id)))
    artifact_refs = tuple(sorted(inp.artifact_refs, key=lambda r: _norm_id(r.ref_id)))
    section_refs = tuple(sorted(inp.section_refs, key=lambda r: _norm_id(r.ref_id)))
    requirement_refs = tuple(sorted(inp.requirement_refs, key=lambda r: _norm_id(r.ref_id)))
    state_claims = tuple(sorted(inp.state_claims, key=lambda c: (_norm_id(c.subject_id), _norm_id(c.pack_id))))
    rules = tuple(sorted(inp.rules, key=lambda r: (_norm_id(r.source_pack_id), r.rule_type.value)))
    issues = tuple(sorted(issues, key=lambda i: i.issue_id))
    reason_codes = tuple(sorted(set(reason_codes), key=lambda c: c.value))

    # 17. Report ID.
    report_id = _build_report_id(inp, generated_at)

    project_version = _resolve_project_version(inp)

    return CrossPackConsistencyReport(
        report_id=report_id,
        generated_at=generated_at,
        state=state,
        project_version=project_version,
        declarations=declarations,
        artifact_refs=artifact_refs,
        section_refs=section_refs,
        requirement_refs=requirement_refs,
        state_claims=state_claims,
        rules=rules,
        issues=issues,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        metadata=inp.metadata,
        notes="",
    )
