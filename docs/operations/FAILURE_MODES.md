# Failure Modes

## Project

Hunter Futures Pro

## Purpose

This file defines known failure modes and the expected safe behavior.

## Current Phase

v0.71.0-rc.2 — Research-only quantitative research framework. All MVPs 0–70 complete, Phase B (real Freqtrade compatibility) established, ZIP safety hardening applied. MVP-71 not started.

## General Rule

The system must fail closed. If something is missing, stale, invalid or unknown, execution must be blocked.

## Stale Memory Failure Modes

### Stale current-state documentation

If `docs/handoff/CURRENT_STATE.md` still describes an older MVP (e.g., MVP-32 or MVP-40) instead of the current state (MVP-47 / v0.47.0-dev pending tag):

- Detection: Compare `CURRENT_STATE.md` with `git tag --list "v0.*-dev"` and `ROADMAP.md`.
- Prevention: After every functional MVP, update `CURRENT_STATE.md` before committing the tag.
- Expected behavior: An agent reading `CURRENT_STATE.md` should see the correct current state. If the file is stale, the agent should stop and request a documentation update before proceeding with functional work.

### Stale version metadata

If `VERSION` or `pyproject.toml` version does not match the latest `v0.*-dev` tag:

- Detection: Compare `VERSION` and `pyproject.toml` version field with the latest tag.
- Prevention: Include version alignment in the finalization step of every MVP.
- Expected behavior: Correct the version metadata. No runtime behavior depends on these values.

### Stale active task

If `tasks/active.md` describes a completed MVP (e.g., MVP-40) rather than the current active work:

- Detection: Read `tasks/active.md` and compare with the latest commits and tags.
- Prevention: Update `tasks/active.md` after each MVP step.
- Expected behavior: The agent should update the active task description before starting new work.

### Missing v0.32.0-dev tag

The tag `v0.32.0-dev` is absent from the tag list. The finalization commit exists but was not tagged.

- Detection: `git tag --list "v0.*-dev"` shows a gap between `v0.31.0-dev` and `v0.33.0-dev`.
- Prevention: Include tag creation in future MVP finalization steps.
- Expected behavior: Record the anomaly; do not create the tag automatically. A separate human decision is required.

### Overall stale project memory drift

If multiple memory files simultaneously point to different states:

- Detection: An agent reads `CURRENT_STATE.md` (MVP-X), `tasks/active.md` (MVP-Y), `VERSION` (Z), and git tags (latest). If three sources disagree, drift is active.
- Prevention: Periodic project memory realignment (e.g., MVP-46) corrects all files in one coordinated step.
- Expected behavior: Align all memory files to the same state before proceeding with functional work.

## Excluded Artifact Area Failure Modes

### Accidental inspection of excluded local artifact areas

If an agent attempts to read, traverse, or modify `data/` or `reports/`:

- Detection: The agent's tool calls or code changes attempt to access these paths.
- Prevention: The active workflow safety rules explicitly forbid this. `ROADMAP.md`, `docs/MVP_INDEX.md`, and `CURRENT_STATE.md` all reference these areas as opaque and excluded.
- Expected behavior: Stop. Do not access these directories. If a report or artifact inside them is referenced, treat the reference as an opaque string. Do not follow, open, validate, or execute it.

### Readiness claim leakage

If generated documentation or comments claim production readiness, trading readiness, approval, certification, recommendation, or suitability:

- Detection: Review generated text for prohibited claims.
- Prevention: All SPECs and generated documentation explicitly forbid these claims.
- Expected behavior: Remove the claim before committing. Do not assert any form of system readiness that has not been explicitly approved by a human.

### Runtime scope creep

If an agent adds runtime features (trading logic, exchange connections, API calls, Freqtrade runtime code, servers, schedulers, daemons, databases, Web UI) without explicit human approval:

- Detection: Review diffs for any code changes outside documented documentation-only boundaries.
- Prevention: All MVPs include a "no runtime changes" boundary section.
- Expected behavior: Stop. Do not merge or commit runtime changes that are not explicitly requested and approved.

## Trading-Related Failure Modes

These rules apply when trading-related modules exist or are added in the future.

### Missing market data

Expected behavior: Block execution.

### Stale market data

Expected behavior: Block execution.

### Invalid JSON output

Expected behavior: Block execution.

### Missing regime file

Expected behavior: Block execution.

### Unknown market regime

Expected behavior: Block execution.

### Missing portfolio file

Expected behavior: Block execution.

### Pair not approved

Expected behavior: Block execution.

### Binance API failure

Expected behavior: Do not trade. Log the failure. Use last known data only for reporting, not for new execution approval.

### Freqtrade cannot read Hunter output

Expected behavior: Block new entries.

### WrongStack proposes unsafe live trading change

Expected behavior: Stop. Ask for human confirmation. Do not apply the change automatically.

## Foundation Failure Modes (Historical)

Original foundation-level failure modes preserved for reference:

- Missing README.md — stop and report.
- Missing PROJECT.md — stop and report.
- Missing AGENTS.md — stop and report.
- Missing .wrongstack/AGENTS.md — stop and report.
- Missing CURRENT_STATE.md — stop and ask for recreation.
- Missing task files — stop and ask for recreation.

## Safety Summary

- When unsure, block execution.
- When data is missing, block execution.
- When project memory is stale, correct it before working.
- When live trading is involved, require explicit human approval.
- When excluded artifact areas are referenced, treat references as opaque strings.
- When runtime scope creep is detected, stop and ask for human confirmation.
