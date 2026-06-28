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

## Current MVP

MVP-13 implements SPEC-014 Local Review Search / Query Layer.

Package:
src/hunter/review_search/

Allowed MVP-13 implementation sequence:
1. models and model tests
2. engine and engine tests
3. writer and writer tests
4. integration tests
5. final validation and version bump to 0.13.0-dev

MVP-13 search results are human-audit artifacts only.
They are not trading signals, not trade approvals, and must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.

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
