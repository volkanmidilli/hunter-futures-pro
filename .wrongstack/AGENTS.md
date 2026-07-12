# hunter-futures-pro WrongStack Agent Guide

## Project identity

hunter-futures-pro is an agent-first crypto futures research and execution-control platform.

Freqtrade is an execution bridge/layer only, not the decision brain.

No live trading is allowed by default.

## Safety invariants

The project is research/audit-first and fail-closed.

Never add:
- Binance live integration
- real exchange connection
- API keys or secrets
- live trading
- real orders
- leverage
- shorting
- real entry/exit execution logic
- feedback from reports/reviews/index/search into execution paths
- Web UI or dashboard unless a SPEC explicitly approves it
- database persistence unless a SPEC explicitly approves it
- config YAML or JSON schema unless a SPEC explicitly approves it
- Freqtrade strategy class or freqtrade import unless a SPEC explicitly approves it

File references in review/index/search artifacts are local strings only.
Do not traverse, open, follow, validate, or execute file references unless a SPEC explicitly approves it.

## Development rules

Use SPEC-driven development.

For each MVP:
1. Read the approved SPEC.
2. Build a task plan.
3. Implement one task at a time.
4. Run focused tests.
5. Run full suite before commit.
6. Update memory docs only after implementation commits.

Use pytest:
pytest -q --import-mode=importlib

Use Python src layout.
Do not use OCR.
Do not use network for implementation.

## Autonomous MVP Workflow

When continuing work on an MVP:

1. Read the current state:
   - `ROADMAP.md`
   - `docs/MVP_INDEX.md`
   - `docs/handoff/CURRENT_STATE.md`
   - `tasks/active.md`
   - The latest approved SPEC for the current MVP

2. Determine:
   - Current MVP and step
   - Last known commit
   - Allowed files
   - Required tests

3. Implement only the current step. Do not expand scope.

4. Run focused tests for the step, then run the full test suite before reporting completion.

5. Self-review against the SPEC and the boundaries listed below.

6. Fix blockers and rerun tests. If a blocker cannot be resolved within scope, stop and report.

7. Stop before commit.

8. Stop before tag.

9. Produce a final report with files changed, summary, boundary, and residual deviations.

### Commit and Tag Policy

- Never commit automatically.
- Never tag automatically.
- The human must provide the exact commit or tag command.

### Autonomous Safety Rules

- Do not inspect or traverse `data/` or `reports/`.
- Do not connect to exchanges, APIs, networks, or Freqtrade runtime.
- Do not start Web UIs, servers, databases, schedulers, or daemons.
- Do not emit trading signals or action commands.
- Do not make production-readiness, trading-readiness, approval, certification, recommendation, or suitability claims.
- Keep artifact refs as opaque strings; do not open, follow, validate, or execute them.

## Current MVP Context

- Current MVP: MVP-47 Cross-Artifact Consistency Engine
- SPEC: specs/SPEC-048-Cross-Artifact-Consistency-Engine.md
- SPEC commit: 4961d55 Add MVP-47 cross-artifact consistency spec
- Step 1 models/engine commit: 8eb368b Implement MVP-47 cross-artifact consistency engine
- Step 2 writer commit: 139738e Implement MVP-47 cross-artifact consistency writer
- Step 3 integration tests commit: c88e229 Add MVP-47 cross-artifact consistency integration tests
- Next: Step 4 memory/status update and finalization review
- Tag policy: v0.47.0-dev only after finalization review PASS and explicit human tag command

## Blocker protocol

If a task cannot be completed within the approved SPEC and current scope, stop and report:

BLOCKED: <one-line reason>
File: <path if applicable>
Reason: <specific issue>
Human decision needed: <specific question>

Do not silently expand scope.
Do not work around source defects in tests.
Do not repeatedly apply broad replacements.
Prefer patch or targeted edit over broad replace.
